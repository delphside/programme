"""The board's issues, as one class per type.

Designed in `programme/records/2.5-changes/programme-tooling/383-one-board-model/`.
The rule this exists to enforce: **a fact is derived in exactly one place, is
named there, and every consumer imports it.** Nine scripts each re-derive the
same few concepts today, and the cost is not duplication but disagreement —
two pictures of "is this built" disagreed about parentage (#370, #375), and
two of "does this owe a route" disagreed about parents (#297).

No I/O happens here. `sources.py` fetches; this interprets.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Iterator, Mapping, Sequence

from . import vocabulary
from .vocabulary import (  # noqa: F401  (some are only re-exported: callers import them from here)
    APPLICATION_TOOLING, CLAIMED_BY, DECISION_STATE, DEC_ACTIONED,
    DEC_ASKED, DEC_DECIDED, DEC_FEEDBACK, DEC_SIGN_OFF,
    DEPRECATED_REPOSITORY, FORMER_APPLICATION_TOOLING,
    FORMER_PROGRAMME_TOOLING, OTHER, PROGRAMME_TOOLING, PROJECT_STATE,
    PROJ_CLOSEDOWN, PROJ_DEPLOYMENT, PROJ_DESIGN, PROJ_DEVELOPMENT,
    PROJ_POST_DEPLOYMENT, PROJ_Q1, PROJ_Q2, PROJ_Q3, PROJ_SCOPE,
    PROJ_USER_TESTING, PR_APPROVED, PR_AWAITING_REVIEW,
    PR_CHANGES_REQUESTED, PR_DRAFTING, PR_STATE, RELEASE, RELEASE_CHECK,
    REQUIREMENT_STATE, REQ_CANDIDATE_1, REQ_CANDIDATE_2, REQ_CANDIDATE_3,
    REQ_ON_HOLD, REQ_READY, REQ_SCOPE, REQ_TRIAGE, ROUTE, TICKET_STATE,
    TKT_CLOSED, TKT_IN_PROGRESS, TKT_NEW, TKT_PENDING, TKT_REFUSED,
    TKT_RESOLVED, TKT_WAITING_ON_SENDER, TURN, TURNS, TURN_CLAUDE,
    TURN_HOLD, TURN_OWNER, TYPE_DECISION, TYPE_PROJECT, TYPE_PULL_REQUEST,
    TYPE_REQUIREMENT, TYPE_TICKET, WORKSTREAM)

# --------------------------------------------------------------------------
# what a source hands over
# --------------------------------------------------------------------------


OWNER, CLAUDE = "owner", "Claude"

# `- [ ] **owner** — run the six browser tests`
#
# Owner, 2026-09-18: *"Label Checkboxes consistently as Claude or owner so the
# tools can differentiate."* Before this, every box looked alike, so nothing
# could tell a task waiting on the owner from one waiting on Claude -- which is
# why R1 could not derive its fourth source and said so under every run.
#
# The label is on the box, not inferred from the heading it sits under: a box
# moved to another section keeps its owner, and a reader sees whose it is
# without scrolling up.
_BOX = re.compile(
    r"^[ \t]*[-*][ \t]*\[([ xX])\][ \t]*"
    r"(?:\*\*(owner|Claude)\*\*[ \t]*[\u2014\u2013-][ \t]*)?"
    r"(.*)$",
    re.M | re.IGNORECASE)


# `**Next review due:** 2026-12-21 — **Claude**`
#
# **A recurrence, and the only state it keeps is the date.** #291 R2: the
# capacity plan is reviewed on a recurrence rather than when somebody
# remembers. A job a machine runs is a scheduled job and belongs to #400; a
# review two people do is this, because it has to reach a person and wait for
# them. Owner, 2026-09-21: *"Reviewing the capacity plan requires Claude to
# update and Steve to review, so an issue date makes more sense."*
#
# Doing the review moves the date on, which is what makes it recur. There is
# no store, no last-run file and nothing to reconcile -- the same reasoning
# #166 gives for the scheduler: rederive, and a restart is automatically
# correct.
#
# Labelled like a checkbox and for the same reason: the label is on the line,
# so a reader sees whose it is without scrolling up, and an unlabelled one is
# waiting on nobody.
_DUE = re.compile(
    r"^[ \t]*\**[ \t]*Next[ \t]+[^:\n]{0,40}?due[ \t]*\**[ \t]*:?[ \t]*\**[ \t]*"
    r"(\d{4}-\d{2}-\d{2})"
    r"(?:[^\n]*?\*\*(owner|Claude)\*\*)?",
    re.M | re.IGNORECASE)


def section(body: str, heading: str) -> str:
    """The text under a markdown heading of any level, up to the next heading
    of the same or a higher level; empty if there is none."""
    lines = (body or "").splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^(#{1,6})\s+(.*?)\s*$", line)
        if m and m.group(2).lower() == heading.lower():
            level, out = len(m.group(1)), []
            for rest in lines[i + 1:]:
                n = re.match(r"^(#{1,6})\s", rest)
                if n and len(n.group(1)) <= level:
                    break
                out.append(rest)
            return "\n".join(out).strip()
    return ""


def none_owed(text: str) -> bool:
    """Whether a record's text opens with `None owed`."""
    return text.strip().lstrip("-* ").lower().startswith("none owed")


