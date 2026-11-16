#!/usr/bin/env bash
# common.sh: what `turpin`, `turpin-host` and the payload's steps share.
# Sourced, never executed. Design: records/2.5-changes/programme-tooling/117-generic-deliver-tool/design.md
#
# It holds: messages and exits, the run log, the gates a host reports, the way a
# request sets one aside, and the hook runner. It names no application and no
# machine. The client's own are in `turpinlib`.

# Exit codes (design §6): 0 done; 1 refused or failed; 3 live, a later step failed.
EXIT_REFUSED=1
EXIT_FUNDAMENTAL=2
# shellcheck disable=SC2034  # read by payload/deploy, which sources this file
EXIT_PARTIAL=3

TURPIN_CMD="${TURPIN_CMD:-turpin}"
RUN_LOG="${RUN_LOG:-}"
SET_ASIDE=()        # "gate<TAB>reason"

EXIT_BLIP=75
EXIT_INTERRUPTED=130

# The request's notes (design section 11, the last request): on a host, turpin-host sets
# TURPIN_NOTE to a file of the running request's, and the payload's steps inherit it. One
# line each, tab separated: what the person was told (O), the gates run (G NAME RESULT) and
# the reason of the latest stop (R KIND REASON MESSAGE, KIND `gate` or `error`; F marks a
# restore that failed). turpin-host reads them once, at the end, to record the outcome and to
# send the controller the result object. Without TURPIN_NOTE nothing is noted.
note() { [[ -n "${TURPIN_NOTE:-}" ]] || return 0; local IFS=$'\t'; printf '%s\n' "$*" >> "$TURPIN_NOTE" 2>/dev/null || true; }
note_result() { note R "$1" "$2" "$(printf '%s' "$3" | tr '\t\n' '  ')"; }   # KIND REASON MESSAGE

# A write that fails (the connection dropped) is the end of the request's input, taken as an
# interruption at the next look, not as an error (design section 6).
input_ended() { if on_host; then : > "$TURPIN_INTERRUPT_FILE" 2>/dev/null || true; fi; return 0; }
say()  { printf '%s\n' "$*" || input_ended; note O "$(printf '%s' "$*" | tr '\t\n' '  ')"; }
warn() { printf '%s: %s\n' "$TURPIN_CMD" "$*" >&2 || input_ended; }
# A stop's reason is a member of the `Reason` enumeration in turpinlib/model.py, named for
# one call by a `REASON=` before `die`, `gate_fail` or `fundamental`; without one, the stop has the type's general reason.
die()  { warn "$*"; note_result error "${REASON:-HOST_REFUSED}" "$*"; exit "$EXIT_REFUSED"; }

# fundamental MESSAGE: stopped by a technical error that only a person can put right (exit 2).
fundamental() { warn "$*"; note_result error "${REASON:-HOST_FUNDAMENTAL}" "$*"; exit "$EXIT_FUNDAMENTAL"; }

# blip_stop MESSAGE: stopped by a blip, to try again later (exit 75).
blip_stop() { warn "$*"; note_result error "${REASON:-HOST_BLIP}" "$*"; exit "$EXIT_BLIP"; }

# unexpected_stop MESSAGE: stopped by something that was not expected, to raise as an issue (exit 70).
unexpected_stop() { warn "$*"; note_result error "${REASON:-HOST_UNEXPECTED}" "$*"; exit 70; }

