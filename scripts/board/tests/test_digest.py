"""The weekly digest, the `weekly-digest` activity in docs/3.8.

From the programme's docs/1.7's brake, not from the code. The cases that matter are the ones
where a bug would flatter the report or repeat a settled question:

  the measure     programme overhead raised per week (types `tooling` and
                  `documentation`, not the type called `non-functional`),
                  beside the week before; every other type counted with its
                  reading; and what is waiting on the owner. Owner, 2026-09-21
                  and 2026-09-27.
  the share       an observation, not the target: no threshold verdict, no
                  date, and no request to confirm what the owner has already
                  answered. Until 2026-09-27 the digest still asked.
  the window      an issue raised and closed inside the week was still raised;
                  closed means closed in the window, not merely touched
  judgement       "anything I decided that you might have decided differently"
                  cannot be derived; an empty section must say it was not
                  written, never that there was nothing

No network: canned counts and issues, a temporary git repository, and
docs/1.1's example of the review record."""

import collections
import re
import unittest

import subprocess
import tempfile
from pathlib import Path

from board.digest import (CONCLUDE, RoundCount, note_records, review_rounds, unrecorded, unlessoned_projects, DRAFT, Digest, with_conclusions, Window, claude_lessons, draft, in_window, issue_lessons,
                          notes_for_write, notes_of, register_rows, render, section, MEASURED_AT)
from board.model import RawIssue
from board.sources import MergedPullRequest

from .cases import Cases


def digest(tooling=48, total=100, **kw):
    d = Digest(since="2026-09-21", until="2026-09-27", tooling=tooling, total=total, **kw)
    d.by_type = collections.Counter({"tooling": tooling, "other": total - tooling})
    return d


def issue(n, kind_of_change, created, closed=None, body="", issue_type="Requirement"):
    return RawIssue(n, f"issue {n}", "CLOSED" if closed else "OPEN", body, issue_type,
                    {"Type of change": kind_of_change} if kind_of_change else {}, (), None, None,
                    frozenset(), created_at=created, closed_at=closed)


class TheBrake(Cases):
    def test_overhead_raised_and_closed_is_counted_beside_the_week_before(self):
        w = Window(overhead=[(401, "a tooling fix")],
                   closed_by_type=collections.Counter({"tooling": 2, "bug": 9}),
                   raised_before=collections.Counter({"tooling": 2, "documentation": 1, "bug": 5}),
                   closed_before=collections.Counter({"documentation": 4}))
        text = render(digest(window=w))
        self.expect("raised and closed this week, overhead only", True,
                    "**1** programme overhead issues raised (`tooling` or `documentation`) and **2** closed" in text)
        self.expect("beside the week before", True, "against **3** raised and **4** closed in the seven days before" in text)
        self.expect("and each is named", True, "#401 a tooling fix" in text)

    def test_every_type_is_counted_raised_closed_and_open_with_its_reading(self):
        w = Window(raised_by_type=collections.Counter({"functional": 4, "bug": 1}),
                   closed_by_type=collections.Counter({"bug": 2}),
                   raised_before=collections.Counter({"bug": 3}),
                   closed_before=collections.Counter({"functional": 1}))
        d = digest(window=w)
        d.by_type = collections.Counter({"functional": 10, "bug": 2})
        text = render(d)
        # Owner, 2026-09-27: this week raised, closed, open; then last week the same.
        self.expect("grouped by week", True,
                    "| type of change | this week: raised | closed | open | last week: raised | closed | open | use of Pat's time |" in text)
        self.expect("functional", True, "| `functional` | 4 | 0 | 10 | 0 | 1 | 0 | constructive |" in text)
        self.expect("bugs", True, "| `bug` | 1 | 2 | 2 | 3 | 0 | 0 | poor quality overhead" in text)
        # A quiet type still gets its row, so a week with no bugs is visible.
        self.expect("a type with nothing is still shown", True, "| `documentation` | 0 | 0 | 0 | 0 | 0 | 0 |" in text)
        # Owner, 2026-09-27: cosmetic is counted separately and credited as functional.
        self.expect("cosmetic reads as functional", True,
                    "| `cosmetic` | 0 | 0 | 0 | 0 | 0 | 0 | constructive |" in text)
        odd = render(digest(window=Window(raised_by_type=collections.Counter({"spike": 1}))))
        self.expect("a type the programme's docs/1.7 does not name is shown, not dropped", True,
                    "| `spike` | 1 | 0 | 0 | 0 | 0 | 0 | not in the programme's docs/1.7 |" in odd)

    def test_what_is_waiting_on_the_owner_is_listed_or_said_to_be_nothing(self):
        self.expect("nothing waiting says nothing", True,
                    "**Nothing** the board reports as waiting on you" in render(digest()))
        one = render(digest(waiting=[(407, "Programme BAU", "tick R3")]))
        self.expect("one thing is singular", True, "**1** thing the board reports" in one)
        self.expect("and says what is asked", True, "#407 Programme BAU: tick R3" in one)

    def test_the_share_is_an_observation_not_a_verdict(self):
        text = render(digest(48, 100))
        self.expect("it is shown", True, "**48%**" in text)
        self.expect("from where it started", True, f"{MEASURED_AT}%" in text)
        self.expect("as an observation", True, "as an observation" in text)
        self.expect("with no date for a horizon", False, "2026-10-17" in text)
        # The owner answered on 2026-09-21; asking again is the defect this replaced.
        self.expect("and no request to confirm", False, "confirm" in text)

    def test_the_share_is_arithmetic(self):
        self.expect("it rounds down, never up", 48, digest(48, 100).share)
        self.expect("no issues at all does not divide by zero", 0, digest(0, 0).share)