_REVIEW_HEADING = re.compile(r"^(#{1,6})\s+Review\b(?!\s+rounds)", re.IGNORECASE)


def owes_no_review(body: str | None) -> bool:
    """Whether a pull request's body says the owner's review is not owed: a
    `Review` section (any heading level; not *Review rounds*, which records agent
    rounds) opening `No review owed`, optionally after `- ` (docs/1.1). HTML
    comments are skipped, so a template's guidance comment left in place does
    not hide the line. Nothing else says it."""
    lines = re.sub(r"<!--.*?-->", "", body or "", flags=re.DOTALL).splitlines()
    for i, line in enumerate(lines):
        m = _REVIEW_HEADING.match(line)
        if not m:
            continue
        for rest in lines[i + 1:]:
            n = re.match(r"^(#{1,6})\s", rest)
            if n and len(n.group(1)) <= len(m.group(1)):
                break
            if rest.strip():
                if rest.strip().lstrip("-").strip().lower().startswith("no review owed"):
                    return True
                break
    return False


@dataclass(frozen=True)
class Recurring:
    """Something that falls due again every time it is done."""

    due: date
    who: str | None
    text: str

    def overdue_by(self, today: date) -> int:
        """Days past due. Negative means it has not come round yet."""
        return (today - self.due).days


@dataclass(frozen=True)
class Box:
    """One checkbox, and whose move it is."""

    ticked: bool
    who: str | None
    text: str


@dataclass(frozen=True)
class RawSubIssue:
    number: int
    issue_type: str | None


@dataclass(frozen=True)
class RawIssue:
    """Exactly what GitHub returned, uninterpreted."""

    number: int
    title: str
    state: str
    body: str
    issue_type: str | None
    fields: Mapping[str, str]
    sub_issues: Sequence[RawSubIssue]
    parent: int | None
    milestone: str | None
    labels: frozenset[str]
    # GitHub's own issue dependencies. The board cannot show them, which is
    # why the roadmap diagram exists — owner, 2026-09-18.
    blocked_by: frozenset[int] = frozenset()
    blocks: frozenset[int] = frozenset()
    # Reports ask "for how long"; gates only ask "is it true now". These are
    # the cheapest answer GitHub gives, and `updated_at` is last activity of
    # any kind -- NOT when the field reached its current value. R1 says so
    # rather than implying a precision it does not have.
    created_at: str | None = None
    updated_at: str | None = None
    # Needed by R2, which asks what *changed* in a window: an issue closed in
    # silence produces no comment at all, so a comment listing never reveals it.
    closed_at: str | None = None
    # A pull request's branch. None for an issue.
    head_ref: str | None = None
    # Dependencies on issues in another repository, as (owner/repo, number,
    # title). Kept apart from `blocked_by` and `blocks`, whose numbers are this
    # repository's: a programme project waits on applications' issues, and a
    # bare number there named the wrong issue.
    blocked_by_elsewhere: frozenset[tuple[str, int, str]] = frozenset()
    blocks_elsewhere: frozenset[tuple[str, int, str]] = frozenset()
    # A pull request a bot opened (Dependabot's), which can carry no `Refs`:
    # GitHub's author type, `Bot`. False for an issue.
    bot: bool = False


@dataclass(frozen=True)
class RawPullRequest:
    """A pull request as the `PR State` writer reads it, in any state.

    Separate from `RawIssue` because the writer needs what the snapshot does
    not carry: the node id an add takes, and how many reviews were given.
    """

    number: int
    node_id: str
    state: str              # OPEN, MERGED or CLOSED
    draft: bool
    review: str | None      # `reviewDecision`; None when nobody has decided
    reviewers: int          # reviews requested and not yet given
    reviews: int            # reviews given
    body: str = ""          # for whether its review is owed


@dataclass(frozen=True)
class RawBoardItem:
    """A pull request's item on the project board, and its `PR State`."""

    number: int
    item_id: str
    pr_state: str | None    # None when the field is unset


@dataclass(frozen=True)
class OpenItem:
    """An open issue or pull request in any of the organisation's repositories,
    and whether the board holds it (`board-add.py`)."""

    repo: str
    kind: str               # "issue" or "pull request"
    number: int
    node_id: str
    on_board: bool

    @property
    def name(self) -> str:
        return f"{self.repo}#{self.number}"


