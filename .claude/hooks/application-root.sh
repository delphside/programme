# application-root.sh — sourced by the three hooks beside it (#485 stage 2).
#
# The hooks live in the programme, which an application carries as its pinned
# submodule `programme/` and which is also a repository of its own. Their state
# (`.claude/.inbox-cache` and the rest) is the application's, in its `.claude/`,
# so a hook works from the application's root. That is the rule
# `scripts/board/profile.py` applies to the board scripts: the superproject's
# working tree when this is a submodule, else the top level of the repository it
# is in (the programme itself, for its tests; a plain copy inside an application,
# for a fixture). It needs no git remote.
#
# Sets PROG (the programme's root), APP (the application's root) and BOARD (the
# board scripts), and changes into APP; the caller exits 0 if that fails.
PROG="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP="$(git -C "$PROG" rev-parse --show-superproject-working-tree 2>/dev/null)"
[[ -n "$APP" ]] || APP="$(git -C "$PROG" rev-parse --show-toplevel 2>/dev/null)"
APP="${APP:-$PROG}"
BOARD="$PROG/scripts/board"
cd "$APP" || exit 0