class TheWindow(Cases):
    START = "2026-09-21"

    def test_raised_counts_open_and_closed_alike(self):
        w = in_window([issue(1, "tooling", "2026-09-22T10:00:00Z")],
                      [issue(2, "documentation", "2026-09-23T10:00:00Z", closed="2026-09-24T10:00:00Z")],
                      self.START)
        self.expect("both are raised", [1, 2], [n for n, _ in w.raised])
        self.expect("both are overhead", [1, 2], [n for n, _ in w.overhead])
        self.expect("and the one closed in the week is closed", [2], [n for n, _ in w.closed])
        self.expect("counted by its type", {"documentation": 1}, dict(w.closed_by_type))

    def test_overhead_means_tooling_and_documentation_not_the_type_called_non_functional(self):
        w = in_window([issue(1, "functional", "2026-09-22T10:00:00Z"),
                                                issue(2, "non-functional", "2026-09-22T10:00:00Z"),
                                                issue(3, None, "2026-09-22T10:00:00Z"),
                                                issue(4, "documentation", "2026-09-22T10:00:00Z")], [], self.START)
        # the programme's docs/1.7, owner 2026-09-27: the overhead is tooling and documentation.
        self.expect("only those two types", [4], [n for n, _ in w.overhead])
        self.expect("every type is still counted", {"functional": 1, "non-functional": 1, "unset": 1, "documentation": 1},
                    dict(w.raised_by_type))

    def test_a_decision_is_counted_as_a_decision_not_as_unset(self):
        w = in_window([issue(1, None, "2026-09-22T10:00:00Z", issue_type="Decision"),
                       issue(2, None, "2026-09-22T10:00:00Z")],
                      [issue(3, None, "2026-09-20T10:00:00Z", closed="2026-09-23T10:00:00Z",
                             issue_type="Decision")], self.START)
        # the programme's docs/1.2 §2.6: a Decision carries no Type of change.
        self.expect("raised", {"decision": 1, "unset": 1}, dict(w.raised_by_type))
        self.expect("closed", {"decision": 1}, dict(w.closed_by_type))

    def test_the_week_before_is_the_seven_days_before_the_window(self):
        w = in_window([issue(1, "tooling", "2026-09-14T00:00:00Z"),
                       issue(2, "bug", "2026-09-20T23:59:00Z"),
                       issue(3, "tooling", "2026-09-13T23:59:00Z")],
                      [issue(4, "bug", "2026-08-01T00:00:00Z", closed="2026-09-15T00:00:00Z"),
                       issue(5, "bug", "2026-08-01T00:00:00Z", closed="2026-09-13T00:00:00Z")], self.START)
        self.expect("raised on the 14th and the 20th, not the 13th", {"tooling": 1, "bug": 1}, dict(w.raised_before))
        self.expect("closed on the 15th, not the 13th", {"bug": 1}, dict(w.closed_before))

    def test_open_last_week_reconciles_with_open_now(self):
        # Open at the end of last week, plus raised, less closed, is open now:
        # the check that both open counts mean what they say.
        open_now = [issue(1, "bug", "2026-09-01T00:00:00Z"), issue(2, "bug", "2026-09-22T00:00:00Z")]
        closed = [issue(3, "bug", "2026-09-02T00:00:00Z", closed="2026-09-23T00:00:00Z"),
                  issue(4, "bug", "2026-09-02T00:00:00Z", closed="2026-09-10T00:00:00Z"),
                  issue(5, "bug", "2026-09-22T00:00:00Z", closed="2026-09-24T00:00:00Z")]
        w = in_window(open_now, closed, self.START)
        self.expect("open at the end of last week: #1 and #3, not #4 closed before it", 2, w.open_before["bug"])
        self.expect("reconciles: 2 + 2 raised - 2 closed = 2 open now", len(open_now),
                    w.open_before["bug"] + w.raised_by_type["bug"] - w.closed_by_type["bug"])

    def test_an_old_issue_closed_before_the_window_is_not_closed_in_it(self):
        w = in_window([], [issue(5, "tooling", "2026-08-01T00:00:00Z", closed="2026-09-01T00:00:00Z")], self.START)
        self.expect("not listed", [], w.closed)
        self.expect("nor counted", 0, sum(w.closed_by_type.values()))


