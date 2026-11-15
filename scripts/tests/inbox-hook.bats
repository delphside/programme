#!/usr/bin/env bats

# .claude/inbox-hook.sh, the SessionStart summary. Owner, 2026-09-27: "can you
# add a hook so you notice a new report?" The workflows report by writing an
# issue as the github-actions bot, so the hook has to pass on the inbox's
# Reports section, and say nothing about reports when there are none.
#
# Run from a copy of the hook in a scratch application whose `programme/` holds
# the hook and stub board scripts, so the cases are about the hook, not about
# GitHub. The hook's state is the application's, in its `.claude/`.

setup() {
  bats_load_library bats-support
  bats_load_library bats-assert
  F="$BATS_TEST_TMPDIR/repo"
  mkdir -p "$F/.claude" "$F/programme/.claude/hooks" "$F/programme/scripts/board" "$BATS_TEST_TMPDIR/bin"
  git init -q "$F"
  cp "$BATS_TEST_DIRNAME/../../.claude/hooks/inbox-hook.sh" "$BATS_TEST_DIRNAME/../../.claude/hooks/application-root.sh" \
    "$F/programme/.claude/hooks/"
  for s in board-actions.py board-check.py board-practices.py; do
    printf '#!/usr/bin/env bash\nexit 0\n' > "$F/programme/scripts/board/$s"
  done
  # How the owner is named is the programme file's, asked of board-profile.py.
  printf 'import sys\nsys.exit(print("Pat") if sys.argv[1:] == ["get", "accounts.owner_name"] else 1)\n' \
    > "$F/programme/scripts/board/board-profile.py"
  # The hook only asks that gh exists.
  printf '#!/usr/bin/env bash\nexit 0\n' > "$BATS_TEST_TMPDIR/bin/gh"
  chmod +x "$F/programme/scripts/board/"* "$BATS_TEST_TMPDIR/bin/gh"
}

inbox() {   # what the stub board-inbox.py prints
  printf '#!/usr/bin/env bash\ncat <<'"'"'OUT'"'"'\n%s\nOUT\n' "$1" > "$F/programme/scripts/board/board-inbox.py"
  chmod +x "$F/programme/scripts/board/board-inbox.py"
}

context() {
  run bash -c 'PATH="$1:$PATH" "$2/programme/.claude/hooks/inbox-hook.sh" | python3 -c "import json,sys; print(json.load(sys.stdin)[\"hookSpecificOutput\"][\"additionalContext\"])"' \
    _ "$BATS_TEST_TMPDIR/bin" "$F"
}

@test "a report the workflows wrote reaches the session's context" {
  inbox 'INBOX  since 2026-09-20

REPORTS FROM THE SCHEDULED WORKFLOWS
  #384   open    2026-09-26T06:15  Dependency advisories need review

OPENED OR CLOSED
  nothing opened or closed'
  context
  assert_output --partial "reports from the scheduled workflows"
  assert_output --partial "#384   open    2026-09-26T06:15  Dependency advisories need review"
}

@test "no report says nothing about reports" {
  inbox 'INBOX  since 2026-09-20

REPORTS FROM THE SCHEDULED WORKFLOWS
  no report opened, updated or closed

OPENED OR CLOSED
  #9     opened        something'
  context
  refute_output --partial "For Claude to read: reports from the scheduled workflows"
  assert_output --partial "#9"
}

@test "the owner is named as the programme file names him" {
  inbox 'INBOX  since 2026-09-20

#7  seven
  > 2026-10-01T09:00  a question'
  context
  assert_output --partial "comments from Pat not yet answered"
}

@test "with no programme file it says the owner and the session still starts" {
  inbox 'INBOX  since 2026-09-20

#7  seven
  > 2026-10-01T09:00  a question'
  rm "$F/programme/scripts/board/board-profile.py"
  context
  assert_success
  assert_output --partial "comments from the owner not yet answered"
}

@test "its state is the application's, in the application's .claude/, not the programme's" {
  inbox 'INBOX  since 2026-09-20

#7  seven
  > 2026-10-01T09:00  a question'
  context
  assert_success
  assert [ -e "$F/.claude/.inbox-hook.log" ]
  assert [ ! -e "$F/programme/.claude/.inbox-hook.log" ]
}

# The pin check at session start: the hook only calls `board-records.py pin`
# (the logic and its cases are `board/pin.py`'s) and passes its line on.
records() {   # what the stub board-records.py prints for `pin`
  printf '#!/usr/bin/env bash\n[[ "$1" == pin ]] && printf "%%s\\n" "%s"\nexit 0\n' "$1" > "$F/programme/scripts/board/board-records.py"
  chmod +x "$F/programme/scripts/board/board-records.py"
}

@test "a pin behind the programme is said at session start" {
  inbox 'INBOX  since 2026-09-20

OPENED OR CLOSED
  nothing opened or closed'
  records "The programme pin is 2 commit(s) behind origin/main"
  context
  assert_output --partial "The programme pin is 2 commit(s) behind origin/main"
}

@test "a pin that is not behind adds nothing" {
  inbox 'INBOX  since 2026-09-20

OPENED OR CLOSED
  nothing opened or closed'
  records ""
  context
  refute_output --partial "programme pin"
}

@test "a pin check that hangs does not hold the session" {
  inbox 'INBOX  since 2026-09-20

OPENED OR CLOSED
  nothing opened or closed'
  printf '#!/usr/bin/env bash\n[[ "$1" == pin ]] && sleep 60\nexit 0\n' > "$F/programme/scripts/board/board-records.py"
  chmod +x "$F/programme/scripts/board/board-records.py"
  start=$SECONDS
  context
  (( SECONDS - start < 20 ))
  refute_output --partial "programme pin"
}

