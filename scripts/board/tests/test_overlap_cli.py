"""`board-overlap.py`: a check run to report, so it exits 0 whatever it finds."""

import importlib.util
import json
import os
import stat
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from unittest import mock

from board import profile, records, sources

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
        path, _, query = args[2].partition("?")
        value = self.answers.get(path)
        page = urllib.parse.parse_qs(query).get("page")
        if isinstance(value, list) and page:
            value = value[100 * (int(page[0]) - 1):100 * int(page[0])]
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

    def test_a_pull_request_that_is_not_there_is_a_business_error(self):
        gh = Github(ANSWERS)
        self.assertEqual(65, self.call(gh, "--pr", "o/r#99")[0])
        self.assertEqual(65, self.call(gh, "--pr", "o/r#99", "--exit-code")[0])

    def test_a_repository_that_is_not_there_is_a_business_error(self):
        self.assertEqual(65, self.call(Github({}), "--files", "a", "--repo", "p/q")[0])
        self.assertEqual(65, self.call(Github({}), "--files", "a", "--repo", "p/q", "--exit-code")[0])

    def test_the_applications_own_repository_missing_cannot_judge(self):
        self.assertEqual(2, self.call(Github({}), "--files", "a")[0])

    def test_a_missing_live_checkout_cannot_judge_even_with_exit_code(self):
        gone = records.NoLiveCheckout(Path("/nowhere"))
        for flags in ((), ("--exit-code",)):
            with mock.patch("builtins.print") as out, \
                    mock.patch.object(profile, "repository_name", side_effect=gone), \
                    mock.patch("sys.stderr"):
                self.assertEqual(2, _command().main(["--files", "a", *flags]))
            self.assertEqual([], [c for c in out.call_args_list if not c.kwargs])

    def test_a_renamed_file_counts_under_both_names(self):
        renamed = {**ANSWERS, "repos/o/r/pulls": [pr(7, "mover")],
                   "repos/o/r/pulls/7/files": [{"filename": "new.md", "previous_filename": "old.md"}]}
        self.assertEqual(["OVERLAP o/r#7 mover — old.md"], self.call(Github(renamed), "--files", "old.md")[1])
        self.assertEqual(["OVERLAP o/r#7 mover — new.md"], self.call(Github(renamed), "--files", "new.md")[1])

    def test_more_than_a_hundred_pull_requests_are_all_read(self):
        many = {"repos/o/r/pulls": [pr(n, f"t{n}") for n in range(1, 151)]}
        many.update({f"repos/o/r/pulls/{n}/files": files("x.md" if n == 150 else f"f{n}") for n in range(1, 151)})
        self.assertEqual(["OVERLAP o/r#150 t150 — x.md"], self.call(Github(many), "--files", "x.md")[1])

    def test_more_than_a_hundred_files_are_all_read(self):
        many = {"repos/o/r/pulls": [pr(1, "big")],
                "repos/o/r/pulls/1/files": files(*[f"f{n}" for n in range(130)])}
        self.assertEqual(["OVERLAP o/r#1 big — f129"], self.call(Github(many), "--files", "f129")[1])

    def test_a_draft_claims_like_any_open_pull_request(self):
        draft = {"repos/o/r/pulls": [{**pr(4, "wip", "Claims: d.md"), "draft": True}],
                 "repos/o/r/pulls/4/files": files("z")}
        self.assertEqual(["OVERLAP o/r#4 wip — d.md"], self.call(Github(draft), "--files", "d.md")[1])

    def test_a_pull_request_that_is_closed_or_merged_is_not_compared(self):
        for raw, word in (({"state": "closed", "merged": False}, "closed"),
                          ({"state": "closed", "merged": True}, "merged")):
            gh = Github({**ANSWERS, "repos/o/r/pulls/2": {**pr(2, "second"), **raw}})
            code, lines = self.call(gh, "--pr", "o/r#2", "--exit-code")
            self.assertEqual(0, code)
            self.assertEqual(1, len(lines), lines)
            self.assertIn(f"is {word}", lines[0])
            self.assertEqual(["repos/o/r/pulls/2"], gh.asked)

    def test_a_pull_request_has_its_files_read_once(self):
        gh = Github(ANSWERS)
        self.call(gh, "--pr", "o/r#2")
        self.assertEqual(1, gh.asked.count("repos/o/r/pulls/2/files?per_page=100&page=1"), gh.asked)

    def test_a_refused_read_cannot_judge(self):
        refused = Github({"repos/o/r/pulls": mock.Mock(returncode=1, stdout="", stderr="HTTP 403: refused")})
        self.assertEqual(2, self.call(refused, "--files", "a")[0])

    def test_a_read_that_timed_out_may_be_retried(self):
        def slow(args, **kw):
            raise sources.subprocess.TimeoutExpired(args, 30)
        self.assertEqual(75, self.call(slow, "--files", "a")[0])


class InTheProgrammesOwnCheckout(unittest.TestCase):
    """Where there is no programme file and no profile, `--files --repo` and
    `--pr` still read, and the other modes say what they need."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        root = Path(self.dir.name)
        (root / "bin").mkdir()
        gh = root / "bin" / "gh"
        gh.write_text("#!/bin/sh\ncase \"$2\" in\n  repos/p/q/pulls\\?*) echo '[]';;\n"
                      "  repos/p/q/pulls/5) echo '{\"state\": \"closed\"}';;\n"
                      "  *) echo 'HTTP 404: Not Found' >&2; exit 1;;\nesac\n")
        gh.chmod(gh.stat().st_mode | stat.S_IXUSR)
        (root / "repo").mkdir()
        os.system(f"git -C {root / 'repo'} init -q")
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("PROGRAMME_", "BOARD_"))}
        self.env["PATH"] = f"{root / 'bin'}:{self.env['PATH']}"
        self.cwd = root / "repo"

    def go(self, *args):
        return run(COMMAND, *args, cwd=self.cwd, env=self.env)

    def test_files_with_repo_needs_no_profile(self):
        done = self.go("--files", "a", "--repo", "p/q")
        self.assertEqual((0, "ok overlap: none\n"), (done.returncode, done.stdout), done.stderr)

    def test_pr_needs_no_profile(self):
        done = self.go("--pr", "p/q#5")
        self.assertEqual((0, "ok overlap: p/q#5 is closed, so nothing was compared\n"),
                         (done.returncode, done.stdout), done.stderr)

    def test_without_repo_the_profile_is_still_asked_for(self):
        done = self.go("--files", "a")
        self.assertEqual(70, done.returncode)
        self.assertIn("programme file", done.stderr)

    def test_all_still_needs_the_programme_file(self):
        self.assertEqual(70, self.go("--all").returncode)


if __name__ == "__main__":
    unittest.main()
