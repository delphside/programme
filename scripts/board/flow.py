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
  where it differs. A `Turn` is kept only where a thread set it: one that is not
  what the sweep last wrote (the ledger, below). A thread-set `Owner` with an
  approval comment, and a `Hold` whose reason still holds, are kept; any other
  is overwritten.
* It lists what has stalled: an item past its bound, by the role that holds
  it, with its claim. A claim that is stale is kept and the item offered to the
  role's current thread.
* It moves a package whose release milestone closed (`Deployment` ->
  `Post-deployment`). A merged pull request that names a package still before
  its merge phase is only reported, under "needs a look": a merge may be one of
  several, so a person moves it.

**The ledger** is the one thing remembered between runs: a JSON block in an HTML
comment at the foot of the pinned issue's body, which only the sweep writes. For
each open item it holds its state, when the sweep first saw it in that state,
and the `Turn` the sweep last wrote. Over REST the timeline says that a field
changed, not which field or to what, so the age of a state cannot be read from
GitHub once the sweep writes fields itself: its own `Turn` write would restart
the clock. An item with no entry (or one whose state has changed since) is aged
from its latest field event of any field, or its creation, judged before this
run writes anything; the entry then keeps that time. A dry run reads the ledger
and writes nothing, the ledger included.

A failed run still replaces the ledger, recording the writes actually made, and
leaves the stalled list as the last complete run's. An item with no entry has
its `Turn` judged afresh (see `judge_issue`), never taken as a thread's. An item
not judged this run keeps its entry while it is open. A pinned body that an
earlier run wrote and that has no readable ledger is listed under "needs a
look". The ledger is compact (short keys), and a body that would pass
`BODY_LIMIT` loses the tail of its list, never its ledger. Runs must not
overlap: the coordinator's one daily trigger runs it.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Sequence

import json

