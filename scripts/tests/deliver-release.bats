#!/usr/bin/env bats

# `deliver release` and the rehearsal's level (test-design.md S17 to S28, S48 to S53a;
# rules R15 to R25). The gates are shown to fail before they pass: each test
# gives the refusal first and the success after.

setup() {
  bats_load_library bats-support
  bats_load_library bats-assert
  load deliver_world
  world_new
}

# ---------------------------------------------------------------- the rehearsal starts at production's level (R15)

two_builds() {   # P (production's) and Q (another)
  commit_change production-build; build_ok "$SHA"; P="$SHA"
  commit_change other-build; build_ok "$SHA"; Q="$SHA"
}

@test "rehearsal_cycle_must_start_from_productions_record (S17, R15)" {
  two_builds
  fake_production 0.10.2 "$P"
  local before; before="$(snapshot)"
  run d deploy rehearsal "$Q"
  assert_failure 1
  assert_output --partial "refused at gate rehearsal-level"
  assert_output --partial "starts from production's current record"
  assert_equal "$(snapshot)" "$before"
  run d deploy rehearsal "$P"
  assert_success
  # a later deploy of the cycle may be any build
  run d deploy rehearsal "$Q"
  assert_success
}

@test "off_level_override_is_recorded (S17, R15, R30)" {
  two_builds
  fake_production 0.10.2 "$P"
  run d deploy rehearsal "$Q" --off-level "testing a fix first"
  assert_success
  run grep -h "testing a fix first" "$(run_log_latest deploy)"
  assert_success
  assert_output --partial '"flag":"off-level"'
}

@test "rehearsal_level_is_read_from_production_host_state_over_ssh (S48, R15)" {
  commit_change one; build_ok "$SHA"; local p1="$SHA"
  commit_change two; build_ok "$SHA"; local p2="$SHA"
  # the last settled record is 0.10.1 (p1); production's host state says 0.10.2 (p2)
  fake_production 0.10.2 "$p2"
  run d deploy rehearsal "$p1"
  assert_failure 1
  assert_output --partial "refused at gate rehearsal-level"
  run grep -c '"event":"ssh-read","env":"production"' "$(run_log_latest deploy)"
  assert_output 1
  assert_regex "$(cat "$W/logs/ssh.log")" "ssh prod: deliver-host status acme production"
  run d deploy rehearsal "$p2"
  assert_success
}

@test "rehearsal_first_deploy_refuses_when_production_runs_a_build_with_no_record (S49, R15)" {
  commit_change one; build_ok "$SHA"
  fake_production "" "$SHA"
  run d deploy rehearsal "$SHA"
  assert_failure 1
  assert_output --partial "refused at gate rehearsal-level"
  assert_output --partial "no record"
  run d deploy rehearsal "$SHA" --off-level "deployed before the tool"
  assert_success
  run grep -h "deployed before the tool" "$(run_log_latest deploy)"
  assert_success
}

@test "a rehearsal with no production deliver state needs --off-level too (S39 shape, R15)" {
  commit_change one; build_ok "$SHA"
  run d deploy rehearsal "$SHA"
  assert_failure 1
  assert_output --partial "production has no deliver state"
}

# ---------------------------------------------------------------- the release

