#!/usr/bin/env bash
# inbox-hook.sh — SessionStart summary of GitHub activity, for Claude's context.
#
# Wraps programme/scripts/board/board-inbox.py. Lives in the programme's
# `.claude/hooks/`, not in `scripts/`, because it is about how Claude is driven,
# not about the project; an application's `.claude/settings.json` runs it from
# its `programme/` submodule, and its cache and log stay in the application's `.claude/`.
#
# **A summary, not a replay.** The full seven-day output is ~25KB, most of it
# Claude's own comments being read back to itself. This emits the owner's
# comments Claude has not answered (of any age from the to-do floor, the 12 that
# have waited longest) and what opened or closed; `programme/scripts/board/board-inbox.py`
# gives the detail on demand.
#
# **Each section's heading says whose move it is, and each is read on its own**:
# one read that fails prints its failure and hides no other section (#455).
#
# Never fails a session: every error path exits 0 with no output, because a
# broken inbox must not stop work starting.
#
# **Fast, because it reads a cache (#452).** The three board calls take ~48s,
# and a session whose first message was sent while the hook ran appears to have
# started with no hook at all (session 60541916, 2026-10-01, no record of any
# kind). So the slow work is `--build`, run detached and written to
# .claude/.inbox-cache; the SessionStart hook only reads it and says how old
# it is. Modes:
#   (none)               SessionStart: emit the cache, refresh it behind us
#   --build              compute the summary and write the cache (locked)
#   --refresh-if-stale   start a detached --build if the cache is old; the
#                        Stop hook calls this so the cache follows the work
#   --backstop SID       UserPromptSubmit: print the cache as plain text if
#                        session SID never had it delivered, then mark it
# Every run is logged to .claude/.inbox-hook.log (start, end, session id) so
# a session with no hook can be told from a hook that ran and was ignored.
set -uo pipefail

# shellcheck source=application-root.sh
source "$(dirname "$0")/application-root.sh"
CACHE=.claude/.inbox-cache
LOCK=.claude/.inbox-build.lock
LOG=.claude/.inbox-hook.log
DELIVERED=.claude/.inbox-delivered
STALE_SECS="${INBOX_STALE_SECS:-600}"
MODE="${1:-}"

log() { printf '%s %s pid=%s %s\n' "$(date -u +%FT%TZ)" "$MODE" "$$" "$*" >> "$LOG" 2> /dev/null || true; }

cache_age() { echo $(( $(date +%s) - $(stat -c %Y "$CACHE" 2>/dev/null || echo 0) )); }

# What the text holds, in the order it holds it (#455-R10).
ORDER="the programme checkout and its pin; opened or closed in the last 7 days; the owner's comments not yet answered; reports from the scheduled workflows; board actions; board-check findings; overdue programme activities"
INTRO="GitHub activity: what opened or closed in the last 7 days, and the owner's comments not yet answered, of any age. Sections come in this order, each only when it has something to show: $ORDER. Each heading says whose move it is. Run programme/scripts/board/board-inbox.py for the detail."

# Plain text, with the cache's age so a stale one is never mistaken for live.
cache_text() {
  printf 'GitHub activity: what opened or closed in the last 7 days, and the owner'"'"'s comments not yet answered, of any age (from a cache %s min old; programme/scripts/board/board-inbox.py for current detail). Sections come in this order, each only when it has something to show: %s. Each heading says whose move it is.\n\n' "$(( $(cache_age) / 60 ))" "$ORDER"
  cat "$CACHE"
}

mark_delivered() {
  [[ -n "${1:-}" ]] || return 0
  mkdir -p "$DELIVERED" && : > "$DELIVERED/$1"
  find "$DELIVERED" -type f -mtime +7 -delete 2> /dev/null || true
}

start_build() {
  nohup setsid "$0" --build > /dev/null 2>&1 < /dev/null &
}

case "$MODE" in
  --refresh-if-stale)
    [[ -f "$CACHE" ]] && (( $(cache_age) < STALE_SECS )) && exit 0
    start_build; exit 0 ;;
  --backstop)
    SID="${2:-}"
    [[ -n "$SID" && ! -e "$DELIVERED/$SID" ]] || exit 0
    log "sid=$SID backstop: no delivery on record"
    if [[ -s "$CACHE" ]]; then
      cache_text; mark_delivered "$SID"; log "sid=$SID backstop delivered"
    else
      start_build   # nothing to say yet; the next turn will have it
    fi
    exit 0 ;;
esac

