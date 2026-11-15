"""The check before Claude comments (#454 R5, #455 R5 and R8; R15 of
delphside/programme#176), on a stub in place of GitHub.

What is tested is which tool inputs it reacts to, what it decides and says, and
when a retry is allowed. Whether an issue has unanswered comments is
`test_inbox.py`'s. Each assertion is on what Claude Code acts on: the hook's
exit status and its decision field (`permissionDecision`), and the reason."""

import json
import os
import stat
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from .cases import Cases
from .profiles import CONFIG

HOOK = Path(__file__).resolve().parents[3] / ".claude" / "hooks" / "comment-check.sh"
T0 = 1_800_000_000

ASK = ["  > 2026-10-01T09:00  #7  seven  a question  (comment 101)"]


def bash(command, session="s1"):
    return {"session_id": session, "tool_name": "Bash", "tool_input": {"command": command}}


def mcp(tool, session="s1", **fields):
    return {"session_id": session, "tool_name": f"mcp__github__{tool}", "tool_input": fields}


class Check(Cases):
    """One scratch directory holds the stub's output and the hook's markers."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.stub = Path(self.dir.name) / "inbox"
        self.say(ASK)
        self.bin = Path(self.dir.name) / "bin"
        self.bin.mkdir()
        self.gh(7)

    def gh(self, number):
        """A stub `gh` that answers `gh pr view` with a number, or fails when None."""
        script = f"#!/bin/sh\necho {number}\n" if number else "#!/bin/sh\necho 'no pull request' >&2\nexit 1\n"
        (self.bin / "gh").write_text(script)
        (self.bin / "gh").chmod(0o755)

    def say(self, lines, status=0, error=""):
        """What the stub board-inbox.py prints, and how it exits."""
        body = "\n".join(f"echo '{line}'" for line in lines)
        self.stub.write_text(f"#!/bin/sh\n{body}\necho '{error}' >&2\nexit {status}\n")
        self.stub.chmod(self.stub.stat().st_mode | stat.S_IEXEC)

    def run_hook(self, data, now=T0, **env):
        run = subprocess.run([str(HOOK)], input=json.dumps(data) if isinstance(data, dict) else data,
                             capture_output=True, text=True,
                             env={**os.environ, "COMMENT_CHECK_INBOX": str(self.stub),
                                  "COMMENT_CHECK_NOW": str(now), "TMPDIR": self.dir.name,
                                  "PATH": f"{self.bin}:{os.environ['PATH']}", **env})
        return run

    def decision(self, run):
        """'deny', or 'allow' for a run that did not deny, and the reason."""
        self.assertEqual(0, run.returncode, "a hook never fails the tool call")
        if not run.stdout.strip():
            return "allow", ""
        out = json.loads(run.stdout)["hookSpecificOutput"]
        self.assertEqual("PreToolUse", out["hookEventName"])
        if out.get("permissionDecision") == "deny":
            return "deny", out["permissionDecisionReason"]
        return "allow", out.get("additionalContext", "")

    def denied(self, data, now=T0, **env):
        return self.decision(self.run_hook(data, now, **env))[0] == "deny"

    # -- what it reacts to (S48) ------------------------------------------------

    COVERED_BASH = (
        "gh issue comment 7 --body hi",
        "gh issue comment #7 --body-file /tmp/x",
        "gh issue comment --body hi 7",
        "gh issue comment 7 -R fakeorg/widget -b hi",
        "gh issue comment https://github.com/fakeorg/widget/issues/7 -F y",
        "gh pr comment 7 --body hi",
        "gh pr comment 7 --body=hi",
        "gh issue close 7 --comment done",
        "gh issue close 7 -c done",
        "gh pr close 7 --comment done",
        "gh pr review 7 --approve --body ok",
        "gh pr review 7 --request-changes -b no",
        "gh pr review --comment -b hm 7",
        "gh pr comment --body hi",
        "gh pr review --approve --body ok",
        "GH_REPO=fakeorg/widget gh issue comment 7 --body hi",
        "gh api -X POST repos/{owner}/{repo}/issues/7/comments -f body=x",
        "gh api -X POST repos/fakeorg/widget/issues/7/comments -f body=x",
        "gh api repos/fakeorg/widget/issues/7/comments -f body=x",
        "gh api --method POST /repos/fakeorg/widget/pulls/7/comments -f body=x",
        "gh api -X POST repos/fakeorg/widget/pulls/7/reviews -f event=COMMENT -f body=x",
        "gh api -X POST repos/fakeorg/widget/pulls/7/comments/55/replies -f body=x",
        "cd x && gh issue comment 7 -F y",
        "FOO=1 gh issue comment 7 --body hi; echo done",
        "gh issue comment 7 --body \"$(cat <<'EOF'\nreply\nEOF\n)\"",
    )

    NOT_COVERED_BASH = (
        "gh issue close 7",
        "gh pr close 7",
        "gh pr review 7 --approve",
        "gh issue comment 7 --edit-last --body fix",
        "gh api -X PATCH repos/fakeorg/widget/issues/comments/55 -f body=x",
        "gh api -X POST repos/fakeorg/widget/pulls/7/reviews -f body=x",
        "gh api repos/fakeorg/widget/issues/7/comments",
        "gh api -X GET repos/fakeorg/widget/issues/7/comments",
        "gh issue view 7",
        "gh issue view 7 --comments",
        "gh pr view 7",
        "gh issue create --title t --body hi",
        "gh pr create --title t --body \"see gh issue comment 7\"",
        "echo gh issue comment 7 --body hi",
        "git commit -m 'gh issue comment 7'",
        "cat <<'EOF'\ngh issue comment 7 --body hi\nEOF",
        "gh issue comment --body hi",
        "ls -l",
    )

    def test_comment_check_fires_on_every_post_and_no_read(self):
        for n, command in enumerate(self.COVERED_BASH):
            self.expect(f"denies: {command!r}", True, self.denied(bash(command, f"covered-{n}")))
        for command in self.NOT_COVERED_BASH:
            self.expect(f"lets through: {command!r}", "allow", self.decision(self.run_hook(bash(command)))[0])
            self.expect(f"says nothing: {command!r}", "", self.run_hook(bash(command)).stdout)

    def test_the_post_on_another_issue_is_the_issue_it_names(self):
        # The comment about issue 7 is posted on issue 9: the stub is asked for 9.
        self.stub.write_text('#!/bin/sh\necho "args: $*" >&2\n[ "$2" = "--issue" ] && [ "$3" = "9" ] '
                             '&& echo "  > 2026-10-01T09:00  #9  nine  asked  (comment 5)"\nexit 0\n')
        self.stub.chmod(self.stub.stat().st_mode | stat.S_IEXEC)
        _, reason = self.decision(self.run_hook(bash("gh issue comment 9 --body 'see #7'")))
        self.expect("asked about 9", True, "#9" in reason)

    def test_a_post_with_no_number_is_the_branchs_pull_request(self):
        self.gh(9)
        self.stub.write_text('#!/bin/sh\n[ "$3" = "9" ] && echo "  > 2026-10-01T09:00  #9  nine  asked  (comment 5)"\nexit 0\n')
        self.stub.chmod(0o755)
        for n, command in enumerate(("gh pr comment --body hi", "gh pr review -c -b hi")):
            _, reason = self.decision(self.run_hook(bash(command, f"branch-{n}")))
            self.expect(f"{command!r} asks about 9", True, "#9" in reason)

    def test_a_branch_with_no_pull_request_lets_the_post_through_and_says_so(self):
        self.gh(None)
        verdict, said = self.decision(self.run_hook(bash("gh pr comment --body hi")))
        self.expect("allowed", "allow", verdict)
        self.expect("saying it could not read", True, "Could not read" in said)

    def test_a_branch_name_is_resolved_by_gh_pr_view_in_the_inputs_cwd(self):
        where = Path(self.dir.name) / "worktree"
        where.mkdir()
        (self.bin / "gh").write_text(f'#!/bin/sh\necho "$*|$PWD" > "{self.dir.name}/gh-args"\necho 7\n')
        (self.bin / "gh").chmod(0o755)
        for command in ("gh pr comment my-branch --body hi", "gh pr review my-branch -c -b hi"):
            data = {**bash(command, f"b-{command[3:9]}"), "cwd": str(where)}
            self.expect(f"{command!r} is denied for #7", True, "#7" in self.decision(self.run_hook(data))[1])
            self.expect("by the view of the word, in the cwd",
                        f"pr view my-branch --json number -q .number|{where.resolve()}",
                        (Path(self.dir.name) / "gh-args").read_text().strip())
        self.gh(None)
        verdict, said = self.decision(self.run_hook(bash("gh pr comment no-such --body hi", "nb")))
        self.expect("a word gh cannot find is allowed", "allow", verdict)
        self.expect("saying it could not read", True, "Could not read" in said)

    def test_the_hook_gives_itself_one_deadline(self):
        slow = '#!/bin/sh\nsleep 5\necho 7\n'
        (self.bin / "gh").write_text(slow)
        (self.bin / "gh").chmod(0o755)
        start = time.monotonic()
        verdict, said = self.decision(self.run_hook(bash("gh pr comment --body hi"), COMMENT_CHECK_SECONDS="1"))
        self.expect("a slow gh is allowed", "allow", verdict)
        self.expect("with the note", True, "Could not read" in said)
        self.expect("inside the deadline, not the subprocess's own limit", True, time.monotonic() - start < 4)
        self.gh(7)
        self.stub.write_text("#!/bin/sh\nsleep 5\necho '%s'\n" % ASK[0])
        self.stub.chmod(0o755)
        start = time.monotonic()
        verdict, said = self.decision(self.run_hook(bash("gh issue comment 7 --body hi"), COMMENT_CHECK_SECONDS="2"))
        self.expect("a slow board-inbox.py is allowed", "allow", verdict)
        self.expect("with the note", True, "Could not read" in said)
        self.expect("at the deadline", True, time.monotonic() - start < 4.5)

    def test_gh_repo_names_the_repository_the_post_goes_to(self):
        other = "gh issue comment 7 --body hi"
        self.expect("GH_REPO in the environment", "allow", self.decision(
            self.run_hook(bash(other), GH_REPO="other/repo"))[0])
        self.expect("GH_REPO before the command", "allow", self.decision(
            self.run_hook(bash("GH_REPO=other/repo " + other)))[0])
        self.expect("GH_REPO as a URL", "allow", self.decision(
            self.run_hook(bash(other), GH_REPO="https://github.com/other/repo"))[0])
        self.expect("without the branch's pull request being read", "", self.run_hook(
            bash("gh pr comment --body hi"), GH_REPO="other/repo").stdout)
        self.expect("the application's own", "deny", self.decision(
            self.run_hook(bash(other, "mine"), GH_REPO="fakeorg/widget"))[0])

    def test_a_post_to_another_repository_is_not_checked_here(self):
        self.expect("-R names another repository", "allow", self.decision(self.run_hook(
            bash("gh issue comment https://github.com/other/repo/issues/7 --body hi")))[0])
        self.expect("so does an MCP input", "allow", self.decision(self.run_hook(
            mcp("add_issue_comment", owner="other", repo="repo", issue_number=7, body="hi")))[0])

    # -- the MCP tools, and TT10 -------------------------------------------------

    MCP_POSTS = (
        mcp("add_issue_comment", owner="fakeorg", repo="widget", issue_number=7, body="hi"),
        mcp("add_reply_to_pull_request_comment", owner="fakeorg", repo="widget", pullNumber=7,
            commentId=55, body="hi"),
        mcp("pull_request_review_write", method="create", owner="fakeorg", repo="widget",
            pullNumber=7, body="hi", event="COMMENT"),
        mcp("pull_request_review_write", method="submit_pending", owner="fakeorg", repo="widget",
            pullNumber=7, body="hi", event="APPROVE"),
        # it posts the pending comments, so the body does not matter
        mcp("pull_request_review_write", method="submit_pending", owner="fakeorg", repo="widget",
            pullNumber=7, event="APPROVE"),
        mcp("pull_request_review_write", method="create", owner="fakeorg", repo="widget",
            pullNumber=7, event="COMMENT"),
    )

    MCP_LET_THROUGH = (
        mcp("add_issue_comment", owner="fakeorg", repo="widget", issue_number=7, reaction="+1"),
        mcp("add_issue_comment", owner="fakeorg", repo="widget", issue_number=7, body="  "),
        mcp("update_issue_comment", owner="fakeorg", repo="widget", comment_id=55, body="hi"),
        mcp("add_comment_to_pending_review", owner="fakeorg", repo="widget", pullNumber=7,
            path="a.py", body="hi"),
        mcp("pull_request_review_write", method="create", owner="fakeorg", repo="widget",
            pullNumber=7, body="hi"),
        mcp("pull_request_review_write", method="delete_pending", owner="fakeorg", repo="widget",
            pullNumber=7),
        mcp("pull_request_read", owner="fakeorg", repo="widget", pullNumber=7, method="get"),
        {"session_id": "s1", "tool_name": "Edit", "tool_input": {"command": "gh issue comment 7 --body x"}},
    )

    def test_comment_check_fires_on_every_post_and_no_read_for_the_mcp_tools(self):
        for n, data in enumerate(self.MCP_POSTS):
            sid = f"{n}-" + data["tool_name"] + str(data["tool_input"].get("method"))
            self.expect(f"denies {sid}", True, self.denied({**data, "session_id": sid}))
        for data in self.MCP_LET_THROUGH:
            self.expect(f"lets through {data['tool_name']} {data['tool_input']}", "",
                        self.run_hook(data).stdout)

    def test_stub_comment_check_denies_once_then_allows_each_hook_input(self):
        """The hook invoked directly with piped hook-input JSON and a stub in place
        of GitHub (not TT10, which runs against the real repositories): denied
        once with the comment, then allowed, for a Bash input and for each MCP
        comment tool."""
        inputs = [bash("gh issue comment 7 --body hi")] + list(self.MCP_POSTS)
        for n, data in enumerate(inputs):
            data = {**data, "session_id": f"tt10-{n}"}
            first = self.decision(self.run_hook(data))
            self.expect(f"input {n}: first attempt denied", "deny", first[0])
            self.expect(f"input {n}: with the comment", True, "a question" in first[1])
            self.expect(f"input {n}: retry allowed", "allow", self.decision(self.run_hook(data, T0 + 30))[0])

    # -- deny once (S49) ---------------------------------------------------------

    def test_comment_check_denies_once_then_allows_a_retry_within_ten_minutes(self):
        post = bash("gh issue comment 7 --body hi")
        first = self.decision(self.run_hook(post))
        self.expect("the first attempt is denied", "deny", first[0])
        self.expect("with the comment as the reason", True, "a question" in first[1])
        self.expect("it says who and how long", True, "Pat" in first[1] and "10 minutes" in first[1])
        self.expect("retry at 9 min 59 s", "allow", self.decision(self.run_hook(post, T0 + 599))[0])
        self.expect("retry at 10 min", "allow", self.decision(self.run_hook(post, T0 + 600))[0])
        self.expect("retry at 10 min 01 s", "deny", self.decision(self.run_hook(post, T0 + 601))[0])

    def test_the_window_is_the_settings_not_a_built_in(self):
        shorter = Path(self.dir.name) / "programme.toml"
        shorter.write_text(CONFIG.read_text().replace("retry_minutes = 10", "retry_minutes = 1"))
        post = bash("gh issue comment 7 --body hi")
        self.run_hook(post, PROGRAMME_CONFIG=str(shorter))
        self.expect("59 s", "allow", self.decision(self.run_hook(post, T0 + 59, PROGRAMME_CONFIG=str(shorter)))[0])
        self.expect("61 s", "deny", self.decision(self.run_hook(post, T0 + 61, PROGRAMME_CONFIG=str(shorter)))[0])

    def test_the_marker_is_of_the_kind_of_post_as_well(self):
        self.run_hook(bash("gh issue comment 7 --body hi"))
        self.expect("a close with a comment is another post", "deny", self.decision(
            self.run_hook(bash("gh issue close 7 --comment done"), T0 + 5))[0])
        self.expect("and its own retry is allowed", "allow", self.decision(
            self.run_hook(bash("gh issue close 7 --comment done"), T0 + 10))[0])
        self.expect("a review is another", "deny", self.decision(
            self.run_hook(mcp("pull_request_review_write", method="submit_pending", owner="fakeorg",
                              repo="widget", pullNumber=7, event="COMMENT"), T0 + 15))[0])

    def test_without_a_session_id_the_marker_is_the_hooks_parents(self):
        post = {"tool_name": "Bash", "tool_input": {"command": "gh issue comment 7 --body hi"}}
        self.run_hook(post)
        self.expect("the same parent retries", "allow", self.decision(self.run_hook(post, T0 + 5))[0])
        self.expect("another parent is a new session", True, self.denied_as_other_parent(post))

    def denied_as_other_parent(self, post):
        """Run the hook through a different parent process: a shell that runs it."""
        run = subprocess.run(["sh", "-c", f"{HOOK}; true"], input=json.dumps(post), capture_output=True,
                             text=True, env={**os.environ, "COMMENT_CHECK_INBOX": str(self.stub),
                                             "COMMENT_CHECK_NOW": str(T0 + 5), "TMPDIR": self.dir.name})
        return self.decision(run)[0] == "deny"

    def test_the_marker_folder_is_private_and_a_link_is_refused(self):
        post = bash("gh issue comment 7 --body hi")
        self.run_hook(post)
        parent = Path(self.dir.name) / f"claude-comment-check-{os.getuid()}"
        self.expect("mode 0700", 0o700, stat.S_IMODE(parent.stat().st_mode))
        markers = [m for m in parent.glob("*/*")]
        self.expect("the marker is private", 0o600, stat.S_IMODE(markers[0].stat().st_mode))
        # the folder is a link to somewhere else: nothing is recorded, nothing denied
        other = Path(self.dir.name) / "elsewhere"
        other.mkdir()
        for child in parent.glob("*"):
            for m in child.glob("*"):
                m.unlink()
            child.rmdir()
        parent.rmdir()
        parent.symlink_to(other)
        verdict, said = self.decision(self.run_hook(post, T0 + 1000))
        self.expect("allowed", "allow", verdict)
        self.expect("saying why", True, "Could not keep a record" in said)
        self.expect("and wrote nothing through the link", [], list(other.iterdir()))

    def test_a_loose_parent_is_made_private_and_a_session_folder_that_is_a_link_is_refused(self):
        post = bash("gh issue comment 7 --body hi")
        parent = Path(self.dir.name) / f"claude-comment-check-{os.getuid()}"
        parent.mkdir(mode=0o755)
        parent.chmod(0o755)
        self.expect("denied", True, self.denied(post))
        self.expect("the parent is now 0700", 0o700, stat.S_IMODE(parent.stat().st_mode))
        other = Path(self.dir.name) / "elsewhere"
        other.mkdir()
        folder = parent / "s2"
        folder.symlink_to(other)
        verdict, said = self.decision(self.run_hook(bash("gh issue comment 7 --body hi", "s2")))
        self.expect("allowed", "allow", verdict)
        self.expect("saying why", True, "Could not keep a record" in said)
        self.expect("and wrote nothing through the link", [], list(other.iterdir()))
        folder.unlink()
        folder.mkdir(mode=0o755)
        folder.chmod(0o755)
        self.expect("a loose session folder is used", True, self.denied(bash("gh issue comment 7 --body hi", "s2")))
        self.expect("and made 0700", 0o700, stat.S_IMODE(folder.stat().st_mode))

    def test_a_marker_that_is_a_link_is_not_followed(self):
        post = bash("gh issue comment 7 --body hi")
        self.run_hook(post)
        marker = next(Path(self.dir.name).glob("claude-comment-check-*/*/*"))
        target = Path(self.dir.name) / "victim"
        target.write_text("keep")
        marker.unlink()
        marker.symlink_to(target)
        self.expect("a link is no marker and cannot be recorded in, so it allows", "allow", self.decision(self.run_hook(post, T0 + 5))[0])
        self.expect("and the file it pointed at is untouched", "keep", target.read_text())

    def test_the_marker_is_the_sessions(self):
        post = lambda sid: bash("gh issue comment 7 --body hi", sid)
        self.run_hook(post("one"))
        self.expect("another session is denied its first attempt", "deny",
                    self.decision(self.run_hook(post("two"), T0 + 5))[0])
        self.expect("another issue too", "deny", self.decision(self.run_hook(
            bash("gh issue comment 8 --body hi", "one"), T0 + 5))[0])

    def test_new_owner_comment_denies_the_retry_again(self):
        post = bash("gh issue comment 7 --body hi")
        self.run_hook(post)
        self.say(ASK + ["  > 2026-10-01T09:05  #7  seven  and another  (comment 102)"])
        again = self.decision(self.run_hook(post, T0 + 60))
        self.expect("denied again", "deny", again[0])
        self.expect("with the new list, oldest first", True,
                    again[1].index("a question") < again[1].index("and another"))
        self.expect("and that retry is allowed", "allow", self.decision(self.run_hook(post, T0 + 90))[0])

    def test_claudes_own_comment_changes_nothing_and_none_unanswered_allows_at_once(self):
        post = bash("gh issue comment 7 --body hi")
        self.run_hook(post)
        self.say([])    # Claude's comment answered them: nothing is unanswered
        self.expect("allowed", "allow", self.decision(self.run_hook(post, T0 + 60))[0])
        self.expect("and silently", "", self.run_hook(post, T0 + 61).stdout)
        self.expect("with none unanswered a first post is allowed at once", "",
                    self.run_hook(bash("gh issue comment 8 --body hi", "fresh")).stdout)

    def test_unreadable_comments_let_the_post_through_and_say_so(self):
        """S53: a check, not a gate."""
        self.say([], status=1, error="HTTP 502")
        run = self.run_hook(bash("gh issue comment 7 --body hi"))
        verdict, said = self.decision(run)
        self.expect("allowed", "allow", verdict)
        self.expect("saying it could not read", True, "Could not read the comments on #7" in said and "HTTP 502" in said)
        self.expect("a missing reader too", "allow", self.decision(self.run_hook(
            bash("gh issue comment 7 --body hi"), COMMENT_CHECK_INBOX="/nonexistent/inbox"))[0])

    # -- the rest ----------------------------------------------------------------

    def test_it_names_the_owner_as_the_programme_file_does(self):
        self.expect("by the programme file's display name", True,
                    "comments from Pat that" in self.decision(self.run_hook(bash("gh issue comment 7 --body hi")))[1])

    def test_with_no_programme_file_it_still_speaks_and_does_not_name_a_person(self):
        verdict, reason = self.decision(self.run_hook(bash("gh issue comment 7 --body hi"),
                                                      PROGRAMME_CONFIG="/nonexistent/programme.toml"))
        self.expect("a hook must not fail", "deny", verdict)
        self.expect("no person named", True, "comments from the owner that" in reason)

    def test_no_input_or_nonsense_is_silent(self):
        for text in ("", "not json", "{}", '{"tool_input": 5}'):
            run = self.run_hook(text)
            self.expect(f"{text!r}", (0, ""), (run.returncode, run.stdout))


if __name__ == "__main__":
    unittest.main()