@test "release_refuses_a_commit_rehearsal_did_not_pass; then releases what rehearsal ran (S18, R16, R25)" {
  ref_commit "a feature" 12
  build_ok "$SHA"; local a="$SHA"
  gh_checks "$a" e2e=success
  gh_milestone 0.10.2 "12|Requirement||0|"
  # rehearsal has never deployed
  run d release --expect 0.10.2
  assert_failure 1
  assert_output --partial "refused at gate rehearsal-passed"
  # rehearsal runs another commit than the one named
  deploy_rehearsal "$a"; assert_success
  ref_commit "another" 12
  build_ok "$SHA"; local b="$SHA"
  gh_checks "$b" e2e=success
  run d release --expect 0.10.2 --commit "$b"
  assert_failure 1
  assert_output --partial "rehearsal-passed"
  # its smoke test did not pass
  local m; m="$(host_state_dir rehearsal rehearsal)/deploys/1/meta.json"
  jq '.smoke = "failed"' "$m" > "$m.new" && mv "$m.new" "$m"
  run d release --expect 0.10.2
  assert_failure 1
  assert_output --partial "rehearsal-passed"
  # the deploy did not finish
  jq '.smoke = "passed"' "$m" > "$m.new" && mv "$m.new" "$m"
  printf 'in progress: smoke\ndeploy=1\n' > "$(host_state_dir rehearsal rehearsal)/state"
  run d release --expect 0.10.2
  assert_failure 1
  assert_output --partial "rehearsal-passed"
  printf 'finished\ndeploy=1\n' > "$(host_state_dir rehearsal rehearsal)/state"
  local before; before="$(snapshot)"
  run d release --expect 0.10.2
  assert_success
  # O10
  local server web; server="$(cand "$a-server")"; web="$(cand "$a-web")"
  assert_equal "$(rel 0.10.2-server)" "$server"
  assert_equal "$(rel 0.10.2-web)" "$web"
  assert_equal "$(reg_meta acme/releases "$server")" "$(reg_meta acme/candidates "$server")"
  assert_equal "$(tag_record v0.10.2 | jq -S .)" "$(registry_record 0.10.2 | jq -S .)"
  run jq -r '[.record, .application, .version, .commit, .images.server, .images.web, (.made|type), .rehearsal.environment, .rehearsal.smoke, (.emergency|tostring), (.rehearsal_skipped|tostring), (.set_aside|tostring), (.tool.programme|type), (.carries|tostring)] | join(" ")' <<< "$(tag_record v0.10.2)"
  assert_output "1 acme 0.10.2 $a $server $web string rehearsal passed null null [] string {\"work_packages\":[],\"issues\":[12]}"
  # O11
  assert_equal "$(remote_version)" 0.10.3
  assert_regex "$(gh_log)" "RELEASE create v0.10.2 notes-start-tag="
  assert_regex "$(gh_log)" "POST repos/acme/acme/milestones title=0.10.3"
  : "$before"
}

@test "skip_rehearsal_records_reason_and_raises_retrospective (S19, R16, R30)" {
  ref_commit "a feature" 12
  build_ok "$SHA"
  gh_checks "$SHA" e2e=success
  gh_milestone 0.10.2 "12|Requirement||0|"
  run d release --expect 0.10.2
  assert_failure 1
  run d release --expect 0.10.2 --commit "$SHA" --skip-rehearsal "rehearsal host down for the weekend"
  assert_success
  run jq -r '.rehearsal_skipped' <<< "$(tag_record v0.10.2)"
  assert_output "rehearsal host down for the weekend"
  run grep -h "rehearsal host down for the weekend" "$(run_log_latest release)"
  assert_success
  assert_regex "$(gh_log)" "POST repos/acme/acme/issues title=Retrospective: 0.10.2 released with rehearsal skipped"
  assert_regex "$(gh_log)" "rehearsal host down for the weekend"
}

@test "release_refuses_a_commit_not_on_main (S20, R17)" {
  git -C "$W/work" checkout -q -b side
  printf 'side\n' > "$W/work/src.txt"; git -C "$W/work" commit -qam "side work Refs #12"
  git -C "$W/work" push -q origin side
  SHA="$(git -C "$W/work" rev-parse HEAD)"
  release_ready "12|Requirement||0|"
  run d release --expect 0.10.2
  assert_failure 1
  assert_output --partial "refused at gate on-main"
  [ -z "$(git -C "$W/remote.git" tag -l v0.10.2)" ]
}

# the history an emergency needs: v0.10.0 and v0.10.1 released, main moved on
emergency_world() {
  set_version 0.10.0; commit_change "base"; C0="$SHA"; text_tag v0.10.0 "$C0"
  set_version 0.10.1; commit_change "release 0.10.1"; C1="$SHA"; text_tag v0.10.1 "$C1"
  set_version 0.10.2; ref_commit "unreleased work on main" 9; C2="$SHA"
  git -C "$W/work" checkout -q -b emergency "$C0"
  set_version 0.10.2; printf 'emergency fix\n' > "$W/work/src.txt"
  git -C "$W/work" commit -qam "emergency fix"$'\n\nRefs #30'; git -C "$W/work" push -q origin emergency
  E="$(git -C "$W/work" rev-parse HEAD)"
  git -C "$W/work" checkout -q -b late "$C1"
  set_version 0.10.2; printf 'late fix\n' > "$W/work/src.txt"
  git -C "$W/work" commit -qam "fix cut from 0.10.1"$'\n\nRefs #31'; git -C "$W/work" push -q origin late
  L="$(git -C "$W/work" rev-parse HEAD)"
  git -C "$W/work" checkout -q --orphan unrelated; git -C "$W/work" rm -rqf . >/dev/null 2>&1
  git -C "$W/work" checkout -q main -- . ; set_version 0.10.2; printf 'unrelated\n' > "$W/work/src.txt"
  git -C "$W/work" commit -qam "unrelated root"$'\n\nRefs #32'; git -C "$W/work" push -q origin unrelated
  U="$(git -C "$W/work" rev-parse HEAD)"
  git -C "$W/work" checkout -q -f main
}

