"""R2's grouping and event rules, on fixtures.

The fetching is not tested here; it is `gh` and a live board. What is tested
is the part that used to be spread through `inbox.sh`'s awk and shell: which
remark belongs to which issue, who is held to have typed it, and what counts
as opened or closed inside the window."""

import unittest

from .cases import Cases

from unittest import mock

from board import inbox as inbox_module
from board import sources
from board.inbox import build, read_waiting, render, render_waiting, unanswered, waiting_for_claude
from board.model import RawIssue
from board.sources import Remark, Report

def issue(n, title="t", created=None, closed=None, state="OPEN"):
    return RawIssue(n, title, state, "", "Requirement", {}, (), None, None,
                    frozenset(), frozenset(), frozenset(),
                    created_at=created, closed_at=closed)

SINCE = "2026-09-14T00:00:00Z"



class TheInbox(Cases):

    def test_grouping(self):
        """grouping"""
        remarks = (
            Remark(7, "2026-09-15T09:00", "owner", "a question", False),
            Remark(7, "2026-09-15T10:00", "claude", "an answer", False),
            Remark(9, "2026-09-16T09:00", "deploy", "Shipped in rel-0.8.1", False),
        )
        inbox = build([issue(7, "seven"), issue(9, "nine")], remarks, SINCE)
        self.expect("a thread per issue", 2, len(inbox.threads))
        self.expect("remarks stay with their issue", 2, len(inbox.threads[0].remarks))
        self.expect("the owner's are counted", 1, inbox.from_owner)

    def test_a_deploys_remark_is_labelled_with_the_profiles_marker(self):
        """a deploy's remark carries the technical profile's marker"""
        remarks = (Remark(9, "2026-09-16T09:00", "deploy", "Shipped in rel-0.8.1", False),)
        text = render(build([issue(9, "nine")], remarks, SINCE), colour=False)
        self.expect("the marker", True, "[ship.sh] Shipped in rel-0.8.1" in text)
        self.expect("not a built-in one", False, "[deploy.sh]" in text)

    def test_a_remark_on_an_issue_the_snapshot_does_not_hold_still_arrives(self):
        """a remark on an issue the snapshot does not hold still arrives"""
        # Something said on an issue outside the window's board is still something said.
        inbox = build([], (Remark(404, "2026-09-15T09:00", "owner", "hello", False),), SINCE)
        self.expect("the thread exists", 1, len(inbox.threads))
        self.expect("with no title rather than being dropped", "", inbox.threads[0].title)

    def test_opened_closed_and_both(self):
        """opened, closed, and both"""
        # **Opened *and* closed inside the window needs saying.** Reporting only
        # "opened" reads as still-open, which after a week away is the one thing
        # somebody would act on wrongly.
        issues = [
            issue(1, "opened only", created="2026-09-15T00:00:00Z"),
            issue(2, "closed only", created="2026-09-01T00:00:00Z", closed="2026-09-15T00:00:00Z"),
            issue(3, "both", created="2026-09-15T00:00:00Z", closed="2026-09-16T00:00:00Z"),
            issue(4, "neither", created="2026-09-01T00:00:00Z"),
        ]
        inbox = build(issues, (), SINCE)
        self.expect("three events, not four", 3, len(inbox.events))
        self.expect("opened", "opened", inbox.events[0].what)
        self.expect("closed", "closed", inbox.events[1].what)
        self.expect("both is said as both", "opened+closed", inbox.events[2].what)

    def test_rendering(self):
        """rendering"""
        out = render(build([issue(7, "seven")],
                           (Remark(7, "2026-09-15T09:00", "owner", "mine", False),),
                           SINCE), colour=False)
        self.expect("the owner's remark is marked", True, "> 2026-09-15T09:00  mine" in out)
        self.expect("a quiet window says so", True,
              "nothing opened or closed" in render(build([], (), SINCE), colour=False))


def say(n, when, who, text="a comment", created=None):
    return Remark(n, when, who, text, False, created or when + ":00")


