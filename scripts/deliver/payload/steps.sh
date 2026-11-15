#!/usr/bin/env bash
# steps.sh: the host-side steps of a deploy and a rollback (design §11). Sourced
# by `deploy` and `rollback`, which `turpin-host` starts from the payload taken
# out of the image, with the environment's lock already held. Names no
# application: the profile (profile.json in the payload) and the hooks say.

host_ctx_load() {   # reads the request and the payload's profile into shell variables
  REQ="$TURPIN_REQUEST"
  H_APP="$(jq -r .app "$REQ")"; H_ENV="$(jq -r .env "$REQ")"; H_ROLE="$(jq -r .role "$REQ")"
  H_SHA="$(jq -r '.sha // ""' "$REQ")"; H_VERSION="$(jq -r '.version // ""' "$REQ")"
  H_STATE="$ENVDIR"
  # each image by digest, as the compose file and the hooks name it
  if [[ "$(jq -r '.local' "$REQ")" == true ]]; then
    H_IMAGES="$(jq -r '(.images // {}) | to_entries[] | "\(.key)=\(.value)"' "$REQ")"
  else
    H_IMAGES="$(jq -r --arg r "$TURPIN_REGISTRY/$(jq -r '.repo // ""' "$REQ")" '(.images // {}) | to_entries[] | "\(.key)=\($r)@\(.value)"' "$REQ")"
  fi
  PROJECT="$(jq -r '.project // empty' "$REQ")"; PROJECT="${PROJECT:-$H_APP-$H_ENV}"
  PJSON="$PAYLOAD/profile.json"
  jq -e . "$PJSON" >/dev/null 2>&1 || REASON=HOST_PAYLOAD_UNREADABLE die "$PJSON is not valid JSON: repair or restore it, then run turpin rollback ENV again"
  REQUIRED_HOOKS="$(jq -r '(.release.required_hooks // [])[]' "$PJSON" | tr '\n' ' ')"
  OVERRIDABLE="$(jq -r '(.release.overridable // [])[]' "$PJSON" | tr '\n' ' ')"
  HOOKS_DIR="$PAYLOAD/hooks"
  mapfile -t SET_ASIDE < <(jq -r '(.set_aside // [])[] | "\(.gate)\t\(.reason)"' "$REQ")
  OPT_WAIT="$(jq -r '.wait // empty' "$REQ")"
  case "$(jq -r '.host_files' "$REQ")" in
    true) HOST_FILES=1 ;; false) HOST_FILES=0 ;;
    *) case "$H_ROLE" in rehearsal|production) HOST_FILES=1 ;; *) HOST_FILES=0 ;; esac ;;
  esac
  FALLBACK="$(jq -r '.turpin.fallback // "the application has named no fallback"' "$PJSON")"
}

# The host's record is state.json (common.sh's state_get and state_save, the only two
# that touch the file). These read and edit it for this environment.
st()      { state_field "$ENVDIR" "$1"; }        # NAME -> a field's value, empty where absent
st_put()  { state_put "$ENVDIR" "$@"; }          # FILTER [jq args]: one write of the record
st_installed() { state_get "$ENVDIR" | jq -c '.installed_host_files // []'; }   # the host files `current` installed
st_step() { st_put '.state = $s' --arg s "$1"; } # TEXT: the state alone, as each step writes it

# finished_request MESSAGE: the `last_request` of a request that has passed its pivot or run to
# its end, written in the same write as the state it ends in (design section 11).
finished_request() {
  jq -nc --arg id "$(jq -r .request_id "$REQ")" --arg m "$1" --argjson g "$(gates_from_notes)" \
    '{request_id: $id, outcome: "finished", exit: 0, gates: $g,
      result: {outcome: "ok", type: null, blip: null, reason: "", domain: "turpin", message: $m, metadata: {}, violations: []}}'
}

deploy_dir()  { printf '%s/deploys/%s' "${ENVDIR:?}" "$1"; }

