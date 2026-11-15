#!/usr/bin/env bash
# Setup script for the Claude project's cloud environment, "programme"
# (delphside/tile-lite-elite#485, R4; delphside/programme#176 R15). Pasted into
# the environment's settings by the owner; this file is the reviewed copy.
#
# **Paste it only after Tile Lite Elite's and Dark Portal's pins have moved past
# the merge that added `board-actions.py --role` and the demand-manager role
# name** (implementation.md: delivery 3, after delivery 2's step 5). Until then the pinned inbox
# hook overruns its 90 s timeout and the roles line names a command the pin
# does not have.
#
# Cloud threads start in the workspace folder ($CLAUDE_PROJECT_DIR) with every
# project repository cloned beside each other, so no repository's own
# .claude/settings.json hooks run. This writes three user-level hooks into
# /root/.claude/settings.json, and the small script they call:
#   - SessionStart: each repository's .claude/cloud-setup.sh, with
#     CLAUDE_PROJECT_DIR set to that repository;
#   - SessionStart: the programme's inbox-hook.sh (the to-do list: the owner's
#     comments not yet answered, and the rest), then a line naming the roles and
#     the command that lists one role's items. The hook cannot know a thread's
#     role, so the thread runs `board-actions.py --role <role>` once it does;
#   - PreToolUse: the programme's comment-check.sh, on `Bash` and on the GitHub
#     MCP tools that post a comment.
# The hooks read GitHub through REST, which works from a cloud thread.
#
# Which application's hooks run: the one the hook input's `cwd` is in (for a
# GitHub MCP tool, the repository `tool_input.repo` names when `tool_input.owner`
# is given too), when it is a repository beside the others with an initialised
# `programme/` submodule that has the hook; otherwise DEFAULT_APP's. The pinned submodule's copy runs, as in
# a local session, so the hooks follow each application's pin. For a cwd in
# another repository (the programme's, or an application without its
# submodule) the default application's hooks run with GH_REPO set to that
# repository, so comment-check lets a post there through instead of checking it
# against the default application's issue of the same number. Where no
# application's hooks are found, the wrapper says so in one line and exits 0:
# the board scripts refuse to run in the programme's own repository, so it has
# no hooks of its own to fall back on.
#
# It initialises each repository's `programme/` submodule first. The hooks run
# that submodule's copy, and a repository's own cloud-setup.sh, which would
# otherwise fetch it, runs beside the inbox hook at session start: the hook ran
# first and found nothing (2026-11-15). The script starts in the folder that
# holds the repositories; CLAUDE_SETUP_WORKSPACE names another.
#
# It also installs the desktop client's libraries, which are slow and so
# belong here, where the result is cached (Tile Lite Elite's docs/4.3.1).
#
# Always exits 0: a non-zero exit would stop every session starting. A
# settings.json of an unexpected shape is left untouched, and one that is not
# JSON is copied to settings.json.bak.<UTC time> first (an existing copy is never
# overwritten); both are said on stderr. A settings.json that is a symlink is
# written through to its target, and keeps its mode.
#
# CLAUDE_USER_DIR (default /root/.claude) is where the settings and the script
# are written, and CLAUDE_SETUP_NO_PACKAGES skips the libraries; a test sets both.

export CLAUDE_USER_DIR="${CLAUDE_USER_DIR:-/root/.claude}"