emergency_ready() {   # COMMIT: built and on rehearsal, CI green, milestone 0.10.2 holds #30 and the main-only #9
  git -C "$W/work" checkout -q -f "$1"
  SHA="$1"; build_ok "$SHA"; deploy_rehearsal "$SHA"; assert_success
  gh_checks "$SHA" e2e=success
  git -C "$W/work" checkout -q -f main
}

@test "emergency_must_descend_from_the_release_production_runs (S20, R17)" {
  emergency_world
  # production runs 0.10.0: its record in host state, which is not the newest tag
  STUB_HEALTH_JSON='{"app_version":"0.10.0"}'; export STUB_HEALTH_JSON
  gh_milestone 0.10.2 "30|Requirement||0|"
  emergency_ready "$E"
  # without the flag a commit off main is refused
  run d release --expect 0.10.2 --commit "$E"
  assert_failure 1
  assert_output --partial "refused at gate on-main"
  # a commit that does not descend from the release production runs
  emergency_ready "$U"
  run d release --expect 0.10.2 --commit "$U" --emergency "customer outage"
  assert_failure 1
  assert_output --partial "refused at gate emergency-descent"
  assert_output --partial "does not descend from v0.10.0"
  [ -z "$(git -C "$W/remote.git" tag -l v0.10.2)" ]
}

@test "emergency_refuses_a_commit_carrying_unreleased_main; the cut from the release production runs passes when a newer tag exists (S20, S50, R17)" {
  emergency_world
  STUB_HEALTH_JSON='{"app_version":"0.10.0"}'; export STUB_HEALTH_JSON
  gh_milestone 0.10.2 "30|Requirement||0|"
  # cut from the newest tag (0.10.1, made but not run): holds main commits after 0.10.0
  emergency_ready "$L"
  run d release --expect 0.10.2 --commit "$L" --emergency "customer outage"
  assert_failure 1
  assert_output --partial "after v0.10.0 are on main"
  # cut from the tag production runs
  emergency_ready "$E"
  gh_milestone 0.10.2 "30|Requirement||0|"
  run d release --expect 0.10.2 --commit "$E" --emergency "customer outage"
  assert_success
  assert_equal "$(jq -r .emergency <<< "$(tag_record v0.10.2)")" "customer outage"
  run grep -h "customer outage" "$(run_log_latest release)"
  assert_success
}

@test "the same two cuts with production's record read from its host state (S50, R17)" {
  emergency_world
  # production has deliver state and its record names 0.10.0
  git -C "$W/work" checkout -q -f "$E"; build_ok "$E"; git -C "$W/work" checkout -q -f main
  fake_production 0.10.0 "$E"
  gh_milestone 0.10.2 "30|Requirement||0|"
  emergency_ready "$L"
  run d release --expect 0.10.2 --commit "$L" --emergency "outage"
  assert_failure 1
  assert_output --partial "are on main"
  emergency_ready "$E"
  gh_milestone 0.10.2 "30|Requirement||0|"
  run d release --expect 0.10.2 --commit "$E" --emergency "outage"
  assert_success
}

@test "emergency_release_moves_main_and_its_milestone_on; emergency_leaves_out_issues_evidenced_only_on_main and moves them (S27, S52, R24)" {
  emergency_world
  STUB_HEALTH_JSON='{"app_version":"0.10.0"}'; export STUB_HEALTH_JSON
  emergency_ready "$E"
  # an open issue in the milestone that no commit evidences at all
  gh_milestone 0.10.2 "30|Requirement||0|" "77|Requirement||0|"
  run d release --expect 0.10.2 --commit "$E" --emergency "outage"
  assert_failure 1
  assert_output --partial "refused at gate milestone"
  assert_output --partial "#77"
  # one evidenced only by a commit on main after the tag is left out and moved
  gh_milestone 0.10.2 "30|Requirement||0|" "9|Requirement||0|"
  run d release --expect 0.10.2 --commit "$E" --emergency "outage"
  assert_success
  assert_equal "$(jq -c .carries <<< "$(tag_record v0.10.2)")" '{"work_packages":[],"issues":[30]}'
  assert_equal "$(remote_version)" 0.10.3
  assert_regex "$(gh_log)" "PATCH repos/acme/acme/issues/9 milestone=100"
  refute_regex "$(gh_log)" "PATCH repos/acme/acme/issues/30 "
}

