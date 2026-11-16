"""`turpin release`, the board model called in-process, and the bump of `main`
(delphside/programme#117, task T7): what each step decides.

Test conditions derive from the design (§4 *The board model*, §6 *Errors, results and the pivot*
and *Interruption*, §9 *Gates and checks*, §10 *The release and its record*) and the test design (R16
to R25, R42, R55, R62, R63, S18 to S28, S50 to S53, S86, S114, S115), not from the code. The board is
faked at its model (`board.release_module` gives a stand-in `release` module), the registry at the
port, the hosts at `hosts.host_status`, and the release copier at `remote.call_turpin`; `git` is a real
repository in a temporary folder with a real bare remote, so a tag and the bump are really pushed.
"""

import contextlib
import io
import json
import os
import signal
import stat
import subprocess
import textwrap
import threading
import types
import unittest
from pathlib import Path
from unittest import mock

from board import release as model_release
from board.sources import Unavailable

from .test_turpin_build import FakePort, digest
from .test_turpin_core import Isolated

from turpinlib import board, gitrepo, hosts, model, remote  # noqa: E402
from turpinlib.model import (Build, DeployedBuild, Deployed, ErrorType, Outcome, ReleaseRecord, Reason,  # noqa: E402
                             TechnicalError, Version)
from turpinlib.registry import connect  # noqa: E402

PROFILE = textwrap.dedent('''\
    application = "acme"

    [versions]
    stamp_form = "app <X.Y.Z> api <M.N>: <subject>"

    [versions.app]
    file = "app.toml"
    pattern = '^version = "([^"]+)"'

    [versions.api]
    file = "api.txt"
    pattern = '^api = "([^"]+)"'

    [versions.bump]
    files = ["app.toml"]
    required = ["app.toml"]

    [versions.deployed]
    path = "/health"
    field = "app_version"

    [release]
    tag_prefix = "v"
    history_prefixes = ["prod-"]
    announcement = "Released in v"
    required_checks = ["e2e"]
    required_hooks = ["release-check"]
    overridable = ["milestone", "release-check"]

    [turpin]
    candidates = "acme/candidates"
    releases = "acme/releases"
    images = ["server", "web"]

    [turpin.release]
    copy_on = "copier"
    copy_login = "docker-config"

    [environments.rehearsal]
    role = "rehearsal"
    ssh = "acme-rehearsal"

    [environments.production]
    role = "production"
    ssh = "acme-prod"
    url = "http://prod.test"
    ''')

HOOK = '#!/bin/sh\necho "$TURPIN_ROLE $TURPIN_ENV $TURPIN_VERSION $TURPIN_SHA" >> "$HOOK_LOG"\nexit "$(cat "$HOOK_EXIT" 2>/dev/null || echo 0)"\n'
BUMP_HOOK = '#!/bin/sh\necho "$TURPIN_VERSION" >> "$HOOK_LOG.bump"\n'
GIT_ENV = {"GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@e.test",
           "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@e.test"}
SMOKE_PASSED = "2026-11-14T10:00:00Z"


class Port(FakePort):
    """The registry port, with the records releases holds."""

    def __init__(self):
        super().__init__()
        self.records: dict[str, ReleaseRecord] = {}

    def read_record(self, repository, version):
        self.calls.append(("read_record", str(version)))
        return self.records.get(str(version))


