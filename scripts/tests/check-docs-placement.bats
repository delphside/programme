#!/usr/bin/env bats

# check-docs.sh, step 3: this application's change documents are in the
# programme repository's live checkout (#485), so the placement check reads them
# there, and stops, saying where it looked, when the checkout is not. What it
# finds in the programme's content is reported and does not change the exit
# status in an application; with `--programme`, from the programme repository
# on its own, it is a gate (the last cases).
#
# npx and node are stubbed so that the lint and the mermaid parse do not run
# (they need the network and 146MB); the other steps run for real and are not
# asserted on.

setup() {
  bats_load_library bats-support
  bats_load_library bats-assert
  load fixtures
  use_fake_profiles
  # The script finds its application from the repository it is run in, so it
  # runs in a scratch application whose profile is the fake one's (#485).
  APP="$BATS_TEST_TMPDIR/widget"
  mkdir -p "$APP/scripts" "$APP/docs"
  git init -q "$APP"
  DOCS="$BATS_TEST_DIRNAME/../docs"
  printf '# 9.1.1 Overview\n\nAn overview.\n\n## One section\n' > "$APP/docs/9.1.1-overview.md"
  printf 'indexed\n' > "$APP/docs/README.md"
  for n in one two; do
    printf '#!/bin/sh\necho "ran fake check %s"\nexit 0\n' "$n" > "$APP/scripts/fake-check-$n.sh"
    chmod +x "$APP/scripts/fake-check-$n.sh"
  done
  (cd "$APP" && python3 "$DOCS/document-map.py" --write > /dev/null)
  CHECK="$DOCS/check-docs.sh"
  STUBS="$BATS_TEST_TMPDIR/stubs"
  mkdir -p "$STUBS"
  # npx records what it is asked to lint; node stands in for the mermaid parse.
  printf '#!/bin/sh\nprintf "%%s\\n" "$@" > "%s/npx-args"\nexit 0\n' "$BATS_TEST_TMPDIR" > "$STUBS/npx"
  printf '#!/bin/sh\nexit 0\n' > "$STUBS/node"
  chmod +x "$STUBS/npx" "$STUBS/node"
  LIVE="$BATS_TEST_TMPDIR/programme"
  mkdir -p "$LIVE"
  cp -r "$FAKES/live/applications" "$LIVE/applications"
  CHANGES="$LIVE/applications/widget/3.6.7-changes"
}

placement() { run env PATH="$STUBS:$PATH" PROGRAMME_DIR="$1" bash -c 'cd "$1" && "$2"' _ "$APP" "$CHECK"; }

@test "placement: no live checkout fails, naming the path it looked at" {
  placement "$BATS_TEST_TMPDIR/not-cloned"
  assert_failure
  assert_output --partial "$BATS_TEST_TMPDIR/not-cloned"
  refute_output --partial "every change document is in"
}

@test "placement: a checkout with no change documents folder is reported rather than passing empty" {
  placement "$LIVE"
  assert_output --partial "MISSING"
  refute_output --partial "every change document is in"
  # Reported only: the exit status is what a clean folder gives, whatever the
  # other steps make of this machine.
  missing_status=$status
  mkdir -p "$CHANGES"
  placement "$LIVE"
  assert_equal "$status" "$missing_status"
}

@test "placement: a stray document at the top of the folder is reported" {
  mkdir -p "$CHANGES"
  : > "$CHANGES/README.md"
  : > "$CHANGES/stray-note.md"
  placement "$LIVE"
  assert_output --partial "STRAY   stray-note.md"
  # Reported only: the exit status is what a clean folder gives, whatever the
  # other steps make of this machine.
  stray_status=$status
  rm "$CHANGES/stray-note.md"
  placement "$LIVE"
  assert_equal "$status" "$stray_status"
}

@test "placement: the grandfathered documents and the folders are in place" {
  mkdir -p "$CHANGES/workstreams/a/1-x"
  : > "$CHANGES/README.md"
  : > "$CHANGES/workstreams/a/1-x/1-design.md"
  placement "$LIVE"
  assert_success
  assert_output --partial "every change document is in an issue or release folder"
}

