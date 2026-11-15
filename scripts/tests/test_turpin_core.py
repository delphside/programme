"""turpinlib's core (delphside/programme#117, task T1): the front end's exits,
the model's results and forms, the profile and `APP.env`, the hooks, and the
delegation to `turpin-legacy`.

Test conditions derive from the design (§2 *Domain model*, §6, §8) and the test
design (R31, R48, R50, S71), not from the code.
"""

import contextlib
import io
import json
import os
import signal
import shutil
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import types
import unittest
from pathlib import Path
from unittest import mock

DELIVER = Path(__file__).resolve().parents[1] / "deliver"
sys.path.insert(0, str(DELIVER))

from turpinlib import cli, commands, gitrepo, hooks, model, profile, runlog  # noqa: E402
from turpinlib.model import (BusinessError, ErrorType, FormError, Outcome, ProfileError, Reason,  # noqa: E402
                             Result, TechnicalError, UnexpectedError, exit_status)

PROFILE = textwrap.dedent('''\
    application = "acme"

    [release]
    tag_prefix = "v"
    history_prefixes = ["prod-"]
    required_hooks = ["pre-deploy"]
    overridable = ["milestone"]

    [turpin]
    candidates = "acme/candidates"
    releases = "acme/releases"
    images = ["server", "web"]
    payload_image = "server"

    [turpin.build]
    on = "control-node"

    [[turpin.host_files]]
    src = "ops/backup.sh"
    dest = "/opt/acme/backup.sh"
    mode = "0755"

    [environments.preview]
    role = "preview"
    host = "controller"

    [environments.production]
    role = "production"
    ssh = "acme-prod"
    login = "oci-instance-principal"
    pull_timeout = 120
    ''')


def failing(case, error_class, call, *args):
    with case.assertRaises(error_class) as caught:
        call(*args)
    return caught.exception.result