from . import merge, profile, refs, sources
from .model import (
    CLAIMED_BY, PROJECT_STATE, RELEASE_CHECK, REVIEW_DUE_DAYS, ROLE_AUTHOR,
    ROLE_OWNER, ROLES, STARTING_STATE, STATE_FIELD_OF, TURN, TURN_HOLD,
    TURN_OWNER, TURNS, TYPE_HOLDER, WORKSTREAM, HOLD_ON_NAMED, HOLD_ON_RELEASE,
    HOLD_ON_SENDER, FLOW, Flow, Issue, Observed, ParentProject, StandaloneProject,
    WorkPackage, classify, flow_row, owes_no_review, role_turn, section, ROLE_DESIGN,
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
# The issue whose body each sweep rewrites, found in the programme repository by
# this exact title (owner, 2026-11-13: a pinned issue). It is an identifier
# stored in GitHub: changing it blinds the sweep to the issue that exists
# (docs/1.10).
STALLED_LIST_TITLE = "Board flow: the stalled list"
# What a pull request that owes no review reads as, in place of `Drafting`.
NO_REVIEW_OWED = "No review owed"

# What an attention finding is called, in the order they are listed.
INVALID_HOLD = "invalid hold"
LOST = "lost"
UNKNOWN_STATE = "unknown state"
UNKNOWN_TYPE = "unknown type"
NO_WORKSTREAM = "no workstream"
NOT_VISIBLE = "not visible"
MALFORMED_CLAIM = "malformed claim"
MERGED = "merged, not moved"
LEDGER_LOST = "no readable ledger"
NEAR_LIMIT = "pinned body near GitHub's limit"
# GitHub caps an issue body at 65,536 characters; the sweep stays under this.
BODY_LIMIT = 65_000
ATTENTION_ORDER = (LOST, INVALID_HOLD, NO_WORKSTREAM, UNKNOWN_STATE, UNKNOWN_TYPE,
                   MALFORMED_CLAIM, MERGED, NOT_VISIBLE, LEDGER_LOST, NEAR_LIMIT)


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
# the ledger
# --------------------------------------------------------------------------

_LEDGER = re.compile(r"<!-- board-flow-ledger\n(.*?)\n-->\n?", re.DOTALL)
LAST_RUN = re.compile(r"(?m)^Last complete run: ")


@dataclass(frozen=True)
class Seen:
    """What the sweep remembers of one item: the state it saw, when it first saw
    the item in that state, and the `Turn` it last wrote (None where it has
    written none, or a thread has set the `Turn` since)."""

    state: str
    since: datetime
    turn: str | None = None


def _ledger_data(body: str | None) -> dict | None:
    """The ledger block's JSON object, or None where there is no block or it
    cannot be read."""
    m = _LEDGER.search(body or "")
    if m is None:
        return None
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def ledger_lost(body: str | None) -> bool:
    """Whether a pinned body that a run has written before no longer holds a
    readable ledger (edited, truncated, or lost). A body no run has written
    (no ledger and no `Last complete run:` line) is the first run, not a loss."""
    if _ledger_data(body) is not None:
        return False
    return bool(_LEDGER.search(body or "")) or LAST_RUN.search(body or "") is not None


def strip_ledger(body: str | None) -> str:
    """The pinned body without its ledger block: the last complete run's list."""
    return _LEDGER.sub("", body or "").strip()


def parse_ledger(body: str | None) -> dict[str, Seen]:
    """The ledger in a pinned issue's body. Absent or unreadable is empty: every
    item is then judged afresh (`judge_issue`) and aged as a first sighting."""
    out: dict[str, Seen] = {}
    for name, entry in (_ledger_data(body) or {}).items():
        since = parse_time(entry.get("d")) if isinstance(entry, dict) else None
        if since is None or not isinstance(entry.get("s"), str):
            continue
        turn = entry.get("t")
        out[name] = Seen(entry["s"], since, turn if isinstance(turn, str) else None)
    return out


def render_ledger(ledger: dict[str, Seen]) -> str:
    """The ledger as compact JSON with short keys (`s` state, `d` since, `t`
    the `Turn` last written, left out where there is none). GitHub caps a body
    at 65,536 characters, which holds about 500 entries at the longest names
    and states (measured 2026-11-15); the board held 88 open items then."""
    data = {name: ({"s": e.state, "d": stamp(e.since), "t": e.turn} if e.turn
                   else {"s": e.state, "d": stamp(e.since)})
            for name, e in sorted(ledger.items())}
    return ("<!-- board-flow-ledger\n"
            + json.dumps(data, separators=(",", ":"), sort_keys=True) + "\n-->\n")


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
    kind: str               # "type", "field", or "clear" (take a field's value off)
    name: str               # the field's name; "Type" for a type
    value: str | None = None

    @property
    def target(self) -> str:
        return f"{self.repo}#{self.number}"

    def __str__(self) -> str:
        if self.kind == "clear":
            return f"{self.target} {self.name} cleared"
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
    # The ledger's two facts about it: when its state began, and the `Turn` the
    # sweep has written (unchanged where it left a thread's `Turn` alone).
    since: datetime | None = None
    written_turn: str | None = None
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
                 board=sources, ledger: dict[str, Seen] | None = None) -> None:
        self.now = now
        self.ledger = ledger or {}
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
            lookback = profile.programme_file().integer("flow.merged_lookback_days")
            since = self.now - timedelta(days=lookback)
            self._merged[repo] = self.board.merged_since(repo, stamp(since))
        return self._merged[repo]

    def state_since(self, obs: Observed, state: str | None) -> datetime | None:
        """When the item's current state began: the ledger's word where it saw
        the item in this state, else the latest field event (a first sighting,
        or a state that has changed since). REST's timeline does not say which
        field an event was for (checked 2026-11-15), so the sweep's own `Turn`
        writes cannot be set aside: with no entry the age may be the age of the
        sweep's last `Turn` write, never older than the state."""
        seen = self.ledger.get(obs.name)
        if seen is not None and seen.state == state:
            return seen.since
        return state_start(obs)

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


