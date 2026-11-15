"""The board flow: who holds each open item, whether it has stalled, and what the
daily sweep writes to keep the board true.

Designed in `programme/records/2.5-changes/process-definition/176-project-board-flow/`
(R1 to R14). **The flow table is `model.FLOW`; this only judges against it.**
Every bound, holder and `Turn` it writes is the table's, so a document and a
list cannot disagree about them (R3).

What the sweep does for each open issue and pull request in the programme's
repositories, read over REST:

* R7: an issue with no type becomes a Requirement; one with no state gets its
  type's starting state. A non-requirement with no workstream is raised with
  the owner. A pull request is never given a type or an issue field.
* It derives the item's holder and `Turn` from the table and writes the `Turn`
  where it differs. A thread-set `Owner` with an approval comment, and a `Hold`
  whose reason still holds, are kept; any other is overwritten.
* It lists what has stalled: an item past its bound, by the role that holds
  it, with its claim. A claim that is stale is kept and the item offered to the
  role's current thread.
* It catches the moves an event missed: a merged pull request's `Refs #N`, and a
  closed release milestone (`Deployment` -> `Post-deployment`).

Nothing is remembered between runs. An item's age is read from GitHub each
time, so a missed day is corrected by the next (implementation.md, choice 2).

**Age over REST is the latest field event of any field.** GitHub's REST
timeline says that a field changed, not which field or to what, so the
`step_ages` way of matching the value moved to is not available to a cloud
session. The sweep's own writes are field events too: a `Turn` it writes
restarts the clock of the item it writes to, so an item first written is aged
from that write and is listed again only when seven days pass from it.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Sequence

from . import flow_settings, profile, refs, sources
from .model import (
    CLAIMED_BY, PROJECT_STATE, RELEASE, RELEASE_CHECK, REVIEW_DUE_DAYS, ROLE_AUTHOR,
    ROLE_OWNER, ROLES, STARTING_STATE, STATE_FIELD_OF, TURN, TURN_HOLD,
    TURN_OWNER, TURNS, TYPE_HOLDER, WORKSTREAM, HOLD_ON_NAMED, HOLD_ON_RELEASE,
    HOLD_ON_SENDER, FLOW, Flow, Issue, Observed, ParentProject, StandaloneProject,
    WorkPackage, classify, delivered_by_merge, flow_row, role_turn, route_of, section,
    ROLE_DESIGN,
)
from .sources import Unavailable
from .turn import waiting_on_owner

SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
SESSION_LINK = re.compile(r"https://claude\.ai/code/session_[A-Za-z0-9_-]+")
_URL = re.compile(r"https?://[^\s)>\]]+")
_REVIEW_DATE = re.compile(r"(?im)\breview(?:\s+date)?\b[^\n]*?(\d{4}-\d{2}-\d{2})")
_REF = re.compile(r"(?:(?P<repo>[\w.-]+/[\w.-]+))?#(?P<n>\d+)\b"
                  r"|https://github\.com/(?P<urepo>[\w.-]+/[\w.-]+)/(?:issues|pull)/(?P<un>\d+)")

# The states a parent rests in while any of its work packages is open: it runs
# Scope to Design and Test Approach, then waits on its packages (design.md).
PARENT_RESTS = ("Design and Test Approach", "Development", "User testing", "Deployment")
DEPENDENCIES_HEADING = "Dependencies and related work"
# A merge from either of these moves a package by its route.
MERGE_FROM = ("Development", "User testing")

# What an attention finding is called, in the order they are listed.
INVALID_HOLD = "invalid hold"
LOST = "lost"
UNKNOWN_STATE = "unknown state"
UNKNOWN_TYPE = "unknown type"
NO_WORKSTREAM = "no workstream"
NOT_VISIBLE = "not visible"
MALFORMED_CLAIM = "malformed claim"
ATTENTION_ORDER = (LOST, INVALID_HOLD, NO_WORKSTREAM, UNKNOWN_STATE, UNKNOWN_TYPE,
                   MALFORMED_CLAIM, NOT_VISIBLE)


def parse_time(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        when = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def stamp(when: datetime) -> str:
    return when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def days(delta: timedelta) -> float:
    return delta.total_seconds() / 86400


# --------------------------------------------------------------------------
# claims
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Claim:
    """`Claimed by`: the role holding the item, and the thread holding the role
    now (design.md, *Claims*). The role alone where no thread is known."""

    role: str
    thread: str | None = None

    def __str__(self) -> str:
        return f"{self.role} {self.thread}" if self.thread else self.role


def parse_claim(text: str | None) -> tuple[Claim | None, bool]:
    """(the claim, whether the text was malformed). No text is no claim and not
    malformed; a malformed claim is reported and read as none (S-G15)."""
    if text is None or not text.strip():
        return None, False
    first, _, rest = text.strip().partition(" ")
    if first not in ROLES:
        return None, True
    rest = rest.strip()
    if not rest:
        return Claim(first), False
    link = _URL.search(rest)
    if link is None:
        return None, True
    return Claim(first, link.group(0)), False


def pull_claim(body: str) -> Claim | None:
    """A pull request's claim: the project thread its body's attribution line
    links (S-G16). The last such link is the line at the foot."""
    links = SESSION_LINK.findall(body or "")
    return Claim(ROLE_AUTHOR, links[-1]) if links else None


# --------------------------------------------------------------------------
# what a judgement holds
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Write:
    """One write the sweep makes: an issue's type, or one of its fields."""

    repo: str
    number: int
    kind: str               # "type" or "field"
    name: str               # the field's name; "Type" for a type
    value: str

    @property
    def target(self) -> str:
        return f"{self.repo}#{self.number}"

    def __str__(self) -> str:
        return f"{self.target} {self.name} = {self.value}"


