"""`board-overlap.py`: a check run to report, so it exits 0 whatever it finds."""

import importlib.util
import json
import unittest
from pathlib import Path
from unittest import mock

from board import profile, sources

from .cli import run

COMMAND = "board/board-overlap.py"


def _command():
    path = Path(__file__).resolve().parents[1] / "board-overlap.py"
    spec = importlib.util.spec_from_file_location("board_overlap", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pr(number, title, body=""):
    return {"number": number, "title": title, "body": body}


def files(*names):
    return [{"filename": n} for n in names]


class Github:
    """A fake `gh api`: the answer for each path, and the paths asked."""

    def __init__(self, answers):
        self.answers = answers
        self.asked = []

    def __call__(self, args, **kw):
        self.asked.append(args[2])
        value = self.answers.get(args[2].split("?")[0])
        if isinstance(value, mock.Mock):
            return value
        if value is not None:
            return mock.Mock(returncode=0, stdout=json.dumps(value), stderr="")
        return mock.Mock(returncode=1, stdout="", stderr="HTTP 404: Not Found")


ANSWERS = {
    "repos/o/r/pulls": [pr(1, "first", "Claims: `docs/1.1.md`"), pr(2, "second"), pr(3, "third", "Claims: scripts/")],
    "repos/o/r/pulls/1/files": files("a.md"),
    "repos/o/r/pulls/2/files": files("docs/1.1.md", "b.md"),
    "repos/o/r/pulls/3/files": files("c.md"),
    "repos/o/r/pulls/2": pr(2, "second"),
}


class TheCommand(unittest.TestCase):
    def test_a_bad_flag_is_a_usage_error(self):
        self.assertEqual(64, run(COMMAND, "--nonsense").returncode)

    def test_one_of_files_pr_all_is_needed(self):
        self.assertEqual(64, run(COMMAND).returncode)
        self.assertEqual(64, run(COMMAND, "--all", "--files", "a").returncode)

    def test_a_pr_must_be_owner_repo_number(self):
        self.assertEqual(64, run(COMMAND, "--pr", "17").returncode)

    def test_repo_goes_with_files_only(self):
        self.assertEqual(64, run(COMMAND, "--all", "--repo", "o/r").returncode)
        self.assertEqual(64, run(COMMAND, "--files", "a", "--repo", "r").returncode)


class Reading(unittest.TestCase):
    """`main` is called in this process so `gh` can be stubbed."""

    def call(self, gh, *argv, repos=("o/r",)):
        with mock.patch.object(sources.subprocess, "run", gh), \
                mock.patch.object(profile, "repository_name", return_value="o/r"), \
                mock.patch.object(profile, "watched_repositories", return_value=repos), \
                mock.patch("builtins.print") as out:
            code = _command().main(list(argv))
        return code, [c.args[0] for c in out.call_args_list if not c.kwargs]

    def test_files_lists_each_pull_request_that_changes_or_claims_one(self):
        code, lines = self.call(Github(ANSWERS), "--files", "docs/1.1.md", "c.md")
        self.assertEqual(0, code)
        self.assertEqual(["OVERLAP o/r#1 first — docs/1.1.md",
                          "OVERLAP o/r#2 second — docs/1.1.md",
                          "OVERLAP o/r#3 third — c.md"], lines)

    def test_files_in_a_claimed_directory_overlap(self):
        self.assertEqual(["OVERLAP o/r#3 third — scripts/board/x.py"],
                         self.call(Github(ANSWERS), "--files", "scripts/board/x.py")[1])

    def test_repo_names_another_repository(self):
        gh = Github({"repos/p/q/pulls": [], })
        self.assertEqual((0, ["ok overlap: none"]), self.call(gh, "--files", "a", "--repo", "p/q"))

    def test_nothing_shared_says_so(self):
        self.assertEqual((0, ["ok overlap: none"]), self.call(Github(ANSWERS), "--files", "zzz"))

    def test_exit_code_is_1_only_with_an_overlap(self):
        self.assertEqual(1, self.call(Github(ANSWERS), "--files", "c.md", "--exit-code")[0])
        self.assertEqual(0, self.call(Github(ANSWERS), "--files", "zzz", "--exit-code")[0])

    def test_pr_uses_its_own_files_and_claims_and_leaves_itself_out(self):
        code, lines = self.call(Github(ANSWERS), "--pr", "o/r#2")
        self.assertEqual((0, ["OVERLAP o/r#1 first — docs/1.1.md"]), (code, lines))

    def test_all_lists_each_pair(self):
        code, lines = self.call(Github(ANSWERS), "--all")
        self.assertEqual((0, ["OVERLAP o/r#1 and #2 — docs/1.1.md"]), (code, lines))

    def test_all_reads_each_repository_the_programme_file_names(self):
        gh = Github({**ANSWERS, "repos/p/q/pulls": []})
        self.call(gh, "--all", repos=("o/r", "p/q"))
        self.assertTrue(any(a.startswith("repos/p/q/pulls?") for a in gh.asked), gh.asked)

    def test_it_reads_by_rest_only(self):
        gh = Github(ANSWERS)
        self.call(gh, "--all")
        self.assertTrue(all(a.startswith("repos/") for a in gh.asked), gh.asked)

    def test_a_missing_pull_request_cannot_judge(self):
        self.assertEqual(2, self.call(Github(ANSWERS), "--pr", "o/r#99")[0])

    def test_a_refused_read_cannot_judge(self):
        refused = Github({"repos/o/r/pulls": mock.Mock(returncode=1, stdout="", stderr="HTTP 403: refused")})
        self.assertEqual(2, self.call(refused, "--files", "a")[0])

    def test_a_read_that_timed_out_may_be_retried(self):
        def slow(args, **kw):
            raise sources.subprocess.TimeoutExpired(args, 30)
        self.assertEqual(75, self.call(slow, "--files", "a")[0])


if __name__ == "__main__":
    unittest.main()
