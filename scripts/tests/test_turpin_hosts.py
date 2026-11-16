"""turpinlib's calls to `turpin-host` and the two commands that read or change a host
(delphside/programme#117, task T4): `hosts.py`, `turpin status` and `turpin rollback`.

Test conditions derive from the design (§6 *Interruption* and its `ssh` table, §11 *The last
request*, §13) and the test design (R50 to R61, S90 to S94, S105 to S113), not from the code.
`ssh` and `turpin-host` are stub executables that answer from a plan and record what they
were sent.
"""

import io
import json
import os
import re
import signal
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from .test_turpin_core import DELIVER, PROFILE, Isolated

from turpinlib import commands, gitrepo, hosts, model, profile, runlog, settings  # noqa: E402
from turpinlib.model import (BusinessError, ErrorType, Outcome, Reason, Result,  # noqa: E402
                             TechnicalError, UnexpectedError, exit_status)

UUID4 = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")

# A stand-in for `ssh` and `turpin-host`: it answers call N from plan[N] (the last one repeats),
# and keeps what it was sent: its arguments, the first line of its input, and whether the input
# was still open a moment later.
STUB = '''#!/usr/bin/env python3
import json, os, select, sys, time
base = os.environ["STUB_DIR"]
n = len(os.listdir(base + "/calls"))
open(base + "/calls/%d" % n, "w").close()
plan = json.load(open(base + "/plan.json"))
step = plan[min(n, len(plan) - 1)]
line = sys.stdin.readline()
ready = select.select([sys.stdin], [], [], 0.3)[0]
rest = sys.stdin.read() if ready else None   # what was left to read, if it was there to read at once
with open(base + "/sent.log", "a") as log:
    log.write(json.dumps({"argv": sys.argv[1:], "line": line, "open": not ready, "rest": rest, "pgid": os.getpgrp()}) + "\\n")
if step.get("wait_for_end"):
    sys.stdin.read()
    print(step.get("stdout_after_end", "the input ended"))
if step.get("hang"):
    open(base + "/hung.pid", "w").write(str(os.getpid()))
    time.sleep(60)
for text in step.get("stderr", []):
    print(text, file=sys.stderr)
print(step.get("stdout", ""), end="")
sys.exit(step.get("exit", 0))
'''

RESULT = {"outcome": "fatal", "type": "business", "blip": None, "reason": "ROLLBACK_NO_PREVIOUS",
          "domain": "turpin", "message": "there is no previous deploy to go back to. Fallback: stop it",
          "metadata": {}, "violations": []}


class Stubbed(Isolated):
    """`ssh` first on the PATH and `TURPIN_HOST_BIN` both run the stub."""

    def setUp(self):
        super().setUp()
        self.stub = self.dir / "stub"
        (self.stub / "calls").mkdir(parents=True)
        bindir = self.dir / "bin"
        bindir.mkdir()
        for name in ("ssh", "turpin-host"):
            (bindir / name).write_text(STUB)
            (bindir / name).chmod(0o755)
        patcher = mock.patch.dict(os.environ, {
            "PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}", "STUB_DIR": str(self.stub),
            "TURPIN_HOST_BIN": str(bindir / "turpin-host")})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.slept = []
        sleeper = mock.patch.object(hosts, "_sleep", self.slept.append)
        sleeper.start()
        self.addCleanup(sleeper.stop)
        self.log = runlog.RunLog.start("acme", "test", [])

    def plan(self, *steps):
        (self.stub / "plan.json").write_text(json.dumps(list(steps)))

    def sent(self):
        path = self.stub / "sent.log"
        return [json.loads(text) for text in path.read_text().splitlines()] if path.exists() else []

    def requests(self):
        return [json.loads(s["line"]) for s in self.sent()]

    def events(self, kind):
        return [json.loads(text) for text in self.log.path.read_text().splitlines()
                if json.loads(text)["event"] == kind]

    def failing(self, call):
        with self.assertRaises(model.ProgrammeError) as caught:
            call()
        return caught.exception.result


