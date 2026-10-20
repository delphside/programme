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

from board.org_sync import Item, apply, check, missing, unseen
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


class Unseen(Cases):

    def test_a_named_repository_the_listing_left_out(self):
        self.assertEqual(unseen(["programme"], ["programme", "service-desk"]),
                         ["service-desk"])
        self.assertEqual(unseen(["programme", "other"], ["programme"]), [])


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
        self.assertEqual((tally.added, tally.missing, tally.failed), (1, 2, 1))
        self.assertIn((True, "  service-desk#1 could not be added"), tally.lines)


class Check(Cases):

    def test_reports_and_changes_nothing(self):
        tally = check([item(1, kind="pull request"), item(2, on_board=True)])
        self.assertEqual(tally.missing, 1)
        self.assertEqual(tally.added, 0)
        self.assertEqual(tally.lines, [(False, "  service-desk#1 (pull request) is not on the board")])


class Help(Cases):

    def test_help_lists_its_messages_and_exits_0(self):
        out = run("board/board-add.py", "--help")
        self.expect("exit 0", 0, out.returncode)
        for message in ("--check", "is not on the board", "could not be added",
                        "is not visible to this token", "could not read"):
            self.expect(message, True, message in out.stdout)


# A stub `gh`, first on PATH. The organisation lists `programme` and
# `service-desk`, or only `programme` under GH_HIDE=service-desk, as a token that
# cannot see a repository leaves it out. Each repository has two open issues,
# answered a page at a time, and one open pull request. `programme`'s items are
# on the fake board (`PVT_fakeboard`); `service-desk`'s are not. GH_FAIL=repos
# refuses the listing, GH_FAIL=issues one repository's issues. Any write exits
# 9, so `--check` is seen to make none.
_STUB_GH = r"""#!/usr/bin/env python3
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
def node(number, repo):
    board = "PVT_fakeboard" if repo == "programme" else "PVT_other"
    return {"number": number, "id": f"I_{repo}_{number}",
            "projectItems": {"nodes": [{"project": {"id": board}}]}}
if "mutation" in query:
    sys.exit(9)
if "organization(" in query:
    names = [n for n in ("programme", "service-desk") if n != os.environ.get("GH_HIDE")]
    answer("repos", {"organization": {"repositories": {
        "pageInfo": {"hasNextPage": False, "endCursor": None},
        "nodes": [{"name": n} for n in names]}}})
repo = args.get("repo", "")
if "pullRequests(" in query:
    answer("prs", {"repository": {"pullRequests": {
        "pageInfo": {"hasNextPage": False, "endCursor": None},
        "nodes": [node(9, repo)]}}})
if "issues(" in query:
    second = args.get("cursor") == "page2"
    answer("issues", {"repository": {"issues": {
        "pageInfo": {"hasNextPage": not second, "endCursor": None if second else "page2"},
        "nodes": [node(8 if second else 7, repo)]}}})
print("stub: unexpected query", file=sys.stderr)
sys.exit(8)
"""


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

    def test_check_names_every_missing_item_on_every_page_and_exits_1(self):
        out = self.check()
        self.expect("exit 1", 1, out.returncode)
        for name in ("service-desk#7 (issue)", "service-desk#8 (issue)",
                     "service-desk#9 (pull request)"):
            self.expect(name, True, f"{name} is not on the board" in out.stdout)
        self.expect("not the held ones", False, "programme#" in out.stdout)

    def test_a_repository_the_token_cannot_see_is_reported(self):
        out = self.check(GH_HIDE="service-desk")
        self.expect("exit 1", 1, out.returncode)
        self.expect("names it", True,
                    "service-desk is not visible to this token" in out.stderr)

    def test_a_read_that_fails_exits_2(self):
        self.expect("the repositories unreadable exits 2", 2,
                    self.check(GH_FAIL="repos").returncode)
        self.expect("an issue list unreadable exits 2", 2,
                    self.check(GH_FAIL="issues").returncode)
