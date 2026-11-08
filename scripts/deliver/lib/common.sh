#!/usr/bin/env bash
# common.sh: what `deliver`, `deliver-host` and the payload's steps share.
# Sourced, never executed. Design: records/2.5-changes/programme-tooling/117-generic-deliver-tool/design.md
#
# It holds: messages and exits, the run log, the gate list (a gate is named when
# it runs, and a command that ends with one unrun refuses), the flags that set a
# gate aside, and the hook runner. It names no application and no machine.

# Exit codes (design §4): 0 done; 1 refused or failed; 3 live, a later step failed.
EXIT_REFUSED=1
EXIT_PARTIAL=3

DELIVER_CMD="${DELIVER_CMD:-deliver}"
RUN_LOG="${RUN_LOG:-}"
GATES_EXPECTED=()
GATES_RAN=()
SET_ASIDE=()        # "gate<TAB>reason"
OVERRIDES=()        # "flag<TAB>reason", for the run log

say()  { printf '%s\n' "$*"; }
warn() { printf '%s: %s\n' "$DELIVER_CMD" "$*" >&2; }
die()  { warn "$*"; exit "$EXIT_REFUSED"; }

need_jq() { command -v jq >/dev/null 2>&1 || die "jq is required"; }

now_utc() { date -u +%Y-%m-%dT%H:%M:%SZ; }

# ---------------------------------------------------------------- run log

# run_log_start APP COMMAND [ARGS...]: one file per run on this machine, newest
# last, the last 20 per command kept. Identifiers only: never a secret.
run_log_start() {
  local app="$1" cmd="$2"; shift 2
  local dir="${DELIVER_LOG_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/deliver}/$app"
  mkdir -p "$dir" 2>/dev/null || { RUN_LOG=""; return 0; }
  RUN_LOG="$dir/$cmd-$(date -u +%Y%m%dT%H%M%S).$$.log"
  : > "$RUN_LOG"
  run_log_event start "args=$*"
  # shellcheck disable=SC2012
  ls -1t "$dir"/"$cmd"-*.log 2>/dev/null | tail -n +21 | while read -r old; do rm -f "$old"; done
  trap '_run_log_exit $?' EXIT
}
# A caller that needs its own exit work calls _run_log_exit last.

_run_log_exit() {
  local code="$1"
  run_log_event exit "code=$code"
}

run_log_event() {   # EVENT [key=value...]
  [[ -n "$RUN_LOG" ]] || return 0
  local event="$1"; shift
  local args=(--arg t "$(now_utc)" --arg event "$event")
  local expr='{t:$t,event:$event}'
  local pair key
  for pair in "$@"; do
    key="${pair%%=*}"
    args+=(--arg "k_$key" "${pair#*=}")
    expr+=" + {\"$key\": \$k_$key}"
  done
  jq -nc "${args[@]}" "$expr" >> "$RUN_LOG" 2>/dev/null || true
}

# ---------------------------------------------------------------- gates

gates_expect() { GATES_EXPECTED=("$@"); }

# On a host the controller reads the gate lines from stderr (GATE_EMIT=1).
gate_emit() { [[ "${GATE_EMIT:-0}" != 1 ]] || printf '@gate %s %s\n' "$1" "$2" >&2; }

gate_ok() {        # NAME [detail]
  GATES_RAN+=("$1")
  run_log_event gate "name=$1" "result=passed" "detail=${2:-}"
  gate_emit "$1" passed
}

# A check that passes and has something to say (an emergency's unticked tests):
# shown to the person and recorded as `reported`, not as plain `passed`.
gate_report() {    # NAME message
  GATES_RAN+=("$1")
  run_log_event gate "name=$1" "result=reported" "detail=$2"
  gate_emit "$1" passed
  say "check $1: $2"
}

