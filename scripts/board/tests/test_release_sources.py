"""The calls a release makes to GitHub, and how they fail.

From the rules (design §11): the board model is deliver's GitHub adapter, reading
over GraphQL where the token allows it and REST where it is refused, and **a read
that no route answers refuses, never reads as empty**. No network: `subprocess.run`
is replaced, so `gh` is never started.

  absent      a 404 is "not there" and nothing else is: any other failure raises
  fallback    a GraphQL refusal falls back to REST, which answers or raises; a
              number that is a pull request or does not exist is absent from both
  writes      the calls the old shell made, in the same words
  lists       milestones and issues are read whole, every page"""

import json
import os
import re
import subprocess
import unittest
from unittest import mock

from board import sources
from board.sources import Refused, Unavailable

from .cases import Cases

REPO = "fakeorg/widget"
REAL_RUN = subprocess.run


def done(code=0, out="", err=""):
    return subprocess.CompletedProcess([], code, out, err)


class Gh:
    """`gh`, answering REST paths from a table: a value is the JSON, an int is a
    failure with that HTTP status. GraphQL is refused unless a function is given."""

    def __init__(self, rest=None, graphql=None):
        self.rest = rest or {}
        self.graphql = graphql
        self.calls = []

    def __call__(self, args, **kw):
        if args[0] != "gh":
            return REAL_RUN(args, **kw)  # git, asked by the profile loader
        self.calls.append(args)
        if args[1] == "release":
            return done(*self.rest.get("release", (0,)))
        if "-X" in args:
            return done(0, "{}")
        path = [a for a in args[2:] if not a.startswith("-") and a not in ("GET", "POST", "PATCH")][0] \
            if args[2] != "graphql" else "graphql"
        if path == "graphql":
            if self.graphql is None:
                return done(1, err="HTTP 403: Resource not accessible by integration")
            return done(0, json.dumps(self.graphql(next(a for a in args if a.startswith("query=")))))
        key = path if path in self.rest else re.sub(r"[?&]per_page=\d+(&page=\d+)?$", "", path)
        answer = self.rest.get(key)
        if answer is None:
            return done(1, err="gh: Not Found (HTTP 404)")
        if isinstance(answer, int):
            return done(1, err=f"gh: HTTP {answer}")
        if re.search(r"&page=([2-9]|\d\d)$", path):
            return done(0, "[]")
        return done(0, json.dumps(answer))

    def writes(self):
        return [" ".join(c[2:]) for c in self.calls if "-X" in c]


def patched(gh):
    return mock.patch.object(sources.subprocess, "run", gh)


class Cases(Cases):
    """Reads and writes go to the fake application's repository."""

    def setUp(self):
        env = mock.patch.dict(os.environ, {"BOARD_REPOSITORY": REPO})
        env.start()
        self.addCleanup(env.stop)


def rest_issue(n, **kw):
    node = {"number": n, "title": f"issue {n}", "state": "open", "body": "", "type": {"name": "Requirement"},
            "milestone": None, "labels": [], "sub_issues_summary": {"total": 0},
            "issue_dependencies_summary": {}}
    node.update(kw)
    return node


class AbsentIsNotUnreadable(Cases):

    def test_only_a_404_is_absence(self):
        """a 404 is absence; a 500 and a dead gh are not"""
        path = f"repos/{REPO}/releases/tags/v1"
        with patched(Gh()):
            self.expect("not found", False, sources.release_exists("v1"))
        with patched(Gh({path: {"id": 1}})):
            self.expect("found", True, sources.release_exists("v1"))
        with patched(Gh({path: 500})):
            with self.assertRaises(Unavailable):
                sources.release_exists("v1")
        with mock.patch.object(sources.subprocess, "run", side_effect=OSError("no gh")):
            with self.assertRaises(Unavailable):
                sources.release_exists("v1")

    def test_a_commit_with_no_checks_endpoint_is_unreadable(self):
        """checks on a commit GitHub does not know raise"""
        with patched(Gh()):
            with self.assertRaises(Unavailable):
                sources.check_conclusions("abc")
        with patched(Gh({f"repos/{REPO}/commits/abc/check-runs?per_page=100": {"check_runs": [
                {"name": "e2e", "conclusion": "success"}, {"name": "e2e", "conclusion": "failure"},
                {"name": "lint", "conclusion": None}]}})):
            self.expect("the first run of a name; one not concluded is pending",
                        {"e2e": "success", "lint": "pending"}, sources.check_conclusions("abc"))


