#!/usr/bin/env bats

# `turpin deploy`, `rollback` and `status` on a non-production host
# (test-design.md S6 to S16, S31, S36, S54 to S59; rules R5 to R14, R28, R29, R35).

setup() {
  bats_load_library bats-support
  bats_load_library bats-assert
  load turpin_world
  world_new
}

# a first deployed commit on rehearsal: SHA1, deploy #1
first_deploy() {
  commit_change first
  build_ok "$SHA"
  SHA1="$SHA"
  deploy_rehearsal "$SHA1"
  assert_success
}

# a second commit built and deployed (deploy #2); SHA2
second_deploy() {
  commit_change second
  build_ok "$SHA"
  SHA2="$SHA"
  run d deploy rehearsal "$SHA2"
  assert_success
}

@test "deploy_refuses_an_image_whose_label_is_another_sha (S8, R7)" {
  commit_change one; local a="$SHA"; build_ok "$a"
  commit_change two; local b="$SHA"; build_ok "$b"
  # B's tag now points at A's image: its revision label is A
  cp "$W/registry/reg.test/ns/acme/candidates/tags/$a-server" "$W/registry/reg.test/ns/acme/candidates/tags/$b-server"
  local before; before="$(snapshot)"
  run d deploy rehearsal "$b" --off-level "first"
  assert_failure 1
  assert_output --partial "refused at gate digests"
  assert_output --partial "not this commit's build"
  assert_equal "$(snapshot)" "$before"
  # a true image deploys
  cp "$W/registry/reg.test/ns/acme/candidates/tags/$a-server" /dev/null
  run d deploy rehearsal "$a" --off-level "first"
  assert_success
}

@test "deploy_runs_the_payload_from_the_image_not_the_tree, with the R29 environment, in order (S6, R5, R11, R29)" {
  commit_change one
  run d deploy rehearsal "$SHA" --off-level first
  assert_failure 1                                  # no build yet
  assert_output --partial "build-exists"
  build_ok "$SHA"
  # the operator's working tree is edited after the build: it must not be used
  printf '#!/usr/bin/env bash\ntouch "%s/TREE-HOOK-RAN"\n' "$W" > "$W/work/turpin/hooks/pre-deploy"
  : > "$HOOKLOG"
  run d deploy rehearsal "$SHA" --off-level first
  assert_success
  [ ! -e "$W/TREE-HOOK-RAN" ]
  run hook_calls
  assert_output "pre-deploy
save-state
migrate
smoke
post-deploy"
  local env; env="$(hook_log_for smoke)"
  assert_regex "$env" "TURPIN_APP=acme"
  assert_regex "$env" "TURPIN_ENV=rehearsal"
  assert_regex "$env" "TURPIN_ROLE=rehearsal"
  assert_regex "$env" "TURPIN_SHA=$SHA"
  assert_regex "$env" "TURPIN_VERSION=0.10.2"
  assert_regex "$env" "TURPIN_STATE=.*/acme/rehearsal"
  assert_regex "$env" "TURPIN_IMAGE_SERVER=reg.test/ns/acme/candidates@$(cand "$SHA-server")"
  assert_regex "$env" "TURPIN_IMAGE_WEB=reg.test/ns/acme/candidates@$(cand "$SHA-web")"
  # O4
  assert_equal "$(running_digests_of rehearsal acme-rehearsal)" "$(digests_of "$SHA")"
  assert_equal "$(host_current rehearsal rehearsal)" 1
  assert_equal "$(host_state rehearsal rehearsal)" finished
  # O5: the joined files are the commit's, from the payload
  local dd; dd="$(host_state_dir rehearsal rehearsal)/deploys/1"
  cmp "$dd/docker-compose.yml" "$W/work/docker-compose.yml"
  cmp "$dd/Caddyfile" "$W/work/Caddyfile"
  # O8: the host files, with their modes, and the unit enabled after a reload
  [ -x "$W/hosts/rehearsal/opt/acme/backup.sh" ]
  assert_equal "$(stat -c %a "$W/hosts/rehearsal/opt/acme/backup.sh")" 755
  assert_equal "$(stat -c %a "$W/hosts/rehearsal/etc/systemd/system/acme-backup.timer")" 644
  run cat "$W/hosts/rehearsal/.systemctl.log"
  assert_output "systemctl daemon-reload
systemctl enable acme-backup.timer
systemctl restart acme-backup.timer"
}

@test "preview_joins_its_own_files_from_the_payload, on the controller, with no ssh (S7, R5, R6)" {
  commit_change one; build_ok "$SHA"
  : > "$W/logs/ssh.log"
  run d deploy preview "$SHA"
  assert_success
  local dd; dd="$(host_state_dir local preview)/deploys/1"
  cmp "$dd/docker-compose.preview.yml" "$W/work/docker-compose.preview.yml"
  cmp "$dd/Caddyfile.preview" "$W/work/Caddyfile.preview"
  [ ! -e "$dd/docker-compose.yml" ]
  [ ! -s "$W/logs/ssh.log" ]
  # a preview's host files are not installed on a host it shares
  [ ! -e "$W/hosts/local/opt/acme/backup.sh" ]
  assert_equal "$(running_digests_of local acme-preview)" "$(digests_of "$SHA")"
}

@test "deploy_refuses_while_the_lock_is_held, then proceeds when it is free (S9, R8)" {
  commit_change one; build_ok "$SHA"
  lock_hold rehearsal rehearsal
  local before; before="$(snapshot)"
  run d deploy rehearsal "$SHA" --off-level first
  assert_failure 1
  assert_output --partial "refused at gate lock"
  assert_equal "$(snapshot)" "$before"
  lock_release
  run d deploy rehearsal "$SHA" --off-level first
  assert_success
}

@test "deploy_with_wait_proceeds_when_the_lock_frees (S9, R8)" {
  commit_change one; build_ok "$SHA"
  lock_hold rehearsal rehearsal
  ( sleep 2; kill "$LOCK_PID" ) &
  run d deploy rehearsal "$SHA" --off-level first --wait=5
  assert_success
  assert_equal "$(host_state rehearsal rehearsal)" finished
}

@test "pre_deploy_not_yet_refuses_without_wait_and_waits_with_it (S10, R8, R29)" {
  commit_change one; build_ok "$SHA"
  hook_exit pre-deploy 1
  run d deploy rehearsal "$SHA" --off-level first
  assert_failure 1
  assert_output --partial "refused at gate pre-deploy"
  hook_exit pre-deploy 75
  run d deploy rehearsal "$SHA" --off-level first
  assert_failure 1
  assert_output --partial "use --wait"
  hook_exit pre-deploy "75 2"
  run d deploy rehearsal "$SHA" --off-level first --wait=5
  assert_success
  assert_equal "$(grep -c '^== pre-deploy' "$HOOKLOG")" 5      # 1 + 1 + (2 not yet, then 0)
  hook_clear pre-deploy
}

