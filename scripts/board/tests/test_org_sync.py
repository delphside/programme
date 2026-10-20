"""Every open issue and pull request in the organisation goes on the board.
On canned records, with no network. The rules are
`scripts/board/board-add.py`'s help and `scripts/board/org_sync.py`'s header:

  missing      an open item the board does not hold is added
  held         one it holds is left alone
  failed add   reported, not counted as added, and the run goes on
  --check      reports the same items and changes nothing
"""

import os
import tempfile
from pathlib import Path

from board.org_sync import Item, apply, check, missing
from board.sources import Unavailable

from .cases import Cases
from .cli import run


def item(number=1, on_board=False, repo="service-desk", kind="issue"):
    return Item(repo, kind, number, f"I_{repo}_{number}", on_board)


class Board:
    """A fake GitHub: records every add, refuses what it is told to."""

    def __init__(self, refuse=()):
        self.added, self.refuse = [], refuse

    def add(self, node_id):
        if node_id in self.refuse:
            raise Unavailable("refused")
        self.added.append(node_id)
        return "PVTI_" + node_id


class Missing(Cases):

    def test_only_what_the_board_does_not_hold(self):
        items = [item(1), item(2, on_board=True), item(3, repo="programme", kind="pull request")]
        self.assertEqual([i.name for i in missing(items)],
                         ["service-desk#1", "programme#3"])

    def test_nothing_missing_is_nothing(self):
        self.assertEqual(missing([item(1, on_board=True)]), [])


class Apply(Cases):

    def test_adds_each_missing_item_once(self):
        board = Board()
        tally = apply([item(1), item(2, on_board=True)], board.add)
        self.assertEqual(board.added, ["I_service-desk_1"])
        self.assertEqual((tally.added, tally.missing), (1, 1))

    def test_a_failed_add_is_reported_not_counted_and_the_run_goes_on(self):
        board = Board(refuse={"I_service-desk_1"})
        tally = apply([item(1), item(2)], board.add)
        self.assertEqual(board.added, ["I_service-desk_2"])
        self.assertEqual((tally.added, tally.missing), (1, 2))
        self.assertIn((True, "  service-desk#1 could not be added"), tally.lines)


class Check(Cases):

    def test_reports_and_changes_nothing(self):
        tally = check([item(1, kind="pull request"), item(2, on_board=True)])
        self.assertEqual(tally.missing, 1)
        self.assertEqual(tally.added, 0)
        self.assertEqual(tally.lines, [(False, "  service-desk#1 (pull request) is not on the board")])


class Help(Cases):

    def test_help_names_both_forms(self):
        out = run("board/board-add.py", "--help")
        self.assertEqual(out.returncode, 0)
        self.assertIn("--check", out.stdout)


# A stub `gh`, first on PATH: the organisation holds two repositories, each with
# one open issue and no pull requests. `programme`'s issue is on the fake board
# (`PVT_fakeboard`); `service-desk`'s is not. GH_FAIL=repos refuses the
# repository list, GH_FAIL=issues one repository's issues. Any write exits 9,
# so `--check` is seen to make none.
_STUB_GH = r'''#!/usr/bin/env python3
import json, os, sys
args = dict(a.split("=", 1) for a in sys.argv if "=" in a)
query = args.get("query", "")
fail = os.environ.get("GH_FAIL", "")
def answer(what, data):
    if fail == what:
        print("stub: refused", file=sys.stderr)
        sys.exit(1)
    print(json.dumps({"data": data}))
    sys.exit(0)
page = {"hasNextPage": False, "endCursor": None}
if "mutation" in query:
    sys.exit(9)
if "organization(" in query:
    answer("repos", {"organization": {"repositories": {"pageInfo": page,
        "nodes": [{"name": "programme"}, {"name": "service-desk"}]}}})
if "pullRequests(" in query:
    answer("prs", {"repository": {"pullRequests": {"pageInfo": page, "nodes": []}}})
if "issues(" in query:
    held = args.get("repo") == "programme"
    answer("issues", {"repository": {"issues": {"pageInfo": page, "nodes": [
        {"number": 7, "id": "I_" + args.get("repo", ""), "projectItems": {"nodes":
            [{"project": {"id": "PVT_fakeboard" if held else "PVT_other"}}]}}]}}})
print("stub: unexpected query", file=sys.stderr)
sys.exit(8)
'''


class TheCommandsExitStatuses(Cases):
    """`board-add.py --check` run as its callers run it, against a stub `gh`."""

    @classmethod
    def setUpClass(cls):
        cls._dir = tempfile.TemporaryDirectory()
        gh = Path(cls._dir.name) / "gh"
        gh.write_text(_STUB_GH)
        gh.chmod(0o755)

    @classmethod
    def tearDownClass(cls):
        cls._dir.cleanup()

    def check(self, **env):
        full = dict(os.environ, PATH=f"{self._dir.name}{os.pathsep}{os.environ['PATH']}",
                    **env)
        return run("board/board-add.py", "--check", env=full)

    def test_check_names_what_is_missing_in_every_repository_and_exits_1(self):
        out = self.check()
        self.expect("exit 1", 1, out.returncode)
        self.expect("names the missing one", True,
                    "service-desk#7 (issue) is not on the board" in out.stdout)
        self.expect("not the held one", False, "programme#7" in out.stdout)

    def test_a_read_that_fails_exits_2(self):
        self.expect("the repositories unreadable exits 2", 2,
                    self.check(GH_FAIL="repos").returncode)
        self.expect("an issue list unreadable exits 2", 2,
                    self.check(GH_FAIL="issues").returncode)