@dataclass(frozen=True)
class Link:
    """An issue another is blocked by, as GitHub's dependency link gives it."""

    repo: str               # owner/name
    number: int
    state: str              # open or closed


@dataclass(frozen=True)
class Comment:
    author: str
    created_at: str
    body: str


@dataclass(frozen=True)
class Milestone:
    title: str
    state: str              # open or closed
    closed_at: str | None


@dataclass(frozen=True)
class MergedPull:
    """A pull request that merged, for the `Refs #N` it carries."""

    number: int
    title: str
    body: str
    merged_at: str


@dataclass(frozen=True)
class Observed:
    """An open issue or pull request as the daily sweep reads it over REST
    (`sources.observe`), with what the flow table's judgements need beside it.

    `fields` (on `raw`) holds the single-selects and the text fields alike, by
    name. `changed_at` is when the item last moved in a way that restarts its
    clock: REST's timeline names neither the field nor the value of a field
    event, so it is the latest field event of any field (and for a pull request
    the latest review event)."""

    repo: str               # owner/name
    raw: RawIssue
    pull: bool = False
    fields_visible: bool = True
    field_ids: Mapping[str, int] = field(default_factory=dict)
    changed_at: str | None = None
    links: tuple[Link, ...] = ()
    open_packages: int = 0
    milestone_state: str | None = None
    head_sha: str | None = None
    draft: bool = False

    @property
    def name(self) -> str:
        return f"{self.repo}#{self.raw.number}"


# The field and option names are in `vocabulary.py`, once; imported at the top
# of this file.

# Issues may carry the old Route names until the field's options are renamed in
# GitHub, so both are read.
FORMER_NAMES = {
    FORMER_APPLICATION_TOOLING: APPLICATION_TOOLING,
    FORMER_PROGRAMME_TOOLING: PROGRAMME_TOOLING,
}


def route_of(value: str | None) -> str | None:
    """The route a Route field value names, reading a former name as its new one."""
    return FORMER_NAMES.get(value or "", value)

def delivered_by_merge(route: str | None) -> bool:
    """Is a change on this route delivered when it merges into main?

    Both repository routes are: nothing deploys them. A Production Release
    waits for its deploy, and Other is applied by hand.
    """
    return route_of(route) in (APPLICATION_TOOLING, PROGRAMME_TOOLING) or (
        route or "").startswith(DEPRECATED_REPOSITORY)


