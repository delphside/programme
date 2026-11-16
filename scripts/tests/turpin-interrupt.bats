#!/usr/bin/env bats

# A person's Ctrl+C, a misspelt flag and a dropped connection, through the Python `turpin`
# end to end (test-design.md S90 and S93; rules R31, R50, R58, R59). The controller is run in
# a process group of its own and given SIGINT as a terminal gives it; the stubs hold a step
# (a hook, a registry, `gh`, a delete) where the test needs the call to be, and `ssh` loses
# the connection as the case says. The host's side of each is in turpin-protocol.bats.

setup() {
  bats_load_library bats-support
  bats_load_library bats-assert
  load turpin_world
  world_new
}

teardown() {
  local f
  for f in "$W"/*.pid; do [[ -f "$f" ]] && kill -KILL -- "-$(cat "$f")" 2>/dev/null; done
  return 0
}

# turpin in a process group of its own, as a terminal runs it: its output goes to $W/TAG.out
tstart() {   # TAG ARGS...
  local t="$1"; shift
  ( cd "$W/work" && exec setsid "$TURPIN" "$@" > "$W/$t.out" 2>&1 ) &
  echo $! > "$W/$t.pid"
}
tint() { kill -INT -- "-$(cat "$W/$1.pid")"; }                              # the Ctrl+C
tend() { TC=0; wait "$(cat "$W/$1.pid")" || TC=$?; TOUT="$(cat "$W/$1.out")"; }   # TC and TOUT
wait_file() { local i; for i in $(seq 1 300); do [[ -e "$1" ]] && return 0; sleep 0.1; done; echo "never appeared: $1" >&2; return 1; }

# a release 0.10.2 made, with production already running another build (deploy 1, unrecorded)
released() {
  commit_change earlier; build_ok "$SHA"; EARLIER="$SHA"
  run d deploy production "$EARLIER" --unrecorded "a build from before the tool"
  [ "$status" -eq 0 ] || { echo "first production deploy failed: $output" >&2; return 1; }
  ref_commit "a feature" 12 555
  gh_issue 12 Requirement "" 0.10.2 0 ""
  gh_issue 555 Project "" 0.10.2 0 "Production Release"
  release_ready "12|Requirement||0|" "555|Project||0|Production Release"
  gh_project 555 Development
  run d release --expect 0.10.2 --set-aside release-check "none"
  [ "$status" -eq 0 ] || { echo "release failed: $output" >&2; return 1; }
  : > "$W/gh/log"
}
prod_smokes() { grep -c '^== smoke' "$HOOKLOG" || true; }

# ---------------------------------------------------------------- S90

@test "a_misspelt_flag_exits_64_naming_it_and_runs_nothing (S90)" {
  commit_change one; build_ok "$SHA"
  local before ssh_calls skopeo_calls
  before="$(snapshot)"; ssh_calls="$(wc -l < "$W/logs/ssh.log")"; skopeo_calls="$(wc -l < "$W/logs/skopeo.log")"
  : > "$HOOKLOG"
  run d deploy rehearsal "$SHA" --off-levle "test world"
  assert_failure 64
  assert_output --partial "--off-levle"
  assert_equal "$(snapshot)" "$before"
  assert_equal "$(wc -l < "$W/logs/ssh.log")" "$ssh_calls"
  assert_equal "$(wc -l < "$W/logs/skopeo.log")" "$skopeo_calls"
  assert_equal "$(cat "$HOOKLOG")" ""
}

@test "sigint_during_the_gates_changes_nothing_and_says_the_change_is_not_live (S90)" {
  released
  local before; before="$(snapshot)"
  export STUB_SKOPEO_HOLD="$W/skopeo.hold"; : > "$STUB_SKOPEO_HOLD"
  tstart a deploy production 0.10.2
  wait_file "$STUB_SKOPEO_HOLD.reached"
  tint a; sleep 1
  rm -f "$STUB_SKOPEO_HOLD"      # the call under way runs to its end, and then nothing more is started
  tend a
  assert_equal "$TC" 130
  [[ "$TOUT" == *"the change is not live"* ]]
  [[ "$TOUT" == *"turpin deploy production 0.10.2"* ]]
  assert_equal "$(snapshot)" "$before"
}

@test "sigint_before_the_pivot_restores_and_says_the_change_is_not_live (S90)" {
  released
  local before_current; before_current="$(host_current prod production)"
  hook_hold smoke
  tstart a deploy production 0.10.2
  wait_file "$HOOKCTL/smoke.reached"
  tint a; sleep 1
  hook_release smoke
  tend a
  assert_equal "$TC" 130
  [[ "$TOUT" == *"the change is not live"* ]]
  [[ "$TOUT" == *"turpin deploy production 0.10.2"* ]]
  # the host restored the previous deploy, and settle was never started
  assert_equal "$(host_current prod production)" "$before_current"
  assert_equal "$(host_state prod production)" restored
  assert_equal "$(running_digests_of prod acme-production)" "$(digests_of "$EARLIER")"
  assert_equal "$(gh_log | wc -c)" 0
}

@test "sigint_during_settle_finishes_the_action_and_says_the_change_is_live (S90)" {
  released
  export STUB_GH_HOLD="$W/gh.hold"; : > "$STUB_GH_HOLD"
  tstart a deploy production 0.10.2
  wait_file "$STUB_GH_HOLD.reached"
  tint a; sleep 1
  rm -f "$STUB_GH_HOLD"
  tend a
  assert_equal "$TC" 130
  [[ "$TOUT" == *"the deploy is live"* ]]
  [[ "$TOUT" == *"turpin settle 0.10.2"* ]]
  assert_equal "$(host_state prod production)" finished
  assert_equal "$(running_digests_of prod acme-production)" "$(digests_of "$RSHA")"
  # the one action under way was done, and no other was started
  assert_equal "$(gh_log | wc -l)" 1
  # the rerun the message names does the rest
  run d settle 0.10.2
  assert_success
  assert_regex "$(gh_log)" "PATCH repos/acme/acme/milestones/7 state=closed"
}

@test "sigint_while_the_host_waits_for_the_lock_changes_nothing (S90)" {
  commit_change one; build_ok "$SHA"; local sha="$SHA"
  lock_hold rehearsal rehearsal
  local before; before="$(snapshot)"
  tstart a deploy rehearsal "$sha" --wait --off-level "test world"
  local i; for i in $(seq 1 100); do ls "$(host_state_dir rehearsal rehearsal)"/request.* >/dev/null 2>&1 && break; sleep 0.1; done
  sleep 1                                    # the host is in its wait for the lock
  tint a
  tend a
  lock_release
  assert_equal "$TC" 130
  [[ "$TOUT" == *"the change is not live"* ]]
  [[ "$TOUT" == *"turpin deploy rehearsal $sha"* ]]
  assert_equal "$(snapshot)" "$before"
  assert_equal "$(host_current rehearsal rehearsal)" ""
}

@test "sigint_during_prune_finishes_the_delete_and_starts_no_other (S90)" {
  commit_change released-build; build_ok "$SHA"; local r="$SHA"
  commit_change old-build; build_ok "$SHA"; local old="$SHA"
  # a release of r, made on 2026-06-01; r and old were built before it
  jq -nc --arg c "$r" --arg s "$(cand "$r-server")" --arg w "$(cand "$r-web")" \
    '{record:1,application:"acme",version:"0.9.0",commit:$c,images:{server:$s,web:$w},made:"2026-06-01T00:00:00Z"}' > "$W/rec.json"
  git -C "$W/work" tag -a -F "$W/rec.json" v0.9.0 "$r" && git -C "$W/work" push -q origin refs/tags/v0.9.0
  local c="$W/registry/reg.test/ns/acme/candidates" sha img d
  for sha in "$r" "$old"; do
    for img in server web; do
      d="$(cat "$c/tags/$sha-$img")"
      jq -c '.Labels["org.opencontainers.image.created"] = "2026-05-01T00:00:00Z"' "$c/meta/${d#sha256:}.json" > "$c/meta/new.json"
      mv "$c/meta/new.json" "$c/meta/${d#sha256:}.json"
    done
  done
  export STUB_OCI_DELETE_HOLD="$W/delete.hold"; : > "$STUB_OCI_DELETE_HOLD"
  tstart a prune
  wait_file "$STUB_OCI_DELETE_HOLD.reached"
  tint a; sleep 1
  rm -f "$STUB_OCI_DELETE_HOLD"
  tend a
  assert_equal "$TC" 130
  [[ "$TOUT" == *"turpin prune"* ]]
  # the first image is removed and the second was never started
  assert_equal "$(grep -c '^oci delete ' "$W/logs/auth.log")" 1
  [ -z "$(cand "$old-server")" ]
  [ -n "$(cand "$old-web")" ]
  [ -n "$(cand "$r-server")" ] && [ -n "$(cand "$r-web")" ]
}

@test "sigint_during_a_rollback_lets_it_run_to_its_end (S90)" {
  first_deploy; second_deploy
  hook_hold restore-state
  tstart a rollback rehearsal
  wait_file "$HOOKCTL/restore-state.reached"
  tint a; sleep 1
  hook_release restore-state
  tend a
  assert_equal "$TC" 0
  [[ "$TOUT" == *"after the rollback began"* ]]
  assert_equal "$(host_state rehearsal rehearsal)" restored
  assert_equal "$(host_current rehearsal rehearsal)" 1
  [ -z "$(host_previous rehearsal rehearsal)" ]
}

# ---------------------------------------------------------------- S93

first_deploy() { commit_change first; build_ok "$SHA"; SHA1="$SHA"; deploy_rehearsal "$SHA1"; assert_success; }
second_deploy() { commit_change second; build_ok "$SHA"; SHA2="$SHA"; run d deploy rehearsal "$SHA2"; assert_success; }
ssh_calls() { grep -c "$1" "$W/logs/ssh.log" || true; }
# the requests the host was sent (STUB_SSH_REQUESTS), as "request_id repeat" lines
requests() { jq -r '"\(.request_id) \(.repeat)"' "$W/requests.log"; }
# the same request id twice, the first sent as new and the second as a repeat of it
assert_one_request_sent_twice() {
  [ "$(requests | wc -l)" -eq 2 ]
  assert_equal "$(requests | cut -d' ' -f1 | sort -u | wc -l)" 1
  assert_equal "$(requests | cut -d' ' -f2 | tr '\n' ' ')" "false true "
}

@test "a_repeat_after_the_pivot_is_answered_from_the_record (S93)" {
  released
  : > "$HOOKLOG"; : > "$W/logs/ssh.log"
  STUB_SSH_REQUESTS="$W/requests.log" STUB_SSH_DROP_AFTER="turpin-host deploy" run d deploy production 0.10.2
  assert_success
  assert_one_request_sent_twice
  assert_equal "$(ssh_calls 'turpin-host deploy acme production')" 2      # the retry was made
  assert_equal "$(prod_smokes)" 1                                          # the deploy ran once
  assert_equal "$(host_current prod production)" 2
  assert_equal "$(running_digests_of prod acme-production)" "$(digests_of "$RSHA")"
  # and turpin went on to settle
  assert_regex "$(gh_log)" "PATCH repos/acme/acme/milestones/7 state=closed"
}

@test "a_repeat_of_a_rollback_waits_for_the_lock_then_is_answered (S93)" {
  first_deploy; second_deploy
  : > "$HOOKLOG"; : > "$W/logs/ssh.log"
  hook_hold restore-state
  # the connection is lost once the rollback holds the lock and is in its restore, which a
  # moment later is let go; the retry meanwhile waits for the lock
  export STUB_SSH_DROP_AT="turpin-host rollback" STUB_SSH_DROP_REACHED="$HOOKCTL/restore-state.reached" STUB_SSH_REQUESTS="$W/requests.log"
  ( wait_file "$HOOKCTL/restore-state.reached" && sleep 4 && hook_release restore-state ) &
  run d rollback rehearsal
  assert_success
  assert_one_request_sent_twice
  assert_equal "$(ssh_calls 'turpin-host rollback acme rehearsal')" 2
  assert_equal "$(grep -c '^== restore-state' "$HOOKLOG")" 1               # the rollback ran once
  assert_equal "$(host_current rehearsal rehearsal)" 1
  assert_equal "$(host_state rehearsal rehearsal)" restored
}

@test "a_repeat_of_a_refused_rollback_gets_the_recorded_refusal (S93)" {
  first_deploy
  : > "$W/logs/ssh.log"
  STUB_SSH_REQUESTS="$W/requests.log" STUB_SSH_DROP_AFTER="turpin-host rollback" run d rollback rehearsal
  assert_failure 1
  assert_one_request_sent_twice
  assert_equal "$(ssh_calls 'turpin-host rollback acme rehearsal')" 2
  assert_output --partial "no previous deploy"
  assert_output --partial "stop the turpin project, restore the snapshot, run the old script"
  # only a replay says it: the live lock gate, then the recorded gates (lock, rollback-target) read back
  # from the record. A host that ran the request again would give each gate once.
  gates=$(jq -r 'select(.event == "gate") | .name' "$(run_log_latest rollback)")
  assert_equal "$(grep -cx lock <<<"$gates")" 2
  assert_equal "$(grep -cx rollback-target <<<"$gates")" 1
  assert_equal "$(host_field rehearsal rehearsal state)" finished
  assert_equal "$(jq -r .last_request.outcome "$(host_state_dir rehearsal rehearsal)/state.json")" refused
}

@test "a_new_request_id_for_the_current_build_runs_as_new (S93)" {
  first_deploy
  : > "$HOOKLOG"; : > "$W/logs/ssh.log"
  STUB_SSH_REQUESTS="$W/requests.log" STUB_SSH_DROP_BEFORE="turpin-host deploy" run d deploy rehearsal "$SHA1"
  assert_success
  assert_one_request_sent_twice                   # the lost call, which never reached the host, and its repeat
  assert_equal "$(ssh_calls 'turpin-host deploy acme rehearsal')" 2        # the lost call, and the retry
  assert_equal "$(grep -c '^== smoke' "$HOOKLOG")" 1                       # the second deploy ran once
  assert_equal "$(host_current rehearsal rehearsal)" 2
}
