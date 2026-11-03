#!/usr/bin/env bats

# Review round 1 of the deliver tool: each finding has a test that fails without
# its fix. The number in each name is the finding's.

setup() {
  bats_load_library bats-support
  bats_load_library bats-assert
  load deliver_world
  world_new
}

# F1 --------------------------------------------------------------------------
@test "F1 the release copier makes the copies and pushes the record, on its own machine (S40, R33)" {
  ref_commit "a feature" 12
  release_ready "12|Requirement||0|"
  : > "$W/logs/where.log"
  run d release --expect 0.10.2
  assert_success
  # every registry write of the release ran on the copier, none on the control node
  [ -s "$W/logs/where.log" ]
  run grep -vc '^copy copier$' "$W/logs/where.log"
  assert_output 0
  assert_regex "$(cat "$W/logs/ssh.log")" "ssh copier: .*deliver-host copy acme"
  # and --unrecorded is the copier's copy too
  git -C "$W/work" pull -q --ff-only origin main
  commit_change two; build_ok "$SHA"
  : > "$W/logs/where.log"
  run d deploy production "$SHA" --unrecorded "record tooling down"
  assert_success
  [ -s "$W/logs/where.log" ]
  run grep -vc '^copy copier$' "$W/logs/where.log"
  assert_output 0
}

# F2 --------------------------------------------------------------------------
@test "F2 a host's prune keeps every environment's current and previous images (R14)" {
  printf '\n[environments.checks]\nrole = "test"\nssh = "rehearsal"\nlogin = "docker-config"\n' >> "$W/work/app-profile.toml"
  commit_change a; local A="$SHA"; build_ok "$A"
  run d deploy checks "$A"; assert_success
  commit_change b; local B="$SHA"; build_ok "$B"; deploy_rehearsal "$B"; assert_success
  commit_change c; local C="$SHA"; build_ok "$C"; deploy_rehearsal "$C"; assert_success
  commit_change d; local D="$SHA"; build_ok "$D"; deploy_rehearsal "$D"; assert_success
  local imgs="$W/hosts/rehearsal/.docker/images" h
  # A is held by `checks`, B by nobody now
  for h in $(cand "$A-server" "$A-web"); do [ -f "$imgs/${h#sha256:}.json" ]; done
  for h in $(cand "$B-server"); do [ ! -f "$imgs/${h#sha256:}.json" ]; done
  for h in $(cand "$C-server") $(cand "$D-server"); do [ -f "$imgs/${h#sha256:}.json" ]; done
}

# F3 --------------------------------------------------------------------------
@test "F3 a failed restore is a failure: the state stays interrupted and the next deploy refuses" {
  commit_change a; build_ok "$SHA"; local A="$SHA"; deploy_rehearsal "$A"; assert_success
  commit_change b; build_ok "$SHA"; local B="$SHA"
  hook_exit smoke 1; hook_exit restore-state 1
  run d deploy rehearsal "$B"
  assert_failure 1
  assert_output --partial "the restore failed"
  local st; st="$(host_state rehearsal rehearsal)"
  [ "$st" != finished ]; [ "$st" != restored ]
  assert_regex "$st" "^failed: the restore did not complete"
  hook_clear smoke; hook_clear restore-state
  commit_change c; build_ok "$SHA"
  run d deploy rehearsal "$SHA"
  assert_failure 1
  assert_output --partial "refused at gate state"
  assert_output --partial "deliver rollback"
  refute_output --partial "redeploy the previous version"
  # the rollback is the way out, and it works once the restore can
  run d rollback rehearsal
  assert_success
  assert_equal "$(host_state rehearsal rehearsal)" restored
}

@test "F3 the previous containers not coming back is a failure too" {
  commit_change a; build_ok "$SHA"; deploy_rehearsal "$SHA"; assert_success
  commit_change b; build_ok "$SHA"
  hook_exit smoke 1
  STUB_COMPOSE_UP_FAIL_ALL=1 run d deploy rehearsal "$SHA"
  assert_failure 1
  assert_regex "$(host_state rehearsal rehearsal)" "^failed: the restore did not complete"
  hook_clear smoke
  run d rollback rehearsal
  assert_success
  assert_equal "$(host_state rehearsal rehearsal)" restored
}

# F4 --------------------------------------------------------------------------
@test "F4 the gates read the commit's profile, not the working tree's" {
  ref_commit "a feature" 12
  release_ready "12|Requirement||0|"
  gh_checks "$RSHA" e2e=failure
  sed -i 's/^required_checks = .*/required_checks = []/' "$W/work/app-profile.toml"     # uncommitted
  run d release --check
  assert_failure 1
  assert_output --partial "refused at gate ci-passed"
  assert_output --partial "e2e is failure"
  git -C "$W/work" checkout -q app-profile.toml
}