# R15 of delphside/programme#176 (#455-R2, R7, R10): every heading says whose
# move it is, the text says what it shows in the order shown, and one failed
# read hides no other section.
board_script() {   # board_script NAME STATUS: a board script that prints stdin and exits STATUS
  local file="$F/programme/scripts/board/$1" body
  body="$(cat)"
  {
    printf '#!/usr/bin/env bash\n'
    [[ "$2" == 0 ]] || printf 'echo "boom from %s" >&2\nexit %s\n' "$1" "$2"
    printf '%s\n' "$body"
  } > "$file"
  chmod +x "$file"
}

everything() {   # every section has something to show
  board_script board-inbox.py 0 <<'BODY'
if [[ "$1" == --open ]]; then
  printf '%s\n' '  > 2026-10-01T09:00  #7  seven  a question' '...3 more on 2 issues (board-inbox.py --open --all)'
else
  printf '%s\n' 'INBOX  since 2026-09-20' '' 'REPORTS FROM THE SCHEDULED WORKFLOWS' \
    '  #384   open    2026-09-26T06:15  advisories' '' 'OPENED OR CLOSED' '  #9     opened        something'
fi
BODY
  board_script board-actions.py 0 <<< "echo '  #12  an action'"
  board_script board-check.py 0 <<< "echo '#13 a finding'"
  board_script board-practices.py 0 <<< "echo 'OVERDUE something'"
  board_script board-records.py 0 <<'BODY'
[[ "$1" == pin ]] && echo "The programme pin is 2 commit(s) behind origin/main"
[[ "$1" == check ]] && echo "The programme checkout is behind"
exit 0
BODY
}

@test "every_heading_names_whose_move_it_is" {
  everything
  context
  assert_success
  for heading in \
    "For Claude to fix: the programme checkout and its pin" \
    "For Claude to read: opened or closed in the last 7 days" \
    "Waiting on Claude: comments from Pat not yet answered, of any age" \
    "For Claude to read: reports from the scheduled workflows" \
    "Waiting on Claude: actions on the board" \
    "For Claude to fix: incomplete for their type and step" \
    "Programme activities overdue, whose move is the activity's owner"; do
    assert_output --partial "$heading"
  done
  # The intro says any age, and the sections come in the order it says.
  assert_output --partial "the owner's comments not yet answered, of any age"
  positions=$(printf '%s\n' "$output" | grep -n -E '^(For Claude to fix: the programme checkout|For Claude to read: opened|Waiting on Claude: comments|For Claude to read: reports|Waiting on Claude: actions|For Claude to fix: incomplete|Programme activities overdue)' | cut -d: -f1 | tr '\n' ' ')
  assert_equal "$(printf '%s\n' $positions | wc -l)" 7
  assert_equal "$positions" "$(printf '%s\n' $positions | sort -n | tr '\n' ' ')"
  # The capped list's counting line passes through.
  assert_output --partial "...3 more on 2 issues"
  # And a later session reads the same sections from the cache, whose line says any age.
  context
  assert_output --partial "of any age (from a cache"
  assert_output --partial "Waiting on Claude: comments from Pat not yet answered, of any age"
}

@test "one_failed_read_hides_no_other_section" {
  everything
  # The seven-day read fails while the to-do read succeeds.
  board_script board-inbox.py 0 <<'BODY'
[[ "$1" == --open ]] && { echo '  > 2026-10-01T09:00  #7  seven  a question'; exit 0; }
echo "week boom" >&2
exit 1
BODY
  context
  assert_success
  assert_output --partial "opened or closed in the last 7 days (programme/scripts/board/board-inbox.py) could not be read (exit 1): week boom"
  assert_output --partial "reports from the scheduled workflows, opened, updated or closed (programme/scripts/board/board-inbox.py) could not be read"
  assert_output --partial "  > 2026-10-01T09:00  #7  seven  a question"
  assert_output --partial "#12  an action"
  assert_output --partial "#13 a finding"
  assert_output --partial "OVERDUE something"

  # The reverse: the to-do read fails while the seven-day read succeeds.
  board_script board-inbox.py 0 <<'BODY'
[[ "$1" == --open ]] && { echo "open boom" >&2; exit 1; }
printf '%s\n' 'OPENED OR CLOSED' '  #9     opened        something'
BODY
  rm -f "$F/.claude/.inbox-cache"
  context
  assert_success
  assert_output --partial "not yet answered, of any age (programme/scripts/board/board-inbox.py --open --all) could not be read (exit 1): open boom"
  assert_output --partial "#9     opened        something"
  assert_output --partial "#12  an action"

  # Two others failing, one of them a practice that cannot be judged, say so too.
  everything
  board_script board-actions.py 3 <<< "true"
  board_script board-practices.py 2 <<< "true"
  rm -f "$F/.claude/.inbox-cache"
  context
  assert_success
  assert_output --partial "actions on the board (programme/scripts/board/board-actions.py --claude for the detail) could not be read (exit 3): boom from board-actions.py"
  assert_output --partial "Programme activities overdue, whose move is the activity's owner in the programme's docs/1.4 (programme/scripts/board/board-practices.py) could not be read (exit 2): boom from board-practices.py"
  assert_output --partial "#9     opened        something"
  assert_output --partial "#13 a finding"
}
