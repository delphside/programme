"""Reading GitHub over REST where GraphQL and search are refused, and the
digest's waiting list across repositories.

A cloud session's token is refused GraphQL and `search/issues` while REST
answers (the W44 digest, 2026-10-26). From the rules, not the code:

  fallback    only a refusal falls back; a read that could not be made, or one
              REST also refuses, is `Unavailable`, never an empty answer
  same shape  the snapshot over REST equals the one GraphQL gives for the same
              data, so no consumer can tell which route it came by
  waiting     the owner's review is wanted in the programme's pull requests too,
              named by repository; one that could not be read is said

No network: `subprocess.run` is stubbed, so `gh` is never started."""

import json
import subprocess
import unittest
from unittest import mock

from board import digest, sources
from board.digest import Digest, build, render
from board.model import PR_STATE, RawIssue, RawSubIssue
from board.sources import Refused, Unavailable

from .cases import Cases

REAL_RUN = subprocess.run
OWNER_REPO = "fakeorg/widget"


class Gh:
    """A stand-in for `subprocess.run`: answers each `gh api` call from a table
    of REST paths, and GraphQL from a function or a refusal. Records the calls."""

    def __init__(self, rest=None, graphql=None, search=None, refuse_rest=()):
        self.rest = rest or {}
        self.graphql = graphql          # callable(query) -> payload, or None: refused
        self.search = search            # stdout, or None: refused
        self.refuse_rest = refuse_rest
        self.calls = []

    def __call__(self, args, **kw):
        if args[0] != "gh":                 # git, asked by the profile loader
            return REAL_RUN(args, **kw)
        self.calls.append(args)
        if "search/issues" in args:
            return self.done(0, self.search) if self.search is not None else self.done(1, err="HTTP 403")
        path = args[2]
        if path == "graphql":
            query = next(a for a in args if a.startswith("query="))
            if self.graphql is None:
                return self.done(1, err="HTTP 403: Resource not accessible by integration")
            return self.done(0, json.dumps(self.graphql(query)))
        if any(path.split("?")[0].endswith(r) for r in self.refuse_rest):
            return self.done(1, err="HTTP 403")
        page = int(path.rsplit("page=", 1)[1])
        key = path.split("&per_page=")[0] if "&per_page=" in path else path.split("?per_page=")[0]
        data = self.rest.get(key, [])
        return self.done(0, json.dumps(data if page == 1 else []))

    @staticmethod
    def done(code, out="", err=""):
        return subprocess.CompletedProcess([], code, out, err)

    def rest_calls(self):
        return [c[2] for c in self.calls if "search/issues" not in c and c[2] != "graphql"]


def graphql_issue(n, **kw):
    node = {"number": n, "title": f"issue {n}", "state": "OPEN", "createdAt": "2026-10-01T00:00:00Z",
            "updatedAt": "2026-10-02T00:00:00Z", "closedAt": None, "body": f"body {n}",
            "issueType": {"name": "Requirement"}, "milestone": None, "parent": None,
            "labels": {"nodes": []}, "subIssues": {"nodes": []}, "blockedBy": {"nodes": []},
            "blocking": {"nodes": []}, "issueFieldValues": {"nodes": []}}
    node.update(kw)
    return node


def rest_issue(n, **kw):
    node = {"number": n, "title": f"issue {n}", "state": "open", "created_at": "2026-10-01T00:00:00Z",
            "updated_at": "2026-10-02T00:00:00Z", "closed_at": None, "body": f"body {n}",
            "type": {"name": "Requirement"}, "milestone": None, "labels": [],
            "sub_issues_summary": {"total": 0}, "issue_dependencies_summary": {}}
    node.update(kw)
    return node


# The same board, in each route's words: a project with a sub-issue, a parent,
# a field, a milestone, a label and a dependency each way; and a plain requirement.
G_PROJECT = graphql_issue(
    10, issueType={"name": "Project"}, milestone={"title": "0.9.0"}, parent={"number": 3},
    labels={"nodes": [{"name": "tooling"}]},
    subIssues={"nodes": [{"number": 11, "issueType": {"name": "Project"}}]},
    blockedBy={"nodes": [{"number": 7}]}, blocking={"nodes": [{"number": 12}]},
    issueFieldValues={"nodes": [{"value": "Development", "field": {"name": "Project State"}}]})