@test "deploy_wait_gives_up_at_the_limit_and_refuses (S54, R8)" {
  commit_change one; build_ok "$SHA"
  # the lock is held beyond the limit
  lock_hold rehearsal rehearsal
  local before; before="$(snapshot)"
  run d deploy rehearsal "$SHA" --off-level first --wait=1
  assert_failure 1
  assert_output --partial "still held after waiting 1 minute(s)"
  assert_equal "$(snapshot)" "$before"
  lock_release
  # a hook answers not yet beyond the limit
  hook_exit pre-deploy 75
  before="$(snapshot)"
  run d deploy rehearsal "$SHA" --off-level first --wait=1
  assert_failure 1
  assert_output --partial "still not yet after waiting 1 minute(s) for hook pre-deploy"
  assert_equal "$(snapshot)" "$before"
  hook_clear pre-deploy
  # the lock frees within the limit
  lock_hold rehearsal rehearsal
  ( sleep 1; kill "$LOCK_PID" ) &
  run d deploy rehearsal "$SHA" --off-level first --wait=4
  assert_success
}

@test "missing_required_hook_refuses_and_missing_optional_hook_is_skipped (S11, R29)" {
  cp "$W/work/turpin/hooks/migrate" "$W/migrate.save"
  git -C "$W/work" rm -q turpin/hooks/migrate
  commit_change one; build_ok "$SHA"
  local before; before="$(snapshot)"
  run d deploy rehearsal "$SHA" --off-level first
  assert_failure 1
  assert_output --partial "required hook migrate is missing"
  assert_equal "$(snapshot)" "$before"

  cp "$W/migrate.save" "$W/work/turpin/hooks/migrate"; chmod -x "$W/work/turpin/hooks/migrate"
  commit_change two; build_ok "$SHA"
  run d deploy rehearsal "$SHA" --off-level first
  assert_failure 1
  assert_output --partial "required hook migrate is not executable"

  chmod +x "$W/work/turpin/hooks/migrate"
  git -C "$W/work" rm -q turpin/hooks/post-deploy
  commit_change three; build_ok "$SHA"
  run d deploy rehearsal "$SHA" --off-level first
  assert_success
}

@test "set_aside_works_only_for_an_overridable_hook (S12, R10, R30)" {
  commit_change one; build_ok "$SHA"
  hook_exit pre-deploy 1
  run d deploy rehearsal "$SHA" --off-level first --set-aside pre-deploy "owner agreed, window closed"
  assert_success
  assert_equal "$(host_state rehearsal rehearsal)" finished
  run grep -h 'set-aside' "$(run_log_latest deploy)"
  assert_output --partial "owner agreed, window closed"
  # the host's own log carries it too
  run grep -rh "owner agreed, window closed" "$(host_state_dir rehearsal rehearsal)/log"
  assert_success
  # not overridable in the next build's profile
  sed -i 's/^overridable = .*/overridable = ["milestone"]/' "$W/work/app-profile.toml"
  commit_change two; build_ok "$SHA"
  run d deploy rehearsal "$SHA" --set-aside pre-deploy "try"
  assert_failure 1
  assert_output --partial "does not list it in overridable"
  # a reason is needed
  run d deploy rehearsal "$SHA" --set-aside pre-deploy
  assert_failure 1
  assert_output --partial "needs a reason"
  hook_clear pre-deploy
}

@test "killed_deploy_is_refused_until_rolled_back (S13, R9)" {
  first_deploy
  commit_change second; build_ok "$SHA"; local sha2="$SHA"
  hook_exit migrate kill
  run d deploy rehearsal "$sha2"
  assert_failure
  hook_clear migrate
  assert_equal "$(host_state rehearsal rehearsal)" "changing: deploy migrate"
  assert_equal "$(host_pending rehearsal rehearsal)" 2
  assert_equal "$(host_target rehearsal rehearsal)" 2
  local before; before="$(snapshot)"
  run d deploy rehearsal "$sha2"
  assert_failure 1
  assert_output --partial "the host is mid-change (state: changing: deploy migrate)"
  assert_output --partial "turpin rollback"
  assert_equal "$(snapshot)" "$before"
  : > "$HOOKLOG"
  run d rollback rehearsal
  assert_success
  run hook_calls
  assert_output "restore-state"
  assert_equal "$(host_current rehearsal rehearsal)" 1
  assert_equal "$(host_state rehearsal rehearsal)" restored
  assert_equal "$(running_digests_of rehearsal acme-rehearsal)" "$(digests_of "$SHA1")"
  run d deploy rehearsal "$sha2"
  assert_success
  assert_equal "$(host_current rehearsal rehearsal)" 3
}

@test "failed_migrate_restores_state_previous_images_and_host_files (S14, R12)" {
  first_deploy
  printf '#!/bin/sh\necho changed\n' > "$W/work/ops/backup.sh"
  commit_change second; build_ok "$SHA"
  hook_exit migrate 1
  : > "$HOOKLOG"
  run d deploy rehearsal "$SHA"
  assert_failure 1
  assert_output --partial "the deploy failed at migrate"
  run hook_calls
  assert_output "pre-deploy
save-state
migrate
restore-state"
  assert_equal "$(host_current rehearsal rehearsal)" 1
  assert_equal "$(host_state rehearsal rehearsal)" restored
  assert_equal "$(running_digests_of rehearsal acme-rehearsal)" "$(digests_of "$SHA1")"
  run cat "$W/hosts/rehearsal/opt/acme/backup.sh"
  assert_output "#!/bin/sh
echo backup"
  hook_clear migrate
}

@test "failed_smoke_restores_state_previous_images_and_host_files (S14, R12)" {
  first_deploy
  printf '#!/bin/sh\necho changed\n' > "$W/work/ops/backup.sh"
  commit_change second; build_ok "$SHA"
  hook_exit smoke 1
  : > "$HOOKLOG"
  run d deploy rehearsal "$SHA"
  assert_failure 1
  assert_output --partial "refused at gate smoke"
  run hook_calls
  assert_output "pre-deploy
save-state
migrate
smoke
restore-state"
  assert_equal "$(host_current rehearsal rehearsal)" 1
  assert_equal "$(running_digests_of rehearsal acme-rehearsal)" "$(digests_of "$SHA1")"
  run cat "$W/hosts/rehearsal/opt/acme/backup.sh"
  assert_output "#!/bin/sh
echo backup"
  hook_clear smoke
}