@test "placement: the grandfathered list is the application's programme profile's, not a built-in one" {
  mkdir -p "$CHANGES"
  : > "$CHANGES/old-design.md"
  : > "$CHANGES/25-rate-limiting-test-design.md"
  placement "$LIVE"
  refute_output --partial "STRAY   old-design.md"
  assert_output --partial "STRAY   25-rate-limiting-test-design.md"
}

@test "the application's own checks are the profile's, run in order, and a failure fails the script" {
  mkdir -p "$CHANGES"
  placement "$LIVE"
  assert_success
  assert_output --partial "first fake check"
  assert_output --partial "ran fake check one"
  assert_output --partial "ran fake check two"
  printf '#!/bin/sh\necho "second one is red"\nexit 1\n' > "$APP/scripts/fake-check-two.sh"
  placement "$LIVE"
  assert_failure
  assert_output --partial "second one is red"
}

@test "the linter skips what the profile says besides the programme's own folders" {
  mkdir -p "$CHANGES"
  placement "$LIVE"
  grep -qx '#vendored' "$BATS_TEST_TMPDIR/npx-args"
  grep -qx '#programme' "$BATS_TEST_TMPDIR/npx-args"
  ! grep -qx '#old-crates' "$BATS_TEST_TMPDIR/npx-args"
}

@test "a profile that cannot be read fails the script and says which key" {
  mkdir -p "$CHANGES"
  printf 'application = "widget"\n' > "$BATS_TEST_TMPDIR/bare.toml"
  run env PATH="$STUBS:$PATH" PROGRAMME_DIR="$LIVE" PROGRAMME_PROFILE="$BATS_TEST_TMPDIR/bare.toml" \
    bash -c 'cd "$1" && "$2"' _ "$APP" "$CHECK"
  assert_failure
  assert_output --partial "documents.lint_ignore"
}

@test "map: a stale map says so and advises regenerating it" {
  printf '\n## A new section\n' >> "$APP/docs/9.1.1-overview.md"
  placement "$LIVE"
  assert_failure
  assert_output --partial "STALE   the document map"
  assert_output --partial "document-map.py --write"
}

@test "map: a failure that is not staleness shows the real error and does not advise --write" {
  printf '\n## One section\n' >> "$APP/docs/9.1.1-overview.md"
  (cd "$APP" && python3 "$DOCS/document-map.py" --write > /dev/null 2>&1 || true)
  placement "$LIVE"
  assert_failure
  assert_output --partial "the document map could not be checked"
  assert_output --partial "duplicate headings"
  refute_output --partial "STALE   the document map"
  refute_output --partial "document-map.py --write"
}

@test "run from inside the programme/ submodule of an application, it checks the application" {
  mkdir -p "$CHANGES"
  # a plain copy stands in for the submodule: the application is the repository around it
  cp -r "$BATS_TEST_DIRNAME/../.." "$APP/programme" 2>/dev/null || true
  find "$APP/programme" -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null
  rm -rf "$APP/programme/.git"
  run env PATH="$STUBS:$PATH" PROGRAMME_DIR="$LIVE" bash -c 'cd "$1" && programme/scripts/docs/check-docs.sh' _ "$APP"
  assert_success
  assert_output --partial "first fake check"
  assert_output --partial "the document map lists every heading"
}

# --- from the programme repository on its own (--programme) -------------------------
# A fake programme repository: the scripts and the programme file, and change
# documents in the two places the programme keeps them. There is no application,
# so what reads one says it does not apply, and the placement check is a gate.

programme_repo() {
  PGM="$BATS_TEST_TMPDIR/fake-programme"
  mkdir -p "$PGM/scripts" "$PGM/config" "$PGM/docs" "$PGM/records/2.5-changes/process-definition/1-x" \
    "$PGM/applications/widget/3.6.7-changes/workstreams/a/2-y"
  git init -q "$PGM"
  cp -r "$DOCS" "$PGM/scripts/docs"
  cp -r "$BATS_TEST_DIRNAME/../board" "$PGM/scripts/board"
  find "$PGM/scripts" -name __pycache__ -prune -exec rm -rf {} +
  cp "$FAKES/programme-config.toml" "$PGM/config/programme.toml"
  printf '# One\n\nSee [two](2.md#two).\n' > "$PGM/docs/1.md"
  printf '# Two\n' > "$PGM/docs/2.md"
  : > "$PGM/records/2.5-changes/README.md"
  : > "$PGM/records/2.5-changes/process-definition/1-x/1-design.md"
  : > "$PGM/applications/widget/3.6.7-changes/README.md"
  cp "$FAKES/live/applications/widget/3.6.6-profile.md" "$PGM/applications/widget/"
  : > "$PGM/applications/widget/3.6.7-changes/workstreams/a/2-y/2-design.md"
}

