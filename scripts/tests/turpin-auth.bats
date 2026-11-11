#!/usr/bin/env bats

# One registry login per component: a skopeo auth file of its own for the
# controller, builder and copier, the machine user's docker login for the
# builder's push and the deployers' pulls; DOCKER_CONFIG never changed (design §3;
# test-design.md R44 to R47, S65 to S70, X23). The stub registry enforces who is
# asking: STUB_AUTH_ENFORCE is on in every world, and the token of a login is the
# role it was made for.

setup() {
  bats_load_library bats-support
  bats_load_library bats-assert
  load turpin_world
  world_new
  AUTH="$HOME/.config/turpin/auth/acme"
}

# an old, unreferenced candidate A, and a release r made after it
prunable_world() {
  commit_change old-unreferenced; build_ok "$SHA"; PA="$SHA"
  commit_change released; build_ok "$SHA"; PR="$SHA"
  local rec; rec="$(jq -nc --arg c "$PR" --arg s "$(cand "$PR-server")" --arg w "$(cand "$PR-web")" \
    '{record:1,application:"acme",version:"0.9.0",commit:$c,images:{server:$s,web:$w},made:"2026-06-01T00:00:00Z"}')"
  printf '%s\n' "$rec" > "$W/rec.json"
  git -C "$W/work" tag -a -F "$W/rec.json" v0.9.0 "$PR" && git -C "$W/work" push -q origin refs/tags/v0.9.0
  local c="$W/registry/reg.test/ns/acme/candidates" sha img d
  for sha in "$PA" "$PR"; do
    for img in server web; do
      d="$(cat "$c/tags/$sha-$img")"
      jq -c '.Labels["org.opencontainers.image.created"] = "2026-05-01T00:00:00Z"' "$c/meta/${d#sha256:}.json" > "$c/meta/new.json"
      mv "$c/meta/new.json" "$c/meta/${d#sha256:}.json"
    done
  done
}

# the roles that made calls of a tool and operation, one per line
roles_of() { awk -v t="$1" -v o="$2" '$1 == t && $2 == o {print $4}' "$W/logs/auth.log" | sort -u | tr '\n' ' '; }

@test "each component uses its own login: builder pushes, copier writes releases, controller reads, host pulls; DOCKER_CONFIG is never set (R44, S65)" {
  ref_commit "a feature" 12
  : > "$W/logs/auth.log"
  release_ready "12|Requirement||0|"
  run d release --expect 0.10.2; assert_success
  run d deploy production 0.10.2; assert_success
  assert_equal "$(roles_of docker push)" "builder "
  assert_equal "$(roles_of skopeo copy-to)" "copier "
  assert_equal "$(roles_of skopeo push-record)" "copier "
  assert_equal "$(roles_of docker pull)" "host "
  # nothing asked the registry without a login, and the controller read for itself
  run grep -c ' none$' "$W/logs/auth.log"; assert_output 0
  [ "$(wc -l < "$W/logs/docker-config.log")" -gt 0 ]
  run grep -c . "$W/logs/docker-config.log"; assert_output 0
  run grep -E '^skopeo (inspect|list-tags) .* controller$' "$W/logs/auth.log"; assert_success
}

@test "the copier's login is not replaced by the builder's, however they are made (R44, S66)" {
  rm -rf "$HOME/.config/turpin/auth"
  run bash -c "cd '$W/work'; printf 'tle-releaser\ntok-copier\n' | '$TURPIN' login copier"
  assert_success
  run bash -c "cd '$W/work'; printf 'tle-builder\ntok-builder\n' | '$TURPIN' login builder"
  assert_success
  run bash -c "cd '$W/work'; printf 'tle-controller\ntok-controller\n' | '$TURPIN' login controller"
  assert_success
  assert_equal "$(jq -r '.auths[].user' "$AUTH/copier.json")" tle-releaser
  assert_equal "$(jq -r '.auths[].user' "$AUTH/builder.json")" tle-builder
  assert_equal "$(jq -r '.auths[].user' "$AUTH/controller.json")" tle-controller
  # three skopeo files; the one docker login is the builder's, the machine user's own, in no directory the tool chose
  assert_equal "$(grep -c '^skopeo ' "$W/logs/login-dirs.log")" 3
  assert_equal "$(grep '^skopeo ' "$W/logs/login-dirs.log" | awk '{print $3}' | sort -u | wc -l)" 3
  assert_equal "$(grep -c '^docker ' "$W/logs/login-dirs.log")" 1
  run grep 'DOCKER_CONFIG=.' "$W/logs/login-dirs.log"; assert_failure
  assert_equal "$(jq -r .user "$W/hosts/local/.docker/login.json")" tle-builder
  # and the whole route works with them
  ref_commit "a feature" 12
  release_ready "12|Requirement||0|"
  run d release --expect 0.10.2; assert_success
}