gate_fail() {      # NAME message
  GATES_RAN+=("$1")
  run_log_event gate "name=$1" "result=refused" "detail=$2"
  gate_emit "$1" refused
  warn "refused at gate $1: $2"
  exit "$EXIT_REFUSED"
}

# gate_set_aside NAME: true when --set-aside named this gate and the profile
# allows it (OVERRIDABLE is the profile's [release].overridable). Records it.
gate_set_aside() {
  local name="$1" entry
  for entry in "${SET_ASIDE[@]}"; do
    [[ "${entry%%$'\t'*}" == "$name" ]] || continue
    case " ${OVERRIDABLE:-} " in
      *" $name "*) ;;
      *) return 1 ;;
    esac
    GATES_RAN+=("$name")
    run_log_event gate "name=$name" "result=set-aside" "reason=${entry#*$'\t'}"
    gate_emit "$name" set-aside
    SET_ASIDE_USED+=("$entry")
    return 0
  done
  return 1
}
SET_ASIDE_USED=()

set_aside_requested() {   # NAME: was it named at all (overridable or not)?
  local entry
  for entry in "${SET_ASIDE[@]}"; do [[ "${entry%%$'\t'*}" == "$1" ]] && return 0; done
  return 1
}

# gates_finish: a command that ends with a gate of its list unrun refuses.
gates_finish() {
  local want ran missing=()
  for want in "${GATES_EXPECTED[@]}"; do
    local found=0
    for ran in "${GATES_RAN[@]}"; do [[ "$ran" == "$want" ]] && { found=1; break; }; done
    [[ $found -eq 1 ]] || missing+=("$want")
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    run_log_event gates-unrun "names=${missing[*]}"
    die "ended with gates unrun: ${missing[*]}"
  fi
}

# ---------------------------------------------------------------- flags

# take_reason FLAG VALUE...: a flag that sets a gate aside takes a reason.
reason_ok() {      # VALUE
  [[ -n "${1:-}" && "$1" != --* ]]
}

# parse_common_flag: handles the flags every command shares. Sets OPT_*.
# Usage in a loop: parse_common_flag "$@" && { shift "$PARSED"; continue; }
OPT_CHECK=0
OPT_WAIT=""
PARSED=0
parse_common_flag() {
  case "$1" in
    --check) OPT_CHECK=1; PARSED=1 ;;
    --wait) OPT_WAIT=60; PARSED=1 ;;
    --wait=*) OPT_WAIT="${1#--wait=}"; [[ "$OPT_WAIT" =~ ^[0-9]+$ ]] || die "--wait takes minutes"; PARSED=1 ;;
    --set-aside)
      [[ -n "${2:-}" && "${2:-}" != --* ]] || die "--set-aside takes a gate and a reason"
      reason_ok "${3:-}" || die "--set-aside $2 needs a reason"
      SET_ASIDE+=("$2"$'\t'"$3"); OVERRIDES+=("set-aside:$2"$'\t'"$3"); PARSED=3 ;;
    *) return 1 ;;
  esac
}

# reason_flag FLAG VALUE: record an override flag's reason or refuse.
reason_flag() {
  reason_ok "${2:-}" || die "$1 needs a reason"
  OVERRIDES+=("$1"$'\t'"$2")
  run_log_event override "flag=$1" "reason=$2"
}

# ---------------------------------------------------------------- hooks

HOOK_NOT_YET=75

# hook_env_export: the variables a hook receives (design §5). The caller sets
# H_APP H_ENV H_ROLE H_SHA H_VERSION H_STATE and H_IMAGES (name=ref lines).
hook_env_export() {
  export DELIVER_APP="$H_APP" DELIVER_ENV="$H_ENV" DELIVER_ROLE="$H_ROLE"
  export DELIVER_SHA="$H_SHA" DELIVER_VERSION="$H_VERSION" DELIVER_STATE="$H_STATE"
  local line name
  while IFS='=' read -r name line; do
    [[ -n "$name" ]] || continue
    name="$(printf '%s' "$name" | tr 'a-z-' 'A-Z_')"
    export "DELIVER_IMAGE_$name=$line"
  done <<< "${H_IMAGES:-}"
}