class World(Isolated):
    """A repository with its remote, and everything a release talks to, faked."""

    def setUp(self):
        super().setUp()
        self.work, self.remote = self.dir / "work", self.dir / "remote.git"
        self.git("init", "-q", "--bare", str(self.remote), cwd=self.dir)
        self.work.mkdir()
        self.git("init", "-q", "-b", "main", cwd=self.work)
        self.git("remote", "add", "origin", str(self.remote), cwd=self.work)
        (self.work / "app-profile.toml").write_text(PROFILE)
        (self.work / "app.toml").write_text('version = "0.10.2"\n')
        (self.work / "api.txt").write_text('api = "1.0"\n')
        (self.work / "turpin" / "hooks").mkdir(parents=True)
        self.hook("release-check", HOOK)
        self.sha = self.commit("first")
        self.port = Port()
        self.hook_log, self.hook_exit = self.dir / "hook.log", self.dir / "hook.exit"
        patch_env = mock.patch.dict(os.environ, {
            "TURPIN_REPO": str(self.work), "HOOK_LOG": str(self.hook_log), "HOOK_EXIT": str(self.hook_exit),
            **GIT_ENV})
        patch_env.start()
        self.addCleanup(patch_env.stop)
        # what the fakes were asked, in order, and what is true when they were
        self.events: list[tuple] = []
        self.rehearsal = self.rehearsal_ran(self.sha)
        self.production = None
        self.promote_error: Exception | None = None
        self.checks = (True, {"e2e": "success"}, [])
        self.gate_result = self.passing_gate()
        self.publish_result = {"retrospective": "not asked", "release": "created", "failed": []}
        self.next_result = {"milestone": "0.10.3", "created": True, "moved": [], "failed": []}
        self.board_error: dict[str, Exception] = {}       # a call of the model to the error it raises
        for patcher in (
                mock.patch.object(connect, "connect", side_effect=lambda app, component, log, bind=True: self.port),
                mock.patch.object(hosts, "host_status", side_effect=self.host_status),
                mock.patch.object(remote, "call_turpin", side_effect=self.copier),
                mock.patch.object(board, "release_module", side_effect=lambda: self.board_model())):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.build(self.sha)

    # ------------------------------------------------------------------ git

    @staticmethod
    def git(*args, cwd):
        env = dict(os.environ, **GIT_ENV)
        return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
                              env=env).stdout.strip()

    def hook(self, name, text):
        path = self.work / "turpin" / "hooks" / name
        path.write_text(text)
        path.chmod(0o755)

    def commit(self, message, *, branch="main", version=None):
        if version is not None:
            (self.work / "app.toml").write_text(f'version = "{version}"\n')
        (self.work / f"file-{len(message)}-{abs(hash(message)) % 10000}.txt").write_text(message)
        self.git("add", "-A", cwd=self.work)
        self.git("commit", "-q", "--allow-empty", "-m", message, cwd=self.work)
        self.git("push", "-q", "origin", branch, cwd=self.work)
        return self.git("rev-parse", "HEAD", cwd=self.work)

    def text_tag(self, tag, sha):
        """A release made before the tool: a tag with no JSON message."""
        self.git("tag", "-a", "-m", f"Release {tag}", tag, sha, cwd=self.work)
        self.git("push", "-q", "origin", f"refs/tags/{tag}", cwd=self.work)

    def remote_tag(self, tag):
        return self.git("tag", "-l", tag, cwd=self.remote)

    def tag_message(self, tag):
        return self.git("tag", "-l", tag, "--format=%(contents)", cwd=self.remote)

    def remote_version(self):
        text = self.git("show", "main:app.toml", cwd=self.remote)
        return text.split('"')[1]

    # ---------------------------------------------------------- the fakes

    def build(self, sha):
        """The commit's images are in candidates."""
        from turpinlib.model import Image
        for name in ("server", "web"):
            self.port.present[(sha, name)] = Image(name, digest(sha + name), sha, "2026-11-01T00:00:00Z")

    def rehearse(self, sha):
        """The commit is built and rehearsal ran it, smoke passed."""
        self.build(sha)
        self.rehearsal = self.rehearsal_ran(sha)

    def images(self, sha):
        return {name: digest(sha + name) for name in ("server", "web")}

    def rehearsal_ran(self, sha, state="finished", smoke=SMOKE_PASSED):
        return Deployed(state, None, None, None,
                        DeployedBuild(Build(sha, self.images(sha)), None, smoke, 1, ""), None)

    def production_runs(self, version, sha):
        record = ReleaseRecord("acme", Version.parse(version), sha, self.images(sha), "2026-10-01T00:00:00Z")
        self.production = Deployed("finished", None, None, None,
                                   DeployedBuild(Build(sha, self.images(sha)), record, SMOKE_PASSED, 1, version), None)

    def host_status(self, machine, app, env, log):
        self.events.append(("status", env))
        deployed = {"rehearsal": self.rehearsal, "production": self.production}[env]
        if deployed is None:
            deployed = Deployed("", None, None, None, None, None)
        return hosts.HostStatus(deployed, (), (), ())

    def copier(self, machine, args, **kw):
        self.events.append(("promote", machine, list(args), kw.get("request"), self.tag_exists("v0.10.2")))
        if self.promote_error is not None:
            raise self.promote_error
        request = kw["request"]
        self.port.records[request["version"]] = ReleaseRecord.from_json(request["record"])
        return mock.Mock(code=0, result=None)

    def tag_exists(self, tag):
        return bool(self.remote_tag(tag))

    def passing_gate(self, **carries):
        carried = {"work_packages": [], "issues": [12], "releases": [], **carries}
        return model_release.GateResult(
            gates=[model_release.Verdict("tests-passed", True, "every work package has its tests ticked"),
                   model_release.Verdict("milestone", True, "carries issues [12]")],
            carries=carried, left_out=[])

    def board_model(self):
        def guarded(name, answer):
            def call(*args):
                self.events.append((name, args, self.remote_tag("v0.10.2") != "", self.remote_version()))
                if name in self.board_error:
                    raise self.board_error[name]
                return answer() if callable(answer) else answer
            return call
        return types.SimpleNamespace(
            GateRequest=model_release.GateRequest,
            gate=guarded("gate", lambda: self.gate_result),
            checks=guarded("checks", lambda: self.checks),
            publish=guarded("publish", lambda: self.publish_result),
            open_next=guarded("open_next", lambda: self.next_result))

    # ------------------------------------------------------------- running

    def release(self, *argv, stdin=""):
        with mock.patch("sys.stdin", io.StringIO(stdin)):
            return self.run_main(["release", *argv])

    def log_events(self, kind=None):
        logs = sorted((self.dir / "logs" / "acme").glob("release-*.log"), key=lambda p: p.stat().st_mtime)
        events = [json.loads(line) for line in logs[-1].read_text().splitlines()]
        return [e for e in events if kind is None or e["event"] == kind]

    def gates(self):
        return {e["name"]: e["result"] for e in self.log_events("gate")}

    def called(self, name):
        return [e for e in self.events if e[0] == name]

    def nothing_changed(self):
        self.assertEqual([], self.called("promote"))
        self.assertEqual("", self.remote_tag("v0.10.2"))
        self.assertEqual("0.10.2", self.remote_version())
        self.assertEqual([], self.called("publish"))
        self.assertEqual([], self.called("open_next"))


# ---------------------------------------------------------------- the command line

class CommandLine(World):
    def test_a_missing_value_or_reason_is_a_usage_error(self):
        for argv in (["--expect"], ["--commit"], ["--set-aside", "milestone"], ["--emergency"],
                     ["--skip-rehearsal"], ["--no-such-flag"], ["extra"]):
            with self.subTest(argv=argv):
                code, _, err = self.release(*argv)
                self.assertEqual(64, code)
                self.assertIn("usage: turpin release", err)
        self.nothing_changed()


# --------------------------------------------------------------------- the gates

