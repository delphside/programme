#!/usr/bin/env bats

# The carried range starts at the release production runs (design sections 6 to 8):
# a release made while an earlier one is undeployed carries both, a revert inside the
# range takes an item out, and the deploy settles what the record lists.

setup() {
  bats_load_library bats-support
  bats_load_library bats-assert
  load deliver_world
  world_new
}

production_runs() {   # VERSION SHA
  fake_production "$1" "$2"
  echo 1 > "$(host_state_dir prod production)/counter"
}

file_commit() {   # NAME N: a commit of its own file, so a revert applies cleanly
  printf '%s\n' "$1" > "$W/work/$1.txt"
  commit_all "$1"$'\n\nRefs #'"$2"
}

# production runs 0.10.1; 0.10.2 made with #1 #2 #3, not deployed
first_release() {
  [[ -z "${OLD:-}" ]] || { file_commit old 6; OLDSHA="$SHA"; }
  set_version 0.10.1; commit_change "release 0.10.1"; C1="$SHA"; text_tag v0.10.1 "$C1"
  production_runs 0.10.1 "$C1"
  set_version 0.10.2
  local wp=() ; [[ -n "${FIRST_WP:-}" ]] && wp=("5|Project||0|Production Release")
  file_commit one 1; file_commit two 2; S2="$SHA"; file_commit three 3
  [[ -z "${FIRST_WP:-}" ]] || file_commit five 5
  release_ready "1|Requirement||0|" "2|Requirement||0|" "3|Requirement||0|" "${wp[@]}"
  run d release --expect 0.10.2; assert_success
  git -C "$W/work" pull -q --ff-only origin main
}

# the second release: #4 in 0.10.3, #1 #3 in the made-but-undeployed 0.10.2
second_release() {   # [revert]
  if [[ "${1:-}" == revert ]]; then
    git -C "$W/work" revert --no-edit "$S2" >/dev/null; git -C "$W/work" push -q origin HEAD:main
  fi
  file_commit four 4
  release_ready "4|Requirement||0|"; gh_milestone 0.10.3 "4|Requirement||0|"
}

issues_fixtures() {
  gh_issue 1 Requirement "" 0.10.2 0 ""; gh_issue 2 Requirement "" 0.10.2 0 ""
  gh_issue 3 Requirement "" 0.10.2 0 ""; gh_issue 4 Requirement "" 0.10.3 0 ""
  rm -f "$W"/gh/state/ms-new-* "$W"/gh/state/ms-closed-*
  gh_fixture repos_acme_acme_milestones '[{"number":7,"title":"0.10.2","state":"open"},{"number":8,"title":"0.10.3","state":"open"}]'
  : > "$W/gh/log"
}

@test "a release made while an earlier one is undeployed carries both (range from production's tag)" {
  first_release
  file_commit four 4
  release_ready "4|Requirement||0|"; gh_milestone 0.10.3 "4|Requirement||0|"
  gh_issue 1 Requirement "" 0.10.2 0 ""; gh_issue 2 Requirement "" 0.10.2 0 ""; gh_issue 3 Requirement "" 0.10.2 0 ""
  run d release --expect 0.10.3
  assert_success
  assert_equal "$(jq -c '.carries | [.work_packages, .issues]' <<< "$(tag_record v0.10.3)")" '[[],[1,2,3,4]]'
  assert_equal "$(jq -c '[.carries.releases[] | [.version, .issues]]' <<< "$(tag_record v0.10.3)")" '[["0.10.2",[1,2,3]]]'
}

@test "a Production Release work package of an earlier release in the range passes the gate; elsewhere it refuses (R20)" {
  FIRST_WP=1 first_release
  file_commit four 4; file_commit again 5
  release_ready "4|Requirement||0|"; gh_milestone 0.10.3 "4|Requirement||0|"
  gh_issue 5 Project "" 0.10.9 0 "Production Release"
  run d release --expect 0.10.3
  assert_failure 1
  assert_output --partial "not in milestone 0.10.3"
  gh_issue 5 Project "" 0.10.2 0 "Production Release"
  run d release --expect 0.10.3
  assert_success
  assert_equal "$(jq -c '.carries.releases[0].work_packages' <<< "$(tag_record v0.10.3)")" '[5]'
  assert_equal "$(jq -c '.carries.work_packages' <<< "$(tag_record v0.10.3)")" '[5]'
}

@test "deploying it settles both, closes both milestones; a rerun changes nothing" {
  first_release
  second_release
  run d release --expect 0.10.3; assert_success
  issues_fixtures
  run d deploy production 0.10.3
  assert_success
  assert_regex "$(gh_log)" "issues/4/comments body=Released in v0.10.3 \(deployed to production\)"
  assert_regex "$(gh_log)" "issues/1/comments body=Released in v0.10.2, deployed with v0.10.3"
  assert_regex "$(gh_log)" "issues/3/comments body=Released in v0.10.2, deployed with v0.10.3"
  assert_regex "$(gh_log)" "milestones/7 state=closed"
  assert_regex "$(gh_log)" "milestones/8 state=closed"
  # the board's startswith match still reads them
  assert_regex "$(gh_log)" "body=Released in v0\.10\.2"
  # a rerun: the comments exist and the milestones are closed
  local f; for f in "$W"/gh/state/ms-closed-*; do :; done
  gh_fixture repos_acme_acme_milestones '[{"number":7,"title":"0.10.2","state":"closed"},{"number":8,"title":"0.10.3","state":"closed"}]'
  jq -nc '[{body:"Released in v0.10.2, deployed with v0.10.3"}]' > "$W/gh/fix/repos_acme_acme_issues_1_comments.json"
  jq -nc '[{body:"Released in v0.10.2, deployed with v0.10.3"}]' > "$W/gh/fix/repos_acme_acme_issues_3_comments.json"
  jq -nc '[{body:"Released in v0.10.3 (deployed to production)"}]' > "$W/gh/fix/repos_acme_acme_issues_4_comments.json"
  gh_issue 1 Requirement "" 0.10.2 0 "" CLOSED; gh_issue 3 Requirement "" 0.10.2 0 "" CLOSED; gh_issue 4 Requirement "" 0.10.3 0 "" CLOSED
  : > "$W/gh/log"
  run d settle 0.10.3
  assert_success
  refute_regex "$(gh_log)" "(POST|PATCH)"
}