class SshErrors(Stubbed):
    """§6's table: `ssh`'s 255 is mapped by the error text it prints."""

    def call(self, text, **kwargs):
        self.plan({"exit": 255, "stderr": [text]})
        return hosts.call_host("acme-prod", ["status", "acme", "production", "--json"], log=self.log, **kwargs)

    def test_a_refused_key_a_host_key_and_an_unknown_host_are_fundamental_each_naming_its_fix(self):
        for text, reason, names in (
                ("acme-prod: Permission denied (publickey).", Reason.SSH_PERMISSION_DENIED, "agent"),
                ("Host key verification failed.", Reason.SSH_HOST_KEY_REFUSED, "known_hosts"),
                ("ssh: Could not resolve hostname acme-prod: Name or service not known",
                 Reason.SSH_HOST_UNRESOLVED, "ssh configuration")):
            with self.subTest(text):
                result = self.failing(lambda: self.call(text))
                self.assertEqual((ErrorType.TECHNICAL, False, reason.value, 2),
                                 (result.type, result.blip, result.reason, exit_status(result)))
                self.assertIn(names, result.message)
                self.assertNotIn(text, result.message)         # no tool's text in a message
                self.assertEqual(text, result.metadata["tool_text"])

    def test_a_lost_connection_is_a_blip_exit_75(self):
        for text in ("Connection timed out", "Connection refused", "Connection reset by peer",
                     "Broken pipe", "Connection closed by remote host"):
            with self.subTest(text):
                result = self.failing(lambda: self.call(text))
                self.assertEqual((True, Reason.SSH_CONNECTION_LOST.value, 75),
                                 (result.blip, result.reason, exit_status(result)))

    def test_any_other_255_is_unexpected_exit_70_with_the_text_for_the_run_log(self):
        result = self.failing(lambda: self.call("kex_exchange_identification: something new"))
        self.assertEqual((ErrorType.UNEXPECTED, 70, Reason.SSH_UNEXPECTED.value),
                         (result.type, exit_status(result), result.reason))
        self.assertIn("something new", result.metadata["tool_text"])
        self.assertNotIn("something new", result.message)

    def test_a_fundamental_error_is_never_retried(self):
        self.failing(lambda: self.call("Permission denied", retry=True))
        self.assertEqual(1, len(self.sent()))
        self.assertEqual([], self.slept)

    def test_a_command_not_found_on_the_host_names_host_install(self):
        self.plan({"exit": 127, "stderr": ["bash: turpin-host: command not found"]})
        result = self.failing(lambda: hosts.call_host("acme-prod", ["status", "a", "e"], log=self.log))
        self.assertEqual((Reason.HOST_COMMAND_MISSING.value, 2), (result.reason, exit_status(result)))
        self.assertIn("host-install", result.message)


class Retries(Stubbed):
    """§6: a blip is retried where a retry is safe, three attempts waiting 2 seconds, then 4."""

    DROPPED = {"exit": 255, "stderr": ["client_loop: send disconnect: Broken pipe"]}

    def test_a_dropped_connection_is_retried_and_a_request_keeps_its_id_and_is_marked_repeat(self):
        self.plan(self.DROPPED, self.DROPPED, {"exit": 0, "stdout": "ok\n"})
        made = []

        def request(repeat):
            made.append(repeat)
            return {"request_id": "abc", "repeat": repeat}

        call = hosts.call_host("acme-prod", ["rollback", "acme", "production"], log=self.log, request=request,
                               retry=True, echo_stdout=False)
        self.assertEqual("ok\n", call.stdout)
        self.assertEqual([False, True, True], made)
        self.assertEqual([2, 4], self.slept)
        self.assertEqual([("abc", False), ("abc", True), ("abc", True)],
                         [(r["request_id"], r["repeat"]) for r in self.requests()])

    def test_each_retry_is_logged_with_what_it_was(self):
        self.plan(self.DROPPED, {"exit": 0})
        hosts.call_host("acme-prod", ["status", "a", "e"], log=self.log, retry=True)
        (event,) = self.events("retry")
        self.assertEqual(("acme-prod", 1, Reason.SSH_CONNECTION_LOST.value, 2),
                         (event["machine"], event["attempt"], event["reason"], event["wait"]))

    def test_retries_that_run_out_are_a_blip_exit_75_naming_where_the_call_stopped(self):
        self.plan(self.DROPPED)
        result = self.failing(lambda: hosts.call_host("acme-prod", ["status", "a", "e"], log=self.log, retry=True,
                                                      where="run turpin status production"))
        self.assertEqual(3, len(self.sent()))
        self.assertEqual([2, 4], self.slept)
        self.assertEqual((True, 75), (result.blip, exit_status(result)))
        self.assertIn("run turpin status production", result.message)

    def test_a_call_that_is_not_safe_to_repeat_is_not_retried(self):
        self.plan(self.DROPPED)
        result = self.failing(lambda: hosts.call_host("acme-prod", ["build", "x"], log=self.log, retry=False))
        self.assertEqual(1, len(self.sent()))
        self.assertEqual(75, exit_status(result))

    def test_a_call_that_hangs_is_killed_with_its_group_and_retried_as_a_blip(self):
        self.plan({"hang": True})
        result = self.failing(lambda: hosts.call_host("acme-prod", ["status", "a", "e"], log=self.log, retry=True,
                                                      timeout=0.6))
        self.assertEqual(3, len(self.sent()))
        self.assertEqual((Reason.HOST_CALL_TIMED_OUT.value, 75), (result.reason, exit_status(result)))
        pid = int((self.stub / "hung.pid").read_text())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    def test_a_host_that_answered_is_not_retried_whatever_it_said(self):
        self.plan({"exit": 75, "stderr": ["turpin-host: still held"]})
        result = self.failing(lambda: hosts.call_host("acme-prod", ["deploy", "a", "e"], log=self.log, retry=True,
                                                      request={"request_id": "x", "repeat": False}))
        self.assertEqual(1, len(self.sent()))
        self.assertEqual(75, exit_status(result))