class Gates(World):
    """Each gate is shown to refuse before it passes (docs/1.9): exit 1, naming the gate, and
    nothing changed."""

    def test_a_commit_rehearsal_did_not_pass_is_refused_then_released_when_it_did(self):          # S18, R16
        self.git("pull", "-q", "--ff-only", "origin", "main", cwd=self.work)
        other = self.commit("another commit", version="0.10.2")
        self.build(other)
        for name, deployed in (
                ("never deployed", Deployed("", None, None, None, None, None)),
                ("runs another commit", self.rehearsal_ran(other)),
                ("smoke did not pass", self.rehearsal_ran(self.sha, smoke=None)),
                ("the deploy did not finish", self.rehearsal_ran(self.sha, state="changing: deploy smoke"))):
            with self.subTest(name):
                self.rehearsal = deployed
                code, _, err = self.release("--expect", "0.10.2", "--commit", self.sha)
                self.assertEqual(1, code)
                self.assertIn("refused at gate rehearsal-passed", err)
                self.assertEqual("refused", self.gates()["rehearsal-passed"])
                self.nothing_changed()
        self.rehearsal = self.rehearsal_ran(self.sha)
        self.assertEqual(0, self.release("--expect", "0.10.2", "--commit", self.sha)[0])
        self.assertEqual("passed", self.gates()["rehearsal-passed"])

    def test_skipping_rehearsal_is_recorded_and_raises_the_retrospective_issue(self):             # S19, R16
        self.rehearsal = Deployed("", None, None, None, None, None)
        self.assertEqual(1, self.release("--expect", "0.10.2")[0])
        code, _, err = self.release("--expect", "0.10.2", "--commit", self.sha, "--skip-rehearsal", "host down")
        self.assertEqual(0, code, err)
        record = json.loads(self.tag_message("v0.10.2"))
        self.assertEqual("host down", record["rehearsal_skipped"])
        self.assertEqual({"environment": "rehearsal", "deployed": None, "smoke": None}, record["rehearsal"])
        (publish,) = self.called("publish")
        self.assertEqual(("v0.10.2", None, "host down", "0.10.2", self.sha), publish[1])
        self.assertIn("host down", json.dumps(self.log_events("override")))

    def test_a_commit_not_on_main_is_refused_without_a_tag(self):                                  # S20, R17
        self.git("checkout", "-q", "-b", "side", cwd=self.work)
        side = self.commit("side work", branch="side")
        self.rehearse(side)
        code, _, err = self.release("--expect", "0.10.2", "--commit", side)
        self.assertEqual(1, code)
        self.assertIn("refused at gate on-main", err)
        self.nothing_changed()

    def emergency_history(self):
        """0.10.0 and 0.10.1 released; main moved on; an emergency cut from each tag, and a root of its own."""
        self.text_tag("v0.10.0", self.sha)
        c1 = self.commit("release 0.10.1", version="0.10.1")
        self.text_tag("v0.10.1", c1)
        self.commit("unreleased work on main", version="0.10.2")
        self.git("checkout", "-q", "-b", "emergency", self.sha, cwd=self.work)
        (self.work / "app.toml").write_text('version = "0.10.2"\n')
        emergency = self.commit("emergency fix", branch="emergency")
        self.git("checkout", "-q", "-b", "late", c1, cwd=self.work)
        late = self.commit("fix cut from 0.10.1", branch="late", version="0.10.2")
        self.git("checkout", "-q", "--orphan", "unrelated", cwd=self.work)
        self.git("rm", "-rqf", ".", cwd=self.work)
        (self.work / "app-profile.toml").write_text(PROFILE)
        (self.work / "app.toml").write_text('version = "0.10.2"\n')
        unrelated = self.commit("unrelated root", branch="unrelated")
        self.git("checkout", "-q", "-f", "main", cwd=self.work)
        self.production_runs("0.10.0", self.sha)
        for commit in (emergency, late, unrelated):
            self.build(commit)
        return emergency, late, unrelated

    def test_an_emergency_descends_from_the_release_production_runs_not_the_newest_tag(self):       # S20, S50, R17
        emergency, late, unrelated = self.emergency_history()
        self.rehearse(emergency)
        code, _, err = self.release("--expect", "0.10.2", "--commit", emergency)
        self.assertEqual((1, True), (code, "refused at gate on-main" in err))         # without the flag, off main
        self.rehearse(unrelated)
        code, _, err = self.release("--expect", "0.10.2", "--commit", unrelated, "--emergency", "outage")
        self.assertEqual(1, code)
        self.assertIn("refused at gate emergency-descent", err)
        self.assertIn("does not descend from v0.10.0", err)
        self.rehearse(late)
        code, _, err = self.release("--expect", "0.10.2", "--commit", late, "--emergency", "outage")
        self.assertEqual(1, code)
        self.assertIn("commit(s) after v0.10.0 are on main", err)                  # cut from the newer tag
        self.nothing_changed()
        self.rehearse(emergency)
        code, _, err = self.release("--expect", "0.10.2", "--commit", emergency, "--emergency", "outage")
        self.assertEqual(0, code, err)
        self.assertEqual("outage", json.loads(self.tag_message("v0.10.2"))["emergency"])
        (gate,) = self.called("gate")
        request = gate[1][0]
        self.assertEqual(("v0.10.0", True), (request.carry_from, request.emergency))   # the range starts at the tag
        self.assertEqual(f"v0.10.0..{emergency}", request.range)
        self.assertEqual("passed", self.gates()["on-main"])
        # the release notes run from the same tag
        self.assertEqual("v0.10.0", self.called("publish")[0][1][1])

    def test_an_emergency_with_no_readable_release_in_production_is_refused(self):                  # S50, R17
        emergency, *_ = self.emergency_history()
        self.rehearse(emergency)
        self.production = None
        with mock.patch("subprocess.run", side_effect=self.curl_fails(subprocess.run)):
            code, _, err = self.release("--expect", "0.10.2", "--commit", emergency, "--emergency", "outage")
        self.assertEqual(1, code)
        self.assertIn("refused at gate emergency-descent: cannot tell which release production runs", err)

    @staticmethod
    def curl_fails(real):
        def run(argv, *a, **kw):
            if argv and argv[0] == "curl":
                return subprocess.CompletedProcess(argv, 22, "", "curl: (22) The requested URL returned error")
            return real(argv, *a, **kw)
        return run

    def test_a_production_with_no_turpin_state_is_read_from_its_health(self):                       # S50, R17
        emergency, *_ = self.emergency_history()
        self.rehearse(emergency)
        self.production = None
        real = subprocess.run

        def run(argv, *a, **kw):
            if argv and argv[0] == "curl":
                self.assertIn("http://prod.test/health", argv)
                return subprocess.CompletedProcess(argv, 0, '{"app_version":"0.10.0+abc1234"}', "")
            return real(argv, *a, **kw)
        with mock.patch("subprocess.run", side_effect=run):
            code, _, err = self.release("--expect", "0.10.2", "--commit", emergency, "--emergency", "outage")
        self.assertEqual(0, code, err)

    def test_a_required_check_that_is_not_green_refuses(self):                                       # S21, R18
        for ok, bad, text in ((False, ["check e2e is failure on abc"], "e2e is failure"),
                              (False, ["check e2e is missing on abc"], "e2e is missing")):
            with self.subTest(text):
                self.checks = (ok, {}, bad)
                code, _, err = self.release("--expect", "0.10.2")
                self.assertEqual(1, code)
                self.assertIn("refused at gate ci-passed", err)
                self.assertIn(text, err)
                self.nothing_changed()
        self.checks = (True, {"e2e": "success"}, [])
        self.assertEqual(0, self.release("--expect", "0.10.2")[0])
        self.assertEqual(("checks", (self.sha, ["e2e"])), self.called("checks")[0][:2])      # the commit's required checks

    def test_a_spent_or_lower_version_is_refused(self):                                              # S22, R19
        # the tag exists already, from before the tool
        self.text_tag("v0.10.2", self.sha)
        code, _, err = self.release("--expect", "0.10.2")
        self.assertEqual(1, code)
        self.assertIn("refused at gate version-spent-once", err)
        self.assertIn("without a record this tool can read", err)
        self.git("tag", "-d", "v0.10.2", cwd=self.work)
        self.git("push", "-q", "origin", ":refs/tags/v0.10.2", cwd=self.work)
        # a record for it in releases, from another commit
        self.port.records["0.10.2"] = ReleaseRecord("acme", Version(0, 10, 2), "c" * 40, {}, "2026-11-01T00:00:00Z")
        code, _, err = self.release("--expect", "0.10.2")
        self.assertEqual(1, code)
        self.assertIn("another commit or other digests", err)
        del self.port.records["0.10.2"]
        # lower than a prod- tag of an earlier prefix
        self.text_tag("prod-0.11.0", self.sha)
        self.production_runs("0.11.0", self.sha)
        code, _, err = self.release("--expect", "0.10.2")
        self.assertEqual(1, code)
        self.assertIn("not higher than the newest release tag 0.11.0", err)
        self.nothing_changed()

    def test_a_tag_holding_a_different_record_refuses_the_rerun(self):                              # S26, R22, R23
        other = ReleaseRecord("acme", Version(0, 10, 2), "d" * 40, self.images("d" * 40), "2026-11-01T00:00:00Z")
        self.git("tag", "-a", "-m", json.dumps(other.to_json()), "v0.10.2", self.sha, cwd=self.work)
        self.git("push", "-q", "origin", "refs/tags/v0.10.2", cwd=self.work)
        code, _, err = self.release("--expect", "0.10.2")
        self.assertEqual(1, code)
        self.assertIn("holds a different record", err)
        self.assertEqual([], self.called("publish"))
        self.assertEqual([], self.called("promote"))

    def test_a_record_version_this_tool_does_not_know_is_refused(self):                              # S28, R23
        self.git("tag", "-a", "-m", '{"record":2,"version":"0.10.2","commit":"x","images":{}}', "v0.10.2",
                 self.sha, cwd=self.work)
        self.git("push", "-q", "origin", "refs/tags/v0.10.2", cwd=self.work)
        code, _, err = self.release("--expect", "0.10.2")
        self.assertEqual(1, code)
        self.assertIn("record version this tool does not read", err)
        self.assertEqual([], self.called("publish"))

    def test_the_board_models_gates_refuse_or_report_by_their_verdicts(self):                       # S23, S53, S53b, R20, R20a
        self.gate_result = model_release.GateResult(
            gates=[model_release.Verdict("tests-passed", True, "ok"),
                   model_release.Verdict("milestone", False, "open in milestone 0.10.2 but no commit says Refs: #50")])
        code, _, err = self.release("--expect", "0.10.2")
        self.assertEqual(1, code)
        self.assertIn("refused at gate milestone: open in milestone 0.10.2 but no commit says Refs: #50", err)
        self.assertEqual({"tests-passed": "passed", "milestone": "refused"},
                         {k: v for k, v in self.gates().items() if k in ("tests-passed", "milestone")})
        self.nothing_changed()
        self.gate_result = model_release.GateResult(
            gates=[model_release.Verdict("tests-passed", False, "tests not passed in milestone 0.10.2: #40")])
        code, _, err = self.release("--expect", "0.10.2")
        self.assertEqual((1, True), (code, "refused at gate tests-passed" in err))
        self.nothing_changed()
        # a check with --emergency: reported, shown, and the release goes ahead
        self.gate_result = model_release.GateResult(
            gates=[model_release.Verdict("tests-passed", True, "emergency: not every test is ticked: #40", reported=True),
                   model_release.Verdict("milestone", True, "carries issues [12]")], carries=self.passing_gate().carries)
        code, out, err = self.release("--check")
        self.assertEqual(0, code, err)
        self.assertIn("check tests-passed: emergency: not every test is ticked: #40", out)
        self.assertEqual("reported", self.gates()["tests-passed"])

    def test_the_request_to_the_board_model_holds_what_git_knows(self):                              # R20, R42, §4
        self.assertEqual(0, self.release("--expect", "0.10.2")[0])
        (event,) = self.called("gate")
        request = event[1][0]
        self.assertEqual(("0.10.2", self.sha, self.sha, "origin/main", None, ("v", "prod-"), False, False),
                         (request.version, request.sha, request.range, request.main_range, request.carry_from,
                          request.prefixes, request.emergency, request.milestone_set_aside))

    def test_the_range_starts_at_the_release_production_runs_not_the_nearest_tag(self):              # R42, S60
        self.text_tag("v0.10.0", self.sha)
        c1 = self.commit("0.10.1", version="0.10.1")
        self.text_tag("v0.10.1", c1)
        sha = self.commit("0.10.2 work", version="0.10.2")
        self.build(sha)
        self.rehearsal = self.rehearsal_ran(sha)
        self.production_runs("0.10.0", self.sha)             # 0.10.1 is made, not deployed
        self.assertEqual(0, self.release("--expect", "0.10.2")[0])
        request = self.called("gate")[0][1][0]
        self.assertEqual(("v0.10.0", f"v0.10.0..{sha}", "v0.10.0..origin/main"),
                         (request.carry_from, request.range, request.main_range))
        self.assertEqual("v0.10.1", self.called("publish")[0][1][1])                          # notes run from the nearest

    def test_a_production_release_with_no_tag_refuses_the_range(self):                              # R42, S63
        self.text_tag("v0.10.1", self.sha)
        self.production_runs("0.9.0", self.sha)
        self.rehearsal = self.rehearsal_ran(self.sha)
        sha = self.commit("0.10.2 work", version="0.10.2")
        self.build(sha)
        self.rehearsal = self.rehearsal_ran(sha)
        code, _, err = self.release("--expect", "0.10.2")
        self.assertEqual(1, code)
        self.assertIn("no tag for production's release 0.9.0", err)
        self.assertEqual("refused", self.gates()["milestone"])
        self.production = None
        with mock.patch("subprocess.run", side_effect=self.curl_fails(subprocess.run)):
            code, _, err = self.release("--expect", "0.10.2")
        self.assertEqual((1, True), (code, "cannot tell which release production runs" in err))

    def test_milestone_is_set_aside_only_where_the_profile_lists_it_and_the_record_says_so(self):    # S53, R20
        self.gate_result = model_release.GateResult(
            gates=[model_release.Verdict("tests-passed", True, "ok"), model_release.Verdict("milestone", True, "set aside")],
            carries={"work_packages": [], "issues": [12, 50], "releases": []})
        code, _, err = self.release("--expect", "0.10.2", "--set-aside", "milestone", "the extra issue is a notes issue")
        self.assertEqual(0, code, err)
        record = json.loads(self.tag_message("v0.10.2"))
        self.assertEqual([{"gate": "milestone", "reason": "the extra issue is a notes issue"}], record["set_aside"])
        self.assertEqual([12, 50], record["carries"]["issues"])
        request = self.called("gate")[0][1][0]
        self.assertTrue(request.milestone_set_aside)
        self.assertEqual("set-aside", self.gates()["milestone"])

    def test_a_gate_the_profile_does_not_list_cannot_be_set_aside(self):                              # S53, R10
        sha = self.commit("profile", version="0.10.2")
        (self.work / "app-profile.toml").write_text(PROFILE.replace('overridable = ["milestone", "release-check"]',
                                                                    'overridable = ["release-check"]'))
        sha = self.commit("the profile lists only release-check")
        self.build(sha)
        self.rehearsal = self.rehearsal_ran(sha)
        code, _, err = self.release("--expect", "0.10.2", "--set-aside", "milestone", "known extra")
        self.assertEqual(1, code)
        self.assertIn("does not list milestone", err)
        self.nothing_changed()

    def test_the_milestone_agreeing_needs_no_flag_and_set_aside_is_empty(self):                        # S53
        self.assertEqual(0, self.release("--expect", "0.10.2")[0])
        self.assertEqual([], json.loads(self.tag_message("v0.10.2"))["set_aside"])

    def test_release_check_refusing_stops_the_release_and_set_aside_records_it(self):                   # S24, R21
        self.hook_exit.write_text("1")
        code, _, err = self.release("--expect", "0.10.2")
        self.assertEqual(1, code)
        self.assertIn("refused at gate release-check", err)
        self.nothing_changed()
        code, _, err = self.release("--expect", "0.10.2", "--set-aside", "release-check", "owner accepts it")
        self.assertEqual(0, code, err)
        self.assertEqual([{"gate": "release-check", "reason": "owner accepts it"}],
                         json.loads(self.tag_message("v0.10.2"))["set_aside"])

    def test_release_check_passing_runs_on_the_controller_from_the_commit(self):                      # S24
        self.assertEqual(0, self.release("--expect", "0.10.2")[0])
        self.assertEqual([f"controller release 0.10.2 {self.sha}"], self.hook_log.read_text().splitlines())
        self.assertEqual([], json.loads(self.tag_message("v0.10.2"))["set_aside"])

    def test_a_required_release_check_that_is_missing_refuses(self):                                    # §8, §9
        (self.work / "turpin" / "hooks" / "release-check").unlink()
        sha = self.commit("no hook")
        self.build(sha)
        self.rehearsal = self.rehearsal_ran(sha)
        code, _, err = self.release("--expect", "0.10.2")
        self.assertEqual(1, code)
        self.assertIn("required hook release-check is missing", err)

    def test_the_owner_confirms_by_typing_the_version(self):                                           # S25, R16
        code, _, err = self.release(stdin="0.10.3\n")
        self.assertEqual(1, code)
        self.assertIn('confirmation "0.10.3" is not 0.10.2', err)
        code, _, err = self.release("--expect", "0.10.3")
        self.assertEqual(1, code)
        self.assertIn("--expect 0.10.3 but the release is 0.10.2", err)
        self.nothing_changed()
        code, out, _ = self.release(stdin="0.10.2\n")
        self.assertEqual(0, code)
        self.assertIn("released 0.10.2", out)

    def test_check_runs_every_gate_and_changes_nothing(self):                                          # S32
        code, out, err = self.release("--check")
        self.assertEqual(0, code, err)
        self.assertIn("nothing changed", out)
        self.nothing_changed()
        self.assertEqual({"rehearsal-passed", "on-main", "emergency-descent", "ci-passed", "version-spent-once",
                          "tests-passed", "milestone", "release-check"}, set(self.gates()))

    def test_a_build_missing_from_candidates_refuses(self):
        del self.port.present[(self.sha, "web")]
        code, _, err = self.release("--expect", "0.10.2")
        self.assertEqual(1, code)
        self.assertIn("no build in candidates", err)
        self.assertIn("run turpin build", err)


