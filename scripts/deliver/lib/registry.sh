#!/usr/bin/env bash
# registry.sh: the registry as `deliver` reads and writes it (skopeo; no Docker
# daemon needed), and the login adapters. DELIVER_REGISTRY is the registry
# address with the tenancy's namespace; it comes from the machine's own local
# configuration and is never in a profile (design §5).

REG_ERR=""

registry_require() {
  [[ -n "${DELIVER_REGISTRY:-}" ]] || die "DELIVER_REGISTRY is not set: put it in ${DELIVER_CONFIG_DIR:-~/.config/deliver}/${APP:-APP}.env (the profile never holds it)"
}

reg_ref() {        # REPO TAG|@DIGEST  ->  docker://REGISTRY/REPO:TAG
  case "$2" in
    sha256:*) printf 'docker://%s/%s@%s' "$DELIVER_REGISTRY" "$1" "$2" ;;
    *)        printf 'docker://%s/%s:%s' "$DELIVER_REGISTRY" "$1" "$2" ;;
  esac
}

# reg_inspect REPO REF: prints skopeo's JSON on stdout. Returns 0 present, 1
# absent (the registry answered "unknown"), 2 the registry could not be queried.
reg_inspect() {
  local out err
  err="$(mktemp)"
  if out="$(skopeo inspect "$(reg_ref "$1" "$2")" 2>"$err")"; then
    rm -f "$err"; printf '%s\n' "$out"; return 0
  fi
  REG_ERR="$(cat "$err")"; rm -f "$err"
  case "$REG_ERR" in
    *"manifest unknown"*|*"name unknown"*|*"not found"*) return 1 ;;
  esac
  return 2
}

reg_digest() {     # REPO TAG -> digest on stdout; same return codes as reg_inspect
  local json code=0
  json="$(reg_inspect "$1" "$2")" || code=$?
  [[ $code -eq 0 ]] || return "$code"
  jq -r .Digest <<< "$json"
}

reg_list_tags() {  # REPO -> one tag per line
  local out
  out="$(skopeo list-tags "docker://$DELIVER_REGISTRY/$1" 2>/dev/null)" || return 1
  jq -r '.Tags[]' <<< "$out"
}

# reg_copy SRC_REPO SRC_REF DST_REPO DST_TAG: by digest, every architecture.
reg_copy() {
  skopeo copy --all --preserve-digests "$(reg_ref "$1" "$2")" "$(reg_ref "$3" "$4")" 2>&1
}

# ---------------------------------------------------------------- login adapters
# One adapter per vendor method, named for the vendor (design §2). Another
# registry adds an adapter here and changes nothing else.

login_adapters() { printf '%s\n' docker-config oci-api-key oci-instance-principal; }

login_tools() {    # ADAPTER -> the commands it needs on the machine
  case "$1" in
    docker-config) : ;;
    oci-api-key) printf '%s\n' oci ;;
    oci-instance-principal) printf '%s\n' oci ;;
    *) return 1 ;;
  esac
}

# login_run ADAPTER: make the machine's registry login valid. The adapters read
# credentials the machine already holds and write none into the tool's own
# output. oci-*: DELIVER_OCI_TOKEN_CMD names the command that prints a registry
# auth token (`oci` CLI call chosen on the host, since the CLI's flags are the
# host's business, #554); the user is DELIVER_REGISTRY_USER.
login_run() {
  case "$1" in
    docker-config) return 0 ;;
    oci-api-key|oci-instance-principal)
      command -v oci >/dev/null 2>&1 || { REG_ERR="login $1 needs the oci CLI"; return 1; }
      [[ -n "${DELIVER_OCI_TOKEN_CMD:-}" && -n "${DELIVER_REGISTRY_USER:-}" ]] || { REG_ERR="login $1 needs DELIVER_OCI_TOKEN_CMD and DELIVER_REGISTRY_USER in the local configuration"; return 1; }
      if [[ "$1" == oci-api-key && -z "${OCI_CLI_KEY_FILE:-}${OCI_CLI_CONFIG_FILE:-}" && ! -f "$HOME/.oci/config" ]]; then
        REG_ERR="login oci-api-key needs an API key (OCI_CLI_KEY_FILE or ~/.oci/config)"; return 1
      fi
      local token
      token="$(bash -c "$DELIVER_OCI_TOKEN_CMD")" || { REG_ERR="the token command failed"; return 1; }
      printf '%s' "$token" | docker login -u "$DELIVER_REGISTRY_USER" --password-stdin "${DELIVER_REGISTRY%%/*}" >/dev/null 2>&1 \
        || { REG_ERR="docker login failed"; return 1; }
      ;;
    *) REG_ERR="unknown login adapter $1"; return 1 ;;
  esac
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
  [[ $code -eq 0 ]] || { REG_ERR="$out"; return 1; }
}

# record_pull REPO TAG: prints the record JSON held by the scratch image.
record_pull() {
  local dir out code=0
  dir="$(mktemp -d)"
  out="$(skopeo copy "$(reg_ref "$1" "$2")" "oci:$dir/layout" 2>&1)" || code=$?
  if [[ $code -ne 0 ]]; then REG_ERR="$out"; rm -rf "$dir"; return 1; fi
  local manifest layer
  manifest="$(jq -r '.manifests[0].digest' "$dir/layout/index.json")"
  layer="$(jq -r '.layers[0].digest' "$dir/layout/blobs/sha256/${manifest#sha256:}")"
  tar -xOf "$dir/layout/blobs/sha256/${layer#sha256:}" record.json
  rm -rf "$dir"
}
