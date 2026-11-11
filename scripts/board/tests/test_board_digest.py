"""`board-digest.py`'s wiring: what it reads, and what it hands the digest.

From the rules, not the code: the removed files and the repositories' visibility
are read once and reach `build`, and a private repository is kept out of the
waiting list. No network: every read is stubbed."""

import importlib.util
import unittest
from pathlib import Path
from unittest import mock

from board import sources
from board.sources import MergedPullRequest, MergedPullRequests

from .cases import Cases

SCRIPT = Path(__file__).resolve().parents[1] / "board-digest.py"


def load():
    spec = importlib.util.spec_from_file_location("board_digest_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TheDigestScript(Cases):
    def test_it_hands_the_digest_what_it_read(self):
        bd = load()
        merged = MergedPullRequests([MergedPullRequest("o/own", 1, "own", ""),
                                     MergedPullRequest("o/other", 2, "other", "")])
        merged.unread = ("o/hidden",)
        seen = {"o/own": False, "o/other": True, "o/hidden": None, "o/open": False}
        calls = {}
        registers = mock.Mock()
        registers.read_text.return_value = ""
        with mock.patch.object(bd.profile, "repository_name", return_value="o/own"), \
             mock.patch.object(bd.profile, "watched_repositories", return_value=("o/other", "o/hidden", "o/open")), \
             mock.patch.object(bd.records, "improvement_registers", return_value=registers), \
             mock.patch.object(bd, "fetch", return_value=sources.Snapshot((), 0, 0, 0, True)), \
             mock.patch.object(bd, "visibility", return_value=seen), \
             mock.patch.object(bd, "merged_pull_requests", return_value=merged) as search, \
             mock.patch.object(bd, "removed_files", return_value=({("o/other", 2): ("x",)}, (("o/other", 9),))) as files, \
             mock.patch.object(bd, "open_pull_requests", return_value=()), \
             mock.patch.object(bd, "build", side_effect=lambda *a, **kw: calls.update(kw)), \
             mock.patch.object(bd, "render", return_value=""):
            code = bd.main(["--since", "2026-10-19"])
        self.expect("exit", 0, code)
        self.expect("the visibility read once is the search's", seen, search.call_args.args[1])
        self.expect("only other repositories' pull requests have their files read",
                    ["o/other"], [p.repository for p in files.call_args.args[0]])
        self.expect("the files reach the digest", ({("o/other", 2): ("x",)}, [("o/other", 9)]),
                    (calls["removed"], list(calls["removed_unread"])))
        self.expect("private and unreadable repositories are counted only",
                    {"o/other", "o/hidden"}, set(calls["private_repositories"]))
        self.expect("an unreadable repository is passed on", ("o/hidden",), tuple(calls["unread_repositories"]))


if __name__ == "__main__":
    unittest.main()
