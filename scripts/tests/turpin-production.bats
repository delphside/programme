#!/usr/bin/env bats

# The production role and settle (test-design.md S29, S30, S59; rules R26, R27).
# The production-role gates are shown in CI only: on a real host they are shown
# by the owner's --check runs and by the first production deploy (part 8).

setup() {
  bats_load_library bats-support
  bats_load_library bats-assert
  load turpin_world
  world_new
}

# a release made and its work packages and issues on the board
released() {
  ref_commit "a feature" 12 555 560 570
  gh_issue 12 Requirement "" 0.10.2 0 ""
  gh_issue 555 Project "" 0.10.2 0 "Production Release"
  gh_issue 560 Task "" 0.10.2 0 ""
  gh_issue 570 Project "" 2026.11.03-1 0 "Application Tooling"
  release_ready "12|Requirement||0|" "555|Project||0|Production Release" "560|Task||0|"
  # the commits also reference an Application Tooling package in its own date milestone
  gh_project 555 Development
  gh_project 570 Development
  run d release --expect 0.10.2
  [ "$status" -eq 0 ] || { echo "release failed: $output" >&2; return 1; }
}

@test "production_refuses_a_version_without_a_record (S29, R26)" {
  commit_change one; build_ok "$SHA"
  local before; before="$(snapshot)"
  run d deploy production 0.10.2
  assert_failure 1
  assert_output --partial "refused at gate production-record"
  assert_equal "$(snapshot)" "$before"
}

@test "production_refuses_a_raw_sha (S29, R26)" {
  commit_change one; build_ok "$SHA"
  local before; before="$(snapshot)"
  run d deploy production "$SHA"
  assert_failure 1
  assert_output --partial "refused at gate production-record"
  assert_output --partial "--unrecorded"
  # a short SHA does not do either
  run d deploy production "${SHA:0:10}" --unrecorded "emergency"
  assert_failure 1
  assert_equal "$(snapshot)" "$before"
}

@test "unrecorded_override_copies_without_spending_a_version (S29, R26, R30)" {
  commit_change one; build_ok "$SHA"
  gh_milestone 0.10.2 "12|Requirement||0|"
  run d deploy production "$SHA" --unrecorded "the record tooling is down"
  assert_success
  assert_equal "$(rel "$SHA-server")" "$(cand "$SHA-server")"
  assert_equal "$(rel "$SHA-web")" "$(cand "$SHA-web")"
  assert_equal "$(host_state prod production)" finished
  assert_equal "$(running_digests_of prod acme-production)" "$(digests_of "$SHA")"
  [ -z "$(git -C "$W/remote.git" tag -l)" ]            # no version spent
  assert_equal "$(gh_log | wc -c)" 0                   # settle has nothing to move
  run grep -h "the record tooling is down" "$(run_log_latest deploy)"
  assert_success
  # the copy is a no-op where the same digests are there already
  local copies; copies="$(grep -c . "$W/logs/copies.log")"
  run d deploy production "$SHA" --unrecorded "again"
  assert_success
  assert_equal "$(grep -c . "$W/logs/copies.log")" "$copies"
}

@test "settle_acts_on_exactly_what_the_record_carries (S29, S30, R27)" {
  released
  run d deploy production 0.10.2
  assert_success
  assert_equal "$(host_state prod production)" finished
  assert_equal "$(running_digests_of prod acme-production)" "$(digests_of "$RSHA")"
  # a record is in the host's deploy folder, and production reads releases only
  assert_equal "$(jq -r .record.version "$(host_state_dir prod production)/deploys/1/meta.json")" 0.10.2
  # O14
  assert_regex "$(gh_log)" "GRAPHQL setIssueFieldValue issue=I_555 option=opt-post"
  refute_regex "$(gh_log)" "I_570"
  refute_regex "$(gh_log)" "issues/570"
  assert_regex "$(gh_log)" "POST repos/acme/acme/issues/555/comments body=Released in v0.10.2"
  assert_regex "$(gh_log)" "POST repos/acme/acme/issues/12/comments body=Released in v0.10.2"
  assert_regex "$(gh_log)" "PATCH repos/acme/acme/issues/12 state=closed state_reason=completed"
  assert_regex "$(gh_log)" "PATCH repos/acme/acme/issues/560 state=closed state_reason=completed"
  refute_regex "$(gh_log)" "PATCH repos/acme/acme/issues/555 "          # a work package is moved, not closed
  assert_regex "$(gh_log)" "PATCH repos/acme/acme/milestones/7 state=closed"
}