# -------------------------------------------------------------------- the steps

class Steps(World):
    def test_the_release_runs_its_steps_in_order_and_the_record_is_the_tags_message(self):          # R22, R23, S26
        code, out, err = self.release("--expect", "0.10.2")
        self.assertEqual(0, code, err)
        self.assertIn("released 0.10.2", out)
        names = [e[0] for e in self.events if e[0] in ("promote", "publish", "open_next")]
        self.assertEqual(["promote", "publish", "open_next"], names)
        (promote,) = self.called("promote")
        machine, argv, request, tagged_at_promote = promote[1:]
        self.assertEqual(("copier", ["promote", "acme"]), (machine, argv))
        self.assertFalse(tagged_at_promote)                                     # the copy comes before the tag
        self.assertEqual({"login": "docker-config", "candidates": "acme/candidates", "releases": "acme/releases",
                          "commit": self.sha, "images": {k: str(v) for k, v in self.images(self.sha).items()},
                          "version": "0.10.2"}, {k: v for k, v in request.items() if k != "record"})
        record = json.loads(self.tag_message("v0.10.2"))
        self.assertEqual(request["record"], record)
        self.assertEqual(["record", "application", "version", "commit", "images", "made", "rehearsal", "emergency",
                          "rehearsal_skipped", "set_aside", "tool", "carries"], list(record))
        self.assertEqual((1, "acme", "0.10.2", self.sha, None, None, []),
                         (record["record"], record["application"], record["version"], record["commit"],
                          record["emergency"], record["rehearsal_skipped"], record["set_aside"]))
        self.assertEqual({"environment": "rehearsal", "deployed": SMOKE_PASSED, "smoke": "passed"}, record["rehearsal"])
        self.assertEqual({"work_packages": [], "issues": [12], "releases": []}, record["carries"])
        self.assertRegex(record["tool"]["programme"], r"^[0-9a-f]{40}$|^$")
        (publish,) = self.called("publish")
        self.assertEqual(("v0.10.2", None, None, None, None), publish[1])
        self.assertTrue(publish[2])                                              # the tag was pushed by then
        self.assertEqual("0.10.2", publish[3])                                   # and main is bumped only after (§10)
        (nxt,) = self.called("open_next")
        self.assertEqual(("0.10.2", []), nxt[1])
        self.assertEqual("0.10.3", nxt[3])                                       # main was bumped before the milestone

    def test_main_is_bumped_by_the_version_only_change_with_the_stamped_subject(self):             # R24, §10 step 6
        self.assertEqual(0, self.release("--expect", "0.10.2")[0])
        self.assertEqual("0.10.3", self.remote_version())
        subject = self.git("log", "-1", "--format=%s", "main", cwd=self.remote)
        self.assertEqual("app 0.10.3 api 1.0: bump the version to 0.10.3 after releasing 0.10.2", subject)
        changed = self.git("show", "--stat", "--format=", "main", cwd=self.remote)
        self.assertEqual(1, changed.count("|"))
        self.assertIn("app.toml", changed)

    def test_the_bump_goes_above_both_the_released_version_and_mains_own(self):                    # R24
        for own, expected, bumped in (("0.10.3", "0.10.3", False), ("0.11.0", "0.11.0", False),
                                      ("0.10.2", "0.10.3", True)):
            with self.subTest(main_has=own):
                self.git("fetch", "-q", "origin", cwd=self.work)
                self.git("reset", "-q", "--hard", "origin/main", cwd=self.work)
                self.commit(f"main holds {own}", version=own)
                done = gitrepo.bump_main(self.work, Version(0, 10, 2), "acme", str(self.dir))
                self.assertEqual(bumped, done)
                self.assertEqual(expected, self.remote_version())

    def test_a_stamp_that_needs_an_api_version_the_file_does_not_give_fails_step_6_with_exit_3(self):    # R24, 1.10
        (self.work / "api.txt").write_text("no version here\n")
        sha = self.commit("the api file holds no version")
        self.rehearse(sha)
        code, _, err = self.release("--expect", "0.10.2")
        self.assertEqual(3, code, err)
        self.assertIn("these steps failed: bump main", err)
        self.assertNotEqual("", self.remote_tag("v0.10.2"))                    # the release is made
        self.assertEqual("0.10.2", self.remote_version())                       # main is not bumped with a guess
        self.assertEqual(1, len(self.called("open_next")))                      # the other steps ran

    def test_the_bump_hook_runs_in_the_bumping_tree_with_the_new_version(self):                     # §8
        self.hook("bump", BUMP_HOOK)
        sha = self.commit("a bump hook")
        self.rehearse(sha)
        self.assertEqual(0, self.release("--expect", "0.10.2")[0])
        self.assertEqual(["0.10.3"], Path(str(self.hook_log) + ".bump").read_text().split())

    def test_a_failure_before_the_tag_spends_nothing_and_exits_by_its_type(self):                  # S26, S86, R22, R55
        for error, expected in (
                (TechnicalError.make(Reason.REGISTRY_UNREACHABLE, "registry down", blip=True), 75),
                (TechnicalError.make(Reason.REGISTRY_REFUSED, "login refused"), 2),
                (model.BusinessError.make(Reason.NO_OVERWRITE, "another digest"), 1)):
            with self.subTest(expected):
                self.promote_error = error
                code, _, err = self.release("--expect", "0.10.2")
                self.assertEqual(expected, code)
                self.assertIn(f"nothing is spent: run turpin release --expect 0.10.2 --commit {self.sha} again", err)
                self.assertEqual("", self.remote_tag("v0.10.2"))
                self.assertEqual([], self.called("publish"))
                self.assertEqual("0.10.2", self.remote_version())
                self.assertEqual([], self.called("open_next"))
        self.promote_error = None
        self.events.clear()
        self.assertEqual(0, self.release("--expect", "0.10.2")[0])             # the rerun makes the release

    def test_a_rerun_reuses_a_record_a_failed_run_left_in_releases(self):                           # R52, S26
        self.assertEqual(0, self.release("--expect", "0.10.2")[0])
        first = self.called("promote")[0][3]["record"]
        self.git("tag", "-d", "v0.10.2", cwd=self.work)                    # as if the tag push had not happened
        self.git("push", "-q", "origin", ":refs/tags/v0.10.2", cwd=self.work)
        self.events.clear()
        self.assertEqual(0, self.release("--expect", "0.10.2")[0])
        self.assertEqual(first, self.called("promote")[0][3]["record"])        # the same record, the same `made`

    def test_a_tag_that_cannot_be_pushed_is_not_left_behind(self):                                   # R22
        self.git("config", "remote.origin.pushurl", str(self.dir / "nowhere.git"), cwd=self.work)
        code, _, err = self.release("--expect", "0.10.2")
        self.assertNotEqual(0, code)
        self.assertIn("cannot push tag v0.10.2", err)
        self.assertEqual("", self.git("tag", "-l", "v0.10.2", cwd=self.work))   # nothing is spent
        self.assertEqual([], self.called("publish"))

    def test_a_push_interrupted_leaves_no_tag_and_the_rerun_makes_the_release(self):                  # R22, S115
        real = gitrepo.git

        def interrupted(repo, *args, **kw):
            if args[:1] == ("push",) and any(a.startswith("refs/tags/") for a in args):
                raise KeyboardInterrupt
            return real(repo, *args, **kw)
        with mock.patch.object(gitrepo, "git", interrupted):
            code, out, err = self.release("--expect", "0.10.2")
        self.assertEqual(130, code)
        self.assertEqual("", self.git("tag", "-l", "v0.10.2", cwd=self.work))      # not left behind, not "spent"
        self.assertEqual("", self.remote_tag("v0.10.2"))
        self.assertNotIn("released", out)
        self.assertEqual([], self.called("publish"))
        code, out, err = self.release("--expect", "0.10.2")
        self.assertEqual(0, code, err)
        self.assertIn("released 0.10.2", out)
        self.assertNotEqual("", self.remote_tag("v0.10.2"))

    def test_a_resume_pushes_a_tag_that_only_the_killed_run_had(self):                                 # R22
        self.publish_result = {"retrospective": "not asked", "release": None, "failed": ["GitHub Release"]}
        self.assertEqual(3, self.release("--expect", "0.10.2")[0])
        self.git("push", "-q", "origin", ":refs/tags/v0.10.2", cwd=self.work)      # a kill before the push landed
        self.assertEqual("", self.remote_tag("v0.10.2"))
        self.publish_result = {"retrospective": "not asked", "release": "created", "failed": []}
        code, out, err = self.release("--expect", "0.10.2")
        self.assertEqual(0, code, err)
        self.assertNotEqual("", self.remote_tag("v0.10.2"))                          # the version is spent for real

    def test_a_resumed_release_takes_its_notes_from_the_tag_before_its_own(self):                       # R25
        before = self.git("rev-parse", "HEAD", cwd=self.work)
        self.text_tag("v0.10.1", before)
        self.production_runs("0.10.1", before)
        sha = self.commit("a later feature")
        self.rehearse(sha)
        self.publish_result = {"retrospective": "not asked", "release": None, "failed": ["GitHub Release"]}
        code, _, err = self.release("--expect", "0.10.2")
        self.assertEqual(3, code, err)
        self.publish_result = {"retrospective": "not asked", "release": "created", "failed": []}
        code, _, err = self.release("--expect", "0.10.2")
        self.assertEqual(0, code, err)
        first, second = [call[1] for call in self.called("publish")]
        self.assertEqual(("v0.10.2", "v0.10.1"), first[:2])
        self.assertEqual(("v0.10.2", "v0.10.1"), second[:2])                          # not its own tag

    def test_the_exit_3_message_names_the_rerun_with_the_flags_of_the_run_and_the_issues_to_move(self):  # R55, S86
        emergency, *_ = Gates.emergency_history(self)
        self.rehearse(emergency)
        self.gate_result = model_release.GateResult(gates=self.passing_gate().gates, carries=self.passing_gate().carries,
                                                    left_out=[9])
        self.next_result = {"milestone": "0.10.3", "created": False, "moved": [], "failed": ["next milestone", "move #9"]}
        code, _, err = self.release("--expect", "0.10.2", "--commit", emergency, "--emergency", "outage")
        self.assertEqual(3, code)
        self.assertIn(f"run turpin release --expect 0.10.2 --commit {emergency} --emergency outage again", err)
        self.assertIn("move #9 into the next milestone by hand", err)

    def release_in_a_session_of_its_own_and_press_ctrl_c(self, after, *argv):
        """A child process, its own session and process group, runs the release; a SIGINT goes to the
        whole group `after` seconds in, as a terminal's Ctrl+C does. Returns its exit code, its
        standard error and the board calls to `publish` it made."""
        reader, writer = os.pipe()
        pid = os.fork()
        if pid == 0:
            status = 99
            try:
                os.setsid()
                threading.Timer(after, lambda: os.killpg(os.getpgrp(), signal.SIGINT)).start()
                code, _, err = self.release(*argv)
                os.write(writer, json.dumps([code, err, [list(map(str, c[1])) for c in self.called("publish")]]).encode())
                status = 0
            finally:
                os._exit(status)
        os.close(writer)
        with os.fdopen(reader) as pipe:
            answer = pipe.read()
        os.waitpid(pid, 0)
        return tuple(json.loads(answer))

    def test_a_real_ctrl_c_during_the_tag_push_lets_the_push_finish_and_says_the_release_is_made(self):   # R22, S115
        hook = self.remote / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\nwhile read old new ref; do case \"$ref\" in refs/tags/*) sleep 1.5;; esac; done\n")
        hook.chmod(0o755)
        code, err, published = self.release_in_a_session_of_its_own_and_press_ctrl_c(0.6, "--expect", "0.10.2")
        self.assertEqual(130, code)
        self.assertNotEqual("", self.remote_tag("v0.10.2"))                   # the push was not killed
        self.assertNotEqual("", self.git("tag", "-l", "v0.10.2", cwd=self.work))   # nor the tag deleted
        self.assertIn("interrupted after v0.10.2 was pushed: the release is made", err)
        self.assertNotIn("not spent", err)
        self.assertEqual([], published)                                         # no step after it began
        hook.unlink()
        self.assertEqual(0, self.release("--expect", "0.10.2")[0])             # the rerun finishes the steps
        self.assertEqual(1, len(self.called("publish")))

    def test_a_rerun_that_resumes_passes_rehearsal_though_rehearsal_has_moved_on(self):                  # R22, §10
        self.publish_result = {"retrospective": "not asked", "release": None, "failed": ["GitHub Release"]}
        self.assertEqual(3, self.release("--expect", "0.10.2")[0])
        self.git("pull", "-q", "--ff-only", "origin", "main", cwd=self.work)      # main was bumped
        other = self.commit("a later change")
        self.rehearse(other)                                                  # rehearsal now runs another commit
        self.publish_result = {"retrospective": "not asked", "release": "created", "failed": []}
        code, out, err = self.release("--expect", "0.10.2", "--commit", self.sha)
        self.assertEqual(0, code, err)
        self.assertIn("released 0.10.2", out)
        self.assertEqual("resuming v0.10.2: its record says rehearsal ran",
                         [e for e in self.log_events("gate") if e["name"] == "rehearsal-passed"][-1]["detail"])

    def test_a_tag_whose_record_is_another_commit_does_not_pass_rehearsal_by_resuming(self):             # R22
        self.assertEqual(0, self.release("--expect", "0.10.2")[0])
        self.git("pull", "-q", "--ff-only", "origin", "main", cwd=self.work)
        other = self.commit("another commit", version="0.10.2")
        self.build(other)                                                     # built, but rehearsal never ran it
        code, _, err = self.release("--expect", "0.10.2", "--commit", other)
        self.assertEqual(1, code)
        self.assertIn("refused at gate rehearsal-passed", err)

    def test_a_resume_that_cannot_push_its_tag_says_whether_origin_holds_it(self):                       # R22
        self.publish_result = {"retrospective": "not asked", "release": None, "failed": ["GitHub Release"]}
        self.assertEqual(3, self.release("--expect", "0.10.2")[0])
        self.git("push", "-q", "origin", ":refs/tags/v0.10.2", cwd=self.work)
        self.git("config", "remote.origin.pushurl", str(self.dir / "nowhere.git"), cwd=self.work)
        code, _, err = self.release("--expect", "0.10.2")
        self.assertNotEqual(0, code)
        self.assertIn("cannot push tag v0.10.2 (origin does not hold it: nothing is spent)", err)

    def test_any_interruption_reaching_a_board_call_says_what_was_interrupted(self):                   # S115
        log = mock.Mock()
        with self.assertRaises(KeyboardInterrupt) as caught:
            with board.calling("the read", log, "interrupted before the release began"):
                raise KeyboardInterrupt
        self.assertEqual("interrupted before the release began", str(caught.exception))

    def test_a_failure_after_the_tag_carries_on_and_exits_3_naming_the_rerun(self):                  # S86, R55
        self.publish_result = {"retrospective": "not asked", "release": None, "failed": ["GitHub Release"]}
        code, _, err = self.release("--expect", "0.10.2")
        self.assertEqual(3, code)
        self.assertIn("these steps failed: GitHub Release", err)
        self.assertIn(f"run turpin release --expect 0.10.2 --commit {self.sha} again", err)
        self.assertNotEqual("", self.remote_tag("v0.10.2"))
        self.assertEqual("0.10.3", self.remote_version())                       # the later steps still ran
        self.assertEqual(1, len(self.called("open_next")))

    def test_each_step_after_the_tag_that_fails_is_named_and_the_others_run(self):                    # R55
        self.next_result = {"milestone": "0.10.3", "created": False, "moved": [], "failed": ["next milestone", "move #9"]}
        with mock.patch.object(gitrepo, "bump_main", side_effect=TechnicalError.make(Reason.GIT_UNREACHABLE,
                                                                                    "no", blip=True)):
            code, _, err = self.release("--expect", "0.10.2")
        self.assertEqual(3, code)
        self.assertIn("bump main, next milestone, move #9", err)
        self.assertEqual(1, len(self.called("publish")))

    def test_a_rerun_resumes_after_the_tag_without_repeating_and_says_when_all_is_done(self):         # S26, R22
        self.publish_result = {"retrospective": "not asked", "release": None, "failed": ["GitHub Release"]}
        self.assertEqual(3, self.release("--expect", "0.10.2")[0])
        tag_commit = self.git("rev-parse", "v0.10.2", cwd=self.remote)
        self.events.clear()
        self.publish_result = {"retrospective": "not asked", "release": "created", "failed": []}
        self.next_result = {"milestone": "0.10.3", "created": False, "moved": [], "failed": []}
        code, out, err = self.release("--expect", "0.10.2")
        self.assertEqual(0, code, err)
        self.assertEqual(tag_commit, self.git("rev-parse", "v0.10.2", cwd=self.remote))
        self.assertEqual([], self.called("promote"))                            # no second copy, no second tag
        self.assertEqual(1, len(self.called("publish")))
        self.assertIn("released 0.10.2", out)
        # everything done: it says so, and changes nothing
        self.events.clear()
        self.publish_result = {"retrospective": "not asked", "release": "exists", "failed": []}
        code, out, err = self.release("--expect", "0.10.2")
        self.assertEqual(0, code, err)
        self.assertIn("already done", out)
        self.assertEqual([], self.called("promote"))
        self.assertEqual("0.10.3", self.remote_version())

    def test_a_resumed_release_keeps_what_the_record_carries(self):                                     # R42
        self.gate_result = self.passing_gate(releases=[{"version": "0.10.1", "work_packages": [], "issues": [1],
                                                        "dropped": []}])
        self.publish_result = {"retrospective": "not asked", "release": None, "failed": ["GitHub Release"]}
        self.assertEqual(3, self.release("--expect", "0.10.2")[0])
        self.gate_result = None            # the gate is not asked again on a resume
        self.publish_result = {"retrospective": "not asked", "release": "created", "failed": []}
        self.assertEqual(0, self.release("--expect", "0.10.2")[0])
        self.assertEqual(1, len(self.called("gate")))
        self.assertEqual([{"version": "0.10.1", "work_packages": [], "issues": [1], "dropped": []}],
                         json.loads(self.tag_message("v0.10.2"))["carries"]["releases"])

    def test_an_emergency_moves_the_left_out_issues_to_the_next_milestone(self):                       # S27, S52, R24
        emergency, *_ = Gates.emergency_history(self)
        self.rehearse(emergency)
        self.gate_result = model_release.GateResult(gates=self.passing_gate().gates, carries=self.passing_gate().carries,
                                                    left_out=[9])
        self.assertEqual(0, self.release("--expect", "0.10.2", "--commit", emergency, "--emergency", "outage")[0])
        (nxt,) = self.called("open_next")
        self.assertEqual(("0.10.2", [9]), nxt[1])
        # without an emergency nothing is moved
        self.assertEqual([], [m for m in self.called("open_next") if m[1][1] and not self.called("gate")[0][1][0].emergency])

    def test_the_retrospective_is_not_raised_by_an_emergency(self):                                        # §10
        emergency, *_ = Gates.emergency_history(self)
        self.rehearse(emergency)
        self.assertEqual(0, self.release("--expect", "0.10.2", "--commit", emergency, "--emergency", "outage")[0])
        self.assertEqual((None, None, None), self.called("publish")[0][1][2:])