@test "release_refuses_while_a_required_check_is_not_green (S21, R18)" {
  ref_commit "a feature" 12
  release_ready "12|Requirement||0|"
  gh_checks "$RSHA" e2e=failure
  run d release --expect 0.10.2
  assert_failure 1
  assert_output --partial "refused at gate ci-passed"
  assert_output --partial "e2e is failure"
  gh_checks "$RSHA" lint=success
  run d release --expect 0.10.2
  assert_failure 1
  assert_output --partial "e2e is missing"
  gh_checks "$RSHA" e2e=success
  run d release --expect 0.10.2
  assert_success
}

@test "release_refuses_a_spent_or_lower_version (S22, R19)" {
  ref_commit "a feature" 12
  release_ready "12|Requirement||0|"
  # the tag exists already (a text tag from before the tool)
  text_tag v0.10.2 "$(git -C "$W/work" rev-parse HEAD~1)"
  run d release --expect 0.10.2
  assert_failure 1
  assert_output --partial "refused at gate version-spent-once"
  git -C "$W/work" tag -d v0.10.2 >/dev/null; git -C "$W/work" push -q origin :refs/tags/v0.10.2
  # a record for it is in releases from another commit
  mkdir -p "$W/registry/reg.test/ns/acme/releases"
  printf '{"record":1,"commit":"deadbeef","images":{}}\n' > "$W/rec.json"
  ( cd "$W/work" && . "$DELIVER_SRC/lib/common.sh" && . "$DELIVER_SRC/lib/registry.sh" && DELIVER_REGISTRY=reg.test/ns && record_push acme/releases 0.10.2-record "$W/rec.json" )
  run d release --expect 0.10.2
  assert_failure 1
  assert_output --partial "another commit or other digests"
  rm -rf "$W/registry/reg.test/ns/acme/releases/oci/0.10.2-record" "$W/registry/reg.test/ns/acme/releases/tags/0.10.2-record"
  # lower than a prod- tag of an earlier prefix
  text_tag prod-0.11.0 "$(git -C "$W/work" rev-parse HEAD~1)"
  run d release --expect 0.10.2
  assert_failure 1
  assert_output --partial "not higher than the newest release tag 0.11.0"
  # a new, higher version
  set_version 0.11.1
  ref_commit "next" 12
  release_ready "12|Requirement||0|"
  run d release --expect 0.11.1
  assert_success
  assert_equal "$(remote_version)" 0.11.2
}

@test "release_refuses_a_milestone_that_disagrees_with_the_commits (S23, R20)" {
  ref_commit "a feature" 12
  release_ready "12|Requirement||0|" "50|Requirement||0|"
  run d release --expect 0.10.2
  assert_failure 1
  assert_output --partial "refused at gate milestone"
  assert_output --partial "#50"
  # a Production Release work package the commits name, not in the milestone
  gh_milestone 0.10.2 "12|Requirement||0|"
  gh_issue 40 Project "" 2026.11.03-1 0 "Production Release"
  ref_commit "work for a package" 40
  build_ok "$SHA"; deploy_rehearsal "$SHA"; gh_checks "$SHA" e2e=success
  run d release --expect 0.10.2
  assert_failure 1
  assert_output --partial "#40"
  # a parent in the milestone is aside
  gh_milestone 0.10.2 "12|Requirement||0|" "40|Project||0|Production Release" "60|Project||2|"
  gh_issue 40 Project "" 0.10.2 0 "Production Release"
  run d release --expect 0.10.2
  assert_success
  assert_equal "$(jq -c .carries <<< "$(tag_record v0.10.2)")" '{"work_packages":[40],"issues":[12]}'
}

@test "parent_refs_counts_for_its_only_work_package (S51, R20)" {
  ref_commit "work under a parent" 70
  gh_issue 70 Project "" 0.10.2 1 ""
  release_ready "70|Project||1|" "71|Project|70|0|Production Release"
  run d release --expect 0.10.2
  assert_success
  assert_equal "$(jq -c .carries <<< "$(tag_record v0.10.2)")" '{"work_packages":[71],"issues":[]}'
}