@test "settle_advances_a_carried_work_package_of_any_route (R27, docs/1.2 section 2.5)" {
  ref_commit "a feature" 12 590
  gh_issue 590 Project "" 0.10.2 0 "Application Tooling"
  release_ready "12|Requirement||0|" "590|Project||0|Application Tooling"
  gh_project 590 Development
  run d release --expect 0.10.2
  assert_success
  assert_equal "$(jq -c .carries.work_packages <<< "$(tag_record v0.10.2)")" '[590]'
  run d settle 0.10.2
  assert_success
  assert_regex "$(gh_log)" "GRAPHQL setIssueFieldValue issue=I_590 option=opt-post"
}

@test "settle_failure_exits_3_and_the_deploy_stands; settle_rerun_changes_nothing (S30, R27)" {
  released
  STUB_GH_FAIL='PATCH repos/acme/acme/issues/560' run d deploy production 0.10.2
  assert_failure 3
  assert_output --partial "settle of 0.10.2 failed; left to do: #560 close"
  # O15: the deploy stands
  assert_equal "$(host_state prod production)" finished
  assert_equal "$(running_digests_of prod acme-production)" "$(digests_of "$RSHA")"
  # the rerun finishes it
  run d settle 0.10.2
  assert_success
  assert_regex "$(gh_log)" "PATCH repos/acme/acme/issues/560 state=closed"
  assert_regex "$(gh_log)" "PATCH repos/acme/acme/milestones/7 state=closed"
  refute_regex "$(gh_log)" "570"
  # nothing is done twice
  assert_equal "$(grep -c 'setIssueFieldValue' "$W/gh/log")" 1
  assert_equal "$(grep -c 'issues/555/comments' "$W/gh/log")" 1
  # and again: no new mutation
  local before; before="$(gh_log)"
  run d settle 0.10.2
  assert_success
  assert_equal "$(gh_log)" "$before"
}

@test "a post-deploy check failing after a deploy that is otherwise exit 3 leaves 3 (S59, R29)" {
  released
  hook_exit post-deploy 1
  STUB_GH_FAIL='PATCH repos/acme/acme/issues/560' run d deploy production 0.10.2
  assert_failure 3
  assert_output --partial "check post-deploy reported exit 1"
  hook_clear post-deploy
}

@test "production deploys the record's digests from releases only (R26, R33)" {
  released
  # production's own credential cannot read candidates
  STUB_READ_DENY='/candidates$' run d deploy production 0.10.2
  assert_success
  # and the record's digests are the ones in releases
  assert_equal "$(running_digests_of prod acme-production)" "$(digests_of "$RSHA")"
}

@test "check_mode_changes_nothing, on deploy and on release (S32, R32, O20)" {
  ref_commit "a feature" 12
  release_ready "12|Requirement||0|"
  local before; before="$(snapshot)"
  run d release --check
  assert_success
  assert_output --partial "every release gate passed; nothing changed"
  assert_equal "$(snapshot)" "$before"
  [ -z "$(git -C "$W/remote.git" tag -l)" ]
  run d release --expect 0.10.2
  assert_success
  # deploys, production
  before="$(snapshot)"
  run d deploy production 0.10.2 --check
  assert_success
  assert_output --partial "nothing changed"
  assert_equal "$(snapshot)" "$before"
  run d deploy production "$RSHA" --check
  assert_failure 1
  assert_output --partial "production-record"
  run d deploy rehearsal "$RSHA" --check --off-level "first cycle"
  assert_success
  assert_equal "$(snapshot)" "$before"
  run grep -h '"event":"gate"' "$(run_log_latest deploy)"
  assert_output --partial '"name":"pre-deploy"'
  refute_output --partial '"name":"smoke"'
}
