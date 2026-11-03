#!/usr/bin/env bash
# steps.sh: the host-side steps of a deploy and a rollback (design §9). Sourced
# by `deploy` and `rollback`, which `deliver-host` starts from the payload taken
# out of the image, with the environment's lock already held. Names no
# application: the profile (profile.json in the payload) and the hooks say.

host_ctx_load() {   # reads the request and the payload's profile into shell variables
  REQ="$DELIVER_REQUEST"
  H_APP="$(jq -r .app "$REQ")"; H_ENV="$(jq -r .env "$REQ")"; H_ROLE="$(jq -r .role "$REQ")"
  H_SHA="$(jq -r '.sha // ""' "$REQ")"; H_VERSION="$(jq -r '.version // ""' "$REQ")"
  H_STATE="$ENVDIR"
  H_IMAGES="$(jq -r '(.images // {}) | to_entries[] | "\(.key)=\(.value)"' "$REQ")"
  PROJECT="$(jq -r '.project // empty' "$REQ")"; PROJECT="${PROJECT:-$H_APP-$H_ENV}"
  PJSON="$PAYLOAD/profile.json"
  REQUIRED_HOOKS="$(jq -r '(.release.required_hooks // [])[]' "$PJSON" | tr '\n' ' ')"
  OVERRIDABLE="$(jq -r '(.release.overridable // [])[]' "$PJSON" | tr '\n' ' ')"
  HOOKS_DIR="$PAYLOAD/hooks"
  mapfile -t SET_ASIDE < <(jq -r '(.set_aside // [])[] | "\(.gate)\t\(.reason)"' "$REQ")
  OPT_WAIT="$(jq -r '.wait // empty' "$REQ")"
  case "$(jq -r '.host_files' "$REQ")" in
    true) HOST_FILES=1 ;; false) HOST_FILES=0 ;;
    *) case "$H_ROLE" in rehearsal|production) HOST_FILES=1 ;; *) HOST_FILES=0 ;; esac ;;
  esac
  FALLBACK="$(jq -r '.deliver.fallback // "the application has named no fallback"' "$PJSON")"
  KEEP_IMAGES="$(jq -r '(.deliver.keep_images // [])[]' "$PJSON")"
}

state_read()  { head -1 "$ENVDIR/state" 2>/dev/null || true; }
state_n()     { sed -n 's/^deploy=//p' "$ENVDIR/state" 2>/dev/null | head -1; }
state_write() {   # TEXT [deploy-n]
  printf '%s\ndeploy=%s\n' "$1" "${2:-}" > "$ENVDIR/state.new" && mv -f "$ENVDIR/state.new" "$ENVDIR/state"
}
state_settled() { case "$(state_read)" in ""|finished|restored*|"failed, no previous deploy") return 0 ;; *) return 1 ;; esac; }

deploy_dir()  { printf '%s/deploys/%s' "${ENVDIR:?}" "$1"; }
link_n()      { local t; t="$(readlink "${ENVDIR:?}/$1" 2>/dev/null)" || return 1; basename "$t"; }
next_n()      { local n=0; [[ -f "$ENVDIR/counter" ]] && n="$(cat "$ENVDIR/counter")"; n=$((n + 1)); printf '%s' "$n" > "$ENVDIR/counter"; printf '%s' "$n"; }

drop_dir()    { local d="${1:?}"; [[ -d "$d" ]] && rm -rf -- "$d"; return 0; }

set_link() {      # NAME N|""
  local link="${ENVDIR:?}/${1:?}"
  if [[ -z "$2" ]]; then rm -f -- "$link"; else ln -sfn "deploys/$2" "$link"; fi
}