class Isolated(unittest.TestCase):
    """A temporary folder, and the environment variables the tool reads, pointed at it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        patcher = mock.patch.dict(os.environ, {
            "TURPIN_LOG_DIR": str(self.dir / "logs"), "TURPIN_CONFIG_DIR": str(self.dir / "config")})
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(argv)
        return code, out.getvalue(), err.getvalue()


def fake_command(run, **declared):
    """A command module for the front end to find through `commands.COMMANDS`."""
    module = types.ModuleType("turpinlib.commands.fake")
    module.run = run
    module.FLAGS = declared.pop("FLAGS", {})
    module.GATE_FLAGS = declared.pop("GATE_FLAGS", ())
    module.MIN_ARGS, module.MAX_ARGS = declared.pop("ARGS", (0, 1))
    return mock.patch.dict(sys.modules, {"turpinlib.commands.fake": module}), \
        mock.patch.dict(commands.COMMANDS, {"fake": "fake"})


class FrontEnd(Isolated):
    def run_fake(self, run, argv, **declared):
        modules, registry = fake_command(run, **declared)
        with modules, registry:
            return self.run_main(["fake", *argv])

    def test_no_arguments_and_an_unknown_command_are_usage_errors(self):
        self.assertEqual(64, self.run_main([])[0])
        code, _, err = self.run_main(["bulid"])
        self.assertEqual(64, code)
        self.assertIn("bulid", err)

    def test_a_misspelt_flag_is_a_usage_error_naming_it_and_nothing_runs(self):
        ran = []
        code, _, err = self.run_fake(lambda args, ctx: ran.append(1), ["--chek"], FLAGS={"--check": "switch"})
        self.assertEqual(64, code)
        self.assertIn("--chek", err)
        self.assertEqual([], ran)

    def test_a_flag_that_sets_a_gate_aside_needs_its_reason(self):
        for argv in (["--emergency"], ["--emergency", "--check"], ["--set-aside", "milestone"]):
            with self.subTest(argv):
                code, _, err = self.run_fake(lambda args, ctx: None, argv,
                                             GATE_FLAGS=("--emergency", "--set-aside"),
                                             FLAGS={"--check": "switch"})
                self.assertEqual(64, code)
                self.assertIn(argv[0], err)

    def test_the_gate_flags_arrive_parsed_with_their_reasons(self):
        seen = []
        code, _, _ = self.run_fake(lambda args, ctx: seen.append(args) or Result.ok(),
                                   ["--set-aside", "milestone", "late", "--emergency", "fire", "x",
                                    "--wait=5", "--expect", "1.2.3"],
                                   GATE_FLAGS=("--emergency", "--set-aside"),
                                   FLAGS={"--wait": "optional", "--expect": "value"}, ARGS=(1, 1))
        self.assertEqual(0, code)
        args = seen[0]
        self.assertEqual([("milestone", "late")], args.set_aside)
        self.assertEqual({"--emergency": "fire"}, args.reasons)
        self.assertEqual({"--wait": "5", "--expect": "1.2.3"}, args.values)
        self.assertEqual(["x"], args.positional)

    def test_a_missing_argument_is_a_usage_error(self):
        self.assertEqual(64, self.run_fake(lambda args, ctx: None, [], ARGS=(1, 1))[0])

    def test_a_profile_error_exits_2_naming_the_key(self):
        def run(args, ctx):
            raise ProfileError.at(Reason.PROFILE_KEY_MISSING, "app-profile.toml: turpin.images is missing", key="turpin.images")
        code, _, err = self.run_fake(run, [])
        self.assertEqual(2, code)
        self.assertIn("turpin.images", err)

    def test_an_unexpected_exception_exits_70_and_its_text_is_in_the_run_log(self):
        def run(args, ctx):
            ctx.start_log("acme")
            raise RuntimeError("the cause of it")
        code, _, err = self.run_fake(run, [])
        self.assertEqual(70, code)
        self.assertIn("raise it as an issue", err)
        self.assertNotIn("the cause of it", err)
        log = next((self.dir / "logs" / "acme").glob("fake-*.log")).read_text()
        self.assertIn("RuntimeError: the cause of it", log)

    def test_a_business_error_exits_1_and_a_blip_75(self):
        for error, want in ((BusinessError.make(Reason.BAD_VALUE, "no"), 1),
                            (TechnicalError.make(Reason.GIT_UNREACHABLE, "later", blip=True), 75)):
            def run(args, ctx, error=error):
                raise error
            self.assertEqual(want, self.run_fake(run, [])[0])

    def test_the_result_is_logged_with_its_exit(self):
        def run(args, ctx):
            ctx.start_log("acme")
            return Result.ok("done")
        self.assertEqual(0, self.run_fake(run, [])[0])
        log = next((self.dir / "logs" / "acme").glob("fake-*.log")).read_text()
        self.assertIn('"event":"result"', log)
        self.assertIn('"exit":0', log)

    def test_the_run_log_holds_the_whole_result_cause_included(self):
        def run(args, ctx):
            ctx.start_log("acme")
            below = TechnicalError.make("TIMEOUT", "timed out", domain="vendor", blip=True, metadata={"attempts": 3})
            raise BusinessError.wrap(below, Reason.BAD_VALUE, "stopped", violations=(model.Violation("f", "v", "l", "r"),))
        self.run_fake(run, [])
        line = [json.loads(x) for x in next((self.dir / "logs" / "acme").glob("fake-*.log")).read_text().splitlines()][-1]
        self.assertEqual(1, line["exit"])
        self.assertEqual("TIMEOUT", line["result"]["cause"]["reason"])
        self.assertEqual("f", line["result"]["violations"][0]["field"])

    def test_a_command_that_ends_with_a_gate_unrun_refuses(self):
        def run(args, ctx):
            ctx.start_log("acme", expected=("lock", "state")).gate("lock", runlog.PASSED)
            return Result.ok()
        code, _, err = self.run_fake(run, [])
        self.assertEqual(1, code)
        self.assertIn("state", err)

    def test_an_interruption_exits_130(self):
        def run(args, ctx):
            raise KeyboardInterrupt
        self.assertEqual(130, self.run_fake(run, [])[0])


class Results(unittest.TestCase):
    def test_each_error_type_and_severity_has_its_exit(self):
        cases = [
            ("ok", Result(Outcome.OK), 0),
            ("warning", Result(Outcome.WARNING), 0),
            ("fatal business", Result(Outcome.FATAL, ErrorType.BUSINESS), 1),
            ("fatal fundamental", Result(Outcome.FATAL, ErrorType.TECHNICAL, blip=False), 2),
            ("fatal blip", Result(Outcome.FATAL, ErrorType.TECHNICAL, blip=True), 75),
            ("fatal unexpected", Result(Outcome.FATAL, ErrorType.UNEXPECTED), 70),
            ("error business, after the pivot", Result(Outcome.ERROR, ErrorType.BUSINESS), 3),
            ("error blip, after the pivot", Result(Outcome.ERROR, ErrorType.TECHNICAL, blip=True), 3),
            ("error unexpected, after the pivot", Result(Outcome.ERROR, ErrorType.UNEXPECTED), 3),
        ]
        for name, result, want in cases:
            with self.subTest(name):
                self.assertEqual(want, exit_status(result))

    def test_an_error_is_raised_with_its_result_and_its_cause(self):
        below = TechnicalError.make("TIMEOUT", "timed out", domain="vendor", blip=True)
        above = BusinessError.make(Reason.BAD_VALUE, "wrapped", cause=below.result)
        self.assertEqual("vendor", above.result.cause.domain)
        self.assertEqual(75, exit_status(below.result))

    def test_a_result_serialises_whole_with_its_cause_and_errors(self):
        inner = TechnicalError.make("TIMEOUT", "timed out", domain="vendor", blip=True,
                                    metadata={"attempts": 3})
        outer = BusinessError.wrap(inner, Reason.BAD_VALUE, "wrapped",
                                   violations=(model.Violation("f", "v", "l", "r"),))
        data = outer.result.to_json()
        self.assertEqual(("business", "BAD_VALUE", "turpin"), (data["type"], data["reason"], data["domain"]))
        self.assertEqual([{"field": "f", "value": "v", "limit": "l", "reason": "r"}], data["violations"])
        self.assertEqual(("vendor", True, {"attempts": 3}),
                         (data["cause"]["domain"], data["cause"]["blip"], data["cause"]["metadata"]))
        done = Result(Outcome.ERROR, ErrorType.UNEXPECTED, errors=(outer.result,)).to_json()
        self.assertEqual("wrapped", done["errors"][0]["message"])
        json.dumps(done)

    def test_context_is_added_keeping_type_reason_and_cause(self):
        inner = TechnicalError.make("TIMEOUT", "t", blip=True)
        outer = TechnicalError.wrap(inner, Reason.GIT_FAILED, "m", blip=True, metadata={"a": 1})
        more = outer.with_context(image="server")
        self.assertEqual({"a": 1, "image": "server"}, dict(more.result.metadata))
        self.assertEqual((outer.result.reason, outer.result.cause, 75),
                         (more.result.reason, more.result.cause, exit_status(more.result)))

    def test_a_result_that_contradicts_itself_is_refused(self):
        with self.assertRaises(ValueError):
            Result(Outcome.FATAL)                              # no type
        with self.assertRaises(ValueError):
            Result(Outcome.FATAL, ErrorType.TECHNICAL)         # no blip
        with self.assertRaises(ValueError):
            Result(Outcome.OK, ErrorType.BUSINESS)

    def test_reasons_are_unique_in_their_domain(self):
        values = [reason.value for reason in Reason]
        self.assertEqual(len(values), len(set(values)))


class Forms(Isolated):
    """R48: a domain type checks its own form where the value is made; the reader
    of an argument or the version file makes a bad one a business error, and any
    other is unexpected (design §3)."""

    BAD = [("a bad version", model.Version.parse, "1.2"),
           ("a version with a v", model.Version.parse, "v1.2.3"),
           ("a short digest", model.Digest, "sha256:abc"),
           ("an upper-case digest", model.Digest, "sha256:" + "A" * 64),
           ("a non-hexadecimal commit", model.check_commit, "g" * 40),
           ("a short commit", model.check_commit, "abc1234")]

    def test_a_good_value_is_made(self):
        self.assertEqual("1.2.3", str(model.Version.parse("1.2.3")))
        self.assertLess(model.Version.parse("0.9.10"), model.Version.parse("0.10.2"))
        self.assertEqual("sha256:" + "a" * 64, str(model.Digest("sha256:" + "a" * 64)))
        self.assertEqual("b" * 40, model.Build("b" * 40, {}).commit)

    def test_a_bad_value_is_a_form_error_not_a_programme_error(self):
        for name, make, text in self.BAD:
            with self.subTest(name):
                with self.assertRaises(FormError) as caught:
                    make(text)
                self.assertNotIsInstance(caught.exception, model.ProgrammeError)
                self.assertEqual(text, caught.exception.violation.value)

    def test_from_an_argument_or_the_version_file_it_is_business_naming_the_source(self):
        for where, name, make, text in (("the argument REF", *self.BAD[5]), ("the version file app.toml", *self.BAD[0])):
            with self.subTest(where):
                result = failing(self, BusinessError, model.read_input, where, make, text)
                self.assertEqual(1, exit_status(result))
                self.assertIn(where, result.message)
                self.assertEqual(text, result.violations[0].value)
                self.assertEqual(where, result.metadata["source"])

    def test_anywhere_else_it_is_unexpected_naming_the_field(self):
        for name, make, text in self.BAD:
            with self.subTest(name):
                try:
                    make(text)
                except FormError as exc:
                    result = exc.unexpected("a host's state").result
                self.assertEqual(70, exit_status(result))
                self.assertIn("a host's state", result.message)

    def test_a_request_with_a_bad_digest_that_nobody_translated_exits_70_keeping_its_field(self):
        def run(args, ctx):
            ctx.start_log("acme")
            model.Digest("sha256:not-a-digest")      # a field of a request, made unchecked
        modules, registry = fake_command(run)
        with modules, registry:
            code, _, err = self.run_main(["fake"])
        self.assertEqual(70, code)
        self.assertIn("raise it as an issue", err)
        self.assertIn("digest", err)
        line = json.loads(next((self.dir / "logs" / "acme").glob("fake-*.log")).read_text().splitlines()[-1])
        self.assertEqual("digest", line["result"]["violations"][0]["field"])

    def test_a_build_with_a_short_commit_is_refused(self):
        with self.assertRaises(FormError):
            model.Build("abc1234", {})


class Profiles(Isolated):
    def test_a_profile_is_read(self):
        read = profile.parse(PROFILE, "app-profile.toml")
        self.assertEqual(("server", "web"), read.images)
        self.assertEqual("controller", read.build_on)            # control-node still works
        self.assertEqual("controller", read.environments["preview"].machine)
        production = read.environments["production"]
        self.assertEqual(("acme-prod", 120, True), (production.machine, production.pull_timeout, production.host_files))
        self.assertEqual(model.CredentialKind.OCI_INSTANCE_PRINCIPAL, production.login)
        self.assertEqual(model.CredentialKind.DOCKER_CONFIG, read.login)
        self.assertEqual("0755", read.host_files[0].mode)

    def test_a_required_key_missing_is_a_fundamental_error_naming_it(self):
        text = PROFILE.replace('candidates = "acme/candidates"\n', "")
        result = failing(self, ProfileError, profile.parse, text, "app-profile.toml")
        self.assertEqual(2, exit_status(result))
        self.assertEqual("turpin.candidates", result.metadata["key"])
        self.assertIn("turpin.candidates", result.message)

    def test_a_fault_names_the_file_it_was_read_from(self):
        text = PROFILE.replace('candidates = "acme/candidates"\n', "")
        self.assertIn("my-profile.toml", failing(self, ProfileError, profile.parse, text, "my-profile.toml").message)
        result = failing(self, ProfileError, profile.read_at_commit, self.dir, "f" * 40)
        self.assertIsNotNone(result.cause)                      # git's failure is the cause
        self.assertIn("app-profile.toml at ffffffffffff", result.message)

    def test_a_pull_timeout_that_is_not_a_number_names_the_key(self):
        for bad in ('"slow"', "true", "1.5"):
            with self.subTest(bad):
                text = PROFILE.replace("pull_timeout = 120", f"pull_timeout = {bad}")
                result = failing(self, ProfileError, profile.parse, text, "app-profile.toml")
                self.assertEqual(2, exit_status(result))
                self.assertEqual("environments.production.pull_timeout", result.metadata["key"])

    def test_an_unknown_role_or_login_is_refused(self):
        for old, new in (('role = "preview"', 'role = "staging"'),
                         ('login = "oci-instance-principal"', 'login = "magic"')):
            with self.subTest(new):
                failing(self, ProfileError, profile.parse, PROFILE.replace(old, new), "p")

    def test_a_file_that_does_not_parse_is_refused(self):
        self.assertEqual(2, exit_status(failing(self, ProfileError, profile.parse, "= nope", "p")))

    def test_the_profile_at_a_commit_is_read_from_git_not_the_working_tree(self):
        repo = self.dir / "work"
        repo.mkdir()
        env = {**os.environ, "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.test",
               "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.test"}
        for command in (["init", "-q", "-b", "main"], ["add", "app-profile.toml"], ["commit", "-q", "-m", "x"]):
            (repo / "app-profile.toml").write_text(PROFILE)
            subprocess.run(["git", "-C", str(repo), *command], check=True, env=env)
        sha = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True,
                             capture_output=True, text=True).stdout.strip()
        (repo / "app-profile.toml").write_text(PROFILE.replace('"acme"', '"changed"', 1))
        self.assertEqual("acme", profile.read_at_commit(repo, sha).application)
        self.assertEqual("changed", profile.read_working_tree(repo).application)
        self.assertEqual(2, exit_status(failing(self, ProfileError, profile.read_at_commit, repo, "f" * 40)))

    def test_an_app_env_is_read(self):
        (self.dir / "config").mkdir()
        (self.dir / "config" / "acme.env").write_text(
            '# the registry\nTURPIN_REGISTRY=reg.test/ns\nexport OTHER="quoted value"\n\nTHIRD=\'x\'\n')
        values = profile.read_app_env("acme")
        self.assertEqual({"TURPIN_REGISTRY": "reg.test/ns", "OTHER": "quoted value", "THIRD": "x"}, values)
        self.assertEqual({}, profile.read_app_env("absent"))

    def test_an_app_env_line_that_does_not_parse_is_refused_naming_the_line(self):
        (self.dir / "config").mkdir()
        (self.dir / "config" / "acme.env").write_text("GOOD=1\nthis is not an assignment\n")
        result = failing(self, ProfileError, profile.read_app_env, "acme")
        self.assertEqual(2, exit_status(result))
        self.assertEqual(2, result.metadata["line"])

    def test_a_key_a_command_needs_is_required_of_the_app_env(self):
        self.assertEqual("reg", profile.require({"TURPIN_REGISTRY": "reg"}, "TURPIN_REGISTRY", "acme.env"))
        result = failing(self, ProfileError, profile.require, {}, "TURPIN_REGISTRY", "acme.env")
        self.assertEqual("TURPIN_REGISTRY", result.metadata["key"])


class Hooks(Isolated):
    def hook(self, body):
        path = self.dir / "hook"
        path.write_text("#!/usr/bin/env python3\nimport os, sys, json\n" + textwrap.dedent(body))
        path.chmod(0o755)
        return path

    @contextlib.contextmanager
    def own_stdin(self):
        """Our standard input is a file, so a hook that inherited it would show."""
        saved = os.dup(0)
        with open(self.dir / "input", "w+") as stdin:
            os.dup2(stdin.fileno(), 0)
            try:
                yield
            finally:
                os.dup2(saved, 0)
                os.close(saved)

    def environment(self, **changes):
        base = dict(app="acme", env="rehearsal", role="rehearsal", sha="a" * 40, version="0.10.2",
                    state="/var/lib/turpin/acme/rehearsal", images={"server": "sha256:" + "1" * 64, "web-app": "sha256:" + "2" * 64})
        return hooks.HookEnv(**{**base, **changes})

    def test_a_hook_gets_the_environment_stdin_from_dev_null_and_a_group_of_its_own(self):
        path = self.hook('''
            print(json.dumps({"env": {k: v for k, v in os.environ.items()
                                      if k.startswith("TURPIN_") and not k.endswith("_DIR")},
                              "stdin": os.readlink("/proc/self/fd/0"), "leader": os.getpgid(0) == os.getpid()}))
            ''')
        with self.own_stdin():
            result = hooks.run_hook(path, self.environment(extra={"TURPIN_DEPLOY": "4"}))
        self.assertTrue(result.passed)
        got = __import__("json").loads(result.output)
        self.assertEqual("/dev/null", got["stdin"])
        self.assertTrue(got["leader"])
        self.assertEqual({"TURPIN_APP": "acme", "TURPIN_ENV": "rehearsal", "TURPIN_ROLE": "rehearsal",
                          "TURPIN_SHA": "a" * 40, "TURPIN_VERSION": "0.10.2",
                          "TURPIN_STATE": "/var/lib/turpin/acme/rehearsal",
                          "TURPIN_IMAGE_SERVER": "sha256:" + "1" * 64,
                          "TURPIN_IMAGE_WEB_APP": "sha256:" + "2" * 64, "TURPIN_DEPLOY": "4"}, got["env"])

    def test_build_gets_its_creation_time_and_local_only_when_asked(self):
        path = self.hook('print(os.environ.get("TURPIN_CREATED"), os.environ.get("TURPIN_LOCAL"))')
        self.assertEqual("None None\n", hooks.run_hook(path, self.environment()).output)
        local = hooks.run_hook(path, self.environment(created="2026-11-15T10:00:00Z", local=True))
        self.assertEqual("2026-11-15T10:00:00Z 1\n", local.output)

    def test_exit_75_is_not_yet_and_stops_as_a_blip(self):
        result = hooks.run_hook(self.hook("sys.exit(75)"), self.environment())
        self.assertTrue(result.not_yet)
        self.assertFalse(result.passed)
        error = failing(self, TechnicalError, result.require)
        self.assertEqual(75, exit_status(error))

    def test_any_other_failure_is_a_business_error_naming_the_hook(self):
        result = hooks.run_hook(self.hook("sys.exit(3)"), self.environment())
        self.assertFalse(result.not_yet)
        error = failing(self, BusinessError, result.require)
        self.assertEqual(1, exit_status(error))
        self.assertIn("hook", error.message)

    def test_a_passing_hook_requires_nothing(self):
        hooks.run_hook(self.hook("pass"), self.environment()).require()

    def test_a_hook_past_its_limit_is_killed_with_its_whole_group(self):
        mark = self.dir / "grandchild"
        path = self.hook(f"""
            import subprocess, time
            subprocess.Popen(["sh", "-c", "sleep 2; echo alive > {mark}"])
            time.sleep(30)
            """)
        error = failing(self, TechnicalError, hooks.run_hook, path, self.environment(), None, 0.5)
        self.assertEqual(75, exit_status(error))
        time.sleep(2.5)
        self.assertFalse(mark.exists(), "the grandchild outlived its group")

    def interrupt_once_started(self, started, times=1):
        """Ctrl+C this process `times` times, once the hook has written `started`."""
        def send():
            while not started.exists():
                time.sleep(0.02)
            for _ in range(times):
                os.kill(os.getpid(), signal.SIGINT)
                time.sleep(0.2)
        thread = threading.Thread(target=send, daemon=True)
        thread.start()
        return thread

    def test_an_interrupted_hook_is_still_held_to_its_limit(self):
        started = self.dir / "started"
        path = self.hook(f"import time\nopen({str(started)!r}, 'w').close()\ntime.sleep(30)")
        thread = self.interrupt_once_started(started, times=2)
        began = time.monotonic()
        error = failing(self, TechnicalError, hooks.run_hook, path, self.environment(), None, 2)
        thread.join()
        self.assertEqual(75, exit_status(error))
        self.assertEqual(Reason.HOOK_TIMED_OUT.value, error.reason)
        self.assertLess(time.monotonic() - began, 6)

    def test_a_hook_killed_by_a_signal_is_unexpected(self):
        for body in ("os.kill(os.getpid(), 9)", "sys.exit(137)"):
            with self.subTest(body):
                result = hooks.run_hook(self.hook(body), self.environment())
                self.assertEqual(70, exit_status(failing(self, UnexpectedError, result.require)))

    def test_an_interruption_waits_for_the_hook_to_finish_then_goes_on(self):
        mark, started = self.dir / "mark", self.dir / "started"
        path = self.hook(f"""
            import time
            open({str(started)!r}, "w").close()
            time.sleep(1)
            open({str(mark)!r}, "w").write("done")
            """)
        thread = self.interrupt_once_started(started)
        with self.assertRaises(KeyboardInterrupt):
            hooks.run_hook(path, self.environment())
        thread.join()
        self.assertEqual("done", mark.read_text())

    def test_a_required_hook_missing_or_not_executable_refuses_and_another_is_a_no_op(self):
        folder = self.dir / "hooks"
        folder.mkdir()
        failing(self, BusinessError, hooks.find_hook, folder, "smoke", True)
        self.assertIsNone(hooks.find_hook(folder, "smoke"))
        (folder / "smoke").write_text("#!/bin/sh\n")
        failing(self, BusinessError, hooks.find_hook, folder, "smoke")
        (folder / "smoke").chmod(0o755)
        self.assertEqual(folder / "smoke", hooks.find_hook(folder, "smoke", True))


class RunLogs(Isolated):
    def test_the_gates_each_command_expects(self):
        self.assertEqual(("lock", "rollback-target"), runlog.expected_gates("rollback"))
        self.assertEqual((), runlog.expected_gates("status"))
        production = runlog.expected_gates("deploy", model.Role.PRODUCTION)
        self.assertIn("production-record", production)
        self.assertNotIn("rehearsal-level", production)
        self.assertIn("rehearsal-level", runlog.expected_gates("deploy", model.Role.REHEARSAL))
        self.assertNotIn("smoke", runlog.expected_gates("deploy", model.Role.PREVIEW, check=True))
        self.assertIn("smoke", runlog.expected_gates("deploy", model.Role.PREVIEW))

    def test_only_the_last_runs_are_kept(self):
        with mock.patch("turpinlib.settings.RUN_LOGS_KEPT", 2), \
                mock.patch("turpinlib.runlog.os.getpid", side_effect=[1, 2, 3, 4]):
            for _ in range(4):
                runlog.RunLog.start("acme", "build", ["x"])
        kept = sorted(p.name for p in (self.dir / "logs" / "acme").glob("build-*.log"))
        self.assertEqual(2, len(kept))


class Delegation(Isolated):
    """A subcommand with no module under `commands/` runs `turpin-legacy`, with
    the arguments unchanged. In T1 that is every subcommand."""

    def copy_tool(self, legacy_body):
        tool = self.dir / "tool"
        shutil.copytree(DELIVER / "turpinlib", tool / "turpinlib", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy(DELIVER / "turpin", tool / "turpin")
        legacy = tool / "turpin-legacy"
        legacy.write_text(legacy_body)
        legacy.chmod(0o755)
        return tool

    ARGS = ["deploy", "rehearsal", "abc 123", "--set-aside", "milestone", "a reason", "", "--wait=5", "*"]

    def test_the_entry_script_passes_its_arguments_through_unchanged(self):
        tool = self.copy_tool('#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "$OUT"\nexit 7\n')
        out = self.dir / "args"
        done = subprocess.run([str(tool / "turpin"), *self.ARGS], env={**os.environ, "OUT": str(out)})
        self.assertEqual(7, done.returncode)            # legacy's own exit is ours
        self.assertEqual(self.ARGS, out.read_text().split("\n")[:-1])

    def test_a_symlink_to_the_entry_script_finds_the_package_and_legacy(self):
        tool = self.copy_tool('#!/usr/bin/env bash\necho legacy "$1"\n')
        (self.dir / "bin").mkdir()
        (self.dir / "bin" / "turpin").symlink_to(tool / "turpin")
        done = subprocess.run([str(self.dir / "bin" / "turpin"), "list", "production"], capture_output=True, text=True)
        self.assertEqual(("legacy list\n", 0), (done.stdout, done.returncode))

    def test_every_subcommand_not_yet_ported_is_delegated(self):
        for command in (c for c in cli.KNOWN_COMMANDS if c not in commands.COMMANDS):
            with self.subTest(command), mock.patch("turpinlib.cli.os.execv") as execv, \
                    mock.patch("turpinlib.cli._restore_for_exec"):
                cli.main([command, "--odd", "x"])
                execv.assert_called_once_with(cli.LEGACY, [str(cli.LEGACY), command, "--odd", "x"])

    def test_legacy_gets_default_signals_the_callers_locale_and_the_three_streams(self):
        tool = self.copy_tool("#!/usr/bin/env bash\n"
                              "grep SigIgn /proc/self/status\n"
                              "echo \"ctype=${LC_CTYPE-unset}\"\n"
                              "read -r line; echo \"in=$line\"; echo err >&2\n")
        env = {k: v for k, v in os.environ.items() if k not in ("LC_ALL", "LC_CTYPE", "LANG", "LANGUAGE")}
        done = subprocess.run([str(tool / "turpin"), "list", "x"], input="hello\n", env=env,
                              capture_output=True, text=True)
        ignored = int(done.stdout.split("SigIgn:")[1].split()[0], 16)
        self.assertEqual(0, ignored & ((1 << (signal.SIGPIPE - 1)) | (1 << (signal.SIGXFSZ - 1))))
        self.assertIn("ctype=unset", done.stdout)
        self.assertIn("in=hello", done.stdout)
        self.assertEqual("err\n", done.stderr)

    def test_the_entry_script_below_python_3_11_says_so_and_exits_2(self):
        tool = self.copy_tool("#!/bin/sh\n")
        text = (tool / "turpin").read_text().replace("(3, 11)", "(99, 0)")
        (tool / "turpin").write_text(text)
        done = subprocess.run([str(tool / "turpin"), "list"], capture_output=True, text=True)
        self.assertEqual((2, ""), (done.returncode, done.stdout))
        self.assertIn("3.11", done.stderr)

    def test_the_legacy_script_is_beside_the_entry_script(self):
        self.assertEqual(DELIVER / "turpin-legacy", cli.LEGACY)
        self.assertTrue(os.access(cli.LEGACY, os.X_OK))

    def test_a_legacy_script_that_cannot_run_is_a_fundamental_error(self):
        with mock.patch("turpinlib.cli.os.execv", side_effect=FileNotFoundError("gone")), \
                mock.patch("turpinlib.cli._restore_for_exec"), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(2, cli.main(["build"]))

    def test_help_is_answered_here_and_names_every_command(self):
        code, out, _ = self.run_main(["--help"])
        self.assertEqual(0, code)
        for command in cli.KNOWN_COMMANDS:
            self.assertIn(f"turpin {command}", out)


class GitFailures(Isolated):
    """A refusal by the remote is fundamental, exit 2; a connection failure a blip,
    exit 75 (design §6, docs/1.10)."""

    def git_saying(self, text):
        bin_dir = self.dir / "bin"
        bin_dir.mkdir(exist_ok=True)
        stub = bin_dir / "git"
        stub.write_text(f"#!/bin/sh\necho {text!r} >&2\nexit 128\n")
        stub.chmod(0o755)
        return mock.patch.dict(os.environ, {"PATH": f"{bin_dir}:{os.environ['PATH']}"})

    def test_what_the_remote_refuses_is_fundamental_even_beside_a_connection_text(self):
        for text in ("git@github.com: Permission denied (publickey).\nfatal: Could not read from remote repository.",
                     "Host key verification failed.\nfatal: Could not read from remote repository.",
                     "ssh: Could not resolve hostname github.test: Name or service not known",
                     "fatal: unable to access 'https://x/': The requested URL returned error: 403",
                     "fatal: unable to access 'https://x/': The requested URL returned error: 401",
                     "fatal: Authentication failed for 'https://x/'"):
            with self.subTest(text), self.git_saying(text):
                result = failing(self, TechnicalError, gitrepo.fetch_tags, self.dir)
                self.assertEqual(2, exit_status(result))

    def test_a_connection_failure_is_a_blip(self):
        for text in ("fatal: unable to access 'https://x/': Could not resolve host: x",
                     "ssh: connect to host x port 22: Connection timed out\nfatal: Could not read from remote repository.",
                     "ssh: connect to host x port 22: Connection refused", "Connection reset by peer"):
            with self.subTest(text), self.git_saying(text):
                self.assertEqual(75, exit_status(failing(self, TechnicalError, gitrepo.fetch_tags, self.dir)))

    def test_any_other_failure_is_fundamental_and_keeps_the_text_out_of_the_message(self):
        with self.git_saying("fatal: bad object"):
            result = failing(self, TechnicalError, gitrepo.show, self.dir, "x", "f")
        self.assertEqual(2, exit_status(result))
        self.assertNotIn("bad object", result.message)
        self.assertIn("bad object", result.metadata["tool_text"])

    def test_git_has_its_own_timeout_setting(self):
        from turpinlib import settings
        self.assertEqual(settings.GIT_CALL_TIMEOUT, gitrepo.git.__kwdefaults__["timeout"])


class RecordOfTag(Isolated):
    def test_a_read_the_board_model_cannot_make_is_technical_not_an_unknown_version(self):
        repo = self.dir / "work"
        repo.mkdir()
        env = {**os.environ, "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.test",
               "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.test"}
        for command in (["init", "-q", "-b", "main"], ["commit", "-q", "--allow-empty", "-m", "x"],
                        ["tag", "-a", "v1.0.0", "-m", "x"]):
            subprocess.run(["git", "-C", str(repo), *command], check=True, env=env)
        from board.sources import Unavailable
        fake = mock.Mock(tag_record=mock.Mock(side_effect=Unavailable("git failed")))
        with mock.patch("turpinlib.gitrepo.board.repo_module", return_value=fake):
            self.assertEqual(2, exit_status(failing(self, TechnicalError, gitrepo.record_of_tag, repo, "v1.0.0")))

    def test_a_tag_that_is_absent_is_a_business_error_and_a_plain_tag_has_no_record(self):
        repo = self.dir / "work"
        repo.mkdir()
        env = {**os.environ, "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.test",
               "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.test"}
        for command in (["init", "-q", "-b", "main"], ["commit", "-q", "--allow-empty", "-m", "x"],
                        ["tag", "-a", "v0.10.1", "-m", "an old release"]):
            subprocess.run(["git", "-C", str(repo), *command], check=True, env=env)
        failing(self, BusinessError, gitrepo.record_of_tag, repo, "v9.9.9")
        self.assertIsNone(gitrepo.record_of_tag(repo, "v0.10.1"))

    def test_a_record_is_read_through_the_board_model(self):
        import json
        repo = self.dir / "work"
        repo.mkdir()
        env = {**os.environ, "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.test",
               "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.test"}
        sha = "c" * 40
        record = {"record": 1, "application": "acme", "version": "0.10.2", "commit": sha,
                  "images": {"server": "sha256:" + "1" * 64}, "made": "2026-11-02T19:04:00Z"}
        subprocess.run(["git", "-C", str(repo), "init", "-q", "-b", "main"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-q", "--allow-empty", "-m", "x"], check=True, env=env)
        for tag, body in (("v0.10.2", record), ("v0.10.3", {**record, "record": 2}),
                          ("v0.10.4", {**record, "commit": "short"})):
            subprocess.run(["git", "-C", str(repo), "tag", "-a", tag, "-m", json.dumps(body)], check=True, env=env)
        read = gitrepo.record_of_tag(repo, "v0.10.2")
        self.assertEqual((model.Version(0, 10, 2), sha), (read.version, read.commit))
        self.assertEqual(record, {k: v for k, v in read.to_json().items() if k in record})
        self.assertEqual(1, exit_status(failing(self, BusinessError, gitrepo.record_of_tag, repo, "v0.10.3")))
        bad = failing(self, UnexpectedError, gitrepo.record_of_tag, repo, "v0.10.4")
        self.assertEqual(70, exit_status(bad))
        self.assertEqual("short", bad.violations[0].value)


if __name__ == "__main__":
    unittest.main()
