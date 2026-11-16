#!/usr/bin/env bats

# The host protocol of `turpin-host deploy` and `rollback` (delphside/programme#117, task T4):
# the request and its id, the last request and what a repeat is answered with, the input held
# open and the interruption it carries, the reasons a stop has, and `status` and `rollback`
# through the Python `turpin` (test-design.md S90 to S94, S105 to S110, S113, R57 to R61).
#
# The host is called directly with a request the controller made, its input held open as the
# controller holds it; a test that interrupts holds the input in a fifo and closes it.

setup() {
  bats_load_library bats-support
  bats_load_library bats-assert
  load turpin_world
  world_new
  ID1=11111111-1111-4111-8111-111111111111
  ID2=22222222-2222-4222-8222-222222222222
  ID3=33333333-3333-4333-a333-333333333333
}

teardown() {
  # nothing a test started is left holding a lock or a fifo
  local f
  for f in "$W"/*.holder; do [[ -f "$f" ]] && kill "$(cat "$f")" 2>/dev/null; done
  return 0
}

first_deploy() {
  commit_change first; build_ok "$SHA"; SHA1="$SHA"
  deploy_rehearsal "$SHA1"; assert_success
}
second_deploy() {
  commit_change second; build_ok "$SHA"; SHA2="$SHA"
  run d deploy rehearsal "$SHA2"; assert_success
}

# the host's record, and the bits of it these tests read
ed() { host_state_dir rehearsal rehearsal; }
last_request() { jq -c '.last_request' "$(ed)/state.json"; }
lr() { jq -r ".last_request.$1" "$(ed)/state.json"; }
# the result the host sent last: the `@result` line of an output
result_of() { grep '^@result ' <<< "${1:-$output}" | tail -1 | sed 's/^@result //'; }
reason_of() { result_of "$@" | jq -r .reason; }

# a deploy request for REF as the controller makes it, with the id and `repeat` given
mkreq() {   # REF ID [REPEAT]  ->  $W/request.json
  # the request is made by a `--check` run of the controller's own call once per ref, while the
  # host is in a state that passes; later requests for the ref (or for a ref made when the host
  # would refuse the check) are the cached one with the ref and the id replaced
  local cache="$W/request.check.$1.json"
  if [[ ! -e "$cache" ]]; then
    if STUB_SSH_TEE="$cache.new" run d deploy rehearsal "$1" --check --off-level "test world" && [ "$status" -eq 0 ]; then
      mv "$cache.new" "$cache"
    else
      local last; last="$(ls -t "$W"/request.check.*.json 2>/dev/null | head -1)"
      [ -n "$last" ] || { echo "no request to copy: $output" >&2; return 1; }
      local old="${last#"$W"/request.check.}"; old="${old%.json}"
      sed "s/$old/$1/g" "$last" > "$cache"
    fi
  fi
  jq -c --arg id "$2" --argjson r "${3:-false}" '.check = false | .request_id = $id | .repeat = $r | .lock_wait = (.lock_wait // (if $r then 60 else null end))' "$cache" > "$W/request.json"
}
# a rollback request
mkrb() {   # ID [REPEAT] [WAIT]  ->  $W/rollback.json
  jq -nc --arg id "$1" --argjson r "${2:-false}" --arg w "${3:-}" \
    '{request_id:$id,repeat:$r,app:"acme",env:"rehearsal",role:"rehearsal",login:"docker-config",repo:"acme/candidates",
      lock:null,project:null,pull_timeout:60,wait:($w|if .=="" then null else tonumber end),
      lock_wait:(if $w != "" then ($w|tonumber) elif $r then 60 else null end),fallback:"stop it; restore the snapshot"}' > "$W/rollback.json"
}
# the host command, run to its end with the request held open
host_call() {   # KIND [REQUEST_FILE]
  local req="${2:-$W/request.json}"; [[ "$1" == rollback && -z "${2:-}" ]] && req="$W/rollback.json"
  run bash -c "env TURPIN_HOST_ROOT='$W/hosts/rehearsal' '$TURPIN_HOST' $1 acme rehearsal < <(held-request '$req')"
}
# the host command in the background, its input a fifo this test closes when it chooses
hs_start() {   # TAG KIND REQUEST_FILE
  mkfifo "${W:?}/$1.in"; rm -f "${W:?}/$1.status"
  ( rc=0
    env TURPIN_HOST_ROOT="$W/hosts/rehearsal" "$TURPIN_HOST" "$2" acme rehearsal < "$W/$1.in" > "$W/$1.out" 2>&1 &
    echo $! > "$W/$1.pid"; wait $! || rc=$?; echo $rc > "$W/$1.status" ) &
  ( cat "$3"; exec sleep 600 ) > "$W/$1.in" &
  echo $! > "$W/$1.holder"
}
hs_close() { kill "$(cat "$W/$1.holder")" 2>/dev/null || true; }
hs_wait() {   # TAG: the exit status, once it has one
  local i; for i in $(seq 1 300); do [[ -f "$W/$1.status" ]] && { HS="$(cat "$W/$1.status")"; HS_OUT="$(cat "$W/$1.out")"; return 0; }; sleep 0.1; done
  echo "$1 did not end: $(cat "$W/$1.out")" >&2; return 1
}
wait_file() { local i; for i in $(seq 1 300); do [[ -e "$1" ]] && return 0; sleep 0.1; done; echo "never appeared: $1" >&2; return 1; }
leftovers() { ls -A "$(ed)" | grep -E '^(interrupted|request|payload|note)\.' || true; }

# ---------------------------------------------------------------- the request

@test "a_request_id_that_is_not_a_version_4_uuid_is_an_unexpected_error (S109)" {
  first_deploy
  commit_change next; build_ok "$SHA"
  local before; before="$(snapshot)"
  local bad
  for bad in not-a-uuid 11111111-1111-1111-8111-111111111111 11111111-1111-4111-c111-111111111111; do
    mkreq "$SHA" "$bad"
    host_call deploy
    assert_failure 70
    assert_output --partial "not a version 4 UUID"
    assert_output --partial "raise it as an issue"
    assert_equal "$(reason_of)" HOST_REQUEST_ID_INVALID
    assert_equal "$(snapshot)" "$before"
  done
  mkreq "$SHA" "$ID1"
  host_call deploy
  assert_success
}

@test "a_malformed_request_id_never_takes_the_lock (S109)" {
  commit_change first; build_ok "$SHA"; mkreq "$SHA" not-a-uuid
  host_call deploy
  assert_failure 70
  run bash -c "exec 9>>'$(ed)/lock'; flock -n 9"   # the lock is free: it was never taken
  assert_success
}

@test "a_request_without_repeat_or_not_one_json_object_is_an_unexpected_error (S109)" {
  first_deploy
  printf 'not json\n' > "$W/request.json"
  host_call deploy; assert_failure 70
  assert_equal "$(reason_of)" HOST_REQUEST_UNREADABLE
  commit_change next; build_ok "$SHA"; mkreq "$SHA" "$ID1"
  jq -c 'del(.repeat)' "$W/request.json" > "$W/request.2"
  host_call deploy "$W/request.2"; assert_failure 70
}

@test "a_deploy_records_its_request_as_running_then_as_finished_in_the_pivot_write (R58)" {
  first_deploy
  commit_change next; build_ok "$SHA"; mkreq "$SHA" "$ID1"
  hook_hold migrate
  hs_start d deploy "$W/request.json"
  wait_file "$HOOKCTL/migrate.reached"
  assert_equal "$(lr outcome)" running
  assert_equal "$(lr request_id)" "$ID1"
  hook_release migrate
  hs_wait d; assert_equal "$HS" 0
  assert_equal "$(lr outcome)" finished
  assert_equal "$(lr exit)" 0
  assert_equal "$(host_current rehearsal rehearsal)" 2
}

# ---------------------------------------------------------------- the repeat table (§11)

@test "host_a_repeat_after_the_pivot_is_answered_from_the_record (S93)" {
  first_deploy
  commit_change next; build_ok "$SHA"; mkreq "$SHA" "$ID1"
  host_call deploy; assert_success
  assert_output --partial "deployed acme to rehearsal: deploy #2"
  : > "$HOOKLOG"; : > "$W/logs/docker.log"
  local before; before="$(snapshot)"
  mkreq "$SHA" "$ID1" true
  host_call deploy
  assert_success
  assert_output --partial "deployed acme to rehearsal: deploy #2"       # the recorded result
  assert_output --partial "@gate state passed"                           # and the gates it ran
  assert_equal "$(hook_calls)" ""                                        # nothing ran again
  run grep -c -E 'pull|compose' "$W/logs/docker.log"; assert_output 0
  assert_equal "$(host_current rehearsal rehearsal)" 2
  assert_equal "$(snapshot)" "$before"
}

@test "a_repeat_of_a_finished_request_whose_prune_failed_is_answered_with_exit_3 (S105)" {
  first_deploy; second_deploy
  commit_change third; build_ok "$SHA"; mkreq "$SHA" "$ID1"
  STUB_RMI_FAIL=1 host_call deploy
  assert_failure 3
  assert_equal "$(reason_of)" HOST_PRUNE_FAILED
  assert_equal "$(result_of | jq -r .outcome)" error
  assert_equal "$(lr outcome):$(lr exit)" finished:3
  : > "$W/logs/docker.log"
  mkreq "$SHA" "$ID1" true
  host_call deploy
  assert_failure 3
  assert_output --partial "pruning the host's images failed"
  run grep -c -E 'rmi|image ls' "$W/logs/docker.log"; assert_output 0     # no second prune
}

@test "a_repeat_of_a_refused_deploy_gets_the_recorded_refusal (S94)" {
  first_deploy
  commit_change next; build_ok "$SHA"; mkreq "$SHA" "$ID1"
  hook_exit smoke 1
  host_call deploy
  assert_failure 1
  assert_output --partial "refused at gate smoke"
  assert_equal "$(lr outcome)" refused
  assert_equal "$(host_state rehearsal rehearsal)" restored
  : > "$HOOKLOG"; mkreq "$SHA" "$ID1" true
  hook_clear smoke
  host_call deploy
  assert_failure 1
  assert_output --partial "refused at gate smoke"
  assert_equal "$(reason_of)" HOOK_REFUSED
  assert_equal "$(hook_calls)" ""                                         # restore-state not called again
}

@test "a_repeat_of_a_failed_deploy_or_rollback_gets_the_recorded_result (S106)" {
  first_deploy; second_deploy
  commit_change third; build_ok "$SHA"; mkreq "$SHA" "$ID1"
  hook_exit migrate 1
  host_call deploy
  assert_failure 1
  assert_equal "$(lr outcome)" failed                                      # an error, not a gate
  assert_equal "$(reason_of)" HOST_STEP_FAILED
  hook_clear migrate; : > "$HOOKLOG"
  mkreq "$SHA" "$ID1" true; host_call deploy
  assert_failure 1
  assert_equal "$(reason_of)" HOST_STEP_FAILED
  assert_equal "$(hook_calls)" ""
  # case 2: a rollback whose restore-state fails at its second step, S101's
  mkrb "$ID2"; hook_exit restore-state 1
  host_call rollback
  assert_failure 1
  assert_equal "$(lr outcome)" failed
  assert_equal "$(host_state rehearsal rehearsal)" "changing: rollback 2"
  hook_clear restore-state; : > "$HOOKLOG"
  mkrb "$ID2" true; host_call rollback
  assert_failure 1
  assert_equal "$(hook_calls)" ""
  # a new rollback request runs it again
  mkrb "$ID3"; host_call rollback; assert_success
  assert_equal "$(host_state rehearsal rehearsal)" restored
}

@test "a_repeat_of_a_rollback_left_running_is_refused_naming_status (S107)" {
  first_deploy; second_deploy
  host_record_set rehearsal rehearsal '.last_request = {request_id: "'"$ID2"'", outcome: "running"}'
  mkrb "$ID2" true; host_call rollback
  assert_failure 1
  assert_output --partial "turpin status"
  assert_equal "$(reason_of)" HOST_REQUEST_RUNNING
  assert_equal "$(last_request)" '{"request_id":"'"$ID2"'","outcome":"running"}'
  assert_equal "$(host_current rehearsal rehearsal)" 2
}

@test "a_repeat_of_a_request_left_running_is_refused_naming_status (S94)" {
  first_deploy
  commit_change next; build_ok "$SHA"; mkreq "$SHA" "$ID1"
  hook_exit migrate kill
  host_call deploy
  assert_failure 70
  assert_equal "$(lr outcome)" running                  # died with its step: left as a reboot would leave it
  hook_clear migrate
  mkreq "$SHA" "$ID1" true; host_call deploy
  assert_failure 1
  assert_output --partial "turpin status"
  assert_equal "$(lr outcome)" running
}

@test "a_new_deploy_after_a_kill_in_preparing_runs (S94)" {
  first_deploy
  commit_change next; build_ok "$SHA"; mkreq "$SHA" "$ID1"
  hook_exit pre-deploy kill
  host_call deploy; assert_failure 70
  hook_clear pre-deploy
  assert_equal "$(lr outcome)" running
  mkreq "$SHA" "$ID2"; host_call deploy
  assert_success
  assert_equal "$(lr request_id):$(lr outcome)" "$ID2:finished"
}

@test "host_a_new_request_id_for_the_current_build_runs_as_new (S93)" {
  first_deploy
  commit_change next; build_ok "$SHA"; mkreq "$SHA" "$ID1"
  host_call deploy; assert_success
  mkreq "$SHA" "$ID2"; host_call deploy
  assert_success
  assert_equal "$(host_current rehearsal rehearsal)" 3
  assert_equal "$(lr request_id)" "$ID2"
}

@test "a_repeat_of_an_interrupted_first_deploy_runs_again (S94, S108)" {
  commit_change first; build_ok "$SHA"; mkreq "$SHA" "$ID1"
  hook_exit pre-deploy 75
  host_call deploy
  assert_failure 75
  assert_equal "$(lr outcome)" interrupted
  assert_equal "$(host_state rehearsal rehearsal)" ""                      # `none` again
  hook_clear pre-deploy
  mkreq "$SHA" "$ID1" true; host_call deploy
  assert_success
  assert_equal "$(host_state rehearsal rehearsal)" finished
  assert_equal "$(lr outcome)" finished
}

@test "a_hook_not_yet_past_the_wait_is_recorded_interrupted_and_its_repeat_runs (S108)" {
  first_deploy
  commit_change next; build_ok "$SHA"; mkreq "$SHA" "$ID1"
  hook_exit pre-deploy 75
  local before; before="$(snapshot)"
  host_call deploy                                   # no wait: at once, exit 75
  assert_failure 75
  assert_output --partial "use --wait"
  assert_equal "$(reason_of)" HOOK_NOT_YET
  assert_equal "$(lr outcome)" interrupted
  assert_equal "$(snapshot)" "$before"
  mkreq "$SHA" "$ID1" true; host_call deploy         # a repeat does not wait for the hook either
  assert_failure 75
  assert_equal "$(lr outcome)" interrupted
  hook_clear pre-deploy
  mkreq "$SHA" "$ID1" true; host_call deploy
  assert_success
  assert_equal "$(host_current rehearsal rehearsal)" 2
}

@test "a_repeat_does_not_wait_for_a_hooks_not_yet_without_wait (S108)" {
  first_deploy
  commit_change next; build_ok "$SHA"; mkreq "$SHA" "$ID1" true
  hook_exit pre-deploy "75 1"
  local start="$SECONDS"
  host_call deploy
  assert_failure 75
  [ $((SECONDS - start)) -lt 5 ]
}

@test "a_repeat_waiting_for_the_lock_past_the_limit_exits_75 (S108)" {
  first_deploy
  commit_change next; build_ok "$SHA"; mkreq "$SHA" "$ID1" true
  jq -c '.wait = 1 | .lock_wait = 1' "$W/request.json" > "$W/request.w.json"
  lock_hold rehearsal rehearsal
  local before; before="$(snapshot)"
  host_call deploy "$W/request.w.json"
  assert_failure 75
  assert_output --partial "still held after waiting 1 minute(s)"
  assert_equal "$(reason_of)" HOST_LOCK_WAIT_LIMIT
  assert_equal "$(snapshot)" "$before"
  lock_release
}

@test "host_a_repeat_of_a_rollback_waits_for_the_lock_then_is_answered (S93)" {
  first_deploy; second_deploy
  mkrb "$ID1"; host_call rollback; assert_success
  : > "$HOOKLOG"
  lock_hold rehearsal rehearsal
  ( sleep 2; kill "$LOCK_PID" ) &
  mkrb "$ID1" true; host_call rollback                 # no wait set: the repeat waits all the same
  assert_success
  assert_output --partial "rolled back to deploy #1"
  assert_equal "$(hook_calls)" ""
}

@test "host_a_repeat_of_a_refused_rollback_gets_the_recorded_refusal (S93)" {
  first_deploy
  mkrb "$ID1"; host_call rollback
  assert_failure 1
  assert_output --partial "no previous deploy"
  assert_equal "$(reason_of)" ROLLBACK_NO_PREVIOUS
  assert_equal "$(lr outcome)" refused
  mkrb "$ID1" true; host_call rollback
  assert_failure 1
  assert_output --partial "no previous deploy"
}

@test "a_request_refused_for_the_lock_writes_nothing_to_last_request (S94)" {
  first_deploy
  commit_change next; build_ok "$SHA"; mkreq "$SHA" "$ID1"
  local was; was="$(last_request)"
  lock_hold rehearsal rehearsal
  host_call deploy
  assert_failure 1
  assert_output --partial "refused at gate lock"
  assert_equal "$(reason_of)" HOST_LOCK_HELD
  assert_equal "$(last_request)" "$was"
  lock_release
  mkrb "$ID2"; lock_hold rehearsal rehearsal
  host_call rollback; assert_failure 1
  assert_equal "$(last_request)" "$was"
  lock_release
}

@test "check_mode_leaves_last_request_alone (S94)" {
  first_deploy
  local was; was="$(last_request)"
  commit_change next; build_ok "$SHA"
  run d deploy rehearsal "$SHA" --check --off-level "test world"
  assert_success
  assert_equal "$(last_request)" "$was"
  # a check carrying the id of the last request is not answered from the record
  STUB_SSH_TEE="$W/request.check.json" run d deploy rehearsal "$SHA" --check --off-level "test world"
  jq -c --arg id "$(lr request_id)" '.request_id = $id | .repeat = true' "$W/request.check.json" > "$W/request.json"
  host_call deploy
  assert_success
  assert_output --partial "nothing changed"
}

@test "a_rollback_on_a_bare_host_has_nothing_to_record_and_names_the_fallback_the_request_carries (S98)" {
  local before; before="$(snapshot)"
  mkrb "$ID1"; host_call rollback
  assert_failure 1
  assert_output --partial "stop it; restore the snapshot"
  assert_equal "$(reason_of)" ROLLBACK_NOTHING_DEPLOYED
  [ ! -e "$(ed)/state.json" ]
  assert_equal "$(snapshot)" "$before"
}

@test "a_rollback_that_runs_a_restore_and_fails_marks_the_restore_incomplete (S116)" {
  first_deploy; second_deploy
  commit_change third; build_ok "$SHA"; local sha3="$SHA"
  mkreq "$sha3" "$ID2"; cp "$W/request.json" "$W/request.d.json"
  hook_exit migrate kill
  run d deploy rehearsal "$sha3"; assert_failure
  hook_clear migrate
  hook_exit restore-state 1
  mkrb "$ID1"; host_call rollback
  assert_failure 1
  assert_equal "$(host_state rehearsal rehearsal)" "failed: the restore did not complete"
  assert_equal "$(lr outcome)" failed
  assert_equal "$(reason_of)" HOST_RESTORE_FAILED
  hook_clear restore-state; : > "$HOOKLOG"
  mkrb "$ID1" true; host_call rollback                     # the repeat: the recorded result
  assert_failure 1
  assert_equal "$(hook_calls)" ""
  host_call deploy "$W/request.d.json"                    # a deploy meanwhile is refused
  assert_failure 1
  assert_equal "$(reason_of)" HOST_STATE_REFUSED
  assert_output --partial "turpin rollback"
  mkrb "$ID3"; host_call rollback; assert_success
  assert_equal "$(host_state rehearsal rehearsal)" restored
}

# ---------------------------------------------------------------- the reasons a stop has

@test "each_refusal_has_a_reason_in_the_result_the_host_sends_last (R61, section 6)" {
  first_deploy
  commit_change next; build_ok "$SHA"; local sha="$SHA"; mkreq "$sha" "$ID1"
  # a hook refuses
  hook_exit pre-deploy 1
  host_call deploy; assert_failure 1
  assert_equal "$(reason_of)" HOOK_REFUSED
  assert_equal "$(result_of | jq -r '.type + " " + .domain')" "business turpin"
  hook_clear pre-deploy
  # a label that is another commit's
  mkreq "$sha" "$ID2"; jq -c --arg sha "$SHA1" '.sha = $sha' "$W/request.json" > "$W/request.x.json"
  host_call deploy "$W/request.x.json"; assert_failure 1
  assert_equal "$(reason_of)" HOST_DIGEST_REFUSED
  # a state that refuses a deploy
  host_record_set rehearsal rehearsal '.state = "changing: deploy migrate" | .pending = 2 | .target = 2'
  mkreq "$SHA1" "$ID3"; host_call deploy; assert_failure 1
  assert_equal "$(reason_of)" HOST_STATE_REFUSED
}

@test "a_rollbacks_refusals_have_their_reasons (S98 to S103)" {
  mkrb "$ID1"; host_call rollback; assert_equal "$(reason_of)" ROLLBACK_NOTHING_DEPLOYED
  first_deploy
  mkrb "$ID2"; host_call rollback; assert_equal "$(reason_of)" ROLLBACK_NO_PREVIOUS
  host_record_set rehearsal rehearsal '.state = "failed, no previous deploy" | del(.current)'
  mkrb "$ID3"; host_call rollback; assert_equal "$(reason_of)" ROLLBACK_FIRST_DEPLOY_FAILED
}

@test "the_hosts_other_stops_have_their_types_and_exits (R50, R61)" {
  first_deploy
  commit_change next; build_ok "$SHA"; mkreq "$SHA" "$ID1"
  # a lock waited for and not freed is a blip, exit 75
  jq -c '.wait = 1 | .lock_wait = 1' "$W/request.json" > "$W/request.w.json"
  lock_hold rehearsal rehearsal
  host_call deploy "$W/request.w.json"
  assert_failure 75
  assert_equal "$(result_of | jq -r '.type + " " + (.blip|tostring)')" "technical true"
  lock_release
  # a layout the Bash turpin left is fundamental, exit 2
  mv "$(ed)/state.json" "$(ed)/state.keep"; printf 'finished\n' > "$(ed)/state"
  host_call deploy
  assert_failure 2
  assert_equal "$(reason_of)" STATE_LAYOUT_BASH
  assert_equal "$(result_of | jq -r '.type + " " + (.blip|tostring)')" "technical false"
}

# ---------------------------------------------------------------- the input and the interruption

@test "an_interruption_while_the_host_waits_for_the_lock_stops_at_the_next_wait (S110)" {
  first_deploy
  commit_change next; build_ok "$SHA"; mkreq "$SHA" "$ID1"
  jq -c '.wait = 5 | .lock_wait = 5' "$W/request.json" > "$W/request.w.json"
  lock_hold rehearsal rehearsal
  local before was; before="$(snapshot)"; was="$(last_request)"
  hs_start b deploy "$W/request.w.json"
  sleep 1.5
  hs_close b
  hs_wait b
  assert_equal "$HS" 130
  [[ "$HS_OUT" == *"interrupted while waiting for the lock"* ]]
  assert_equal "$(last_request)" "$was"
  assert_equal "$(snapshot)" "$before"
  assert_equal "$(leftovers)" ""
  # the holder still holds it
  run bash -c "exec 9>>'$(ed)/lock'; flock -n 9"
  assert_failure
  lock_release
}

@test "an_interrupted_request_waiting_for_the_lock_leaves_the_holder_to_finish (S110)" {
  first_deploy
  commit_change next; build_ok "$SHA"; mkreq "$SHA" "$ID1"
  cp "$W/request.json" "$W/request.a.json"
  jq -c --arg id "$ID2" '.request_id = $id | .wait = 5 | .lock_wait = 5' "$W/request.json" > "$W/request.b.json"
  hook_hold migrate
  hs_start a deploy "$W/request.a.json"
  wait_file "$HOOKCTL/migrate.reached"
  hs_start b deploy "$W/request.b.json"
  sleep 1.5
  hs_close b; hs_wait b
  assert_equal "$HS" 130
  hook_release migrate
  hs_wait a
  assert_equal "$HS" 0
  assert_equal "$(host_current rehearsal rehearsal)" 2
  assert_equal "$(lr request_id)" "$ID1"
  hs_close a
}

@test "an_interruption_between_hook_retries_stops_at_the_next_look (S110)" {
  first_deploy
  commit_change next; build_ok "$SHA"; mkreq "$SHA" "$ID1"
  jq -c '.wait = 30 | .lock_wait = 30' "$W/request.json" > "$W/request.w.json"
  hook_exit pre-deploy 75
  local before; before="$(snapshot)"
  : > "$HOOKLOG"
  hs_start a deploy "$W/request.w.json"
  sleep 2.5
  hs_close a; hs_wait a
  assert_equal "$HS" 130
  local calls; calls="$(grep -c '^== pre-deploy' "$HOOKLOG")"
  [ "$calls" -ge 1 ] && [ "$calls" -lt 8 ]
  sleep 1.5
  assert_equal "$(grep -c '^== pre-deploy' "$HOOKLOG")" "$calls"             # the hook was not run again
  assert_equal "$(lr outcome)" interrupted
  assert_equal "$(reason_of "$HS_OUT")" HOST_INTERRUPTED
  assert_equal "$(snapshot)" "$before"
  hs_close a
}

@test "a_hook_reading_its_input_gets_end_of_file_at_once (S110)" {
  first_deploy
  commit_change next
  printf '#!/usr/bin/env bash\ncat > "%s"\nexit 0\n' "$W/hook.stdin" > "$W/work/turpin/hooks/pre-deploy"
  commit_all "a hook that reads"; build_ok "$SHA"; mkreq "$SHA" "$ID1"
  host_call deploy
  assert_success
  [ -f "$W/hook.stdin" ]
  [ ! -s "$W/hook.stdin" ]                      # none of the request line, and it did not block
}

@test "an_interruption_before_the_deploy_folder_changes_nothing (S90)" {
  first_deploy
  commit_change next; build_ok "$SHA"; mkreq "$SHA" "$ID1"
  hook_hold pre-deploy
  local before; before="$(snapshot)"
  hs_start a deploy "$W/request.json"
  wait_file "$HOOKCTL/pre-deploy.reached"
  hs_close a; sleep 1
  hook_release pre-deploy
  hs_wait a
  assert_equal "$HS" 130
  assert_equal "$(host_state rehearsal rehearsal)" finished
  assert_equal "$(host_current rehearsal rehearsal)" 1
  assert_equal "$(lr outcome)" interrupted
  assert_equal "$(snapshot)" "$before"
  hs_close a
}

@test "an_interruption_after_save_state_restores_and_records_interrupted (S90, S91)" {
  first_deploy
  commit_change next; build_ok "$SHA"; mkreq "$SHA" "$ID1"
  hook_hold migrate
  : > "$HOOKLOG"
  hs_start a deploy "$W/request.json"
  wait_file "$HOOKCTL/migrate.reached"
  hs_close a; sleep 1
  hook_release migrate
  hs_wait a
  assert_equal "$HS" 130
  [[ "$HS_OUT" == *"the deploy is undone"* ]]
  assert_equal "$(host_state rehearsal rehearsal)" restored
  assert_equal "$(host_current rehearsal rehearsal)" 1
  assert_equal "$(running_digests_of rehearsal acme-rehearsal)" "$(digests_of "$SHA1")"
  run hook_calls; assert_output --partial "restore-state"
  assert_equal "$(lr outcome)" interrupted
  # the repeat runs it again, from the state a restore left
  mkreq "$SHA" "$ID1" true; hook_clear migrate; host_call deploy
  assert_success
  assert_equal "$(host_current rehearsal rehearsal)" 3
  hs_close a
}

@test "an_interruption_before_the_pivot_restores_the_previous_deploy (S90)" {
  first_deploy
  commit_change next; build_ok "$SHA"; mkreq "$SHA" "$ID1"
  hook_hold smoke
  hs_start a deploy "$W/request.json"
  wait_file "$HOOKCTL/smoke.reached"
  hs_close a; sleep 1
  hook_release smoke
  hs_wait a
  assert_equal "$HS" 130
  assert_equal "$(host_current rehearsal rehearsal)" 1
  assert_equal "$(host_state rehearsal rehearsal)" restored
  assert_equal "$(running_digests_of rehearsal acme-rehearsal)" "$(digests_of "$SHA1")"
  assert_equal "$(lr outcome)" interrupted
  hs_close a
}

@test "an_interruption_after_the_pivot_leaves_the_prune_for_the_next_deploy (S90)" {
  first_deploy; second_deploy
  commit_change third; build_ok "$SHA"; mkreq "$SHA" "$ID1"
  export STUB_LS_HOLD="$W/ls.hold"; : > "$STUB_LS_HOLD"
  hs_start a deploy "$W/request.json"
  wait_file "$STUB_LS_HOLD.reached"                     # the image prune has begun: the pivot is past
  hs_close a; sleep 1
  rm -f "${STUB_LS_HOLD:?}"
  hs_wait a
  assert_equal "$HS" 130
  [[ "$HS_OUT" == *"the change is live"* ]]
  assert_equal "$(host_current rehearsal rehearsal)" 3
  assert_equal "$(host_state rehearsal rehearsal)" finished
  assert_equal "$(lr outcome):$(lr exit)" finished:0
  [ -f "$(ed)/deploys/1/payload/deploy" ]               # deploy 1's folder was not cut down
  hs_close a
}

@test "a_rollback_waiting_for_the_lock_stops_and_one_holding_it_runs_to_its_end (S110)" {
  first_deploy; second_deploy
  # case 4: waiting for the lock
  mkrb "$ID1" false 5
  lock_hold rehearsal rehearsal
  hs_start r rollback "$W/rollback.json"
  sleep 1.5; hs_close r; hs_wait r
  assert_equal "$HS" 130
  assert_equal "$(host_current rehearsal rehearsal)" 2
  lock_release
  # case 5: holding it
  mkrb "$ID2"
  hook_hold restore-state
  hs_start r2 rollback "$W/rollback.json"
  wait_file "$HOOKCTL/restore-state.reached"
  hs_close r2; sleep 1
  hook_release restore-state
  hs_wait r2
  assert_equal "$HS" 0
  assert_equal "$(host_state rehearsal rehearsal)" restored
  assert_equal "$(host_current rehearsal rehearsal)" 1
  assert_equal "$(lr outcome)" finished
}

@test "an_interrupted_file_is_removed_on_exit_and_a_stale_one_is_never_read (S110)" {
  first_deploy
  local dead; sleep 0 & dead=$!; wait "$dead" 2>/dev/null
  touch "$(ed)/interrupted.$dead" "$(ed)/request.$dead"
  mkdir -p "$(ed)/payload.$dead"; touch "$(ed)/payload.$dead/deploy" "$(ed)/note.$dead"
  commit_change next; build_ok "$SHA"; mkreq "$SHA" "$ID1"
  host_call deploy
  assert_success
  assert_equal "$(leftovers)" ""
  # a request that ended leaves none of its own, whichever way it ended
  hook_exit pre-deploy 1
  mkreq "$SHA" "$ID2"; host_call deploy; assert_failure 1
  assert_equal "$(leftovers)" ""
}

@test "a_kill_leaves_temp_files_and_the_next_request_cleans_them_up (section 11)" {
  first_deploy
  commit_change next; build_ok "$SHA"; mkreq "$SHA" "$ID1"
  hook_hold migrate
  hs_start a deploy "$W/request.json"
  wait_file "$HOOKCTL/migrate.reached"
  wait_file "$W/a.pid"; pkill -9 -P "$(cat "$W/a.pid")"; kill -9 "$(cat "$W/a.pid")"; sleep 0.5
  [ -n "$(leftovers)" ]                                  # a killed request cannot clean up after itself
  hook_release migrate
  local i; for i in $(seq 1 150); do (exec 9>>"$(ed)/lock"; flock -n 9) && break; sleep 0.2; done; (exec 9>>"$(ed)/lock"; flock -n 9)   # the orphaned hook lets go of the lock
  hook_clear migrate
  host_record_set rehearsal rehearsal '.state = "restored" | del(.pending, .target)'
  mkreq "$SHA" "$ID2"; host_call deploy
  assert_success
  assert_equal "$(leftovers)" ""
  hs_close a
}

@test "a_dropped_write_is_taken_as_the_end_of_the_input (section 6)" {
  first_deploy
  commit_change next; build_ok "$SHA"; mkreq "$SHA" "$ID1"
  run bash -c "env TURPIN_HOST_ROOT='$W/hosts/rehearsal' '$TURPIN_HOST' deploy acme rehearsal < <(held-request '$W/request.json') 2> >(head -c0); sleep 0.5"
  # the host reached its next step, stopped as for an interruption, and recorded it
  local i; for i in $(seq 1 50); do [[ "$(lr outcome)" == interrupted ]] && break; sleep 0.2; done
  assert_equal "$(lr outcome)" interrupted
  assert_equal "$(host_current rehearsal rehearsal)" 1
  assert_equal "$(host_state rehearsal rehearsal)" finished
}

@test "the_hosts_data_calls_change_nothing_without_the_closing_line (section 6)" {
  first_deploy
  local before; before="$(snapshot)"
  run bash -c "printf 'user\ntoken\n' | env TURPIN_HOST_ROOT='$W/hosts/rehearsal' '$TURPIN_HOST' login acme deployer rehearsal"
  assert_failure 75
  assert_output --partial "closing line"
  run bash -c "printf '/opt/acme/x\tops/x\t0644\tfalse\n' | env TURPIN_HOST_ROOT='$W/hosts/rehearsal' '$TURPIN_HOST' allowlist acme"
  assert_failure 75
  assert_equal "$(snapshot)" "$before"
  run bash -c "printf 'user\ntoken\n# turpin: end\n' | env TURPIN_HOST_ROOT='$W/hosts/rehearsal' '$TURPIN_HOST' login acme deployer rehearsal"
  assert_success
  run bash -c "printf '/opt/acme/x\tops/x\t0644\tfalse\n# turpin: end\n' | env TURPIN_HOST_ROOT='$W/hosts/rehearsal' '$TURPIN_HOST' allowlist acme"
  assert_success
  run grep -c 'turpin: end' "$W/hosts/rehearsal/etc/turpin/acme/host_files.allow"; assert_output 0
  run grep -c '/opt/acme/x' "$W/hosts/rehearsal/etc/turpin/acme/host_files.allow"; assert_output 1
}

# ---------------------------------------------------------------- through the Python turpin

@test "a_host_gate_is_reported_to_the_controllers_run_log_only (S113)" {
  first_deploy
  run d rollback rehearsal
  assert_failure 1                                             # one finished deploy has no previous
  refute_output --partial "@gate"
  refute_output --partial "@result"
  run jq -r 'select(.event == "gate") | .name' "$(run_log_latest rollback)"
  assert_output --partial "lock"
  assert_output --partial "rollback-target"
}

@test "turpin_rollback_makes_one_request_id_and_the_host_sees_repeat_false (section 6)" {
  first_deploy; second_deploy
  run d rollback rehearsal
  assert_success
  assert_output --partial "rolled back to deploy #1"
  assert_equal "$(host_current rehearsal rehearsal)" 1
  [[ "$(lr request_id)" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$ ]]
  assert_equal "$(lr outcome)" finished
}

@test "a_dropped_connection_after_a_rollback_is_retried_under_the_same_request_id_and_it_runs_once (S91, S93)" {
  first_deploy; second_deploy
  : > "$HOOKLOG"
  STUB_SSH_DROP_AFTER="turpin-host rollback" run d rollback rehearsal
  assert_success
  run grep -c 'turpin-host rollback' "$W/logs/ssh.log"; assert_output 2
  run grep -c '^== restore-state' "$HOOKLOG"; assert_output 1
  assert_equal "$(host_current rehearsal rehearsal)" 1
}

@test "a_rollback_on_a_bare_host_names_the_profiles_fallback (S98)" {
  run d rollback rehearsal
  assert_failure 1
  assert_output --partial "restore the snapshot"                # [turpin].fallback, in the request
  [ ! -e "$(ed)/state.json" ]
}

@test "a_status_call_that_is_dropped_is_retried_and_shown (S91)" {
  first_deploy; : > "$W/logs/ssh.log"; rm -f "$W/logs/ssh.count"
  STUB_SSH_DROP_FIRST=1 run d status rehearsal
  assert_success
  assert_output --partial "state: finished"
  run grep -c 'turpin-host status' "$W/logs/ssh.log"; assert_output 2
}

@test "a_status_call_that_keeps_failing_exits_75_naming_the_rerun (S92)" {
  first_deploy; : > "$W/logs/ssh.log"; rm -f "$W/logs/ssh.count"
  STUB_SSH_DROP_FIRST=9 run d status rehearsal
  assert_failure 75
  assert_output --partial "turpin status rehearsal"
  run grep -c 'turpin-host status' "$W/logs/ssh.log"; assert_output 3
  run jq -r 'select(.event == "retry") | .attempt' "$(run_log_latest status)"
  assert_output "1
2"
}

@test "a_refused_key_or_host_key_exits_2_naming_the_fix (S91)" {
  first_deploy; : > "$W/logs/ssh.log"; rm -f "$W/logs/ssh.count"
  STUB_SSH_FAIL=rehearsal STUB_SSH_FAIL_TEXT="rehearsal: Permission denied (publickey)." run d status rehearsal
  assert_failure 2
  assert_output --partial "ssh agent"
  STUB_SSH_FAIL=rehearsal STUB_SSH_FAIL_TEXT="Host key verification failed." run d status rehearsal
  assert_failure 2
  assert_output --partial "known_hosts"
  run grep -c 'turpin-host status' "$W/logs/ssh.log"; assert_output 2        # one attempt for each of the two calls: nothing was retried
}

# ---------------------------------------------------------------- review round 1

@test "turpin_status_shows_a_host_part_way_through_a_deploy_and_the_request_left_running (section 11)" {
  first_deploy
  commit_change next; build_ok "$SHA"; mkreq "$SHA" "$ID1"
  hook_hold migrate
  hs_start a deploy "$W/request.json"
  wait_file "$HOOKCTL/migrate.reached"
  run d status rehearsal
  assert_success
  assert_output --partial "state: changing: deploy migrate"
  assert_output --partial "pending: deploy 2 commit $SHA"
  assert_output --partial "smoke not passed"
  assert_output --partial "last request: $ID1 running"
  assert_output --partial "current: deploy 1 commit $SHA1"
  hook_release migrate
  hs_close a; hs_wait a
  hook_clear migrate
}

@test "turpin_status_shows_the_previous_deploy_and_a_finished_request (section 11)" {
  first_deploy; second_deploy
  run d status rehearsal
  assert_success
  assert_output --partial "last request: $(lr request_id) finished"
  assert_output --partial "previous: deploy 1 commit $SHA1"
  refute_output --partial "pending:"
}

@test "a_hosts_refusal_is_shown_once (section 6)" {
  first_deploy
  local n; n="$(d rollback rehearsal 2>&1 | grep -c 'no previous deploy' || true)"
  assert_equal "$n" 1
}

@test "a_kill_leaves_its_notes_in_the_state_folder_and_none_outside_it (section 11)" {
  first_deploy
  commit_change next; build_ok "$SHA"; mkreq "$SHA" "$ID1"
  hook_hold migrate
  mkdir -p "$W/tmpx"
  TMPDIR="$W/tmpx" hs_start a deploy "$W/request.json"
  wait_file "$HOOKCTL/migrate.reached"; wait_file "$W/a.pid"
  pkill -9 -P "$(cat "$W/a.pid")"; kill -9 "$(cat "$W/a.pid")"; sleep 0.5
  ls "$(ed)" | grep -q '^note\.'
  run bash -c "ls '$W/tmpx' | grep -c note"
  assert_output 0
  hook_release migrate
  local i; for i in $(seq 1 150); do (exec 9>>"$(ed)/lock"; flock -n 9) && break; sleep 0.2; done
  hook_clear migrate
  host_record_set rehearsal rehearsal '.state = "restored" | del(.pending, .target)'
  mkreq "$SHA" "$ID2"; host_call deploy
  assert_success
  assert_equal "$(leftovers)" ""                                # the next request swept the notes
}

@test "the_watcher_exits_when_its_host_is_killed (section 6)" {
  first_deploy
  commit_change next; build_ok "$SHA"; mkreq "$SHA" "$ID1"
  hook_hold migrate
  hs_start a deploy "$W/request.json"
  wait_file "$HOOKCTL/migrate.reached"; wait_file "$W/a.pid"
  local host watcher; host="$(cat "$W/a.pid")"
  watcher="$(pgrep -P "$host" -f 'turpin-host deploy' | head -1)"   # the host's own fork, not the payload
  [ -n "$watcher" ]
  pkill -9 -P "$host" -f 'payload\.'; kill -9 "$host"
  local i gone=0; for i in $(seq 1 60); do kill -0 "$watcher" 2>/dev/null || { gone=1; break; }; sleep 0.2; done
  hook_release migrate; hs_close a
  [ "$gone" -eq 1 ]
  local j; for j in $(seq 1 150); do (exec 9>>"$(ed)/lock"; flock -n 9) && break; sleep 0.2; done
  hook_clear migrate
}

@test "a_repeat_sent_without_lock_wait_does_not_wait_for_the_lock (section 11)" {
  first_deploy
  commit_change next; build_ok "$SHA"; mkreq "$SHA" "$ID1" true
  jq -c '.lock_wait = null' "$W/request.json" > "$W/request.nw.json"
  lock_hold rehearsal rehearsal
  local start="$SECONDS"
  host_call deploy "$W/request.nw.json"
  lock_release
  assert_failure 1
  assert_output --partial "held by another"
  [ $((SECONDS - start)) -lt 5 ]
}