# --------------------------------------------------------------------------
# the issues
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Issue:
    """What every issue has. `step` is what the obligations grid is indexed by."""

    raw: RawIssue
    type_was_defaulted: bool = False
    stage_was_defaulted: bool = False

    # -- identity ----------------------------------------------------------
    @property
    def number(self) -> int:
        return self.raw.number

    @property
    def title(self) -> str:
        return self.raw.title

    @property
    def state(self) -> str:
        return self.raw.state

    @property
    def body(self) -> str:
        return self.raw.body or ""

    @property
    def kind(self) -> str:
        return type(self).__name__

    # -- fields, always by name --------------------------------------------
    def field(self, name: str) -> str | None:
        """A field's value by NAME. Option ids never leave `sources.py`."""
        return self.raw.fields.get(name)

    @property
    def step(self) -> str | None:
        """The lifecycle step this issue is at. Overridden per type."""
        return None

    @property
    def step_field(self) -> str:
        return "-"

    # -- body reading ------------------------------------------------------
    def has_heading(self, text: str) -> bool:
        """A markdown heading whose text matches, at any level.

        Matched case-insensitively and ignoring trailing punctuation, because
        `## Test approach` and `## Test Approach:` are the same heading to a
        reader and differ only to a grep.
        """
        wanted = text.strip().lower().rstrip(":")
        for line in self.body.splitlines():
            if not line.lstrip().startswith("#"):
                continue
            got = line.lstrip("#").strip().lower().rstrip(":")
            if got == wanted or got.startswith(wanted + " "):
                return True
        return False

    def section(self, heading: str) -> str:
        """The text under a heading, including its subheadings.

        Stops at the next heading of the SAME OR HIGHER level, not at the next
        heading of any level. The documented shape of a test approach is
        `## Test approach` with `### Functional user tests` and
        `### Technical tests` beneath it, so stopping at any heading reported
        a fully written section as empty — #363 read as having no test
        approach when it has one under its subheadings.
        """
        wanted = heading.strip().lower().rstrip(":")
        out: list[str] = []
        depth: int | None = None
        for line in self.body.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("#"):
                level = len(stripped) - len(stripped.lstrip("#"))
                got = stripped.lstrip("#").strip().lower().rstrip(":")
                if depth is not None:
                    if level <= depth:
                        break
                    out.append(line)          # a subheading is part of it
                    continue
                if got == wanted or got.startswith(wanted + " "):
                    depth = level
                continue
            if depth is not None:
                out.append(line)
        return "\n".join(out).strip()

    # -- checkboxes --------------------------------------------------------
    @property
    def boxes(self) -> list[Box]:
        out = []
        for mark, who, text in _BOX.findall(self.body):
            label = None
            if who:
                label = OWNER if who.lower() == "owner" else CLAUDE
            out.append(Box(mark.lower() == "x", label, text.strip()))
        return out

    @property
    def recurrences(self) -> list[Recurring]:
        out = []
        for line in self.body.splitlines():
            m = _DUE.search(line)
            if not m:
                continue
            try:
                when = date.fromisoformat(m.group(1))
            except ValueError:
                # A date-shaped string that is not a date -- 2026-13-40. Not a
                # recurrence, and not worth failing a report over.
                continue
            who = m.group(2)
            label = None
            if who:
                label = OWNER if who.lower() == "owner" else CLAUDE
            # Asterisks stripped throughout, not just at the ends: the label
            # sits mid-line, so `.strip("*")` leaves `review due:** 2026-…`.
            out.append(Recurring(when, label,
                                 line.replace("*", "").strip(" -\u2014\t")))
        return out

    def boxes_in(self, heading: str) -> list[Box]:
        section = Issue(RawIssue(0, "", "", self.section(heading), None, {},
                                 (), None, None, frozenset()))
        return section.boxes

    def unticked_for(self, who: str) -> list[Box]:
        return [b for b in self.boxes if not b.ticked and b.who == who]

    @property
    def unlabelled_boxes(self) -> list[Box]:
        """Boxes that say nothing about whose move it is.

        Reported rather than assumed: guessing from the heading would be the
        same inference the label exists to replace, and a box nobody owns is
        how work waits on nobody at all.
        """
        return [b for b in self.boxes if b.who is None]

    @property
    def unticked_boxes(self) -> int:
        """Unticked boxes anywhere in the body.

        Only correct where the obligation really is about the whole issue —
        closedown, which owes no unticked boxes at all. For anything scoped to
        a section use `unticked_in`: counting globally made #252 report its
        post-deployment checks as unanswered when they were answered and its
        *test approach* boxes were the unticked ones. Naming the wrong thing
        to fix is the defect this model exists to stop.
        """
        return len(re.findall(r"^\s*[-*]\s*\[ \]", self.body, re.M))

    def unticked_in(self, heading: str) -> int:
        return len(re.findall(r"^\s*[-*]\s*\[ \]", self.section(heading), re.M))

    def unanswered_rows_in(self, heading: str) -> int:
        """Table rows under a heading whose last cell is empty.

        **Post-deployment checks are a table, not a checklist**, so counting
        boxes says a section full of blank answers is complete. #374 reported
        `complete, 0 not checked` on 2026-09-19 with R1 and R2 both unanswered;
        the rule that caught it (#346 R4) did not survive `check-transitions.sh`
        retiring into this model.

        **Empty, rather than not one of `passed`/`cannot be tested`/`failed`.**
        The bash rule required those three words and so flagged rows carrying a
        considered answer in other words. A blank cell is unambiguous; judging
        prose is a person's job, and a check that cries wolf gets ignored rather
        than fixed.
        """
        rows = 0
        seen_header = False
        for line in self.section(heading).splitlines():
            stripped = line.strip()
            if not stripped.startswith("|"):
                continue
            if re.match(r"^\|[\s:-]+\|", stripped):      # the --- separator
                continue
            if not seen_header:                            # the header row
                seen_header = True
                continue
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if cells and not cells[-1]:
                rows += 1
        return rows

    def ticked_in(self, heading: str) -> int:
        return len(re.findall(r"^\s*[-*]\s*\[[xX]\]", self.section(heading), re.M))

    @property
    def ticked_boxes(self) -> int:
        return len(re.findall(r"^\s*[-*]\s*\[[xX]\]", self.body, re.M))

    # -- shape -------------------------------------------------------------
    @property
    def sub_issues(self) -> Sequence[RawSubIssue]:
        return self.raw.sub_issues

    @property
    def parent(self) -> int | None:
        return self.raw.parent

    @property
    def labels(self) -> frozenset[str]:
        return self.raw.labels

    # -- sequencing --------------------------------------------------------
    @property
    def blocked_by(self) -> frozenset[int]:
        """What must finish first, as GitHub records it.

        The project board has no column for this, so it is invisible until
        something draws it: `programme/scripts/board/roadmap-diagram.py` is that something.
        """
        return self.raw.blocked_by

    @property
    def blocks(self) -> frozenset[int]:
        return self.raw.blocks

    # -- age ---------------------------------------------------------------
    @property
    def quiet_days(self) -> float | None:
        """Days since anything at all happened on this issue.

        A floor on how long something has been waiting, not a measure of it:
        a comment that changed nothing resets it. Named `quiet_days` rather
        than `waiting_days` so no consumer can read it as the latter.
        """
        if not self.raw.updated_at:
            return None
        stamp = datetime.fromisoformat(self.raw.updated_at.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - stamp).total_seconds() / 86400