@dataclass(frozen=True)
class Attention:
    """Something a role must look at that is not a stall: a hold that no longer
    holds, an item no one holds, a field that cannot be read."""

    kind: str
    role: str
    detail: str


@dataclass
class Verdict:
    obs: Observed
    typ: str | None = None
    state: str | None = None
    role: str | None = None
    workstream: str | None = None
    turn: str | None = None
    owes: str = ""
    age: timedelta | None = None
    bound: float | None = None
    bound_text: str = ""
    stalled: bool = False
    resting: str | None = None
    claim: Claim | None = None
    parts: tuple[tuple[str, str], ...] = ()
    writes: list[Write] = field(default_factory=list)
    attention: list[Attention] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.obs.name

    @property
    def title(self) -> str:
        return self.obs.raw.title

    @property
    def age_days(self) -> float | None:
        return None if self.age is None else days(self.age)

    @property
    def offered(self) -> bool:
        """A claim on a stalled item is stale: the item is offered to the
        role's current thread and the claim kept (S-G9)."""
        return self.stalled and self.claim is not None


# --------------------------------------------------------------------------
# the context a judgement reads from
# --------------------------------------------------------------------------


def semver(title: str | None) -> tuple[int, int, int] | None:
    m = SEMVER.match(title or "")
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


class Context:
    """The run's clock and its lazy reads: each is made once, only when an item
    needs it, so a sweep with nothing to judge costs only its listings."""

    def __init__(self, observed: Sequence[Observed], now: datetime,
                 board=sources) -> None:
        self.now = now
        self.today = now.astimezone(timezone.utc).date()
        self.board = board
        self.open = {(o.repo.lower(), o.raw.number) for o in observed}
        self.pulls: dict[str, list[Observed]] = {}
        for o in observed:
            if o.pull:
                self.pulls.setdefault(o.repo, []).append(o)
        self.owner = profile.programme_file().string("accounts.owner").lower()
        self._milestones: dict[str, tuple] = {}
        self._merged: dict[str, tuple] = {}
        self._comments: dict[tuple[str, int], tuple] = {}
        self._commits: dict[tuple[str, str], str] = {}

    def milestones(self, repo: str):
        if repo not in self._milestones:
            self._milestones[repo] = self.board.milestones_of(repo)
        return self._milestones[repo]

    def merged(self, repo: str):
        if repo not in self._merged:
            since = self.now - timedelta(days=flow_settings.MERGED_LOOKBACK_DAYS)
            self._merged[repo] = self.board.merged_since(repo, stamp(since))
        return self._merged[repo]

    def comments(self, repo: str, number: int):
        key = (repo, number)
        if key not in self._comments:
            self._comments[key] = self.board.comments_of(repo, number)
        return self._comments[key]

    def commit_time(self, repo: str, sha: str) -> str:
        key = (repo, sha)
        if key not in self._commits:
            self._commits[key] = self.board.commit_time(repo, sha)
        return self._commits[key]

    def pulls_naming(self, repo: str, number: int) -> list[Observed]:
        """The open pull requests of `repo` for issue `number`: by the `Refs`
        in the title or body, or by the branch's name."""
        found = []
        for p in self.pulls.get(repo, ()):
            named = refs.pull_request_names(p.raw.title, p.raw.body)
            if p.raw.head_ref and refs.branch_issue(p.raw.head_ref):
                named.add(refs.branch_issue(p.raw.head_ref))
            if number in named:
                found.append(p)
        return found