@test "parent_refs_does_not_count_with_two_work_packages (S51, R20)" {
  ref_commit "work under a parent" 70
  release_ready "70|Project||2|" "71|Project|70|0|Production Release" "72|Project|70|0|Production Release"
  run d release --expect 0.10.2
  assert_failure 1
  assert_output --partial "#71"
  assert_output --partial "#72"
  ref_commit "work for each" 71 72
  build_ok "$SHA"; deploy_rehearsal "$SHA"; gh_checks "$SHA" e2e=success
  run d release --expect 0.10.2
  assert_success
}

@test "a work package of another route is neither counted nor carried; a Production Release one outside refuses (S53a, R20)" {
  ref_commit "tooling work" 80 12
  gh_issue 80 Project "" 2026.11.03-1 0 "Application Tooling"
  release_ready "12|Requirement||0|"
  run d release --expect 0.10.2
  assert_success
  assert_equal "$(jq -c .carries <<< "$(tag_record v0.10.2)")" '{"work_packages":[],"issues":[12]}'
}

@test "a Production Release work package outside the milestone refuses (S53a, R20)" {
  ref_commit "release work" 81 12
  gh_issue 81 Project "" "" 0 "Production Release"
  release_ready "12|Requirement||0|"
  run d release --expect 0.10.2
  assert_failure 1
  assert_output --partial "refused at gate milestone"
  assert_output --partial "#81"
}

@test "set_aside_milestone_needs_a_reason_and_an_overridable_profile (S53, R20, R30, R10)" {
  ref_commit "a feature" 12
  release_ready "12|Requirement||0|" "50|Requirement||0|"
  # (1) disagrees, no flag
  run d release --expect 0.10.2
  assert_failure 1
  # (2) the flag without a reason
  run d release --expect 0.10.2 --set-aside milestone
  assert_failure 1
  assert_output --partial "needs a reason"
  # (3) the profile does not list milestone
  sed -i 's/^overridable = .*/overridable = ["release-check"]/' "$W/work/app-profile.toml"
  run d release --expect 0.10.2 --set-aside milestone "known extra"
  assert_failure 1
  assert_output --partial "does not list milestone"
  sed -i 's/^overridable = .*/overridable = ["milestone", "release-check"]/' "$W/work/app-profile.toml"
  # (4) with a reason where it is overridable
  run d release --expect 0.10.2 --set-aside milestone "the extra issue is a notes issue"
  assert_success
  assert_equal "$(jq -c .set_aside <<< "$(tag_record v0.10.2)")" '[{"gate":"milestone","reason":"the extra issue is a notes issue"}]'
  assert_equal "$(jq -c .carries <<< "$(tag_record v0.10.2)")" '{"work_packages":[],"issues":[12,50]}'
}

@test "the milestone agreeing needs no flag, and set_aside is empty (S53, R20)" {
  ref_commit "a feature" 12
  release_ready "12|Requirement||0|"
  run d release --expect 0.10.2
  assert_success
  assert_equal "$(jq -c .set_aside <<< "$(tag_record v0.10.2)")" '[]'
}

@test "release_check_refusal_stops_the_release (S24, R21)" {
  ref_commit "a feature" 12
  release_ready "12|Requirement||0|"
  hook_exit release-check 1
  run d release --expect 0.10.2
  assert_failure 1
  assert_output --partial "refused at gate release-check"
  [ -z "$(git -C "$W/remote.git" tag -l v0.10.2)" ]
  run d release --expect 0.10.2 --set-aside release-check "owner accepts the patch with a functional change"
  assert_success
  assert_equal "$(jq -c .set_aside <<< "$(tag_record v0.10.2)")" '[{"gate":"release-check","reason":"owner accepts the patch with a functional change"}]'
  hook_clear release-check
}

@test "release_check passing leaves set_aside empty (S24)" {
  ref_commit "a feature" 12
  release_ready "12|Requirement||0|"
  run d release --expect 0.10.2
  assert_success
  assert_equal "$(jq -c .set_aside <<< "$(tag_record v0.10.2)")" '[]'
  run hook_calls
  assert_regex "$output" "release-check"
}

@test "release_refuses_a_mistyped_confirmation (S25, R16)" {
  ref_commit "a feature" 12
  release_ready "12|Requirement||0|"
  run bash -c "cd '$W/work' && printf '0.10.3\n' | '$DELIVER' release"
  assert_failure 1
  assert_output --partial 'confirmation "0.10.3" is not 0.10.2'
  run d release --expect 0.10.3
  assert_failure 1
  [ -z "$(git -C "$W/remote.git" tag -l v0.10.2)" ]
  run bash -c "cd '$W/work' && printf '0.10.2\n' | '$DELIVER' release"
  assert_success
  assert_output --partial "released 0.10.2"
}