REGISTERS = """## Continual improvement

### The problem register

| id | problem | occurrences | initiative | raised |
| --- | --- | --- | --- | --- |
| `P-1` | old trouble | twice | `CI-1` | 2026-09-01 |
| `P-2` | new trouble | twice | none yet | 2026-09-22 |

### The continual improvement register

| id | initiative | measure it moves | state | raised |
| --- | --- | --- | --- | --- |
| `CI-1` | finished work | a | done 2026-09-10 | 2026-09-01 |
| `CI-2` | ongoing work | b | in progress | 2026-09-02 |
"""


class TheReview(Cases):
    """the programme's docs/1.4, owner 2026-09-27: the digest collates lessons learnt and tracks
    recurring problems and improvement initiatives."""

    def test_a_section_is_read_to_the_next_heading_of_its_level(self):
        body = "## Design\nx\n## Lessons learnt\n\nfirst\n### detail\nsecond\n## Deliveries\ny"
        self.expect("the section and its subsections, nothing after", "first\n### detail\nsecond",
                    section(body, "Lessons learnt"))
        self.expect("no such heading is empty", "", section(body, "Nothing"))

    def test_lessons_come_from_issues_closed_in_the_window(self):
        lesson = "## Lessons learnt\n\nrun it once before merging"
        found = issue_lessons([issue(1, "tooling", "2026-09-01", closed="2026-09-22T00:00:00Z", body=lesson),
                               issue(2, "tooling", "2026-09-01", closed="2026-09-10T00:00:00Z", body=lesson),
                               issue(3, "tooling", "2026-09-01", closed="2026-09-23T00:00:00Z", body="no lessons")],
                              "2026-09-21")
        self.expect("only the one closed this week that recorded one", [(1, "issue 1", "run it once before merging")], found)

    def test_the_registers_are_read_from_docs_3_8(self):
        problems = register_rows(REGISTERS, "The problem register")
        self.expect("every row", ["`P-1`", "`P-2`"], [r["id"] for r in problems])
        self.expect("keyed by the header", "none yet", problems[1]["initiative"])
        self.expect("and the other table separately", 2,
                    len(register_rows(REGISTERS, "The continual improvement register")))

    def test_open_ones_are_reported_and_new_ones_marked(self):
        d = digest(problems=register_rows(REGISTERS, "The problem register"),
                   initiatives=register_rows(REGISTERS, "The continual improvement register"))
        text = render(d)
        self.expect("a new problem is marked", True, "`P-2` new trouble: none yet **new this week**" in text)
        self.expect("an older one is not", True, "`P-1` old trouble: `CI-1`\n" in text)
        self.expect("an open initiative is shown", True, "`CI-2` ongoing work: in progress" in text)
        self.expect("a finished one is not", False, "finished work" in text)

    def test_claudes_own_lessons_come_from_the_memory_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git = lambda *a: subprocess.run(["git", "-C", tmp, "-c", "user.email=t@t", "-c", "user.name=t", *a],
                                            check=True, capture_output=True)
            git("init", "-q")
            mem = repo / "projects" / "p" / "memory"
            mem.mkdir(parents=True)
            (mem / "feedback_stub_the_outward.md").write_text("---\nname: x\ndescription: stub what the script reaches\n---\n")
            (mem / "project_status.md").write_text("---\ndescription: not a lesson\n---\n")
            git("add", "-A"); git("commit", "-q", "-m", "x")
            found = claude_lessons(repo, "2000-01-01")
            self.expect("a feedback note is a lesson, a project note is not",
                        [("stub the outward", "stub what the script reaches")], found)
        self.expect("no repository is not available, not none", None, claude_lessons(Path("/nonexistent"), "2000-01-01"))

    def test_unavailable_reads_differently_from_none(self):
        self.expect("not available", True, "*Not available: the memory repository" in render(digest(own_lessons=None)))
        self.expect("none", True, "None added this week." in render(digest(own_lessons=[])))