R_PROJECT = rest_issue(
    10, type={"name": "Project"}, milestone={"title": "0.9.0"},
    parent_issue_url=f"https://api.github.com/repos/{OWNER_REPO}/issues/3",
    labels=[{"name": "tooling"}], sub_issues_summary={"total": 1},
    issue_dependencies_summary={"total_blocked_by": 1, "total_blocking": 1},
    issue_field_values=[{"issue_field_name": "Project State",
                         "single_select_option": {"name": "Development"}}])
REST_BASE = f"repos/{OWNER_REPO}"


def open_pr(n, draft=False, reviewers=(), **kw):
    node = {"number": n, "title": f"pr {n}", "state": "open", "body": "", "draft": draft,
            "created_at": "2026-10-20T00:00:00Z", "updated_at": "2026-10-21T00:00:00Z",
            "closed_at": None, "merged_at": None, "milestone": None, "labels": [],
            "head": {"ref": f"branch-{n}"}, "requested_reviewers": [{"login": r} for r in reviewers],
            "requested_teams": [], "user": {"type": "User"}}
    node.update(kw)
    return node


def graphql_for(issues, prs):
    def answer(query):
        if "pullRequests(" in query:
            return {"data": {"repository": {"pullRequests": {
                "pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": prs}}}}
        return {"data": {"repository": {"issues": {
            "pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": issues}}}}
    return answer


G_PR = {"number": 20, "title": "pr 20", "state": "OPEN", "body": "", "createdAt": "2026-10-20T00:00:00Z",
        "updatedAt": "2026-10-21T00:00:00Z", "headRefName": "branch-20", "isDraft": False,
        "reviewDecision": "APPROVED", "reviewRequests": {"totalCount": 0}, "milestone": None,
        "labels": {"nodes": []}}


def rest_table():
    return {
        f"{REST_BASE}/issues?state=open": [R_PROJECT, rest_issue(12),
                                           rest_issue(13, pull_request={"url": "x"})],
        f"{REST_BASE}/issues/10/sub_issues": [{"number": 11, "type": {"name": "Project"}}],
        f"{REST_BASE}/issues/10/dependencies/blocked_by": [{"number": 7}],
        f"{REST_BASE}/issues/10/dependencies/blocking": [{"number": 12}],
        f"{REST_BASE}/pulls?state=open": [open_pr(20, reviewers=["owner"])],
        f"{REST_BASE}/pulls/20/reviews": [
            {"state": "COMMENTED", "user": {"login": "owner"}},
            {"state": "APPROVED", "user": {"login": "owner"}}],
    }