@dataclass(frozen=True)
class Requirement(Issue):
    """A request for a change. Its journey is `Stage`."""

    @property
    def step(self) -> str | None:
        # Owner, 2026-09-18: an unset Stage is Triage. A row every rule skips
        # is a row nothing enforces, which is the untyped defect (#361) in
        # different clothes.
        return self.field(REQUIREMENT_STATE) or REQ_TRIAGE

    @property
    def step_field(self) -> str:
        return REQUIREMENT_STATE

    @property
    def stage_to_record(self) -> str | None:
        """The Stage to write onto the issue, or None when there is nothing to write.

        The default `step` reads, made a fact on the board, so a view filtered
        by Stage shows a new requirement instead of hiding it. Typed
        requirements only. Owner, 2026-09-29: *"yes for a Requirement Issue.
        Other issue types use different lifecycle fields"*, and an untyped
        issue may yet become one of those.
        """
        if self.stage_was_defaulted and not self.type_was_defaulted:
            return self.step
        return None


@dataclass(frozen=True)
class Project(Issue):
    """A bounded piece of work. Its journey is `Phase`."""

    @property
    def step(self) -> str | None:
        return self.field(PROJECT_STATE)

    @property
    def step_field(self) -> str:
        return PROJECT_STATE


@dataclass(frozen=True)
class ParentProject(Project):
    """Owns requirements, design and documents. Makes no delivery itself.

    Carries no Route and no milestone: both answer how a change reaches its
    users, and a parent has no delivery role. Its work packages carry a Route
    each, and a milestone where their delivery has one. See #297 — a report asked a parent for a route and named the wrong
    thing to fix, and two parents were given one to silence it.
    """

    @property
    def work_packages(self) -> list[int]:
        return [s.number for s in self.sub_issues if s.issue_type == TYPE_PROJECT]

    @property
    def folded_requirements(self) -> list[int]:
        return [s.number for s in self.sub_issues if s.issue_type == TYPE_REQUIREMENT]


@dataclass(frozen=True)
class WorkPackage(Project):
    """One delivery of a parent project. Carries a Route, and a milestone where
    its delivery has one."""

    @property
    def route(self) -> str | None:
        return self.field(ROUTE)

    @property
    def milestone(self) -> str | None:
        return self.raw.milestone


@dataclass(frozen=True)
class StandaloneProject(Project):
    """One delivery, with no work packages under it. Carries both, the milestone where its delivery has one."""

    @property
    def route(self) -> str | None:
        return self.field(ROUTE)

    @property
    def milestone(self) -> str | None:
        return self.raw.milestone


# --------------------------------------------------------------------------
# the flow table: who holds an item in each state, and for how long
# --------------------------------------------------------------------------
#
# Designed in `programme/records/2.5-changes/process-definition/176-project-board-flow/`
# (design.md's tables; implementation.md §1). **One table, read by every
# caller** (R3): the sweep (`flow.py`), the role lists, the owner's list and
# `turn.py`'s waits. The bounds live here and nowhere else in code. It holds the
# generalisation of what `DECISION_TURNS` held for Decisions alone.
#
# `role` is the one holder (R1): the mover of the move the state owes or, where
# the item rests, whoever reviews the wait. `parts` are the other actors with a
# part in the state, who see the item on their own lists. `turn` is the `Turn`
# the state implies; `bound` is the days an item may sit in the state before
# somebody is told, None where it has none.

ROLE_OWNER = "owner"
ROLE_DESIGN = "design-authority"
ROLE_TECHNICAL = "technical-lead"
ROLE_DEMAND = "demand-manager"
ROLE_TEST = "test-manager"
ROLE_RELEASE = "release-manager"
ROLE_ENVIRONMENTS = "environments-manager"
ROLE_LIBRARIAN = "librarian"
ROLE_SECURITY = "security"
# Every role of docs/1.7, as a lower-case hyphenated slug, even where the flow
# table gives a role nothing yet.
ROLES = (ROLE_OWNER, ROLE_DESIGN, ROLE_TECHNICAL, ROLE_DEMAND, ROLE_RELEASE,
         ROLE_ENVIRONMENTS, ROLE_TEST, ROLE_LIBRARIAN, ROLE_SECURITY)
# The author of a pull request holds its states but is no role: docs/1.2 §2.24
# says it means the pull request's author, and `--role author` lists the pull
# requests a thread opened.
ROLE_AUTHOR = "author"
HOLDERS = ROLES + (ROLE_AUTHOR,)