# Each repository's pinned programme/, so the hooks find it at session start.
for d in "${CLAUDE_SETUP_WORKSPACE:-$PWD}"/*/; do
  git -C "$d" config -f .gitmodules --get submodule.programme.path >/dev/null 2>&1 || continue
  timeout 120 git -C "$d" submodule update --init programme >/dev/null 2>&1 \
    || echo "setup: could not fetch ${d}programme" >&2
done
# The application whose hooks run when the cwd is in none that has them.
DEFAULT_APP="tile-lite-elite"
mkdir -p "$CLAUDE_USER_DIR"

# The script the hooks call: cloud-programme-hook.sh <hook> [args...], or --roles.
cat > "$CLAUDE_USER_DIR/cloud-programme-hook.sh" <<'HOOK' || echo "setup: could not write cloud-programme-hook.sh" >&2
#!/usr/bin/env bash
# cloud-programme-hook.sh <hook> [args...] | --roles: runs the pinned programme's
# hook of that name for the application the hook input names (its cwd, or a
# GitHub MCP tool's repo), else for DEFAULT_APP. Written by the programme's
# .claude/cloud-environment-setup.sh. Never fails a session.
DEFAULT_APP="@DEFAULT_APP@"
WS="${CLAUDE_PROJECT_DIR:-$PWD}"
NAME="${1:-}"; [ "$NAME" = "--roles" ] && NAME="inbox-hook.sh"
INPUT="$(timeout 2 cat 2>/dev/null)"
IFS=$'\x1e' read -r CWD REPO <<<"$(printf '%s' "$INPUT" | python3 -c '
import json, sys
d = json.load(sys.stdin)
tool = d.get("tool_input") or {}
named = str(d.get("tool_name") or "").startswith("mcp__") and tool.get("owner") and tool.get("repo")
repo = tool.get("repo") if named else ""
print("\x1e".join([d.get("cwd") or "", repo if isinstance(repo, str) else ""]))
' 2>/dev/null)"
has_hook() { [ -x "$1/programme/.claude/hooks/$NAME" ]; }

# The repository the cwd is in; from inside an application's pinned programme/,
# the application.
TOP="$(git -C "${CWD:-$PWD}" rev-parse --show-toplevel 2>/dev/null)"
SUPER="$(git -C "${CWD:-$PWD}" rev-parse --show-superproject-working-tree 2>/dev/null)"
[ -n "$SUPER" ] && TOP="$SUPER"

APP=""
if [ -n "$REPO" ]; then
  case "$REPO" in */*|.*) ;; *) has_hook "$WS/$REPO" && APP="$WS/$REPO" ;; esac
elif [ -n "$TOP" ] && [ "$(dirname "$TOP")" = "$WS" ] && has_hook "$TOP"; then
  APP="$TOP"
fi
if [ -z "$APP" ] && has_hook "$WS/$DEFAULT_APP"; then
  APP="$WS/$DEFAULT_APP"
  # A cwd in another repository: a Bash post there is that repository's, which
  # comment-check lets through when GH_REPO names it.
  if [ -z "$REPO" ] && [ -n "$TOP" ] && [ "$TOP" != "$APP" ]; then
    URL="$(git -C "$TOP" remote get-url origin 2>/dev/null)"
    URL="${URL%.git}"; BASE="${URL##*/}"; OWNER="${URL%/*}"; OWNER="${OWNER##*/}"; OWNER="${OWNER##*:}"
    if [ -n "$URL" ] && [ -n "$BASE" ] && [ -n "$OWNER" ]; then export GH_REPO="$OWNER/$BASE"
    else export GH_REPO="local/$(basename "$TOP")"; fi
  fi
fi
[ -n "$APP" ] || { echo "No application's pinned programme hooks were found beside the workspace, so ${1:-a hook} did not run."; exit 0; }
HOOKS="$APP/programme/.claude/hooks"
if [ "${1:-}" = "--roles" ]; then
  ROLES="$(PYTHONPATH="$HOOKS/../../scripts" python3 -c 'from board.model import ROLES; print(", ".join(ROLES))' 2>/dev/null)"
  echo "Your role's to-do list is not shown: a cloud thread does not know its role at start. Once you know it (${ROLES:-see scripts/board/model.py ROLES}), run programme/scripts/board/board-actions.py --role <role>, and again at each wake."
  exit 0