def _closed_after(milestone, when: datetime | None) -> bool:
    closed = parse_time(milestone.closed_at)
    return when is not None and closed is not None and closed > when


def release_wait(obs: Observed, issue: Issue, ctx: Context,
                 entered: datetime | None = None) -> Reason | None:
    """The release an item waits on (design.md, *Hold reasons*), or None where
    it waits on none. `Deployment` waits for its own milestone; a `Release
    Check` package at `Post-deployment` waits for the next release milestone in
    its repository: the first after its own semver, or, where its own is a date
    or missing, the lowest semver milestone that is open or that closed after
    the package `entered` `Post-deployment`. While none is open the wait stays
    valid.

    `entered` is the ledger's word, else the latest field event. With no ledger
    entry that event can be the sweep's own `Turn` write, later than the real
    entry, so the first run may hold one release that closed in between: it
    under-reports, the safe direction."""
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
            later = [m for v, m in releases
                     if m.state == "open" or _closed_after(m, entered)]
        nxt = later[0] if later else None
        if nxt is None or nxt.state == "open":
            name = nxt.title if nxt else "none raised yet"
            return Reason(True, f"waiting for the next release ({name})")
        return Reason(False, f"the next release {nxt.title} has closed",
                      parse_time(nxt.closed_at))
    return None


def hold_reason(obs: Observed, issue: Issue, ctx: Context,
                entered: datetime | None = None) -> Reason:
    """Whether the item's `Hold` is valid: the first accepted reason that still
    holds, else why none does (S-G14)."""
    if issue.step == "Waiting on sender":
        return Reason(True, "waiting on the sender")
    ended = []
    release = release_wait(obs, issue, ctx, entered)
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


def missed_move(obs: Observed, issue: Issue) -> str | None:
    """The `Project State` a work package should already be in because its
    release milestone closed and nobody moved it (I5, S-G13): `Deployment` ->
    `Post-deployment`. A merge is never moved here: see `merged_naming`."""
    if not isinstance(issue, (WorkPackage, StandaloneProject)):
        return None
    if issue.step == "Deployment" and semver(obs.raw.milestone) \
            and obs.milestone_state == "closed":
        return "Post-deployment"
    return None


def merged_naming(obs: Observed, issue: Issue, ctx: Context) -> list[int]:
    """The pull requests merged within the lookback whose `Refs #N` names a
    package that is still before its merge phase (`merge.next_phase` decides
    which, by route). They are reported and the package is not moved: a merge
    may be one of several, and a person says whether this one delivered it. A
    package with an open pull request is not reported: a reopened one has a new
    branch."""
    if merge.next_phase(issue) is None or ctx.pulls_naming(obs.repo, obs.raw.number):
        return []
    return [m.number for m in ctx.merged(obs.repo)
            if obs.raw.number in refs.pull_request_names(m.title, m.body)]


# --------------------------------------------------------------------------
# judging
# --------------------------------------------------------------------------


def state_start(obs: Observed) -> datetime | None:
    """When the item's current state began, as far as REST can say: the later
    of its creation and its last field event."""
    times = [t for t in (parse_time(obs.raw.created_at), parse_time(obs.changed_at)) if t]
    return max(times) if times else None