class WaitingForClaude(Cases):
    """#454. The rules, as the owner stated them on 2026-10-01: a comment of his
    is open until a later comment from Claude on the same issue, automatic
    comments do not count as an answer, and there is no time limit."""

    def test_unanswered_and_answered(self):
        self.expect("a question alone is open", 1,
                    len(unanswered((say(7, "2026-10-01T09:00", "owner"),))))
        self.expect("a later answer closes it", 0, len(unanswered((
            say(7, "2026-10-01T09:00", "owner"), say(7, "2026-10-01T10:00", "claude")))))
        self.expect("an answer before the question does not", 1, len(unanswered((
            say(7, "2026-10-01T08:00", "claude"), say(7, "2026-10-01T09:00", "owner")))))
        self.expect("an answer on another issue does not", 1, len(unanswered((
            say(7, "2026-10-01T09:00", "owner"), say(8, "2026-10-01T10:00", "claude")))))

    def test_a_reply_in_the_same_second_counts_as_an_answer(self):
        self.expect("nothing can order them", 0, len(unanswered((
            say(7, "2026-10-01T09:00", "owner"), say(7, "2026-10-01T09:00", "claude")))))

    def test_asked_again_after_an_answer(self):
        got = unanswered((say(7, "2026-10-01T09:00", "owner", "first"),
                          say(7, "2026-10-01T10:00", "claude"),
                          say(7, "2026-10-01T11:00", "owner", "second")))
        self.expect("only the later one is open", ["second"], [r.text for r in got])

    def test_an_automatic_comment_is_not_an_answer(self):
        for who in ("deploy", "bot"):
            self.expect(f"{who} after a question", 1, len(unanswered((
                say(7, "2026-10-01T09:00", "owner"), say(7, "2026-10-01T10:00", who)))))

    def test_there_is_no_time_limit_after_the_floor(self):
        # The floor, 2026-08-25, is the only limit: a to-do is not forgotten by age.
        self.expect("a question from the first day after the floor is still open", 1,
                    len(unanswered((say(7, "2026-08-26T09:00", "owner"),))))

    def test_an_edit_does_not_reopen_an_answered_comment(self):
        # `when` is the updated time; the order is by when each was first written.
        owner = say(7, "2026-10-02T09:00", "owner", created="2026-10-01T09:00:00")
        claude = say(7, "2026-10-01T10:00", "claude")
        self.expect("an edited question is still answered", 0, len(unanswered((owner, claude))))

    def test_a_closed_issue_or_merged_pull_request_has_nothing_waiting(self):
        r = (say(7, "2026-10-01T09:00", "owner"), say(8, "2026-10-01T09:00", "owner"),
             say(9, "2026-10-01T09:00", "owner"))
        issues = [issue(7, state="OPEN"), issue(8, state="CLOSED"), issue(9, state="MERGED")]
        self.expect("only the open one", [7], [t.number for t in waiting_for_claude(issues, r)])

    def test_each_shows_the_first_words(self):
        text = render_waiting(waiting_for_claude(
            [issue(7, "seven")], (say(7, "2026-10-01T09:00", "owner", "x" * 400),)), colour=False)
        self.expect("cut at 120 characters", True, "x" * 120 in text and "x" * 121 not in text)

    def test_nothing_waiting_says_so(self):
        self.expect("a sentence, not an empty list", "nothing from the owner is waiting for an answer",
                    render_waiting((), colour=False))


def comment_world(rows):
    """Remarks and open issues for `rows` of (issue, minutes after 2026-10-01T00:00, text)."""
    remarks = tuple(say(n, f"2026-10-01T{m // 60:02d}:{m % 60:02d}", "owner", text)
                    for n, m, text in rows)
    return [issue(n, f"title {n}") for n in sorted({r[0] for r in rows})], remarks


def shown(text):
    return [l for l in text.splitlines() if l.startswith("  > ")]