@test "the owner's scenario: #2 reverted between the releases is not carried, is removed from 0.10.2 and its state left alone" {
  first_release
  local t2; t2="$(git -C "$W/remote.git" rev-parse refs/tags/v0.10.2)"
  second_release revert
  gh_issue 1 Requirement "" 0.10.2 0 ""; gh_issue 2 Requirement "" 0.10.2 0 ""; gh_issue 3 Requirement "" 0.10.2 0 ""
  run d release --expect 0.10.3
  assert_success
  # the check names it before the deploy
  assert_output --partial "#2 is in 0.10.2 but not carried by 0.10.3"
  assert_equal "$(jq -c '.carries.issues' <<< "$(tag_record v0.10.3)")" '[1,3,4]'
  assert_equal "$(jq -c '.carries.releases[0] | [.issues, .dropped]' <<< "$(tag_record v0.10.3)")" '[[1,3],[2]]'
  issues_fixtures
  run d deploy production 0.10.3
  assert_success
  assert_regex "$(gh_log)" "issues/1/comments body=Released in v0.10.2, deployed with v0.10.3"
  assert_regex "$(gh_log)" "issues/3/comments body=Released in v0.10.2, deployed with v0.10.3"
  assert_regex "$(gh_log)" "issues/4/comments body=Released in v0.10.3 \(deployed to production\)"
  assert_regex "$(gh_log)" "issues/2/comments body=Not shipped: in 0.10.2 but not carried by v0.10.3"
  assert_regex "$(gh_log)" "PATCH repos/acme/acme/issues/2 milestone=null"
  refute_regex "$(gh_log)" "PATCH repos/acme/acme/issues/2 state"
  refute_regex "$(gh_log)" "issues/2/comments body=Released"
  assert_regex "$(gh_log)" "milestones/7 state=closed"
  assert_regex "$(gh_log)" "milestones/8 state=closed"
  # 0.10.2's own tag is untouched
  assert_equal "$(git -C "$W/remote.git" rev-parse refs/tags/v0.10.2)" "$t2"
}

@test "a revert of a commit outside the range has no effect: its own Refs still count" {
  OLD=1 first_release
  git -C "$W/work" revert --no-edit "$OLDSHA" >/dev/null
  git -C "$W/work" commit -q --amend -m "$(git -C "$W/work" log -1 --format=%B)"$'\n\nRefs #6'
  git -C "$W/work" push -q origin HEAD:main
  file_commit four 4
  release_ready "4|Requirement||0|" "6|Requirement||0|"; gh_milestone 0.10.3 "4|Requirement||0|" "6|Requirement||0|"
  gh_issue 1 Requirement "" 0.10.2 0 ""; gh_issue 2 Requirement "" 0.10.2 0 ""; gh_issue 3 Requirement "" 0.10.2 0 ""
  run d release --expect 0.10.3
  assert_success
  assert_equal "$(jq -c '.carries.issues' <<< "$(tag_record v0.10.3)")" '[1,2,3,4,6]'
}

@test "an emergency range still starts at production's tag" {
  set_version 0.10.0; commit_change "base"; C0="$SHA"; text_tag v0.10.0 "$C0"
  [[ -z "${OLD:-}" ]] || { file_commit old 6; OLDSHA="$SHA"; }
  set_version 0.10.1; commit_change "release 0.10.1"; C1="$SHA"; text_tag v0.10.1 "$C1"
  production_runs 0.10.0 "$C0"
  set_version 0.10.2; ref_commit "unreleased work on main" 9
  git -C "$W/work" checkout -q -b emergency "$C0"
  set_version 0.10.2; printf 'emergency fix\n' > "$W/work/src.txt"
  git -C "$W/work" commit -qam "emergency fix"$'\n\nRefs #30'; git -C "$W/work" push -q origin emergency
  local E; E="$(git -C "$W/work" rev-parse HEAD)"
  build_ok "$E"; deploy_rehearsal "$E"; assert_success
  gh_checks "$E" e2e=success
  git -C "$W/work" checkout -q -f main
  gh_milestone 0.10.2 "30|Requirement||0|"
  run d release --expect 0.10.2 --commit "$E" --emergency "outage"
  assert_success
  assert_equal "$(jq -c '.carries.issues' <<< "$(tag_record v0.10.2)")" '[30]'
  assert_equal "$(jq -c '.carries.releases' <<< "$(tag_record v0.10.2)")" '[]'
}
