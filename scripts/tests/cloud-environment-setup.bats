#!/usr/bin/env bats

# .claude/cloud-environment-setup.sh writes the user-level hooks a cloud thread
# runs (delphside/programme#176 R15). Run against a scratch CLAUDE_USER_DIR with
# the libraries skipped, so nothing outside the temporary folder changes.

bats_require_minimum_version 1.5.0

setup() {
  bats_load_library bats-support
  bats_load_library bats-assert
  # SETUP_UNDER_TEST names another copy of the script, to show a test red against it.
  SETUP="${SETUP_UNDER_TEST:-$BATS_TEST_DIRNAME/../../.claude/cloud-environment-setup.sh}"
  export CLAUDE_USER_DIR="$BATS_TEST_TMPDIR/user"
  export CLAUDE_SETUP_NO_PACKAGES=1
  WS="$BATS_TEST_TMPDIR/ws"
  mkdir -p "$WS"
}

hooks() {   # hooks <python expression over the settings s>
  python3 -c 'import json,sys; s=json.load(open(sys.argv[1])); print(eval(sys.argv[2]))' \
    "$CLAUDE_USER_DIR/settings.json" "$1"
}

# A stub application in the workspace whose pinned programme/ hook prints its
# own name, GH_REPO and the input it was given.
stub_app() {   # stub_app NAME
  local app="$WS/$1"
  mkdir -p "$app/programme/.claude/hooks"
  git init -q "$app"
  printf '#!/usr/bin/env bash\necho "%s $* GH_REPO=${GH_REPO-unset} $(cat)"\n' "$1" > "$app/programme/.claude/hooks/comment-check.sh"
  chmod +x "$app/programme/.claude/hooks/comment-check.sh"
}

# The wrapper, given a hook input: hook_run '<json with $WS for the workspace>' [hook]
hook_run() {
  local input="${1//@WS@/$WS}"
  run bash -c 'cd "$1" && echo "$3" | CLAUDE_PROJECT_DIR="$1" "$2/cloud-programme-hook.sh" "${4:-comment-check.sh}"' \
    _ "$WS" "$CLAUDE_USER_DIR" "$input" "${2:-}"
}

@test "it writes the three hooks, and exits 0" {
  run "$SETUP"
  assert_success
  run hooks 's["hooks"]["SessionStart"][0]["matcher"], "cloud-setup.sh" in s["hooks"]["SessionStart"][0]["hooks"][0]["command"]'
  assert_output "('startup|resume', True)"
  run hooks '[h["command"].split("/")[-1] for h in s["hooks"]["SessionStart"][1]["hooks"]]'
  assert_output "['cloud-programme-hook.sh inbox-hook.sh', 'cloud-programme-hook.sh --roles']"
  run hooks 's["hooks"]["PreToolUse"][0]["matcher"]'
  assert_output "Bash|mcp__github__add_issue_comment|mcp__github__add_reply_to_pull_request_comment|mcp__github__pull_request_review_write"
}

@test "a second run changes nothing, and keeps a setting that is not its own" {
  mkdir -p "$CLAUDE_USER_DIR"
  echo '{"model": "x", "hooks": {"Stop": [{"hooks": []}]}}' > "$CLAUDE_USER_DIR/settings.json"
  "$SETUP"
  cp "$CLAUDE_USER_DIR/settings.json" "$BATS_TEST_TMPDIR/first.json"
  run "$SETUP"
  assert_success
  run diff "$BATS_TEST_TMPDIR/first.json" "$CLAUDE_USER_DIR/settings.json"
  assert_success
  run hooks 's["model"], len(s["hooks"]["Stop"]), len(s["hooks"]["SessionStart"]), len(s["hooks"]["PreToolUse"])'
  assert_output "('x', 1, 2, 1)"
}

@test "a settings file that is not JSON is copied to settings.json.bak.<time>, and said on stderr" {
  mkdir -p "$CLAUDE_USER_DIR"
  echo 'not json' > "$CLAUDE_USER_DIR/settings.json"
  run --separate-stderr "$SETUP"
  assert_success
  local bak=("$CLAUDE_USER_DIR"/settings.json.bak.*)
  assert_equal "${#bak[@]}" 1
  assert_equal "$(cat "${bak[0]}")" "not json"
  [[ "$stderr" == *"${bak[0]}"* ]]
  run hooks 'len(s["hooks"]["PreToolUse"])'
  assert_output 1
}