class Protocol(Stubbed):
    def run_host(self, step, machine="acme-prod", **kwargs):
        self.plan(step)
        return hosts.call_host(machine, ["deploy", "acme", "production"], log=self.log, **kwargs)

    def test_a_request_is_one_line_and_the_input_is_held_open_while_the_call_runs(self):
        self.run_host({"exit": 0}, request={"request_id": "r", "repeat": False})
        (sent,) = self.sent()
        self.assertEqual({"request_id": "r", "repeat": False}, json.loads(sent["line"]))
        self.assertTrue(sent["open"])

    def test_a_call_with_no_request_gets_an_empty_line_held_open(self):
        self.run_host({"exit": 0})
        (sent,) = self.sent()
        self.assertEqual(("\n", True), (sent["line"], sent["open"]))

    def test_the_call_runs_in_a_process_group_of_its_own(self):
        self.run_host({"exit": 0})
        self.assertNotEqual(os.getpgrp(), self.sent()[0]["pgid"])

    def test_data_goes_in_then_the_closing_line_and_the_input_ends(self):
        self.plan({"exit": 0})
        hosts.call_host("acme-prod", ["allowlist", "acme"], log=self.log, data="a\tb\nc\td")
        (sent,) = self.sent()
        self.assertEqual("a\tb\n", sent["line"])
        # the stub read one line; the rest, then the closing line, and the end of the input, followed
        self.assertEqual(("c\td\n# turpin: end\n", False), (sent["rest"], sent["open"]))

    def test_the_closing_line_is_the_one_the_design_names(self):
        self.assertEqual("# turpin: end", hosts.CLOSING_LINE)

    def test_gates_go_to_the_run_log_and_not_to_the_operator(self):
        stdout_err = []
        step = {"exit": 0, "stderr": ["@gate lock passed", "turpin-host: a word for the operator",
                                      "@gate pre-deploy set-aside"]}
        with mock.patch.object(sys, "stderr") as err:
            err.write.side_effect = stdout_err.append
            call = self.run_host(step)
        self.assertEqual([("lock", "passed"), ("pre-deploy", "set-aside")], call.gates)
        shown = "".join(stdout_err)
        self.assertIn("a word for the operator", shown)
        self.assertNotIn("@gate", shown)
        self.assertEqual([("lock", "passed"), ("pre-deploy", "set-aside")],
                         [(e["name"], e["result"]) for e in self.events("gate")])
        self.assertEqual(["lock", "pre-deploy"], self.log.ran)

    def test_the_hosts_result_object_is_read_from_its_last_line_and_not_shown(self):
        step = {"exit": 3, "stderr": ["@result " + json.dumps({**RESULT, "outcome": "error", "type": "technical",
                                                               "blip": False, "reason": "HOST_PRUNE_FAILED"})]}
        call = self.run_host(step)       # done with errors: returned, not raised
        self.assertEqual((3, Outcome.ERROR, "HOST_PRUNE_FAILED"), (call.code, call.result.outcome, call.result.reason))
        self.assertEqual("", call.stderr)

    def test_each_exit_status_is_mapped_by_its_type_taking_the_hosts_reason_and_message(self):
        cases = ((1, "business", None, BusinessError, "ROLLBACK_NO_PREVIOUS", 1),
                 (2, "technical", False, TechnicalError, "STATE_LAYOUT_BASH", 2),
                 (75, "technical", True, TechnicalError, "HOST_LOCK_WAIT_LIMIT", 75),
                 (70, "unexpected", None, UnexpectedError, "HOST_REQUEST_ID_INVALID", 70))
        for code, kind, blip, error, reason, exit_ in cases:
            with self.subTest(code):
                told = {**RESULT, "type": kind, "blip": blip, "reason": reason, "message": f"told {code}"}
                with self.assertRaises(error) as caught:
                    self.run_host({"exit": code, "stderr": ["@result " + json.dumps(told)]})
                self.assertEqual((reason, f"told {code}", exit_), (caught.exception.result.reason,
                                                                   caught.exception.result.message,
                                                                   exit_status(caught.exception.result)))

    def test_a_result_of_another_type_than_the_exit_is_not_trusted(self):
        told = {**RESULT, "type": "business", "reason": "SOMETHING_ELSE"}
        result = self.failing(lambda: self.run_host({"exit": 2, "stderr": ["@result " + json.dumps(told)]}))
        self.assertEqual((Reason.HOST_FUNDAMENTAL.value, 2), (result.reason, exit_status(result)))

    def test_a_status_with_no_result_is_generic_and_a_signals_status_is_unexpected(self):
        result = self.failing(lambda: self.run_host({"exit": 1, "stderr": ["turpin-host: refused"]}))
        self.assertEqual((Reason.HOST_REFUSED.value, "turpin-host: refused"), (result.reason, result.message))
        result = self.failing(lambda: self.run_host({"exit": 137}))
        self.assertEqual((ErrorType.UNEXPECTED, 70), (result.type, exit_status(result)))

    def test_a_host_that_read_the_interruption_exits_130_and_so_does_the_caller(self):
        with self.assertRaises(KeyboardInterrupt):
            self.run_host({"exit": 130})

    def test_a_ctrl_c_closes_the_hosts_input_and_the_call_is_waited_for_to_its_end(self):
        timer = threading.Timer(0.8, os.kill, (os.getpid(), signal.SIGINT))
        timer.start()
        self.addCleanup(timer.cancel)
        call = self.run_host({"wait_for_end": True, "exit": 0, "stdout_after_end": "saw the end"},
                             request={"request_id": "r", "repeat": False}, echo_stdout=False)
        self.assertTrue(call.interrupted)
        self.assertEqual("saw the end\n", call.stdout)
        self.assertEqual(0, call.code)

    def test_a_second_ctrl_c_changes_nothing(self):
        for delay in (0.8, 1.0):
            timer = threading.Timer(delay, os.kill, (os.getpid(), signal.SIGINT))
            timer.start()
            self.addCleanup(timer.cancel)
        call = self.run_host({"wait_for_end": True, "exit": 0}, echo_stdout=False)
        self.assertEqual(0, call.code)


