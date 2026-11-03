#!/usr/bin/env bats

# `deliver build` (delphside/programme#117; test-design.md S1 to S5, R3, R4).
# The world is deliver_world.bash's: a dummy application, a directory registry
# behind a skopeo stub and a docker stub, a bare remote.

setup() {
  bats_load_library bats-support
  bats_load_library bats-assert
  load deliver_world
  world_new
}

@test "build_refuses_a_commit_not_on_the_remote (S1)" {
  printf 'local only\n' > "$W/work/src.txt"
  git -C "$W/work" commit -qam "unpushed"
  local before; before="$(snapshot)"
  run d build HEAD
  assert_failure 1
  assert_output --partial "build-commit"
  assert_output --partial "not a commit on the remote"
  assert_equal "$(snapshot)" "$before"
  git -C "$W/work" push -q origin main
  run d build HEAD
  assert_success
}

@test "build_pushes_each_image_as_sha_dash_image, labelled with revision and version (S1, R3)" {
  commit_change one
  run d build "$SHA"
  assert_success
  local server web
  server="$(cand "$SHA-server")"; web="$(cand "$SHA-web")"
  [ -n "$server" ] && [ -n "$web" ]
  assert_line "server $server"
  assert_line "web $web"
  run reg_meta acme/candidates "$server"
  assert_output --partial "\"org.opencontainers.image.revision\":\"$SHA\""
  assert_output --partial '"org.opencontainers.image.version":"0.10.2"'
  assert_output --partial "\"Digest\":\"$server\""
}

@test "build_never_pushes_over_an_image_already_stored (S1, R4)" {
  commit_change one
  run d build "$SHA"; assert_success
  local before_digests before_bakes
  before_digests="$(digests_of "$SHA")"; before_bakes="$(bake_count)"
  run d build "$SHA"
  assert_success
  assert_equal "$(bake_count)" "$before_bakes"
  assert_equal "$(digests_of "$SHA")" "$before_digests"
  assert_output --partial "$(cand "$SHA-server")"
}

@test "build_ignores_the_operators_dirty_tree (S2, R3)" {
  commit_change one
  printf 'uncommitted rubbish\n' > "$W/work/src.txt"
  printf 'new file\n' > "$W/work/untracked.txt"
  run d build "$SHA"
  assert_success
  assert_equal "$(cand "$SHA-server")" "$(expected_digest "$SHA" server)"
  assert_equal "$(cand "$SHA-web")" "$(expected_digest "$SHA" web)"
}

@test "build_refuses_when_the_registry_cannot_be_queried; a present image is kept and a missing one built (S3, R4)" {
  commit_change one
  run d build "$SHA"; assert_success
  local server_before; server_before="$(cand "$SHA-server")"
  rm "$W/registry/reg.test/ns/acme/candidates/tags/$SHA-web"
  : > "$W/logs/bake.log"
  run d build "$SHA"
  assert_success
  assert_equal "$(grep -c . "$W/logs/bake.log")" 1
  run grep -c "^web " "$W/logs/bake.log"; assert_output 1
  assert_equal "$(cand "$SHA-server")" "$server_before"
  [ -n "$(cand "$SHA-web")" ]

  commit_change two
  local before; before="$(snapshot)"
  STUB_REGISTRY_DOWN=1 run d build "$SHA"
  assert_failure 1
  assert_output --partial "store-query"
  assert_equal "$(snapshot)" "$before"
}

@test "build_without_a_hook_uses_buildx_bake, and with one calls the hook (S4, R3)" {
  commit_change one
  run d build "$SHA"; assert_success
  run grep -c "buildx bake" "$W/logs/docker.log"
  assert_output --regexp '^[1-9]'
  : > "$HOOKLOG"
  cat > "$W/work/deliver/hooks/build" <<'EOF'
#!/usr/bin/env bash
echo "== build $DELIVER_BUILD_IMAGES revision=$DELIVER_LABEL_REVISION version=$DELIVER_LABEL_VERSION" >> "$HOOKLOG"
for i in $DELIVER_BUILD_IMAGES; do
  v="DELIVER_BUILD_TAG_$(printf '%s' "$i" | tr a-z A-Z)"
  docker buildx bake "$i" --push --set "$i.tags=${!v}" \
    --set "$i.labels.org.opencontainers.image.revision=$DELIVER_LABEL_REVISION" \
    --set "$i.labels.org.opencontainers.image.version=$DELIVER_LABEL_VERSION" \
    --set "$i.labels.org.opencontainers.image.created=$DELIVER_LABEL_CREATED"
done
EOF
  chmod +x "$W/work/deliver/hooks/build"
  commit_all "add a build hook"
  : > "$W/logs/docker.log"
  run d build "$SHA"
  assert_success
  run hook_calls
  assert_output "build"
  run grep -c "== build server web revision=$SHA version=0.10.2" "$HOOKLOG"
  assert_output 1
  [ -n "$(cand "$SHA-server")" ]
}

@test "a build whose image lacks the revision label is refused (R3)" {
  commit_change one
  cat > "$W/work/deliver/hooks/build" <<'EOF'
#!/usr/bin/env bash
for i in $DELIVER_BUILD_IMAGES; do
  v="DELIVER_BUILD_TAG_$(printf '%s' "$i" | tr a-z A-Z)"
  docker buildx bake "$i" --push --set "$i.tags=${!v}" --set "$i.labels.org.opencontainers.image.revision=not-the-commit"
done
EOF
  chmod +x "$W/work/deliver/hooks/build"
  commit_all "a build hook that labels wrongly"
  run d build "$SHA"
  assert_failure 1
  assert_output --partial "build-labels"
}

@test "multi_arch_build_deploys_by_index_digest (S5, R3, R7; the index is the stub's)" {
  commit_change one
  STUB_ARCH=multi run d build "$SHA"
  assert_success
  local idx; idx="$(cand "$SHA-server")"
  assert_line "server $idx"
  run d deploy rehearsal "$SHA" --off-level "first"
  assert_success
  assert_equal "$(running_digests_of rehearsal acme-rehearsal)" "$(digests_of "$SHA")"
}

@test "build --local is for the preview role and pushes nothing" {
  commit_change one
  git -C "$W/work" reset -q --hard HEAD
  printf 'unpushed\n' > "$W/work/src.txt"; git -C "$W/work" commit -qam "unpushed"
  local sha; sha="$(git -C "$W/work" rev-parse HEAD)"
  run d build "$sha" --local
  assert_success
  assert_output --regexp "server sha256:"
  [ ! -e "$W/registry/reg.test/ns/acme/candidates/tags/$sha-server" ]
  run d deploy preview "$sha"
  assert_success
  assert_equal "$(host_state local preview)" finished
}
