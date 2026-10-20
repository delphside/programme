"""D54's weekly digest: the brake's two measures, what landed, what was deleted.

#382, the job spec: *"a weekly digest, one issue comment — what landed, what
was deleted, the tooling share, and anything I decided that you might have
decided differently."*

**Derived, so it cannot flatter.** Three of the four parts come from git and
the board, not from memory of the week. A hand-written digest reports what its
author remembers, which is the work they are proud of; this one reports what
the repository actually shows, including a tooling share moving the wrong way.

**The fourth part cannot be derived and is not faked.** *Anything I decided
that you might have decided differently* is a judgement about someone else's
preferences. The tool leaves the section empty and says so, on the same rule as
`obligations.py` — something nothing can evidence must not read as *nothing to
report*, because an empty section and an unanswerable question look identical.

**The measure is the programme's docs/1.7's, not the one first proposed.** Owner, 2026-09-21:
*"The test is that we produce fewer issues and that they take less of my
time"*, and 2026-09-27, that the issues he meant are programme overhead,
`tooling` and `documentation`. So the headline is that count beside the week
before, every other type is counted with the programme's docs/1.7's reading of it, and what
the board reports as waiting on the owner. The tooling
share stays as an observation: its 45% figure is provisional and its horizon is
#383 finishing, not a date. Until 2026-09-27 this module still reported the
share against a 45% threshold and a 2026-10-17 date, and asked for a
confirmation the owner had already given, because the answer landed in the programme's docs/1.7
and not here.

**Deletions are counted first among equals**, because D54 says so: *"removing
tooling is as much in scope as adding it, and needs no more permission"*, and
the measure of success is the tooling share falling rather than the tooling
backlog being worked efficiently.
"""

from __future__ import annotations

import collections
import re
import subprocess
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from . import profile, repo
from .model import classify
from .sources import Snapshot
from .turn import waiting_on_owner

# The programme's docs/1.7's brake: programme overhead is these two types of change. Not the
# type called `non-functional`, which is work on the application (owner,
# 2026-09-27).
OVERHEAD = ("tooling", "documentation")

# Every type, in the programme's docs/1.7's order and with its reading in the owner's words
# (2026-09-27), so the digest counts them all rather than only the overhead.
READINGS = (
    ("functional", "constructive"),
    ("cosmetic", "constructive"),
    ("non-functional", "constructive if an enhancement"),
    ("bug", "poor quality overhead"),
    ("tooling", "programme overhead"),
    ("documentation", "programme overhead"),
    ("decision", "a choice put to you"),
    ("unset", "not categorised"),
)


def kind_of(raw) -> str:
    """An issue's `Type of change`. A Decision carries none (the programme's
    docs/1.2 §2.6), so it is counted as a decision rather than as uncategorised."""
    if kind := (raw.fields or {}).get("Type of change"):
        return kind
    return "decision" if raw.issue_type == "Decision" else "unset"


# The share when D54 was agreed, kept so the observation says where it moved
# from. Not a target.
MEASURED_AT = 55



def report_code(day: date) -> str:
    """The code a weekly digest is filed under for the ISO week `day` falls in:
    `<code>_<yyyy>_W<ww>`. A digest is programme-wide, so the code is the
    programme file's (`records.weekly_digest_code`), not an application's."""
    year, week, _ = day.isocalendar()
    return f"{profile.programme_file().string('records.weekly_digest_code')}_{year}_W{week:02d}"


def _subject_without_stamp(subject: str) -> str:
    """The subject after the commit stamp (the technical profile's
    `versions.stamp`, whose last group is the rest of the subject), or the whole
    subject when it carries none."""
    match = re.match(profile.technical().string("versions.stamp"), subject)
    return match.group(match.lastindex) if match and match.lastindex else subject