def _development_start(obs: Observed, ctx: Context,
                       since: datetime | None) -> datetime | None:
    """`Development` is aged from the head commit of the package's open pull
    request (S-G11); with none, from when the state began."""
    for pull in ctx.pulls_naming(obs.repo, obs.raw.number):
        if pull.head_sha:
            return parse_time(ctx.commit_time(obs.repo, pull.head_sha))
    return since


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
    if issue.step == "Drafting" and not obs.draft and owes_no_review(raw.body):
        # Ready, with no reviewer asked, and its body says none is owed: its
        # author merges it on green. GitHub's own state still reads `Drafting`.
        v.state, v.owes = NO_REVIEW_OWED, "merge it on green: no review is owed"
    v.since = ctx.state_since(obs, v.state)
    v.age = None if v.since is None else ctx.now - v.since
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
    target = missed_move(obs, issue)
    if target:
        prior_release = release_wait(obs, issue, ctx, ctx.state_since(obs, issue.step))
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

    # When its state began: the move itself, else the ledger's word or the
    # latest field event, judged before this run writes anything.
    since = ctx.now if moved else ctx.state_since(obs, issue.step)
    v.since = since

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
    named = merged_naming(obs, issue, ctx)
    if named:
        prs = ", ".join(f"#{n}" for n in named)
        v.attention.append(Attention(
            MERGED, role, f"merged PR{'s' if len(named) > 1 else ''} {prs} "
                          f"name{'' if len(named) > 1 else 's'} it; move it if that merge "
                          "delivered it"))

    # What `Turn` says. A `Turn` is kept only where a thread set it: one that is
    # what the sweep last wrote (the ledger) is the sweep's to rewrite. With no
    # ledger entry nothing says who set it, so it is judged afresh: a `Hold` is
    # kept only while a Hold reason holds, an `Owner` only while an approval
    # request is pending, and any other is overwritten.
    seen = ctx.ledger.get(obs.name)
    sweep_set = cur is not None and seen is not None and cur == seen.turn
    derived = role_turn(role)
    hold_applies = (row.hold in (HOLD_ON_NAMED, HOLD_ON_SENDER)
                    or (row.hold == HOLD_ON_RELEASE
                        and (issue.step == "Deployment" or RELEASE_CHECK in raw.labels)))
    thread_hold = cur == TURN_HOLD and not sweep_set
    reason: Reason | None = None
    if hold_applies or thread_hold:
        reason = hold_reason(obs, issue, ctx, since)
        if moved and prior_release is not None and not prior_release.valid:
            reason = Reason(reason.valid, prior_release.text, reason.ended_at)
    final = derived
    if hold_applies:
        final = TURN_HOLD if reason.valid else derived
    kept = False
    if thread_hold:
        if reason.valid:
            final, kept = TURN_HOLD, True
        else:
            v.attention.append(Attention(INVALID_HOLD, role, reason.text))
    elif hold_applies and not reason.valid and (row.hold == HOLD_ON_NAMED or cur == TURN_HOLD):
        v.attention.append(Attention(INVALID_HOLD, role, reason.text))
    if cur == TURN_OWNER and not sweep_set and derived != TURN_OWNER \
            and owner_approval_pending(obs, ctx):
        final, role, kept = TURN_OWNER, ROLE_OWNER, True
    if cur != final:
        if final is None:
            # A state with no holder (a closed Ticket): never write a null, take
            # the value off.
            v.writes.append(Write(obs.repo, raw.number, "clear", TURN))
        else:
            v.writes.append(Write(obs.repo, raw.number, "field", TURN, final))
    v.written_turn = (seen.turn if seen else None) if kept else final
    # The owner has a part in a state only while he has something to do in it:
    # his own sources (`turn.waiting_on_owner`) say so, not the state alone.
    parts = tuple(p for p in row.parts if p[0] != ROLE_OWNER or waiting_on_owner(issue))
    v.role, v.turn, v.owes, v.parts = role, final, row.owes, parts
    if role != row.role and role == ROLE_OWNER:
        v.owes = "approve, or answer, as the latest comment asks"

    # How long it has sat.
    v.bound = row.bound
    start = since
    if issue.step == "Development":
        start = _development_start(obs, ctx, since)
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
    elif issue.step == "On Hold" and typ == "Requirement":
        _on_hold(v, obs, ctx)
    else:
        _stall(v)
    return v


def _resting(v: Verdict, row: Flow, resting_parent: bool) -> str | None:
    if resting_parent:
        return "waiting on its work packages"
    if v.turn == TURN_HOLD and not row.stalls_under_hold:
        return "held"
    return None