# F5 --------------------------------------------------------------------------
@test "F5 a resumed release does not raise the retrospective issue again (S26)" {
  ref_commit "a feature" 12
  build_ok "$SHA"; gh_checks "$SHA" e2e=success; gh_milestone 0.10.2 "12|Requirement||0|"
  STUB_GH_FAIL=release run d release --expect 0.10.2 --commit "$SHA" --skip-rehearsal "host down"
  assert_failure 3
  run d release --expect 0.10.2 --commit "$SHA" --skip-rehearsal "host down"
  assert_success
  assert_equal "$(grep -c 'POST repos/acme/acme/issues title=Retrospective' "$W/gh/log")" 1
}

# F6 --------------------------------------------------------------------------
@test "F6 the payload's steps come from the programme the commit pins, and the record names it" {
  mkdir -p "$W/work/programme/scripts"
  cp -R "$DELIVER_SRC" "$W/work/programme/scripts/deliver"
  echo '# PINNED-MARKER' >> "$W/work/programme/scripts/deliver/payload/deploy"
  git -C "$W/work/programme" init -q -b main
  git -C "$W/work/programme" add -A && git -C "$W/work/programme" commit -q -m pinned
  local pinned; pinned="$(git -C "$W/work/programme" rev-parse HEAD)"
  ref_commit "a feature" 12
  release_ready "12|Requirement||0|"
  local payload="$W/registry/reg.test/ns/acme/candidates/payload/$(cand "$RSHA-server" | sed 's/^sha256://')"
  grep -q PINNED-MARKER "$payload/deploy"
  ! grep -q PINNED-MARKER "$DELIVER_SRC/payload/deploy"
  run d release --expect 0.10.2
  assert_success
  assert_equal "$(jq -r .tool.programme <<< "$(tag_record v0.10.2)")" "$pinned"
}

# F7 --------------------------------------------------------------------------
@test "F7 oci-instance-principal reads its settings from the host's .env over a bare ssh" {
  printf '#!/bin/sh\nexit 0\n' > "$W/bin/oci"; chmod +x "$W/bin/oci"
  printf 'the-token' > "$W/token"
  awk '/^\[environments.rehearsal\]/{r=1} r&&/^login = /{sub(/docker-config/,"oci-instance-principal"); r=0} {print}' "$W/work/app-profile.toml" > "$W/p.new" && mv "$W/p.new" "$W/work/app-profile.toml"
  printf 'DELIVER_OCI_TOKEN_CMD=cat %s\nDELIVER_REGISTRY_USER=tenancy/user\nOCI_CLI_AUTH=instance_principal\n' "$W/token" >> "$(host_state_dir rehearsal rehearsal)/.env"
  commit_change a; build_ok "$SHA"
  : > "$W/logs/login.log"
  deploy_rehearsal "$SHA"
  assert_success
  assert_regex "$(cat "$W/logs/login.log")" "login ok bytes=9"
  # without the lines the adapter says what it lacks
  sed -i '/^DELIVER_OCI_TOKEN_CMD=/d' "$(host_state_dir rehearsal rehearsal)/.env"
  commit_change b; build_ok "$SHA"
  run d deploy rehearsal "$SHA"
  assert_failure 1
  assert_output --partial "needs DELIVER_OCI_TOKEN_CMD"
}

# F8 --------------------------------------------------------------------------
@test "F8 --expect and --commit with no value refuse and do not loop" {
  cd "$W/work"
  run timeout 10 "$DELIVER" release --expect
  assert_failure 1
  assert_output --partial "--expect needs a version"
  run timeout 10 "$DELIVER" release --commit
  assert_failure 1
  assert_output --partial "--commit needs a commit"
}

# F11 -------------------------------------------------------------------------
@test "F11 a host file moved to a longer path is removed from the old one" {
  commit_change a; build_ok "$SHA"; deploy_rehearsal "$SHA"; assert_success
  [ -f "$W/hosts/rehearsal/opt/acme/backup.sh" ]
  sed -i 's|dest = "/opt/acme/backup.sh"|dest = "/srv/opt/acme/backup.sh"|' "$W/work/app-profile.toml"
  commit_change b; build_ok "$SHA"
  # the new destination is not on the host's root-owned allowlist until host-install is rerun
  run d deploy rehearsal "$SHA"
  assert_failure 1
  assert_output --partial "rerun deliver host-install"
  run d host-install rehearsal
  assert_success
  run d deploy rehearsal "$SHA"
  assert_success
  [ -f "$W/hosts/rehearsal/srv/opt/acme/backup.sh" ]
  [ ! -e "$W/hosts/rehearsal/opt/acme/backup.sh" ]
}

