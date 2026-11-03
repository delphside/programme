#!/usr/bin/env bats

# Run logs, access, secrets, environments, host-install, prune, and the tool's
# independence of any application (test-design.md S32, S40 to S47; rules R1, R2,
# R4, R31, R33, R34, R36 to R38, R40, R41).

setup() {
  bats_load_library bats-support
  bats_load_library bats-assert
  load deliver_world
  world_new
}

@test "every_run_log_names_each_gate_it_ran (S32, R31)" {
  ref_commit "a feature" 12
  commit_change one
  run d build "$SHA"; assert_success
  assert_equal "$(run_log_gates build)" "build-commit build-labels store-immutable store-query "
  run d deploy rehearsal "$SHA" --off-level first; assert_success
  local gates; gates="$(run_log_gates deploy)"
  for g in ref rehearsal-level lock state digests hooks-present pre-deploy smoke; do
    assert_regex "$gates" "(^| )$g( |$)"
  done
  gh_checks "$SHA" e2e=success; gh_milestone 0.10.2
  # a refusal is in the log too
  hook_exit release-check 1
  run d release --expect 0.10.2
  assert_failure 1
  run jq -r 'select(.event=="gate" and .result=="refused") | .name' "$(run_log_latest release)"
  assert_output "release-check"
  hook_clear release-check
  run d release --expect 0.10.2; assert_success
  gates="$(run_log_gates release)"
  for g in rehearsal-passed on-main emergency-descent ci-passed version-spent-once milestone release-check; do
    assert_regex "$gates" "(^| )$g( |$)"
  done
  # the exit is in the log, and so are the arguments
  run jq -r 'select(.event=="exit") | .code' "$(run_log_latest release)"
  assert_output 0
}

@test "only_the_release_copier_can_write_releases (S40, R33, R4)" {
  ref_commit "a feature" 12
  release_ready "12|Requirement||0|"
  # the build environment's credential writes candidates only
  STUB_WRITE_ONLY='/candidates$' run d release --expect 0.10.2
  assert_failure 1
  assert_output --partial "the copy to releases failed"
  [ -z "$(git -C "$W/remote.git" tag -l v0.10.2)" ]
  [ -z "$(rel 0.10.2-server)" ]
  # the copier's credential writes releases only
  commit_change two
  STUB_WRITE_ONLY='/releases$' run d build "$SHA"
  assert_failure 1
  [ -z "$(cand "$SHA-server")" ]
  STUB_WRITE_ONLY='/releases$' run d release --expect 0.10.2
  assert_success
  assert_equal "$(rel 0.10.2-server)" "$(cand "$RSHA-server")"
}

@test "no_secret_reaches_a_log_record_tag_or_screen (S44, R34)" {
  local canary="hunter2-canary"
  export DELIVER_REGISTRY_TOKEN="$canary"
  ref_commit "a feature" 12
  release_ready "12|Requirement||0|"
  run d release --expect 0.10.2
  assert_success
  local all="$output"
  run d deploy production 0.10.2
  assert_success
  all+="$output"
  run d status rehearsal; all+="$output"
  run d list rehearsal; all+="$output"
  # the host's .env holds the canary; nothing that is not .env may
  refute_regex "$all" "$canary"
  run grep -rl "$canary" "$W" --exclude=.env
  [ "$status" -eq 1 ]
  [ -z "$(git -C "$W/remote.git" tag -l -n99 | grep "$canary")" ]
}

@test "env_create_and_destroy_leave_nothing_behind; the secret is read at a hidden prompt (S41, R37, R34)" {
  mkdir -p "$W/payload"; cp -a "$W/work/deliver/hooks" "$W/payload/hooks"
  export DELIVER_PROFILE="$W/work/app-profile.toml" DELIVER_PAYLOAD="$W/payload"
  run bash -c "printf 's3cret-canary\n' | '$DELIVER' env create e3"
  assert_success
  refute_regex "$output" "s3cret-canary"
  local envdir="$W/hosts/local/var/lib/deliver/acme/e3"
  [ -d "$envdir" ]
  assert_equal "$(stat -c %a "$envdir/.env")" 600
  run cat "$envdir/.env"
  assert_output --partial "COMPOSE_PROJECT_NAME=acme-e3"
  assert_output --partial "ACME_SECRET=s3cret-canary"
  assert_equal "$(cat "$W/hosts/local/.users")" "acme-e3"
  [ -d "$W/hosts/local/srv/acme/e3" ]
  run hook_calls
  assert_output "env-create"
  run grep -rl "s3cret-canary" "$W" --exclude=.env
  [ "$status" -eq 1 ]
  run "$DELIVER" env destroy e3
  assert_success
  [ ! -e "$envdir" ]
  assert_equal "$(cat "$W/hosts/local/.users")" ""
  run hook_calls
  assert_output "env-create
env-destroy"
}

