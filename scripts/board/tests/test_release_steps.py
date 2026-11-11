"""What happens after the gates: settling the board from the record, the next
milestone, the GitHub Release and the retrospective issue, and the CI read.

From the rules (design §10 and §12), not the code. GitHub is an in-memory
fixture with the same calls as `sources.py`; a call can be made to fail.

  settle     a carried work package goes to Post-deployment and is told so once;
             a carried issue is told and closed; an item of an earlier release is
             told which release it was in; a dropped item is told and taken out of
             its milestone with its state alone; the milestones close
  rerun      every action checks first, so a second run does nothing and a run
             that failed finishes what was left
  next       the next patch's milestone is opened if it is not, and the left-out
             issues move into it
  publish    the Release and the retrospective issue are each skipped where they
             exist, and a failure of either is named
  checks     each required check's conclusion on the commit; a missing run is
             `missing`, and only success passes"""

import unittest
from unittest import mock

from board import release
from board.model import RawIssue
from board.sources import Unavailable

from .cases import Cases

ANNOUNCEMENT = "Released in v"


def raw(n, type="Requirement", milestone="0.10.2", state="OPEN", project_state=None):
    fields = {"Project State": project_state} if project_state else {}
    return RawIssue(n, f"issue {n}", state, "", type, fields, (), None, milestone, frozenset())


class GitHub:
    """The calls `sources.py` makes, over a dictionary. Every write is logged."""

    def __init__(self, issues=(), milestones=None, comments=None, titled=(), releases=()):
        self.issues = {r.number: r for r in issues}
        self.milestones_ = milestones if milestones is not None else [
            {"number": 7, "title": "0.10.2", "state": "open"}]
        self.comments = {n: list(c) for n, c in (comments or {}).items()}
        self.titles = set(titled)
        self.releases = set(releases)
        self.log = []
        self.fail = set()
        self.unreadable = set()

    def _w(self, name, *args):
        key = (name, *args)
        if name in self.fail or key in self.fail:
            raise Unavailable(f"simulated failure of {key}")
        self.log.append(" ".join(str(a) for a in key))

    def _r(self, name):
        if name in self.unreadable:
            raise Unavailable(f"simulated unreadable {name}")

    def __enter__(self):
        gh = self

        def in_full(numbers):
            gh._r("issues_in_full")
            return {n: gh.issues[n] for n in numbers if n in gh.issues}

        def set_field(n, field, value):
            gh._w("state", n, value)
            from dataclasses import replace
            old = gh.issues[n]
            gh.issues[n] = replace(old, fields={**old.fields, field: value})

        def comment_bodies(n):
            gh._r("comment_bodies")
            return list(gh.comments.get(n, []))

        def add_comment(n, body):
            gh._w("comment", n, body)
            gh.comments.setdefault(n, []).append(body)

        def close_issue(n):
            gh._w("close", n)
            from dataclasses import replace
            gh.issues[n] = replace(gh.issues[n], state="CLOSED")

        def set_milestone(n, number):
            gh._w("milestone", n, number)
            from dataclasses import replace
            title = next((m["title"] for m in gh.milestones_ if m["number"] == number), None)
            gh.issues[n] = replace(gh.issues[n], milestone=title)

        def milestones():
            gh._r("milestones")
            return [dict(m) for m in gh.milestones_]

        def create_milestone(title):
            gh._w("create milestone", title)
            gh.milestones_.append({"number": 100 + len(gh.milestones_), "title": title, "state": "open"})

        def close_milestone(number):
            gh._w("close milestone", number)
            for m in gh.milestones_:
                if m["number"] == number:
                    m["state"] = "closed"

        def issue_titled(title):
            gh._r("issue_titled")
            return title in gh.titles

        def create_issue(title, body):
            gh._w("create issue", title)
            gh.titles.add(title)
            gh.last_body = body

        def release_exists(tag):
            gh._r("release_exists")
            return tag in gh.releases

        def create_release(tag, start):
            gh._w("release", tag, start)
            gh.releases.add(tag)

        names = dict(issues_in_full=in_full, set_field=set_field, comment_bodies=comment_bodies,
                     add_comment=add_comment, close_issue=close_issue, set_milestone=set_milestone,
                     milestones=milestones, create_milestone=create_milestone,
                     close_milestone=close_milestone, issue_titled=issue_titled,
                     create_issue=create_issue, release_exists=release_exists,
                     create_release=create_release,
                     check_conclusions=lambda sha: gh.checks)
        self.checks = {}
        self.patches = [mock.patch.object(release.sources, k, v) for k, v in names.items()]
        for p in self.patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in self.patches:
            p.stop()


def record(version="0.10.2", wps=(), issues=(), releases=()):
    return {"record": 1, "version": version,
            "carries": {"work_packages": list(wps), "issues": list(issues), "releases": list(releases)}}


def settle(gh, rec, tag=None):
    return release.settle(rec, ANNOUNCEMENT, tag or f"v{rec['version']}")


