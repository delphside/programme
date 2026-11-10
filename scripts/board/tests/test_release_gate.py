"""The release's board gates: tests passed, and the milestone as a shipping list.

From the rules (design §9 *The milestone gate*, §10 *The record*), not the code.
The board is a fixture (`sources.fetch` and `sources.issues_in_full` are
replaced); git is a real history, because the evidence is git's.

  evidence    every open issue in the milestone has a `Refs #N` commit in the
              release, parents aside; a commit that is reverted, and its
              revert, name nothing
  parents     a parent's `Refs` is reported beside its work package and never
              counted for it (delphside/tile-lite-elite#375)
  emergency   an issue evidenced only on `main` is left out, not refused
  routes      a Production Release work package the commits name is in the
              milestone or an undeployed earlier release's; other routes are not
  earlier     an undeployed release in the range is carried too, less what only
              a reverted commit named; what it drops is reported as a check
  tests       every work package in the milestone has its tests ticked: a gate,
              and a reported check under `--emergency`
  unreadable  a board that cannot be read refuses; it is never read as empty"""

import json
import unittest
from types import SimpleNamespace
from unittest import mock

from board import release
from board.model import RawIssue, RawSubIssue
from board.release import GateRequest, gate
from board.sources import Unavailable

from .cases import Cases
from .gitrepo import History
from .profiles import inside

TICKED = ("## Test approach\n\n### Functional user tests — Preview\n\n- [x] **Claude** — a\n\n"
          "### Technical tests — Rehearsal\n\n- [x] **Claude** — b\n")
UNTICKED = TICKED.replace("[x] **Claude** — a", "[ ] **owner** — a")


def raw(n, type="Requirement", milestone="0.10.2", parent=None, subs=(), route=None,
        body="", state="OPEN"):
    fields = {"Route": route} if route else {}
    return RawIssue(n, f"issue {n}", state, body, type, fields, tuple(subs), parent,
                    milestone, frozenset())


def wp(n, milestone="0.10.2", parent=None, route="Production Release", body=TICKED):
    return raw(n, "Project", milestone, parent=parent if parent is not None else 9000 + n,
               route=route, body=body)


def request(sha, **kw):
    base = dict(version="0.10.2", sha=sha, range=sha, main_range="main", carry_from=None,
                prefixes=("v", "prod-"), emergency=False, milestone_set_aside=False)
    base.update(kw)
    return GateRequest(**base)


class Board:
    """`sources` as a fixture: the open issues, and the others by number."""

    def __init__(self, open_issues, others=()):
        self.open = list(open_issues)
        self.others = {r.number: r for r in others}
        self.unavailable = False

    def __enter__(self):
        def fetch(states="OPEN", with_bodies=True, with_pull_requests=True, pr_states="OPEN"):
            if self.unavailable:
                raise Unavailable("GitHub did not answer")
            return SimpleNamespace(issues=tuple(self.open))

        def in_full(numbers):
            if self.unavailable:
                raise Unavailable("GitHub did not answer")
            return {n: self.others[n] for n in numbers if n in self.others}

        self.patches = [mock.patch.object(release.sources, "fetch", fetch),
                        mock.patch.object(release.sources, "issues_in_full", in_full)]
        for p in self.patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in self.patches:
            p.stop()


def verdicts(result):
    return {g.name: (g.passed, g.message) for g in result.gates}