@test "release_failure_before_the_tag_spends_nothing; a rerun reuses the copies (S26, R22)" {
  ref_commit "a feature" 12
  release_ready "12|Requirement||0|"
  STUB_FAIL_RECORD_PUSH=1 run d release --expect 0.10.2
  assert_failure 1
  assert_output --partial "pushing the record failed"
  [ -z "$(git -C "$W/remote.git" tag -l v0.10.2)" ]
  [ -n "$(rel 0.10.2-server)" ]                    # the copy was made
  [ -z "$(rel 0.10.2-record)" ]
  local copies; copies="$(grep -c . "$W/logs/copies.log")"
  run d release --expect 0.10.2
  assert_success
  assert_equal "$(grep -c . "$W/logs/copies.log")" "$copies"      # already there: a no-op
  [ -n "$(git -C "$W/remote.git" tag -l v0.10.2)" ]
}

@test "release_rerun_resumes_after_the_tag_without_repeating (S26, R22)" {
  ref_commit "a feature" 12
  release_ready "12|Requirement||0|"
  STUB_GH_FAIL=release run d release --expect 0.10.2
  assert_failure 3
  assert_output --partial "these steps failed: GitHub Release"
  local tag_sha; tag_sha="$(git -C "$W/remote.git" rev-parse v0.10.2)"
  assert_equal "$(remote_version)" 0.10.3             # the later steps still ran
  run d release --expect 0.10.2
  assert_success
  assert_equal "$(git -C "$W/remote.git" rev-parse v0.10.2)" "$tag_sha"
  assert_equal "$(grep -c '^RELEASE create' "$W/gh/log")" 1
  # everything done: it says so, exit 0, and changes nothing
  local before_gh before_reg; before_gh="$(gh_log | sha256sum)"; before_reg="$(snapshot)"
  run d release --expect 0.10.2
  assert_success
  assert_output --partial "already done"
  assert_equal "$(gh_log | sha256sum)" "$before_gh"
  assert_equal "$(snapshot)" "$before_reg"
}

@test "a tag holding a different record refuses the rerun (S26, R22, R23)" {
  ref_commit "a feature" 12
  release_ready "12|Requirement||0|"
  local other; other="$(git -C "$W/work" rev-parse HEAD~1)"
  printf '{"record":1,"application":"acme","version":"0.10.2","commit":"%s","images":{"server":"sha256:aaa","web":"sha256:bbb"}}\n' "$other" > "$W/rec.json"
  git -C "$W/work" tag -a -F "$W/rec.json" v0.10.2 "$other" && git -C "$W/work" push -q origin refs/tags/v0.10.2
  run d release --expect 0.10.2
  assert_failure 1
  assert_output --partial "holds a different record"
  assert_equal "$(grep -c '^RELEASE create' "$W/gh/log")" 0
}

@test "release_record_in_registry_equals_the_tag_message (S26, R22, R23)" {
  ref_commit "a feature" 12
  release_ready "12|Requirement||0|"
  run d release --expect 0.10.2
  assert_success
  assert_equal "$(registry_record 0.10.2 | jq -S .)" "$(tag_record v0.10.2 | jq -S .)"
}

@test "unknown_record_version_is_refused; pre_tool_tags_are_read_as_history_only (S28, R23)" {
  commit_change one; build_ok "$SHA"
  # a record version 2
  git -C "$W/work" tag -a -m '{"record":2,"version":"0.10.5","commit":"x","images":{}}' v0.10.5 HEAD && git -C "$W/work" push -q origin refs/tags/v0.10.5
  run d deploy rehearsal 0.10.5 --off-level first
  assert_failure 1
  assert_output --partial "record version this tool does not know"
  # tags made before the tool: v0.10.1 (text) and prod-0.9.0
  text_tag v0.10.1 HEAD; text_tag prod-0.9.0 HEAD
  run d deploy production 0.10.1
  assert_failure 1
  assert_output --partial "refused at gate production-record"
  run d deploy production 0.9.0
  assert_failure 1
  assert_output --partial "refused at gate production-record"
  run d settle 0.10.1
  assert_failure
  assert_output --partial "no record this tool reads"
  run d list rehearsal
  assert_success
  assert_output --partial "0.10.1  (history: no record)"
  assert_output --partial "0.9.0  (history: no record)"
}