# Owner, 2026-11-13: 7 days for every state where the owner or a thread owes a
# move, a day for triage, none for a queue.
TRIAGE_DAYS = 1
OWED_DAYS = 7
# A delivery at Post-deployment owes a review after this long, and is stalled
# when it is the same again overdue.
REVIEW_DUE_DAYS = 7
POST_DEPLOYMENT_DAYS = REVIEW_DUE_DAYS + OWED_DAYS

# Why a `Hold` is valid, by the kind of wait a state makes (design.md, *Hold
# reasons*). A state with no kind accepts a thread-set `Hold` on any reason.
HOLD_ON_RELEASE = "release"
HOLD_ON_SENDER = "sender"
HOLD_ON_NAMED = "named"


@dataclass(frozen=True)
class Flow:
    """One row of the flow table."""

    role: str | None
    turn: str | None
    bound: float | None
    owes: str
    leaves_on: str
    parts: tuple[tuple[str, str], ...] = ()
    # The wait this state makes, where it is a wait: it derives `Turn` = `Hold`
    # while its reason holds.
    hold: str | None = None
    # A Ticket's sender is the reason for `Hold`, and the hold stalls under the
    # owner after the bound (design.md, Hold reasons).
    stalls_under_hold: bool = False


def _row(role, turn, bound, owes, leaves_on, **kw) -> Flow:
    return Flow(role, turn, bound, owes, leaves_on, **kw)


REQUIREMENT_FLOW: dict[str, Flow] = {
    REQ_TRIAGE: _row(ROLE_DESIGN, TURN_CLAUDE, TRIAGE_DAYS,
                   "the minimum fields, then an outcome",
                   "the thread's action, at raising (R10)"),
    REQ_SCOPE: _row(
        ROLE_DESIGN, TURN_CLAUDE, OWED_DAYS,
        "options, dependencies, a recommendation", "the thread's action"),
    REQ_ON_HOLD: _row(ROLE_DESIGN, TURN_HOLD, None,
                    "none: resting",
                    "the named event, or the issue it waits on closing",
                    hold=HOLD_ON_NAMED),
    REQ_READY: _row(ROLE_DEMAND, TURN_CLAUDE, None,
                              "a slot at planning",
                              "board-sweep planning; the owner agrees"),
    REQ_CANDIDATE_1: _row(ROLE_DEMAND, TURN_CLAUDE, OWED_DAYS,
                                "raise the project, since it is next",
                                "board-sweep planning"),
    REQ_CANDIDATE_2: _row(ROLE_DEMAND, TURN_CLAUDE, None,
                                "a slot at planning", "board-sweep planning"),
    REQ_CANDIDATE_3: _row(ROLE_DEMAND, TURN_CLAUDE, None,
                                "a slot at planning", "board-sweep planning"),
}

PROJECT_FLOW: dict[str, Flow] = {
    PROJ_SCOPE: _row(ROLE_DESIGN, TURN_CLAUDE, OWED_DAYS,
                  "what the project does", "its action; the owner agrees the next move"),
    PROJ_Q3: _row(ROLE_DEMAND, TURN_CLAUDE, None, "a place in the queue",
               "board-sweep planning"),
    PROJ_Q2: _row(ROLE_DEMAND, TURN_CLAUDE, None, "a place in the queue",
               "board-sweep planning"),
    PROJ_Q1: _row(ROLE_DEMAND, TURN_CLAUDE, None, "to be pulled into design",
               "board-sweep planning"),
    PROJ_DESIGN: _row(
        ROLE_DESIGN, TURN_CLAUDE, OWED_DAYS,
        "the design, and the test approach",
        "design done and test approach approved",
        parts=((ROLE_TEST, "approve the test approach"),
               (ROLE_OWNER, "answer the Design boxes"))),
    PROJ_DEVELOPMENT: _row(ROLE_TECHNICAL, TURN_CLAUDE, OWED_DAYS,
                        "the change on its branch", "first test deploy, or merge"),
    PROJ_USER_TESTING: _row(ROLE_TECHNICAL, TURN_CLAUDE, OWED_DAYS,
                         "the branch tip deployed and tested", "tests ticked",
                         parts=((ROLE_OWNER, "run the browser tests"),)),
    PROJ_DEPLOYMENT: _row(ROLE_TECHNICAL, TURN_HOLD, None,
                       "the release it waits for", "the deploy",
                       parts=((ROLE_RELEASE, "make the release"),),
                       hold=HOLD_ON_RELEASE),
    PROJ_POST_DEPLOYMENT: _row(ROLE_TECHNICAL, TURN_CLAUDE, POST_DEPLOYMENT_DAYS,
                            "the post-deployment review, due after "
                            f"{REVIEW_DUE_DAYS} days", "the review",
                            hold=HOLD_ON_RELEASE),
    PROJ_CLOSEDOWN: _row(ROLE_TECHNICAL, TURN_CLAUDE, OWED_DAYS,
                              "the lessons written", "lessons written, closed"),
}