class TheMilestoneIsAShippingList(Cases):

    def test_evidence_in_the_release(self):
        """an open issue needs a Refs commit in the release"""
        with History() as h, inside(h.path):
            h.commit("base\n\nRefs #99")
            h.tag("v0.10.1")
            sha = h.commit("a feature\n\nRefs #12")
            with Board([raw(12), raw(13)]):
                result = gate(request(sha, range=f"v0.10.1..{sha}"))
            self.expect("the unevidenced issue refuses", (False, "open in milestone 0.10.2 but no commit in the release says Refs: #13"),
                        verdicts(result)["milestone"])
            with Board([raw(12)]):
                result = gate(request(sha, range=f"v0.10.1..{sha}"))
            self.expect("every issue evidenced passes and is carried", (True, "carries work packages [] and issues [12]"),
                        verdicts(result)["milestone"])
            self.expect("and says so", {"work_packages": [], "issues": [12], "releases": []}, result.carries)
            with Board([raw(99)]):
                result = gate(request(sha, range=f"v0.10.1..{sha}"))
            self.expect("a commit before the release is not evidence", False, result.passed)

    def test_a_revert_takes_the_evidence_away(self):
        """a commit that is reverted, and the revert, name nothing"""
        with History() as h, inside(h.path):
            a = h.commit("a feature\n\nRefs #12")
            sha = h.revert(a, "Refs #12")
            with Board([raw(12)]):
                result = gate(request(sha))
            self.expect("the issue has no evidence left", False, verdicts(result)["milestone"][0])

    def test_a_parent_s_commits_are_reported_never_counted(self):
        """a parent's Refs is shown beside its work package, never counted for it"""
        with History() as h, inside(h.path):
            sha = h.commit("work\n\nRefs #301\nRefs #302")
            parent = raw(301, "Project", milestone=None, subs=(RawSubIssue(363, "Project"), RawSubIssue(364, "Project")))
            with Board([parent, wp(363, parent=301), raw(364, "Project", parent=301, route="Production Release", body=TICKED)]):
                result = gate(request(sha))
            ok, message = verdicts(result)["milestone"]
            self.expect("the package is refused although its parent has commits", False, ok)
            self.expect("with the parent's count beside it", True,
                        "#363 (parent #301 has 1)" in message and "#364 (parent #301 has 1)" in message)
            self.expect("the parent itself is never a finding", False, "#301 " in message.replace("parent #301", ""))
            with Board([parent, wp(363, parent=301)]):
                result = gate(request(h.commit("own\n\nRefs #363")))
            self.expect("a package with its own commit passes", True, result.passed)
            self.expect("and the parent is not carried", [363], result.carries["work_packages"])

    def test_a_parent_with_one_package_does_not_credit_it(self):
        """a parent with a single work package is still not credit for it: the package is refused"""
        with History() as h, inside(h.path):
            sha = h.commit("work\n\nRefs #301")
            parent = raw(301, "Project", milestone=None, subs=(RawSubIssue(363, "Project"),))
            with Board([parent, wp(363, parent=301)]):
                result = gate(request(sha))
            ok, message = verdicts(result)["milestone"]
            self.expect("refused although the parent has a commit", False, ok)
            self.expect("with the parent's count beside it", True, "#363 (parent #301 has 1)" in message)

    def test_an_emergency_leaves_out_what_only_main_evidences(self):
        """an issue evidenced only on main is left out, and others still refuse"""
        with History() as h, inside(h.path):
            base = h.commit("base")
            h.tag("v0.10.1", at=base)
            sha = h.commit("the fix\n\nRefs #30")
            h.git("branch", "emergency")
            h.git("reset", "-q", "--hard", base)
            h.commit("on main only\n\nRefs #9")
            main = h.git("rev-parse", "HEAD")
            req = dict(range=f"v0.10.1..{sha}", main_range=f"v0.10.1..{main}", emergency=True)
            with Board([raw(30), raw(9)]):
                result = gate(request(sha, **req))
            self.expect("passes", True, verdicts(result)["milestone"][0])
            self.expect("the main-only issue is left out", [9], result.left_out)
            self.expect("and not carried", [30], result.carries["issues"])
            with Board([raw(30), raw(77)]):
                result = gate(request(sha, **req))
            self.expect("an issue evidenced nowhere still refuses", False, result.passed)
            with Board([raw(30), raw(9)]):
                result = gate(request(sha, range=f"v0.10.1..{sha}", main_range=f"v0.10.1..{main}"))
            self.expect("without the flag nothing is left out", False, result.passed)

    def test_production_release_work_packages_the_commits_name(self):
        """a Production Release work package the commits name is in the milestone or an earlier release's"""
        with History() as h, inside(h.path):
            sha = h.commit("work\n\nRefs #40\nRefs #41\nRefs #42\nRefs #43")
            others = [wp(40, milestone="2026.11.03-1"), wp(41, milestone=None),
                      wp(42, milestone="2026.11.03-1", route="Application Tooling"),
                      raw(43, "Requirement", milestone="2026.11.03-1")]
            with Board([], others):
                result = gate(request(sha))
            ok, message = verdicts(result)["milestone"]
            self.expect("outside the milestone refuses", False, ok)
            self.expect("naming only the Production Release packages", True,
                        message.startswith("work package(s) #40 #41 name Route Production Release in "))
            with Board([wp(40), wp(41)], others[2:]):
                result = gate(request(sha))
            self.expect("in the milestone passes; other routes and types are left out", True, result.passed)

    def test_a_set_aside_milestone_carries_what_stands(self):
        """set aside, the milestone's open items are carried as they stand"""
        with History() as h, inside(h.path):
            sha = h.commit("nothing")
            with Board([raw(12), wp(40), raw(60, "Project", milestone="0.10.2", subs=(RawSubIssue(1, "Project"),))]):
                result = gate(request(sha, milestone_set_aside=True))
            self.expect("passes with no evidence", True, result.passed)
            self.expect("a parent aside", {"work_packages": [40], "issues": [12], "releases": []}, result.carries)