class TheTodoList(Cases):
    """#455-R1, R4, R10: the floor, the cap and what a line says (R15 of
    delphside/programme#176; the owner's answers of 2026-11-13)."""

    def test_comments_before_claudes_account_are_not_to_dos(self):
        """S44: the floor is 2026-08-25, to the second, and a setting."""
        remarks = (say(7, "2026-08-24T23:59", "owner", "before"),
                   say(7, "2026-08-25T00:00", "owner", "at the floor"),
                   say(7, "2026-08-25T00:01", "owner", "after"))
        threads = waiting_for_claude([issue(7)], remarks)
        self.expect("the floor comment and the one after, not the one before",
                    ["at the floor", "after"], [r.text for r in threads[0].remarks])

        import tempfile, pathlib
        from board.tests.profiles import CONFIG, using
        with tempfile.TemporaryDirectory() as d:
            moved = pathlib.Path(d) / "programme.toml"
            moved.write_text(CONFIG.read_text().replace('to_do_floor = "2026-08-25"',
                                                        'to_do_floor = "2026-08-25T00:01"'))
            with using(config=moved):
                threads = waiting_for_claude([issue(7)], remarks)
        self.expect("the floor is the setting's, not a built-in date", ["after"],
                    [r.text for r in threads[0].remarks])

    def test_an_edit_does_not_bring_back_a_comment_from_before_the_floor(self):
        edited = Remark(7, "2026-10-01T09:00", "owner", "old", False, "2026-08-01T09:00:00")
        self.expect("it was made before the floor", (), unanswered((edited,)))

    def test_cap_bounds_lines_and_counts_the_rest(self):
        """S47: the cap counts comments; the oldest show, oldest first."""
        rows = [(1, m, f"c{m}") for m in range(1, 25)]           # 24 on issue 1, minutes 1..24
        rows += [(n, 24 + k, f"c{24 + k}") for k, n in enumerate((2, 2, 3, 4, 5, 6), 1)]
        issues, remarks = comment_world(rows)
        text = render_waiting(waiting_for_claude(issues, remarks), colour=False)
        lines = shown(text)
        self.expect("twelve lines, not twelve issues", 12, len(lines))
        self.expect("the oldest twelve, oldest first", [f"c{m}" for m in range(1, 13)],
                    [l.split("  ")[-1] for l in lines])
        left = rows[12:]
        self.expect("the rest, counted from the world", f"...{len(left)} more on "
                    f"{len({r[0] for r in left})} issues (board-inbox.py --open --all)",
                    text.splitlines()[-1])
        self.expect("uncapped on request", 30,
                    len(shown(render_waiting(waiting_for_claude(issues, remarks), colour=False, limit=99))))

        issues, remarks = comment_world([(1, m, f"c{m}") for m in range(1, 13)])
        text = render_waiting(waiting_for_claude(issues, remarks), colour=False)
        self.expect("exactly twelve: twelve lines and no further line", (12, 12),
                    (len(shown(text)), len(text.splitlines())))
        issues, remarks = comment_world([(1, m, f"c{m}") for m in range(1, 13)] + [(2, 13, "c13")])
        text = render_waiting(waiting_for_claude(issues, remarks), colour=False)
        self.expect("thirteen: twelve lines and the count", (12, "...1 more on 1 issue (board-inbox.py --open --all)"),
                    (len(shown(text)), text.splitlines()[-1]))

    def test_to_do_line_shows_when_the_comment_was_made(self):
        """S52: not when it was edited."""
        edited = Remark(7, "2026-10-09T17:30", "owner", "asked", False, "2026-10-01T09:15:42")
        text = render_waiting(waiting_for_claude([issue(7, "seven")], (edited,)), colour=False)
        self.expect("the creation time, to the minute", True, "2026-10-01T09:15  " in text)
        self.expect("not the edit's", False, "2026-10-09" in text)

    def test_a_line_names_its_issue_title_and_diff(self):
        diff = Remark(8, "2026-10-01T09:00", "owner", "rename this", True, "2026-10-01T09:00:00")
        text = render_waiting(waiting_for_claude([issue(8, "the pull request")], (diff,)), colour=False)
        self.expect("number, title, diff mark and words", True,
                    "#8  the pull request  (review) rename this" in text)


