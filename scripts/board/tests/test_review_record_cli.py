"""`board-review-record.py`: a check run to report, so it exits 0 whatever it finds."""

import importlib.util
import json
import unittest
from pathlib import Path
from unittest import mock

from board import sources
from board.digest import record_problems

from .cli import run

COMMAND = "board/board-review-record.py"
GOOD = ("## Review rounds\n\n- doc: docs/a.md; type rule; words 5; change applied; lines 1; places 1; "
        "last review never; terms added 0\n- R1 none\n- R1 cost: reader 5k\n- owner — not reviewed\n")


class TheCommand(unittest.TestCase):
    def test_a_good_body_on_stdin_is_ok(self):
        for flags in ((), ("--exit-code",)):
            done = run(COMMAND, *flags, stdin=GOOD)
            self.assertEqual((0, ""), (done.returncode, done.stderr), flags)
            self.assertTrue(done.stdout.startswith("ok review record"), done.stdout)

    def test_none_owed_is_ok(self):
        done = run(COMMAND, "--exit-code", stdin="## Review rounds\n\nNone owed: a record\n")
        self.assertEqual(0, done.returncode)

    def test_findings_are_warned_and_exit_0(self):
        done = run(COMMAND, stdin="no section here")
        self.assertEqual(0, done.returncode)
        self.assertEqual("WARN review record: " + record_problems("no section here")[0] + "\n", done.stdout)

    def test_findings_exit_1_with_exit_code(self):
        done = run(COMMAND, "--exit-code", stdin=GOOD.replace("- owner — not reviewed\n", ""))
        self.assertEqual(1, done.returncode)
        self.assertEqual(["WARN review record: there is no owner line"], done.stdout.splitlines())

    def test_a_bad_flag_or_pr_is_a_usage_error(self):
        self.assertEqual(64, run(COMMAND, "--nonsense").returncode)
        self.assertEqual(64, run(COMMAND, "--pr", "17").returncode)


def _command():
    path = Path(__file__).resolve().parents[1] / "board-review-record.py"
    spec = importlib.util.spec_from_file_location("board_review_record", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReadingAPullRequest(unittest.TestCase):
    """`main` is called in this process so the one command, `gh`, can be stubbed."""

    def call(self, gh, *argv):
        with mock.patch.object(sources.subprocess, "run", gh), mock.patch("builtins.print") as out:
            code = _command().main(list(argv))
        return code, [c.args[0] for c in out.call_args_list if not c.kwargs]

    def test_the_body_is_read_by_rest(self):
        seen = []

        def gh(args, **kw):
            seen.append(args)
            return mock.Mock(returncode=0, stdout=json.dumps({"body": GOOD}), stderr="")
        code, lines = self.call(gh, "--pr", "o/r#7", "--exit-code")
        self.assertEqual((0, ["ok review record: nothing the digest would leave unread"]), (code, lines))
        self.assertEqual(["gh", "api", "repos/o/r/pulls/7"], seen[0])

    def test_a_refused_read_cannot_judge(self):
        def refused(args, **kw):
            return mock.Mock(returncode=1, stdout="", stderr="HTTP 403: refused")
        self.assertEqual(2, self.call(refused, "--pr", "o/r#7")[0])

    def test_a_read_that_timed_out_may_be_retried(self):
        def slow(args, **kw):
            raise sources.subprocess.TimeoutExpired(args, 30)
        self.assertEqual(75, self.call(slow, "--pr", "o/r#7")[0])

    def test_a_missing_pull_request_cannot_judge(self):
        def missing(args, **kw):
            return mock.Mock(returncode=1, stdout="", stderr="HTTP 404: Not Found")
        self.assertEqual(2, self.call(missing, "--pr", "o/r#7")[0])


if __name__ == "__main__":
    unittest.main()