@test "a failing compose up and a failing host-file install restore the previous deploy (S14, R12)" {
  first_deploy
  commit_change second; build_ok "$SHA"
  STUB_COMPOSE_UP_FAIL=1 run d deploy rehearsal "$SHA"
  assert_failure 1
  assert_output --partial "failed at compose up"
  assert_equal "$(host_current rehearsal rehearsal)" 1
  assert_equal "$(running_digests_of rehearsal acme-rehearsal)" "$(digests_of "$SHA1")"
  STUB_SYSTEMCTL_FAIL=once run d deploy rehearsal "$SHA"
  assert_failure 1
  assert_output --partial "failed at host-files"
  assert_equal "$(host_current rehearsal rehearsal)" 1
  assert_equal "$(running_digests_of rehearsal acme-rehearsal)" "$(digests_of "$SHA1")"
  run d deploy rehearsal "$SHA"
  assert_success
}

@test "host_files_installed_with_modes_and_units_enabled; status_reports_a_host_file_that_differs (S15, R13)" {
  first_deploy
  run d status rehearsal
  assert_success
  refute_output --partial "differs"
  refute_output --partial "missing"
  assert_output --partial "host file /opt/acme/backup.sh: equal"
  printf 'edited by hand\n' > "$W/hosts/rehearsal/opt/acme/backup.sh"
  run d status rehearsal
  assert_success
  assert_output --partial "host file /opt/acme/backup.sh: differs"
  rm "$W/hosts/rehearsal/etc/systemd/system/acme-backup.timer"
  run d status rehearsal
  assert_output --partial "acme-backup.timer: missing"
  # a new release puts both right
  commit_change second; build_ok "$SHA"
  run d deploy rehearsal "$SHA"; assert_success
  run d status rehearsal
  refute_output --partial "differs"
  refute_output --partial "missing"
  # a new host file arrives with the release that lists it
  printf '#!/bin/sh\necho extra\n' > "$W/work/ops/extra.sh"
  cat >> "$W/work/app-profile.toml" <<'EOF'

[[turpin.host_files]]
src = "ops/extra.sh"
dest = "/opt/acme/extra.sh"
mode = "0700"
EOF
  commit_change third; build_ok "$SHA"
  run d host-install rehearsal; assert_success      # the owner's step: the allowlist learns the new destination
  run d deploy rehearsal "$SHA"; assert_success
  assert_equal "$(stat -c %a "$W/hosts/rehearsal/opt/acme/extra.sh")" 700
}

@test "dropped_host_file_is_removed (S55, R13)" {
  first_deploy
  [ -f "$W/hosts/rehearsal/etc/systemd/system/acme-backup.timer" ]
  drop_timer_from_profile
  commit_change second; build_ok "$SHA"
  run d deploy rehearsal "$SHA"
  assert_success
  [ ! -e "$W/hosts/rehearsal/etc/systemd/system/acme-backup.timer" ]
  assert_equal "$(stat -c %a "$W/hosts/rehearsal/opt/acme/backup.sh")" 755
  run grep -c "^systemctl disable acme-backup.timer" "$W/hosts/rehearsal/.systemctl.log"
  assert_output 1
  run d status rehearsal
  refute_output --partial "differs"
  refute_output --partial "missing"
}

@test "rollback_removes_the_current_releases_extra_host_files (S56, R28, R13)" {
  drop_timer_from_profile
  commit_change first; build_ok "$SHA"; local sha1="$SHA"
  run d deploy rehearsal "$sha1" --off-level first; assert_success
  [ ! -e "$W/hosts/rehearsal/etc/systemd/system/acme-backup.timer" ]
  git -C "$W/work" checkout -q HEAD~1 -- app-profile.toml 2>/dev/null || true
  # the second release restores the timer
  git -C "$W/work" show "HEAD~1:app-profile.toml" > "$W/work/app-profile.toml"
  commit_change second; build_ok "$SHA"
  run d deploy rehearsal "$SHA"; assert_success
  [ -f "$W/hosts/rehearsal/etc/systemd/system/acme-backup.timer" ]
  run d rollback rehearsal
  assert_success
  [ ! -e "$W/hosts/rehearsal/etc/systemd/system/acme-backup.timer" ]
  run grep -c "^systemctl disable acme-backup.timer" "$W/hosts/rehearsal/.systemctl.log"
  assert_output 1
  assert_equal "$(host_current rehearsal rehearsal)" 1
  assert_equal "$(running_digests_of rehearsal acme-rehearsal)" "$(digests_of "$sha1")"
  assert_equal "$(stat -c %a "$W/hosts/rehearsal/opt/acme/backup.sh")" 755
}

@test "host_keeps_only_current_and_previous_images (S16, R14)" {
  first_deploy
  second_deploy
  commit_change third; build_ok "$SHA"
  run d deploy rehearsal "$SHA"; assert_success
  run bash -c "ls '$W'/hosts/rehearsal/.docker/images/*.json | wc -l"
  assert_output 4
}

@test "rollback_without_a_previous_deploy_names_the_fallback; with one it switches back (S31, R28)" {
  first_deploy
  local before; before="$(snapshot)"
  run d rollback rehearsal
  assert_failure 1
  assert_output --partial "no previous deploy"
  assert_output --partial "restore the snapshot"
  assert_equal "$(snapshot)" "$before"
  second_deploy
  run d rollback rehearsal
  assert_success
  assert_equal "$(host_current rehearsal rehearsal)" 1
  assert_equal "$(running_digests_of rehearsal acme-rehearsal)" "$(digests_of "$SHA1")"
}

@test "first_deploy_failing_after_save_state_restores_and_names_the_fallback (S57, R12, O24)" {
  commit_change first; build_ok "$SHA"
  local point n=0 dd; dd="$(host_state_dir rehearsal rehearsal)/deploys"
  for point in migrate smoke; do
    n=$((n + 1))
    hook_exit "$point" 1
    : > "$HOOKLOG"
    run d deploy rehearsal "$SHA" --off-level first
    assert_failure 1
    assert_output --partial "Fallback: stop the turpin project"
    assert_regex "$(hook_calls | tr '\n' ' ')" "restore-state"
    # O24: save-state had no current to keep, the state says so, nothing is left of the deploy but its folder
    run hook_log_for save-state
    assert_output --partial "TURPIN_DEPLOY=$n"
    refute_output --partial "TURPIN_CURRENT"
    assert_equal "$(host_state rehearsal rehearsal)" "failed, no previous deploy"
    assert_equal "$(host_current rehearsal rehearsal)" ""
    assert_equal "$(host_pending rehearsal rehearsal)" ""
    assert_equal "$(host_target rehearsal rehearsal)" ""
    [ -z "$(running_digests_of rehearsal acme-rehearsal)" ]
    [ ! -e "$W/hosts/rehearsal/opt/acme/backup.sh" ]
    [ ! -e "$W/hosts/rehearsal/etc/systemd/system/acme-backup.timer" ]
    [ -f "$dd/$n/meta.json" ]
    hook_clear "$point"
  done
  STUB_COMPOSE_UP_FAIL=1 run d deploy rehearsal "$SHA" --off-level first
  assert_failure 1
  assert_output --partial "Fallback"
  assert_equal "$(host_state rehearsal rehearsal)" "failed, no previous deploy"
  [ -z "$(running_digests_of rehearsal acme-rehearsal)" ]
  # the next deploy is the way forward
  rm -f "$W/hosts/rehearsal/.docker/up_failed"
  run d deploy rehearsal "$SHA" --off-level first
  assert_success
  assert_equal "$(host_state rehearsal rehearsal)" finished
  assert_equal "$(host_current rehearsal rehearsal)" 4
}

