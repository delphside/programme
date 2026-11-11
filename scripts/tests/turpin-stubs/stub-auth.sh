# shellcheck shell=bash
# Sourced by the skopeo and docker stubs: a registry that enforces who is asking.
# With STUB_AUTH_ENFORCE set, every call must carry a login: skopeo the auth file
# the tool chose for the component (REGISTRY_AUTH_FILE, a file named for its
# component), docker the machine user's own login. The login's token is the role
# it was made for. Access, as the registry runbook's policy gives it:
#   candidates: read by any role; write and delete by builder only
#   releases:   read by controller, copier, host; write by copier only
# Every call is logged in $STUB_LOG_DIR/auth.log as "<tool> <op> <repo> <role>".

# stub_role_of_user USER -> the role a login made as USER is for
stub_role_of_user() {
  case "$1" in
    tenancy/user) echo any ;;   # S44's all-purpose canary user
    *builder*) echo builder ;; *releaser*|*copier*) echo copier ;; *controller*) echo controller ;; *) echo host ;;
  esac
}

# stub_auth_role TOOL -> the role of the login in use, or "none". skopeo uses the
# auth file REGISTRY_AUTH_FILE names; docker uses the machine user's own login,
# which the stub keeps in <machine root>/.docker/login.json (DOCKER_CONFIG is
# never set by the tool).
stub_auth_role() {
  if [[ "$1" == skopeo ]]; then
    local f="${REGISTRY_AUTH_FILE:-}"
    [[ -n "$f" && -f "$f" ]] || { echo none; return; }
    jq -r '[.auths[]?.auth][0] // "none"' "$f" 2>/dev/null || echo none
  else
    local f="${TURPIN_HOST_ROOT:-${STUB_LOCAL_ROOT:?}}/.docker/login.json"
    [[ -f "$f" ]] || { echo none; return; }
    jq -r '.role // "none"' "$f" 2>/dev/null || echo none
  fi
}

# stub_auth_check TOOL OP REPO ACCESS(read|write): exits 1 as a registry does
stub_auth_check() {
  local role; role="$(stub_auth_role "$1")"
  echo "$1 $2 $3 $role" >> "${STUB_LOG_DIR:?}/auth.log"
  [[ -n "${STUB_AUTH_ENFORCE:-}" ]] || return 0
  local ok=0 kind="${3##*/}"
  [[ "$role" == any ]] && ok=1
  case "$kind:$4:$role" in
    candidates:read:controller|candidates:read:builder|candidates:read:copier|candidates:read:host) ok=1 ;;
    candidates:write:builder) ok=1 ;;
    releases:read:controller|releases:read:copier|releases:read:host) ok=1 ;;
    releases:write:copier) ok=1 ;;
  esac
  [[ $ok -eq 1 ]] || { echo "denied: requested access to the resource is denied" >&2; exit 1; }
}