# F12 -------------------------------------------------------------------------
@test "F12 a registry failure reaches the screen and the log as a summary, never the registry's words or address" {
  commit_change a
  STUB_REGISTRY_DOWN=1 run d build "$SHA"
  assert_failure 1
  assert_output --partial "the registry could not be reached"
  refute_output --partial "dial tcp"
  refute_output --partial "reg.test"
  ref_commit "a feature" 12
  release_ready "12|Requirement||0|"
  STUB_WRITE_ONLY='/candidates$' run d release --expect 0.10.2
  assert_failure 1
  assert_output --partial "the registry refused access"
  refute_output --partial "requested access"
  refute_output --partial "reg.test"
  run grep -rl "reg.test\|dial tcp\|requested access" "$XDG_STATE_HOME/deliver/acme"
  [ "$status" -ne 0 ] || { echo "the run log holds: $output" >&2; false; }
}

# F13 -------------------------------------------------------------------------
@test "F13 one --wait budget covers the lock and the hook" {
  commit_change a; build_ok "$SHA"
  hook_exit pre-deploy 75
  lock_hold rehearsal rehearsal
  ( sleep 2.4; kill "$LOCK_PID" ) &
  run d deploy rehearsal "$SHA" --off-level first --wait=4
  assert_failure 1
  assert_output --partial "still not yet after waiting 4 minute(s)"
  # the minutes the lock took are the hook's too: it is asked 4 - used + 1 times
  local used; used="$(sed -n 's/^DELIVER_WAIT_USED=//p' "$HOOKLOG" | head -1)"
  [ "$used" -ge 1 ]
  assert_equal "$(grep -c '^== pre-deploy' "$HOOKLOG")" "$((5 - used))"
  hook_clear pre-deploy
}

# F14 -------------------------------------------------------------------------
@test "F14 a record pushed by an earlier run is the record the tag carries (O10)" {
  ref_commit "a feature" 12
  release_ready "12|Requirement||0|"
  printf '#!/bin/sh\necho "tags rejected" >&2\nwhile read -r old new ref; do case "$ref" in refs/tags/*) exit 1;; esac; done\n' > "$W/remote.git/hooks/pre-receive"
  chmod +x "$W/remote.git/hooks/pre-receive"
  run d release --expect 0.10.2
  assert_failure 1
  assert_output --partial "cannot push tag"
  [ -n "$(rel 0.10.2-record)" ]
  rm "$W/remote.git/hooks/pre-receive"
  rm -f "$XDG_STATE_HOME/deliver/acme/release-0.10.2.json"
  sleep 1.2
  run d release --expect 0.10.2
  assert_success
  assert_equal "$(tag_record v0.10.2)" "$(registry_record 0.10.2)"
}

# F15 -------------------------------------------------------------------------
@test "F15 a release with rehearsal skipped does not describe another commit's rehearsal" {
  commit_change a; build_ok "$SHA"; deploy_rehearsal "$SHA"; assert_success
  ref_commit "a feature" 12
  build_ok "$SHA"; gh_checks "$SHA" e2e=success; gh_milestone 0.10.2 "12|Requirement||0|"
  run d release --expect 0.10.2 --commit "$SHA" --skip-rehearsal "rehearsal host down"
  assert_success
  assert_equal "$(jq -c .rehearsal <<< "$(tag_record v0.10.2)")" '{"environment":"rehearsal","deployed":null,"smoke":null}'
}

# F16 -------------------------------------------------------------------------
@test "F16 old deploy folders are pruned, keeping the current and the previous" {
  local i
  for i in a b c d; do commit_change $i; build_ok "$SHA"; deploy_rehearsal "$SHA"; assert_success; done
  local dirs; dirs="$(ls "$(host_state_dir rehearsal rehearsal)/deploys" | sort | tr '\n' ' ')"
  assert_equal "$dirs" "3 4 "
  assert_equal "$(host_current rehearsal rehearsal)" 4
  assert_equal "$(host_previous rehearsal rehearsal)" 3
}