@test "first_deploy_failing_before_save_state_changes_nothing (S57, R12)" {
  commit_change first; build_ok "$SHA"
  hook_exit pre-deploy 1
  local before; before="$(snapshot)"
  run d deploy rehearsal "$SHA" --off-level first
  assert_failure 1
  assert_equal "$(snapshot)" "$before"
  # the only record is the refused request's, which holds nothing else
  run jq -c '[keys, .last_request.outcome]' "$(host_state_dir rehearsal rehearsal)/state.json"
  assert_output '[["last_request"],"refused"]'
  refute_regex "$(hook_calls | tr '\n' ' ')" "save-state"
  hook_clear pre-deploy
}

@test "deploy_after_a_failed_first_deploy_proceeds (S57, R9)" {
  commit_change first; build_ok "$SHA"
  hook_exit migrate 1
  run d deploy rehearsal "$SHA" --off-level first
  assert_failure 1
  hook_clear migrate
  run d deploy rehearsal "$SHA" --off-level first
  assert_success
  assert_equal "$(host_state rehearsal rehearsal)" finished
}

@test "ambiguous_short_sha_refuses, and a longer prefix deploys (S58, R6)" {
  commit_change first; build_ok "$SHA"
  local real="$SHA" fake six
  six="${real:5:1}"; six="$([ "$six" = 0 ] && echo 1 || echo 0)"
  fake="${real:0:5}${six}$(printf 'e%.0s' $(seq 34))"
  local c="$W/registry/reg.test/ns/acme/candidates"
  cp "$c/tags/$real-server" "$c/tags/$fake-server"; cp "$c/tags/$real-web" "$c/tags/$fake-web"
  local before; before="$(snapshot)"
  run d deploy rehearsal "${real:0:5}" --off-level first
  assert_failure 1
  assert_output --partial "ref-unambiguous"
  assert_output --partial "$real"
  assert_output --partial "$fake"
  assert_equal "$(snapshot)" "$before"
  run d deploy rehearsal "${real:0:8}" --off-level first
  assert_success
}

@test "pull_beyond_timeout_refuses_before_change (S36, R35)" {
  commit_change first; build_ok "$SHA"
  sed -i 's/^pull_timeout = 60/pull_timeout = 1/' "$W/work/app-profile.toml"
  local before; before="$(snapshot)"
  STUB_PULL_SECONDS=3 run d deploy rehearsal "$SHA" --off-level first
  assert_failure 1
  assert_output --partial "longer than pull_timeout (1 s)"
  assert_equal "$(snapshot)" "$before"
  run d deploy rehearsal "$SHA" --off-level first
  assert_success
}

@test "post_deploy_check_failure_is_reported_and_leaves_the_exit_code (S59, R29)" {
  commit_change first; build_ok "$SHA"
  hook_exit post-deploy 1
  run d deploy rehearsal "$SHA" --off-level first
  assert_success
  assert_output --partial "check post-deploy reported exit 1"
  assert_equal "$(host_state rehearsal rehearsal)" finished
  hook_clear post-deploy
  commit_change second; build_ok "$SHA"
  run d deploy rehearsal "$SHA"
  assert_success
  refute_output --partial "post-deploy reported"
}

@test "status shows the digests, the state and the matching record; list shows the records beside them (S46, R40)" {
  first_deploy
  second_deploy
  run d status rehearsal
  assert_success
  assert_output --partial "state: finished"
  assert_output --partial "current: deploy 2 commit $SHA2"
  assert_output --partial "image server $(cand "$SHA2-server")"
  assert_output --partial "running: the current digests"
  assert_output --partial "record: none matches"
  run d list rehearsal
  assert_success
}

# ---- design §11: state.json, the state table, the restore and the rollback --------------

# four finished deploys (current 4, previous 3); SHA1..SHA4
four_deploys() {
  first_deploy
  local i
  for i in b c d; do commit_change "$i"; build_ok "$SHA"; run d deploy rehearsal "$SHA"; assert_success; done
  SHA4="$SHA"
}

# a deploy cut short in step 6: the payload copy kills the step and the host command
killed_in_step_6() {   # SHA
  STUB_CP=kill run d deploy rehearsal "$1"
  assert_failure
}

@test "a_pruned_deploy_folder_keeps_only_its_meta_json (S82, R54)" {
  four_deploys
  local dd n; dd="$(host_state_dir rehearsal rehearsal)/deploys"
  assert_equal "$(ls "$dd" | tr '\n' ' ')" "1 2 3 4 "
  for n in 1 2; do
    assert_equal "$(ls -A "$dd/$n")" "meta.json"
    jq -e --argjson n "$n" '.n == $n and has("sha") and has("version") and has("images") and has("role") and has("record")
      and has("join") and has("host_files") and has("project") and .smoke == "passed" and (.deployed | type) == "string"' "$dd/$n/meta.json"
  done
  assert_equal "$(jq -r .sha "$dd/1/meta.json")" "$SHA1"
  for n in 3 4; do [ -d "$dd/$n/payload" ] && [ -f "$dd/$n/turpin.env" ] && [ -f "$dd/$n/docker-compose.yml" ]; done
  assert_equal "$(host_current rehearsal rehearsal)" 4
  assert_equal "$(host_previous rehearsal rehearsal)" 3
}

@test "the host's record is one state.json, replaced whole, and the Bash files are gone (S82, R54)" {
  first_deploy
  local ed; ed="$(host_state_dir rehearsal rehearsal)"
  [ -f "$ed/state.json" ]
  [ ! -e "$ed/state" ] && [ ! -e "$ed/counter" ] && [ ! -e "$ed/current" ] && [ ! -e "$ed/previous" ] && [ ! -e "$ed/host_files.installed" ]
  [ -z "$(ls "$ed" | grep 'state.json.')" ]
  run jq -c 'del(.installed_host_files) | keys' "$ed/state.json"
  assert_output '["current","last_request","state"]'
  run jq -c '.installed_host_files | map(.dest) | sort' "$ed/state.json"
  assert_output '["/etc/systemd/system/acme-backup.timer","/opt/acme/backup.sh"]'
  run jq -c '.current' "$ed/state.json"
  assert_output 1
}