@test "an existing backup is never overwritten: a second bad file gets a backup of its own" {
  mkdir -p "$CLAUDE_USER_DIR"
  echo 'first' > "$CLAUDE_USER_DIR/settings.json.bak"
  echo 'not json' > "$CLAUDE_USER_DIR/settings.json"
  "$SETUP"
  echo 'also not json' > "$CLAUDE_USER_DIR/settings.json"
  "$SETUP"
  assert_equal "$(cat "$CLAUDE_USER_DIR/settings.json.bak")" "first"
  local bak=("$CLAUDE_USER_DIR"/settings.json.bak.*)
  assert_equal "${#bak[@]}" 2
  run cat "${bak[@]}"
  assert_output --partial "also not json"
  assert_output --partial "not json"
}

@test "a settings.json that is a symlink stays one, its target is written, and its mode is kept" {
  mkdir -p "$CLAUDE_USER_DIR" "$BATS_TEST_TMPDIR/real"
  echo '{"model": "keep"}' > "$BATS_TEST_TMPDIR/real/settings.json"
  chmod 600 "$BATS_TEST_TMPDIR/real/settings.json"
  ln -s "$BATS_TEST_TMPDIR/real/settings.json" "$CLAUDE_USER_DIR/settings.json"
  run "$SETUP"
  assert_success
  [ -L "$CLAUDE_USER_DIR/settings.json" ]
  run python3 -c 'import json,sys; s=json.load(open(sys.argv[1])); print(s["model"], len(s["hooks"]["PreToolUse"]))' "$BATS_TEST_TMPDIR/real/settings.json"
  assert_output "keep 1"
  run stat -c %a "$BATS_TEST_TMPDIR/real/settings.json"
  assert_output 600
}

@test "a settings file of the wrong shape is left untouched, and said on stderr" {
  mkdir -p "$CLAUDE_USER_DIR"
  local bad
  for bad in '[]' '{"model":"keep","hooks":[]}' '{"model":"keep","hooks":{"PreToolUse":{}}}' \
             '{"model":"keep","hooks":{"SessionStart":"x"}}'; do
    echo "$bad" > "$CLAUDE_USER_DIR/settings.json"
    run --separate-stderr "$SETUP"
    assert_success
    assert_equal "$(cat "$CLAUDE_USER_DIR/settings.json")" "$bad"
    [[ "$stderr" == *"left untouched"* ]]
  done
}

@test "settings are written to a temporary file and renamed: none is left behind" {
  "$SETUP"
  run ls "$CLAUDE_USER_DIR"
  refute_output --partial "settings.json.tmp"
  assert_output --partial "settings.json"
}

@test "a write that fails part-way leaves the settings whole" {
  mkdir -p "$CLAUDE_USER_DIR/settings.json.tmp"      # the temporary file cannot be created
  echo '{"model": "keep"}' > "$CLAUDE_USER_DIR/settings.json"
  run --separate-stderr "$SETUP"
  assert_success
  assert_equal "$(cat "$CLAUDE_USER_DIR/settings.json")" '{"model": "keep"}'
  [[ "$stderr" == *"could not write"* ]]
}

@test "the hook runs the pinned programme of the repository the input's cwd is in, with the input" {
  stub_app one
  stub_app two
  "$SETUP"
  run bash -c 'echo "{\"cwd\": \"$1/two\", \"tool_name\": \"Bash\"}" | CLAUDE_PROJECT_DIR="$1" "$2/cloud-programme-hook.sh" comment-check.sh --flag' _ "$WS" "$CLAUDE_USER_DIR"
  assert_success
  assert_output --partial "two --flag GH_REPO=unset"
  assert_output --partial '"tool_name": "Bash"'
}

@test "with no cwd in a repository the default application's hooks run, not the first alphabetically" {
  stub_app aaa
  stub_app tile-lite-elite
  "$SETUP"
  hook_run '{}'
  assert_success
  assert_output --partial "tile-lite-elite  GH_REPO=unset"
}

@test "a cwd in another repository runs the default application's hooks with GH_REPO naming that repository" {
  stub_app tile-lite-elite
  mkdir -p "$WS/programme" "$WS/dark-portal"
  git init -q "$WS/programme"
  git -C "$WS/programme" remote add origin https://github.com/delphside/programme.git
  git init -q "$WS/dark-portal"
  git -C "$WS/dark-portal" remote add origin git@github.com:delphside/dark-portal.git
  "$SETUP"
  hook_run '{"cwd": "@WS@/programme"}'
  assert_success
  assert_output --partial "tile-lite-elite  GH_REPO=delphside/programme"
  hook_run '{"cwd": "@WS@/dark-portal"}'
  assert_output --partial "tile-lite-elite  GH_REPO=delphside/dark-portal"
}

