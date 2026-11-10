"""What a milestone still owes before it ships.

Moved from `verify.sh`'s `check_approach`. It asked GitHub for the milestone's
open projects, then for each one's body, then for its sub-issues to tell a
parent from a package -- three questions the model answers from one snapshot.

**A release question, not a per-issue one.** `board-check.py`'s obligations ask
whether *this* delivery owes a test approach at *its* step. This asks whether
the tests the projects in *this release* said they would run have been run, which
is the question a person has before deploying and is scoped by milestone.

**A parent owes nothing here.** Its packages own the test approach -- D51 -- so
naming it would be a finding nobody can clear.

**It is also the release's board half** (delphside/programme#117): the gates
`turpin release` takes from the board, what the release carries, what settling
it does, and the GitHub steps after the tag. `scripts/board/board-release.py` is
the command over them. The rules are the board model's (`milestone.py`'s, `repo.py`'s)
and `turpin` keeps none.

Design: programme/records/2.5-changes/programme-tooling/383-one-board-model/ and
programme/records/2.5-changes/programme-tooling/117-generic-deliver-tool/
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Sequence

from . import profile, repo, sources
from .milestone import carried, unbuilt
from .model import (PROJECT_STATE, RELEASE, Issue, ParentProject, PullRequest,
                    StandaloneProject, WorkPackage, classify, route_of)
from .sources import Unavailable

DELIVERING = (StandaloneProject, WorkPackage)

# Both halves, as the documents name them. `verify.sh` matched on the substring
# so a project writing either the long or the short form was read either way,
# and that latitude is kept: the skill says to write "None." rather than remove
# a heading, and both spellings are in use.
PREVIEW = "Functional user tests"
REHEARSAL = "Technical tests"


@dataclass(frozen=True)
class Outstanding:
    number: int
    title: str
    preview: int
    rehearsal: int
    missing_headings: bool


def outstanding(issues: Sequence[Issue], milestone: str) -> tuple[Outstanding, ...]:
    """Projects in `milestone` with tests they said they would run, unrun.

    A parent is skipped rather than reported. A project with neither heading is
    reported with `missing_headings`, because a delivery that never said what it
    would test is a different fault from one that said and has not.
    """
    out = []
    for issue in issues:
        # Type before milestone: a Decision carries no milestone attribute at
        # all, so asking it first is an AttributeError rather than a mismatch.
        if isinstance(issue, ParentProject):
            continue
        if not isinstance(issue, DELIVERING):
            continue
        if issue.milestone != milestone:
            continue
        preview_un = issue.unticked_in(PREVIEW)
        rehearsal_un = issue.unticked_in(REHEARSAL)
        has_either = issue.has_heading(PREVIEW) or issue.has_heading(REHEARSAL)
        if not has_either:
            out.append(Outstanding(issue.number, issue.title, 0, 0, True))
        elif preview_un or rehearsal_un:
            out.append(Outstanding(issue.number, issue.title,
                                   preview_un, rehearsal_un, False))
    return tuple(out)


def render(found: Sequence[Outstanding], milestone: str,
           colour: bool = True) -> str:
    bold = (lambda s: f"\033[1m{s}\033[0m") if colour else (lambda s: s)
    dim = (lambda s: f"\033[2m{s}\033[0m") if colour else (lambda s: s)
    red = (lambda s: f"\033[31m{s}\033[0m") if colour else (lambda s: s)
    green = (lambda s: f"\033[32m{s}\033[0m") if colour else (lambda s: s)

    out = [f"{bold('TESTS PROMISED')}  {dim(f'milestone {milestone}')}"]
    if not found:
        out.append(f"  {green('ok')} {dim('nothing outstanding')}")
        return "\n".join(out)
    for o in found:
        if o.missing_headings:
            out.append(f"  {red('!!')} {bold(f'#{o.number}')} {o.title[:46]}  "
                       f"{dim('no test approach headings')}")
        else:
            out.append(f"  {red('!!')} {bold(f'#{o.number}')} {o.title[:46]}  "
                       f"{dim(f'{o.preview} on Preview, {o.rehearsal} on Rehearsal')}")
    return "\n".join(out)


# --------------------------------------------------------------------------
# the gates (`board-release.py gate`)
# --------------------------------------------------------------------------

POST_DEPLOYMENT = "Post-deployment"


def compact(value) -> str:
    """JSON the way `jq -c` writes it, for the messages the gates always had."""
    return json.dumps(value, separators=(",", ":"))


def next_patch(version: str) -> str:
    """The milestone after a released version: the patch number plus one."""
    head, _, tail = version.rpartition(".")
    return f"{head}.{int(tail) + 1}"


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


@dataclass(frozen=True)
class GateRequest:
    """What the controller knows that the board does not: the commit, its range
    in git, the range on `main`, where the carried range starts, and the flags.

    `milestone_set_aside` is the controller's decision (whether the profile
    allows it is its to know); the gate then carries the milestone's open items
    as they stand and judges nothing about them.
    """

    version: str
    sha: str
    range: str
    main_range: str
    carry_from: str | None
    prefixes: tuple[str, ...]
    emergency: bool
    milestone_set_aside: bool

    @classmethod
    def parse(cls, data: dict) -> "GateRequest":
        try:
            return cls(version=data["version"], sha=data["sha"], range=data["range"],
                       main_range=data["main_range"], carry_from=data.get("carry_from"),
                       prefixes=tuple(data["prefixes"]),
                       emergency=bool(data.get("emergency", False)),
                       milestone_set_aside=bool(data.get("milestone_set_aside", False)))
        except (KeyError, TypeError) as exc:
            raise profile.ProfileError(f"the gate request is malformed: {exc!r}") from None


@dataclass
class Verdict:
    name: str
    passed: bool
    message: str
    reported: bool = False   # a check: passes, but says something the person must see


@dataclass
class GateResult:
    gates: list[Verdict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    carries: dict = field(default_factory=lambda: {"work_packages": [], "issues": [], "releases": []})
    left_out: list[int] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(g.passed for g in self.gates)

    def as_json(self) -> dict:
        return {"passed": self.passed,
                "gates": [{"name": g.name, "result": ("refused" if not g.passed else "reported" if g.reported else "passed"),
                           "message": g.message} for g in self.gates],
                "notes": self.notes, "carries": self.carries, "left_out": self.left_out}


def _delivered(issue: Issue) -> bool:
    return isinstance(issue, (StandaloneProject, WorkPackage))


def _items(issues: Sequence[Issue], milestone: str) -> list[Issue]:
    """The open issues in a milestone that ship: parents and pull requests aside."""
    return [i for i in issues
            if i.raw.milestone == milestone
            and not isinstance(i, (ParentProject, PullRequest))]


def _split(items: Sequence[Issue]) -> tuple[list[int], list[int]]:
    """(work packages, other issues), by number: a project that delivers is a
    work package, anything else is an issue."""
    return (sorted(i.number for i in items if _delivered(i)),
            sorted(i.number for i in items if not _delivered(i)))


def tests_passed(issues: Sequence[Issue], version: str, emergency: bool) -> Verdict:
    """Every work package in the milestone has its tests ticked (`outstanding`).
    A gate; with `emergency` a check, reported and not refused."""
    found = outstanding(issues, version)
    if not found:
        return Verdict("tests-passed", True, f"every work package in {version} has its tests ticked")
    lines = []
    for o in found:
        what = ("no Functional user tests or Technical tests heading" if o.missing_headings
                else f"{o.preview} unticked under {PREVIEW}, {o.rehearsal} under {REHEARSAL}")
        lines.append(f"#{o.number} {o.title[:46]}: {what}")
    text = "; ".join(lines)
    if emergency:
        return Verdict("tests-passed", True, f"emergency: not every test is ticked: {text}", reported=True)
    return Verdict("tests-passed", False, f"tests not passed in milestone {version}: {text}")


def _earlier(req: GateRequest, issues: Sequence[Issue], ev: set[int],
             evall: set[int]) -> list[dict]:
    """The releases made but not deployed whose tags lie in the range, each with
    what it carried that this release also carries. Production gains them too."""
    if not req.carry_from:
        return []
    out = []
    for tag in repo.tags_in_range(f"{req.carry_from}..{req.sha}", list(req.prefixes)):
        version = repo.tag_version(tag, list(req.prefixes))
        if version == req.version:
            continue
        record = repo.tag_record(tag)
        if record is not None:
            all_wp, all_is = list(record["carries"]["work_packages"]), list(record["carries"]["issues"])
            # named only by a reverted commit: not carried
            keep = lambda n: n not in evall or n in ev  # noqa: E731
            wp, other = [n for n in all_wp if keep(n)], [n for n in all_is if keep(n)]
        else:
            # A release made before the tool has no record: its milestone's open
            # items stand for it, carried only where an unreverted commit in the
            # range names them (or the parent that holds them).
            items = _items(issues, version)
            all_wp, all_is = _split(items)
            named = {i.number for i in items
                     if i.number in ev or (i.parent is not None and i.parent in ev)}
            wp, other = [n for n in all_wp if n in named], [n for n in all_is if n in named]
        dropped = sorted(set(all_wp + all_is) - set(wp + other))
        out.append({"version": version, "work_packages": wp, "issues": other, "dropped": dropped})
    return sorted(out, key=lambda r: _version_key(r["version"]))


def _absent_work_packages(req: GateRequest, issues: Sequence[Issue], ev: set[int],
                          earlier_versions: list[str]) -> list[int]:
    """Production Release work packages the commits name that are in neither this
    release's milestone nor an earlier undeployed release's. Other routes are
    left out: they deliver on date milestones."""
    by_number = {i.number: i for i in issues}
    unknown = sorted(n for n in ev if n not in by_number)
    if unknown:
        # a closed one, or a number that is not an issue at all (absent)
        by_number.update({n: classify(raw) for n, raw in sources.issues_in_full(unknown).items()})
    absent = []
    for n in sorted(ev):
        issue = by_number.get(n)
        if issue is None or not _delivered(issue):
            continue
        if route_of(issue.field("Route")) != RELEASE:
            continue
        if issue.raw.milestone != req.version and issue.raw.milestone not in earlier_versions:
            absent.append(n)
    return absent


def milestone_gate(req: GateRequest, issues: Sequence[Issue], result: GateResult) -> None:
    """The milestone is a shipping list (design §9, *The milestone gate*)."""
    own = _items(issues, req.version)
    wp, other = _split(own)
    if req.milestone_set_aside:
        result.carries = {"work_packages": wp, "issues": other, "releases": []}
        result.gates.append(Verdict("milestone", True, "set aside: the milestone's open items are carried as they stand"))
        return

    ev_counts = repo.named_in_range(req.range, effective=True)
    evall = set(repo.named_in_range(req.range, effective=False))
    ev = set(ev_counts)
    main_named = set(repo.named_in_range(req.main_range, effective=False))

    # An open issue not evidenced by a commit in the release (parents aside). A
    # parent's own commits are shown beside its work package and never counted
    # for it (delphside/tile-lite-elite#375).
    missing = unbuilt(carried(issues, req.version, lambda n: ev_counts.get(n, 0)))
    left_out = [r.number for r in missing if req.emergency and r.number in main_named]
    refused = [r for r in missing if r.number not in left_out]
    if refused:
        def one(r) -> str:
            return f"#{r.number}" + (f" (parent #{r.parent} has {r.parent_mentions})"
                                     if r.parent and r.parent_mentions else "")
        result.gates.append(Verdict("milestone", False,
                                    f"open in milestone {req.version} but no commit in the release says Refs: "
                                    + " ".join(one(r) for r in refused)))
        return

    earlier = _earlier(req, issues, ev, evall)
    result.notes += [f"#{n} is in {r['version']} but not carried by {req.version}"
                     for r in earlier for n in r["dropped"]]
    versions = [r["version"] for r in earlier]

    absent = _absent_work_packages(req, issues, ev, versions)
    if absent:
        result.gates.append(Verdict("milestone", False,
                                    "work package(s) " + " ".join(f"#{n}" for n in absent)
                                    + f" name Route Production Release in the release's commits "
                                      f"but are not in milestone {req.version}"))
        return

    result.left_out = sorted(left_out)
    wp = sorted(set([n for n in wp if n not in left_out] + [n for r in earlier for n in r["work_packages"]]))
    other = sorted(set([n for n in other if n not in left_out] + [n for r in earlier for n in r["issues"]]))
    result.carries = {"work_packages": wp, "issues": other, "releases": earlier}
    result.gates.append(Verdict(
        "milestone", True,
        f"carries work packages {compact(wp)} and issues {compact(other)}"
        + (f" (earlier releases in the range: {compact(versions)})" if versions else "")))


def gate(req: GateRequest) -> GateResult:
    """The release's board gates: tests passed, then the milestone. Raises
    `Unavailable` when the board or git cannot be read, which refuses."""
    issues = [classify(raw) for raw in
              sources.fetch("OPEN", with_bodies=True, with_pull_requests=False).issues]
    result = GateResult()
    result.gates.append(tests_passed(issues, req.version, req.emergency))
    milestone_gate(req, issues, result)
    return result


# --------------------------------------------------------------------------
# the checks and the GitHub steps (`checks`, `next`, `publish`)
# --------------------------------------------------------------------------


def checks(sha: str, required: Sequence[str]) -> tuple[bool, dict[str, str], list[str]]:
    """(all green, each required check's conclusion, the ones that are not).
    A required check with no run is `missing`."""
    seen = sources.check_conclusions(sha)
    got = {name: seen.get(name, "missing") for name in required}
    bad = [f"check {name} is {c} on {sha[:12]}" for name, c in got.items() if c != "success"]
    return not bad, got, bad


def open_next(version: str, move: Sequence[int]) -> dict:
    """Open the milestone after `version` and move the left-out items into it.
    Each step that fails is named in `failed`; a rerun finishes what is left."""
    nxt = next_patch(version)
    out: dict = {"milestone": nxt, "created": False, "moved": [], "failed": []}
    try:
        found = {m["title"]: m for m in sources.milestones()}
        if nxt not in found:
            sources.create_milestone(nxt)
            out["created"] = True
            found = {m["title"]: m for m in sources.milestones()}
        number = found[nxt]["number"]
    except (Unavailable, KeyError):
        out["failed"] = ["next milestone"] + [f"move #{n}" for n in move]
        return out
    for n in move:
        try:
            sources.set_milestone(n, number)
            out["moved"].append(n)
        except Unavailable:
            out["failed"].append(f"move #{n}")
    return out


def publish(tag: str, notes_start_tag: str | None = None, retrospective: str | None = None,
            version: str | None = None, commit: str | None = None) -> dict:
    """The retrospective issue (where the rehearsal was skipped), then the GitHub
    Release; each is skipped where it exists, and a failure is named."""
    out: dict = {"retrospective": "not asked", "release": None, "failed": []}
    if retrospective is not None:
        title = f"Retrospective: {version} released with rehearsal skipped"
        try:
            exists = sources.issue_titled(title)
        except Unavailable:
            exists = None
            out["retrospective"] = "unread"
            out["failed"].append("retrospective issue (cannot read the issues)")
        if exists is False:
            body = (f"Release {version} ({commit}) was made with --skip-rehearsal. "
                    f"Reason: {retrospective}. Skipped: rehearsal of this commit and the smoke test "
                    f"the release gate reads. turpin: rehearsal skipped for {version}")
            try:
                sources.create_issue(title, body)
                out["retrospective"] = "raised"
            except Unavailable:
                out["retrospective"] = "failed"
                out["failed"].append("retrospective issue")
        elif exists:
            out["retrospective"] = "exists"
    try:
        if sources.release_exists(tag):
            out["release"] = "exists"
        else:
            sources.create_release(tag, notes_start_tag)
            out["release"] = "created"
    except Unavailable:
        out["failed"].append("GitHub Release")
    return out


# --------------------------------------------------------------------------
# settling (`board-release.py settle`, design §12)
# --------------------------------------------------------------------------


def _comment_once(number: int, text: str, accept: str) -> bool:
    """Say `text` on an issue unless it has been said. `accept` is the plain
    announcement an earlier deploy may already have made (with or without its
    `(deployed to production)`). Returns whether a comment was added."""
    accept = accept or text
    existing = sources.comment_bodies(number)
    if any(b in (accept, accept + " (deployed to production)", text) for b in existing):
        return False
    sources.add_comment(number, text)
    return True


def settle(record: dict, announcement: str, tag: str) -> dict:
    """Do what the record lists, skipping what is done: a work package to
    Post-deployment, an issue closed, each with the announcement once; an item
    an earlier release held that this one drops, out of its milestone; the
    milestones closed. Returns `{settled, done, left}`, and `why` when the issues could not be read; a rerun is harmless."""
    version = record["version"]
    carries = record["carries"]
    releases = carries.get("releases") or []
    comment = f"{announcement}{version}"
    held_by = {n: r["version"] for r in releases for n in r["work_packages"] + r["issues"]}
    done: list[str] = []
    left: list[str] = []

    def words(n: int) -> tuple[str, str]:
        earlier = held_by.get(n)
        if earlier:
            return f"{announcement}{earlier}, deployed with {tag}", f"{announcement}{earlier}"
        return f"{comment} (deployed to production)", comment

    dropped = [(r["version"], n) for r in releases for n in r.get("dropped") or []]
    wanted = list(carries["work_packages"]) + list(carries["issues"]) + [n for _, n in dropped]
    why = ""
    try:
        read = {n: classify(raw) for n, raw in sources.issues_in_full(wanted).items()}
    except Unavailable as exc:
        read, why = {}, str(exc)

    for n in carries["work_packages"]:
        issue = read.get(n)
        if issue is None:
            left.append(f"#{n}")
            continue
        if issue.field(PROJECT_STATE) != POST_DEPLOYMENT:
            try:
                sources.set_field(n, PROJECT_STATE, POST_DEPLOYMENT)
                done.append(f"#{n} state")
            except Unavailable:
                left.append(f"#{n} state")
                continue
        try:
            if _comment_once(n, *words(n)):
                done.append(f"#{n} comment")
        except Unavailable:
            left.append(f"#{n} comment")

    for n in carries["issues"]:
        issue = read.get(n)
        if issue is None:
            left.append(f"#{n}")
            continue
        try:
            if _comment_once(n, *words(n)):
                done.append(f"#{n} comment")
        except Unavailable:
            left.append(f"#{n} comment")
            continue
        if issue.state != "CLOSED":
            try:
                sources.close_issue(n)
                done.append(f"#{n} close")
            except Unavailable:
                left.append(f"#{n} close")

    # Items an earlier release held that this one does not carry: out of that
    # release's milestone, state untouched.
    for held, n in dropped:
        issue = read.get(n)
        if issue is None:
            left.append(f"#{n}")
            continue
        if issue.raw.milestone != held:
            continue
        try:
            if _comment_once(n, f"{announcement}{version} without this (not shipped): it was in "
                                f"milestone {held}, which {tag} supersedes, but {tag} does not carry "
                                f"it, so it is removed from {held}", ""):
                done.append(f"#{n} comment")
        except Unavailable:
            left.append(f"#{n} comment")
            continue
        try:
            sources.set_milestone(n, None)
            done.append(f"#{n} milestone")
        except Unavailable:
            left.append(f"#{n} milestone")

    titles = [version] + [r["version"] for r in releases]
    try:
        found = {m["title"]: m for m in sources.milestones()}
    except Unavailable:
        left += [f"milestone {t}" for t in titles]
        found = {}
    for title in titles:
        m = found.get(title)
        if m is None or m.get("state") == "closed":
            continue
        try:
            sources.close_milestone(m["number"])
            done.append(f"milestone {title}")
        except Unavailable:
            left.append(f"milestone {title}")
    out = {"settled": not left, "done": done, "left": left}
    if why:
        out["why"] = why     # why the issues could not be read, said once
    return out
