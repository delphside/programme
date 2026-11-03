#!/usr/bin/env bats

# `deliver deploy`, `rollback` and `status` on a non-production host
# (test-design.md S6 to S16, S31, S36, S54 to S59; rules R5 to R14, R28, R29, R35).

setup() {
  bats_load_library bats-support
  bats_load_library bats-assert
  load deliver_world
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
  printf '#!/usr/bin/env bash\ntouch "%s/TREE-HOOK-RAN"\n' "$W" > "$W/work/deliver/hooks/pre-deploy"
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
  assert_regex "$env" "DELIVER_APP=acme"
  assert_regex "$env" "DELIVER_ENV=rehearsal"
  assert_regex "$env" "DELIVER_ROLE=rehearsal"
  assert_regex "$env" "DELIVER_SHA=$SHA"
  assert_regex "$env" "DELIVER_VERSION=0.10.2"
  assert_regex "$env" "DELIVER_STATE=.*/acme/rehearsal"
  assert_regex "$env" "DELIVER_IMAGE_SERVER=reg.test/ns/acme/candidates@$(cand "$SHA-server")"
  assert_regex "$env" "DELIVER_IMAGE_WEB=reg.test/ns/acme/candidates@$(cand "$SHA-web")"
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

@test "preview_joins_its_own_files_from_the_payload, on the control node, with no ssh (S7, R5, R6)" {
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
  cp "$W/work/deliver/hooks/migrate" "$W/migrate.save"
  git -C "$W/work" rm -q deliver/hooks/migrate
  commit_change one; build_ok "$SHA"
  local before; before="$(snapshot)"
  run d deploy rehearsal "$SHA" --off-level first
  assert_failure 1
  assert_output --partial "required hook migrate is missing"
  assert_equal "$(snapshot)" "$before"

  cp "$W/migrate.save" "$W/work/deliver/hooks/migrate"; chmod -x "$W/work/deliver/hooks/migrate"
  commit_change two; build_ok "$SHA"
  run d deploy rehearsal "$SHA" --off-level first
  assert_failure 1
  assert_output --partial "required hook migrate is not executable"

  chmod +x "$W/work/deliver/hooks/migrate"
  git -C "$W/work" rm -q deliver/hooks/post-deploy
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

@test "interrupted_deploy_is_refused_until_rolled_back (S13, R9)" {
  first_deploy
  commit_change second; build_ok "$SHA"; local sha2="$SHA"
  hook_exit migrate kill
  run d deploy rehearsal "$sha2"
  assert_failure
  hook_clear migrate
  assert_regex "$(host_state rehearsal rehearsal)" "in progress: migrate"
  run d deploy rehearsal "$sha2"
  assert_failure 1
  assert_output --partial "did not finish (state: in progress: migrate)"
  : > "$HOOKLOG"
  run d rollback rehearsal
  assert_success
  run hook_calls
  assert_output "restore-state"
  assert_equal "$(host_current rehearsal rehearsal)" 1
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
  STUB_SYSTEMCTL_FAIL=1 run d deploy rehearsal "$SHA"
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

[[deliver.host_files]]
src = "ops/extra.sh"
dest = "/opt/acme/extra.sh"
mode = "0700"
EOF
  commit_change third; build_ok "$SHA"
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
  run grep -c "disable --now acme-backup.timer" "$W/hosts/rehearsal/.systemctl.log"
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
  run grep -c "disable --now acme-backup.timer" "$W/hosts/rehearsal/.systemctl.log"
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

@test "first_deploy_failing_after_save_state_restores_and_names_the_fallback (S57, R12)" {
  commit_change first; build_ok "$SHA"
  local point
  for point in migrate smoke; do
    hook_exit "$point" 1
    : > "$HOOKLOG"
    run d deploy rehearsal "$SHA" --off-level first
    assert_failure 1
    assert_output --partial "Fallback: stop the deliver project"
    assert_regex "$(hook_calls | tr '\n' ' ')" "restore-state"
    assert_equal "$(host_state rehearsal rehearsal)" "failed, no previous deploy"
    [ ! -e "$(host_state_dir rehearsal rehearsal)/current" ]
    [ -z "$(running_digests_of rehearsal acme-rehearsal)" ]
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
}

@test "first_deploy_failing_before_save_state_changes_nothing (S57, R12)" {
  commit_change first; build_ok "$SHA"
  hook_exit pre-deploy 1
  local before; before="$(snapshot)"
  run d deploy rehearsal "$SHA" --off-level first
  assert_failure 1
  assert_equal "$(snapshot)" "$before"
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