@test "a_failed_restore_refuses_the_next_deploy_naming_rollback (S95, R9)" {
  first_deploy
  commit_change b; build_ok "$SHA"; local sha2="$SHA"
  hook_exit migrate 1; hook_exit restore-state "1 1"
  run d deploy rehearsal "$sha2"
  assert_failure 1
  assert_equal "$(host_state rehearsal rehearsal)" "failed: the restore did not complete"
  assert_equal "$(host_pending rehearsal rehearsal)" 2
  assert_equal "$(host_target rehearsal rehearsal)" 2
  assert_equal "$(host_current rehearsal rehearsal)" 1
  hook_clear migrate
  local before; before="$(snapshot)"
  run d deploy rehearsal "$sha2"
  assert_failure 1
  assert_output --partial "refused at gate state"
  assert_output --partial "failed: the restore did not complete"
  assert_output --partial "turpin rollback"
  assert_equal "$(snapshot)" "$before"
}

@test "a_kill_in_step_6_leaves_a_folder_the_next_deploy_numbers_past (S95, R9)" {
  four_deploys
  local dd; dd="$(host_state_dir rehearsal rehearsal)/deploys"
  commit_change e; build_ok "$SHA"
  killed_in_step_6 "$SHA"
  assert_equal "$(host_state rehearsal rehearsal)" "preparing: deploy-folder"
  assert_equal "$(host_pending rehearsal rehearsal)" 5
  [ -d "$dd/5" ] && [ ! -e "$dd/5/meta.json" ]
  assert_equal "$(host_current rehearsal rehearsal)" 4
  # a new deploy is not refused; it numbers past the folder, and its prune removes it
  run d deploy rehearsal "$SHA"
  assert_success
  assert_equal "$(host_current rehearsal rehearsal)" 6
  assert_equal "$(host_previous rehearsal rehearsal)" 4
  assert_equal "$(host_pending rehearsal rehearsal)" ""
  assert_equal "$(ls "$dd" | tr '\n' ' ')" "1 2 3 4 6 "
  assert_equal "$(ls -A "$dd/3")" "meta.json"
  assert_equal "$(jq -r .n "$dd/1/meta.json")" 1
  # a folder whose meta.json was written is cut to it
  mkdir -p "$dd/7/payload"; : > "$dd/7/payload/x"
  jq -c '.n = 7 | .deployed = null | .smoke = null' "$dd/6/meta.json" > "$dd/7/meta.json"
  host_record_set rehearsal rehearsal '.state = "preparing: deploy-folder" | .pending = 7'
  commit_change f; build_ok "$SHA"
  run d deploy rehearsal "$SHA"
  assert_success
  assert_equal "$(host_current rehearsal rehearsal)" 8
  assert_equal "$(ls -A "$dd/7")" "meta.json"
  assert_equal "$(jq -r .smoke "$dd/7/meta.json")" null
}

@test "a_failure_in_step_6_removes_its_folder (S95, R9)" {
  first_deploy
  commit_change b; build_ok "$SHA"
  local before; before="$(snapshot)"
  STUB_CP=fail run d deploy rehearsal "$SHA"
  assert_failure 1
  assert_output --partial "cannot keep the payload"
  assert_equal "$(ls "$(host_state_dir rehearsal rehearsal)/deploys")" 1
  assert_equal "$(host_pending rehearsal rehearsal)" ""
  assert_equal "$(host_state rehearsal rehearsal)" finished
  assert_equal "$(snapshot)" "$before"
}

@test "rollback_restores_a_deploy_killed_before_or_after_compose_up (S96, R9)" {
  first_deploy; second_deploy
  printf '#!/bin/sh\necho changed\n' > "$W/work/ops/backup.sh"
  local point sha n=3
  for point in migrate smoke; do
    commit_change "third $point"; build_ok "$SHA"; sha="$SHA"
    hook_exit "$point" kill
    run d deploy rehearsal "$sha"
    assert_failure
    hook_clear "$point"
    assert_equal "$(host_state rehearsal rehearsal)" "changing: deploy $point"
    assert_equal "$(host_pending rehearsal rehearsal)" "$n"
    if [ "$point" = smoke ]; then      # compose up from pending had run
      assert_equal "$(running_digests_of rehearsal acme-rehearsal)" "$(digests_of "$sha")"
    fi
    : > "$HOOKLOG"
    run d rollback rehearsal
    assert_success
    run hook_calls
    assert_output "restore-state"
    run hook_log_for restore-state
    assert_output --partial "TURPIN_DEPLOY=$n"
    assert_equal "$(host_state rehearsal rehearsal)" restored
    assert_equal "$(host_current rehearsal rehearsal)" 2
    assert_equal "$(host_previous rehearsal rehearsal)" 1
    assert_equal "$(host_pending rehearsal rehearsal)" ""
    assert_equal "$(host_target rehearsal rehearsal)" ""
    assert_equal "$(running_digests_of rehearsal acme-rehearsal)" "$(digests_of "$SHA2")"
    run cat "$W/hosts/rehearsal/opt/acme/backup.sh"
    assert_output "#!/bin/sh
echo backup"
    [ -f "$W/hosts/rehearsal/etc/systemd/system/acme-backup.timer" ]
    n=$((n + 1))
  done
}

@test "a_rollback_killed_part_way_is_run_again (S96, R9)" {
  first_deploy; second_deploy
  hook_exit restore-state kill
  run d rollback rehearsal
  assert_failure
  hook_clear restore-state
  assert_equal "$(host_state rehearsal rehearsal)" "changing: rollback 2"
  assert_equal "$(host_target rehearsal rehearsal)" 1
  assert_equal "$(host_current rehearsal rehearsal)" 2
  run d rollback rehearsal
  assert_success
  assert_equal "$(host_current rehearsal rehearsal)" 1
  assert_equal "$(host_previous rehearsal rehearsal)" ""
  assert_equal "$(host_state rehearsal rehearsal)" restored
  assert_equal "$(host_target rehearsal rehearsal)" ""
  assert_equal "$(running_digests_of rehearsal acme-rehearsal)" "$(digests_of "$SHA1")"
}