DECISION_FLOW: dict[str, Flow] = {
    DEC_ASKED: _row(ROLE_OWNER, TURN_OWNER, OWED_DAYS, "answer the question",
                  "the owner answers"),
    DEC_FEEDBACK: _row(ROLE_DESIGN, TURN_CLAUDE, OWED_DAYS,
                              "write the decision down", "Claude writes it down"),
    DEC_SIGN_OFF: _row(
        ROLE_OWNER, TURN_OWNER, OWED_DAYS, "read the decision and sign it off",
        "the owner signs off"),
    DEC_DECIDED: _row(ROLE_DESIGN, TURN_CLAUDE, OWED_DAYS, "apply the decision",
                    "Claude applies it"),
    DEC_ACTIONED: _row(ROLE_OWNER, TURN_OWNER, OWED_DAYS,
                     "read the outcome, and close it", "the owner closes it"),
}

# Derived from GitHub's own state by `board-pr-state.py`, never typed. Awaiting
# review is the owner's; every other state is its author's (design.md).
PULL_REQUEST_FLOW: dict[str, Flow] = {
    PR_DRAFTING: _row(ROLE_AUTHOR, TURN_CLAUDE, OWED_DAYS,
                     "finish the draft, then ask for review", "ready for review"),
    PR_AWAITING_REVIEW: _row(ROLE_OWNER, TURN_OWNER, OWED_DAYS,
                            "review: approve or request changes", "the review"),
    PR_CHANGES_REQUESTED: _row(ROLE_AUTHOR, TURN_CLAUDE, OWED_DAYS,
                              "make the changes, then re-request the review",
                              "re-requested"),
    PR_APPROVED: _row(ROLE_AUTHOR, TURN_CLAUDE, OWED_DAYS,
                     "approved — mine to merge", "the merge"),
}

TICKET_FLOW: dict[str, Flow] = {
    TKT_NEW: _row(ROLE_OWNER, TURN_OWNER, OWED_DAYS, "read it", "the owner reads it"),
    TKT_IN_PROGRESS: _row(ROLE_OWNER, TURN_OWNER, OWED_DAYS, "answer it",
                        "a reply is sent"),
    TKT_WAITING_ON_SENDER: _row(ROLE_OWNER, TURN_HOLD, OWED_DAYS,
                              "review the wait on the sender",
                              "the sender answers", hold=HOLD_ON_SENDER,
                              stalls_under_hold=True),
    # Its bound is the review date in the Ticket's last note; a Ticket whose
    # note names none falls back to the figure here.
    TKT_PENDING: _row(ROLE_OWNER, TURN_OWNER, OWED_DAYS,
                    "decide it, at the review date in the last note",
                    "the review date"),
    TKT_RESOLVED: _row(ROLE_OWNER, TURN_OWNER, OWED_DAYS, "close it", "closed"),
    TKT_REFUSED: _row(ROLE_OWNER, TURN_OWNER, OWED_DAYS, "close it", "closed"),
    TKT_CLOSED: _row(None, None, None, "none", "none"),
}

# type -> state -> row. A project's three kinds share the Project rows; a
# parent's difference is the sweep's (`flow.py`), as design.md states it.
FLOW: dict[str, dict[str, Flow]] = {
    TYPE_REQUIREMENT: REQUIREMENT_FLOW,
    TYPE_PROJECT: PROJECT_FLOW,
    TYPE_DECISION: DECISION_FLOW,
    TYPE_PULL_REQUEST: PULL_REQUEST_FLOW,
    TYPE_TICKET: TICKET_FLOW,
}

# The field that carries each type's state, and the state it starts at
# (R7; S-G5, S-G6). A pull request's is derived from GitHub, never written.
STATE_FIELD_OF: dict[str, str] = {
    TYPE_REQUIREMENT: REQUIREMENT_STATE,
    TYPE_PROJECT: PROJECT_STATE,
    TYPE_DECISION: DECISION_STATE,
    TYPE_PULL_REQUEST: PR_STATE,
    TYPE_TICKET: TICKET_STATE,
}
STARTING_STATE: dict[str, str] = {
    TYPE_REQUIREMENT: REQ_TRIAGE,
    TYPE_PROJECT: PROJ_SCOPE,
    TYPE_DECISION: DEC_ASKED,
    TYPE_TICKET: TKT_NEW,
}

# The holder of an item of a type whose state the table cannot place, where its
# workstream is known (design.md, *The turn*).
TYPE_HOLDER: dict[str, str] = {
    TYPE_REQUIREMENT: ROLE_DESIGN,
    TYPE_PROJECT: ROLE_DESIGN,
    TYPE_DECISION: ROLE_DESIGN,
    TYPE_PULL_REQUEST: ROLE_AUTHOR,
    TYPE_TICKET: ROLE_OWNER,
}