fi
shift
# exec with the input as standard input, so the hook's parent stays the session.
exec "$HOOKS/$NAME" "$@" <<<"$INPUT"
HOOK
sed -i "s|@DEFAULT_APP@|$DEFAULT_APP|" "$CLAUDE_USER_DIR/cloud-programme-hook.sh" 2>/dev/null || true
chmod +x "$CLAUDE_USER_DIR/cloud-programme-hook.sh" 2>/dev/null || true

python3 - <<'PY' || echo "setup: could not write the user-level settings.json" >&2
import json, os, shutil, stat, sys
from datetime import datetime, timezone
d = os.environ["CLAUDE_USER_DIR"]
# Through a symlink to the file it stands for: the link stays a link.
p = os.path.realpath(os.path.join(d, "settings.json"))
helper = os.path.join(d, "cloud-programme-hook.sh")


def say(text):
    print(f"setup: {text}", file=sys.stderr)


s = {}
if os.path.exists(p):
    try:
        s = json.load(open(p))
    except Exception:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup, n = f"{p}.bak.{stamp}", 1
        while os.path.exists(backup):
            n += 1
            backup = f"{p}.bak.{stamp}-{n}"
        shutil.copyfile(p, backup)
        say(f"{p} is not JSON: copied to {backup} and started afresh")
        s = {}
    if not isinstance(s, dict):
        say(f"{p} is not a JSON object: left untouched, so no hooks were written")
        sys.exit(0)
hooks = s.get("hooks", {})
if not isinstance(hooks, dict):
    say(f"'hooks' in {p} is not an object: left untouched, so no hooks were written")
    sys.exit(0)
for event in ("SessionStart", "PreToolUse"):
    if not isinstance(hooks.get(event, []), list):
        say(f"'hooks.{event}' in {p} is not a list: left untouched, so no hooks were written")
        sys.exit(0)
s["hooks"] = hooks


def replace(event, marker, entries):
    """The event's entries, without any that carry `marker`, then these."""
    cur = hooks.setdefault(event, [])
    cur[:] = [h for h in cur if marker not in json.dumps(h)] + entries


cmd = ('for f in "${CLAUDE_PROJECT_DIR:-$PWD}"/*/.claude/cloud-setup.sh; do '
       '[ -x "$f" ] && CLAUDE_PROJECT_DIR="$(dirname "$(dirname "$f")")" "$f" </dev/null; '
       'done; exit 0')
replace("SessionStart", "cloud-setup.sh", [
    {"matcher": "startup|resume",
     "hooks": [{"type": "command", "command": cmd, "timeout": 300,
                "statusMessage": "Installing each repository's build and test tools..."}]}])
replace("SessionStart", "cloud-programme-hook.sh", [
    {"hooks": [{"type": "command", "command": f"{helper} inbox-hook.sh", "timeout": 90,
                "statusMessage": "Checking the GitHub inbox..."},
               {"type": "command", "command": f"{helper} --roles", "timeout": 20}]}])
replace("PreToolUse", "cloud-programme-hook.sh", [
    {"matcher": "Bash|mcp__github__add_issue_comment"
                "|mcp__github__add_reply_to_pull_request_comment"
                "|mcp__github__pull_request_review_write",
     "hooks": [{"type": "command", "command": f"{helper} comment-check.sh", "timeout": 30}]}])
# Written beside the file and renamed over it, so a failure part-way leaves it whole.
tmp = p + ".tmp"
with open(tmp, "w") as f:
    json.dump(s, f, indent=2)
if os.path.exists(p):
    os.chmod(tmp, stat.S_IMODE(os.stat(p).st_mode))
os.replace(tmp, p)
PY

if [ -z "${CLAUDE_SETUP_NO_PACKAGES:-}" ]; then
    apt-get update -qq && apt-get install -y -qq --no-install-recommends \
        libwebkit2gtk-4.1-dev libgtk-3-dev libxdo-dev \
        || echo "setup: desktop libraries not installed" >&2
fi

exit 0