programme_check() { run env -u PROGRAMME_PROFILE -u PROGRAMME_CONFIG -u PROGRAMME_DIR PATH="$STUBS:$PATH" "$PGM/scripts/docs/check-docs.sh" --programme; }

@test "programme: a clean repository passes, and says what does not apply to it" {
  programme_repo
  programme_check
  assert_success
  assert_output --partial "every change document is in an issue or release folder"
  assert_output --partial "not applicable here"
  refute_output --partial "ran fake check"
}

@test "programme: the programme's own documents are linted and not skipped as the submodule" {
  programme_repo
  programme_check
  grep -qx '#.claude/worktrees' "$BATS_TEST_TMPDIR/npx-args"
  ! grep -qx '#programme' "$BATS_TEST_TMPDIR/npx-args"
  ! grep -qx '#.claude/skills' "$BATS_TEST_TMPDIR/npx-args"
}

@test "programme: a stray change document in the programme's records fails the gate" {
  programme_repo
  : > "$PGM/records/2.5-changes/stray-note.md"
  programme_check
  assert_failure
  assert_output --partial "STRAY   stray-note.md"
}

@test "programme: a stray in an application's change documents fails it too, and a listed one does not" {
  programme_repo
  : > "$PGM/applications/widget/3.6.7-changes/old-design.md"
  programme_check
  assert_success
  : > "$PGM/applications/widget/3.6.7-changes/new-note.md"
  programme_check
  assert_failure
  assert_output --partial "STRAY   new-note.md"
}

@test "programme: a broken link in its documents fails the gate" {
  programme_repo
  printf '# One\n\nSee [two](2.md#nope).\n' > "$PGM/docs/1.md"
  programme_check
  assert_failure
  assert_output --partial "no such heading there"
}

@test "programme: an application with no profile has no list, so every document at the top of its folder is a stray" {
  programme_repo
  rm "$PGM/applications/widget/3.6.6-profile.md"
  programme_check
  assert_success
  : > "$PGM/applications/widget/3.6.7-changes/old-design.md"
  programme_check
  assert_failure
  assert_output --partial "STRAY   old-design.md"
}

@test "programme: two profiles in one application is ambiguous and fails the gate" {
  programme_repo
  cp "$PGM/applications/widget/3.6.6-profile.md" "$PGM/applications/widget/3.6.6-other.md"
  programme_check
  assert_failure
  assert_output --partial "AMBIGUOUS"
}

@test "programme: the grandfathered list is each application's profile's, so removing a row makes the document a stray" {
  programme_repo
  : > "$PGM/applications/widget/3.6.7-changes/old-design.md"
  programme_check
  assert_success
  grep -v 'old-design' "$PGM/applications/widget/3.6.6-profile.md" > "$BATS_TEST_TMPDIR/p.md"
  cp "$BATS_TEST_TMPDIR/p.md" "$PGM/applications/widget/3.6.6-profile.md"
  programme_check
  assert_failure
  assert_output --partial "STRAY   old-design.md"
}

@test "programme: a document listed for one application does not excuse the same name in another" {
  programme_repo
  mkdir -p "$PGM/applications/gadget/3.7.7-changes"
  sed 's/widget/gadget/g; s/3\.6\./3.7./g' "$PGM/applications/widget/3.6.6-profile.md" | grep -v 'old-design' > "$PGM/applications/gadget/3.7.6-profile.md"
  : > "$PGM/applications/gadget/3.7.7-changes/old-design.md"
  programme_check
  assert_failure
  assert_output --partial "STRAY   old-design.md (in $PGM/applications/gadget/3.7.7-changes)"
}