# SessionStart, and --build, below. Only SessionStart has a hook payload on stdin.
SID=""
if [[ "$MODE" != "--build" && ! -t 0 ]]; then
  SID="$(timeout 2 cat 2>/dev/null | sed -n 's/.*"session_id" *: *"\([^"]*\)".*/\1/p' | head -1)"
fi
log "sid=${SID:-?} start"

# The live programme checkout missing, off main or behind: one line, or nothing.
# Local git only, never changes the checkout, and never fails the session.
#
# The same moment checks the programme pin (`board-records.py pin`, one fetch
# of at most five seconds): one more line when the pin is behind. It warns and
# never moves it. Run beside the first, so the two cost the slower, not the sum.
NOTE=""
if [[ "$MODE" != "--build" ]]; then
  PIN_OUT="$(mktemp 2>/dev/null)" || PIN_OUT=/dev/null
  timeout 8 "$BOARD"/board-records.py pin > "$PIN_OUT" 2>/dev/null &
  NOTE="$(timeout 10 "$BOARD"/board-records.py check 2>/dev/null || true)"
  wait
  PIN_NOTE="$(cat "$PIN_OUT" 2>/dev/null || true)"
  [[ "$PIN_OUT" != /dev/null ]] && rm -f "$PIN_OUT"
  [[ -n "$PIN_NOTE" ]] && NOTE="${NOTE:+$NOTE$'\n'}$PIN_NOTE"
fi
[[ -n "$NOTE" ]] && NOTE="For Claude to fix: the programme checkout and its pin (programme/scripts/board/board-records.py):"$'\n'"$NOTE"
with_note() { if [[ -n "$NOTE" ]]; then printf '%s\n\n%s' "$NOTE" "$1"; else printf '%s' "$1"; fi; }
# Leave without a summary, still saying so if the checkout has a problem.
bail() { [[ -n "$NOTE" ]] && emit_json "$NOTE" && mark_delivered "$SID"; exit 0; }

emit_json() {
  printf '%s' "$1" | python3 -c '
import sys, json
t = sys.stdin.read().strip()
if t:
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": t,
    }}))
' 2>/dev/null
}

if [[ "$MODE" != "--build" && -s "$CACHE" ]]; then
  emit_json "$(with_note "$(cache_text)")" && mark_delivered "$SID"
  (( $(cache_age) >= STALE_SECS )) && start_build
  log "sid=${SID:-?} end (from cache)"
  exit 0
fi

# --build, or SessionStart with no cache at all: do the slow work.
command -v gh > /dev/null 2>&1 || bail
if [[ "$MODE" == "--build" ]]; then
  # One build at a time; a lock older than five minutes is a dead build's.
  find "$LOCK" -maxdepth 0 -mmin +5 -exec rmdir {} \; 2> /dev/null || true
  mkdir "$LOCK" 2> /dev/null || exit 0
  trap 'rmdir "$LOCK" 2> /dev/null' EXIT
fi

# **Every section is read on its own** (#455-R7). The seven-day read, the to-do
# read, the actions, the findings and the practices run in parallel, because
# five sequential calls measured 16s against a 30s timeout and a slow GitHub
# would eat the margin; each one's output, error and exit status are kept
# apart, so one that fails prints its failure under its own heading and the
# others still show. A section's `could not be read` line is a report, not a
# stop: the hook still exits 0 and the session still starts.
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"; [[ "$MODE" == "--build" ]] && rmdir "$LOCK" 2> /dev/null' EXIT

read_to() {   # read_to NAME SECONDS COMMAND...: output, error and status in $TMP/NAME{,.err,.rc}
  local name="$1" secs="$2"; shift 2
  ( timeout "$secs" "$@" > "$TMP/$name" 2> "$TMP/$name.err" < /dev/null; echo $? > "$TMP/$name.rc" ) &
}
read_to week     60 "$BOARD"/board-inbox.py 7 --no-colour
read_to open     60 "$BOARD"/board-inbox.py --open --no-colour
read_to actions  25 "$BOARD"/board-actions.py --claude --no-colour
read_to findings 25 "$BOARD"/board-check.py --no-colour
read_to practice 10 "$BOARD"/board-practices.py
wait

# Why a read failed, in one line: its status, and the first line it said.
failure() {   # failure NAME HEADING: prints the failure line and succeeds when NAME failed
  local rc detail
  rc="$(cat "$TMP/$1.rc" 2>/dev/null)"; rc="${rc:-1}"
  [[ "$rc" == 0 ]] && return 1
  detail="$(head -1 "$TMP/$1.err" 2>/dev/null)"
  [[ "$rc" == 124 ]] && detail="timed out"
  printf '%s could not be read (exit %s)%s' "$2" "$rc" "${detail:+: $detail}"
}

# Opened or closed: news, not work, so only that section of the seven-day read
# (its comments are listed by `board-inbox.py 7`, on demand).
H_EVENTS="For Claude to read: opened or closed in the last 7 days"
if FAIL="$(failure week "$H_EVENTS (programme/scripts/board/board-inbox.py)")"; then
  SUMMARY="$FAIL"
