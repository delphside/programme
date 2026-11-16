#!/usr/bin/env bash
# registry.sh: on an environment's host, the deployer's registry login (design §3).
# The host reaches the registry by `docker pull` alone; every other read or write of
# the registry is the Python controller's. TURPIN_REGISTRY is the registry address
# with the tenancy's namespace; it comes from the machine's own local configuration
# and is never in a profile.

REG_ERR=""
# REG_COMPONENT names the component whose login is in use, for the messages.
REG_COMPONENT=""

# reg_summarise RAW: what a failure says, without the registry's address or the
# tool's own words; the raw text is kept nowhere.
reg_summarise() {
  case "$1" in
    *denied*|*unauthorized*|*"authentication required"*|*forbidden*|*"not authorized"*) printf 'the registry refused access: the login may have expired or been revoked, or lacks the right (turpin login%s)' "${REG_COMPONENT:+ $REG_COMPONENT}" ;;
    *"manifest unknown"*|*"name unknown"*|*"not found"*) printf 'not found in the registry' ;;
    *"connection refused"*|*"no such host"*|*timeout*|*dial*|*TLS*|*"tls:"*|*"EOF"*) printf 'the registry could not be reached' ;;
    *) printf 'the registry operation failed' ;;
  esac
}

# login_docker USER: the token on standard input, to `docker login` (the machine
# user's, kept in ~/.docker beside its contexts, which the tool never moves). The
# tool's own words only: a failure is summarised, never the tool's text.
login_docker() {
  local out
  out="$(docker login -u "$1" --password-stdin "${TURPIN_REGISTRY%%/*}" 2>&1 >/dev/null)" \
    || { REG_ERR="docker login: $(reg_summarise "$out")"; return 1; }
}

# ---------------------------------------------------------------- login adapters
# One adapter per vendor method, named for the vendor (design §3). Another
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

login_run() { _login_adapter "$1"; }          # the machine user's docker login

# _login_adapter ADAPTER: make the login valid. The adapters read credentials the
# machine already holds and write none into the tool's own output. docker-config:
# the owner made the login with `turpin login`, the machine user's own. oci-*:
# TURPIN_OCI_TOKEN_CMD names the command that prints a registry auth token (`oci`
# CLI call chosen on the host, since the CLI's flags are the host's business,
# #554); the user is TURPIN_REGISTRY_USER.
_login_adapter() {
  local adapter="${1:-docker-config}"
  case "$adapter" in
    docker-config) return 0 ;;
    oci-api-key|oci-instance-principal)
      command -v oci >/dev/null 2>&1 || { REG_ERR="login $adapter needs the oci CLI"; return 1; }
      [[ -n "${TURPIN_OCI_TOKEN_CMD:-}" && -n "${TURPIN_REGISTRY_USER:-}" ]] || { REG_ERR="login $adapter needs TURPIN_OCI_TOKEN_CMD and TURPIN_REGISTRY_USER in the local configuration"; return 1; }
      if [[ "$adapter" == oci-api-key && -z "${OCI_CLI_KEY_FILE:-}${OCI_CLI_CONFIG_FILE:-}" && ! -f "$HOME/.oci/config" ]]; then
        REG_ERR="login oci-api-key needs an API key (OCI_CLI_KEY_FILE or ~/.oci/config)"; return 1
      fi
      local token
      token="$(bash -c "$TURPIN_OCI_TOKEN_CMD")" || { REG_ERR="the token command failed"; return 1; }
      printf '%s' "$token" | login_docker "$TURPIN_REGISTRY_USER" || return 1
      ;;
    *) REG_ERR="unknown login adapter $adapter"; return 1 ;;
  esac
}
