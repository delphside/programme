#!/usr/bin/env bats

# .claude/cloud-environment-setup.sh writes the user-level hooks a cloud thread
# runs (delphside/programme#176 R15). Run against a scratch CLAUDE_USER_DIR with
# the libraries skipped, so nothing outside the temporary folder changes.

setup() {
  bats_load_library bats-support
  bats_load_library bats-assert
  SETUP="$BATS_TEST_DIRNAME/../../.claude/cloud-environment-setup.sh"
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
# own name, the working directory it ran in and the input it was given.
stub_app() {   # stub_app NAME
  local app="$WS/$1"
  mkdir -p "$app/programme/.claude/hooks"
  git init -q "$app"
  printf '#!/usr/bin/env bash\necho "%s $* $(cat)"\n' "$1" > "$app/programme/.claude/hooks/comment-check.sh"
  chmod +x "$app/programme/.claude/hooks/comment-check.sh"
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

@test "a settings file that is not JSON is replaced, not a failure" {
  mkdir -p "$CLAUDE_USER_DIR"
  echo 'not json' > "$CLAUDE_USER_DIR/settings.json"
  run "$SETUP"
  assert_success
  run hooks 'len(s["hooks"]["PreToolUse"])'
  assert_output 1
}

@test "the hook runs the pinned programme of the repository the input's cwd is in, with the input" {
  stub_app one
  stub_app two
  "$SETUP"
  run bash -c 'echo "{\"cwd\": \"$1/two\", \"tool_name\": \"Bash\"}" | CLAUDE_PROJECT_DIR="$1" "$2/cloud-programme-hook.sh" comment-check.sh --flag' _ "$WS" "$CLAUDE_USER_DIR"
  assert_success
  assert_output --partial "two --flag "
  assert_output --partial '"tool_name": "Bash"'
}

@test "with no cwd in a repository the first one with a programme submodule is used" {
  stub_app one
  "$SETUP"
  run bash -c 'echo "{}" | CLAUDE_PROJECT_DIR="$1" "$2/cloud-programme-hook.sh" comment-check.sh' _ "$WS" "$CLAUDE_USER_DIR"
  assert_success
  assert_output --partial "one  "
}

@test "with no programme anywhere the hook says so and exits 0" {
  "$SETUP"
  run bash -c 'echo "{}" | CLAUDE_PROJECT_DIR="$1" "$2/cloud-programme-hook.sh" comment-check.sh' _ "$WS" "$CLAUDE_USER_DIR"
  assert_success
  assert_output --partial "hooks were not found"
}

@test "--roles names the roles and the command that lists one role's items" {
  mkdir -p "$WS/programme/.claude/hooks"
  printf '#!/usr/bin/env bash\n' > "$WS/programme/.claude/hooks/inbox-hook.sh"
  chmod +x "$WS/programme/.claude/hooks/inbox-hook.sh"
  ln -s "$BATS_TEST_DIRNAME/../../scripts" "$WS/programme/scripts"
  "$SETUP"
  run bash -c 'echo "{}" | CLAUDE_PROJECT_DIR="$1" "$2/cloud-programme-hook.sh" --roles' _ "$WS" "$CLAUDE_USER_DIR"
  assert_success
  assert_output --partial "does not know its role"
  assert_output --partial "coordinator"
  assert_output --partial "board-actions.py --role <role>"
}
