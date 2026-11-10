#!/usr/bin/env bash
# registry.sh: the registry as `turpin` reads and writes it (skopeo; no Docker
# daemon needed), and the login adapters. TURPIN_REGISTRY is the registry
# address with the tenancy's namespace; it comes from the machine's own local
# configuration and is never in a profile (design §10).

REG_ERR=""; REG_DIGEST=""

# reg_summarise RAW: what a failure says, without the registry's address or the
# tool's own words (skopeo's stderr names the host and the repository, and it
# reaches the screen and the run log); the raw text is kept nowhere.
reg_summarise() {
  case "$1" in
    *denied*|*unauthorized*|*"authentication required"*|*forbidden*|*"not authorized"*) printf 'the registry refused access: the login may have expired or been revoked, or lacks the right (turpin login%s)' "${REG_COMPONENT:+ $REG_COMPONENT}" ;;
    *"manifest unknown"*|*"name unknown"*|*"not found"*) printf 'not found in the registry' ;;
    *"connection refused"*|*"no such host"*|*timeout*|*dial*|*TLS*|*"tls:"*|*"EOF"*) printf 'the registry could not be reached' ;;
    *) printf 'the registry operation failed' ;;
  esac
}

registry_require() {
  [[ -n "${TURPIN_REGISTRY:-}" ]] || die "TURPIN_REGISTRY is not set: put it in ${TURPIN_CONFIG_DIR:-~/.config/turpin}/${APP:-APP}.env (the profile never holds it)"
}

reg_ref() {        # REPO TAG|@DIGEST  ->  docker://REGISTRY/REPO:TAG
  case "$2" in
    sha256:*) printf 'docker://%s/%s@%s' "$TURPIN_REGISTRY" "$1" "$2" ;;
    *)        printf 'docker://%s/%s:%s' "$TURPIN_REGISTRY" "$1" "$2" ;;
  esac
}

# reg_inspect REPO REF: prints skopeo's JSON on stdout. Returns 0 present, 1
# absent (the registry answered "unknown"), 2 the registry could not be queried.
reg_inspect() {
  local out err
  reg_prepare || return 2
  err="$(mktemp)"
  if out="$(skopeo inspect "$(reg_ref "$1" "$2")" 2>"$err")"; then
    rm -f "$err"; printf '%s\n' "$out"; return 0
  fi
  local raw; raw="$(cat "$err")"; rm -f "$err"
  REG_ERR="$(reg_summarise "$raw")"
  case "$raw" in
    *"manifest unknown"*|*"name unknown"*|*"not found"*) return 1 ;;
  esac
  return 2
}

reg_digest() {     # REPO TAG -> REG_DIGEST (and stdout); same return codes as reg_inspect.
  # Call it as `reg_digest R T || code=$?; d="$REG_DIGEST"`, not inside $(...): REG_ERR must reach the caller.
  local tmp code=0
  tmp="$(mktemp)"; REG_DIGEST=""
  reg_inspect "$1" "$2" > "$tmp" || code=$?
  [[ $code -eq 0 ]] && REG_DIGEST="$(jq -r .Digest "$tmp")"
  rm -f "$tmp"
  [[ $code -ne 0 ]] || printf '%s\n' "$REG_DIGEST"
  return "$code"
}

reg_list_tags() {  # REPO -> one tag per line
  local out
  reg_prepare || return 1
  out="$(skopeo list-tags "docker://$TURPIN_REGISTRY/$1" 2>/dev/null)" || return 1
  jq -r '.Tags[]' <<< "$out"
}

# reg_delete REPO TAG: only the builder's login may.
reg_delete() {
  local out
  out="$(skopeo delete "$(reg_ref "$1" "$2")" 2>&1)" && return 0
  REG_ERR="$(reg_summarise "$out")"; return 1
}

# reg_copy SRC_REPO SRC_REF DST_REPO DST_TAG: by digest, every architecture.
reg_copy() {
  local out
  out="$(skopeo copy --all --preserve-digests "$(reg_ref "$1" "$2")" "$(reg_ref "$3" "$4")" 2>&1)" && return 0
  REG_ERR="$(reg_summarise "$out")"; return 1
}

# ---------------------------------------------------------------- one login per component
# `skopeo` keeps its login in an auth file, so a component that only calls
# skopeo (the controller's reads, the release copier's copy and record, the
# builder's delete) has a file of its own, ~/.config/turpin/auth/APP/COMPONENT.json,
# chosen with REGISTRY_AUTH_FILE alone: two components on one machine never
# replace one another's login. `docker` keeps the machine user's login in
# ~/.docker beside its contexts and builders, which the tool never moves
# (DOCKER_CONFIG is never set): the builder's push and each deployer's pull use it
# (design §10).