# ---------------------------------------------- reads the board model cannot make (S114, S115)

class TheBoardIsNotReadAsAnAnswer(World):
    """R62: a read that cannot be made is never refused or empty: exit by its type, nothing changed."""

    def exit_of(self, error, call="gate"):
        self.board_error = {call: error}
        code, _, err = self.release("--expect", "0.10.2")
        self.nothing_changed()
        return code, err

    @staticmethod
    def profile_error():
        with contextlib.redirect_stderr(io.StringIO()):      # the model prints its message as it raises it
            return board.profile_error()("versions.bump.files is not a list")

    def test_a_blip_is_75_a_refusal_is_2_a_profile_error_2_and_a_crash_70(self):                    # S114
        for error, expected in (
                (Unavailable("GitHub did not answer: timed out", transient=True), 75),
                (Unavailable("GitHub refused repos/x: HTTP 503", transient=True), 75),
                (Unavailable("GitHub refused repos/x: HTTP 403 Resource not accessible"), 2),
                (self.profile_error(), 2),
                (ZeroDivisionError("a defect"), 70)):
            with self.subTest(error=str(error)[:30]):
                code, _ = self.exit_of(error)
                self.assertEqual(expected, code)

    def test_the_message_names_the_read_and_holds_no_tool_text(self):                                 # R62, docs/1.10
        code, err = self.exit_of(Unavailable("GitHub refused repos/acme/acme/issues: HTTP 503 secret-text", transient=True))
        self.assertEqual(75, code)
        self.assertIn("the release's milestone gate could not be read: try again later", err)
        self.assertNotIn("secret-text", err)
        self.assertNotIn("refused at gate milestone", err)

    def test_checks_that_cannot_be_read_are_not_read_as_missing(self):                                  # R18, R62
        self.board_error = {"checks": Unavailable("GitHub did not answer", transient=True)}
        code, _, err = self.release("--expect", "0.10.2")
        self.assertEqual(75, code)
        self.assertIn("the CI checks could not be read", err)
        self.assertNotEqual("refused", self.gates().get("ci-passed"))

    def test_a_record_version_the_board_does_not_read_is_refused_not_unavailable(self):                  # §10
        from board.repo import RecordVersionUnknown
        code, err = self.exit_of(RecordVersionUnknown("tag v0.9.0 holds record version 2"))
        self.assertEqual(1, code)

    def test_the_models_own_standard_error_goes_to_the_run_log(self):                                     # §4
        def chatter(request):
            import sys
            print("profile: noise from the board model", file=sys.stderr)
            return self.gate_result
        original = self.board_model

        def noisy():
            namespace = original()
            namespace.gate = chatter
            return namespace
        with mock.patch.object(board, "release_module", side_effect=noisy):
            code, _, err = self.release("--expect", "0.10.2")
        self.assertEqual(0, code)
        self.assertNotIn("noise from the board model", err)
        self.assertIn("noise from the board model", json.dumps(self.log_events("board-stderr")))

    def test_a_ctrl_c_during_a_board_read_lets_it_finish_then_stops_before_the_tag(self):                 # S115, R63
        finished = []

        def slow_gate(request):
            os.kill(os.getpid(), signal.SIGINT)            # the operator presses Ctrl+C while the read runs
            finished.append(True)                           # the read is not abandoned
            return self.gate_result
        original = self.board_model

        def model_with_slow_gate():
            namespace = original()
            namespace.gate = slow_gate
            return namespace
        with mock.patch.object(board, "release_module", side_effect=model_with_slow_gate):
            code, _, err = self.release("--expect", "0.10.2")
        self.assertEqual(130, code)
        self.assertEqual([True], finished)
        self.assertIn("nothing was changed", err)
        self.nothing_changed()