# hook_run NAME: run hooks/NAME from $HOOKS_DIR. Returns the hook's own exit code
# (0 passed, 75 not yet, other refused). A missing hook is a no-op (0) unless it
# is in REQUIRED_HOOKS, where missing or not executable refuses (exit 1 via die).
hook_run() {
  local name="$1" path="${HOOKS_DIR:-/nonexistent}/$1" required=0
  case " ${REQUIRED_HOOKS:-} " in *" $name "*) required=1 ;; esac
  if [[ ! -e "$path" ]]; then
    [[ $required -eq 0 ]] && { run_log_event hook "name=$name" "result=absent"; return 0; }
    run_log_event hook "name=$name" "result=missing-required"
    HOOK_REFUSAL="required hook $name is missing"; return 1
  fi
  if [[ ! -x "$path" ]]; then
    if [[ $required -eq 1 ]]; then
      run_log_event hook "name=$name" "result=not-executable"
      HOOK_REFUSAL="required hook $name is not executable"; return 1
    fi
    run_log_event hook "name=$name" "result=not-executable-optional"
    return 0
  fi
  hook_env_export
  local code=0
  "$path" || code=$?
  run_log_event hook "name=$name" "result=exit-$code"
  return "$code"
}
HOOK_REFUSAL=""

# hook_gate NAME: a hook that is a gate. With --wait, 75 retries each minute.
# A set-aside hook (profile-overridable, named by --set-aside) is passed on.
hook_gate() {
  # one --wait budget covers the lock and this hook: what the lock used is spent
  local name="$1" code=0 waited="${DELIVER_WAIT_USED:-0}" limit="${OPT_WAIT:-}"
  local unit="${DELIVER_WAIT_UNIT:-60}"
  while :; do
    code=0; hook_run "$name" || code=$?
    [[ $code -eq 0 ]] && { gate_ok "$name"; return 0; }
    if [[ -n "$HOOK_REFUSAL" ]]; then
      gate_fail "$name" "$HOOK_REFUSAL"
    fi
    if [[ $code -eq $HOOK_NOT_YET && -n "$limit" ]]; then
      if (( waited >= limit )); then
        gate_fail "$name" "still not yet after waiting $limit minute(s) for hook $name"
      fi
      sleep "$unit"; waited=$((waited + 1)); continue
    fi
    if gate_set_aside "$name"; then return 0; fi
    if set_aside_requested "$name"; then
      gate_fail "$name" "hook $name refused (exit $code) and the profile does not list it in overridable"
    fi
    if [[ $code -eq $HOOK_NOT_YET ]]; then gate_fail "$name" "hook $name says not yet (exit 75); use --wait to wait"; fi
    gate_fail "$name" "hook $name refused (exit $code)"
  done
}

# hook_step NAME: a step; any non-zero exit is a failure the caller handles.
hook_step() {
  local code=0
  hook_run "$1" || code=$?
  [[ -z "$HOOK_REFUSAL" ]] || { warn "$HOOK_REFUSAL"; return 1; }
  return "$code"
}

# ---------------------------------------------------------------- small helpers

sha256_of() { sha256sum | cut -d' ' -f1; }

# image_var NAME: DELIVER_IMAGE_<NAME> for the compose file's ${...}.
image_var() { printf 'DELIVER_IMAGE_%s' "$(printf '%s' "$1" | tr 'a-z-' 'A-Z_')"; }

semver_gt() {      # A B: is A strictly greater than B
  [[ "$1" != "$2" && "$(printf '%s\n%s\n' "$1" "$2" | sort -V | tail -1)" == "$1" ]]
}

host_root() { printf '%s' "${DELIVER_HOST_ROOT:-}"; }