@test "a cwd in an application's pinned programme/ submodule runs that application's hooks" {
  stub_app tile-lite-elite
  local pin="$BATS_TEST_TMPDIR/pin" app="$WS/zeta"
  mkdir -p "$pin/.claude/hooks" "$app"
  printf '#!/usr/bin/env bash\necho "zeta GH_REPO=${GH_REPO-unset}"\n' > "$pin/.claude/hooks/comment-check.sh"
  chmod +x "$pin/.claude/hooks/comment-check.sh"
  git init -q "$pin"
  git -C "$pin" add -A
  git -C "$pin" -c user.name=t -c user.email=t@t commit -q -m pin
  git init -q "$app"
  git -C "$app" -c protocol.file.allow=always submodule add -q "$pin" programme
  "$SETUP"
  hook_run '{"cwd": "@WS@/zeta/programme"}'
  assert_success
  assert_output "zeta GH_REPO=unset"
}

@test "a GitHub MCP tool picks the application from tool_input.repo, else the cwd" {
  stub_app one
  stub_app two
  "$SETUP"
  hook_run '{"cwd": "@WS@/one", "tool_name": "mcp__github__add_issue_comment", "tool_input": {"owner": "x", "repo": "two"}}'
  assert_output --partial "two  GH_REPO=unset"
  hook_run '{"cwd": "@WS@/one", "tool_name": "mcp__github__add_issue_comment", "tool_input": {"owner": "x"}}'
  assert_output --partial "one  GH_REPO=unset"
  hook_run '{"cwd": "@WS@/one", "tool_name": "mcp__github__add_issue_comment", "tool_input": {"repo": "two"}}'
  assert_output --partial "one  GH_REPO=unset"
}

@test "a GitHub MCP tool naming a repository without hooks runs the default application's" {
  stub_app one
  stub_app tile-lite-elite
  "$SETUP"
  hook_run '{"cwd": "@WS@/one", "tool_name": "mcp__github__add_issue_comment", "tool_input": {"owner": "x", "repo": "programme"}}'
  assert_output --partial "tile-lite-elite  GH_REPO=unset"
}

@test "with no programme anywhere the hook says so in one line and exits 0" {
  "$SETUP"
  hook_run '{}'
  assert_success
  assert_output "No application's pinned programme hooks were found beside the workspace, so comment-check.sh did not run."
}

@test "a cwd in the programme repository with no default application says so and exits 0" {
  mkdir -p "$WS/programme"
  git init -q "$WS/programme"
  "$SETUP"
  hook_run '{"cwd": "@WS@/programme"}'
  assert_success
  assert_output "No application's pinned programme hooks were found beside the workspace, so comment-check.sh did not run."
}

@test "--roles names the roles and the command that lists one role's items" {
  stub_app tile-lite-elite
  printf '#!/usr/bin/env bash\n' > "$WS/tile-lite-elite/programme/.claude/hooks/inbox-hook.sh"
  chmod +x "$WS/tile-lite-elite/programme/.claude/hooks/inbox-hook.sh"
  ln -s "$BATS_TEST_DIRNAME/../../scripts" "$WS/tile-lite-elite/programme/scripts"
  "$SETUP"
  run bash -c 'echo "{}" | CLAUDE_PROJECT_DIR="$1" "$2/cloud-programme-hook.sh" --roles' _ "$WS" "$CLAUDE_USER_DIR"
  assert_success
  assert_output --partial "does not know its role"
  assert_output --partial "demand-manager"
  assert_output --partial "board-actions.py --role <role>"
}

@test "each repository's programme/ submodule is fetched before any session starts" {
  local pin="$BATS_TEST_TMPDIR/pin" src="$BATS_TEST_TMPDIR/src"
  export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=protocol.file.allow GIT_CONFIG_VALUE_0=always
  mkdir -p "$pin/.claude/hooks"
  printf '#!/usr/bin/env bash\necho pinned\n' > "$pin/.claude/hooks/inbox-hook.sh"
  chmod +x "$pin/.claude/hooks/inbox-hook.sh"
  git init -q "$pin" && git -C "$pin" add -A
  git -C "$pin" -c user.name=t -c user.email=t@t commit -q -m pin
  git init -q "$src"
  git -C "$src" submodule add -q "$pin" programme
  git -C "$src" -c user.name=t -c user.email=t@t commit -q -m app
  git clone -q "$src" "$WS/tile-lite-elite"
  mkdir -p "$WS/notes"
  [ ! -e "$WS/tile-lite-elite/programme/.claude/hooks/inbox-hook.sh" ]
  CLAUDE_SETUP_WORKSPACE="$WS" run "$SETUP"
  assert_success
  [ -x "$WS/tile-lite-elite/programme/.claude/hooks/inbox-hook.sh" ]
  hook_run '{}' inbox-hook.sh
  assert_output "pinned"
}