class Status(unittest.TestCase):
    META = {"state": "finished", "pending": None, "last_request": {"request_id": "r", "outcome": "finished"},
            "current": {"n": 2, "sha": "a" * 40, "version": "0.10.2", "images": {"server": "sha256:" + "1" * 64},
                        "record": None, "deployed": "2026-11-01T00:00:00Z"},
            "previous": None, "running": ["sha256:" + "1" * 64], "host_files": [{"dest": "/x", "status": "equal"}],
            "deploys": [{"n": 1, "deployed": None}, {"n": 2, "deployed": "2026-11-01T00:00:00Z"}]}

    def test_the_hosts_status_is_read_as_what_the_environment_runs(self):
        status = hosts.parse_status(json.dumps({"outcome": "ok", "metadata": self.META}))
        deployed = status.deployed
        self.assertEqual(("finished", "r", "finished", 2, "0.10.2"),
                         (deployed.state, deployed.request_id, deployed.outcome, deployed.current.number,
                          deployed.current.version))
        self.assertEqual(model.Digest("sha256:" + "1" * 64), deployed.current.build.images["server"])
        self.assertIsNone(deployed.previous)
        self.assertEqual((("/x", "equal"),), status.host_files)
        self.assertEqual(((1, None), (2, "2026-11-01T00:00:00Z")), status.deploys)

    def test_a_deploy_under_way_is_the_pending_build(self):
        meta = {**self.META, "pending": {**self.META["current"], "n": 3}}
        self.assertEqual(3, hosts.parse_status(json.dumps({"metadata": meta})).deployed.pending.number)

    def test_a_status_that_is_not_a_result_object_is_unexpected(self):
        for text in ("not json", json.dumps({"outcome": "ok"}), json.dumps({"metadata": {"current": {"sha": "short"}}})):
            with self.subTest(text), self.assertRaises(model.ProgrammeError) as caught:
                hosts.parse_status(text)
            self.assertEqual(70, exit_status(caught.exception.result))