else
  SUMMARY="$(awk '
    /^OPENED OR CLOSED/ { tail = 1; next }
    tail && /^  #/ { events[++e] = $0 }
    END {
      # Capped. A release week closes thirty issues at once, and an unbounded
      # summary of a busy week is the same wall of text this was meant to avoid.
      if (e) {
        printf "For Claude to read: opened or closed in the last 7 days (%d; newest last):\n", e
        start = e > 10 ? e - 9 : 1
        if (start > 1) printf "  ...%d earlier\n", start - 1
        for (i = start; i <= e; i++) print events[i]
      }
    }
  ' "$TMP/week")"
fi

# How the owner is named is the programme file's; a hook must not fail.
OWNER_NAME="$(python3 "$BOARD"/board-profile.py get accounts.owner_name 2>/dev/null)" || OWNER_NAME="the owner"

# The to-do list: the comment lines and the `...N more` line. The sentence for an
# empty list is not a finding, so a quiet board adds nothing.
H_OPEN="Waiting on Claude: comments from $OWNER_NAME not yet answered, of any age (programme/scripts/board/board-inbox.py --open --all)"
if FAIL="$(failure open "$H_OPEN")"; then
  OPEN_SECTION="$FAIL"
else
  OPEN="$(grep -E '^(  > |\.\.\.[0-9]+ more )' "$TMP/open" 2>/dev/null || true)"
  OPEN_SECTION="${OPEN:+$H_OPEN:$'\n'$OPEN}"
fi

# Reports from the scheduled workflows. Owner, 2026-09-27: "can you add a hook so
# you notice a new report?" They are written as issues by the github-actions bot
# and edited on later runs, which leaves no comment for the to-do list to count.
# `board-inbox.py` lists them in their own section of the seven-day read.
H_REPORTS="For Claude to read: reports from the scheduled workflows, opened, updated or closed (programme/scripts/board/board-inbox.py)"
if FAIL="$(failure week "$H_REPORTS")"; then
  REPORTS_SECTION="$FAIL"
else
  REPORTS="$(sed -n '/^REPORTS FROM THE SCHEDULED WORKFLOWS/,/^$/p' "$TMP/week" | grep -E '^  #[0-9]+' || true)"
  REPORTS_SECTION="${REPORTS:+$H_REPORTS:$'\n'$REPORTS}"
fi

# What is waiting on Claude, and what does not add up (#347 R2): the actions
# report and the transition check, both on the board model.
H_ACTIONS="Waiting on Claude: actions on the board (programme/scripts/board/board-actions.py --claude for the detail)"
if FAIL="$(failure actions "$H_ACTIONS")"; then
  ACTIONS_SECTION="$FAIL"
else
  ACTIONS="$(grep -E '^  #[0-9]+' "$TMP/actions" 2>/dev/null | head -40 || true)"
  ACTIONS_SECTION="${ACTIONS:+$H_ACTIONS:$'\n'$ACTIONS}"
fi

# Only the findings. A clean run says nothing is missing, which is worth nothing in
# context and would be repeated into every later turn. A finding's issue is at
# column 0.
H_FINDINGS="For Claude to fix: incomplete for their type and step (programme/scripts/board/board-check.py)"
if FAIL="$(failure findings "$H_FINDINGS")"; then
  FINDINGS_SECTION="$FAIL"
else
  FINDINGS="$(grep -E '^#[0-9]+' "$TMP/findings" 2>/dev/null | head -20 || true)"
  FINDINGS_SECTION="${FINDINGS:+$H_FINDINGS:$'\n'$FINDINGS}"
fi

# #407 R3: read every session, since a session start is not a repetition of the
# previous one. Its stderr is the reason when it cannot judge (the live checkout
# missing), so it reaches the session rather than being thrown away.
H_PRACTICE="Programme activities overdue, whose move is the activity's owner in the programme's docs/1.4 (programme/scripts/board/board-practices.py)"
if FAIL="$(failure practice "Programme activities could not be judged (programme/scripts/board/board-practices.py)")"; then
  PRACTICE_SECTION="$FAIL"
else
  PRACTICE="$(grep -E 'OVERDUE|never logged' "$TMP/practice" 2>/dev/null || true)"
  PRACTICE_SECTION="${PRACTICE:+$H_PRACTICE:$'\n'$PRACTICE}"
fi

# The order is the one INTRO says: events (SUMMARY), then these.
EXTRA=""
for section in "$OPEN_SECTION" "$REPORTS_SECTION" "$ACTIONS_SECTION" "$FINDINGS_SECTION" "$PRACTICE_SECTION"; do
  [[ -n "$section" ]] && EXTRA="$EXTRA"$'\n\n'"$section"
done

[[ -z "$SUMMARY" && -z "$EXTRA" ]] && bail

# Written whole and moved into place, so a reader never sees half a cache.
printf '%s\n' "$SUMMARY$EXTRA" > "$CACHE.tmp" && mv "$CACHE.tmp" "$CACHE"
if [[ "$MODE" == "--build" ]]; then
  log "build end"
else
  emit_json "$(with_note "$INTRO

$SUMMARY$EXTRA")" && mark_delivered "$SID"
  log "sid=${SID:-?} end (built)"
fi
exit 0