@dataclass
class Digest:
    since: str
    until: str
    landed: list[tuple[str, str]] = field(default_factory=list)
    files_deleted: list[str] = field(default_factory=list)
    lines_added: int = 0
    lines_removed: int = 0
    tooling: int = 0
    total: int = 0
    by_type: collections.Counter = field(default_factory=collections.Counter)
    closed: list[tuple[int, str]] = field(default_factory=list)
    raised: list[tuple[int, str]] = field(default_factory=list)
    window: "Window" = field(default_factory=lambda: Window())
    # The review half (the programme's docs/1.4, owner 2026-09-27): lessons collated, and the
    # two registers tracked. None means not available, which is not "none".
    lessons: list[tuple[int, str, str]] = field(default_factory=list)
    own_lessons: list[tuple[str, str]] | None = None
    # Projects closed in the window with neither lessons nor a delegation: the
    # closedown obligation is checked only while an issue is open.
    unlessoned: list[tuple[int, str]] = field(default_factory=list)
    # Each merged pull request's *Review rounds* section (the programme's
    # docs/1.1), or None when the search did not answer.
    reviews: list[tuple[str, int, str, str]] | None = None
    # Merged pull requests with neither rounds nor `None owed`.
    unrecorded: list[tuple[str, int, str]] | None = None
    problems: list[dict] = field(default_factory=list)
    initiatives: list[dict] = field(default_factory=list)

    @property
    def overhead(self) -> list[tuple[int, str]]:
        return self.window.overhead

    @property
    def overhead_before(self) -> int:
        return sum(self.window.raised_before[t] for t in OVERHEAD)
    waiting: list[tuple[int, str, str]] = field(default_factory=list)

    @property
    def share(self) -> int:
        return (self.tooling * 100 // self.total) if self.total else 0


def resolve(since: str, main: str = "origin/main") -> str:
    """A tag, a sha, or a date — a date becomes the last commit before it.

    Resolving to a commit rather than passing `--since` keeps every part of
    the digest on the same range: `git log --since` and `git diff A..B` do not
    agree about boundaries, and two counts of the same week a few lines apart
    is the defect this repository has already hit once, in the behind-main
    count.
    """
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", since):
        sha = repo._git("rev-list", "-1", f"--before={since}", main).strip()
        return sha or since
    return since


def window_start(since: str) -> str:
    """The window's first day, as YYYY-MM-DD, whatever `since` was given as."""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", since):
        return since
    return repo._git("log", "-1", "--format=%cs", since).strip() or since


@dataclass
class Window:
    """Issues raised and closed in the window and the seven days before it,
    counted by `kind_of`."""

    raised: list[tuple[int, str]] = field(default_factory=list)
    overhead: list[tuple[int, str]] = field(default_factory=list)
    closed: list[tuple[int, str]] = field(default_factory=list)
    raised_by_type: collections.Counter = field(default_factory=collections.Counter)
    closed_by_type: collections.Counter = field(default_factory=collections.Counter)
    raised_before: collections.Counter = field(default_factory=collections.Counter)
    closed_before: collections.Counter = field(default_factory=collections.Counter)
    # Open at the end of the week before: raised before the window and not
    # closed by its start. Derived from the two dates, since the board only
    # says what is open now.
    open_before: collections.Counter = field(default_factory=collections.Counter)


def in_window(open_raw, closed_raw, start: str) -> Window:
    """What was raised and closed in the window beginning `start`, a
    YYYY-MM-DD date, and in the seven days before it.

    Raised whatever state it is in now: an issue raised and closed inside the
    week was still raised. Until 2026-09-27 only the open ones were counted,
    and closed was read from `updated_at`, so a comment on an old closed issue
    listed it as closed this week. Closed is counted beside raised (owner,
    2026-09-27): raised alone says what arrived, not whether it is being
    cleared.
    """
    before = (date.fromisoformat(start) - timedelta(days=7)).isoformat()
    w = Window()
    for raw in list(open_raw) + list(closed_raw):
        created = (raw.created_at or "")[:10]
        if created >= start:
            w.raised.append((raw.number, raw.title))
            w.raised_by_type[kind_of(raw)] += 1
            if kind_of(raw) in OVERHEAD:
                w.overhead.append((raw.number, raw.title))
        elif created >= before:
            w.raised_before[kind_of(raw)] += 1
    for raw in list(open_raw) + list(closed_raw):
        if (raw.created_at or "")[:10] < start and not (raw.closed_at and raw.closed_at[:10] < start):
            w.open_before[kind_of(raw)] += 1
    for raw in closed_raw:
        closed = (raw.closed_at or "")[:10]
        if closed >= start:
            w.closed.append((raw.number, raw.title))
            w.closed_by_type[kind_of(raw)] += 1
        elif closed >= before:
            w.closed_before[kind_of(raw)] += 1
    w.raised.sort(); w.overhead.sort(); w.closed.sort()
    return w


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


def issue_lessons(closed_raw, start: str) -> list[tuple[int, str, str]]:
    """The *Lessons learnt* section of every issue closed in the window."""
    out = []
    for raw in closed_raw:
        if (raw.closed_at or "")[:10] >= start:
            text = section(raw.body, "Lessons learnt")
            if text:
                out.append((raw.number, raw.title, text))
    return sorted(out)


def register_rows(markdown: str, heading: str) -> list[dict]:
    """The rows of the first table under `heading`, as dicts keyed by its header
    cells. The programme's docs/1.4's registers are read this way, like its activity table."""
    rows, header = [], None
    for line in section(markdown, heading).splitlines():
        if not line.startswith("|"):
            if header:
                break
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header is None:
            header = cells
        elif not set(line.replace("|", "").strip()) <= set("-: "):
            rows.append(dict(zip(header, cells)))
    return rows


def unlessoned_projects(closed_raw, start: str) -> list[tuple[int, str]]:
    """Projects closed in the window with no *Lessons learnt* section and no
    `Delegated to #` statement, which the programme's docs/1.2 accepts instead."""
    return sorted((raw.number, raw.title) for raw in closed_raw
                  if (raw.closed_at or "")[:10] >= start and raw.issue_type == "Project"
                  and not section(raw.body, "Lessons learnt") and "Delegated to #" not in (raw.body or ""))


def _none_owed(text: str) -> bool:
    return text.strip().lstrip("-* ").lower().startswith("none owed")


def review_rounds(pull_requests) -> list[tuple[str, int, str, str]]:
    """The *Review rounds* section of each merged pull request that records
    rounds; one that says `None owed` records none."""
    out = []
    for pr in pull_requests:
        text = section(pr.body, "Review rounds")
        if text and not _none_owed(text):
            out.append((pr.repository, pr.number, pr.title, text))
    return out


def unrecorded(pull_requests) -> list[tuple[str, int, str]]:
    """Merged pull requests with no *Review rounds* section or an empty one,
    so a skipped review is told apart from a change that owed none. One a bot
    opened owes none and is left out."""
    return [(pr.repository, pr.number, pr.title) for pr in pull_requests
            if not pr.bot and not section(pr.body, "Review rounds")]


_FINDING = re.compile(r"^\s*-\s*R\d+\s+(\S+)\s+—\s*(.*)$")
_ALSO = re.compile(r"\(also (\S+?)\)")
# `(from a fix to R3 truth)`, `(from a fix to R3 reader truth)` for a shared
# finding, or `(from a fix to owner)`; an older record's bare `(from a fix)`
# names no finding.
_FROM_FIX = re.compile(r"\(from a fix(?: to (?:R\d+ )?([^)]+?))?\)")
_OWNER = re.compile(r"^\s*-\s*owner\s+—\s*(.*)$")
# `- R2 cost: reader 60k, 80%; truth 90k, 75%`: each reviewer's tokens and its
# completeness estimate in that round.
_COST = re.compile(r"^\s*-\s*R\d+\s+cost:\s*(.*)$")
_ROUND = re.compile(r"^\s*-\s*R(\d+)")
_SPENT = re.compile(r"([A-Za-z]+)\s+(\d+(?:\.\d+)?)k\b", re.I)
_TOKENS = re.compile(r"(\d+(?:\.\d+)?)k\b", re.I)
# The pair whose shared findings are counted: the two document reviewers.
PAIR = ("reader", "truth")
REVIEWERS = {"reader", "truth", "change", "owner"}


# The line a new draft's *Notes* opens with; it is not a note.
PLACEHOLDER = "Anything noticed during the week, for the review."


def note_records(notes: str) -> list[str]:
    """The notes split into records, one per top-level `- ` line other than a
    round, cost or owner line, so each record's cost lines pay only for its own
    findings; such a line stays with the record above it."""
    records, current = [], []
    for line in (notes or "").splitlines():
        rounds = (_FINDING.match(line) or _COST.match(line) or _OWNER.match(line)
                  or re.match(r"^\s*-\s*R\d+\s+none\b", line))
        if line.startswith("- ") and not rounds and current:
            records.append("\n".join(current))
            current = []
        current.append(line)
    if current:
        records.append("\n".join(current))
    return records


@dataclass
class RoundCount:
    """Material findings in *Review rounds* lines: their form is the programme's
    docs/1.1, and what is counted its docs/1.4.
    A finding marked `(also X)` is credited to both reviewers. A fault from a
    fix is crossed when none of its reviewers made the finding fixed, which its
    marker names: two reviewers pulling the same text different ways. A fix to
    the owner's finding, a bare marker or a name no reviewer has is never
    crossed."""

    by_reviewer: collections.Counter = field(default_factory=collections.Counter)
    findings: int = 0
    both: int = 0
    from_fix: int = 0
    crossed: int = 0
    missed: int = 0
    owner: int = 0
    tokens: float = 0
    cost_lines: int = 0
    # Findings in rounds that carry a cost line, so tokens are divided only by
    # the findings they paid for; and the findings in rounds with none.
    costed_findings: int = 0
    uncosted: int = 0
    # Cost lines with no figure in k, and figures naming no reviewer, which
    # add tokens to the total but to no reviewer.
    unread_costs: int = 0
    # Bang for buck, from the rounds that carry cost lines: tokens and
    # findings by reviewer and by round number.
    spent: collections.Counter = field(default_factory=collections.Counter)
    found: collections.Counter = field(default_factory=collections.Counter)

    def add(self, text: str) -> "RoundCount":
        lines = (text or "").splitlines()
        # A record's cost lines first, so each finding is charged to its own round.
        costed: dict[str, set[str]] = {}
        for line in lines:
            if m := _COST.match(line):
                self.cost_lines += 1
                round_ = "R" + _ROUND.match(line).group(1)
                costed.setdefault(round_, set())
                figures = _TOKENS.findall(m.group(1))
                named = _SPENT.findall(m.group(1))
                self.unread_costs += (not figures) + max(0, len(figures) - len(named))
                self.tokens += sum(float(t) for t in figures)
                for who, k in named:
                    who = who.lower()
                    if who in REVIEWERS:
                        costed[round_].add(who)
                        self.spent[who] += float(k)
                    else:
                        self.unread_costs += 1
                    self.spent[round_] += float(k)
        for line in lines:
            if _COST.match(line):
                continue
            if m := _FINDING.match(line):
                if m.group(2).strip().lower() == "none":
                    continue
                self.findings += 1
                who = {w.lower() for w in {m.group(1)} | set(_ALSO.findall(line))}
                round_ = "R" + _ROUND.match(line).group(1)
                for reviewer in who:
                    self.by_reviewer[reviewer] += 1
                if round_ in costed:
                    self.costed_findings += 1
                    self.found[round_] += 1
                    for reviewer in who & costed[round_]:
                        self.found[reviewer] += 1
                else:
                    self.uncosted += 1
                self.both += set(PAIR) <= who
                if fix := _FROM_FIX.search(line):
                    self.from_fix += 1
                    fixed = set((fix.group(1) or "").split()) & REVIEWERS
                    if fixed and "owner" not in fixed:
                        self.crossed += not (who & fixed)
                self.missed += "(missed in R" in line
            elif (m := _OWNER.match(line)) and m.group(1).strip().lower() not in ("none", "not reviewed"):
                self.owner += 1
        return self

    def __bool__(self) -> bool:
        return bool(self.by_reviewer) or bool(self.owner) or bool(self.cost_lines)

    def summary(self) -> str:
        found = ", ".join(f"{who} {n}" for who, n in sorted(self.by_reviewer.items())) or "none"
        return (f"material findings: {found}; found by both {PAIR[0]} and {PAIR[1]}: {self.both}; "
                f"from a fix: {self.from_fix}, of them crossed (only other reviewers made the finding fixed): {self.crossed}; missed by an earlier round: {self.missed}; "
                f"found by the owner afterwards: {self.owner}")

    def missed_share(self) -> str:
        """The share of findings a later round proved an earlier one could have
        found: a count, where a capture-recapture estimate assumes reviewers
        alike, which the two lenses are briefed not to be."""
        if not self.findings:
            return "no reviewer findings"
        return (f"{self.missed} of {self.findings} findings missed by an earlier round "
                f"({100 * self.missed / self.findings:.0f}%)")

    def cost(self) -> str:
        if not self.cost_lines:
            return "no cost lines"
        if not self.tokens:
            return "cost lines with no k figure"
        per = (f", about {self.tokens / self.costed_findings:.0f}k per material finding"
               if self.costed_findings else "")
        gap = f"; {self.uncosted} finding(s) in rounds with no cost line" if self.uncosted else ""
        unread = f"; {self.unread_costs} cost figure(s) not read" if self.unread_costs else ""
        return f"{self.tokens:.0f}k tokens{per}{gap}{unread}"


    def value(self) -> str:
        """Tokens per material finding by reviewer, then by round number, over
        the rounds that carry cost lines: which lens and which round paid for
        itself. A shared finding counts for each of its reviewers."""
        def per(key: str) -> str:
            n = self.found[key]
            return f"{key} {self.spent[key]:.0f}k for {n}" + (f" ({self.spent[key] / n:.0f}k each)" if n else "")
        keys = set(self.spent) | set(self.found)
        reviewers = sorted(k for k in keys if not re.fullmatch(r"R\d+", k))
        rounds = sorted((k for k in keys if re.fullmatch(r"R\d+", k)), key=lambda k: int(k[1:]))
        if not keys:
            return "no cost lines"
        gap = f". Not costed: {self.uncosted} finding(s)" if self.uncosted else ""
        return ("by reviewer, a shared finding counting for each: " + "; ".join(per(k) for k in reviewers)
                + ". By round: " + "; ".join(per(k) for k in rounds) + gap)


def claude_lessons(memory_repo: Path, start: str) -> list[tuple[str, str]] | None:
    """The feedback notes Claude added to its memory in the window: its own
    lessons, which live outside this repository (owner, 2026-09-27). None when
    the memory repository is not on this machine."""
    if not (memory_repo / ".git").exists():
        return None
    run = subprocess.run(["git", "-C", str(memory_repo), "log", "--diff-filter=A", f"--since={start}",
                          "--name-only", "--format=", "--", "projects/*/memory/feedback_*.md"],
                         capture_output=True, text=True)
    if run.returncode:
        return None
    out = []
    for name in sorted(set(run.stdout.split())):
        path = memory_repo / name
        if not path.exists():
            continue
        m = re.search(r"^description:\s*(.+)$", path.read_text(), re.M)
        out.append((path.stem.removeprefix("feedback_").replace("_", " "),
                    m.group(1).strip().strip('"') if m else ""))
    return out


def build(open_snapshot: Snapshot, closed_snapshot: Snapshot | None,
          since: str, until: str = "HEAD", registers: str = "",
          memory_repo: Path | None = None, merged_prs=None) -> Digest:
    d = Digest(since=since, until=until)
    start = window_start(since)

    rev = f"{resolve(since)}..{until}"
    log = repo._git("log", "--no-merges", "--format=%H%x1f%s", rev)
    for line in log.splitlines():
        if "\x1f" not in line:
            continue
        sha, subject = line.split("\x1f", 1)
        d.landed.append((sha[:7], _subject_without_stamp(subject)))

    d.files_deleted = [f for f in repo._git(
        "log", "--diff-filter=D", "--name-only", "--format=", rev).split() if f]

    stat = repo._git("diff", "--shortstat", rev)
    if add := re.search(r"(\d+) insertion", stat):
        d.lines_added = int(add.group(1))
    if rm := re.search(r"(\d+) deletion", stat):
        d.lines_removed = int(rm.group(1))

    everything = [classify(r) for r in open_snapshot.issues]
    issues = [i for i in everything if i.raw.issue_type != "PullRequest"]
    d.total = len(issues)
    d.by_type = collections.Counter(kind_of(i.raw) for i in issues)
    d.tooling = d.by_type.get("tooling", 0)

    # Pull requests are in the snapshot for this: a review waiting is his.
    for issue in everything:
        w = waiting_on_owner(issue)
        if w:
            d.waiting.append((issue.number, issue.title, w.asked))

    closed_raw = list(closed_snapshot.issues) if closed_snapshot else []
    d.window = in_window([i.raw for i in issues], closed_raw, start)
    d.raised, d.closed = d.window.raised, d.window.closed
    d.lessons = issue_lessons(closed_raw, start)
    d.unlessoned = unlessoned_projects(closed_raw, start)
    d.reviews = review_rounds(merged_prs) if merged_prs is not None else None
    d.unrecorded = unrecorded(merged_prs) if merged_prs is not None else None
    d.own_lessons = claude_lessons(memory_repo, start) if memory_repo else None
    d.problems = register_rows(registers, "The problem register")
    d.initiatives = register_rows(registers, "The continual improvement register")
    return d


DRAFT = "<!-- draft: notes only, until board-digest.py --write fills it in -->"

# Left by the digest after every lesson and note, and replaced at Claude's
# weekly review by its conclusion (the programme's docs/1.4, owner 2026-09-27). The four named
# are examples: "that list may not be comprehensive".
CONCLUDE = ("*Conclusion, at the weekly review: for example an initiative (which `CI-`), "
            "monitoring (which `P-` or measure), a process change (what, where), or no action "
            "(why).*")


def with_conclusions(notes: str) -> str:
    """The week's notes, each bulleted record of `note_records` followed by its
    conclusion to decide. Text before the first bullet is a preamble and takes
    none; text with no bullets at all is one note."""
    if not notes:
        return notes
    records = note_records(notes)
    if not any(record.startswith("- ") for record in records):
        return f"{notes}\n\n{CONCLUDE}"
    return "\n".join(f"{record}\n  - {CONCLUDE}" if record.startswith("- ") else record
                     for record in records)


def draft(code: str, first_day: str) -> str:
    """Next week's report, before it is written: only a Notes section, for
    whatever occurs to either of us during the week (the programme's docs/1.4)."""
    return (f"# Weekly digest, from {first_day}\n\n`{code}`\n\n{DRAFT}\n\n"
            f"## Notes\n\n{PLACEHOLDER}\n")


def notes_of(text: str) -> str:
    """The Notes section a draft collected, without its placeholder line."""
    notes = section(text, "Notes")
    if notes.startswith(PLACEHOLDER):
        notes = notes[len(PLACEHOLDER):].strip()
    return notes


def notes_for_write(existing: str | None) -> str | None:
    """What writing a week's report may do, given the file already there: the
    notes to keep, "" for no file, or None to refuse. A draft's notes are kept;
    a written report is refused, since one still in review is regenerated by
    deleting it first, a deliberate act, and a reviewed one never."""
    if existing is None:
        return ""
    return notes_of(existing) if DRAFT in existing else None


def render(d: Digest, judgements: list[str] | None = None, notes: str = "") -> str:
    until = date.today().isoformat() if d.until == "HEAD" else d.until[:10]
    out = [f"# Weekly digest, {window_start(d.since)} to {until}", ""]

    # the programme's docs/1.7's brake, limit 1: fewer non-functional issues, and less of the
    # owner's time. Both counted, neither argued.
    out.append("## The brake: less programme overhead, less of your time")
    out.append("")
    w = d.window
    closed_now = sum(w.closed_by_type[t] for t in OVERHEAD)
    closed_then = sum(w.closed_before[t] for t in OVERHEAD)
    out.append(f"**{len(d.overhead)}** programme overhead issues raised (`tooling` or "
               f"`documentation`) and **{closed_now}** closed, against **{d.overhead_before}** "
               f"raised and **{closed_then}** closed in the seven days before.")
    if d.overhead:
        out.append("")
    for number, title in d.overhead:
        out.append(f"- #{number} {title}")
    out.append("")
    # Every type, because each says something different about the owner's
    # time (the programme's docs/1.7). A type with nothing either week still gets its row, so
    # a quiet week for bugs is visible rather than absent.
    # Raised, closed and open by type: what arrived, what was cleared, and
    # what stands (owner, 2026-09-27). Every type in the programme's docs/1.7's order, a quiet
    # one included, so a week with no bugs is visible rather than absent.
    # Grouped by week, owner 2026-09-27: raised, closed and open for this
    # week, then the same for last week. Markdown has one header row, so the
    # week names the first column of each group.
    out.append("| type of change | this week: raised | closed | open | last week: raised | closed | open "
               f"| use of {profile.owner_name()}'s time |")
    out.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    known = {kind for kind, _ in READINGS}
    others = sorted((set(w.raised_by_type) | set(w.closed_by_type) | set(w.raised_before)
                     | set(w.closed_before) | set(w.open_before) | set(d.by_type)) - known)
    for kind, reading in list(READINGS) + [(k, "not in the programme's docs/1.7") for k in others]:
        out.append(f"| `{kind}` | {w.raised_by_type[kind]} | {w.closed_by_type[kind]} | {d.by_type[kind]} | "
                   f"{w.raised_before[kind]} | {w.closed_before[kind]} | {w.open_before[kind]} | {reading} |")
    out.append("")
    if d.waiting:
        things = "thing" if len(d.waiting) == 1 else "things"
        out.append(f"**{len(d.waiting)}** {things} the board reports as waiting on you:")
        out.append("")
        for number, title, action in d.waiting:
            out.append(f"- #{number} {title}: {action}")
    else:
        out.append("**Nothing** the board reports as waiting on you.")
    out.append("")
    # An observation, not the target (the programme's docs/1.7). Always name the starting
    # point, so a one-point move cannot read like a ten-point one.
    out.append(f"*The tooling share, as an observation:* {d.tooling} of {d.total} open "
               f"issues are `tooling`, **{d.share}%**, against {MEASURED_AT}% when D54 "
               "was agreed. Not the target: the 45% figure is provisional until "
               "#383's model has replaced the tooling it is replacing.")
    out.append("")
    out.append(f"## What landed — {len(d.landed)} commits")
    out.append("")
    for sha, subject in d.landed[:40]:
        out.append(f"- `{sha}` {subject}")
    if len(d.landed) > 40:
        out.append(f"- …and {len(d.landed) - 40} more")

    out.append("")
    out.append("## What was deleted")
    out.append("")
    if d.files_deleted:
        for path in d.files_deleted:
            out.append(f"- `{path}`")
    else:
        out.append("Nothing was removed this week.")
    out.append("")
    out.append(f"{d.lines_added} lines added, {d.lines_removed} removed. "
               "D54: *removing tooling is as much in scope as adding it.*")

    if d.raised or d.closed:
        out.append("")
        out.append("## Issues")
        out.append("")
        if d.raised:
            out.append(f"### Raised ({len(d.raised)})")
            out.append("")
            for number, title in d.raised:
                out.append(f"- #{number} {title}")
        if d.closed:
            if d.raised:
                out.append("")
            out.append(f"### Closed ({len(d.closed)})")
            out.append("")
            for number, title in d.closed:
                out.append(f"- #{number} {title}")

    out.append("")
    start = window_start(d.since)
    out.append("## Lessons learnt")
    out.append("")
    out.append("### From the issues closed this week")
    out.append("")
    if d.lessons:
        for number, title, text in d.lessons:
            # A title may already carry its number: "#214 MAIN PROJECT: ...".
            name = title if title.startswith(f"#{number} ") else f"#{number} {title}"
            out.append(f"#### {name}")
            out.append("")
            out.append(text)
            out.append("")
            out.append(CONCLUDE)
            out.append("")
    else:
        out.append("No issue closed this week recorded a lesson.")
        out.append("")
    if d.unlessoned:
        out.append("Projects closed this week with no lessons learnt and no delegation: "
                   + ", ".join(f"#{n}" for n, _ in d.unlessoned) + ".")
        out.append("")
    out.append("### Document reviews")
    out.append("")
    total = RoundCount()
    if d.reviews is None:
        out.append("*Not available: the search for merged pull requests did not answer.*")
        out.append("")
    elif not d.reviews:
        out.append("No pull request merged this week recorded review rounds; one that owed none is not listed.")
        out.append("")
    for repository, number, title, text in d.reviews or []:
        out.append(f"#### {repository}#{number} {title}")
        out.append("")
        out.append(text)
        out.append("")
        out.append(RoundCount().add(text).summary() + ".")
        out.append("")
        total.add(text)
    if d.unrecorded:
        out.append("Merged with neither *Review rounds* nor `None owed`: "
                   + ", ".join(f"{r}#{n}" for r, n, _ in d.unrecorded) + ".")
        out.append("")
    # A change committed straight to main records its rounds in the notes.
    entries = note_records(notes)
    in_notes = RoundCount()
    for entry in entries:
        in_notes.add(entry)
    if in_notes:
        out.append(f"From the notes below, for changes with no pull request: {in_notes.summary()}.")
        out.append("")
        for entry in entries:
            total.add(entry)
    if total:
        out.append(f"**This week:** {total.summary()}. Missed: {total.missed_share()}. "
                   f"Cost: {total.cost()}.")
        out.append("")
        out.append(f"**Bang for buck**, {total.value()}.")
        out.append("")
    # The programme's docs/1.4: a Fable agent reads the week's rounds and counts
    # beside last week's digest; its report is written in here.
    out.append("### Review of the reviews")
    out.append("")
    out.append("*To be written at the weekly review, as the programme's docs/1.4 says.*")
    out.append("")
    out.append("### Claude's own, added to its memory this week")
    out.append("")
    if d.own_lessons is None:
        out.append("*Not available: the memory repository is not on this machine.*")
    elif d.own_lessons:
        for name, description in d.own_lessons:
            out.append(f"- **{name}**: {description}")
            out.append(f"  - {CONCLUDE}")
    else:
        out.append("None added this week.")
    out.append("")

    # The registers are the programme's docs/1.4's; the digest reports them, new ones marked.
    for title, rows, what in (("Recurring problems", d.problems, "problem"),
                              ("Improvement initiatives", d.initiatives, "initiative")):
        out.append(f"## {title}")
        out.append("")
        live = [r for r in rows if not r.get("state", "").startswith("done")]
        if not live:
            out.append(f"No open {what} in the programme's docs/1.4's register.")
        for r in live:
            new = " **new this week**" if r.get("raised", "") >= start else ""
            detail = r.get("initiative") if what == "problem" else r.get("state")
            out.append(f"- {r.get('id', '')} {r.get(what, '')}: {detail}{new}")
        out.append("")

    out.append("## Notes from the week")
    out.append("")
    out.append(with_conclusions(notes) or "None were added to this week's draft.")
    out.append("")

    out.append("## What I decided that you might have decided differently")
    out.append("")
    if judgements:
        out += [f"- {j}" for j in judgements]
    else:
        # Not derivable, and not to be reported as "nothing".
        out.append("*Not filled in. This section is a judgement about what you "
                   "would have wanted, which nothing in git or the board can "
                   "answer — an empty one here means it was not written, not "
                   "that there was nothing.*")

    # the programme's docs/1.4: Claude reviews weekly, the owner monthly; the report is fixed
    # once the owner's review has covered it.
    out.append("")
    out.append("## Review")
    out.append("")
    out.append("- [ ] **Claude** — weekly review: the review of the reviews written; lessons, notes, problems and initiatives assessed, "
               "the registers updated, and each section and measure checked for use")
    out.append("- [ ] **owner** — monthly review (`improvement-review`): Claude ticks this when the "
               "owner says it is done; the report is fixed once ticked")
    return "\n".join(out)