@test "the controller's reads use the controller's login, and refuse without one (R45, S67)" {
  ref_commit "a feature" 12
  release_ready "12|Requirement||0|"
  mv "$AUTH/controller.json" "$AUTH/controller.away"
  run d release --expect 0.10.2
  assert_failure 1
  assert_output --partial "no registry login for the controller"
  assert_output --partial "turpin login controller"
  [ -z "$(git -C "$W/remote.git" tag -l v0.10.2)" ]
  mv "$AUTH/controller.away" "$AUTH/controller.json"
  # a login made for another role does not read for it: releases are the copier's and the hosts'
  seed_login "$AUTH/controller.json" builder
  run d release --expect 0.10.2
  assert_failure 1
  seed_login "$AUTH/controller.json" controller
  run d release --expect 0.10.2; assert_success
}

@test "prune's deletion runs on the builder with the builder's login; the controller only reads (R46, S68)" {
  prunable_world
  : > "$W/logs/auth.log"; : > "$W/logs/where.log"; : > "$W/logs/ssh.log"
  # the builder is another machine
  sed -i '/^\[turpin.build\]/,/^login/ s/^on = .*/on = "rehearsal"/' "$W/work/app-profile.toml"
  run d prune
  assert_success
  assert_output --partial "removed $PA-server"
  [ -z "$(cand "$PA-server")" ] && [ -z "$(cand "$PA-web")" ]
  [ -n "$(cand "$PR-server")" ]
  assert_equal "$(roles_of skopeo delete)" "builder "
  run cat "$W/logs/where.log"; assert_output --partial "delete rehearsal"
  refute_output --partial "delete local"
  run grep -c 'turpin-host delete' "$W/logs/ssh.log"; assert_output 1
  # the controller's own calls were reads
  run grep -E '^skopeo (inspect|list-tags) .* controller$' "$W/logs/auth.log"; assert_success
  run grep -E '^skopeo delete .* controller$' "$W/logs/auth.log"; assert_failure
}

@test "prune on the controller's own machine still deletes with the builder's login, not the controller's (R46, S68)" {
  prunable_world
  : > "$W/logs/auth.log"
  run d prune; assert_success
  [ -z "$(cand "$PA-server")" ]
  assert_equal "$(roles_of skopeo delete)" "builder "
}

@test "prune --dry-run sends nothing to the builder and deletes nothing (R46, S69)" {
  prunable_world
  : > "$W/logs/auth.log"; : > "$W/logs/where.log"; : > "$W/logs/ssh.log"
  local before; before="$(snapshot)"
  run d prune --dry-run
  assert_success
  assert_output --partial "would remove $PA-server"
  assert_equal "$(snapshot)" "$before"
  run grep -c delete "$W/logs/where.log"; assert_output 0
  run grep -c 'delete' "$W/logs/auth.log"; assert_output 0
}

@test "the builder deletes a candidate only while it still has the digest the controller chose (R46, S69)" {
  prunable_world
  local d; d="$(cand "$PA-server")"
  local req
  req="$(jq -nc --arg d "sha256:$(printf 'other' | sha256sum | cut -d' ' -f1)" '{login:"docker-config",candidates:"acme/candidates",deletes:[{tag:"'"$PA"'-server",digest:$d}]}')"
  run bash -c "printf '%s' '$req' | '$TURPIN_HOST' delete acme"
  assert_failure
  assert_output --partial "no longer points at the digest"
  assert_equal "$(cand "$PA-server")" "$d"
  req="$(jq -nc --arg d "$d" '{login:"docker-config",candidates:"acme/candidates",deletes:[{tag:"'"$PA"'-server",digest:$d},{tag:"gone-tag",digest:$d}]}')"
  run bash -c "printf '%s' '$req' | '$TURPIN_HOST' delete acme"
  assert_success
  [ -z "$(cand "$PA-server")" ]
}

@test "the controller's login cannot delete: the registry refuses a delete made with it (R46, S68)" {
  prunable_world
  run bash -c "export REGISTRY_AUTH_FILE='$AUTH/controller.json'; skopeo delete docker://reg.test/ns/acme/candidates:$PA-server"
  assert_failure
  [ -n "$(cand "$PA-server")" ]
}

