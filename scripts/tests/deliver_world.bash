# Shared by scripts/tests/deliver-*.bats: builds, per test, the world the
# deliver tool runs in (test-design.md part 8), with nothing from the network.
#
#   - a git repository "work" with a bare remote, holding a dummy application,
#     "acme": two images, a payload image, stub hooks that log what they are
#     given and exit as each test sets, a second environment `join`, host files;
#   - stubs on PATH for skopeo, docker, ssh, gh, sudo, systemctl, useradd,
#     userdel and curl (scripts/tests/deliver-stubs/), answering from folders;
#   - three "machines" as folders: the control node (`local`), `rehearsal` and
#     `prod`, reached through the ssh stub, each with its own docker state.
#
# `load deliver_world`, then `world_new` in setup.

DELIVER_SRC="$(cd "$BATS_TEST_DIRNAME/../deliver" && pwd)"
DELIVER="$DELIVER_SRC/deliver"
DELIVER_HOST="$DELIVER_SRC/deliver-host"
STUBS_SRC="$(cd "$BATS_TEST_DIRNAME/deliver-stubs" && pwd)"

world_new() {
  W="$BATS_TEST_TMPDIR"
  mkdir -p "$W/bin" "$W/registry" "$W/hosts/local" "$W/hosts/rehearsal" "$W/hosts/prod" "$W/logs" "$W/gh" "$W/home" "$W/hookctl" "$W/xdg"
  cp "$STUBS_SRC"/* "$W/bin/"
  ln -sf "$DELIVER_HOST" "$W/bin/deliver-host"
  ln -sf "$DELIVER" "$W/bin/deliver"
  export PATH="$W/bin:$PATH"
  export HOME="$W/home" XDG_STATE_HOME="$W/xdg"
  export STUB_REGISTRY="$W/registry" STUB_LOG_DIR="$W/logs" STUB_HOSTS="$W/hosts" STUB_LOCAL_ROOT="$W/hosts/local" STUB_GH="$W/gh"
  export DELIVER_HOST_ROOT="$W/hosts/local" DELIVER_STATE_DIR=/var/lib/deliver
  export DELIVER_REPO="$W/work" DELIVER_GH_REPO=acme/acme DELIVER_WAIT_UNIT=1
  export HOOKLOG="$W/hook.log" HOOKCTL="$W/hookctl"
  export GIT_AUTHOR_NAME=Test GIT_AUTHOR_EMAIL=t@example.test GIT_COMMITTER_NAME=Test GIT_COMMITTER_EMAIL=t@example.test
  export DELIVER_REGISTRY_VALUE="reg.test/ns"
  mkdir -p "$HOME/.config/deliver"
  printf 'DELIVER_REGISTRY=%s\n' "$DELIVER_REGISTRY_VALUE" > "$HOME/.config/deliver/acme.env"
  : > "$HOOKLOG"
  local h
  for h in local rehearsal prod; do
    mkdir -p "$W/hosts/$h/var/lib/deliver/acme"
  done
  host_env local preview; host_env rehearsal rehearsal; host_env prod production
  : > "$W/gh/log"
  git init -q --bare "$W/remote.git"
  git init -q -b main "$W/work"
  git -C "$W/work" remote add origin "$W/remote.git"
  write_app
  cd "$W/work" || return 1
  git add -A && git commit -q -m "app 0.10.2 api 1.0: first" && git push -q origin main
  SHA="$(git rev-parse HEAD)"
}

# host_env HOST ENVNAME: the machine's .env, holding its registry (and a canary secret).
host_env() {
  local d="$W/hosts/$1/var/lib/deliver/acme/$2"
  mkdir -p "$d"
  printf 'DELIVER_REGISTRY=%s\nCANARY_SECRET=%s\n' "$DELIVER_REGISTRY_VALUE" "${CANARY:-hunter2-canary}" > "$d/.env"
}

# write_app: the dummy application, in the work tree.
write_app() {
  cd "$W/work" || return 1
  mkdir -p deliver/hooks ops
  cat > app-profile.toml <<'EOF'
application = "acme"

[versions]
stamp = '^app ([0-9]+\.[0-9]+\.[0-9]+) api ([0-9]+\.[0-9]+): (.+)'
stamp_form = "app <X.Y.Z> api <M.N>: <subject>"

[versions.app]
file = "app.toml"
pattern = '^version = "([^"]+)"'

[versions.api]
file = "api.txt"
pattern = '^api = "([^"]+)"'

[versions.bump]
files = ["app.toml"]
required = ["app.toml"]

[versions.deployed]
path = "/health"
field = "app_version"

[release]
tag_prefix = "v"
history_prefixes = ["prod-"]
announcement = "Released in v"
deploy_marker = "[deliver]"
required_checks = ["e2e"]
required_hooks = ["pre-deploy", "save-state", "migrate", "smoke", "restore-state", "release-check"]
overridable = ["milestone", "pre-deploy", "release-check"]

[deliver]
candidates = "acme/candidates"
releases = "acme/releases"
images = ["server", "web"]
payload_image = "server"
keep_images = ["acme-server:latest"]
join = ["docker-compose.yml", "Caddyfile"]
fallback = "stop the deliver project, restore the snapshot, run the old script"

[deliver.build]
on = "control-node"
login = "docker-config"

[deliver.release]
copy_on = "control-node"
copy_login = "docker-config"

[deliver.ephemeral]
user_prefix = "acme-"
home = "/srv/acme"
secrets = ["ACME_SECRET"]

[[deliver.host_files]]
src = "ops/backup.sh"
dest = "/opt/acme/backup.sh"
mode = "0755"

[[deliver.host_files]]
src = "ops/acme-backup.timer"
dest = "/etc/systemd/system/acme-backup.timer"
mode = "0644"
enable = true

[environments.preview]
role = "preview"
host = "control-node"
join = ["docker-compose.preview.yml", "Caddyfile.preview"]

[environments.rehearsal]
role = "rehearsal"
ssh = "rehearsal"
login = "docker-config"
pull_timeout = 60

[environments.production]
role = "production"
ssh = "prod"
login = "docker-config"
url = "http://prod.test"
EOF
  printf 'version = "0.10.2"\n' > app.toml
  printf 'api = "1.0"\n' > api.txt
  printf 'content one\n' > src.txt
  printf 'services: {}\n' > docker-compose.yml
  printf 'services: {preview: {}}\n' > docker-compose.preview.yml
  printf ':80 { respond "acme" }\n' > Caddyfile
  printf ':8080 { respond "preview" }\n' > Caddyfile.preview
  printf '#!/bin/sh\necho backup\n' > ops/backup.sh
  printf '[Timer]\nOnCalendar=daily\n' > ops/acme-backup.timer
  local hook
  for hook in pre-deploy save-state migrate smoke restore-state release-check post-deploy env-create env-destroy; do
    cat > "deliver/hooks/$hook" <<'EOF'
#!/usr/bin/env bash
# A stub hook: logs its name, its DELIVER_* environment and its arguments, then
# exits as $HOOKCTL/<name> says: empty or absent = 0; "N" = exit N; "N COUNT" =
# exit N for the first COUNT calls, then 0; "kill" = kill the parent (a deploy
# interrupted at this step).
name="$(basename "$0")"
{ echo "== $name $*"; env | grep '^DELIVER_' | grep -v '^DELIVER_REQUEST' | sort; } >> "${HOOKLOG:-/dev/null}"
ctl="${HOOKCTL:-/nonexistent}/$name"
[[ -s "$ctl" ]] || exit 0
read -r mode count < "$ctl"
if [[ "$mode" == kill ]]; then kill -9 "$PPID"; sleep 1; exit 137; fi
if [[ -n "$count" ]]; then
  seen="$ctl.seen"; n=0; [[ -f "$seen" ]] && n="$(cat "$seen")"
  if (( n >= count )); then exit 0; fi
  echo $((n + 1)) > "$seen"
fi
exit "$mode"
EOF
    chmod +x "deliver/hooks/$hook"
  done
}

# commit_all MESSAGE: commit the work tree and push main; SHA is the commit.
commit_all() {
  git -C "$W/work" add -A && git -C "$W/work" commit -q --allow-empty -m "$1" && git -C "$W/work" push -q origin main
  SHA="$(git -C "$W/work" rev-parse HEAD)"
}

# commit_change MESSAGE: a change to src.txt (a new image content), pushed.
commit_change() {
  printf '%s\n' "$1 $RANDOM" > "$W/work/src.txt"
  commit_all "$1"
}

set_version() {   # VERSION: in app.toml (the work tree; not committed)
  printf 'version = "%s"\n' "$1" > "$W/work/app.toml"
}

hook_exit() { printf '%s\n' "$2" > "$HOOKCTL/$1"; rm -f "$HOOKCTL/$1.seen"; }   # NAME "N [COUNT]" | kill
hook_clear() { rm -f "$HOOKCTL/$1" "$HOOKCTL/$1.seen"; }

# ---- running the tool

d() { ( cd "$W/work" && "$DELIVER" "$@" ); }

build_ok() {      # [REF]: build, expect success
  run d build "${1:-HEAD}"
  [ "$status" -eq 0 ] || { echo "build failed: $output" >&2; return 1; }
}

# ---- reading what the stubs recorded

reg_tag_digest() { cat "$W/registry/reg.test/ns/$1/tags/$2" 2>/dev/null; }   # REPO TAG
cand() { reg_tag_digest acme/candidates "$1"; }                               # SHA-IMAGE
rel() { reg_tag_digest acme/releases "$1"; }
reg_meta() { cat "$W/registry/reg.test/ns/$1/meta/${2#sha256:}.json"; }       # REPO DIGEST

host_state_dir() { printf '%s/hosts/%s/var/lib/deliver/acme/%s' "$W" "$1" "$2"; }   # HOST ENV
host_state() { head -1 "$(host_state_dir "$1" "$2")/state" 2>/dev/null; }
host_current() { basename "$(readlink "$(host_state_dir "$1" "$2")/current" 2>/dev/null)" 2>/dev/null; }
host_previous() { basename "$(readlink "$(host_state_dir "$1" "$2")/previous" 2>/dev/null)" 2>/dev/null; }

hook_calls() { grep '^== ' "$HOOKLOG" | awk '{print $2}'; }
hook_log_for() { awk -v n="$1" '/^== /{p=($2==n)} p' "$HOOKLOG"; }
gh_log() { cat "$W/gh/log"; }
run_log_latest() { ls -1t "$XDG_STATE_HOME"/deliver/acme/"$1"-*.log | head -1; }
run_log_gates() { jq -r 'select(.event=="gate") | .name' "$(run_log_latest "$1")" | sort -u | tr '\n' ' '; }

# snapshot of everything a refused command must leave alone (outcome O1)
snapshot() {
  {
    (cd "$W/registry" && find . -type f | sort | xargs -r sha256sum)
    (cd "$W/hosts" && find . -path '*/.docker' -prune -o -path '*/log' -prune -o -type f -not -name '.systemctl.log' -print | sort | xargs -r sha256sum 2>/dev/null)
    (cd "$W/hosts" && find . -path '*/.docker/compose/*' -type f | sort | xargs -r sha256sum 2>/dev/null)
    git -C "$W/work" for-each-ref
    git -C "$W/remote.git" for-each-ref
    cat "$W/gh/log"
  } 2>/dev/null | sha256sum
}