# --------------------------------------------------------------------------
# holds
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Reason:
    valid: bool
    text: str
    ended_at: datetime | None = None   # for a release that has closed


def _linked_refs(obs: Observed) -> list[tuple[str, int]]:
    """The issues the body's *Dependencies and related work* section names."""
    text = section(obs.raw.body, DEPENDENCIES_HEADING)
    out = []
    for m in _REF.finditer(text):
        repo = m.group("repo") or m.group("urepo") or obs.repo
        number = int(m.group("n") or m.group("un"))
        out.append((repo.lower(), number))
    return out


def release_wait(obs: Observed, issue: Issue, ctx: Context) -> Reason | None:
    """The release an item waits on (design.md, *Hold reasons*), or None where
    it waits on none. `Deployment` waits for its own milestone; a `Release
    Check` package at `Post-deployment` waits for the next release milestone in
    its repository, the one after its own. While none is open the wait stays
    valid."""
    raw = obs.raw
    if issue.step == "Deployment":
        if not raw.milestone:
            return None
        if obs.milestone_state == "closed":
            return Reason(False, f"its release {raw.milestone} has closed")
        return Reason(True, f"waiting for release {raw.milestone}")
    if issue.step == "Post-deployment" and RELEASE_CHECK in raw.labels:
        releases = sorted(((semver(m.title), m) for m in ctx.milestones(obs.repo)
                           if semver(m.title)), key=lambda pair: pair[0])
        own = semver(raw.milestone)
        if own:
            later = [m for v, m in releases if v > own]
        else:
            later = [m for v, m in releases if m.state == "open"]
        nxt = later[0] if later else None
        if nxt is None or nxt.state == "open":
            name = nxt.title if nxt else "none raised yet"
            return Reason(True, f"waiting for the next release ({name})")
        return Reason(False, f"the next release {nxt.title} has closed",
                      parse_time(nxt.closed_at))
    return None


def hold_reason(obs: Observed, issue: Issue, ctx: Context) -> Reason:
    """Whether the item's `Hold` is valid: the first accepted reason that still
    holds, else why none does (S-G14)."""
    if issue.step == "Waiting on sender":
        return Reason(True, "waiting on the sender")
    ended = []
    release = release_wait(obs, issue, ctx)
    if release is not None:
        if release.valid:
            return release
        ended.append(release)
    open_links = [f"{lk.repo}#{lk.number}" for lk in obs.links if lk.state == "open"]
    closed_links = [f"{lk.repo}#{lk.number}" for lk in obs.links if lk.state != "open"]
    for repo, number in _linked_refs(obs):
        label = f"{repo}#{number}"
        if (repo, number) in ctx.open:
            open_links.append(label)
        else:
            closed_links.append(label)
    if open_links:
        return Reason(True, "waiting on " + ", ".join(dict.fromkeys(open_links)))
    text = section(obs.raw.body, DEPENDENCIES_HEADING)
    dated = _REVIEW_DATE.search(text)
    if dated:
        try:
            when = date.fromisoformat(dated.group(1))
        except ValueError:
            when = None
        if when is not None:
            if ctx.today < when:
                return Reason(True, f"waiting on a named event, reviewed {when}")
            ended.append(Reason(False, f"its review date {when} has come"))
    if closed_links:
        ended.append(Reason(False, "its dependency " + ", ".join(dict.fromkeys(closed_links))
                            + " has closed"))
    if ended:
        return Reason(False, "; ".join(r.text for r in ended),
                      next((r.ended_at for r in ended if r.ended_at), None))
    return Reason(False, "no reason is named under Dependencies and related work")