@test "turpin login reads the token at a hidden prompt and never prints, logs or passes it as an argument (R47, S70, X23)" {
  rm -rf "$HOME/.config/turpin/auth"
  local canary="hunter2-canary-token"
  run bash -c "cd '$W/work'; printf 'tle-builder\n%s\n' '$canary' | '$TURPIN' login builder 2>&1"
  assert_success
  refute_output --partial "$canary"
  assert_output --partial "logged in: builder"
  # both tools saw the token on standard input only: its length, never its text
  run grep -c "login ok bytes=${#canary}" "$W/logs/login.log"; assert_output 2
  run grep -c "^docker " "$W/logs/login-dirs.log"; assert_output 1
  run grep -rl "$canary" "$W"
  assert_failure
  assert_equal "$(stat -c %a "$AUTH")" 700
  assert_equal "$(stat -c %a "$AUTH/builder.json")" 600
  # an empty token is refused
  run bash -c "cd '$W/work'; printf 'tle-releaser\n\n' | '$TURPIN' login copier 2>&1"
  assert_failure 1
  [ ! -f "$AUTH/copier.json" ]
  # preview is on the builder's machine, so it shares the builder's docker login: it is not made twice
  run bash -c "cd '$W/work'; printf 'tle-prev\n%s\n' '$canary' | '$TURPIN' login preview 2>&1"
  assert_failure 1
  assert_output --partial "preview shares the builder's docker login on this machine: run turpin login builder"
  assert_equal "$(jq -r .user "$W/hosts/local/.docker/login.json")" tle-builder
  run grep -rl "$canary" "$W"
  assert_failure
}

@test "turpin login reaches a builder or a deployer on another machine over ssh, the token on standard input only (R47, S70)" {
  rm -f "$HOME/.config/turpin/auth/acme/builder.json"
  # the remote machine has a home of its own, with its own local configuration
  mkdir -p "$W/hosts/rehearsal/home/.config/turpin"
  cp "$HOME/.config/turpin/acme.env" "$W/hosts/rehearsal/home/.config/turpin/"
  sed -i '/^\[turpin.build\]/,/^login/ s/^on = .*/on = "rehearsal"/' "$W/work/app-profile.toml"
  local canary="hunter2-canary-token"
  : > "$W/logs/ssh.log"
  run bash -c "cd '$W/work'; printf 'tle-builder\n%s\n' '$canary' | '$TURPIN' login builder 2>&1"
  assert_success
  assert_equal "$(jq -r .user "$W/hosts/rehearsal/.docker/login.json")" tle-builder
  [ -f "$W/hosts/rehearsal/home/.config/turpin/auth/acme/builder.json" ]
  [ ! -e "$AUTH/builder.json" ]
  run bash -c "cd '$W/work'; printf 'host-user\n%s\n' '$canary' | '$TURPIN' login production 2>&1"
  assert_success
  assert_equal "$(jq -r .user "$W/hosts/prod/.docker/login.json")" host-user
  run grep -c "turpin-host login" "$W/logs/ssh.log"; assert_output 2
  run grep -c "$canary" "$W/logs/ssh.log"; assert_output 0
}

@test "an unknown component is refused by turpin login (R47)" {
  run bash -c "cd '$W/work'; printf 'u\nt\n' | '$TURPIN' login nonsense 2>&1"
  assert_failure 1
  assert_output --partial "nonsense is not controller, builder, copier"
}

@test "a docker-config login is checked before use: none made names turpin login (R44, S66)" {
  rm -f "$AUTH/builder.json"
  commit_change one
  run d build "$SHA"
  assert_failure 1
  assert_output --partial "the builder's registry login (docker-config) failed"
  assert_output --partial "turpin login builder"
}

@test "a revoked login is told apart and named: the registry refuses the copier, and the message says turpin login copier (R44, S66)" {
  ref_commit "a feature" 12
  release_ready "12|Requirement||0|"
  seed_login "$AUTH/copier.json" builder
  run d release --expect 0.10.2
  assert_failure 1
  assert_output --partial "the registry refused access"
  assert_output --partial "turpin login copier"
  [ -z "$(git -C "$W/remote.git" tag -l v0.10.2)" ]
}

@test "a local preview build and deploy need no controller login (R45, S67)" {
  rm -f "$AUTH/controller.json"
  commit_change one
  run d build "$SHA" --local; assert_success
  run d deploy preview "$SHA"; assert_success
  assert_equal "$(host_state local preview)" finished
}

@test "a refused pull on the builder's machine names turpin login builder, on another machine the environment (R44, S66)" {
  commit_change one; build_ok "$SHA"
  rm -f "$W/hosts/local/.docker/login.json"
  run d deploy preview "$SHA"
  assert_failure 1
  assert_output --partial "turpin login builder"
  rm -f "$W/hosts/rehearsal/.docker/login.json"
  run d deploy rehearsal "$SHA" --off-level first
  assert_failure 1
  assert_output --partial "turpin login rehearsal"
}