class TheRestFallback(Cases):
    def fetch(self, gh, **kw):
        with mock.patch.object(sources.subprocess, "run", gh):
            return sources.fetch(**kw)

    def test_a_refused_graphql_gives_the_same_snapshot_over_rest(self):
        graphql = Gh(graphql=graphql_for([G_PROJECT, graphql_issue(12)], [G_PR]))
        rest = Gh(rest=rest_table())
        want = self.fetch(graphql).issues
        got = self.fetch(rest).issues
        self.expect("the same issues and pull requests, field for field", want, got)
        self.expect("with the sub-issue, parent and dependencies", True,
                    got[0].sub_issues == (RawSubIssue(11, "Project"),) and got[0].parent == 3
                    and got[0].blocked_by == {7} and got[0].blocks == {12})
        self.expect("and the pull request's state from the ladder", "Approved",
                    got[-1].fields[PR_STATE])
        self.expect("a pull request in the issues list is not an issue", [10, 12, 20],
                    [i.number for i in got])

    def test_a_pull_requests_state_is_the_ladders_over_rest(self):
        table = rest_table()
        table[f"{REST_BASE}/pulls?state=open"] = [
            open_pr(21, draft=True), open_pr(22, reviewers=["o"]), open_pr(23),
            open_pr(24, reviewers=["o"]), open_pr(25, reviewers=["o"])]
        table[f"{REST_BASE}/pulls/24/reviews"] = [
            {"state": "APPROVED", "user": {"login": "a"}},
            {"state": "CHANGES_REQUESTED", "user": {"login": "b"}},
            {"state": "APPROVED", "user": {"login": "b"}},
            {"state": "CHANGES_REQUESTED", "user": {"login": "b"}}]
        table[f"{REST_BASE}/pulls/25/reviews"] = [
            {"state": "APPROVED", "user": {"login": "a"}},
            {"state": "DISMISSED", "user": {"login": "a"}},
            {"state": "COMMENTED", "user": {"login": "c"}}]
        got = {i.number: i.fields[PR_STATE] for i in self.fetch(Gh(rest=table)).issues
               if i.issue_type == "PullRequest"}
        self.expect("draft", "Drafting", got[21])
        self.expect("a review requested", "Awaiting review", got[22])
        self.expect("none requested", "Drafting", got[23])
        self.expect("the latest review of each reviewer, a change requested wins",
                    "Changes requested", got[24])
        self.expect("a dismissed approval and a comment are no decision",
                    "Awaiting review", got[25])

    def test_graphql_that_answers_is_not_replaced(self):
        gh = Gh(graphql=graphql_for([graphql_issue(12)], []), rest=rest_table())
        self.fetch(gh, with_pull_requests=False)
        self.expect("REST was not asked", [], gh.rest_calls())

    def test_bodies_not_asked_for_are_not_returned_over_rest(self):
        got = self.fetch(Gh(rest=rest_table()), with_bodies=False, with_pull_requests=False)
        self.expect("no body", {""}, {i.body for i in got.issues})

    def test_rest_refused_too_is_unavailable_never_an_empty_snapshot(self):
        with self.assertRaises(Unavailable):
            self.fetch(Gh(refuse_rest=("issues",)))

    def test_a_dependency_list_rest_refuses_is_unavailable(self):
        with self.assertRaises(Unavailable):
            self.fetch(Gh(rest=rest_table(), refuse_rest=("blocked_by",)))

    def test_a_gh_that_cannot_run_does_not_fall_back(self):
        def no_gh(args, **kw):
            if args[0] != "gh":
                return REAL_RUN(args, **kw)
            raise OSError("gh not found")
        with mock.patch.object(sources.subprocess, "run", no_gh):
            with self.assertRaises(Unavailable) as caught:
                sources.fetch()
        self.expect("it is not a refusal", False, isinstance(caught.exception, Refused))

    def test_closed_issues_are_read_as_closed(self):
        table = {f"{REST_BASE}/issues?state=closed": [rest_issue(5, state="closed",
                                                                 closed_at="2026-10-03T00:00:00Z")]}
        got = self.fetch(Gh(rest=table), states="CLOSED", with_pull_requests=False).issues
        self.expect("state and date", ("CLOSED", "2026-10-03T00:00:00Z"),
                    (got[0].state, got[0].closed_at))


def merged(n, merged_at, updated, bot=False, title="t"):
    return {"number": n, "title": title, "body": f"body {n}", "merged_at": merged_at,
            "updated_at": updated, "user": {"type": "Bot" if bot else "User"}}


class TheMergedList(Cases):
    def test_a_refused_search_lists_the_merged_pull_requests_over_rest(self):
        table = {
            "repos/fakeorg/widget/pulls?state=closed&sort=updated&direction=desc": [
                merged(9, "2026-10-21T10:00:00Z", "2026-10-21T10:00:00Z"),
                merged(8, None, "2026-10-20T10:00:00Z"),                       # closed unmerged
                merged(7, "2026-10-19T10:00:00Z", "2026-10-19T10:00:00Z", bot=True),
                merged(6, "2026-10-01T10:00:00Z", "2026-10-01T10:00:00Z")],    # before the window
            "repos/fakeorg/fake-programme/pulls?state=closed&sort=updated&direction=desc": [
                merged(105, "2026-10-26T10:00:00Z", "2026-10-26T10:00:00Z")]}
        gh = Gh(rest=table)
        with mock.patch.object(sources.subprocess, "run", gh):
            got = sources.merged_pull_requests("2026-10-19")
        self.expect("merged in the window, both repositories, in order",
                    [("fakeorg/fake-programme", 105, False), ("fakeorg/widget", 7, True),
                     ("fakeorg/widget", 9, False)],
                    [(p.repository, p.number, p.bot) for p in got])
        self.expect("the body is kept", "body 9", got[2].body)

    def test_the_listing_stops_at_the_window(self):
        old = [merged(i, "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z") for i in range(100)]
        table = {"repos/fakeorg/widget/pulls?state=closed&sort=updated&direction=desc":
                 [merged(9, "2026-10-21T10:00:00Z", "2026-10-21T10:00:00Z")] + old}
        gh = Gh(rest=table)
        with mock.patch.object(sources.subprocess, "run", gh):
            sources.merged_pull_requests("2026-10-19")
        self.expect("no page past the first old one was asked for",
                    1, len([c for c in gh.rest_calls() if "fakeorg/widget" in c]))

    def test_a_search_that_answers_is_used(self):
        line = json.dumps(["https://api.github.com/repos/fakeorg/widget", 4, "t", "b", False])
        gh = Gh(search=line)
        with mock.patch.object(sources.subprocess, "run", gh):
            got = sources.merged_pull_requests("2026-10-19")
        self.expect("one, and no REST", ([("fakeorg/widget", 4)], []),
                    ([(p.repository, p.number) for p in got], gh.rest_calls()))

    def test_search_and_rest_both_refused_is_unavailable(self):
        with mock.patch.object(sources.subprocess, "run", Gh(refuse_rest=("pulls",))):
            with self.assertRaises(Unavailable):
                sources.merged_pull_requests("2026-10-19")