class IssuesInFull(Cases):

    def test_graphql_refused_falls_back_to_rest(self):
        """a refusal reads over REST, and a pull request or a missing number is absent"""
        base = f"repos/{REPO}/issues"
        gh = Gh({f"{base}/5": rest_issue(5, state="closed", milestone={"title": "0.10.2"},
                                         issue_field_values=[{"issue_field_name": "Route",
                                                              "single_select_option": {"name": "Production Release"}}]),
                 f"{base}/6": rest_issue(6, pull_request={})})
        with patched(gh):
            got = sources.issues_in_full([5, 6, 7])
        self.expect("only the issue", [5], list(got))
        self.expect("with its state, milestone and field", ("CLOSED", "0.10.2", "Production Release"),
                    (got[5].state, got[5].milestone, got[5].fields["Route"]))

    def test_rest_that_also_fails_raises(self):
        """REST that fails is not an empty answer"""
        with patched(Gh({f"repos/{REPO}/issues/5": 500})):
            with self.assertRaises(Unavailable):
                sources.issues_in_full([5])

    def test_graphql_that_answers_is_used(self):
        """where GraphQL answers, REST is not asked"""
        def answer(query):
            return {"data": {"repository": {"i5": {"number": 5, "title": "five", "state": "OPEN",
                                                    "issueType": {"name": "Project"}, "milestone": {"title": "0.10.2"}}}}}
        gh = Gh(graphql=answer)
        with patched(gh):
            got = sources.issues_in_full([5])
        self.expect("read", ("Project", "0.10.2"), (got[5].issue_type, got[5].milestone))
        self.expect("one call, GraphQL", 1, len(gh.calls))


    def _partial(self, errors):
        """gh as it answers a partly failed GraphQL read: exit 1, the payload on stdout"""
        node = {"number": 5, "title": "five", "state": "OPEN", "issueType": {"name": "Project"},
                "milestone": {"title": "0.10.2"}}
        payload = {"data": {"repository": {"i5": node, "i9": None}}, "errors": errors}

        def run(args, **kw):
            if args[0] != "gh":
                return REAL_RUN(args, **kw)
            return done(1, json.dumps(payload), "gh: partial")
        return mock.patch.object(sources.subprocess, "run", side_effect=run)

    def test_a_number_that_is_not_found_is_absent_beside_the_rest(self):
        """NOT_FOUND on one alias leaves it absent; the others are read"""
        with patched(Gh()), self._partial([{"type": "NOT_FOUND", "path": ["repository", "i9"],
                                           "message": "Could not resolve"}]):
            got = sources.issues_in_full([5, 9])
        self.expect("5 read, 9 absent", [5], list(got))

    def test_any_other_error_on_an_alias_refuses(self):
        """a rate limit or a timeout on an alias is an issue that could not be read, not one that is absent"""
        for kind in ("RATE_LIMITED", "SERVICE_UNAVAILABLE", None):
            err = {"path": ["repository", "i9"], "message": "boom"}
            if kind:
                err["type"] = kind
            with patched(Gh()), self._partial([err]):
                with self.assertRaises(Unavailable):
                    sources.issues_in_full([5, 9])