def owner_approval_pending(obs: Observed, ctx: Context) -> bool:
    """Whether a thread-set `Turn` = `Owner` still has its approval comment: the
    latest comment is not the owner's, so what he is to approve is asked and
    unanswered (M10). Once he comments the move is the thread's again."""
    comments = ctx.comments(obs.repo, obs.raw.number)
    return bool(comments) and comments[-1].author.lower() != ctx.owner


# --------------------------------------------------------------------------
# missed events
# --------------------------------------------------------------------------


def missed_move(obs: Observed, issue: Issue, ctx: Context) -> str | None:
    """The `Project State` a work package should already be in because of an
    event nobody moved it for, or None (I5, S-G13).

    A closed release milestone ships its package at `Deployment`. A merged pull
    request whose `Refs #N` names a package at `Development` or `User testing`
    moves it by its route: a Production Release to `Deployment`, a tooling
    route (delivered by the merge) to `Post-deployment`. A package with an open
    pull request is not moved: a reopened one has a new branch."""
    if not isinstance(issue, (WorkPackage, StandaloneProject)):
        return None
    if issue.step == "Deployment":
        if semver(obs.raw.milestone) and obs.milestone_state == "closed":
            return "Post-deployment"
        return None
    if issue.step not in MERGE_FROM:
        return None
    route = route_of(issue.route)
    if route == RELEASE:
        target = "Deployment"
    elif delivered_by_merge(route):
        target = "Post-deployment"
    else:
        return None
    if ctx.pulls_naming(obs.repo, obs.raw.number):
        return None
    for merged in ctx.merged(obs.repo):
        if obs.raw.number in refs.pull_request_names(merged.title, merged.body):
            return target
    return None


# --------------------------------------------------------------------------
# judging
# --------------------------------------------------------------------------


def state_start(obs: Observed) -> datetime | None:
    """When the item's current state began, as far as REST can say: the later
    of its creation and its last field event."""
    times = [t for t in (parse_time(obs.raw.created_at), parse_time(obs.changed_at)) if t]
    return max(times) if times else None


def _development_start(obs: Observed, ctx: Context) -> datetime | None:
    """`Development` is aged from the head commit of the package's open pull
    request (S-G11); with none, from the field's own age."""
    for pull in ctx.pulls_naming(obs.repo, obs.raw.number):
        if pull.head_sha:
            return parse_time(ctx.commit_time(obs.repo, pull.head_sha))
    return state_start(obs)


def _review_due(text: str) -> date | None:
    m = _REVIEW_DATE.search(text or "")
    if not m:
        return None
    try:
        return date.fromisoformat(m.group(1))
    except ValueError:
        return None


def judge(obs: Observed, ctx: Context) -> Verdict:
    """Judge one item against the flow table. Reads what it needs through the
    context; raises `Unavailable` where a read it needs could not be made."""
    return judge_pull(obs, ctx) if obs.pull else judge_issue(obs, ctx)


def judge_pull(obs: Observed, ctx: Context) -> Verdict:
    """A pull request: its state is derived from GitHub (never typed), it takes
    no issue field, and its claim is the thread its body links."""
    raw = obs.raw
    issue = classify(raw)
    v = Verdict(obs, typ="PullRequest", state=issue.step)
    row = flow_row(issue)
    v.claim = pull_claim(raw.body)
    if row is None:
        v.attention.append(Attention(UNKNOWN_STATE, ROLE_AUTHOR,
                                     f"pull request state {issue.step!r} is not in the flow table"))
        return v
    v.role, v.owes, v.bound = row.role, row.owes, row.bound
    v.turn = row.turn
    start = state_start(obs)
    v.age = None if start is None else ctx.now - start
    _stall(v)
    return v


