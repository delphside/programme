"""A release's range in git: which commits name which issue once reverts are
counted, which release tags lie in it, and what a tag carries.

From the rules (design §9 *The milestone gate*, §10 *The record*), against a real
history because the answer is git's:

  evidence   a commit a later commit in the range reverts, and the revert, name
             nothing; reverts count by parity (a revert of a revert keeps the
             change, a third leaves it out); a revert of a commit outside the
             range has no effect; a short sha is matched
  tags       the release tags, of any prefix, whose commit is in the range
  records    a tag's message is its record; a text tag is history only; a record
             of a version this tool does not know is refused
  unreadable a range git cannot list raises, and is never read as empty"""

import json
from unittest import mock

from board import repo
from board.sources import Unavailable

from .cases import Cases
from .gitrepo import History
from .profiles import inside


class TheEvidence(Cases):

    def test_a_revert_takes_the_change_and_itself_out(self):
        """a revert takes the change and itself out"""
        with History() as h, inside(h.path):
            h.commit("base\n\nRefs #1")
            a = h.commit("feature\n\nRefs #12")
            h.revert(a, "Refs #13")
            h.commit("other\n\nRefs #14")
            self.expect("all of it, reverts counted", {1: 1, 12: 1, 13: 1, 14: 1},
                        dict(repo.named_in_range("main", effective=False)))
            self.expect("the reverted commit and the revert name nothing", {1: 1, 14: 1},
                        dict(repo.named_in_range("main")))

    def test_reverts_count_by_parity(self):
        """a revert of a revert keeps the change, a third leaves it out"""
        with History() as h, inside(h.path):
            a = h.commit("feature\n\nRefs #12")
            r1 = h.revert(a)
            self.expect("one revert: out", {}, dict(repo.named_in_range("main")))
            r2 = h.revert(r1)
            self.expect("a revert of the revert: the change stands", {12: 1},
                        dict(repo.named_in_range("main")))
            h.revert(r2)
            self.expect("a third: out again", {}, dict(repo.named_in_range("main")))

    def test_a_revert_of_a_commit_outside_the_range_has_no_effect(self):
        """a revert of a commit outside the range has no effect"""
        with History() as h, inside(h.path):
            old = h.commit("old\n\nRefs #5")
            h.tag("v1", at=old)
            h.revert(old, "Refs #6")
            h.commit("new\n\nRefs #7")
            self.expect("the revert is counted for what it says", {6: 1, 7: 1},
                        dict(repo.named_in_range("v1..main")))

    def test_a_short_sha_is_matched_and_prose_is_not(self):
        """a short sha is matched, and prose naming a sha is not a revert"""
        with History() as h, inside(h.path):
            a = h.commit("feature\n\nRefs #12")
            h.commit(f"Revert\n\nRefs #13\nThis reverts commit {a[:9]}.")
            self.expect("the short sha reverts it", {}, dict(repo.named_in_range("main")))
        with History() as h, inside(h.path):
            a = h.commit("feature\n\nRefs #12")
            h.commit(f"talks about {a} in prose\n\nRefs #13")
            self.expect("prose is not a revert", {12: 1, 13: 1}, dict(repo.named_in_range("main")))

    def test_a_prefix_is_matched_against_the_range_without_git(self):
        """a revert's sha is matched as a prefix of the range's own, with no question to git"""
        full = "abc1234" + "0" * 33
        other = "def5678" + "0" * 33
        commits = [("f" * 40, f"Revert\n\nThis reverts commit abc1234."), (other, "x"), (full, "feature")]
        with mock.patch.object(repo, "_git", side_effect=AssertionError("git was asked")):
            skip = repo.reverted_in(commits)
        self.expect("the prefix finds the one commit; the revert goes too", {"f" * 40, full}, set(skip))
        with mock.patch.object(repo, "_git", side_effect=AssertionError("git was asked")):
            self.expect("a prefix of nothing in the range has no effect", frozenset(),
                        repo.reverted_in([("f" * 40, "This reverts commit 1111111"), (full, "feature")]))

    def test_an_ambiguous_prefix_refuses(self):
        """a prefix that fits two commits of the range refuses, and is not read as no revert"""
        a, b = "abc1234" + "1" * 33, "abc1234" + "2" * 33
        commits = [("f" * 40, "This reverts commit abc1234"), (a, "one"), (b, "two")]
        try:
            repo.reverted_in(commits)
        except Unavailable as exc:
            self.expect("it says why", True, "abc1234" in str(exc) and "2 commits" in str(exc))
        else:
            self.expect("it raises", True, False)

    def test_an_unreadable_range_raises(self):
        """a range git cannot list raises"""
        with History() as h, inside(h.path):
            h.commit("one\n\nRefs #1")
            with self.assertRaises(Unavailable):
                repo.named_in_range("no-such-tag..main")


class TheTags(Cases):

    def test_tags_of_any_prefix_in_the_range(self):
        """release tags of any prefix whose commit is in the range"""
        with History() as h, inside(h.path):
            a = h.commit("one")
            h.tag("prod-0.9.0", at=a)
            h.tag("v0.10.0", at=h.commit("two"))
            h.tag("v0.10.1", at=h.commit("three"))
            h.tag("other-1", at=h.commit("four"))
            h.commit("five")
            got = sorted(repo.tags_in_range("v0.10.0..main", ["v", "prod-"]))
            self.expect("the later tag only, and none of another prefix", ["v0.10.1"], got)
            self.expect("the whole history reaches the history prefix too",
                        ["prod-0.9.0", "v0.10.0", "v0.10.1"],
                        sorted(repo.tags_in_range("main", ["v", "prod-"])))
            self.expect("a version is the tag less its prefix", "0.9.0",
                        repo.tag_version("prod-0.9.0", ["v", "prod-"]))

    def test_a_record_a_text_tag_and_an_unknown_record(self):
        """a record, a text tag, and a record version this tool does not read"""
        record = {"record": 1, "version": "0.10.2", "carries": {"work_packages": [3], "issues": [], "releases": []}}
        with History() as h, inside(h.path):
            a = h.commit("one")
            h.tag("v0.10.2", json.dumps(record), at=a)
            h.tag("v0.10.1", "Release 0.10.1", at=a)
            h.tag("v9", json.dumps({"record": 2}), at=a)
            self.expect("the message is the record", record, repo.tag_record("v0.10.2"))
            self.expect("a text tag has none: history only", None, repo.tag_record("v0.10.1"))
            with self.assertRaises(Unavailable):
                repo.tag_record("v9")

    def test_the_origin_is_a_slug(self):
        """the origin URL is owner/name"""
        with History() as h, inside(h.path):
            self.expect("no origin", None, repo.origin_slug())
            h.git("remote", "add", "origin", "git@github.com:fakeorg/widget.git")
            self.expect("ssh form", "fakeorg/widget", repo.origin_slug())
            h.git("remote", "set-url", "origin", "https://github.com/fakeorg/widget")
            self.expect("https form", "fakeorg/widget", repo.origin_slug())
            h.git("remote", "set-url", "origin", "/srv/git/widget.git")
            self.expect("not GitHub", None, repo.origin_slug())
