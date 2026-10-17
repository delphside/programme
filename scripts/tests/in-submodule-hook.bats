#!/usr/bin/env bats

# .githooks/in-submodule/: a commit made inside the programme/ submodule of an
# application is refused (#485 T1: the submodule is read-only by rule, every
# write goes to the live checkout). The mechanism is the submodule's own
# `core.hooksPath`, set by the application's setup; these cases set it the same
# way, in a real submodule, and commit as git does.

setup() {
  bats_load_library bats-support
  bats_load_library bats-assert
  load fixtures
  use_fake_profiles
  export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t
  # The programme: the hooks folder and the board scripts the message asks, as in the repository.
  SRC="$BATS_TEST_TMPDIR/programme-src"
  mkdir -p "$SRC/.githooks" "$SRC/scripts"
  git init -q -b main "$SRC"
  cp -r "$BATS_TEST_DIRNAME/../../.githooks/in-submodule" "$SRC/.githooks/in-submodule"
  cp -r "$BATS_TEST_DIRNAME/../board" "$SRC/scripts/board"
  find "$SRC" -name __pycache__ -prune -exec rm -rf {} +
  git -C "$SRC" add -A
  git -C "$SRC" commit -qm "the programme"
  # An application carrying it as its submodule.
  APP="$BATS_TEST_TMPDIR/app"
  git init -q -b main "$APP"
  git -C "$APP" -c protocol.file.allow=always submodule add -q "$SRC" programme
  git -C "$APP" commit -qm "pin"
}

install() { git -C "$APP/programme" config core.hooksPath .githooks/in-submodule; }

change_in_submodule() { printf '%s\n' "$RANDOM" > "$APP/programme/note.txt"; git -C "$APP/programme" add note.txt; }

@test "a commit inside the submodule is refused, saying where to write instead" {
  install
  change_in_submodule
  run git -C "$APP/programme" commit -qm "edit the pinned copy"
  assert_failure
  assert_output --partial "commit refused: this is the pinned copy of the programme"
  assert_output --partial "$APP"
  assert_output --partial "the live checkout, $FAKES/live"
  # and nothing was committed
  assert_equal "$(git -C "$APP/programme" log --oneline | wc -l)" 1
}

@test "an amend is refused too" {
  install
  run git -C "$APP/programme" commit -q --amend -m "rewrite the pin's commit"
  assert_failure
  assert_output --partial "commit refused"
}

@test "a merge commit inside the submodule is refused" {
  install
  git -C "$APP/programme" -c core.hooksPath=/dev/null switch -q -c side
  printf 's\n' > "$APP/programme/side.txt"; git -C "$APP/programme" add side.txt
  git -C "$APP/programme" -c core.hooksPath=/dev/null commit -qm side
  git -C "$APP/programme" -c core.hooksPath=/dev/null switch -q main
  printf 'm\n' > "$APP/programme/main.txt"; git -C "$APP/programme" add main.txt
  git -C "$APP/programme" -c core.hooksPath=/dev/null commit -qm main
  run git -C "$APP/programme" merge --no-ff -m "merge side" side
  assert_failure
  assert_output --partial "commit refused"
}

@test "--no-verify still commits: the owner may set the rule aside" {
  install
  change_in_submodule
  run git -C "$APP/programme" commit -q --no-verify -m "deliberate"
  assert_success
}

@test "the application's own commits are not affected" {
  install
  printf 'a\n' > "$APP/file.txt"; git -C "$APP" add file.txt
  run git -C "$APP" commit -qm "an application commit"
  assert_success
}

@test "without the setup nothing refuses, which is why the setup scripts do it" {
  change_in_submodule
  run git -C "$APP/programme" commit -qm "unguarded"
  assert_success
}

@test "the live checkout, which is the same repository, can still be committed to even with the path set" {
  git -C "$SRC" config core.hooksPath .githooks/in-submodule
  printf 'r\n' > "$SRC/record.txt"; git -C "$SRC" add record.txt
  run git -C "$SRC" commit -qm "a record"
  assert_success
}

# A linked worktree of the application has a submodule of its own, with its own
# git directory and so its own configuration: the path set in the first one does not
# reach it, and the hook has to refuse there as well.
@test "in a linked worktree of the application, its submodule refuses a commit once the path is set" {
  git -C "$APP" worktree add -q "$BATS_TEST_TMPDIR/wt" -b other
  git -C "$BATS_TEST_TMPDIR/wt" -c protocol.file.allow=always submodule update -q --init
  WT="$BATS_TEST_TMPDIR/wt"
  printf 'x\n' > "$WT/programme/note.txt"; git -C "$WT/programme" add note.txt
  # not set: the first worktree's setup does not reach this submodule
  install
  run git -C "$WT/programme" commit -qm "unprotected"
  assert_success
  git -C "$WT/programme" reset -q --soft HEAD~1
  git -C "$WT/programme" config core.hooksPath .githooks/in-submodule
  run git -C "$WT/programme" commit -qm "edit the pinned copy"
  assert_failure
  assert_output --partial "commit refused: this is the pinned copy of the programme"
  assert_output --partial "$WT"
}