class AnEarlierReleaseInTheRange(Cases):

    def history(self, h, record=True):
        h.commit("base")
        h.tag("v0.10.1")
        a = h.commit("one\n\nRefs #1")
        b = h.commit("two\n\nRefs #2")
        c = h.commit("three\n\nRefs #3")
        message = json.dumps({"record": 1, "version": "0.10.2", "carries": {
            "work_packages": [], "issues": [1, 2, 3], "releases": []}}) if record else "Release 0.10.2"
        h.tag("v0.10.2", message)
        return a, b, c

    def test_with_a_record_it_is_carried_less_what_a_revert_took(self):
        """an undeployed release is carried, less what only a reverted commit named"""
        with History() as h, inside(h.path):
            a, b, c = self.history(h)
            h.revert(b)
            sha = h.commit("four\n\nRefs #4")
            with Board([raw(4, milestone="0.10.3")]):
                result = gate(request(sha, version="0.10.3", range=f"v0.10.1..{sha}", carry_from="v0.10.1"))
            self.expect("passes", True, result.passed)
            self.expect("it carries its own and the earlier release's", {"work_packages": [], "issues": [1, 3, 4],
                        "releases": [{"version": "0.10.2", "work_packages": [], "issues": [1, 3], "dropped": [2]}]},
                        result.carries)
            self.expect("the drop is reported as a check", ["#2 is in 0.10.2 but not carried by 0.10.3"], result.notes)
            self.expect("the message names the release", True,
                        "(earlier releases in the range: [\"0.10.2\"])" in verdicts(result)["milestone"][1])

    def test_without_a_record_its_milestone_stands_for_it(self):
        """a release made before the tool: its milestone's open items, where a commit names them"""
        with History() as h, inside(h.path):
            self.history(h, record=False)
            sha = h.commit("four\n\nRefs #4")
            held = [raw(1, milestone="0.10.2"), raw(2, milestone="0.10.2"), raw(8, milestone="0.10.2"),
                    raw(3, "Project", milestone="0.10.2", parent=77, route="Production Release", body=TICKED),
                    raw(4, milestone="0.10.3")]
            with Board(held[:2] + held[2:3] + held[4:] + [wp(3)]):
                result = gate(request(sha, version="0.10.3", range=f"v0.10.1..{sha}", carry_from="v0.10.1"))
            release_ = result.carries["releases"][0]
            self.expect("named items are carried, the unnamed one is dropped",
                        ([3], [1, 2], [8]), (release_["work_packages"], release_["issues"], release_["dropped"]))
            self.expect("a work package in an earlier release's milestone is not absent", True, result.passed)

    def test_a_record_of_an_unknown_version_refuses(self):
        """a reader refuses an unknown record version"""
        with History() as h, inside(h.path):
            h.commit("base")
            h.tag("v0.10.1")
            h.commit("one\n\nRefs #1")
            h.tag("v0.10.2", json.dumps({"record": 2}))
            sha = h.commit("two\n\nRefs #2")
            with Board([raw(2, milestone="0.10.3")]):
                with self.assertRaises(Unavailable):
                    gate(request(sha, version="0.10.3", range=f"v0.10.1..{sha}", carry_from="v0.10.1"))