class SettlingFromTheRecord(Cases):

    def test_a_work_package_is_moved_and_an_issue_is_closed(self):
        """a work package moves to Post-deployment, an issue is closed, each told once"""
        with GitHub([raw(555, "Project", project_state="Development"), raw(12), raw(570, "Project", "2026.11.03-1", project_state="Development")]) as gh:
            out = settle(gh, record(wps=[555], issues=[12]))
            self.expect("settled", (True, []), (out["settled"], out["left"]))
            self.expect("the package is moved, not closed", "Post-deployment", gh.issues[555].fields["Project State"])
            self.expect("and still open", "OPEN", gh.issues[555].state)
            self.expect("the issue is closed", "CLOSED", gh.issues[12].state)
            self.expect("each told in the announcement's words",
                        ["Released in v0.10.2 (deployed to production)"], gh.comments[555])
            self.expect("the milestone closes", "closed", gh.milestones_[0]["state"])
            self.expect("what was not in the record is left alone", "Development", gh.issues[570].fields["Project State"])

    def test_a_rerun_does_nothing(self):
        """every action checks first: a second run changes nothing"""
        with GitHub([raw(555, "Project", project_state="Development"), raw(12)]) as gh:
            settle(gh, record(wps=[555], issues=[12]))
            before = list(gh.log)
            out = settle(gh, record(wps=[555], issues=[12]))
            self.expect("settled again", True, out["settled"])
            self.expect("with no write", before, gh.log)

    def test_an_earlier_deploy_s_plain_announcement_is_accepted(self):
        """a comment an earlier deploy made, with or without its suffix, is not repeated"""
        with GitHub([raw(12), raw(13)], comments={12: ["Released in v0.10.2"], 13: ["Released in v0.10.2 (deployed to production)"]}) as gh:
            settle(gh, record(issues=[12, 13]))
            self.expect("no second comment", {12: ["Released in v0.10.2"], 13: ["Released in v0.10.2 (deployed to production)"]}, gh.comments)

    def test_what_failed_is_left_and_a_rerun_finishes_it(self):
        """a failure is named; the rest is done; a rerun finishes"""
        with GitHub([raw(560), raw(12)]) as gh:
            gh.fail.add(("close", 560))
            out = settle(gh, record(issues=[12, 560]))
            self.expect("named", (False, ["#560 close"]), (out["settled"], out["left"]))
            self.expect("the other is done", "CLOSED", gh.issues[12].state)
            gh.fail.clear()
            out = settle(gh, record(issues=[12, 560]))
            self.expect("the rerun finishes", (True, "CLOSED"), (out["settled"], gh.issues[560].state))
            self.expect("without a second comment", 1, len(gh.comments[560]))

    def test_an_unreadable_board_leaves_everything(self):
        """an issue that cannot be read is left, never taken as settled"""
        with GitHub([raw(12), raw(555, "Project")]) as gh:
            gh.unreadable.add("issues_in_full")
            out = settle(gh, record(wps=[555], issues=[12]))
            self.expect("both left", ["#555", "#12"], out["left"])
            self.expect("and the reason is said once", True, bool(out.get("why")))
            self.expect("nothing written but the milestone", ["close milestone 7"], gh.log)
        with GitHub([raw(12)]) as gh:
            out = settle(gh, record(issues=[12, 13]))
            self.expect("an issue that does not exist is left", ["#13"], out["left"])

    def test_a_state_that_cannot_be_set_skips_the_comment(self):
        """a work package whose state fails is not told it is deployed"""
        with GitHub([raw(555, "Project", project_state="Development")]) as gh:
            gh.fail.add("state")
            out = settle(gh, record(wps=[555]))
            self.expect("left", ["#555 state"], out["left"])
            self.expect("no comment", {}, gh.comments)

    def test_the_worked_example(self):
        """design §12: items of an undeployed release are settled with its words, the dropped one is taken out"""
        earlier = {"version": "0.10.2", "work_packages": [], "issues": [1, 3], "dropped": [2]}
        issues = [raw(1, milestone="0.10.2"), raw(2, milestone="0.10.2"), raw(3, milestone="0.10.2"), raw(4, milestone="0.10.3")]
        with GitHub(issues, milestones=[{"number": 7, "title": "0.10.2", "state": "open"},
                                        {"number": 8, "title": "0.10.3", "state": "open"}]) as gh:
            out = settle(gh, record("0.10.3", issues=[1, 3, 4], releases=[earlier]))
            self.expect("settled", True, out["settled"])
            self.expect("an earlier release's item says which", ["Released in v0.10.2, deployed with v0.10.3"], gh.comments[1])
            self.expect("this release's own item says so", ["Released in v0.10.3 (deployed to production)"], gh.comments[4])
            self.expect("the dropped item says it did not ship", True,
                        gh.comments[2][0].startswith("Released in v0.10.3 without this (not shipped)"))
            self.expect("and leaves its milestone", (None, "OPEN"), (gh.issues[2].milestone, gh.issues[2].state))
            self.expect("both milestones close", ["closed", "closed"], [m["state"] for m in gh.milestones_])
            before = list(gh.log)
            settle(gh, record("0.10.3", issues=[1, 3, 4], releases=[earlier]))
            self.expect("and a rerun writes nothing", before, gh.log)


