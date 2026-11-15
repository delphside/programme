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

    def say(self, lines, status=0, error=""):
        """What the stub board-inbox.py prints, and how it exits."""
        body = "\n".join(f"echo '{line}'" for line in lines)
        self.stub.write_text(f"#!/bin/sh\n{body}\necho '{error}' >&2\nexit {status}\n")
        self.stub.chmod(self.stub.stat().st_mode | stat.S_IEXEC)

    def run_hook(self, data, now=T0, **env):
        run = subprocess.run([str(HOOK)], input=json.dumps(data) if isinstance(data, dict) else data,
                             capture_output=True, text=True,
                             env={**os.environ, "COMMENT_CHECK_INBOX": str(self.stub),
                                  "COMMENT_CHECK_NOW": str(now), "TMPDIR": self.dir.name, **env})
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
        "gh pr comment --body hi",
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
        for data in self.MCP_POSTS:
            sid = data["tool_name"] + str(data["tool_input"].get("method"))
            self.expect(f"denies {sid}", True, self.denied({**data, "session_id": sid}))
        for data in self.MCP_LET_THROUGH:
            self.expect(f"lets through {data['tool_name']} {data['tool_input']}", "",
                        self.run_hook(data).stdout)

    def test_live_comment_check_denies_once_then_allows_each_hook_input(self):
        """TT10: the hook invoked directly with piped hook-input JSON, a stub in
        place of GitHub and no real post: denied once with the comment, then
        allowed, for a Bash input and for each MCP comment tool."""
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
