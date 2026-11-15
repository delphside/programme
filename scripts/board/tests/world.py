"""A stand-in for GitHub's REST API, for the board flow's tests.

Built from the test design (`records/2.5-changes/process-definition/
176-project-board-flow/test-design.md`, *Approach*), not from the code under
test. It stands in for `subprocess.run` as the `gh` command does, so the real
`sources.py`, `flow.py` and scripts run against it. It:

* holds five repositories with issues, issue fields, timelines, sub-issues,
  dependency links, comments, milestones, pull requests (reviews, commits) and
  merged pull requests;
* refuses every GraphQL call, as a cloud session's proxy does, and counts them;
* logs every write with its target and value, and applies it, so a second run
  sees what the first wrote;
* can be told to fail a read, refuse a write with 403, or hang a call;
* has a fixed *now*, and every timeline event and commit is dated relative to
  it, so boundaries are exact to the minute.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
REAL_RUN = subprocess.run
ORG = "fakeorg"
PROGRAMME = f"{ORG}/programme"
REPOS = (PROGRAMME, f"{ORG}/dark-portal", f"{ORG}/infrastructure",
         f"{ORG}/service-desk", f"{ORG}/tile-lite-elite")

# name -> (id, data type)
FIELDS = {
    "Turn": (49935304, "single_select"),
    "Project State": (46162136, "single_select"),
    "Requirement State": (46185224, "single_select"),
    "Decision State": (46531431, "single_select"),
    "Ticket State": (48733274, "single_select"),
    "Workstream": (46217763, "single_select"),
    "Route": (46415058, "single_select"),
    "Claimed by": (49999001, "text"),
}
BY_ID = {fid: name for name, (fid, _) in FIELDS.items()}


def iso(when: datetime) -> str:
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def ago(**delta) -> str:
    """A time `delta` before the world's now, as GitHub writes it."""
    return iso(NOW - timedelta(**delta))