# REG_COMPONENT names the component whose login is in use, for the messages.
REG_COMPONENT=""
# REG_AUTH_HOOK: a command run before a registry read (the controller makes its
# login lazily, so a command that never reads the registry needs none).
REG_AUTH_HOOK=""

auth_file_of() {   # COMPONENT -> the auth file of the controller, builder or copier on this machine
  printf '%s/auth/%s/%s.json' "${TURPIN_CONFIG_DIR:-$HOME/.config/turpin}" "${APP:?}" "$1"
}

# auth_use FILE COMPONENT: this process's skopeo login is FILE. The directory is
# 0700 and the file 0600, set on every use.
auth_use() {
  local file="$1" dir
  dir="$(dirname "$file")"
  ( umask 077; mkdir -p "$dir" ) || die "cannot make the registry login directory $dir"
  chmod 700 "$dir" 2>/dev/null || true
  [[ ! -e "$file" ]] || chmod 600 "$file" 2>/dev/null || true
  export REGISTRY_AUTH_FILE="$file"
  REG_COMPONENT="$2"
}

reg_prepare() {
  [[ -z "$REG_AUTH_HOOK" ]] && return 0
  "$REG_AUTH_HOOK"
}

# login_docker USER, login_skopeo USER: the token on standard input, to
# `docker login` (the machine user's) or `skopeo login` (REGISTRY_AUTH_FILE).
# The tool's own words only: a failure is summarised, never the tool's text.
login_docker() {
  local out
  out="$(docker login -u "$1" --password-stdin "${TURPIN_REGISTRY%%/*}" 2>&1 >/dev/null)" \
    || { REG_ERR="docker login: $(reg_summarise "$out")"; return 1; }
}
login_skopeo() {
  local out
  [[ -n "${REGISTRY_AUTH_FILE:-}" ]] || { REG_ERR="no auth file chosen"; return 1; }
  out="$(skopeo login --authfile "$REGISTRY_AUTH_FILE" -u "$1" --password-stdin "${TURPIN_REGISTRY%%/*}" 2>&1 >/dev/null)" \
    || { REG_ERR="skopeo login: $(reg_summarise "$out")"; return 1; }
  chmod 600 "$REGISTRY_AUTH_FILE" 2>/dev/null || true
}

# ---------------------------------------------------------------- login adapters
# One adapter per vendor method, named for the vendor (design §10). Another
# registry adds an adapter here and changes nothing else. Each is used for the
# docker login of a docker user (login_run) or for the auth file of a skopeo
# user (login_run_skopeo).

login_adapters() { printf '%s\n' docker-config oci-api-key oci-instance-principal; }

login_tools() {    # ADAPTER -> the commands it needs on the machine
  case "$1" in
    docker-config) : ;;
    oci-api-key) printf '%s\n' oci ;;
    oci-instance-principal) printf '%s\n' oci ;;
    *) return 1 ;;
  esac
}

login_run() { _login_adapter docker "$1"; }          # the machine user's docker login
login_run_skopeo() { _login_adapter skopeo "$1"; }   # REGISTRY_AUTH_FILE's login

# _login_adapter KIND ADAPTER: make the login valid. The adapters read
# credentials the machine already holds and write none into the tool's own
# output. docker-config: the owner made the login with `turpin login`; a docker
# user's is the machine user's own, a skopeo user's file is checked. oci-*:
# TURPIN_OCI_TOKEN_CMD names the command that prints a registry auth token (`oci`
# CLI call chosen on the host, since the CLI's flags are the host's business,
# #554); the user is TURPIN_REGISTRY_USER.
_login_adapter() {
  local kind="$1" adapter="${2:-docker-config}"
  case "$adapter" in
    docker-config)
      [[ "$kind" == docker ]] && return 0
      jq -e --arg h "${TURPIN_REGISTRY%%/*}" '((.auths // {}) | has($h)) or ((.credHelpers // {}) | has($h))' \
        "${REGISTRY_AUTH_FILE:-/nonexistent}" >/dev/null 2>&1 \
        || { REG_ERR="no registry login for the ${REG_COMPONENT:-component}: make it with turpin login ${REG_COMPONENT:-COMPONENT}"; return 1; }
      ;;
    oci-api-key|oci-instance-principal)
      command -v oci >/dev/null 2>&1 || { REG_ERR="login $adapter needs the oci CLI"; return 1; }
      [[ -n "${TURPIN_OCI_TOKEN_CMD:-}" && -n "${TURPIN_REGISTRY_USER:-}" ]] || { REG_ERR="login $adapter needs TURPIN_OCI_TOKEN_CMD and TURPIN_REGISTRY_USER in the local configuration"; return 1; }
      if [[ "$adapter" == oci-api-key && -z "${OCI_CLI_KEY_FILE:-}${OCI_CLI_CONFIG_FILE:-}" && ! -f "$HOME/.oci/config" ]]; then
        REG_ERR="login oci-api-key needs an API key (OCI_CLI_KEY_FILE or ~/.oci/config)"; return 1
      fi
      local token
      token="$(bash -c "$TURPIN_OCI_TOKEN_CMD")" || { REG_ERR="the token command failed"; return 1; }
      printf '%s' "$token" | "login_$kind" "$TURPIN_REGISTRY_USER" || return 1
      ;;
    *) REG_ERR="unknown login adapter $adapter"; return 1 ;;
  esac
}

# auth_login LABEL ADAPTER [docker|skopeo]: as above, or die naming the label.
auth_login() {
  _login_adapter "${3:-skopeo}" "${2:-docker-config}" || die "the $1's registry login (${2:-docker-config}) failed: $REG_ERR"
}

# ---------------------------------------------------------------- the record image

# record_push REPO TAG FILE: the record as a scratch image (one layer holding
# record.json), built as an OCI layout and copied by skopeo.
record_push() {
  local repo="$1" tag="$2" file="$3" dir tar layer_sha config config_sha manifest manifest_sha
  dir="$(mktemp -d)"
  mkdir -p "$dir/layout/blobs/sha256" "$dir/root"
  cp "$file" "$dir/root/record.json"
  tar -C "$dir/root" --mtime=@0 --owner=0 --group=0 --numeric-owner -cf "$dir/layer.tar" record.json
  layer_sha="$(sha256_of < "$dir/layer.tar")"
  cp "$dir/layer.tar" "$dir/layout/blobs/sha256/$layer_sha"
  config="$(jq -nc --arg d "sha256:$layer_sha" '{architecture:"amd64",os:"linux",config:{},rootfs:{type:"layers",diff_ids:[$d]}}')"
  config_sha="$(printf '%s' "$config" | sha256_of)"
  printf '%s' "$config" > "$dir/layout/blobs/sha256/$config_sha"
  manifest="$(jq -nc --arg c "sha256:$config_sha" --arg l "sha256:$layer_sha" \
    --argjson cs "${#config}" --argjson ls "$(stat -c %s "$dir/layer.tar")" \
    '{schemaVersion:2,mediaType:"application/vnd.oci.image.manifest.v1+json",
      config:{mediaType:"application/vnd.oci.image.config.v1+json",digest:$c,size:$cs},
      layers:[{mediaType:"application/vnd.oci.image.layer.v1.tar",digest:$l,size:$ls}]}')"
  manifest_sha="$(printf '%s' "$manifest" | sha256_of)"
  printf '%s' "$manifest" > "$dir/layout/blobs/sha256/$manifest_sha"
  printf '{"imageLayoutVersion":"1.0.0"}' > "$dir/layout/oci-layout"
  jq -nc --arg m "sha256:$manifest_sha" --argjson s "${#manifest}" \
    '{schemaVersion:2,manifests:[{mediaType:"application/vnd.oci.image.manifest.v1+json",digest:$m,size:$s}]}' > "$dir/layout/index.json"
  local out code=0
  out="$(skopeo copy "oci:$dir/layout" "$(reg_ref "$repo" "$tag")" 2>&1)" || code=$?
  rm -rf "$dir"
  [[ $code -eq 0 ]] || { REG_ERR="$(reg_summarise "$out")"; return 1; }
}

# record_pull REPO TAG: prints the record JSON held by the scratch image.
record_pull() {
  local dir out code=0
  reg_prepare || return 1
  dir="$(mktemp -d)"
  out="$(skopeo copy "$(reg_ref "$1" "$2")" "oci:$dir/layout" 2>&1)" || code=$?
  if [[ $code -ne 0 ]]; then REG_ERR="$(reg_summarise "$out")"; rm -rf "$dir"; return 1; fi
  local manifest layer
  manifest="$(jq -r '.manifests[0].digest' "$dir/layout/index.json")"
  layer="$(jq -r '.layers[0].digest' "$dir/layout/blobs/sha256/${manifest#sha256:}")"
  tar -xOf "$dir/layout/blobs/sha256/${layer#sha256:}" record.json
  rm -rf "$dir"
}
