#!/usr/bin/env bats

# The board's half of a release, called through `board-release.py` (design §6, *The
# board model's part*): the tests-passed gate, and a board, git or GitHub that
# cannot be read. A read that cannot be made refuses; it is never read as empty.
# The rules themselves are tested in scripts/board/tests/test_release_*.py.

setup() {
  bats_load_library bats-support
  bats_load_library bats-assert
  load deliver_world
  world_new
}

UNTICKED='## Test approach

### Functional user tests — Preview

- [ ] **owner** — look at it

### Technical tests — Rehearsal

- [x] **Claude** — ran it
'

# a release ready to make, whose milestone holds #12 and a work package #40
ready_with_package() {
  ref_commit "a feature and a package" 12 40
  release_ready "12|Requirement||0|" "40|Project||0|Production Release"
}

set_body() {   # N BODY: the issue's body in the fixture
  local f; f="$(gh_issues_file)"
  jq -c --argjson n "$1" --arg b "$2" 'map(if .number == $n then .body = $b else . end)' "$f" > "$f.new" && mv "$f.new" "$f"
}

@test "an unticked test box refuses the release; an emergency reports it; ticked, it is made (S53b, R20a)" {
  ready_with_package
  set_body 40 "$UNTICKED"
  local before; before="$(snapshot)"
  run d release --expect 0.10.2
  assert_failure 1
  assert_output --partial "refused at gate tests-passed"
  assert_output --partial "#40"
  assert_output --partial "1 unticked under Functional user tests"
  assert_equal "$(snapshot)" "$before"
  # a package that never said what it would test refuses too
  set_body 40 "## Design"
  run d release --expect 0.10.2
  assert_failure 1
  assert_output --partial "no Functional user tests or Technical tests heading"
  # ticked: made
  set_body 40 "$(printf '## Test approach\n\n### Functional user tests — Preview\n\n- [x] **Claude** — a\n\n### Technical tests — Rehearsal\n\n- [x] **Claude** — b\n')"
  run d release --expect 0.10.2
  assert_success
  assert_equal "$(jq -c .carries.work_packages <<< "$(tag_record v0.10.2)")" '[40]'
}

@test "the tests-passed gate is a check under --emergency: the release is made and says what was not ticked (S53b, R20a)" {
  set_version 0.10.0; commit_change "base"; local C0="$SHA"; text_tag v0.10.0 "$C0"
  STUB_HEALTH_JSON='{"app_version":"0.10.0"}'; export STUB_HEALTH_JSON
  git -C "$W/work" checkout -q -b emergency "$C0"
  set_version 0.10.2; printf 'emergency fix\n' > "$W/work/src.txt"
  git -C "$W/work" commit -qam "emergency fix"$'\n\nRefs #40'; git -C "$W/work" push -q origin emergency
  local E; E="$(git -C "$W/work" rev-parse HEAD)"
  build_ok "$E"; deploy_rehearsal "$E"; assert_success
  gh_checks "$E" e2e=success
  git -C "$W/work" checkout -q -f main
  gh_milestone 0.10.2 "40|Project||0|Production Release"
  set_body 40 "$UNTICKED"
  run d release --expect 0.10.2 --commit "$E" --emergency "outage"
  assert_success
  assert_output --partial "check tests-passed: emergency: not every test is ticked: #40"
  run jq -r 'select(.event=="gate" and .name=="tests-passed") | .result + " " + .detail' "$(run_log_latest release)"
  assert_output --partial "reported emergency: not every test is ticked: #40"
}

@test "a board that cannot be read refuses the release, and changes nothing (R20)" {
  ref_commit "a feature" 12
  release_ready "12|Requirement||0|"
  local before; before="$(snapshot)"
  STUB_GH_FAIL='GET repos/acme/acme/issues$' run d release --expect 0.10.2
  assert_failure 1
  assert_output --partial "refused at gate milestone"
  assert_equal "$(snapshot)" "$before"
  run d release --expect 0.10.2
  assert_success
}

@test "checks that cannot be read refuse; they are not read as missing (R18)" {
  ref_commit "a feature" 12
  release_ready "12|Requirement||0|"
  STUB_GH_FAIL='check-runs' run d release --expect 0.10.2
  assert_failure 1
  assert_output --partial "refused at gate ci-passed"
  assert_output --partial "GitHub refused"
  gh_checks "$RSHA" e2e=pending
  run d release --expect 0.10.2
  assert_failure 1
  assert_output --partial "check e2e is pending"
}

@test "settle that cannot read the board leaves everything and exits 3; a rerun settles (R27)" {
  ref_commit "a feature" 12
  release_ready "12|Requirement||0|"
  run d release --expect 0.10.2
  assert_success
  gh_issue 12 Requirement "" 0.10.2 0 ""
  local before; before="$(gh_log)"
  STUB_GH_FAIL='GET repos/acme/acme/issues/12$' run d settle 0.10.2
  assert_failure 3
  assert_output --partial "settle of 0.10.2 failed; left to do: #12"
  assert_output --partial "because: "
  assert_equal "$(gh_log | grep -c 'issues/12')" 0
  run d settle 0.10.2
  assert_success
  assert_regex "$(gh_log)" "PATCH repos/acme/acme/issues/12 state=closed"
}

@test "a GitHub Release that already exists is not made again (R22)" {
  ref_commit "a feature" 12
  release_ready "12|Requirement||0|"
  mkdir -p "$W/gh/state/releases"; : > "$W/gh/state/releases/v0.10.2"
  run d release --expect 0.10.2
  assert_success
  assert_equal "$(grep -c '^RELEASE create' "$W/gh/log")" 0
}