def _on_hold(v: Verdict, obs: Observed, ctx: Context) -> None:
    """A Requirement at `On Hold` is bound by its review date (design.md,
    Requirement table): past it, it is stalled for its role, even while a linked
    issue is still open. With no date named it rests until its reason ends."""
    due = _review_due(section(obs.raw.body, DEPENDENCIES_HEADING))
    if due is None:
        _stall(v)
        return
    v.bound, v.bound_text = None, f"until {due}"
    v.stalled = ctx.today > due


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
    prior: dict[str, Seen] = field(default_factory=dict)   # the ledger as read
    open_names: set[str] = field(default_factory=set)      # every item still open
    attempted: bool = False                                # `perform` has run
    notices: list[Attention] = field(default_factory=list)  # findings about the run itself

    @property
    def ledger(self) -> dict[str, Seen]:
        """The ledger to publish: every judged item, with the state it is in and
        when that began, as far as the writes actually made reach.

        * An item whose `Turn` write was not made keeps the `Turn` the ledger
          last held for it (the board still holds the old one).
        * An item whose type or state write was not made keeps its prior entry,
          or none: what the board holds is not what was judged.
        * An item not judged this run (not visible, an unknown type or state, a
          read that failed) keeps its prior entry while it is still open."""
        made = set(self.made) if self.attempted else None
        out: dict[str, Seen] = {}
        for v in self.verdicts:
            if not (v.state and v.since):
                continue
            prior = self.prior.get(v.name)
            undone = [] if made is None else [w for w in v.writes if w not in made]
            if any(w.name != TURN for w in undone):
                continue
            turn = (prior.turn if prior else None) if undone else v.written_turn
            out[v.name] = Seen(v.state, v.since, turn)
        for name, entry in self.prior.items():
            if name in self.open_names and name not in out:
                out[name] = entry
        return out

    @property
    def stalled(self) -> list[Verdict]:
        return [v for v in self.verdicts if v.stalled]

    @property
    def attention(self) -> list[tuple[Verdict, Attention]]:
        found = [(v, a) for v in self.verdicts for a in v.attention]
        if self.pinned is not None:
            found += [(Verdict(self.pinned), a) for a in self.notices]
        return found


def programme_repository() -> str:
    return profile.programme_file().string("programme.repository")


def find_pinned(observed: Sequence[Observed]) -> Observed | None:
    for o in observed:
        if (o.repo == programme_repository() and not o.pull
                and o.raw.title == STALLED_LIST_TITLE):
            return o
    return None


def field_ids(observed: Sequence[Observed]) -> dict[str, int]:
    """Each field's id: the programme file's `[flow.field_ids]` where it holds
    one, else the id some issue carries a value of the field under."""
    learned: dict[str, int] = {}
    for o in observed:
        learned.update(o.field_ids)
    ids = dict(learned)
    ids.update(profile.programme_file().table("flow.field_ids"))
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
        raise Refusal(f"there is no open issue titled {STALLED_LIST_TITLE!r} in "
                      f"{programme_repository()}: create it by hand, then run again")
    items = [o for o in observed if o is not pinned]
    prior = parse_ledger(pinned.raw.body) if pinned is not None else {}
    ctx = Context(observed, now, board, prior)
    sweep = Sweep([], pinned, now=now, prior=prior, open_names={o.name for o in items})
    if pinned is not None and ledger_lost(pinned.raw.body):
        sweep.notices.append(Attention(
            LEDGER_LOST, ROLE_OWNER,
            "the pinned body has no readable ledger: every Turn was judged afresh and "
            "ages fell back to field events"))
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
    sweep.attempted = True
    for v in sweep.verdicts:
        for w in v.writes:
            try:
                if w.kind == "type":
                    board.set_issue_type(w.repo, w.number, w.value)
                else:
                    fid = ids.get(w.name)
                    if fid is None:
                        raise Unavailable(f"no id is known for the issue field {w.name!r}: set it "
                                          "under [flow.field_ids] in config/programme.toml")
                    if w.kind == "clear":
                        board.clear_issue_field(w.repo, w.number, fid)
                    else:
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


