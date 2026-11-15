#!/usr/bin/env bash
# Setup script for the Claude project's cloud environment, "programme"
# (delphside/tile-lite-elite#485, R4; delphside/programme#176 R15). Pasted into
# the environment's settings by the owner; this file is the reviewed copy.
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
# Which repository's hooks: the one the hook input's `cwd` is in, when it is a
# repository beside the others; else the first with an initialised `programme/`
# submodule; else the programme repository itself, whose hooks then read the
# programme's own board only. The pinned submodule's copy runs, as in a local
# session, so the hooks follow each application's pin.
#
# It also installs the desktop client's libraries, which are slow and so
# belong here, where the result is cached (Tile Lite Elite's docs/4.3.1).
#
# Never fails: a non-zero exit would stop every session starting.
#
# CLAUDE_USER_DIR (default /root/.claude) is where the settings and the script
# are written, and CLAUDE_SETUP_NO_PACKAGES skips the libraries; a test sets both.

export CLAUDE_USER_DIR="${CLAUDE_USER_DIR:-/root/.claude}"
mkdir -p "$CLAUDE_USER_DIR"

# The script the hooks call: cloud-programme-hook.sh <hook> [args...], or --roles.
cat > "$CLAUDE_USER_DIR/cloud-programme-hook.sh" <<'HOOK' || echo "setup: could not write cloud-programme-hook.sh" >&2
#!/usr/bin/env bash
# cloud-programme-hook.sh <hook> [args...] | --roles: runs the programme's hook
# of that name for the repository the hook input's cwd is in. Written by the
# programme's .claude/cloud-environment-setup.sh. Never fails a session.
WS="${CLAUDE_PROJECT_DIR:-$PWD}"
INPUT="$(timeout 2 cat 2>/dev/null)"
CWD="$(printf '%s' "$INPUT" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("cwd") or "")' 2>/dev/null)"
TOP="$(git -C "${CWD:-$PWD}" rev-parse --show-toplevel 2>/dev/null)"
NAME="${1:-}"; [ "$NAME" = "--roles" ] && NAME="inbox-hook.sh"
APP=""
if [ -n "$TOP" ] && [ "$(dirname "$TOP")" = "$WS" ]; then
  APP="$TOP"
else
  for d in "$WS"/*/; do
    [ -x "${d}programme/.claude/hooks/$NAME" ] && { APP="${d%/}"; break; }
  done
fi
if [ -n "$APP" ] && [ -x "$APP/programme/.claude/hooks/$NAME" ]; then HOOKS="$APP/programme/.claude/hooks"
elif [ -n "$APP" ] && [ -x "$APP/.claude/hooks/$NAME" ]; then HOOKS="$APP/.claude/hooks"
else HOOKS="$WS/programme/.claude/hooks"; fi
[ -x "$HOOKS/$NAME" ] || { echo "The programme's hooks were not found beside the workspace, so ${1:-a hook} did not run."; exit 0; }
if [ "${1:-}" = "--roles" ]; then
  ROLES="$(PYTHONPATH="$HOOKS/../../scripts" python3 -c 'from board.model import ROLES; print(", ".join(ROLES))' 2>/dev/null)"
  echo "Your role's to-do list is not shown: a cloud thread does not know its role at start. Once you know it (${ROLES:-see scripts/board/model.py ROLES}), run programme/scripts/board/board-actions.py --role <role>, and again at each wake."
  exit 0
fi
shift
# exec with the input as standard input, so the hook's parent stays the session.
exec "$HOOKS/$NAME" "$@" <<<"$INPUT"
HOOK
chmod +x "$CLAUDE_USER_DIR/cloud-programme-hook.sh" 2>/dev/null || true

python3 - <<'PY' || echo "setup: could not write the user-level settings.json" >&2
import json, os
d = os.environ["CLAUDE_USER_DIR"]
p = os.path.join(d, "settings.json")
helper = os.path.join(d, "cloud-programme-hook.sh")
try:
    s = json.load(open(p))
except Exception:
    s = {}
hooks = s.setdefault("hooks", {})


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
json.dump(s, open(p, "w"), indent=2)
PY

if [ -z "${CLAUDE_SETUP_NO_PACKAGES:-}" ]; then
    apt-get update -qq && apt-get install -y -qq --no-install-recommends \
        libwebkit2gtk-4.1-dev libgtk-3-dev libxdo-dev \
        || echo "setup: desktop libraries not installed" >&2
fi

exit 0