# sudo rule -------------------------------------------------------------------
@test "root-ops trusts only what root wrote: forged files under the state folder change nothing" {
  commit_change a; build_ok "$SHA"; deploy_rehearsal "$SHA"; assert_success
  local root="$W/hosts/rehearsal" st="$W/hosts/rehearsal/var/lib/deliver/acme/rehearsal"
  local src="$st/deploys/1/payload/host_files/ops/backup.sh"
  # the real allowlist permits the real destination, and root-ops records it in its own file
  run env DELIVER_HOST_ROOT="$root" "$DELIVER_HOST" root-ops install "$src" /opt/acme/backup.sh 0755
  assert_success
  grep -qx /opt/acme/backup.sh "$root/etc/deliver/acme/installed"
  [ "$(stat -c %a "$root/etc/deliver/acme")" = 755 ]
  # attack 1: a hand-written profile.json in the payload names a destination of its own
  jq '.deliver.host_files += [{src:"ops/backup.sh",dest:"/etc/sudoers.d/x",mode:"0440"}]' "$st/deploys/1/payload/profile.json" > "$W/pj" && cp "$W/pj" "$st/deploys/1/payload/profile.json"
  run env DELIVER_HOST_ROOT="$root" "$DELIVER_HOST" root-ops install "$src" /etc/sudoers.d/x 0440
  assert_failure 1
  assert_output --partial "not on the host's allowlist"
  [ ! -e "$root/etc/sudoers.d/x" ]
  # attack 2: a hand-written installed list in the state folder names a file that is not ours
  mkdir -p "$root/etc"; echo secret > "$root/etc/shadow"
  printf '/etc/shadow\t\n' > "$st/host_files.installed"; printf '/etc/shadow\n' > "$st/installed"
  run env DELIVER_HOST_ROOT="$root" "$DELIVER_HOST" root-ops rm /etc/shadow
  assert_failure 1
  assert_output --partial "not a file root-ops installed"
  [ -f "$root/etc/shadow" ]
  # attack 3: a hand-written prefix in the state folder makes any user "ours"
  printf '\n' > /dev/null; printf 'ro\n' > "$st/ephemeral.prefix"; printf 'ro\n' > "$root/var/lib/deliver/acme/ephemeral.prefix"
  run env DELIVER_HOST_ROOT="$root" "$DELIVER_HOST" root-ops userdel root
  assert_failure 1
  assert_output --partial "ephemeral user_prefix"
  # what it installed it may remove, and then it forgets it
  run env DELIVER_HOST_ROOT="$root" "$DELIVER_HOST" root-ops rm /opt/acme/backup.sh
  assert_success
  ! grep -qx /opt/acme/backup.sh "$root/etc/deliver/acme/installed"
}

@test "an ephemeral environment's user is created and removed only under the installed prefix" {
  mkdir -p "$W/payload"; cp -a "$W/work/deliver/hooks" "$W/payload/hooks"
  export DELIVER_PROFILE="$W/work/app-profile.toml" DELIVER_PAYLOAD="$W/payload"
  run bash -c "printf 's\n' | '$DELIVER' env create e9"
  assert_success
  run "$DELIVER" env destroy e9
  assert_success
  assert_equal "$(cat "$W/hosts/local/.users")" ""
  rm -rf "$W/hosts/local/etc/deliver"
  run bash -c "printf 's\n' | '$DELIVER' env create e8"
  assert_failure 1
  assert_output --partial "ephemeral user_prefix"
}

# round 2 ---------------------------------------------------------------------
@test "R2-2 a retrospective issue on a later page of the listing is found, and a pull request is not one" {
  ref_commit "a feature" 12
  build_ok "$SHA"; gh_checks "$SHA" e2e=success; gh_milestone 0.10.2 "12|Requirement||0|"
  local title="Retrospective: 0.10.2 released with rehearsal skipped"
  gh_fixture repos_acme_acme_issues "[{\"title\":\"$title\",\"pull_request\":{}}]"
  run d release --expect 0.10.2 --commit "$SHA" --skip-rehearsal "host down"
  assert_success
  assert_equal "$(grep -c 'POST repos/acme/acme/issues title=Retrospective' "$W/gh/log")" 1
  # another release: the issue is on page 2
  git -C "$W/work" pull -q --ff-only origin main
  ref_commit two 12; build_ok "$SHA"; gh_checks "$SHA" e2e=success; gh_milestone 0.10.3 "12|Requirement||0|"
  rm -f "$W/gh/state/issues-new"
  gh_fixture repos_acme_acme_issues '[{"title":"filler"}]'
  gh_fixture repos_acme_acme_issues_page2 '[{"title":"Retrospective: 0.10.3 released with rehearsal skipped"}]'
  : > "$W/gh/log"
  run d release --expect 0.10.3 --commit "$SHA" --skip-rehearsal "host down"
  assert_success
  assert_equal "$(grep -c 'POST repos/acme/acme/issues title=Retrospective' "$W/gh/log")" 0
}

@test "R2-3 a commit that is not in this repository is refused, not read from the working tree" {
  run d deploy rehearsal aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa --off-level first
  assert_failure 1
  assert_output --partial "is not in this repository"
  assert_output --partial "git fetch"
}

@test "R2-4 host-install takes the release copier, which gets the command and its libraries but no sudo rule" {
  run d host-install copier
  assert_success
  local root="$W/hosts/copier"
  [ -x "$root/usr/local/bin/deliver-host" ]
  [ -f "$root/usr/local/lib/deliver/registry.sh" ]
  [ ! -e "$root/etc/sudoers.d/deliver-host" ]
  [ ! -e "$root/etc/deliver" ]
  run d host-install nowhere
  assert_failure 1
  assert_output --partial "not the release copier"
}