class FakeGitHub:
    """`gh api` as the board reads it: canned rows in place of jq's output."""

    def __init__(self, issues, comments, diff_comments, pull_requests=()):
        self.issues, self.comments, self.diff_comments = issues, comments, diff_comments
        self.pull_requests = set(pull_requests)
        self.calls = []
        self.real = __import__("subprocess").run

    def id_of(self, row):
        return 1000 + (self.comments + self.diff_comments).index(row)

    def run(self, args, **kwargs):
        if args[0] != "gh":
            return self.real(args, **kwargs)
        path = args[2].split("?")[0]
        self.calls.append(path)
        rows, import_json = [], False
        tail = path.split("repos/fakeorg/widget/")[-1]
        if tail == "issues/comments":
            rows = self.comments
        elif tail == "pulls/comments":
            rows = self.diff_comments
        elif tail.endswith("/comments") and tail.startswith("issues/"):
            rows = [r for r in self.comments if r[0] == int(tail.split("/")[1])]
        elif tail.endswith("/comments") and tail.startswith("pulls/"):
            rows = [r for r in self.diff_comments if r[0] == int(tail.split("/")[1])]
        elif tail.startswith("issues/"):
            n = int(tail.split("/")[1])
            node = {"number": n, "title": self.issues[n][0], "state": self.issues[n][1]}
            if n in self.pull_requests:
                node["pull_request"] = {}
            return mock.Mock(returncode=0, stdout=__import__("json").dumps(node), stderr="")
        out = "".join("\t".join([str(r[0]), r[1][:16], "owner", r[2], r[1], str(self.id_of(r))]) + "\n"
                      for r in rows)
        return mock.Mock(returncode=0, stdout=out, stderr="")


class OneIssueFollowsTheBoard(Cases):

    def read(self, world, issue_number=None):
        snapshot = lambda issues: mock.Mock(issues=tuple(
            inbox_module.RawIssue(n, t, st, "", "Requirement", {}, (), None, None, frozenset())
            for n, (t, st) in issues.items()))
        with mock.patch.object(sources.subprocess, "run", world.run), \
             mock.patch.object(inbox_module, "fetch",
                               lambda states, **kw: snapshot({n: v for n, v in world.issues.items()
                                                              if v[1] == states})):
            return render_waiting(read_waiting(issue_number), colour=False, ids=True)

    def test_one_issue_follows_the_same_rules_and_reads_as_the_board(self):
        """S46: the open-issues rule and the diff comments, on both paths."""
        world = FakeGitHub(
            issues={5: ("an open issue", "OPEN"), 6: ("a closed issue", "CLOSED"),
                    8: ("a pull request", "OPEN")},
            comments=[(5, "2026-10-01T09:00:00", "plain ask"), (6, "2026-10-01T09:00:00", "closed ask"),
                      (8, "2026-10-01T10:00:00", "conversation ask")],
            diff_comments=[(8, "2026-10-01T11:00:00", "diff ask")],
            pull_requests=[8])
        self.expect("a closed issue gives nothing", "nothing from the owner is waiting for an answer",
                    self.read(world, 6))
        one = self.read(world, 8)
        board = self.read(world)
        self.expect("the diff comment is listed, with the title", True,
                    "#8  a pull request  (review) diff ask" in one)
        self.expect("and so is the conversation", True, "conversation ask" in one)
        self.expect("every line of the one-issue read is on the board-wide read", [],
                    [l for l in shown(one) if l not in shown(board)])
        self.expect("the board-wide read has no closed issue's comment", False, "closed ask" in board)

    def test_a_plain_issue_is_not_asked_for_diff_comments(self):
        world = FakeGitHub({5: ("an issue", "OPEN")}, [(5, "2026-10-01T09:00:00", "ask")], [])
        self.read(world, 5)
        self.expect("pulls/5/comments does not exist for an issue", False,
                    any("pulls/5/comments" in c for c in world.calls))


