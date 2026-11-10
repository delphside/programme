"""`board-release.py`, the command `turpin` calls: JSON in, JSON out, and an exit
status that says which of done, refused, partly done and broken it was.

From the rules (design §4 *The board model*): exit 0 passed, 1 refused,
3 partly done (settle, next, publish), 70 a profile error, never read as
refused; and a board or git that cannot be read refuses."""

import importlib.util
import io
import json
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from board import profile, release
from board.sources import Unavailable

from .cases import Cases

SCRIPT = Path(__file__).resolve().parents[1] / "board-release.py"
spec = importlib.util.spec_from_file_location("board_release_cli", SCRIPT)
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


def run(*argv, stdin=""):
    out, err = io.StringIO(), io.StringIO()
    with mock.patch("sys.stdin", io.StringIO(stdin)), redirect_stdout(out), redirect_stderr(err):
        try:
            code = profile.run(cli.main, list(argv))
        except SystemExit as exit_:      # a profile error exits 70 by itself
            code = exit_.code
    return code, out.getvalue(), err.getvalue()


GATE = {"version": "0.10.2", "sha": "a" * 40, "range": "a", "main_range": "b", "prefixes": ["v"]}


class TheCommand(Cases):

    def setUp(self):
        env = mock.patch.dict(os.environ, {"TURPIN_GH_REPO": "fakeorg/widget"})
        env.start()
        self.addCleanup(env.stop)

    def test_gate_passes_and_refuses_by_its_exit(self):
        """gate: 0 when every gate passed, 1 when one refused, the verdicts on stdout"""
        for passed, want in ((True, 0), (False, 1)):
            result = release.GateResult(gates=[release.Verdict("milestone", passed, "m")])
            with mock.patch.object(release, "gate", return_value=result):
                code, out, _ = run("gate", stdin=json.dumps(GATE))
            self.expect(f"passed={passed}", (want, passed), (code, json.loads(out)["passed"]))
        self.expect("a gate lists its verdicts", [{"name": "milestone", "result": "refused", "message": "m"}],
                    json.loads(out)["gates"])

    def test_an_unreadable_board_refuses_and_says_why(self):
        """a board or git that cannot be read: exit 1 with the reason, never a pass"""
        with mock.patch.object(release, "gate", side_effect=Unavailable("GitHub did not answer")):
            code, out, err = run("gate", stdin=json.dumps(GATE))
        self.expect("refused", (1, {"refused": "GitHub did not answer"}), (code, json.loads(out)))
        self.expect("and stderr says it", True, "GitHub did not answer" in err)

    def test_a_crash_and_a_bad_request_are_70_not_1(self):
        """a crash or a malformed request is a profile error, which no caller reads as refused"""
        with mock.patch.object(release, "gate", side_effect=KeyError("x")):
            code, _, err = run("gate", stdin=json.dumps(GATE))
        self.expect("a crash", 70, code)
        code, _, err = run("gate", stdin="{}")
        self.expect("a request without its fields", (70, True), (code, "malformed" in err))

    def test_the_partial_commands_exit_3(self):
        """settle, next and publish: 0 when done, 3 when some is left, named"""
        record = {"version": "0.10.2", "carries": {"work_packages": [], "issues": [], "releases": []}}
        for settled, want in ((True, 0), (False, 3)):
            with mock.patch.object(release, "settle", return_value={"settled": settled, "done": [], "left": ["#1"]}) as m:
                code, out, _ = run("settle", "--announcement", "Released in v", "--tag", "v0.10.2", stdin=json.dumps(record))
            self.expect(f"settle settled={settled}", want, code)
        self.expect("settle is given the record, the announcement and the tag", (record, "Released in v", "v0.10.2"), m.call_args.args)
        code, _, err = run("settle", stdin=json.dumps(record))
        self.expect("settle without its words is an error", 70, code)
        for failed, want in (([], 0), (["next milestone"], 3)):
            done = {"milestone": "0.10.3", "created": True, "moved": [], "failed": failed}
            with mock.patch.object(release, "open_next", return_value=done) as m:
                code, _, _ = run("next", "0.10.2", "--move", "9", "10")
            self.expect(f"next failed={failed}", want, code)
        self.expect("next is given the version and the numbers", ("0.10.2", [9, 10]), m.call_args.args)
        for failed, want in (([], 0), (["GitHub Release"], 3)):
            with mock.patch.object(release, "publish", return_value={"release": "created", "failed": failed}) as m:
                code, _, _ = run("publish", "v0.10.2", "--notes-start-tag", "v0.10.1", "--retrospective", "why",
                                 "--version", "0.10.2", "--commit", "abc")
            self.expect(f"publish failed={failed}", want, code)
        self.expect("publish is given every flag", ("v0.10.2", "v0.10.1", "why", "0.10.2", "abc"), m.call_args.args)

    def test_checks_pass_only_when_every_required_check_is_green(self):
        """checks: 0 green, 1 not, the failures named"""
        with mock.patch.object(release, "checks", return_value=(False, {"e2e": "failure"}, ["check e2e is failure on aaa"])) as m:
            code, out, _ = run("checks", "a" * 40, "--require", "e2e", "lint")
        self.expect("refused", (1, ["check e2e is failure on aaa"]), (code, json.loads(out)["failures"]))
        self.expect("with the names asked", ("a" * 40, ["e2e", "lint"]), m.call_args.args)

    def test_the_repository_is_named_or_the_command_refuses(self):
        """the repository is TURPIN_GH_REPO or the origin's; neither refuses"""
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TURPIN_GH_REPO")
            with mock.patch.object(cli.repo, "origin_slug", return_value=None):
                code, out, _ = run("checks", "abc")
            self.expect("refused, saying how to name it", (1, True),
                        (code, "TURPIN_GH_REPO" in json.loads(out)["refused"]))
            with mock.patch.object(cli.repo, "origin_slug", return_value="fakeorg/origin"), \
                    mock.patch.object(release, "checks", return_value=(True, {}, [])):
                code, _, _ = run("checks", "abc")
            self.expect("the origin is used", ("fakeorg/origin", 0), (os.environ["BOARD_REPOSITORY"], code))

    def test_an_unknown_command_is_a_usage_error(self):
        """an unknown command is 2"""
        self.expect("usage", 2, run("frobnicate")[0])


if __name__ == "__main__":
    unittest.main()