def waiting_pr(n, step_state):
    return RawIssue(n, f"pr {n}", "OPEN", "", "PullRequest", {PR_STATE: step_state}, (), None,
                    None, frozenset())


class TheWaitingList(Cases):
    def build(self, **kw):
        with mock.patch.object(digest.repo, "_git", return_value=""):
            return build(sources.Snapshot((), 0, 0, 0, True), None, since="2026-10-19", **kw)

    def test_the_programmes_pull_requests_awaiting_review_are_waiting_on_the_owner(self):
        d = self.build(other_prs={"delphside/programme": [waiting_pr(68, "Awaiting review"),
                                                          waiting_pr(86, "Awaiting review"),
                                                          waiting_pr(90, "Approved"),
                                                          waiting_pr(91, "Drafting")]})
        self.expect("two, each naming its repository",
                    ["delphside/programme#68", "delphside/programme#86"],
                    [w[0] for w in d.waiting])
        text = render(d)
        self.expect("counted", True, "**2** things GitHub reports as waiting on you" in text)
        self.expect("and listed by repository", True,
                    "- delphside/programme#68 pr 68: review: approve or request changes" in text)

    def test_a_repository_that_could_not_be_read_is_said_not_read_as_none(self):
        d = self.build(other_prs={}, unread=["delphside/programme"])
        text = render(d)
        self.expect("it still says nothing was found", True, "**Nothing** GitHub reports" in text)
        self.expect("and that it did not look in the programme", True,
                    "Not read, so not counted:* open pull requests in delphside/programme" in text)

    def test_the_applications_own_stay_numbered_by_issue(self):
        snapshot = sources.Snapshot((waiting_pr(5, "Awaiting review"),), 0, 0, 0, True)
        with mock.patch.object(digest.repo, "_git", return_value=""):
            d = build(snapshot, None, since="2026-10-19")
        self.expect("#5, as before", [5], [w[0] for w in d.waiting])
        self.expect("rendered as before", True, "- #5 pr 5:" in render(d))

    def test_the_repositories_are_the_programme_files(self):
        from board import profile
        self.expect("the programme's first, then the organisation's, once each",
                    ("fakeorg/fake-programme", "fakeorg/programme", "fakeorg/service-desk"),
                    profile.watched_repositories())


class TheOpenPullRequestsOfAnotherRepository(Cases):
    def test_graphql_that_is_refused_is_read_over_rest(self):
        table = {"repos/fakeorg/fake-programme/pulls?state=open": [open_pr(68, reviewers=["o"])],
                 "repos/fakeorg/fake-programme/pulls/68/reviews": []}
        with mock.patch.object(sources.subprocess, "run", Gh(rest=table)):
            got = sources.open_pull_requests("fakeorg/fake-programme")
        self.expect("with its state", [(68, "Awaiting review")],
                    [(i.number, i.fields[PR_STATE]) for i in got])

    def test_unread_is_unavailable(self):
        with mock.patch.object(sources.subprocess, "run", Gh(refuse_rest=("pulls",))):
            with self.assertRaises(Unavailable):
                sources.open_pull_requests("fakeorg/fake-programme")


if __name__ == "__main__":
    unittest.main()