class TheWrites(Cases):

    def test_the_words_the_shell_used(self):
        """each write is the call the shell made"""
        gh = Gh()
        with patched(gh):
            sources.create_milestone("0.10.3")
            sources.close_milestone(7)
            sources.set_milestone(9, 100)
            sources.set_milestone(2, None)
            sources.add_comment(12, "Released in v0.10.2")
            sources.close_issue(12)
            sources.create_issue("Retrospective: 0.10.2 released with rehearsal skipped", "why")
        self.expect("as the stub logs them", [
            f"-X POST repos/{REPO}/milestones -f title=0.10.3",
            f"-X PATCH repos/{REPO}/milestones/7 -f state=closed",
            f"-X PATCH repos/{REPO}/issues/9 -F milestone=100",
            f"-X PATCH repos/{REPO}/issues/2 -F milestone=null",
            f"-X POST repos/{REPO}/issues/12/comments -f body=Released in v0.10.2",
            f"-X PATCH repos/{REPO}/issues/12 -f state=closed -f state_reason=completed",
            f"-X POST repos/{REPO}/issues -f title=Retrospective: 0.10.2 released with rehearsal skipped -f body=why",
        ], gh.writes())

    def test_a_refused_write_raises(self):
        """a write GitHub refuses is Unavailable, which the caller names"""
        gh = Gh()
        gh.__class__ = type("Failing", (Gh,), {"__call__": lambda self, args, **kw: done(1, err="HTTP 422")})
        with patched(gh):
            with self.assertRaises(Unavailable):
                sources.close_issue(1)

    def test_the_release_is_made_from_the_previous_tag(self):
        """the Release verifies the tag and generates notes from the previous one"""
        gh = Gh()
        with patched(gh):
            sources.create_release("v0.10.2", "v0.10.1")
            sources.create_release("v0.10.2", None)
        self.expect("with the start tag", ["gh", "release", "create", "v0.10.2", "--repo", REPO, "--verify-tag",
                                           "--title", "v0.10.2", "--generate-notes", "--notes-start-tag", "v0.10.1"],
                    gh.calls[0])
        self.expect("and without it", False, "--notes-start-tag" in gh.calls[1])
        with patched(Gh({"release": (1, "", "HTTP 422")})):
            with self.assertRaises(Unavailable):
                sources.create_release("v0.10.2", None)


class TheLists(Cases):

    def test_an_issue_with_the_title_is_found_on_any_page_and_a_pull_request_is_not_one(self):
        """the retrospective issue is looked for on every page, and a pull request with the title is not it"""
        title = "Retrospective: 0.10.2 released with rehearsal skipped"
        page1 = [{"number": i, "title": f"filler {i}"} for i in range(100)]
        gh = Gh({f"repos/{REPO}/issues?state=all": page1})
        calls = []

        def second_page(args, **kw):
            calls.append(args[2])
            if args[2].endswith("page=2"):
                return done(0, json.dumps([{"number": 500, "title": title}]))
            return gh(args, **kw)
        with mock.patch.object(sources.subprocess, "run", second_page):
            self.expect("found on page 2", True, sources.issue_titled(title))
        with patched(Gh({f"repos/{REPO}/issues?state=all": [{"number": 1, "title": title, "pull_request": {}}]})):
            self.expect("a pull request is not an issue", False, sources.issue_titled(title))
        with patched(Gh({f"repos/{REPO}/issues?state=all": 500})):
            with self.assertRaises(Unavailable):
                sources.issue_titled(title)

    def test_milestones_and_comments(self):
        """milestones of any state; a comment's whole text"""
        long = "x" * 400
        with patched(Gh({f"repos/{REPO}/milestones?state=all": [{"number": 7, "title": "0.10.2", "state": "open"}],
                         f"repos/{REPO}/issues/12/comments": [{"body": long}, {"body": None}]})):
            self.expect("milestones", ["0.10.2"], [m["title"] for m in sources.milestones()])
            self.expect("the comment is not cut", [long, ""], sources.comment_bodies(12))


if __name__ == "__main__":
    unittest.main()