class World:
    def __init__(self) -> None:
        self.issues: dict[tuple[str, int], dict] = {}
        self.pulls: dict[tuple[str, int], dict] = {}
        self.milestones: dict[str, list[dict]] = {r: [] for r in REPOS}
        self.commits: dict[tuple[str, str], str] = {}
        self.log: list[tuple[str, str, Any]] = []      # (method, path, payload)
        self.graphql_calls = 0
        self.read_paths: list[str] = []
        self.timeouts: list[float | None] = []
        self.fail_reads: dict[str, str] = {}           # path fragment -> stderr
        self.refuse_writes: set[str] = set()           # path fragment
        self.hang: dict[str, float] = {}               # path fragment -> seconds
        self.add_issue(PROGRAMME, 900, "Requirement", title="Board flow: the stalled list",
                       fields={"Requirement State": "Triage"}, since=timedelta(days=60))

    # -- building ---------------------------------------------------------
    def add_issue(self, repo: str, number: int, type: str | None = "Requirement", *,
                  fields: dict[str, str] | None = None, since: timedelta = timedelta(hours=1),
                  created: timedelta | None = None, body: str = "", title: str | None = None,
                  labels: tuple[str, ...] = (), milestone: tuple[str, str] | None = None,
                  sub: tuple[tuple[int, str, str], ...] = (),
                  blocked_by: tuple[tuple[str, int, str], ...] = (),
                  comments: tuple[tuple[str, str, timedelta], ...] = (),
                  parent: int | None = None, hide_fields: bool = False) -> dict:
        """An open issue whose last field event was `since` ago. `sub` are
        (number, type, state); `blocked_by` are (repo, number, state);
        `comments` are (login, text, age)."""
        stamp = NOW - since
        issue = {
            "number": number, "title": title or f"issue {number}", "state": "open",
            "body": body, "type": {"name": type} if type else None,
            "labels": [{"name": n} for n in labels], "milestone": None,
            "created_at": iso(NOW - (created if created is not None else since)),
            "updated_at": iso(stamp), "closed_at": None, "comments": len(comments),
            "repository_url": f"https://api.github.com/repos/{repo}",
            "_fields": dict(fields or {}),
            "_events": [{"event": "issue_field_added", "created_at": iso(stamp)}] if fields else [],
            "_sub": list(sub), "_blocked": list(blocked_by),
            "_comments": [{"user": {"login": u}, "body": t, "created_at": iso(NOW - a)}
                          for u, t, a in comments],
            "_hide": hide_fields,
        }
        if milestone:
            issue["milestone"] = {"title": milestone[0], "state": milestone[1]}
        if parent:
            issue["parent_issue_url"] = f"https://api.github.com/repos/{repo}/issues/{parent}"
        self.issues[(repo, number)] = issue
        return issue

    def add_pull(self, repo: str, number: int, *, draft: bool = False, reviewers: int = 0,
                 review: str | None = None, since: timedelta = timedelta(hours=1),
                 body: str = "", title: str | None = None, head_ref: str | None = None,
                 sha: str | None = None, commit_age: timedelta | None = None) -> dict:
        stamp = NOW - since
        pull = {
            "number": number, "title": title or f"pr {number}", "state": "open", "draft": draft,
            "body": body, "labels": [], "milestone": None, "user": {"type": "User"},
            "created_at": iso(stamp), "updated_at": iso(stamp), "merged_at": None,
            "requested_reviewers": [{"login": f"r{i}"} for i in range(reviewers)],
            "requested_teams": [], "base": {"ref": "main"},
            "head": {"ref": head_ref or f"branch-{number}", "sha": sha or f"sha{number}"},
            "_review": review, "_events": [{"event": "review_requested", "created_at": iso(stamp)}],
        }
        if commit_age is not None:
            self.commits[(repo, pull["head"]["sha"])] = ago(
                seconds=commit_age.total_seconds())
        self.pulls[(repo, number)] = pull
        return pull

    def add_merged(self, repo: str, number: int, *, body: str = "", title: str | None = None,
                   age: timedelta = timedelta(days=1)) -> dict:
        stamp = iso(NOW - age)
        pull = {"number": number, "title": title or f"merged {number}", "state": "closed",
                "body": body, "merged_at": stamp, "updated_at": stamp, "created_at": stamp,
                "base": {"ref": "main"}, "head": {"ref": f"m{number}", "sha": f"m{number}"}}
        self.pulls[(repo, number)] = pull
        return pull

    def add_milestone(self, repo: str, title: str, state: str = "open",
                      closed: timedelta | None = None) -> None:
        self.milestones[repo].append({
            "title": title, "state": state,
            "closed_at": iso(NOW - closed) if closed is not None else None})

    def field(self, repo: str, number: int, name: str) -> str | None:
        return self.issues[(repo, number)]["_fields"].get(name)

    def field_writes(self) -> list[tuple[str, str, Any]]:
        return [w for w in self.log if w[1].endswith("/issue-field-values")]

    def body_writes(self) -> list[tuple[str, str, Any]]:
        return [w for w in self.log if w[0] == "PATCH" and isinstance(w[2], dict)
                and "body" in w[2]]

    def pinned_body(self) -> str:
        return self.issues[(PROGRAMME, 900)]["body"]

    # -- GitHub's side ----------------------------------------------------
    def __call__(self, args, **kw):
        if args[0] != "gh":
            return REAL_RUN(args, **kw)
        if args[1] == "api" and args[2] == "graphql":
            self.graphql_calls += 1
            return self.done(1, err="HTTP 403: Resource not accessible by integration")
        if args[1] != "api":
            return self.done(1, err="unexpected gh command")
        self.timeouts.append(kw.get("timeout"))
        if "-X" in args:
            return self.write(args, kw)
        path = args[2]
        self.read_paths.append(path)
        for fragment, seconds in self.hang.items():
            if fragment in path and seconds > (kw.get("timeout") or 1e9):
                raise subprocess.TimeoutExpired(args, kw.get("timeout"))
        for fragment, err in self.fail_reads.items():
            if fragment in path:
                return self.done(1, err=err)
        return self.done(0, json.dumps(self.read(path)))

    @staticmethod
    def done(code: int, out: str = "", err: str = ""):
        return subprocess.CompletedProcess([], code, out, err)

    def read(self, path: str):
        base, _, query = path.partition("?")
        params = dict(p.split("=", 1) for p in query.split("&") if "=" in p)
        parts = base.split("/")                      # repos, owner, repo, ...
        if parts[0] != "repos":
            return {}
        repo = f"{parts[1]}/{parts[2]}"
        rest = parts[3:]
        if rest == ["issues"]:
            data = [self.render_issue(repo, i) for (r, _), i in sorted(self.issues.items())
                    if r == repo]
            data += [self.render_issue_of_pull(repo, p) for (r, _), p in sorted(self.pulls.items())
                     if r == repo and p["state"] == "open"]
        elif rest == ["pulls"]:
            if params.get("state") == "open":
                data = [self.render_pull(p) for (r, _), p in sorted(self.pulls.items())
                        if r == repo and p["state"] == "open"]
            else:
                data = sorted((p for (r, _), p in self.pulls.items()
                               if r == repo and p["state"] != "open"),
                              key=lambda p: p["updated_at"], reverse=True)
        elif rest == ["milestones"]:
            data = self.milestones[repo]
        elif rest[:1] == ["commits"]:
            when = self.commits.get((repo, rest[1]))
            return {"commit": {"committer": {"date": when}}} if when else {}
        elif rest[:1] == ["issues"] and len(rest) == 3:
            number, what = int(rest[1]), rest[2]
            issue = self.issues.get((repo, number))
            pull = self.pulls.get((repo, number))
            if what == "sub_issues":
                data = [{"number": n, "type": {"name": t}, "state": s}
                        for n, t, s in issue["_sub"]]
            elif what == "comments":
                data = (issue or {"_comments": []})["_comments"]
            elif what == "timeline":
                data = (issue or pull)["_events"]
            else:
                data = []
        elif len(rest) == 4 and rest[0] == "issues" and rest[2] == "dependencies":
            issue = self.issues[(repo, int(rest[1]))]
            data = [{"number": n, "state": s,
                     "repository_url": f"https://api.github.com/repos/{r}"}
                    for r, n, s in issue["_blocked"]]
        elif len(rest) == 3 and rest[0] == "pulls" and rest[2] == "reviews":
            pull = self.pulls[(repo, int(rest[1]))]
            data = [{"state": pull["_review"], "user": {"login": "rev"}}] if pull.get("_review") else []
        else:
            data = []
        if "per_page" in params:
            size, page = int(params["per_page"]), int(params.get("page", 1))
            return data[(page - 1) * size: page * size]
        return data

    def render_issue(self, repo: str, i: dict) -> dict:
        out = {k: v for k, v in i.items() if not k.startswith("_")}
        if not i["_hide"]:
            out["issue_field_values"] = [
                ({"issue_field_id": FIELDS[n][0], "issue_field_name": n,
                  "data_type": FIELDS[n][1], "value": v,
                  **({"single_select_option": {"name": v}} if FIELDS[n][1] == "single_select" else {})})
                for n, v in i["_fields"].items()]
        out["sub_issues_summary"] = {"total": len(i["_sub"])}
        out["issue_dependencies_summary"] = {"total_blocked_by": len(i["_blocked"])}
        return out

    @staticmethod
    def render_issue_of_pull(repo: str, p: dict) -> dict:
        return {"number": p["number"], "pull_request": {}, "state": "open"}

    @staticmethod
    def render_pull(p: dict) -> dict:
        return {k: v for k, v in p.items() if not k.startswith("_")}

    def write(self, args, kw):
        method, path = args[args.index("-X") + 1], args[args.index("-X") + 2]
        for fragment in self.refuse_writes:
            if fragment in path:
                return self.done(1, err="HTTP 403")
        payload: Any = None
        if "--input" in args:
            payload = json.loads(kw.get("input") or "{}")
        else:
            payload = {}
            rest = args[args.index("-X") + 3:]
            for i in range(0, len(rest), 2):
                key, _, value = rest[i + 1].partition("=")
                payload[key] = value
        self.log.append((method, path, payload))
        parts = path.split("/")
        repo, rest = f"{parts[1]}/{parts[2]}", parts[3:]
        issue = self.issues.get((repo, int(rest[1]))) if rest[:1] == ["issues"] else None
        if issue is None:
            return self.done(1, err="HTTP 404")
        if rest[2:] == ["issue-field-values"]:
            for entry in payload["issue_field_values"]:
                name = BY_ID[entry["field_id"]]
                had = name in issue["_fields"]
                issue["_fields"][name] = entry["value"]
                issue["_events"].append({
                    "event": "issue_field_changed" if had else "issue_field_added",
                    "created_at": iso(NOW)})
        elif rest[2:3] == ["issue-field-values"]:
            name = BY_ID[int(rest[3])]
            issue["_fields"].pop(name, None)
            issue["_events"].append({"event": "issue_field_removed", "created_at": iso(NOW)})
        elif len(rest) == 2:
            if "type" in payload:
                issue["type"] = {"name": payload["type"]}
            if "body" in payload:
                issue["body"] = payload["body"]
        return self.done(0, "{}")