@test "host_install_installs_dependencies_and_sudo_rule (S42, R38)" {
  run d host-install rehearsal
  assert_success
  local root="$W/hosts/rehearsal"
  [ -x "$root/usr/local/bin/deliver-host" ]
  cmp "$root/usr/local/bin/deliver-host" "$DELIVER_SRC/deliver-host"
  cmp "$root/usr/local/lib/deliver/common.sh" "$DELIVER_SRC/lib/common.sh"
  [ -f "$root/usr/local/lib/deliver/toml.awk" ]
  run cat "$root/etc/sudoers.d/deliver-host"
  assert_output --regexp '^[a-z0-9_-]+ ALL=\(root\) NOPASSWD: /usr/local/bin/deliver-host root-ops \*$'
  assert_equal "$(stat -c %a "$root/etc/sudoers.d/deliver-host")" 440
  # again: an update, not a failure
  echo '# changed' >> "$root/usr/local/lib/deliver/common.sh"
  run d host-install rehearsal
  assert_success
  cmp "$root/usr/local/lib/deliver/common.sh" "$DELIVER_SRC/lib/common.sh"
}

@test "host_install refuses a host missing a tool the login adapter needs (S42, R38, R39)" {
  sed -i 's/^login = "docker-config"\npull_timeout/&/' "$W/work/app-profile.toml"
  awk '/^\[environments.rehearsal\]/{f=1} f&&/^login = /{sub(/docker-config/,"oci-instance-principal"); f=0} {print}' "$W/work/app-profile.toml" > "$W/p.toml"
  mv "$W/p.toml" "$W/work/app-profile.toml"
  mkdir -p "$W/nobin"
  # oci is not on PATH of the stub host
  run d host-install rehearsal
  assert_failure
  assert_output --partial "oci is missing (needed by the oci-instance-principal login)"
}

@test "login adapters: the three are named, and an unknown one is refused (R39)" {
  run bash -c ". '$DELIVER_SRC/lib/common.sh'; . '$DELIVER_SRC/lib/registry.sh'; login_adapters"
  assert_output "docker-config
oci-api-key
oci-instance-principal"
  run bash -c ". '$DELIVER_SRC/lib/common.sh'; . '$DELIVER_SRC/lib/registry.sh'; login_run nonsense; echo \$REG_ERR"
  assert_output --partial "unknown login adapter nonsense"
}

@test "oci-api-key refuses without a key and succeeds with one (R39, X14 shape)" {
  run bash -c ". '$DELIVER_SRC/lib/common.sh'; . '$DELIVER_SRC/lib/registry.sh'; printf '#!/bin/sh\n' > '$W/bin/oci'; chmod +x '$W/bin/oci'; printf '#!/bin/sh\ncat >/dev/null\n' > '$W/bin/docker-login-sink'
    export DELIVER_OCI_TOKEN_CMD='echo tok' DELIVER_REGISTRY_USER=u DELIVER_REGISTRY=reg.test/ns HOME='$W/nohome'
    login_run oci-api-key; echo \"rc=\$? \$REG_ERR\""
  assert_output --partial "needs an API key"
}

@test "prune_keeps_releases_and_deployed_candidates (S43, R36)" {
  commit_change old-unreferenced; build_ok "$SHA"; local a="$SHA"
  commit_change old-deployed; build_ok "$SHA"; local b="$SHA"
  commit_change released; build_ok "$SHA"; local r="$SHA"
  commit_change newer; build_ok "$SHA"; local n="$SHA"
  commit_change dated-after-but-pushed-before; build_ok "$SHA"; local late="$SHA"
  run d deploy rehearsal "$b" --off-level first; assert_success
  # a release made at 2026-06-01, of r
  local rec; rec="$(jq -nc --arg c "$r" --arg s "$(cand "$r-server")" --arg w "$(cand "$r-web")" \
    '{record:1,application:"acme",version:"0.9.0",commit:$c,images:{server:$s,web:$w},made:"2026-06-01T00:00:00Z"}')"
  printf '%s\n' "$rec" > "$W/rec.json"
  git -C "$W/work" tag -a -F "$W/rec.json" v0.9.0 "$r" && git -C "$W/work" push -q origin refs/tags/v0.9.0
  # push times: a, b, r and late before the release; n after it
  local c="$W/registry/reg.test/ns/acme/candidates" img sha d
  for sha in "$a" "$b" "$r" "$late" "$n"; do
    for img in server web; do
      d="$(cat "$c/tags/$sha-$img")"
      local when="2026-05-01T00:00:00Z"; [[ "$sha" == "$n" ]] && when="2026-07-01T00:00:00Z"
      jq -c --arg w "$when" '.Labels["org.opencontainers.image.created"] = $w' "$c/meta/${d#sha256:}.json" > "$c/meta/new.json"
      mv "$c/meta/new.json" "$c/meta/${d#sha256:}.json"
    done
  done
  run d prune
  assert_success
  assert_output --partial "removed $a-server"
  assert_output --partial "removed $late-web"
  [ -z "$(cand "$a-server")" ] && [ -z "$(cand "$late-web")" ]
  # kept: deployed (b), released (r), pushed after the release (n); releases are never touched
  [ -n "$(cand "$b-server")" ] && [ -n "$(cand "$r-server")" ] && [ -n "$(cand "$n-server")" ]
}