class ReviewAndNotes(Cases):
    """the programme's docs/1.4: Claude reviews weekly, the owner monthly; notes between digests
    go in next week's draft."""

    def test_a_report_ends_with_a_box_for_each_review(self):
        text = render(digest())
        self.expect("Claude's weekly review", True, "- [ ] **Claude** — weekly review" in text)
        self.expect("the owner's monthly review", True, "- [ ] **owner** — monthly review" in text)
        self.expect("and they are last", True, text.rstrip().endswith("the report is fixed once ticked"))

    def test_a_drafts_notes_reach_the_report(self):
        d = draft("TLE_WD_2026_W40", "2026-09-28")
        self.expect("a new draft is marked as one", True, DRAFT in d)
        self.expect("and its placeholder is not a note", "", notes_of(d))
        written = d.replace("Anything noticed during the week, for the review.", "- the watcher lied twice")
        self.expect("a note is read back", "- the watcher lied twice", notes_of(written))
        self.expect("and carried into the report", True,
                    "- the watcher lied twice" in render(digest(), notes=notes_of(written)))

    def test_writing_keeps_a_drafts_notes_and_refuses_a_written_report(self):
        d = draft("TLE_WD_2026_W40", "2026-09-28").replace(
            "Anything noticed during the week, for the review.", "- a note")
        self.expect("no file: nothing to keep", "", notes_for_write(None))
        self.expect("a draft: its notes are kept", "- a note", notes_for_write(d))
        self.expect("a written report: refused", None, notes_for_write(render(digest())))

    def test_no_notes_says_so(self):
        self.expect("rather than an empty heading", True, "None were added to this week's draft." in render(digest()))


class Conclusions(Cases):
    """the programme's docs/1.4, owner 2026-09-27: every lesson and note ends with a conclusion,
    decided at the weekly review, so the digest leaves one to decide for each."""

    def test_each_lesson_from_an_issue_has_one(self):
        text = render(digest(lessons=[(1, "a", "first"), (2, "b", "second")]))
        self.expect("one per lesson", 2, text.count(CONCLUDE))

    def test_each_of_claudes_own_lessons_has_one(self):
        text = render(digest(own_lessons=[("x", "one"), ("y", "two"), ("z", "three")]))
        self.expect("one per lesson", 3, text.count(CONCLUDE))

    def test_each_note_has_one_whatever_its_shape(self):
        self.expect("a bullet, with its continuation line kept above it", 2,
                    with_conclusions("- one\n  more of one\n- two").count(CONCLUDE))
        self.expect("continuation stays with its note", True,
                    with_conclusions("- one\n  more of one\n- two").startswith("- one\n  more of one\n  - *Conclusion"))
        self.expect("text with no bullets is one note", 1, with_conclusions("plain note").count(CONCLUDE))
        self.expect("text before the first bullet takes none; each bullet takes one", 2,
                    with_conclusions("Anything noticed during the week.\n- one\n- two").count(CONCLUDE))
        self.expect("the placeholder is dropped before real notes", "- one",
                    notes_of("## Notes\n\nAnything noticed during the week, for the review.\n- one\n"))
        self.expect("a note's top-level round lines share its conclusion", 1,
                    with_conclusions("- abc1234 rounds:\n- R1 reader — x — y\n- R1 cost: reader 5k").count(CONCLUDE))
        self.expect("no notes, nothing to conclude", "", with_conclusions(""))
        self.expect("and the report carries them", 2, render(digest(), notes="- a\n- b").count(CONCLUDE))

    def test_nothing_to_conclude_asks_for_nothing(self):
        self.expect("an empty week has no conclusions to decide", 0,
                    render(digest(own_lessons=[])).count(CONCLUDE))

    def test_the_owners_box_is_ticked_by_claude_when_he_says(self):
        self.expect("so no review means editing a file", True,
                    "Claude ticks this when the owner says it is done" in render(digest()))