def role_turn(role: str | None) -> str | None:
    """The `Turn` a role's holding implies: the owner's, or Claude's."""
    if role is None:
        return None
    return TURN_OWNER if role == ROLE_OWNER else TURN_CLAUDE


def flow_type(issue) -> str:
    """The flow table's type for a classified issue: its three project kinds
    are one."""
    # By class, not by `kind`, which is a Python name that only happens to equal
    # GitHub's: renaming a type in GitHub must not move an issue's flow.
    if isinstance(issue, Project):
        return TYPE_PROJECT
    if isinstance(issue, Decision):
        return TYPE_DECISION
    if isinstance(issue, Ticket):
        return TYPE_TICKET
    if isinstance(issue, PullRequest):
        return TYPE_PULL_REQUEST
    return TYPE_REQUIREMENT


def flow_row(issue) -> Flow | None:
    """The row for an issue's type and state, or None where the state is not in
    the table (a renamed option is reported, never defaulted)."""
    return FLOW.get(flow_type(issue), {}).get(issue.step or "")


# Who holds a decision at each `Decision State`, and what they do next:
# the programme's docs/1.2's table, now the flow table's rows. The turn
# alternates at every step, so the owner holds three of the five. Until
# 2026-09-30 the reports knew only `Asked`, and five decisions documented for
# sign-off read as nothing waiting.
DECISION_TURNS: dict[str, tuple[str, str]] = {
    state: (OWNER if row.role == ROLE_OWNER else CLAUDE, row.owes)
    for state, row in DECISION_FLOW.items()
}


@dataclass(frozen=True)
class Decision(Issue):
    """A question and its answer. Its journey is `Decision State`."""

    @property
    def step(self) -> str | None:
        return self.field(DECISION_STATE)

    @property
    def step_field(self) -> str:
        return DECISION_STATE

    @property
    def turn(self) -> tuple[str, str] | None:
        """Who holds the decision now, and what they do: the programme's docs/1.2's table."""
        return DECISION_TURNS.get(self.step or "")

    @property
    def agreed(self) -> str:
        return self.section("Agreed Decision")


@dataclass(frozen=True)
class Ticket(Issue):
    """A service desk Ticket (docs/1.8). Its journey is `Ticket State`; it owes
    the project rules nothing, so only the rules every issue owes apply."""

    @property
    def step(self) -> str | None:
        return self.field(TICKET_STATE)

    @property
    def step_field(self) -> str:
        return TICKET_STATE


@dataclass(frozen=True)
class PullRequest(Issue):
    """The review surface. Its journey is `PR State`.

    A pull request is an issue in GitHub and is modelled as one here, so the
    review surface is inside the model rather than beside it.
    """

    @property
    def step(self) -> str | None:
        return self.field(PR_STATE)

    @property
    def step_field(self) -> str:
        return PR_STATE


# --------------------------------------------------------------------------
# classification: the one place an issue's kind is decided
# --------------------------------------------------------------------------


def classify(raw: RawIssue) -> Issue:
    """Turn a raw issue into the class that knows what it owes.

    The parent test is the narrow one and is the part that breaks: **a parent
    is a project whose sub-issues include projects**, not a project with any
    sub-issues. A project carries folded requirements as sub-issues routinely
    and is still one delivery owing one route — #214 has two work packages and
    two folded requirements, and counting sub-issues rather than project
    sub-issues misread it.
    """
    match raw.issue_type:
        case vocabulary.TYPE_DECISION:
            return Decision(raw)
        case vocabulary.TYPE_PULL_REQUEST:
            return PullRequest(raw)
        case vocabulary.TYPE_PROJECT:
            if any(s.issue_type == TYPE_PROJECT for s in raw.sub_issues):
                return ParentProject(raw)
            if raw.parent is not None:
                return WorkPackage(raw)
            return StandaloneProject(raw)
        case vocabulary.TYPE_TICKET:
            return Ticket(raw)
        case vocabulary.TYPE_REQUIREMENT:
            return Requirement(
                raw, stage_was_defaulted=raw.fields.get(REQUIREMENT_STATE) is None
            )
        case _:
            # Owner, 2026-09-18: untyped becomes a Requirement. There is no
            # Untyped class — a class owing nothing is skipped by every rule
            # keyed on type, which is #361 restated rather than fixed.
            return Requirement(
                raw,
                type_was_defaulted=True,
                stage_was_defaulted=raw.fields.get(REQUIREMENT_STATE) is None,
            )


def classify_all(raws: Iterator[RawIssue]) -> list[Issue]:
    return [classify(r) for r in raws]