class TheNextMilestone(Cases):

    def test_it_is_opened_and_the_left_out_move_into_it(self):
        """the next patch's milestone is opened and the left-out issues move"""
        with GitHub([raw(9), raw(30)]) as gh:
            out = release.open_next("0.10.2", [9])
            self.expect("0.10.3 created", ("0.10.3", True, [9], []), (out["milestone"], out["created"], out["moved"], out["failed"]))
            self.expect("the issue is in it", "0.10.3", gh.issues[9].milestone)
            self.expect("the other is untouched", "0.10.2", gh.issues[30].milestone)
            out = release.open_next("0.10.2", [])
            self.expect("a rerun creates nothing", (False, 1), (out["created"], sum("create milestone" in l for l in gh.log)))

    def test_what_fails_is_named(self):
        """a milestone that cannot be opened is named, with the moves it blocked"""
        with GitHub([raw(9)]) as gh:
            gh.fail.add("create milestone")
            out = release.open_next("0.10.2", [9])
            self.expect("named", ["next milestone", "move #9"], out["failed"])
        with GitHub([raw(9), raw(10)]) as gh:
            gh.fail.add(("milestone", 9, 101))
            out = release.open_next("0.10.2", [9, 10])
            self.expect("one move fails and the other is made", (["move #9"], [10]), (out["failed"], out["moved"]))
        self.expect("the next patch", "1.0.1", release.next_patch("1.0.0"))


class ThePublishedRelease(Cases):

    def test_the_release_is_made_with_notes_from_the_previous_tag(self):
        """the Release is created from the previous tag, once"""
        with GitHub() as gh:
            out = release.publish("v0.10.2", "v0.10.1")
            self.expect("created", ("created", []), (out["release"], out["failed"]))
            self.expect("with the previous tag", ["release v0.10.2 v0.10.1"], gh.log)
            out = release.publish("v0.10.2", "v0.10.1")
            self.expect("a second time it exists", ("exists", 1), (out["release"], len(gh.log)))

    def test_the_retrospective_issue_is_raised_once(self):
        """the retrospective issue is raised where rehearsal was skipped, and not twice"""
        with GitHub() as gh:
            out = release.publish("v0.10.2", None, "host down", "0.10.2", "abc123")
            self.expect("raised", "raised", out["retrospective"])
            self.expect("with its reason and commit", True,
                        "host down" in gh.last_body and "abc123" in gh.last_body)
            out = release.publish("v0.10.2", None, "host down", "0.10.2", "abc123")
            self.expect("then it exists", ("exists", 2), (out["retrospective"], sum("create issue" in l for l in gh.log) + 1))
            out = release.publish("v0.10.2")
            self.expect("none asked for, none raised", "not asked", out["retrospective"])

    def test_failures_are_named_and_neither_hides_the_other(self):
        """a failing Release is named; a retrospective that cannot be read is named"""
        with GitHub() as gh:
            gh.fail.add("release")
            out = release.publish("v0.10.2", None, "why", "0.10.2", "abc")
            self.expect("the issue is still raised", ("raised", ["GitHub Release"]), (out["retrospective"], out["failed"]))
        with GitHub() as gh:
            gh.unreadable.add("issue_titled")
            out = release.publish("v0.10.2", None, "why", "0.10.2", "abc")
            self.expect("unread, so not raised and named", (["retrospective issue (cannot read the issues)"], "created"),
                        (out["failed"], out["release"]))
            self.expect("no issue was raised blind", False, any("create issue" in l for l in gh.log))
        with GitHub() as gh:
            gh.unreadable.add("release_exists")
            self.expect("a Release that cannot be looked for is not created blind", (["GitHub Release"], []),
                        (release.publish("v0.10.2")["failed"], gh.log))


class TheChecks(Cases):

    def test_each_required_check_is_read(self):
        """only success passes; a missing run is missing"""
        with GitHub() as gh:
            gh.checks = {"e2e": "success", "lint": "failure", "slow": "pending"}
            ok, got, bad = release.checks("a" * 40, ["e2e"])
            self.expect("green", (True, {"e2e": "success"}, []), (ok, got, bad))
            ok, got, bad = release.checks("a" * 40, ["e2e", "lint", "slow", "absent"])
            self.expect("the others are named",
                        (False, ["check lint is failure on " + "a" * 12, "check slow is pending on " + "a" * 12,
                                 "check absent is missing on " + "a" * 12]), (ok, bad))
            self.expect("none required, none to fail", True, release.checks("a" * 40, [])[0])


if __name__ == "__main__":
    unittest.main()