def render(sweep: Sweep, room: int | None = None) -> str:
    """The stalled list: what the pinned issue's body holds and the run prints.
    Given `room` (characters), it leaves out the last items, stalled ones before
    findings, until it fits, and says how many."""
    head = [f"Last complete run: {stamp(sweep.now)}", ""]
    stalled = stalled_by_role(sweep)
    attention = attention_by_role(sweep)
    if not stalled and not attention:
        return "\n".join(head + ["Nothing is stalled."]) + "\n"
    out = list(head)
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
    if room is not None and len("\n".join(out)) + 1 > room:
        out = _fit(out, room)
    return "\n".join(out) + "\n"


def _fit(lines: list[str], room: int) -> list[str]:
    """`lines` without the last items that do not fit `room`, with a line saying
    how many were left out. Stalled items go before findings, the last first;
    the finding that the body is near its limit is never left out."""
    marker = f": {NEAR_LIMIT}: "
    items = [i for i, text in enumerate(lines) if text.startswith("- ") and marker not in text]
    attention_at = next((i for i, text in enumerate(lines) if text == "## Needs a look"),
                        len(lines))
    droppable = ([i for i in items if i < attention_at][::-1]
                 + [i for i in items if i >= attention_at][::-1])
    gone: set[int] = set()
    note = "Items left out to keep this body within GitHub's limit: {}"
    size = len("\n".join(lines)) + 1
    for i in droppable:
        if size + len(note.format(len(items))) + 1 <= room:
            break
        size -= len(lines[i]) + 1
        gone.add(i)
    kept = [text for i, text in enumerate(lines) if i not in gone]
    kept.insert(2, note.format(len(gone)))
    return kept


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
        say(f"would rewrite {sweep.pinned.name} ({STALLED_LIST_TITLE})")
    else:
        perform(sweep, board)
        for w in sweep.made:
            say(f"wrote {w}")

    if sweep.failures:
        complain("board-flow: the run did not finish:")
        for failure in sweep.failures:
            complain(f"  {failure}")
        # The writes that were made are the ledger's to record; the list stays the
        # last complete run's.
        if not dry_run:
            kept = strip_ledger(sweep.pinned.raw.body)
            sweep.body = (kept + "\n\n" if kept else "") + render_ledger(sweep.ledger)
            try:
                board.rewrite_body(sweep.pinned.repo, sweep.pinned.raw.number, sweep.body)
            except Unavailable as exc:
                complain(f"board-flow: could not record the ledger in {sweep.pinned.name}: {exc}")
            else:
                complain("the stalled list was not rewritten, so it still names the last "
                         "complete run; the ledger records the writes made")
        say(render(sweep))
        return EXIT_FAILED

    ledger = render_ledger(sweep.ledger)
    text = render(sweep)
    if len(text) + 1 + len(ledger) > BODY_LIMIT:
        sweep.notices.append(Attention(
            NEAR_LIMIT, ROLE_OWNER,
            f"the body would be {len(text) + 1 + len(ledger)} characters of the "
            f"{BODY_LIMIT} kept under GitHub's limit: the stalled list is cut, the ledger is not"))
        text = render(sweep, room=BODY_LIMIT - len(ledger) - 1)
    sweep.body = text + "\n" + ledger
    if not dry_run:
        try:
            board.rewrite_body(sweep.pinned.repo, sweep.pinned.raw.number, sweep.body)
        except Unavailable as exc:
            complain(f"board-flow: could not rewrite {sweep.pinned.name}: {exc}")
            say(render(sweep))
            return EXIT_FAILED
    say(render(sweep))
    return EXIT_STALLED if (sweep.stalled or sweep.attention) else EXIT_CLEAN