class FlagsThatQualifyOpen(Cases):

    def board_inbox(self, *args):
        import os, pathlib, stat, subprocess, tempfile
        script = pathlib.Path(__file__).resolve().parents[1] / "board-inbox.py"
        with tempfile.TemporaryDirectory() as d:
            gh = pathlib.Path(d) / "gh"
            gh.write_text("#!/bin/sh\necho 'no network in tests' >&2\nexit 1\n")
            gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
            return subprocess.run([str(script), *args], capture_output=True, text=True,
                                  env={**os.environ, "PATH": f"{d}:{os.environ['PATH']}"})

    def test_issue_or_all_without_open_is_refused(self):
        """S51: refused naming the flag, not ignored; then accepted with --open."""
        for args, flag in ((("--issue", "5"), "--issue"), (("--all",), "--all"), (("--ids",), "--ids")):
            run = self.board_inbox(*args)
            self.expect(f"{flag} alone: usage error", 2, run.returncode)
            self.expect(f"{flag} alone: names the missing flag", True, f"{flag} needs --open" in run.stderr)
        for args in (("--open", "--issue", "5"), ("--open", "--all")):
            run = self.board_inbox(*args)
            self.expect(f"{' '.join(args)}: accepted, and failing on the read it was refused", 1, run.returncode)
            self.expect("with the read's message", True, "board-inbox:" in run.stderr)


class WhoTypedIt(Cases):
    """sources.comment_jq, run through the real jq on canned comments. The rule
    lived untested in a string, which is how a bot's comment read as the
    owner's until 2026-09-27."""

    def who(self, login, kind, body="a comment"):
        import json, shutil, subprocess
        if not shutil.which("jq"):
            self.skipTest("jq is not installed")
        from board.sources import comment_jq
        comment = [{"issue_url": "https://api.github.com/repos/o/r/issues/7", "updated_at": "2026-09-27T10:00:00Z", "created_at": "2026-09-26T08:00:00Z",
                    "user": {"login": login, "type": kind}, "body": body}]
        out = subprocess.run(["jq", "-r", comment_jq("issue_url")], input=json.dumps(comment),
                             capture_output=True, text=True, check=True).stdout
        return out.split("\t")[2]

    def test_the_row_carries_when_it_was_first_written(self):
        import json, shutil, subprocess
        if not shutil.which("jq"):
            self.skipTest("jq is not installed")
        from board.sources import comment_jq
        c = [{"issue_url": "https://x/issues/7", "updated_at": "2026-09-27T10:00:00Z",
              "created_at": "2026-09-26T08:00:05Z", "user": {"login": "u", "type": "User"}, "body": "b"}]
        row = subprocess.run(["jq", "-r", comment_jq("issue_url")], input=json.dumps(c),
                             capture_output=True, text=True, check=True).stdout.rstrip("\n").split("\t")
        self.expect("a fifth column, to the second", "2026-09-26T08:00:05", row[4])

    def test_each_account_is_read_as_what_it_is(self):
        self.expect("the owner", "owner", self.who("fake-owner", "User"))
        self.expect("Claude", "claude", self.who("fake-owner-claude", "User"))
        self.expect("a workflow", "bot", self.who("github-actions[bot]", "Bot"))
        self.expect("Dependabot", "bot", self.who("dependabot[bot]", "Bot"))
        self.expect("deploy.sh's announcement", "deploy",
                    self.who("fake-owner-claude", "User", "Shipped in rel-0.9.0"))

    def test_a_cloud_session_posting_as_the_owner_is_claude(self):
        # #455 R9: a cloud session posts through the GitHub connector as the
        # owner's account, and its comments end with the Claude Code footer.
        footer = "Triage.\n\n---\n_Generated by [Claude Code](https://claude.ai/code)_"
        self.expect("the footer marks it as Claude's", "claude", self.who("fake-owner", "User", footer))
        self.expect("a mention of Claude Code is still his", "owner",
                    self.who("fake-owner", "User", "Is Claude Code generating these?"))
        self.expect("whitespace after the footer is still Claude's", "claude",
                    self.who("fake-owner", "User", footer + "\n\n  "))
        self.expect("a reply written below a footer is his", "owner",
                    self.who("fake-owner", "User", "_Generated by [Claude Code](u)_\nmy reply"))
        self.expect("a quoted footer is his", "owner",
                    self.who("fake-owner", "User", "He wrote:\n> _Generated by [Claude Code](u)_"))