# next_n: one above the highest folder in deploys/ (1 where there is none). Pruned
# folders keep their meta.json, so a number is never used twice.
next_n() {
  local d n=0 b
  for d in "$ENVDIR"/deploys/*; do
    [[ -d "$d" ]] || continue
    b="$(basename "$d")"
    [[ "$b" =~ ^[0-9]+$ ]] && (( b > n )) && n="$b"
  done
  printf '%s' $((n + 1))
}

drop_dir()    { local d="${1:?}"; [[ -d "$d" ]] && rm -rf -- "$d"; return 0; }

compose_args() {  # N -> prints the base arguments for the deploy folder, NUL separated
  local dir; dir="$(deploy_dir "$1")"
  local args=(compose -p "$PROJECT" --project-directory "$dir")
  [[ -f "$ENVDIR/.env" ]] && args+=(--env-file "$ENVDIR/.env")
  args+=(--env-file "$dir/turpin.env")
  local f
  while read -r f; do
    case "$f" in *.yml|*.yaml) args+=(-f "$dir/$f") ;; esac
  done < <(jq -r '.join[]' "$dir/meta.json")
  printf '%s\0' "${args[@]}"
}
compose_run() {   # N ARGS...
  local n="$1"; shift
  local base=() a
  while IFS= read -r -d '' a; do base+=("$a"); done < <(compose_args "$n")
  docker "${base[@]}" "$@"
}

# running_digests: the image digests of the project's running containers (their RepoDigests)
running_digests() {
  local id img
  for id in $(docker ps -q --filter "label=com.docker.compose.project=$PROJECT" 2>/dev/null); do
    img="$(docker inspect --format '{{.Image}}' "$id" 2>/dev/null)" || continue
    docker image inspect "$img" --format '{{json .RepoDigests}}' 2>/dev/null | jq -r '.[]? | sub("^.*@"; "")' || true
    printf '%s\n' "$img"
  done | sort -u
}

verify_running() {   # N: every digest of the deploy is what runs
  local n="$1" d have missing=""
  have="$(running_digests)"
  for d in $(jq -r '.images[]' "$(deploy_dir "$n")/meta.json"); do
    grep -qxF "$d" <<< "$have" || missing+="$d "
  done
  [[ -z "$missing" ]] || { warn "the running containers do not match the deploy's digests: $missing"; return 1; }
}

# hook_numbered NAME DEPLOY [CURRENT]: save-state and restore-state get deploy numbers
# (design §8); the other hooks never see them.
hook_numbered() {
  local code=0
  H_DEPLOY="$2" H_CURRENT="${3:-}" hook_step "$1" || code=$?
  H_DEPLOY="" H_CURRENT=""
  return "$code"
}

# ------------------------------------------------------------------ host files

root_ops() {   # ARGS...: through the one sudo rule, unless already root
  if [[ "$(id -u)" -eq 0 ]]; then turpin-host root-ops "$@"; else sudo -n turpin-host root-ops "$@"; fi
}

# host_files_of N: the host files deploy N installs, as [{dest, enable}]; none where
# its host_files is false.
host_files_of() {
  local dir; dir="$(deploy_dir "$1")"
  if [[ "$(jq -r '.host_files' "$dir/meta.json")" != true ]]; then printf '[]'; return 0; fi
  jq -c '[(.turpin.host_files // [])[] | {dest: .dest, enable: (.enable // false)}]' "$dir/payload/profile.json"
}

# host_files_apply N REMOVE: make the host's installed files N's set (N empty: install
# none), then take away each file of REMOVE ([{dest, enable}]) that N lacks. Safe to run again: an install rewrites
# the file, and a file already gone is done.
host_files_apply() {
  local n="$1" remove="$2" payload dest src mode enable changed=0 mine="[]"
  jq -e 'type == "array"' <<< "$remove" >/dev/null 2>&1 || { warn "cannot tell which host files to remove"; return 1; }
  if [[ -n "$n" ]]; then
    payload="$(deploy_dir "$n")/payload"
    mine="$(host_files_of "$n")"
  fi
  while IFS=$'\t' read -r src dest mode enable; do
    [[ -n "$src" ]] || continue
    [[ "$(jq -r --arg d "$dest" 'any(.[]; .dest == $d)' <<< "$mine")" == true ]] || continue
    root_ops install "$payload/host_files/$src" "$dest" "${mode:-0644}" || return 1
    changed=1
  done < <([[ -z "$n" ]] || jq -r '(.turpin.host_files // [])[] | [.src, .dest, (.mode // "0644"), ((.enable // false) | tostring)] | @tsv' "$payload/profile.json")
  while IFS=$'\t' read -r dest enable; do
    [[ -n "$dest" ]] || continue
    [[ "$(jq -r --arg d "$dest" 'any(.[]; .dest == $d)' <<< "$mine")" != true ]] || continue
    [[ -e "$(host_root)$dest" ]] || continue
    if [[ "$enable" == true ]]; then
      root_ops systemctl stop "$(basename "$dest")" || { warn "cannot stop $(basename "$dest"), which this deploy no longer carries"; return 1; }
      root_ops systemctl disable "$(basename "$dest")" || { warn "cannot disable $(basename "$dest"), which this deploy no longer carries"; return 1; }
    fi
    root_ops rm "$dest" || return 1
    changed=1
  done < <(jq -r '.[] | [.dest, (.enable | tostring)] | @tsv' <<< "$remove")
  if [[ $changed -eq 1 ]]; then
    root_ops systemctl daemon-reload || return 1
    while IFS=$'\t' read -r dest enable; do
      [[ "$enable" == true ]] || continue
      root_ops systemctl enable "$(basename "$dest")" || return 1
      root_ops systemctl restart "$(basename "$dest")" || return 1
    done < <(jq -r '.[] | [.dest, (.enable | tostring)] | @tsv' <<< "$mine")
  fi
  return 0
}

# ------------------------------------------------------------------ restore

# restore: put `current`, the last finished deploy, back after the deploy `pending` (design
# §11). The state stays as it is until the one write that ends it. Returns 1 when the
# restore itself failed: the state is then `failed: the restore did not complete`, with
# `pending` and `target` kept, so nothing deploys over it until `turpin rollback` runs
# the restore again.
restore() {
  local cur pend
  cur="$(st current)"; pend="$(st pending)"
  [[ -n "$pend" ]] || { warn "there is no deploy under way to restore from"; note F; note_result error HOST_RESTORE_FAILED "there is no deploy under way to restore from"; return 1; }
  restore_failed() { warn "$1"; note F; note_result error HOST_RESTORE_FAILED "$1"; st_put '.state = "failed: the restore did not complete"'; return 1; }
  if [[ -d "$(deploy_dir "$pend")/payload/hooks" ]]; then HOOKS_DIR="$(deploy_dir "$pend")/payload/hooks"; fi
  # each step is run only if the one before it worked: `current`'s build is never started
  # on data that was not restored
  hook_numbered restore-state "$pend" || { restore_failed "restore-state failed; the saved state may need restoring by hand"; return 1; }
  if [[ -z "$cur" ]]; then
    # a first deploy: nothing to go back to
    compose_run "$pend" down >/dev/null || { restore_failed "stopping the failed deploy's containers failed"; return 1; }
    host_files_apply "" "$(host_files_of "$pend")" || { restore_failed "removing the failed deploy's host files failed"; return 1; }
    st_put 'del(.pending, .target) | .state = "failed, no previous deploy"'
    return 0
  fi
  host_files_apply "$cur" "$(host_files_of "$pend")" || { restore_failed "reinstalling the last good host files failed"; return 1; }
  compose_run "$cur" up -d --no-build --remove-orphans >/dev/null || { restore_failed "bringing the last good deploy back failed"; return 1; }
  st_put 'del(.pending, .target) | .state = "restored"'
}

# ------------------------------------------------------------------ pruning, after the pivot

# prune_host_images: keep the current, previous and pending sets of every environment on
# this host (and of every application); remove the rest. Only images from the registry
# are considered, so a local image such as a fallback's `:latest` is never touched.
prune_host_images() {
  local keep="" line repo digest id f st n state_root rc=0
  state_root="$(dirname "$(dirname "$ENVDIR")")"
  for st in "$state_root"/*/*/; do
    [[ -d "$st" ]] || continue
    if [[ -n "$(state_layout_what "${st%/}")" ]]; then warn "the image prune skips ${st%/}, in the Bash turpin's layout: its images are not kept"; continue; fi
    for n in $(state_get "${st%/}" | jq -r '[.current, .previous, .pending] | map(select(. != null)) | .[]'); do
      f="${st%/}/deploys/$n/meta.json"
      [[ -f "$f" ]] && keep+="$(jq -r '.images[]?' "$f")"$'\n'
    done
  done
  while read -r line; do
    [[ -n "$line" ]] || continue
    read -r repo digest id <<< "$line"
    [[ "$repo" == "$TURPIN_REGISTRY/"* ]] || continue
    grep -qxF "$digest" <<< "$keep" && continue
    # an image already gone is done: only one still there after the rmi is a failure
    docker rmi "${repo%:*}@$digest" >/dev/null 2>&1 || {
      if docker image inspect "${repo%:*}@$digest" >/dev/null 2>&1; then warn "cannot remove the image ${repo%:*}@$digest"; rc=1; fi
    }
  done < <(docker image ls --digests --format '{{.Repository}}:{{.Tag}} {{.Digest}} {{.ID}}' 2>/dev/null)
  : "${id:-}"
  return "$rc"
}

# prune_deploys: each deploy folder other than the current and previous is cut to its
# meta.json, the whole record of what the host tried; one without a meta.json is removed.
prune_deploys() {
  local d n cur prev rc=0
  cur="$(st current)"; prev="$(st previous)"
  for d in "$ENVDIR"/deploys/*; do
    [[ -d "$d" ]] || continue
    n="$(basename "$d")"
    [[ "$n" == "$cur" || "$n" == "$prev" ]] && continue
    if [[ -f "$d/meta.json" ]]; then
      find "$d" -mindepth 1 ! -path "$d/meta.json" -delete || rc=1
    else
      rm -rf -- "$d" || rc=1
    fi
  done
  return "$rc"
}