class CommandsBase(Stubbed):
    """`turpin rollback` and `status` run through the front end against a profile."""

    def setUp(self):
        super().setUp()
        self.text = PROFILE.replace('fallback', 'fallback')
        for patcher in (mock.patch.object(profile, "repo_dir", lambda: self.dir),
                        mock.patch.object(profile, "read_working_tree",
                                          lambda repo: profile.parse(self.text, "app-profile.toml"))):
            patcher.start()
            self.addCleanup(patcher.stop)

    def main(self, *argv):
        return self.run_main(list(argv))


class RollbackCommand(CommandsBase):
    GATES = ["@gate lock passed", "@gate rollback-target passed"]

    def test_both_commands_are_registered(self):
        self.assertLessEqual({"status", "rollback"}, set(commands.COMMANDS))

    def test_the_request_names_its_id_the_role_s_repository_and_the_fallback(self):
        self.text = self.text.replace('images = ["server", "web"]', 'images = ["server", "web"]\nfallback = "stop it"')
        self.plan({"exit": 0, "stderr": self.GATES})
        code, _, _ = self.main("rollback", "production")
        self.assertEqual(0, code)
        (sent,) = self.sent()
        self.assertEqual(["acme-prod", "turpin-host rollback acme production"], sent["argv"][-2:])
        request = json.loads(sent["line"])
        self.assertRegex(request["request_id"], UUID4)
        self.assertEqual(
            {"repeat": False, "app": "acme", "env": "production", "role": "production",
             "login": "oci-instance-principal", "repo": "acme/releases", "pull_timeout": 120, "url": "",
             "wait": None, "lock_wait": None, "fallback": "stop it"},
            {k: v for k, v in request.items() if k not in ("request_id", "lock", "project")})

    def test_the_request_carries_the_environments_url_for_the_hooks(self):                          # T3, R66
        self.assertIn("[environments.production]", self.text)
        self.text = self.text.replace("[environments.production]", '[environments.production]\nurl = "https://acme.test"', 1)
        self.plan({"exit": 0, "stderr": self.GATES})
        self.assertEqual(0, self.main("rollback", "production")[0])
        (sent,) = self.sent()
        self.assertEqual("https://acme.test", json.loads(sent["line"])["url"])

    def test_a_non_production_environment_reads_candidates_and_a_missing_fallback_is_said(self):
        self.plan({"exit": 0, "stderr": self.GATES})
        self.main("rollback", "preview")
        request = self.requests()[0]
        self.assertEqual(("acme/candidates", "controller", "the application has named no fallback"),
                         (request["repo"], "controller" if "ssh" not in self.sent()[0]["argv"] else "ssh",
                          request["fallback"]))

    def test_a_dropped_connection_is_retried_under_the_same_request_id_marked_repeat(self):
        drop = {"exit": 255, "stderr": ["Connection reset by peer"]}
        self.plan(drop, {"exit": 0, "stderr": self.GATES})
        code, _, _ = self.main("rollback", "production")
        self.assertEqual(0, code)
        first, second = self.requests()
        self.assertEqual((first["request_id"], False, True), (second["request_id"], first["repeat"], second["repeat"]))
        self.assertEqual([2], self.slept)

    def test_a_repeat_asks_the_host_to_wait_for_the_lock_as_long_as_settings_say(self):
        self.plan({"exit": 255, "stderr": ["Connection reset by peer"]}, {"exit": 0, "stderr": self.GATES})
        self.main("rollback", "production")
        first, second = self.requests()
        self.assertEqual((None, settings.WAIT_DEFAULT_MINUTES), (first["lock_wait"], second["lock_wait"]))

    def test_each_command_has_its_own_request_id(self):
        self.plan({"exit": 0, "stderr": self.GATES})
        self.main("rollback", "production")
        self.main("rollback", "production")
        first, second = self.requests()
        self.assertNotEqual(first["request_id"], second["request_id"])

    def test_a_refusal_exits_1_with_the_hosts_reason_and_the_gates_it_ran_are_logged(self):
        self.plan({"exit": 1, "stderr": self.GATES[:1] + ["turpin-host: " + RESULT["message"],
                                                          "@result " + json.dumps(RESULT)]})
        code, _, err = self.main("rollback", "production")
        self.assertEqual(1, code)
        self.assertEqual(1, err.count("no previous deploy"))      # the host's line and turpin's are one message
        self.assertNotIn("@result", err)
        logs = sorted((self.dir / "logs" / "acme").glob("rollback-*.log"))
        lines = [json.loads(text) for text in logs[-1].read_text().splitlines()]
        self.assertEqual("ROLLBACK_NO_PREVIOUS", [e for e in lines if e["event"] == "result"][-1]["result"]["reason"])
        self.assertIn("lock", [e["name"] for e in lines if e["event"] == "gate"])

    def test_a_host_line_that_says_more_than_the_result_is_shown(self):
        self.plan({"exit": 1, "stderr": ["turpin-host: a detail the result lacks", "@result " + json.dumps(RESULT)]})
        err = self.main("rollback", "production")[2]
        self.assertIn("a detail the result lacks", err)
        self.assertIn("no previous deploy", err)

    def test_an_interruption_while_the_host_waits_for_the_lock_says_nothing_changed_and_the_rerun(self):
        said = "interrupted while waiting for the lock: no further step is started"
        result = {**RESULT, "type": "technical", "blip": True, "reason": "HOST_INTERRUPTED", "message": said}
        self.plan({"exit": 130, "stderr": self.GATES[:1] + ["turpin-host: " + said, "@result " + json.dumps(result)]})
        code, _, err = self.main("rollback", "production")
        self.assertEqual(130, code)
        self.assertIn("interrupted while waiting for the lock: nothing changed; run turpin rollback production again",
                      err)
        self.assertEqual(1, err.count(said))                   # the host's own line, once

    def test_any_other_interruption_says_the_call_may_have_reached_the_host_and_names_status(self):
        self.plan({"exit": 130, "stderr": self.GATES[:1]})       # a 130 with no result of the host's
        code, _, err = self.main("rollback", "production")
        self.assertEqual(130, code)
        self.assertIn("the call may have reached the host; run turpin status production", err)
        self.assertNotIn("nothing changed", err)

    def test_a_ctrl_c_in_a_retry_backoff_names_status_not_a_rerun_of_nothing_changed(self):
        self.plan({"exit": 255, "stderr": ["Connection reset by peer"]})
        with mock.patch.object(hosts, "_sleep", side_effect=KeyboardInterrupt):
            code, _, err = self.main("rollback", "production")
        self.assertEqual(130, code)
        self.assertIn("run turpin status production", err)
        self.assertNotIn("nothing changed", err)

    def test_a_call_that_ended_with_errors_shows_the_hosts_message_once(self):
        # exit 3 raises nothing, so nothing else prints what the host said
        told = {**RESULT, "outcome": "error", "type": "technical", "blip": False, "reason": "HOST_PRUNE_FAILED",
                "message": "the prune failed: nothing else was affected"}
        self.plan({"exit": 3, "stderr": self.GATES + ["turpin-host: " + told["message"], "@result " + json.dumps(told)]})
        code, _, err = self.main("rollback", "production")
        self.assertEqual(0, code)
        self.assertEqual(1, err.count("the prune failed: nothing else was affected"))

    def test_ssh_s_own_text_on_255_is_not_shown_to_the_operator(self):
        self.plan({"exit": 255, "stderr": ["Connection reset by peer 10.9.8.7 port 22 (private detail)"]})
        code, out, err = self.main("rollback", "production")
        self.assertEqual(75, code)
        for text in (out, err):
            self.assertNotIn("10.9.8.7", text)
            self.assertNotIn("private detail", text)
        self.plan({"exit": 255, "stderr": ["rehearsal: Permission denied (publickey). private detail"]})
        code, out, err = self.main("rollback", "production")
        self.assertEqual(2, code)
        self.assertNotIn("private detail", out + err)

    def test_a_retry_that_keeps_failing_exits_75_naming_status(self):
        self.plan({"exit": 255, "stderr": ["Connection timed out"]})
        code, _, err = self.main("rollback", "production")
        self.assertEqual(75, code)
        self.assertIn("turpin status production", err)
        self.assertEqual(3, len(self.sent()))

    def test_an_environment_the_profile_lacks_is_refused_naming_the_profile(self):
        code, _, err = self.main("rollback", "nowhere")
        self.assertEqual(1, code)
        self.assertIn("no environment nowhere", err)
        self.assertEqual([], self.sent())

    def test_an_interruption_after_the_rollback_began_runs_to_its_end_and_exits_0_saying_so(self):
        self.plan({"wait_for_end": True, "exit": 0, "stderr": self.GATES, "stdout_after_end": "rolled back"})
        timer = threading.Timer(0.8, os.kill, (os.getpid(), signal.SIGINT))
        timer.start()
        self.addCleanup(timer.cancel)
        code, _, err = self.main("rollback", "production")
        self.assertEqual(0, code)
        self.assertIn("after the rollback began", err)

    def test_an_interruption_the_host_stopped_for_exits_130(self):
        self.plan({"wait_for_end": True, "exit": 130, "stderr": ["@gate lock passed"]})
        timer = threading.Timer(0.8, os.kill, (os.getpid(), signal.SIGINT))
        timer.start()
        self.addCleanup(timer.cancel)
        self.assertEqual(130, self.main("rollback", "production")[0])

    def test_a_missing_environment_is_a_usage_error(self):
        self.assertEqual(64, self.main("rollback")[0])