def _stall(v: Verdict) -> None:
    """Past the bound, and not resting, is stalled; at the bound is not."""
    v.bound_text = "no bound" if v.bound is None else f"{v.bound:g} days"
    if v.resting or v.bound is None or v.age is None:
        return
    v.stalled = v.age > timedelta(days=v.bound)


def judge_issue(obs: Observed, ctx: Context) -> Verdict:
    raw = obs.raw
    v = Verdict(obs)
    if not obs.fields_visible:
        v.attention.append(Attention(NOT_VISIBLE, ROLE_OWNER,
                                     "its issue fields could not be read"))
        return v

    typ = raw.issue_type
    v.workstream = raw.fields.get(WORKSTREAM)
    if typ is None:
        v.writes.append(Write(obs.repo, raw.number, "type", "Type", "Requirement"))
        typ = "Requirement"
    v.typ = typ
    cur = raw.fields.get(TURN)

    if typ not in FLOW:
        # A type the table has no states for: it is reported, never retyped.
        v.role = ROLE_OWNER
        v.attention.append(Attention(UNKNOWN_TYPE, ROLE_OWNER,
                                     f"issue type {typ!r} is not one the flow table holds"))
        if cur not in TURNS:
            v.attention.append(Attention(LOST, ROLE_OWNER,
                                         f"it has a type the flow table cannot place and no {TURN}"))
        return v

    fields = dict(raw.fields)
    state_field = STATE_FIELD_OF[typ]
    if not fields.get(state_field):
        start = STARTING_STATE[typ]
        v.writes.append(Write(obs.repo, raw.number, "field", state_field, start))
        fields[state_field] = start
    issue = classify(replace(raw, issue_type=typ, fields=fields))

    moved = False
    prior_release: Reason | None = None
    target = missed_move(obs, issue, ctx)
    if target:
        prior_release = release_wait(obs, issue, ctx)
        v.writes.append(Write(obs.repo, raw.number, "field", PROJECT_STATE, target))
        fields[PROJECT_STATE] = target
        issue = classify(replace(raw, issue_type=typ, fields=fields))
        moved = True

    v.state = issue.step
    v.claim, malformed = parse_claim(raw.fields.get(CLAIMED_BY))
    row = flow_row(issue)
    if row is None:
        v.role = TYPE_HOLDER[typ] if v.workstream else ROLE_OWNER
        v.attention.append(Attention(UNKNOWN_STATE, v.role,
                                     f"{state_field} {issue.step!r} is not in the flow table"))
        if cur not in TURNS:
            v.attention.append(Attention(LOST, v.role,
                                         f"its state is not in the flow table and it has no {TURN}"))
        return v

    # Who holds it.
    role = row.role
    if typ == "Requirement" and issue.step == "Triage" and not v.workstream:
        role = ROLE_OWNER                       # the triage queue is the owner's (R7)
    parent = isinstance(issue, ParentProject)
    resting_parent = parent and obs.open_packages > 0 and issue.step in PARENT_RESTS
    if parent and (resting_parent or issue.step == "Project Closedown"):
        role = ROLE_DESIGN
    if typ in ("Project", "Decision") and not v.workstream:
        v.attention.append(Attention(NO_WORKSTREAM, ROLE_OWNER,
                                     "it has no workstream: give it one"))
    if malformed:
        v.attention.append(Attention(MALFORMED_CLAIM, role,
                                     f"{CLAIMED_BY} {raw.fields.get(CLAIMED_BY)!r} is not a role "
                                     "and a link; read as no claim"))

    # What `Turn` says.
    derived = role_turn(role)
    hold_applies = (row.hold in (HOLD_ON_NAMED, HOLD_ON_SENDER)
                    or (row.hold == HOLD_ON_RELEASE
                        and (issue.step == "Deployment" or RELEASE_CHECK in raw.labels)))
    reason: Reason | None = None
    if hold_applies or cur == TURN_HOLD:
        reason = hold_reason(obs, issue, ctx)
        if moved and prior_release is not None and not prior_release.valid:
            reason = Reason(reason.valid, prior_release.text, reason.ended_at)
    final = derived
    if hold_applies:
        final = TURN_HOLD if reason.valid else derived
    if cur == TURN_HOLD:
        if reason.valid:
            final = TURN_HOLD
        else:
            v.attention.append(Attention(INVALID_HOLD, role, reason.text))
    elif hold_applies and not reason.valid and row.hold == HOLD_ON_NAMED:
        v.attention.append(Attention(INVALID_HOLD, role, reason.text))
    if cur == TURN_OWNER and derived != TURN_OWNER and owner_approval_pending(obs, ctx):
        final, role = TURN_OWNER, ROLE_OWNER
    if cur != final:
        v.writes.append(Write(obs.repo, raw.number, "field", TURN, final))
    # The owner has a part in a state only while he has something to do in it:
    # his own sources (`turn.waiting_on_owner`) say so, not the state alone.
    parts = tuple(p for p in row.parts if p[0] != ROLE_OWNER or waiting_on_owner(issue))
    v.role, v.turn, v.owes, v.parts = role, final, row.owes, parts
    if role != row.role and role == ROLE_OWNER:
        v.owes = "approve, or answer, as the latest comment asks"

    # How long it has sat.
    v.bound = row.bound
    start = state_start(obs)
    if issue.step == "Development":
        start = _development_start(obs, ctx)
    if issue.step == "Post-deployment" and RELEASE_CHECK in raw.labels and reason is not None \
            and not reason.valid and reason.ended_at:
        # The hold has ended: the review is due at once, and stalls 7 days
        # after the next release closed (design.md, Project table).
        start, v.bound = reason.ended_at, REVIEW_DUE_DAYS
    if moved:
        start = ctx.now                          # the state began with this write
    v.age = None if start is None else max(ctx.now - start, timedelta(0))
    if start is None and row.bound is not None:
        v.attention.append(Attention(NOT_VISIBLE, role, "its age could not be read"))

    v.resting = _resting(v, row, resting_parent)
    if issue.step == "Pending" and typ == "Ticket":
        _pending(v, obs, ctx)
    else:
        _stall(v)
    return v


