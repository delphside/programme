#!/usr/bin/env bash
# comment-check.sh — before Claude posts a comment on an issue or pull request,
# deny the first attempt when the owner has said something there that nobody has
# answered, and say what (#454 R5, #455 R5 and R8).
#
# Runs on PreToolUse. It reads the tool's input and reacts to the ways Claude
# posts a comment, and to nothing else: `gh issue comment`, `gh pr comment`,
# `gh issue close --comment`, `gh pr close --comment`, `gh pr review --body` and
# `gh api -X POST` to a comment, a review or a reply (the `Bash` tool), and the
# GitHub MCP tools `add_issue_comment`, `add_reply_to_pull_request_comment` and
# `pull_request_review_write` when it creates a review with an event or submits
# a pending one, whatever its body (it posts the pending comments).
# `gh pr comment` and `gh pr review` with no number mean the branch's pull
# request. A post to another repository than the application's, by `-R`, a URL,
# `GH_REPO` or an MCP owner and repo, is not checked: the board reads one
# repository. The table of ways is implementation.md §6 of
# delphside/programme#176. A reaction, an edit, a pending review comment, a
# read, a commit message and text quoted inside a body are let through.
#
# **Deny once.** A hook's context reaches Claude only after the command runs,
# but a denial's reason is read before the post, so the denial shapes the
# comment. The first post to an issue with unanswered owner comments is denied,
# the reason listing them oldest first. The same post to the same issue in the
# same session within `comments.retry_minutes` (the programme file) of the
# denial is allowed. A new owner comment changes the set, so it denies again;
# Claude's own comment answers them, so nothing is unanswered and it is allowed.
# The marker is a file in the system's temporary directory under the session's
# id (the hook's parent process where there is none), keyed by repository,
# issue, the kind of post (comment, close with a comment, review) and the
# comments' ids: another session has another directory, so a marker never lets
# a different session through. The directory is private to the user; the check
# allows the post, and says so, if it finds one that is not or is a link.
#
# **A check, not a gate** (docs/1.2 §2.16) apart from that one denial. When the
# comments cannot be read it allows the post and says it could not read. Every
# other path allows silently, and the hook always exits 0.
#
# `COMMENT_CHECK_INBOX` replaces the command that reads the issue, and
# `COMMENT_CHECK_NOW` (epoch seconds) the clock, so both can be tested without
# GitHub or waiting.
set -uo pipefail

# shellcheck source=application-root.sh
source "$(dirname "$0")/application-root.sh"
export BOARD
export COMMENT_CHECK_INBOX="${COMMENT_CHECK_INBOX:-$BOARD/board-inbox.py}"
export COMMENT_CHECK_PARENT="$PPID"   # the session, for a hook input with no session_id

INPUT="$(timeout 2 cat 2>/dev/null)"
[[ -n "$INPUT" ]] || exit 0

read -r -d '' CHECK <<'PYTHON'
import hashlib, json, os, re, shlex, stat, subprocess, sys, time

BOARD = os.environ["BOARD"]
INBOX = os.environ["COMMENT_CHECK_INBOX"]
PUNCT = ";&|()<>\n"


def say(**fields):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", **fields}}))