# The notes, read at the end of a request (design section 11, the last request).
# result_from_notes CODE: the request's result object, docs/1.10's, from the exit status and
# the latest stop's reason noted.
result_from_notes() {
  [[ -f "${TURPIN_NOTE:-}" ]] || { printf '{}'; return 0; }
  jq -Rnc --argjson code "$1" '
    [inputs | split("\t")] as $n
    | ([$n[] | select(.[0] == "R")] | last) as $r
    | ([$n[] | select(.[0] == "O")] | last) as $o
    | (if $code == 0 then {outcome: "ok", type: null, blip: null, reason: "", message: ($o[1] // "")}
       else ({"1": "business", "2": "technical", "3": "technical", "75": "technical", "130": "technical"}[($code | tostring)] // "unexpected") as $t
         | {outcome: (if $code == 3 then "error" else "fatal" end), type: $t,
            blip: (if $t == "technical" then ($code == 75 or $code == 130) else null end),
            reason: ($r[2] // ({"1": "HOST_REFUSED", "2": "HOST_FUNDAMENTAL", "3": "HOST_PRUNE_FAILED", "75": "HOST_BLIP", "130": "HOST_INTERRUPTED"}[($code | tostring)] // "HOST_UNEXPECTED")),
            message: ($r[3] // "the host stopped with exit \($code)")}
       end)
    + {domain: "turpin", metadata: {}, violations: []}' < "$TURPIN_NOTE"
}
# gates_from_notes: the gates the request ran, as [{name, result}].
gates_from_notes() {
  [[ -f "${TURPIN_NOTE:-}" ]] || { printf '[]'; return 0; }
  jq -Rnc '[inputs | split("\t") | select(.[0] == "G") | {name: .[1], result: .[2]}]' < "$TURPIN_NOTE"
}
# notes_refusal_kind: `refused` where the latest stop was a gate's and no restore failed, else `failed`.
notes_refusal_kind() {
  [[ -f "${TURPIN_NOTE:-}" ]] || { printf failed; return 0; }
  jq -Rnr '[inputs | split("\t")] as $n
    | if any($n[]; .[0] == "F") then "failed"
      elif ([$n[] | select(.[0] == "R")] | last | .[1]) == "gate" then "refused" else "failed" end' < "$TURPIN_NOTE"
}

# on_host: running as turpin-host or its payload, which look for an interruption.
on_host() { [[ -n "${TURPIN_INTERRUPT_FILE:-}" ]]; }
# interrupted_now: the request's input has ended (design section 6, Interruption): the
# watcher wrote the request's own file, keyed by turpin-host's process id.
interrupted_now() { on_host && [[ -e "$TURPIN_INTERRUPT_FILE" ]]; }
# interrupt_stop WHERE: starts no further step; exit 130.
interrupt_stop() {
  warn "interrupted $1: no further step is started"
  note_result error HOST_INTERRUPTED "interrupted $1: no further step is started"
  exit "$EXIT_INTERRUPTED"
}
# look_for_interruption WHERE: stops if the input has ended.
look_for_interruption() { ! interrupted_now || interrupt_stop "$1"; }
# wait_unit: one wait of the `--wait` clock (TURPIN_WAIT_UNIT seconds, 60 by default), in
# slices of one second with a look at each.
wait_unit() {
  local unit="${TURPIN_WAIT_UNIT:-60}" i
  for (( i = 0; i < unit; i++ )); do sleep 1; if interrupted_now; then return 1; fi; done
  return 0
}

need_jq() { command -v jq >/dev/null 2>&1 || die "jq is required"; }

now_utc() { date -u +%Y-%m-%dT%H:%M:%SZ; }

# ---------------------------------------------------------------- run log

# run_log_start APP COMMAND [ARGS...]: one file per run on this machine, newest
# last, the last 20 per command kept. Identifiers only: never a secret.
run_log_start() {
  local app="$1" cmd="$2"; shift 2
  local dir="${TURPIN_LOG_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/turpin}/$app"
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

# On a host the controller reads the gate lines from stderr (GATE_EMIT=1).
gate_emit() {
  note G "$1" "$2"
  [[ "${GATE_EMIT:-0}" != 1 ]] || printf '@gate %s %s\n' "$1" "$2" >&2 || input_ended
}

gate_ok() {        # NAME [detail]
  run_log_event gate "name=$1" "result=passed" "detail=${2:-}"
  gate_emit "$1" passed
}

gate_fail() {      # NAME message
  run_log_event gate "name=$1" "result=refused" "detail=$2"
  gate_emit "$1" refused
  warn "refused at gate $1: $2"
  note_result gate "${REASON:-HOST_GATE_REFUSED}" "refused at gate $1: $2"
  exit "$EXIT_REFUSED"
}

# gate_blip NAME message: a gate that could not be passed for now: refused as a blip (exit 75).
gate_blip() {
  run_log_event gate "name=$1" "result=refused" "detail=$2"
  gate_emit "$1" refused
  warn "refused at gate $1: $2"
  note_result gate "${REASON:-HOST_BLIP}" "refused at gate $1: $2"
  exit "$EXIT_BLIP"
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

# The minutes a hook that says "not yet" is waited for: the request's `wait`, set by the payload's steps.
OPT_WAIT=""

# ---------------------------------------------------------------- hooks

HOOK_NOT_YET=75

# hook_env_export: the variables a hook receives (design §8). The caller sets
# H_APP H_ENV H_ROLE H_SHA H_VERSION H_STATE H_URL and H_IMAGES (name=ref lines).
hook_env_export() {
  export TURPIN_APP="$H_APP" TURPIN_ENV="$H_ENV" TURPIN_ROLE="$H_ROLE"
  export TURPIN_SHA="$H_SHA" TURPIN_VERSION="$H_VERSION" TURPIN_STATE="$H_STATE" TURPIN_URL="${H_URL:-}"
  # the deploy a hook is part of, from step 7 on (design §8): the caller sets H_DEPLOY, and the
  # folder and the Compose command line follow from it, in one place (`compose_line`). H_CURRENT
  # is `save-state`'s alone.
  if [[ -n "${H_DEPLOY:-}" ]]; then
    local dir line
    dir="$(deploy_dir "$H_DEPLOY")"; line="$(compose_line "$H_DEPLOY")"
    export TURPIN_DEPLOY="$H_DEPLOY" TURPIN_DEPLOY_DIR="$dir" TURPIN_COMPOSE="$line"
  else
    unset TURPIN_DEPLOY TURPIN_DEPLOY_DIR TURPIN_COMPOSE
  fi
  if [[ -n "${H_CURRENT:-}" ]]; then export TURPIN_CURRENT="$H_CURRENT"; else unset TURPIN_CURRENT; fi
  local line name
  while IFS='=' read -r name line; do
    [[ -n "$name" ]] || continue
    name="$(printf '%s' "$name" | tr 'a-z-' 'A-Z_')"
    export "TURPIN_IMAGE_$name=$line"
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
    HOOK_REFUSAL="required hook $name is missing"; HOOK_REFUSAL_REASON=HOOK_MISSING; return 1
  fi
  if [[ ! -x "$path" ]]; then
    if [[ $required -eq 1 ]]; then
      run_log_event hook "name=$name" "result=not-executable"
      HOOK_REFUSAL="required hook $name is not executable"; HOOK_REFUSAL_REASON=HOOK_NOT_EXECUTABLE; return 1
    fi
    run_log_event hook "name=$name" "result=not-executable-optional"
    return 0
  fi
  hook_env_export
  local code=0
  "$path" </dev/null || code=$?
  run_log_event hook "name=$name" "result=exit-$code"
  return "$code"
}
HOOK_REFUSAL=""
HOOK_REFUSAL_REASON=""

# hook_gate NAME: a hook that is a gate. With --wait, 75 retries each minute.
# A set-aside hook (profile-overridable, named by --set-aside) is passed on.
hook_gate() {
  # one --wait budget covers the lock and this hook: what the lock used is spent
  local name="$1" code=0 waited="${TURPIN_WAIT_USED:-0}" limit="${OPT_WAIT:-}"
  while :; do
    look_for_interruption "before hook $name"
    code=0; hook_run "$name" || code=$?
    [[ $code -eq 0 ]] && { gate_ok "$name"; return 0; }
    if [[ -n "$HOOK_REFUSAL" ]]; then
      REASON="$HOOK_REFUSAL_REASON" gate_fail "$name" "$HOOK_REFUSAL"
    fi
    if [[ $code -eq $HOOK_NOT_YET && -n "$limit" ]]; then
      if (( waited >= limit )); then
        hook_not_yet "$name" "still not yet after waiting $limit minute(s) for hook $name"
      fi
      if ! wait_unit; then interrupt_stop "while waiting for hook $name"; fi
      waited=$((waited + 1)); continue
    fi
    if gate_set_aside "$name"; then return 0; fi
    if set_aside_requested "$name"; then
      REASON=HOOK_REFUSED gate_fail "$name" "hook $name refused (exit $code) and the profile does not list it in overridable"
    fi
    if [[ $code -eq $HOOK_NOT_YET ]]; then hook_not_yet "$name" "hook $name says not yet (exit 75); use --wait to wait"; fi
    REASON=HOOK_REFUSED gate_fail "$name" "hook $name refused (exit $code)"
  done
}

# hook_not_yet NAME MESSAGE: on a host a hook's `not yet` that is not waited for any further is a
# blip (exit 75, the request recorded interrupted, to be run again); elsewhere it refuses.
hook_not_yet() {
  if on_host; then REASON=HOOK_NOT_YET gate_blip "$1" "$2"; else gate_fail "$1" "$2"; fi
}

# hook_step NAME: a step; any non-zero exit is a failure the caller handles.
hook_step() {
  local code=0
  hook_run "$1" || code=$?
  [[ -z "$HOOK_REFUSAL" ]] || { warn "$HOOK_REFUSAL"; return 1; }
  return "$code"
}

# ---------------------------------------------------------------- compose

# Compose runs as the deploy does, from one place: the project name, `--project-directory` the
# deploy's folder, the host's `.env` then `turpin.env`, and the deploy's joined compose files
# (design §11). The deploy, a hook's TURPIN_COMPOSE and `turpin-host compose` all take it from here.
# They need ENVDIR (the state folder) and PROJECT.
deploy_dir()  { printf '%s/deploys/%s' "${ENVDIR:?}" "$1"; }

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
# compose_line N: the same as one command line, each word quoted for the shell (a hook runs it
# with `eval "$TURPIN_COMPOSE" ARGS` or `bash -c`).
compose_line() {
  local a line="docker"
  while IFS= read -r -d '' a; do line+=" $(printf '%q' "$a")"; done < <(compose_args "$1")
  printf '%s' "$line"
}

# ---------------------------------------------------------------- small helpers

# image_var NAME: TURPIN_IMAGE_<NAME> for the compose file's ${...}.
image_var() { printf 'TURPIN_IMAGE_%s' "$(printf '%s' "$1" | tr 'a-z-' 'A-Z_')"; }

# ---------------------------------------------------------------- the host's record

# state.json is the host's whole record (design §11): state, current, previous,
# pending, target, installed_host_files and last_request, a field absent where it
# has no value. Two functions touch the file, so the layout lives in one place:
# state_get reads it whole and state_save replaces it whole, by a write and a
# rename. state_put is the edit of one write: a jq filter over the record read.

state_file() { printf '%s/state.json' "${1:?}"; }

state_get_raw() {   # ENVDIR: the record as written, empty where there is none
  local f; f="$(state_file "$1")"
  if [[ -f "$f" ]]; then cat "$f"; fi
}

state_get() {   # ENVDIR: the record, {} where the host has none
  local raw; raw="$(state_get_raw "$1")"
  if [[ -n "$raw" ]]; then printf '%s\n' "$raw"; else printf '{}\n'; fi
}

state_save() {  # ENVDIR JSON: the record, replaced whole by rename; "" removes it (none)
  local f tmp; f="$(state_file "$1")"
  if [[ -z "$2" ]]; then rm -f -- "$f"; return 0; fi
  tmp="$(mktemp "$f.XXXXXX")"
  printf '%s\n' "$2" > "$tmp"
  mv -f -- "$tmp" "$f"
}

state_put() {   # ENVDIR FILTER [jq args...]: one write of the record the filter makes of the one read
  local envdir="$1" filter="$2" new; shift 2
  new="$(state_get "$envdir" | jq -c "$@" "$filter")"
  state_save "$envdir" "$new"
}

state_field() { state_get "$1" | jq -r --arg f "$2" '.[$f] // empty'; }   # ENVDIR NAME

# state_layout_what ENVDIR: what marks a folder as the Bash turpin's layout (a `state` file or a
# `current` link, and no state.json), empty where it is not.
state_layout_what() {
  local envdir="$1"
  [[ ! -f "$(state_file "$envdir")" ]] || return 0
  if [[ -e "$envdir/state" ]]; then printf 'the file %s/state' "$envdir"
  elif [[ -L "$envdir/current" ]]; then printf 'the link %s/current' "$envdir"; fi
  return 0
}

# state_layout_check ENVDIR: such a folder is refused, exit 2: nothing says what it ran.
state_layout_check() {
  local envdir="$1" what
  what="$(state_layout_what "$envdir")"
  [[ -z "$what" ]] || REASON=STATE_LAYOUT_BASH fundamental "$what is the Bash turpin's layout and there is no state.json: nothing says what it ran, so clear $envdir's state by hand"
}

# state_layout_check_all DIR...: the same for each environment folder given.
state_layout_check_all() {
  local d
  for d in "$@"; do
    [[ -d "$d" ]] || continue
    state_layout_check "${d%/}"
  done
}

# state_admits_deploy STATE: the state gate of design §9 and §11's table.
state_admits_deploy() {
  case "$1" in ""|"preparing: "*|finished|restored|"failed, no previous deploy") return 0 ;; *) return 1 ;; esac
}

host_root() { printf '%s' "${TURPIN_HOST_ROOT:-}"; }