def _resting(v: Verdict, row: Flow, resting_parent: bool) -> str | None:
    if resting_parent:
        return "waiting on its work packages"
    if v.turn == TURN_HOLD and not row.stalls_under_hold:
        return "held"
    return None


def _pending(v: Verdict, obs: Observed, ctx: Context) -> None:
    """A Ticket at `Pending` is stalled after the review date in its last note
    (1.8); a note naming none falls back to the table's bound."""
    comments = ctx.comments(obs.repo, obs.raw.number)
    due = _review_due(comments[-1].body) if comments else None
    if due is None:
        _stall(v)
        return
    v.bound, v.bound_text = None, f"until {due}"
    v.stalled = ctx.today > due


# --------------------------------------------------------------------------
# the sweep
# --------------------------------------------------------------------------


class Refusal(Exception):
    """The sweep will not run: a thing it needs is missing."""


@dataclass
class Sweep:
    verdicts: list[Verdict]
    pinned: Observed | None
    failures: list[str] = field(default_factory=list)
    made: list[Write] = field(default_factory=list)
    planned: list[Write] = field(default_factory=list)
    now: datetime | None = None
    body: str = ""
    ids: dict[str, int] = field(default_factory=dict)

    @property
    def stalled(self) -> list[Verdict]:
        return [v for v in self.verdicts if v.stalled]

    @property
    def attention(self) -> list[tuple[Verdict, Attention]]:
        return [(v, a) for v in self.verdicts for a in v.attention]


def programme_repository() -> str:
    return profile.programme_file().string("programme.repository")


def find_pinned(observed: Sequence[Observed]) -> Observed | None:
    for o in observed:
        if (o.repo == programme_repository() and not o.pull
                and o.raw.title == flow_settings.STALLED_LIST_TITLE):
            return o
    return None