class TheTestsPassedGate(Cases):

    def test_unticked_boxes_refuse(self):
        """a work package with an unticked box refuses the release"""
        with History() as h, inside(h.path):
            sha = h.commit("work\n\nRefs #40\nRefs #41")
            with Board([wp(40), wp(41, body=UNTICKED)]):
                result = gate(request(sha))
            ok, message = verdicts(result)["tests-passed"]
            self.expect("refused", False, ok)
            self.expect("naming it and what is unticked", True,
                        "#41" in message and "1 unticked under Functional user tests" in message and "#40" not in message)
            self.expect("the milestone gate is still judged", True, verdicts(result)["milestone"][0])

    def test_a_package_with_no_headings_refuses_too(self):
        """a package that never said what it would test refuses"""
        with History() as h, inside(h.path):
            sha = h.commit("work\n\nRefs #40")
            with Board([wp(40, body="## Design\n")]):
                result = gate(request(sha))
            self.expect("refused, in other words", (False, True), (result.passed,
                        "no Functional user tests or Technical tests heading" in verdicts(result)["tests-passed"][1]))

    def test_an_emergency_reports_instead_of_refusing(self):
        """with --emergency the gate is a check: reported, not refused"""
        with History() as h, inside(h.path):
            sha = h.commit("work\n\nRefs #41")
            with Board([wp(41, body=UNTICKED)]):
                result = gate(request(sha, emergency=True, main_range=sha))
            ok, message = verdicts(result)["tests-passed"]
            self.expect("passes", True, ok)
            self.expect("but says what was not ticked", True, message.startswith("emergency:") and "#41" in message)
            self.expect("and is listed as reported, not plainly passed", "reported",
                        {g["name"]: g["result"] for g in result.as_json()["gates"]}["tests-passed"])

    def test_everything_ticked_and_nothing_to_test_pass(self):
        """everything ticked passes; a parent and a requirement owe no tests"""
        with History() as h, inside(h.path):
            sha = h.commit("work\n\nRefs #40\nRefs #12")
            parent = raw(60, "Project", milestone="0.10.2", body="", subs=(RawSubIssue(1, "Project"),))
            with Board([wp(40), raw(12), parent]):
                result = gate(request(sha))
            self.expect("passes", True, verdicts(result)["tests-passed"][0])


class WhenTheBoardCannotBeRead(Cases):

    def test_it_raises_so_the_caller_refuses(self):
        """a board that cannot be read is never read as empty"""
        with History() as h, inside(h.path):
            sha = h.commit("work\n\nRefs #12")
            board = Board([raw(12)])
            board.unavailable = True
            with board:
                with self.assertRaises(Unavailable):
                    gate(request(sha))
            with Board([], []) as b:
                b.open = [raw(12)]
                b.others = {}
                self.expect("a number nothing answers for is left aside", True,
                            gate(request(sha)).passed)

    def test_a_malformed_request_is_a_profile_error(self):
        """a request missing its range is refused as an error, not as a verdict"""
        with self.assertRaises(SystemExit) as caught:
            GateRequest.parse({"version": "0.10.2"})
        self.expect("exit 70", 70, caught.exception.code)


if __name__ == "__main__":
    unittest.main()