class TheBoardModelsCallsAreDetached(unittest.TestCase):
    """R63 with a real process: the `gh` the model starts is not in `turpin`'s process group, so a
    signal to that group (a Ctrl+C) does not reach it and it runs to its end. The check runs in
    a session of its own, so the signal reaches nobody else."""

    SCRIPT = textwrap.dedent('''\
        import os, signal, sys, threading
        sys.path.insert(0, sys.argv[1])
        from board import sources
        hits = []
        signal.signal(signal.SIGUSR1, lambda *_: hits.append(True))     # the Ctrl+C's SIGINT, held
        threading.Timer(0.3, lambda: os.killpg(os.getpgrp(), signal.SIGUSR1)).start()
        done = sources.run_detached(["gh", "api", "x"], capture_output=True, text=True, timeout=20)
        print(done.returncode, os.getpgrp(), len(hits))
        ''')

    def test_gh_runs_in_a_group_of_its_own_and_a_signal_to_turpins_group_does_not_reach_it(self):
        import sys
        import tempfile
        scripts = str(Path(__file__).resolve().parents[1])
        with tempfile.TemporaryDirectory() as tmp:
            stub = Path(tmp) / "gh"
            # a stand-in that dies of the signal if it receives it, and otherwise finishes its work
            stub.write_text('#!/bin/sh\nps -o pgid= -p $$ > "$GH_PGID"\ntrap - USR1\nsleep 1\necho done > "$GH_DONE"\necho "{}"\n')
            stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
            env = dict(os.environ, PATH=f"{tmp}:{os.environ['PATH']}", GH_PGID=f"{tmp}/pgid", GH_DONE=f"{tmp}/done")
            done = subprocess.run([sys.executable, "-c", self.SCRIPT, scripts], env=env, capture_output=True,
                                  text=True, start_new_session=True, timeout=60)
            self.assertEqual(0, done.returncode, done.stderr)
            code, turpin_group, hits = done.stdout.split()
            self.assertEqual(("0", "1"), (code, hits))                       # the signal reached turpin
            self.assertNotEqual(turpin_group, (Path(tmp) / "pgid").read_text().strip())
            self.assertTrue((Path(tmp) / "done").exists())                    # and not gh, which ran to its end


if __name__ == "__main__":
    unittest.main()