# ---- a deployed world

deploy_rehearsal() {   # REF [more args]: deploy to rehearsal, off level (the first cycle)
  local ref="$1"; shift
  run d deploy rehearsal "$ref" --off-level "test world" "$@"
}

gh_fixture() { printf '%s\n' "$2" > "$W/gh/fix/$1.json"; }    # NAME JSON
gh_checks() {   # SHA name=conclusion...
  local sha="$1"; shift
  local json='{"check_runs":[]}' kv
  for kv in "$@"; do json="$(jq -c --arg n "${kv%%=*}" --arg c "${kv#*=}" '.check_runs += [{name:$n,conclusion:$c}]' <<< "$json")"; done
  gh_fixture "repos_acme_acme_commits_${sha}_check-runs" "$json"
}
# gh_milestone VERSION "number|type|parent|subs|route" ...
gh_milestone() {
  local version="$1"; shift
  local nodes='[]' row n t p s r
  for row in "$@"; do
    IFS='|' read -r n t p s r <<< "$row"
    nodes="$(jq -c --argjson n "$n" --arg t "$t" --arg p "$p" --argjson s "$s" --arg r "$r" '. + [{number:$n,
      issueType:(if $t=="" then null else {name:$t} end), parent:(if $p=="" then null else {number:($p|tonumber)} end),
      subIssues:{totalCount:$s}, projectItems:{nodes:[{fieldValueByName:(if $r=="" then null else {name:$r} end)}]}}]' <<< "$nodes")"
  done
  jq -nc --arg v "$version" --argjson nodes "$nodes" '{data:{repository:{milestones:{nodes:[{number:7,title:$v,state:"OPEN",issues:{nodes:$nodes}}]}}}}' > "$W/gh/fix/graphql_MilestoneItems.json"
}
# gh_issue N type parent milestone subs route [state]
gh_issue() {
  local n="$1" t="$2" p="$3" m="$4" s="$5" r="$6" st="${7:-OPEN}"
  jq -nc --argjson n "$n" --arg t "$t" --arg p "$p" --arg m "$m" --argjson s "$s" --arg r "$r" --arg st "$st" '{data:{repository:{issue:{number:$n,state:$st,
    issueType:(if $t=="" then null else {name:$t} end), parent:(if $p=="" then null else {number:($p|tonumber)} end),
    milestone:(if $m=="" then null else {title:$m} end), subIssues:{totalCount:$s},
    projectItems:{nodes:[{fieldValueByName:(if $r=="" then null else {name:$r} end)}]}}}}}' > "$W/gh/fix/graphql_IssueInfo-$n.json"
}
# gh_project N: the board item for a work package, currently in STATE
gh_project() {
  jq -nc --argjson n "$1" --arg s "${2:-Development}" '{data:{repository:{issue:{projectItems:{nodes:[{id:("PVTI_"+($n|tostring)),
    project:{id:"PVT_1",field:{id:"FLD_1",options:[{id:"opt-dev",name:"Development"},{id:"opt-post",name:"Post-deployment"}]}},
    fieldValueByName:{name:$s}}]}}}}}' > "$W/gh/fix/graphql_ProjectState-$1.json"
}