@test "rollback_reruns_a_first_deploys_failed_restore (S96, R9)" {
  commit_change first; build_ok "$SHA"
  hook_exit migrate 1; hook_exit restore-state "1 1"
  run d deploy rehearsal "$SHA" --off-level first
  assert_failure 1
  assert_equal "$(host_state rehearsal rehearsal)" "failed: the restore did not complete"
  assert_equal "$(host_pending rehearsal rehearsal)" 1
  assert_equal "$(host_target rehearsal rehearsal)" 1
  hook_clear migrate
  run d deploy rehearsal "$SHA" --off-level first
  assert_failure 1
  assert_output --partial "turpin rollback"
  : > "$HOOKLOG"
  run d rollback rehearsal
  assert_success
  assert_output --partial "Fallback: stop the turpin project"
  run hook_log_for restore-state
  assert_output --partial "TURPIN_DEPLOY=1"
  assert_equal "$(host_state rehearsal rehearsal)" "failed, no previous deploy"
  assert_equal "$(host_pending rehearsal rehearsal)" ""
  assert_equal "$(host_target rehearsal rehearsal)" ""
  [ -z "$(running_digests_of rehearsal acme-rehearsal)" ]
  [ ! -e "$W/hosts/rehearsal/opt/acme/backup.sh" ]
}

@test "restore_state_finds_no_complete_snapshot_and_restores_nothing (S97, R12)" {
  contract_hooks
  commit_change first; build_ok "$SHA"; deploy_rehearsal "$SHA"; assert_success
  assert_equal "$(data_db)" "m1 "
  commit_change second; build_ok "$SHA"
  hook_exit save-state kill
  run d deploy rehearsal "$SHA"
  assert_failure
  run hook_log_for save-state
  assert_output --partial "TURPIN_DEPLOY=2"
  assert_output --partial "TURPIN_CURRENT=1"
  hook_clear save-state
  assert_equal "$(host_state rehearsal rehearsal)" "changing: deploy save-state"
  [ -d "$W/data/snaps/2" ] && [ ! -e "$W/data/snaps/2/complete" ]
  : > "$HOOKLOG"
  run d rollback rehearsal
  assert_success
  run hook_log_for restore-state
  assert_output --partial "TURPIN_DEPLOY=2"
  assert_equal "$(data_db)" "m1 "
  assert_equal "$(host_state rehearsal rehearsal)" restored
}

@test "rollback_restores_currents_snapshot_never_the_restored_deploys (S97, R12, R28)" {
  contract_hooks
  commit_change first; build_ok "$SHA"; deploy_rehearsal "$SHA"; assert_success
  commit_change second; build_ok "$SHA"; run d deploy rehearsal "$SHA"; assert_success
  assert_equal "$(data_db)" "m1 m2 "
  commit_change third; build_ok "$SHA"
  hook_exit migrate 1
  run d deploy rehearsal "$SHA"
  assert_failure 1
  assert_equal "$(host_state rehearsal rehearsal)" restored
  assert_equal "$(data_db)" "m1 m2 "                      # the failed deploy's migration is undone
  hook_clear migrate
  : > "$HOOKLOG"
  run d rollback rehearsal
  assert_success
  run hook_log_for restore-state
  assert_output --partial "TURPIN_DEPLOY=2"               # current's, not the restored deploy's 3
  assert_equal "$(data_db)" "m1 "                         # the data as before current's migrate
  assert_equal "$(host_current rehearsal rehearsal)" 1
}

@test "save_state_keeps_currents_snapshot_through_six_failed_deploys (S97, R28, R29)" {
  contract_hooks
  commit_change first; build_ok "$SHA"; deploy_rehearsal "$SHA"; assert_success
  commit_change second; build_ok "$SHA"; run d deploy rehearsal "$SHA"; assert_success
  commit_change third; build_ok "$SHA"
  hook_exit migrate 1
  local i
  for i in 1 2 3 4 5 6; do
    run d deploy rehearsal "$SHA"
    assert_failure 1
    assert_equal "$(host_state rehearsal rehearsal)" restored
    [ -f "$W/data/snaps/2/complete" ]
  done
  assert_equal "$(grep -c '^TURPIN_CURRENT=2$' "$HOOKLOG")" 6
  hook_clear migrate
  run d rollback rehearsal
  assert_success
  assert_equal "$(data_db)" "m1 "
}

@test "rollback_on_a_bare_host_refuses_naming_the_fallback (S98, R57)" {
  local before; before="$(snapshot)"
  run d rollback rehearsal
  assert_failure 1
  assert_output --regexp '[Ff]allback'
  [ ! -e "$(host_state_dir rehearsal rehearsal)/state.json" ]
  [ ! -e "$(host_state_dir rehearsal rehearsal)/deploys" ]
  assert_equal "$(snapshot)" "$before"
}

@test "rollback_from_preparing_switches_to_previous_or_refuses_without_one (S99, R57)" {
  # case 2: one finished deploy has no previous
  first_deploy
  commit_change b; build_ok "$SHA"; local sha2="$SHA"
  killed_in_step_6 "$sha2"
  assert_equal "$(host_state rehearsal rehearsal)" "preparing: deploy-folder"
  # what the kill left is not the rollback's change: the next request sweeps it (turpin-protocol.bats)
  rm -rf "${W:?}/hosts/rehearsal/var/lib/turpin/acme/rehearsal"/payload.* "${W:?}/hosts/rehearsal/var/lib/turpin/acme/rehearsal"/request.* "${W:?}/hosts/rehearsal/var/lib/turpin/acme/rehearsal"/note.*
  local before; before="$(snapshot)"
  run d rollback rehearsal
  assert_failure 1
  assert_output --partial "no previous deploy"
  assert_output --partial "Fallback: stop the turpin project"
  assert_equal "$(host_state rehearsal rehearsal)" "preparing: deploy-folder"
  assert_equal "$(snapshot)" "$before"
  # case 1: two finished deploys; the new deploy runs from preparing, then another is killed in step 6
  run d deploy rehearsal "$sha2"
  assert_success
  commit_change c; build_ok "$SHA"; local sha3="$SHA"
  killed_in_step_6 "$sha3"
  assert_equal "$(host_state rehearsal rehearsal)" "preparing: deploy-folder"
  local cur prev; cur="$(host_current rehearsal rehearsal)"; prev="$(host_previous rehearsal rehearsal)"
  : > "$HOOKLOG"
  run d rollback rehearsal
  assert_success
  run hook_log_for restore-state
  assert_output --partial "TURPIN_DEPLOY=$cur"          # current's number
  assert_equal "$(host_current rehearsal rehearsal)" "$prev"
  assert_equal "$(host_previous rehearsal rehearsal)" ""
  assert_equal "$(host_pending rehearsal rehearsal)" ""
  assert_equal "$(host_state rehearsal rehearsal)" restored
  assert_equal "$(running_digests_of rehearsal acme-rehearsal)" "$(digests_of "$SHA1")"
}