compose_args() {  # N -> prints the base arguments for the deploy folder, NUL separated
  local dir; dir="$(deploy_dir "$1")"
  local args=(compose -p "$PROJECT" --project-directory "$dir")
  [[ -f "$ENVDIR/.env" ]] && args+=(--env-file "$ENVDIR/.env")
  args+=(--env-file "$dir/deliver.env")
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
    docker image inspect "$img" --format '{{json .RepoDigests}}' 2>/dev/null | jq -r '.[]? | sub("^.*@"; "")'
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

# ------------------------------------------------------------------ host files

root_ops() {   # ARGS...: through the one sudo rule, unless already root
  if [[ "$(id -u)" -eq 0 ]]; then deliver-host root-ops "$@"; else sudo -n deliver-host root-ops "$@"; fi
}

# install_set DIR: make the host's installed files exactly DIR's payload set.
install_set() {
  local payload="$1/payload" pj dest src mode enable listed="$ENVDIR/host_files.installed" new="$ENVDIR/host_files.new" changed=0
  pj="$payload/profile.json"
  : > "$new"
  while IFS=$'\t' read -r src dest mode enable; do
    [[ -n "$src" ]] || continue
    root_ops install "$payload/host_files/$src" "$dest" "${mode:-0644}" || return 1
    printf '%s\t%s\n' "$dest" "$enable" >> "$new"; changed=1
  done < <(jq -r '(.deliver.host_files // [])[] | [.src, .dest, (.mode // "0644"), ((.enable // false) | tostring)] | @tsv' "$pj")
  # a file the previous set installed and this one does not carry is removed
  if [[ -f "$listed" ]]; then
    while IFS=$'\t' read -r dest enable; do
      [[ -n "$dest" ]] || continue
      grep -qF "$dest"$'\t' "$new" && continue
      if [[ "$enable" == true ]]; then root_ops systemctl disable --now "$(basename "$dest")" || true; fi
      root_ops rm "$dest" || return 1; changed=1
    done < "$listed"
  fi
  if [[ $changed -eq 1 ]]; then
    root_ops systemctl daemon-reload || return 1
    while IFS=$'\t' read -r dest enable; do
      [[ "$enable" == true ]] || continue
      root_ops systemctl enable "$(basename "$dest")" || return 1
      root_ops systemctl restart "$(basename "$dest")" || return 1
    done < "$new"
  fi
  mv -f "$new" "$listed"
}

# ------------------------------------------------------------------ restore

# restore_to GOOD FAILED_N PRIOR_PREVIOUS: put the last good deploy back. GOOD may
# be the empty string (a first deploy: nothing to go back to).
restore_to() {
  local good="$1" failed="$2" prevprev="$3"
  HOOKS_DIR="$(deploy_dir "$failed")/payload/hooks"; [[ -d "$HOOKS_DIR" ]] || HOOKS_DIR="$PAYLOAD/hooks"
  hook_step restore-state || warn "restore-state failed; the saved state may need restoring by hand"
  if [[ -z "$good" ]]; then
    [[ -d "$(deploy_dir "$failed")" ]] && { compose_run "$failed" down >/dev/null 2>&1 || true; }
    set_link current ""; set_link previous ""
    state_write "failed, no previous deploy" "$failed"
    drop_dir "$(deploy_dir "$failed")"
    return 0
  fi
  if [[ "$HOST_FILES" -eq 1 ]]; then install_set "$(deploy_dir "$good")" || warn "reinstalling the previous host files failed"; fi
  compose_run "$good" up -d --no-build --remove-orphans >/dev/null 2>&1 || warn "bringing the previous deploy back failed"
  set_link current "$good"; set_link previous "$prevprev"
  state_write "restored" "$good"
  [[ "$failed" != "$good" ]] && drop_dir "$(deploy_dir "$failed")"
  return 0
}

prune_host_images() {   # keep the current and previous sets, and keep_images
  local keep="" n line repo digest id
  for n in current previous; do
    [[ -f "$ENVDIR/$n/deliver.env" ]] && keep+="$(sed -n 's/^[^=]*=.*@//p' "$ENVDIR/$n/deliver.env")"$'\n'
  done
  while read -r line; do
    [[ -n "$line" ]] || continue
    read -r repo digest id <<< "$line"
    [[ "$repo" == "$DELIVER_REGISTRY/"* ]] || continue
    grep -qxF "$digest" <<< "$keep" && continue
    grep -qxF "$repo" <<< "$KEEP_IMAGES" && continue
    docker rmi "${repo%:*}@$digest" >/dev/null 2>&1 || true
  done < <(docker image ls --digests --format '{{.Repository}}:{{.Tag}} {{.Digest}} {{.ID}}' 2>/dev/null)
  : "${id:-}"
}