def field_ids(observed: Sequence[Observed]) -> dict[str, int]:
    """Each field's id: the setting where it holds one, else the id some issue
    carries a value of the field under."""
    learned: dict[str, int] = {}
    for o in observed:
        learned.update(o.field_ids)
    ids = dict(learned)
    ids.update({k: v for k, v in flow_settings.FIELD_IDS.items() if v is not None})
    return ids


def survey(now: datetime, board=sources, repositories: Sequence[str] | None = None,
           require_pinned: bool = False) -> Sweep:
    """Read every repository and judge every open item; write nothing. Raises
    `Unavailable` where a listing could not be read, `Refusal` where a pinned
    issue is required and missing."""
    observed: list[Observed] = []
    for repo in repositories or profile.watched_repositories():
        observed += board.observe(repo)
    pinned = find_pinned(observed)
    if require_pinned and pinned is None:
        raise Refusal(f"there is no open issue titled {flow_settings.STALLED_LIST_TITLE!r} in "
                      f"{programme_repository()}: create it by hand, then run again")
    items = [o for o in observed if o is not pinned]
    ctx = Context(observed, now, board)
    sweep = Sweep([], pinned, now=now)
    sweep.ids = field_ids(observed)
    for o in items:
        try:
            sweep.verdicts.append(judge(o, ctx))
        except Unavailable as exc:
            sweep.failures.append(f"{o.name}: {exc}")
    sweep.planned = [w for v in sweep.verdicts for w in v.writes]
    return sweep


def perform(sweep: Sweep, board=sources) -> None:
    """Make each planned write, one call each. A write that fails is recorded
    with the item and the call, and the rest of that item's writes are not
    attempted; every other item is still written."""
    ids = sweep.ids
    for v in sweep.verdicts:
        for w in v.writes:
            try:
                if w.kind == "type":
                    board.set_issue_type(w.repo, w.number, w.value)
                else:
                    fid = ids.get(w.name)
                    if fid is None:
                        raise Unavailable(f"no id is known for the issue field {w.name!r}: set it in "
                                          "flow_settings.FIELD_IDS")
                    board.write_issue_field(w.repo, w.number, fid, w.value)
            except Unavailable as exc:
                sweep.failures.append(f"{w}: {exc}")
                break
            sweep.made.append(w)


# --------------------------------------------------------------------------
# what is published
# --------------------------------------------------------------------------


def _place(v: Verdict) -> tuple[str, str]:
    return v.role or ROLE_OWNER, v.workstream or ""


def line(v: Verdict) -> str:
    age = "age unknown" if v.age is None else f"{v.age_days:.1f} days"
    claim = ""
    if v.offered:
        claim = f"; stale claim {v.claim} kept, offered to the role's current thread"
    elif v.claim:
        claim = f"; claimed by {v.claim}"
    state = f" ({v.state})" if v.state else ""
    return f"{v.name} {v.title}{state}: {v.owes}; {age} against {v.bound_text}{claim}"


def stalled_by_role(sweep: Sweep) -> dict[tuple[str, str], list[Verdict]]:
    groups: dict[tuple[str, str], list[Verdict]] = {}
    for v in sweep.stalled:
        groups.setdefault(_place(v), []).append(v)
    for items in groups.values():
        items.sort(key=lambda v: (-(v.age_days or 0), v.name))
    return dict(sorted(groups.items()))


def attention_by_role(sweep: Sweep) -> dict[str, list[tuple[Verdict, Attention]]]:
    groups: dict[str, list[tuple[Verdict, Attention]]] = {}
    for v, a in sorted(sweep.attention,
                       key=lambda p: (ATTENTION_ORDER.index(p[1].kind), p[0].name)):
        groups.setdefault(a.role, []).append((v, a))
    return dict(sorted(groups.items()))