@test "a_new_deploy_after_a_rollback_left_part_way_is_refused_naming_rollback (S100, R9, R57)" {
  first_deploy; second_deploy
  commit_change third; build_ok "$SHA"; local sha3="$SHA"
  hook_exit restore-state kill
  run d rollback rehearsal
  assert_failure
  hook_clear restore-state
  local before; before="$(snapshot)"
  run d deploy rehearsal "$sha3"
  assert_failure 1
  assert_output --partial "changing: rollback 2"
  assert_output --partial "turpin rollback"
  assert_equal "$(snapshot)" "$before"
  run d rollback rehearsal
  assert_success
  assert_equal "$(host_current rehearsal rehearsal)" 1
  run d deploy rehearsal "$sha3"
  assert_success
  assert_equal "$(running_digests_of rehearsal acme-rehearsal)" "$(digests_of "$sha3")"
}

@test "a_rollback_that_fails_is_run_again_and_blocks_a_deploy_meanwhile (S101, R57)" {
  first_deploy; second_deploy
  commit_change third; build_ok "$SHA"; local sha3="$SHA"
  hook_exit restore-state 1
  run d rollback rehearsal
  assert_failure 1
  assert_equal "$(host_state rehearsal rehearsal)" "changing: rollback 2"
  assert_equal "$(host_current rehearsal rehearsal)" 2          # nothing undone
  assert_equal "$(host_previous rehearsal rehearsal)" 1
  run d deploy rehearsal "$sha3"
  assert_failure 1
  assert_output --partial "turpin rollback"
  hook_clear restore-state
  run d rollback rehearsal
  assert_success
  assert_equal "$(host_current rehearsal rehearsal)" 1
  assert_equal "$(host_state rehearsal rehearsal)" restored
}

@test "a_second_rollback_refuses_naming_the_fallback (S102, R28, R57)" {
  first_deploy; second_deploy
  run d rollback rehearsal
  assert_success
  local before; before="$(snapshot)"
  run d rollback rehearsal
  assert_failure 1
  assert_output --partial "no previous deploy"
  assert_output --partial "Fallback: stop the turpin project"
  assert_equal "$(host_state rehearsal rehearsal)" restored
  assert_equal "$(snapshot)" "$before"
  commit_change third; build_ok "$SHA"
  run d deploy rehearsal "$SHA"
  assert_success
  assert_equal "$(host_state rehearsal rehearsal)" finished
}

@test "rollback_after_a_failed_first_deploy_refuses_naming_the_fallback (S103, R57)" {
  commit_change first; build_ok "$SHA"
  hook_exit migrate 1
  run d deploy rehearsal "$SHA" --off-level first
  assert_failure 1
  hook_clear migrate
  local before; before="$(snapshot)"
  run d rollback rehearsal
  assert_failure 1
  assert_output --partial "Fallback: stop the turpin project"
  assert_equal "$(host_state rehearsal rehearsal)" "failed, no previous deploy"
  assert_equal "$(snapshot)" "$before"
}

@test "rollback_after_a_failed_restore_runs_the_restore_again_from_current (S104, R57)" {
  first_deploy
  printf '#!/bin/sh\necho changed\n' > "$W/work/ops/backup.sh"
  commit_change second; build_ok "$SHA"; local sha2="$SHA"
  hook_exit migrate 1; hook_exit restore-state "1 1"
  run d deploy rehearsal "$sha2"
  assert_failure 1
  assert_equal "$(host_state rehearsal rehearsal)" "failed: the restore did not complete"
  assert_equal "$(host_pending rehearsal rehearsal)" 2
  assert_equal "$(host_target rehearsal rehearsal)" 2
  hook_clear migrate
  run d deploy rehearsal "$sha2"
  assert_failure 1
  assert_output --partial "turpin rollback"
  : > "$HOOKLOG"
  run d rollback rehearsal
  assert_success
  run hook_log_for restore-state
  assert_output --partial "TURPIN_DEPLOY=2"
  assert_equal "$(host_state rehearsal rehearsal)" restored
  assert_equal "$(host_pending rehearsal rehearsal)" ""
  assert_equal "$(host_target rehearsal rehearsal)" ""
  assert_equal "$(host_current rehearsal rehearsal)" 1
  assert_equal "$(host_previous rehearsal rehearsal)" ""
  assert_equal "$(running_digests_of rehearsal acme-rehearsal)" "$(digests_of "$SHA1")"
  run cat "$W/hosts/rehearsal/opt/acme/backup.sh"
  assert_output "#!/bin/sh
echo backup"
}

# S112: each command, directly on the host, against a folder in the Bash turpin's layout
layout_refused() {   # WHAT-IT-NAMES
  local root="$W/hosts/rehearsal" cmd
  for cmd in "deploy acme rehearsal" "rollback acme rehearsal" "status acme rehearsal --json" "allowlist acme"; do
    run bash -c "echo '{}' | env TURPIN_HOST_ROOT='$root' '$TURPIN_HOST' $cmd"
    assert_failure 2
    assert_output --partial "$1"
  done
}

@test "a_state_folder_in_the_bash_turpins_layout_is_refused_by_deploy_rollback_status_and_allowlist (S112, R60)" {
  commit_change first; build_ok "$SHA"
  local ed; ed="$(host_state_dir rehearsal rehearsal)"
  printf 'finished\ndeploy=1\n' > "$ed/state"
  local before; before="$(snapshot)"
  layout_refused "$ed/state"
  assert_equal "$(snapshot)" "$before"
  rm "$ed/state"
  mkdir -p "$ed/deploys/1"; ln -s deploys/1 "$ed/current"
  before="$(snapshot)"
  layout_refused "$ed/current"
  assert_equal "$(snapshot)" "$before"
  rm "$ed/current"; rm -rf "$ed/deploys"
  run d deploy rehearsal "$SHA" --off-level first
  assert_success
  assert_equal "$(host_state rehearsal rehearsal)" finished
}

@test "host_status_json_is_one_result_object (R54)" {
  first_deploy
  run env TURPIN_HOST_ROOT="$W/hosts/rehearsal" "$TURPIN_HOST" status acme rehearsal --json
  assert_success
  run jq -e --arg sha "$SHA1" '.outcome == "ok" and .domain == "turpin" and (.reason | type) == "string" and (.message | type) == "string"
    and .metadata.state == "finished" and .metadata.pending == null and .metadata.last_request.outcome == "finished"
    and .metadata.current.n == 1 and .metadata.current.sha == $sha and .metadata.current.smoke == "passed"
    and (.metadata.current.deployed | type) == "string" and .metadata.previous == null and (.metadata.running | length) == 2' <<< "$output"
  assert_success
}