def profile_value(key):
    """One programme-file value, or None: a hook must not fail."""
    try:
        run = subprocess.run([sys.executable, f"{BOARD}/board-profile.py", "get", key],
                             capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return run.stdout.strip() or None if run.returncode == 0 else None


# --- which post is this ------------------------------------------------------

def segments(command):
    """The command split into the simple commands it runs. Quoting is honoured,
    so text inside a body is one word and starts no command; a heredoc's body
    is dropped first, as it is text."""
    command = re.sub(r"(<<-?\s*(['\"]?)(\w+)\2[^\n]*)\n.*?\n[ \t]*\3[ \t]*(?=\n|$)", r"\1",
                     command, flags=re.S)
    lex = shlex.shlex(command, posix=True, punctuation_chars=PUNCT)
    lex.whitespace = " \t\r"
    lex.commenters = ""           # `#7` is an issue, not a comment
    lex.wordchars += ":@%+,{}$#"  # URLs, `{owner}` placeholders
    try:
        words = list(lex)
    except ValueError:
        return []
    out = [[]]
    for word in words:
        if word and all(c in PUNCT for c in word):
            out.append([])
        else:
            out[-1].append(word)
    return out


def parse(args, valued):
    """(positionals, flags, fields): `valued` flags take the next word."""
    positional, flags, fields = [], {}, []
    i = 0
    while i < len(args):
        a = args[i]
        if a.startswith("--") and "=" in a:
            name, value = a.split("=", 1)
        elif a.startswith("-") and a != "-":
            name, value = a, True
            if a in valued and i + 1 < len(args):
                i += 1
                value = args[i]
        else:
            positional.append(a)
            i += 1
            continue
        flags[name] = value
        if name in ("-f", "-F", "--field", "--raw-field") and isinstance(value, str):
            fields.append(value)
        i += 1
    return positional, flags, fields


def norm_repo(repo):
    """`owner/repo` of a repository given as that, a URL or HOST/OWNER/REPO, or None."""
    parts = [p for p in re.sub(r"\.git$", "", str(repo or "")).split("/") if p]
    return "/".join(parts[-2:]) if len(parts) >= 2 else None


BRANCH = "branch"     # no number was given: the current branch's pull request


def target(word, repo, kind, branch_ok=False):
    """(repo, number, kind) of an issue or pull request given as a number, #number
    or URL; with no word, the branch's pull request where `branch_ok`."""
    m = re.search(r"github\.com/([^/]+/[^/]+)/(?:issues|pull)/(\d+)", word or "")
    if m:
        return m.group(1), int(m.group(2)), kind
    m = re.fullmatch(r"#?(\d+)", word or "")
    if m:
        return norm_repo(repo), int(m.group(1)), kind
    if word is None and branch_ok:
        return norm_repo(repo), BRANCH, kind
    return None


API_PATH = re.compile(r"^/?repos/([^/]+/[^/]+)/(?:issues/(\d+)/comments"
                      r"|pulls/(\d+)/(?:comments(?:/\d+/replies)?|reviews(?:/\d+/events)?))/?$")


def gh_post(args, default_repo=None):
    if len(args) < 2:
        return None
    group, verb, rest = args[0], args[1], args[2:]
    repo_flags = {"-R", "--repo"}
    if group in ("issue", "pr") and verb == "comment":
        positional, flags, _ = parse(rest, repo_flags | {"-b", "--body", "-F", "--body-file"})
        if "--edit-last" in flags or "--delete-last" in flags:
            return None
        return target(positional[0] if positional else None, flags.get("-R") or flags.get("--repo") or default_repo,
                      "comment", group == "pr")
    if group in ("issue", "pr") and verb == "close":
        positional, flags, _ = parse(rest, repo_flags | {"-c", "--comment", "-r", "--reason"})
        if not (flags.get("-c") or flags.get("--comment")):
            return None
        return target(positional[0] if positional else None, flags.get("-R") or flags.get("--repo") or default_repo,
                      "close")
    if group == "pr" and verb == "review":
        positional, flags, _ = parse(rest, repo_flags | {"-b", "--body", "-F", "--body-file"})
        if not any(isinstance(flags.get(k), str) and flags.get(k)
                   for k in ("-b", "--body", "-F", "--body-file")):
            return None
        return target(positional[0] if positional else None, flags.get("-R") or flags.get("--repo") or default_repo,
                      "review", True)
    return None


def gh_api_post(args, default_repo=None):
    positional, flags, fields = parse(
        args, {"-X", "--method", "-f", "-F", "--field", "--raw-field", "-H", "--header",
               "--jq", "-q", "--input", "-t", "--template", "--hostname", "--cache", "-p",
               "--preview"})
    if not positional:
        return None
    method = flags.get("-X") or flags.get("--method")
    if not method:
        method = "POST" if (fields or "--input" in flags) else "GET"
    if str(method).upper() != "POST":
        return None
    m = API_PATH.match(positional[0])
    if not m:
        return None
    number = m.group(2) or m.group(3)
    if re.search(r"/reviews/?$", positional[0]) and not (
            any(f.startswith("event=") for f in fields) or "--input" in flags):
        return None          # a review created without an event is pending: nothing is posted
    repo = m.group(1)
    kind = "review" if "/reviews" in positional[0] else "comment"
    return (norm_repo(default_repo) if "{" in repo else repo), int(number), kind


def bash_post(command):
    for seg in segments(command):
        default_repo = os.environ.get("GH_REPO")
        while seg and re.fullmatch(r"\w+=.*", seg[0]):
            if seg[0].startswith("GH_REPO="):
                default_repo = seg[0].split("=", 1)[1]
            seg = seg[1:]
        if not seg or os.path.basename(seg[0]) != "gh":
            continue
        found = (gh_api_post(seg[2:], default_repo) if seg[1:2] == ["api"]
                 else gh_post(seg[1:], default_repo))
        if found:
            return found
    return None


def mcp_post(name, tool_input):
    body = tool_input.get("body")
    kind = "comment"
    if name == "pull_request_review_write":
        method = tool_input.get("method")
        if not ((method == "create" and tool_input.get("event")) or method == "submit_pending"):
            return None
        kind = "review"      # it posts the pending comments, so whatever its body
    elif not (isinstance(body, str) and body.strip()):
        return None          # a reaction alone, or nothing to say
    elif name not in ("add_issue_comment", "add_reply_to_pull_request_comment"):
        return None          # update_issue_comment, add_comment_to_pending_review, and the rest
    number = next((tool_input[k] for k in ("issue_number", "issueNumber", "pullNumber",
                                           "pull_number", "number") if tool_input.get(k)), None)
    if not str(number).isdigit():
        return None
    owner, repo = tool_input.get("owner"), tool_input.get("repo")
    return (f"{owner}/{repo}" if owner and repo else None), int(number), kind


def which_post(data):
    name, tool_input = data.get("tool_name") or "", data.get("tool_input") or {}
    if name == "Bash" or (not name and "command" in tool_input):
        return bash_post(tool_input.get("command") or "")
    if name.startswith("mcp__"):
        return mcp_post(name.rsplit("__", 1)[-1], tool_input)
    return None


# --- what is unanswered, and whether this is the retry ----------------------

def main():
    try:
        data = json.loads(sys.stdin.read())
        post = which_post(data)
    except Exception:
        return
    if not post:
        return
    repo, number, kind = post
    ours = profile_value("profile.identity.repository")
    if repo and ours and repo.lower() != ours.lower():
        return               # the board reads this application's repository only
    if number == BRANCH:
        try:
            view = subprocess.run(["gh", "pr", "view", "--json", "number", "-q", ".number"],
                                  capture_output=True, text=True, timeout=20,
                                  env={**os.environ, **({"GH_REPO": repo} if repo else {})})
            number = int(view.stdout.strip()) if view.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired, ValueError):
            number = None
        if number is None:
            say(additionalContext="Could not read the comments: the pull request for this branch "
                                  "could not be found, so this post was not checked for unanswered "
                                  "comments from the owner.")
            return

    try:
        run = subprocess.run([INBOX, "--open", "--issue", str(number), "--all", "--ids", "--no-colour"],
                             capture_output=True, text=True, timeout=20)
        failed = None if run.returncode == 0 else (run.stderr.strip().splitlines() or [f"exit {run.returncode}"])[0]
    except (OSError, subprocess.TimeoutExpired) as exc:
        run, failed = None, str(exc)
    if failed is not None:
        say(additionalContext=f"Could not read the comments on #{number} ({failed[:150]}), "
                              "so this post was not checked for unanswered comments from the owner.")
        return
    lines = [l for l in run.stdout.splitlines() if l.startswith("  > ")]
    if not lines:
        return

    ids = [i for l in lines for i in re.findall(r"\(comment (\d+)\)$", l)]
    key = hashlib.sha1(f"{repo or ours}#{number}|{kind}|{','.join(sorted(ids)) if ids else chr(10).join(lines)}"
                       .encode()).hexdigest()
    session = re.sub(r"[^\w.-]", "_", str(data.get("session_id") or "")) \
        or f"parent-{os.environ.get('COMMENT_CHECK_PARENT') or 'none'}"
    parent = os.path.join(os.environ.get("TMPDIR") or "/tmp", f"claude-comment-check-{os.getuid()}")
    folder = os.path.join(parent, session)
    marker = os.path.join(folder, key)
    try:
        try:
            os.mkdir(parent, 0o700)
        except FileExistsError:
            pass
        info = os.lstat(parent)
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
            raise OSError("not ours")
        os.makedirs(folder, mode=0o700, exist_ok=True)
        if os.lstat(folder).st_uid != os.getuid():
            raise OSError("not ours")
    except OSError:
        say(additionalContext=f"Could not keep a record of a denial in {parent} (it is not a folder "
                              "of yours), so this post was not checked for unanswered comments "
                              "from the owner.")
        return
    now = int(os.environ.get("COMMENT_CHECK_NOW") or time.time())

    minutes = profile_value("comments.retry_minutes")
    try:
        with os.fdopen(os.open(marker, os.O_RDONLY | os.O_NOFOLLOW)) as handle:
            denied_at = int(handle.read().strip())
    except (OSError, ValueError):
        denied_at = None
    if denied_at is not None:
        if not (minutes or "").isdigit():
            return           # cannot judge the window: a check, not a gate
        if 0 <= now - denied_at <= int(minutes) * 60:
            return
    else:
        minutes = minutes if (minutes or "").isdigit() else "a few"
    try:
        fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.write(str(now))
    except OSError:
        return               # nowhere to record the denial, so deny nothing

    name = profile_value("accounts.owner_name") or "the owner"
    say(permissionDecision="deny", permissionDecisionReason=(
        f"#{number} has comments from {name} that no comment of yours has answered. "
        "Make this comment answer them, or say why not, then post again: the same post "
        f"to this issue within {minutes} minutes is allowed.\n" + "\n".join(lines)))


main()
PYTHON

printf '%s' "$INPUT" | python3 -c "$CHECK" 2>/dev/null
exit 0