# ---- more helpers

# expected_digest SHA IMAGE: what the stub's bake makes of the commit's own content.
expected_digest() {
  local content; content="$(git -C "$W/work" show "$1:src.txt")"
  printf 'sha256:%s' "$(printf '%s|%s|%s' "$content" "$2" "$1" | sha256sum | cut -d' ' -f1)"
}

bake_count() { grep -c . "$W/logs/bake.log" 2>/dev/null || echo 0; }

# lock_hold HOST ENV: hold that environment's lock in the background (LOCK_PID).
lock_hold() {
  local f; f="$(host_state_dir "$1" "$2")/lock"; mkdir -p "$(dirname "$f")"
  ( exec 9>>"$f"; flock -n 9 && sleep 60 ) &
  LOCK_PID=$!
  sleep 0.3
}
lock_release() { kill "$LOCK_PID" 2>/dev/null; wait "$LOCK_PID" 2>/dev/null || true; }

# drop_timer_from_profile: the profile without the second host file (the timer).
drop_timer_from_profile() {
  awk 'BEGIN{n=0} /^\[\[deliver.host_files\]\]/{n++} n==2 && /^\[environments/{n=3} n!=2{print}' "$W/work/app-profile.toml" > "$W/work/app-profile.new"
  mv "$W/work/app-profile.new" "$W/work/app-profile.toml"
}

# a built and deployed commit: new content, pushed, built, deployed to REHEARSAL (off level)
new_build() {   # MESSAGE -> SHA
  commit_change "${1:-change}"
  build_ok "$SHA" || return 1
}

# the numbers in the host's `docker` compose state for a project
running_digests_of() {   # HOST PROJECT
  local f
  for f in "$W/hosts/$1/.docker/compose/$2".*; do [[ -f "$f" ]] && sed 's/^.*@//' "$f"; done | sort | tr '\n' ' '
}
digests_of() {   # SHA -> sorted candidate digests of both images
  { cand "$1-server"; cand "$1-web"; } | sort | tr '\n' ' '
}