@test "tool_names_no_application (S45, R1)" {
  run grep -rniE 'tile[ -]?lite|dark[ -]?portal|oracle|ocid|oci\.oraclecloud|tenancy-' "$DELIVER_SRC"
  assert_failure 1
}

@test "registry_address_never_comes_from_the_profile (S45, R2)" {
  rm "$HOME/.config/deliver/acme.env"
  sed -i 's|^candidates = .*|&\nregistry = "reg.test/ns"|' "$W/work/app-profile.toml"
  commit_change one
  run d build "$SHA"
  assert_failure 1
  assert_output --partial "DELIVER_REGISTRY is not set"
  assert_output --partial "the profile never holds it"
}

@test "a second dummy application drives build, deploy and release (S45, R1)" {
  # another application: other names, other images, other registry repositories
  sed -i '/^src = /!s/acme/widget/g; s/"server", "web"/"api", "ui"/; s/payload_image = "server"/payload_image = "api"/' "$W/work/app-profile.toml"
  mv "$HOME/.config/deliver/acme.env" "$HOME/.config/deliver/widget.env"
  local h
  for h in rehearsal prod local; do mv "$W/hosts/$h/var/lib/deliver/acme" "$W/hosts/$h/var/lib/deliver/widget"; done
  export DELIVER_GH_REPO=widget/widget
  ref_commit "a feature" 12
  run d build "$SHA"
  assert_success
  assert_line --regexp '^api sha256:'
  assert_line --regexp '^ui sha256:'
  [ -f "$W/registry/reg.test/ns/widget/candidates/tags/$SHA-api" ]
  run d deploy rehearsal "$SHA" --off-level first
  assert_success
  [ -L "$W/hosts/rehearsal/var/lib/deliver/widget/rehearsal/current" ]
  gh_fixture "repos_widget_widget_commits_${SHA}_check-runs" '{"check_runs":[{"name":"e2e","conclusion":"success"}]}'
  jq -nc '{data:{repository:{milestones:{nodes:[{number:7,title:"0.10.2",state:"OPEN",issues:{nodes:[
    {number:12,issueType:{name:"Requirement"},parent:null,subIssues:{totalCount:0},projectItems:{nodes:[]}}]}}]}}}}' > "$W/gh/fix/graphql_MilestoneItems.json"
  run d release --expect 0.10.2
  assert_success
  [ -f "$W/registry/reg.test/ns/widget/releases/tags/0.10.2-api" ]
}

@test "board_reads_v_tags_as_released_and_prod_tags_as_history (S47, R41)" {
  local repo="$W/boardrepo"
  git init -q -b main "$repo"
  git -C "$repo" commit -q --allow-empty -m one
  git -C "$repo" tag prod-0.10.0
  git -C "$repo" commit -q --allow-empty -m two
  git -C "$repo" tag -a -m "Release 0.10.2" v0.10.2
  cat > "$W/board-profile.toml" <<'EOF'
application = "acme"
[release]
tag_prefix = "v"
history_prefixes = ["prod-"]
announcement = "Released in v"
EOF
  run bash -c "cd '$repo' && PROGRAMME_PROFILE='$W/board-profile.toml' python3 -I -c '
import sys; sys.path.insert(0, \"$BATS_TEST_DIRNAME/..\")
from board import repo
print(repo.release_tags(), repo.history_tags(), sorted(repo.Commits().shipped_milestones()), repo.commits().last_tag)
' 2>&1"
  assert_success
  assert_output "['v0.10.2'] ['prod-0.10.0'] ['0.10.0', '0.10.2'] v0.10.2"
}