class WhatIsNotDerived(Cases):
    def test_an_unwritten_judgement_says_so_and_never_claims_nothing(self):
        self.expect("an unwritten section says so", True, "was not written" in render(digest()))
        self.expect("and does not claim there was nothing", False, "nothing to report" in render(digest()))
        written = render(digest(), ["I left status.sh alone"])
        self.expect("a supplied judgement is shown", True, "I left status.sh alone" in written)
        self.expect("and the disclaimer goes away", False, "was not written" in written)

    # D54: "removing tooling is as much in scope as adding it", so a week that
    # removed nothing must say so.
    def test_deletion_is_reported_even_when_it_is_zero(self):
        plain = render(digest(lines_added=4174, lines_removed=334))
        self.expect("nothing removed is stated, not omitted", True, "Nothing was removed this week." in plain)
        self.expect("the line counts appear", True, "4174 lines added, 334 removed" in plain)
        self.expect("a deleted file is named", True,
                    "`scripts/old.sh`" in render(digest(files_deleted=["scripts/old.sh"])))


class DocumentReviews(Cases):
    """The programme's docs/1.1: a document change's pull request records each
    material finding in its *Review rounds* section, and the digest collects them."""

    ROUNDS = """- R1 reader — 1.5 *Roles by name* — "you" in a table cell (also truth)
- R1 truth — 1.5 *One fact, one home* — a pointer to the wrong document
- R1 truth — 1.5 *True now* — a field table missing the digest
- R2 truth — 1.5 *True now* — a count left wrong (from a fix to R1 reader truth)
- R2 reader — 1.5 *Brevity* — a duplicated clause (missed in R1)
- R3 none
- owner — none"""

    def test_each_finding_is_counted_by_reviewer_with_its_markers(self):
        c = RoundCount().add(self.ROUNDS)
        # The shared R1 finding is one line, credited to both.
        self.expect("by reviewer", {"reader": 2, "truth": 4}, dict(c.by_reviewer))
        self.expect("found by both", 1, c.both)
        self.expect("from a fix", 1, c.from_fix)
        # Truth shared the R1 reader finding it then faulted the fix to.
        self.expect("a fix faulted by a reviewer who shared the finding is not crossed", 0, c.crossed)
        self.expect("missed by an earlier round", 1, c.missed)
        self.expect("an owner line of none is not a finding", 0, c.owner)

    def test_a_fix_is_crossed_only_when_another_reviewer_faults_it(self):
        c = RoundCount().add("- R2 truth — x — y (from a fix to R1 truth)\n"
                             "- R2 reader — x — z (from a fix)\n"
                             "- R3 reader — x — w (from a fix to owner)\n"
                             "- R3 reader — x — v (from a fix to R1 truth)")
        self.expect("four are from a fix", 4, c.from_fix)
        # Not its own finding's fix, a bare marker or the owner's; only the reader faulting truth's.
        self.expect("crossed", 1, c.crossed)
        self.expect("the summary names it", True, "of them crossed (only other reviewers made the finding fixed): 1" in c.summary())
        self.expect("a malformed marker is not crossed", 0, RoundCount().add("- R2 reader — x — y (from a fix to R2)").crossed)
        shared = RoundCount().add("- R2 reader — x — y (from a fix to R1 truth reader)")
        self.expect("a reviewer who shared the finding fixed is not crossed", 0, shared.crossed)

    def test_a_round_or_owner_with_nothing_is_not_counted(self):
        c = RoundCount().add("- R3 reader — none\n- R3 none\n- owner — not reviewed")
        self.expect("nothing", ({}, 0), (dict(c.by_reviewer), c.owner))
        self.expect("an owner finding counts", 1, RoundCount().add("- owner — a wrong link").owner)

    def test_the_missed_share_and_the_cost_are_counts(self):
        c = RoundCount().add(self.ROUNDS + "\n- R1 cost: reader 60k, 80%; truth 90.5k, 75%")
        self.expect("missed share", "1 of 5 findings missed by an earlier round (20%)",
                    c.missed_share())
        self.expect("cost", "150k tokens, about 50k per material finding; 2 finding(s) in rounds with no cost line", c.cost())
        self.expect("a cost line is not a finding", 5, c.findings)
        self.expect("no findings", "no reviewer findings", RoundCount().missed_share())
        self.expect("no cost lines", "no cost lines", RoundCount().add(self.ROUNDS).cost())

    def test_tokens_are_divided_only_by_the_findings_they_paid_for(self):
        c = RoundCount().add("- R1 reader — x — y\n- R1 cost: reader 100K, 80%")
        c.add("- R1 reader — x — a\n- R1 truth — x — b")
        self.expect("mixed", "100k tokens, about 100k per material finding; "
                    "2 finding(s) in rounds with no cost line", c.cost())
        self.expect("a cost line with no k figure is said", "cost lines with no k figure",
                    RoundCount().add("- R1 cost: reader 60000").cost())
        self.expect("and counted beside one that has", "50k tokens; 1 cost figure(s) not read",
                    RoundCount().add("- R1 cost: reader 50k\n- R2 cost: reader 60000").cost())

    def test_each_note_is_its_own_record(self):
        notes = ("- 2026-09-22, rounds for abc1234:\n  - R1 reader — x — y\n  - R1 cost: reader 50k\n"
                 "- 2026-09-23, rounds for def5678:\n  - R1 reader — x — a\n  - R1 truth — x — b")
        text = render(digest(reviews=[]), notes=notes)
        self.expect("tokens paid for one finding", True,
                    "50k tokens, about 50k per material finding; 2 finding(s) in rounds with no cost line" in text)

    def test_a_week_whose_rounds_found_nothing_still_reports_its_cost(self):
        text = render(digest(reviews=[("o/p", 1, "docs", "- R1 none\n- R1 cost: reader 40k, 90%")]))
        self.expect("cost", True, "Cost: 40k tokens." in text)

    def test_round_lines_at_the_top_level_stay_with_their_note(self):
        notes = ("Before the notes.\n- abc1234 rounds:\n- R1 reader — x — y\n- R1 truth — x — z\n"
                 "- R1 cost: reader 50k, 80%; truth 60k\n- R2 none\n- owner — none\n- def5678 rounds:\n  - R1 none")
        self.expect("records", 3, len(note_records(notes)))
        text = render(digest(reviews=[]), notes=notes)
        self.expect("cost paid for both findings", True,
                    "110k tokens, about 55k per material finding." in text)

    def test_bang_for_buck_is_by_reviewer_and_by_round(self):
        c = RoundCount().add("- R1 reader — x — y (also truth)\n- R1 truth — x — z\n"
                             "- R1 cost: reader 60k, 80%; truth 90k, 75%\n"
                             "- R2 none\n- R2 cost: reader 40k; truth 60k")
        self.expect("value", "by reviewer, a shared finding counting for each: reader 100k for 1 (100k each); "
                    "truth 150k for 2 (75k each). "
                    "By round: R1 150k for 2 (75k each); R2 100k for 0", c.value())
        mixed = RoundCount().add("- R1 reader — x — a\n- R1 truth — x — b\n"
                                 "- R2 Reader — x — c\n- R2 cost: reader 30k; truth 20k; about 5k")
        self.expect("an uncosted round's findings are not charged to another's tokens",
                    "by reviewer, a shared finding counting for each: reader 30k for 1 (30k each); "
                    "truth 20k for 0. By round: R2 55k for 1 (55k each). Not costed: 2 finding(s)",
                    mixed.value())
        self.expect("a figure naming no reviewer is not read", 1, mixed.unread_costs)
        self.expect("nor is a bare figure", 1, RoundCount().add("- R1 cost: 150k").unread_costs)
        text = render(digest(reviews=[("o/p", 1, "docs", "- R1 reader — x — y\n- R1 cost: reader 40k")]))
        self.expect("the digest prints it", True, "**Bang for buck**, by reviewer" in text)
        self.expect("an uncosted record is left out", "no cost lines",
                    RoundCount().add("- R1 reader — x — y").value())
        unfigured = RoundCount().add("- R1 change — x — a\n- R1 cost: reader 100k; truth about 50k")
        self.expect("a reviewer with no figure is said", (0, 1, True),
                    (unfigured.found["change"], unfigured.unfigured,
                     unfigured.value().endswith("By a reviewer with no cost figure: 1 finding(s)")))
        bare = RoundCount().add("- R1 reader — x — y\n- R1 cost: reader 60000")
        self.expect("a cost line with no k figure costs nothing", (0, 1, "cost lines with no k figure"),
                    (bare.costed_findings, bare.uncosted, bare.value()))
        unnamed = RoundCount().add("- R1 reader — x — y\n- R1 cost: about 50k")
        self.expect("an empty reviewer list is not printed", "By round: R1 50k for 1 (50k each). By a reviewer with no cost figure: 1 finding(s)",
                    unnamed.value())

    def test_the_example_in_docs_1_1_counts_as_it_should(self):
        # The record's form is docs/1.1's example; the parser is tested against it.
        doc = (Path(__file__).resolve().parents[3] / "docs" / "1.1-programme-tooling.md").read_text()
        example = re.search(r"```text\n(- R1 reader.*?)```", doc, re.S).group(1)
        c = RoundCount().add(example)
        self.expect("counts",
                    ({"reader": 2, "truth": 3}, 1, 1, 1, 1, 0, 4, 370),
                    (dict(c.by_reviewer), c.both, c.from_fix, c.crossed, c.missed, c.owner,
                     c.findings, c.tokens))

    def test_rounds_in_the_notes_are_counted_for_a_change_with_no_pull_request(self):
        notes = "- 2026-09-22, review rounds for abc1234:\n  - R1 reader — x — y (also truth)\n  - R2 none"
        text = render(digest(reviews=[]), notes=notes)
        self.expect("counted", True, "reader 1, truth 1" in text)

    def test_only_pull_requests_with_the_section_are_collected(self):
        prs = [MergedPullRequest("o/p", 1, "docs", "## Review rounds\n\n" + self.ROUNDS),
               MergedPullRequest("o/p", 2, "code", "Before: x")]
        self.expect("one", [1], [n for _, n, _, _ in review_rounds(prs)])

    def test_none_owed_is_told_apart_from_no_record(self):
        prs = [MergedPullRequest("o/p", 1, "docs", "## Review rounds\n\n" + self.ROUNDS),
               MergedPullRequest("o/p", 2, "report", "## Review rounds\n\nNone owed: a report."),
               MergedPullRequest("o/p", 3, "code", "Before: x"),
               MergedPullRequest("o/p", 4, "bump", "Bumps x", bot=True),
               MergedPullRequest("o/p", 5, "record", "## Review rounds\n\n- None owed: a record"),
               MergedPullRequest("o/p", 6, "empty", "## Review rounds\n\n## Next")]
        self.expect("rounds", [1], [n for _, n, _, _ in review_rounds(prs)])
        self.expect("unrecorded: no section or an empty one, and no bot's", [3, 6],
                    [n for _, n, _ in unrecorded(prs)])
        text = render(digest(reviews=review_rounds(prs), unrecorded=unrecorded(prs)))
        self.expect("named in the digest", True,
                    "Merged with neither *Review rounds* nor `None owed`: o/p#3, o/p#6." in text)
        self.expect("the review of the reviews has a place", True,
                    "### Review of the reviews" in text)

    def test_a_search_that_did_not_answer_is_said_not_read_as_none(self):
        self.expect("unavailable", True,
                    "Not available" in render(digest(reviews=None)))
        self.expect("none merged", True,
                    "No pull request merged this week recorded" in render(digest(reviews=[])))


class ProjectsClosedWithoutLessons(Cases):
    START = "2026-09-21"

    def test_a_project_closed_with_neither_lessons_nor_delegation_is_named(self):
        def closed(n, body, issue_type="Project"):
            return RawIssue(n, f"issue {n}", "CLOSED", body, issue_type, {}, (), None, None,
                            frozenset(), created_at="2026-09-01T00:00:00Z",
                            closed_at="2026-09-22T00:00:00Z")
        found = unlessoned_projects([closed(1, "## Lessons learnt\n\nA lesson."),
                                     closed(2, "## Lessons learnt\n\nDelegated to #9."),
                                     closed(3, "## Requirements\n\nx"),
                                     closed(4, "x", issue_type="Decision")], self.START)
        self.expect("only the project with neither", [3], [n for n, _ in found])


if __name__ == "__main__":
    unittest.main()