def render(sweep: Sweep) -> str:
    """The stalled list: what the pinned issue's body holds and the run prints."""
    out = [f"Last complete run: {stamp(sweep.now)}", ""]
    stalled = stalled_by_role(sweep)
    attention = attention_by_role(sweep)
    if not stalled and not attention:
        out.append("Nothing is stalled.")
        return "\n".join(out) + "\n"
    if stalled:
        out.append("## Stalled")
        for (role, workstream), items in stalled.items():
            out += ["", f"### {role}" + (f" ({workstream})" if workstream else "")]
            out += [f"- {line(v)}" for v in items]
    else:
        out.append("Nothing is stalled.")
    if attention:
        out += ["", "## Needs a look"]
        for role, found in attention.items():
            out += ["", f"### {role}"]
            out += [f"- {v.name} {v.title}: {a.kind}: {a.detail}" for v, a in found]
    return "\n".join(out) + "\n"


def role_list(sweep: Sweep, role: str, workstream: str | None = None) -> list[tuple[Verdict, str]]:
    """The items a role has to do with, oldest first: those it holds, and those
    where it has a part in the state (design.md, R1)."""
    found: list[tuple[Verdict, str]] = []
    for v in sweep.verdicts:
        if workstream and (v.workstream or "") != workstream:
            continue
        if v.role == role:
            found.append((v, v.owes))
        else:
            for part_role, what in v.parts:
                if part_role == role:
                    found.append((v, f"your part: {what}"))
    found.sort(key=lambda p: (-(p[0].age_days or 0), p[0].name))
    return found


def render_role(sweep: Sweep, role: str, workstream: str | None = None) -> str:
    found = role_list(sweep, role, workstream)
    who = role + (f" ({workstream})" if workstream else "")
    if not found:
        return f"Nothing is waiting on the {who}.\n"
    out = [f"{len(found)} for the {who}, oldest first", ""]
    for v, what in found:
        age = "age unknown" if v.age_days is None else f"{v.age_days:.1f} days"
        marks = []
        if v.stalled:
            marks.append("STALLED")
        if v.resting:
            marks.append(f"resting: {v.resting}")
        if v.claim:
            marks.append(f"claimed by {v.claim}")
        extra = f" [{'; '.join(marks)}]" if marks else ""
        out.append(f"  {v.name} {v.title}  —  {what}  ({age} against {v.bound_text}){extra}")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------
# the command
# --------------------------------------------------------------------------

EXIT_CLEAN, EXIT_STALLED, EXIT_FAILED = 0, 1, 2


def run(now: datetime, dry_run: bool = False, board=sources,
        say: Callable[[str], None] = print,
        complain: Callable[[str], None] | None = None) -> int:
    """One daily sweep. Exits 0 when nothing is stalled or needs a look, 1 when
    something is, 2 when it could not finish; a failed run never exits 1 (S-G21)."""
    complain = complain or (lambda text: print(text, file=sys.stderr))
    try:
        sweep = survey(now, board, require_pinned=True)
    except Refusal as exc:
        complain(f"board-flow: refusing: {exc}")
        return EXIT_FAILED
    except Unavailable as exc:
        complain(f"board-flow: could not read the board: {exc}")
        return EXIT_FAILED

    if dry_run:
        for w in sweep.planned:
            say(f"would write {w}")
        say(f"would rewrite {sweep.pinned.name} ({flow_settings.STALLED_LIST_TITLE})")
    else:
        perform(sweep, board)
        for w in sweep.made:
            say(f"wrote {w}")

    if sweep.failures:
        complain("board-flow: the run did not finish:")
        for failure in sweep.failures:
            complain(f"  {failure}")
        complain("the stalled list was not rewritten, so it still names the last complete run")
        say(render(sweep))
        return EXIT_FAILED

    sweep.body = render(sweep)
    if not dry_run:
        try:
            board.rewrite_body(sweep.pinned.repo, sweep.pinned.raw.number, sweep.body)
        except Unavailable as exc:
            complain(f"board-flow: could not rewrite {sweep.pinned.name}: {exc}")
            say(sweep.body)
            return EXIT_FAILED
    say(sweep.body)
    return EXIT_STALLED if (sweep.stalled or sweep.attention) else EXIT_CLEAN