class StatusCommand(CommandsBase):
    def reply(self, **changes):
        meta = {**Status.META, **changes}
        self.plan({"exit": 0, "stdout": json.dumps({"outcome": "ok", "metadata": meta})})

    def setUp(self):
        super().setUp()
        self.record = None
        for patcher in (mock.patch.object(gitrepo, "fetch_tags", lambda repo: None),
                        mock.patch.object(gitrepo, "tags", lambda repo, prefix: ["v0.10.2"] if prefix == "v" else []),
                        mock.patch.object(gitrepo, "record_of_tag", lambda repo, tag: self.record)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_the_state_the_build_the_digests_and_the_host_files_are_shown(self):
        self.reply()
        code, out, _ = self.main("status", "production")
        self.assertEqual(0, code)
        self.assertEqual(
            ["environment: production (production)", "state: finished", "last request: r finished",
             f"current: deploy 2 commit {'a' * 40} version 0.10.2 smoke passed 2026-11-01T00:00:00Z",
             f"image server sha256:{'1' * 64}",
             "running: the current digests", "record: none matches", "host file /x: equal"],
            out.splitlines())
        self.assertEqual(["acme-prod", "turpin-host status acme production --json"], self.sent()[0]["argv"][-2:])

    def test_digests_that_differ_from_the_running_ones_are_said(self):
        self.reply(running=["sha256:" + "2" * 64])
        out = self.main("status", "production")[1]
        self.assertIn(f"running: DIFFERS from the current digests (sha256:{'2' * 64})", out)

    def test_the_record_whose_images_are_the_current_ones_is_named(self):
        self.reply()
        self.record = model.ReleaseRecord.from_json({
            "application": "acme", "version": "0.10.2", "commit": "a" * 40, "made": "2026-11-01T00:00:00Z",
            "images": {"server": "sha256:" + "1" * 64}})
        self.assertIn("record: 0.10.2", self.main("status", "production")[1])

    def test_a_host_part_way_through_a_deploy_shows_what_is_pending_and_the_request_that_is_running(self):
        # section 11: the state `changing: deploy migrate` with `pending` and a request left `running`,
        # which is what the host's refusal sends the owner to turpin status to judge
        self.reply(state="changing: deploy migrate", last_request={"request_id": "q-1", "outcome": "running"},
                   pending={"n": 3, "sha": "b" * 40, "version": "0.11.0", "images": {"server": "sha256:" + "3" * 64},
                            "record": None, "deployed": None},
                   previous={"n": 1, "sha": "c" * 40, "version": "", "images": {"server": "sha256:" + "4" * 64},
                             "record": None, "deployed": "2026-10-01T00:00:00Z"})
        out = self.main("status", "production")[1].splitlines()
        self.assertEqual("state: changing: deploy migrate", out[1])
        self.assertEqual(f"pending: deploy 3 commit {'b' * 40} version 0.11.0 smoke not passed", out[2])
        self.assertEqual("last request: q-1 running", out[3])
        self.assertIn(f"previous: deploy 1 commit {'c' * 40} version - smoke passed 2026-10-01T00:00:00Z", out)

    def test_a_first_deploy_killed_part_way_shows_its_pending_deploy_though_nothing_is_current(self):
        self.reply(state="preparing: deploy-folder", current=None, previous=None, running=[], host_files=[],
                   last_request={"request_id": "q-2", "outcome": "running"},
                   pending={"n": 1, "sha": "b" * 40, "version": "", "images": {}, "record": None, "deployed": None})
        out = self.main("status", "production")[1].splitlines()
        self.assertEqual([f"pending: deploy 1 commit {'b' * 40} version - smoke not passed",
                          "last request: q-2 running", "current: none"], out[2:])

    def test_a_pending_deploy_whose_folder_was_not_written_says_so(self):
        self.reply(state="preparing: deploy-folder", pending={"n": 4}, previous=None)
        out = self.main("status", "production")[1].splitlines()
        self.assertIn("pending: deploy 4 (folder not written)", out)

    def test_a_host_with_no_deploy_says_so(self):
        self.reply(state=None, current=None, previous=None, running=[], host_files=[], deploys=[])
        out = self.main("status", "production")[1]
        self.assertIn("state: none (no turpin deploy yet)", out)
        self.assertIn("current: none", out)

    def test_a_status_call_that_is_dropped_is_retried_and_shown(self):
        meta = json.dumps({"outcome": "ok", "metadata": Status.META})
        self.plan({"exit": 255, "stderr": ["Connection closed by 1.2.3.4"]}, {"exit": 0, "stdout": meta})
        self.assertEqual(0, self.main("status", "production")[0])
        self.assertEqual(2, len(self.sent()))

    def test_a_status_call_that_keeps_failing_exits_75_naming_the_rerun(self):
        self.plan({"exit": 255, "stderr": ["Connection reset by peer"]})
        code, _, err = self.main("status", "production")
        self.assertEqual(75, code)
        self.assertIn("turpin status production", err)
        self.assertEqual([2, 4], self.slept)

    def test_a_status_that_hangs_exits_75(self):
        self.plan({"hang": True})
        with mock.patch.object(hosts.settings, "HOST_CALL_TIMEOUT", 0.5):
            code, _, err = self.main("status", "production")
        self.assertEqual(75, code)

    def test_an_environment_the_profile_lacks_is_refused(self):
        self.assertEqual(1, self.main("status", "nowhere")[0])


class Reasons(unittest.TestCase):
    """The host's reasons are the Python enumeration's: one place for each (docs/1.10)."""

    def test_every_reason_the_host_scripts_name_is_a_member_of_the_enumeration(self):
        known = {member.value for member in Reason}
        named = set()
        for path in (DELIVER / "turpin-host", DELIVER / "lib" / "common.sh", *(DELIVER / "payload").iterdir()):
            text = path.read_text()
            named |= set(re.findall(r"\bREASON=([A-Z][A-Z_]+)", text))
            named |= set(re.findall(r"\bnote_result (?:error|gate) ([A-Z][A-Z_]+)", text))
            named |= set(re.findall(r'"(HOST_[A-Z_]+)"', text))
            named |= set(re.findall(r"\b(HOOK_(?:MISSING|NOT_EXECUTABLE|REFUSED|NOT_YET))\b", text))
        self.assertGreater(len(named), 15)
        self.assertEqual(set(), named - known)


if __name__ == "__main__":
    unittest.main()