# the request the controller sends turpin-host deploy for REF, kept (by --check) and made real
captured_request() {   # REF -> $W/request.json
  STUB_SSH_TEE="$W/request.check.json" run d deploy rehearsal "$1" --check --off-level "test world"
  assert_success
  jq -c '.check = false' "$W/request.check.json" > "$W/request.json"
}
direct_deploy() {   # runs turpin-host deploy on the rehearsal host with $W/request.json, under a request id of its own, the input held open
  jq -c --arg id "$(cat /proc/sys/kernel/random/uuid)" '.request_id = $id' "$W/request.json" > "$W/request.fresh.json"
  run env TURPIN_HOST_ROOT="$W/hosts/rehearsal" bash -c "'$TURPIN_HOST' deploy acme rehearsal < <(held-request '$W/request.fresh.json')"
}

@test "one_failed_delete_in_prune_leaves_the_others_removed_and_exits_3 (R54)" {
  first_deploy; second_deploy
  commit_change third; build_ok "$SHA"
  captured_request "$SHA"
  STUB_RMI_FAIL=1 direct_deploy
  assert_failure 3
  assert_output --partial "pruning the host's images failed"
  assert_equal "$(host_state rehearsal rehearsal)" finished
  assert_equal "$(host_current rehearsal rehearsal)" 3
  # the folders were still pruned: a failure in one step does not end the others
  assert_equal "$(ls -A "$(host_state_dir rehearsal rehearsal)/deploys/1")" "meta.json"
}

@test "host_exit keeps the statuses docs/1.10 names and makes any other unexpected, 70 (R54)" {
  run bash -c "export TURPIN_LIB='$TURPIN_SRC/lib'; . <(sed '\$d' '$TURPIN_HOST'); for c in 0 1 2 3 64 70 75 130 4 137 255; do printf '%s ' \$(host_exit \$c); done"
  assert_output "0 1 2 3 64 70 75 130 70 70 70 "
}

@test "a_payload_step_killed_outright_exits_70 and a_refusal_exits_1 (R54)" {
  first_deploy
  commit_change second; build_ok "$SHA"
  captured_request "$SHA"
  hook_exit migrate kill
  direct_deploy
  assert_failure 70
  hook_clear migrate
  host_record_set rehearsal rehearsal '.state = "finished"'
  hook_exit pre-deploy 1
  direct_deploy
  assert_failure 1
}

@test "a_failed_stop_in_a_first_deploys_restore_marks_the_restore_incomplete (S57, R12)" {
  commit_change first; build_ok "$SHA"
  hook_exit smoke 1
  STUB_COMPOSE_DOWN_FAIL=1 run d deploy rehearsal "$SHA" --off-level first
  assert_failure 1
  assert_output --partial "stopping the failed deploy's containers failed"
  assert_equal "$(host_state rehearsal rehearsal)" "failed: the restore did not complete"
  assert_equal "$(host_pending rehearsal rehearsal)" 1
  assert_equal "$(host_target rehearsal rehearsal)" 1
  hook_clear smoke
  run d rollback rehearsal
  assert_success
  assert_equal "$(host_state rehearsal rehearsal)" "failed, no previous deploy"
}

@test "an_unexpected_error_after_step_7_runs_the_restore (R12)" {
  first_deploy
  cat > "$W/work/turpin/hooks/smoke" <<'EOF2'
#!/usr/bin/env bash
echo "== smoke" >> "$HOOKLOG"
n="$(jq -r .pending "$TURPIN_STATE/state.json")"
echo '{' > "$TURPIN_STATE/deploys/$n/payload/profile.json"
EOF2
  commit_change second; build_ok "$SHA"
  : > "$HOOKLOG"
  run d deploy rehearsal "$SHA"
  assert_failure 1
  assert_output --partial "the deploy failed at reading the host files"
  assert_equal "$(hook_calls | grep -c '^restore-state$')" 1      # the restore ran once
  # the restore could not tell which host files the deploy installed, so it says it is incomplete
  assert_equal "$(host_state rehearsal rehearsal)" "failed: the restore did not complete"
  assert_equal "$(host_current rehearsal rehearsal)" 1
  assert_equal "$(host_pending rehearsal rehearsal)" 2
  # a rollback cannot read the corrupt file either, and says which file to repair
  run d rollback rehearsal
  assert_failure 1
  assert_output --partial "deploys/2/payload/profile.json is not valid JSON"
  assert_output --partial "repair or restore it, then run turpin rollback ENV again"
  refute_output --partial "parse error"
}

@test "a_restore_stops_at_its_first_failed_step_and_never_starts_currents_build_on_data_not_restored (S104, R57)" {
  first_deploy
  commit_change second; build_ok "$SHA"; local sha2="$SHA"
  hook_exit smoke 1; hook_exit restore-state 1
  run d deploy rehearsal "$sha2"
  assert_failure 1
  assert_equal "$(host_state rehearsal rehearsal)" "failed: the restore did not complete"
  # the failed build still runs; current's was not started over it
  assert_equal "$(running_digests_of rehearsal acme-rehearsal)" "$(digests_of "$sha2")"
}

@test "a_mid_change_gate_says_so_and_names_the_step_and_rollback (S13)" {
  first_deploy
  host_record_set rehearsal rehearsal '.state = "changing: deploy smoke" | .pending = 2 | .target = 2'
  run d deploy rehearsal "$SHA1"
  assert_failure 1
  assert_output --partial "the host is mid-change (state: changing: deploy smoke)"
  assert_output --partial "turpin rollback"
}

@test "a_deploy_is_refused_while_another_environment_of_the_application_is_in_the_bash_layout (S112)" {
  printf '\n[environments.checks]\nrole = "test"\nssh = "rehearsal"\nlogin = "docker-config"\n' >> "$W/work/app-profile.toml"
  commit_change a; build_ok "$SHA"
  captured_request "$SHA"
  local other="$W/hosts/rehearsal/var/lib/turpin/acme/checks"
  mkdir -p "$other"; printf 'finished\ndeploy=1\n' > "$other/state"
  local before pulls; before="$(snapshot)"; pulls="$(grep -c 'docker pull' "$W/hosts/rehearsal/.docker/log" 2>/dev/null || true)"
  direct_deploy
  assert_failure 2
  assert_output --partial "$other/state"
  [ ! -e "$(host_state_dir rehearsal rehearsal)/state.json" ]
  assert_equal "$(snapshot)" "$before"
  assert_equal "$(grep -c 'docker pull' "$W/hosts/rehearsal/.docker/log" 2>/dev/null || true)" "$pulls"
}