class Reports(Cases):
    """Owner, 2026-09-27: "can you add a hook so you notice a new report?" The
    workflows report by writing an issue, which leaves no comment behind."""

    def test_a_bot_is_not_the_owner(self):
        # Everything not Claude's account was the owner's until 2026-09-27.
        inbox = build([issue(393)], (Remark(393, "2026-09-19T10:00", "bot", "Dependabot will rebase", False),), SINCE)
        self.expect("a bot's comment is not counted as his", 0, inbox.from_owner)
        self.expect("and is shown as a bot's", True, "[bot] Dependabot will rebase" in render(inbox, colour=False))

    def test_a_report_has_its_own_section(self):
        inbox = build([], (), SINCE, (Report(384, "Dependency advisories need review", "OPEN", "2026-09-19T19:36"),))
        text = render(inbox, colour=False)
        self.expect("under its heading", True, "REPORTS FROM THE SCHEDULED WORKFLOWS" in text)
        self.expect("named, with its state", True, "#384   open" in text and "Dependency advisories" in text)

    def test_a_cleared_report_is_news_too(self):
        text = render(build([], (), SINCE, (Report(384, "advisories", "CLOSED", "2026-09-20T06:15"),)), colour=False)
        self.expect("a closed report is listed as closed", True, "#384   closed" in text)

    def test_no_report_says_so(self):
        text = render(build([], (), SINCE), colour=False)
        self.expect("rather than an empty heading", True, "no report opened, updated or closed" in text)


class TheNotesForTheLocalSession(Cases):
    """`--notes`: what web sessions left on the notes issue in the window."""

    def read(self, issues, comments, since="2026-11-17T00:00:00Z"):
        def fake(repo, number, since_iso):
            return tuple(sources.Note(number, c, a, t, f"https://x/{number}#{i}")
                         for i, (c, a, t) in enumerate(comments))
        with mock.patch.object(inbox_module, "open_issue_titled",
                               lambda repo, title: issues.get(title)), \
             mock.patch.object(inbox_module, "comments_with_authors", fake), \
             mock.patch.object(inbox_module.profile, "repository_name", lambda: "fakeorg/widget"):
            return inbox_module.render_notes(inbox_module.read_notes(since))

    def test_notes_in_the_window_one_line_each(self):
        text = self.read({inbox_module.NOTES_TITLE: {"number": 643}},
                         [("2026-11-20T10:00:00Z", "pat", "Finished the thing\nand more"),
                          ("2026-11-10T10:00:00Z", "pat", "too old, though edited since")])
        self.expect("one line", 1, len(text.splitlines()))
        self.expect("date, author, issue, first line, url", True,
                    "2026-11-20T10:00  pat  #643  Finished the thing  https://x/643#0" in text)

    def test_no_notes_in_the_window_prints_nothing(self):
        self.expect("nothing", "", self.read({inbox_module.NOTES_TITLE: {"number": 643}}, []))

    def test_no_notes_issue_prints_nothing(self):
        self.expect("nothing", "", self.read({}, [("2026-11-20T10:00:00Z", "pat", "x")]))

    def test_a_long_first_line_is_cut(self):
        text = self.read({inbox_module.NOTES_TITLE: {"number": 1}},
                         [("2026-11-20T10:00:00Z", "pat", "w" * 500)])
        self.expect("cut with an ellipsis", True, "…" in text and "w" * 200 not in text)

    def test_a_failed_read_exits_one_with_the_reason_on_stderr(self):
        run = FlagsThatQualifyOpen().board_inbox("--notes")
        self.expect("status", 1, run.returncode)
        self.expect("the reason", True, "board-inbox: " in run.stderr)
        self.expect("nothing on stdout", "", run.stdout)


if __name__ == "__main__":
    unittest.main()

