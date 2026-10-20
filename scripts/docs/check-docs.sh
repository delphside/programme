#!/usr/bin/env bash
set -uo pipefail

# check-docs.sh — the documentation's own gate: lint, links, and placement.
#
# 4.3.3's rule, applied to itself: *"wherever a rule can be checked by the
# tooling, check it there — a rule in a document is advisory; a rule in a gate
# is real."* Every check here was being run by hand, which means run when
# remembered, which is how #137 shipped 81 broken anchors into a branch and
# found them by luck.
#
# The application's own facts (what the linter skips, the grandfathered change
# documents, its own checks) come from its technical profile, `app-profile.toml`,
# through `board-profile.py` (#485); nothing here names an application.
#
# One script, called by `.github/workflows/docs.yml`, so the check you make
# before pushing and the one the pull request enforces are the same code — the
# same reason `ci-status.sh` is shared between `deploy.sh` and the terminal.
#
# The first three checks, each reported separately and all of them run even when an
# earlier one fails, because "fix one, discover the next" wastes a lap:
#
#   1. markdownlint  — the house style in .markdownlint.jsonc
#   2. links         — every `](#anchor)` resolves (programme/scripts/docs/check-doc-links.py)
#   3. placement     — the folder convention settled on #156, and the numbering
#                      of the documents in docs/ (4.1 to 4.4, three levels)
#
# Exits non-zero if any check failed, except the placement of the programme's
# change documents (step 3), which is reported only **in an application**.
#
# **Two places it runs** (#485 stage 2):
#
#   - from an application's `programme/` submodule, over the application's own
#     documents: `programme/scripts/docs/check-docs.sh`. This is the default.
#   - from the programme repository on its own, `scripts/docs/check-docs.sh
#     --programme`, over the programme's markdown (CI of the programme). There is
#     no application there, so what reads one (the technical profile's lint
#     ignores, the document map, the application's own checks, the history signals)
#     says it does not apply instead of passing silently, and the placement of the
#     programme's change documents is a gate, because they are its own.
#     Those steps are tested against a fixture application in
#     `scripts/tests/check-docs-placement.bats`.

SELF="$(cd "$(dirname "$0")" && pwd)"
PROG="$(cd "$SELF/../.." && pwd)"
PROGRAMME_ONLY=0
[[ "${1:-}" == "--programme" ]] && PROGRAMME_ONLY=1
if (( PROGRAMME_ONLY )); then
  HERE="$PROG"
  # The programme file is this repository's own, not a pinned copy of it.
  export PROGRAMME_CONFIG="${PROGRAMME_CONFIG:-$PROG/config/programme.toml}"
else
  # The application is the repository we are run in, by the rule `board/profile.py`
  # applies: the superproject's working tree when run inside a submodule, else the
  # top level of the working tree. Not where this script sits, so the same copy
  # serves the pre-commit hook of any repository and a fixture application.
  HERE="$(git rev-parse --show-superproject-working-tree 2>/dev/null)"
  [[ -n "$HERE" ]] || HERE="$(git rev-parse --show-toplevel 2>/dev/null)"
fi
[[ -n "$HERE" ]] && cd "$HERE" || { echo "check-docs: not inside a git working tree, so the application's root cannot be found"; exit 1; }
PROFILE="$SELF/../board/board-profile.py"

bold() { printf '\033[1m%s\033[0m\n' "$1"; }
FAILED=0

# Pinned, and the same globs CI used before this script existed — the linter is
# otherwise "whatever is in one machine's npx cache", which is not a dependency
# anybody declared. Agents' worktrees under .claude/worktrees/ are copies of the
# repository, so they are skipped (#441). In an application so is the `programme/`
# submodule: its documents are checked in the programme repository, not as ours,
# and so are the skills and agents linked from `.claude/` into it (#485). CI
# checks the live programme checkout out at `.programme-live/`, also skipped. In
# the programme itself the skills and agents are its own, and are linted.
bold "1. markdownlint"
# What else the linter skips is the application's: the technical profile's `documents.lint_ignore`.
# (Read into a variable first: the status of a process substitution is lost.)
APP_IGNORE=()
if (( PROGRAMME_ONLY )); then
  SKIP=("#.claude/worktrees" "#**/node_modules")
else
  if IGNORED="$("$PROFILE" get documents.lint_ignore)"; then
    mapfile -t APP_IGNORE <<< "$IGNORED"
  else
    echo "  cannot read documents.lint_ignore from the technical profile"
    FAILED=1
  fi
  SKIP=("#.claude/worktrees" "#programme" "#.programme-live" "#.claude/skills" "#.claude/agents")
fi
npx --yes markdownlint-cli2@0.23.2 "**/*.md" "${APP_IGNORE[@]}" "${SKIP[@]}" 2>&1 | tail -4 || FAILED=1

bold "2. links"
if (( PROGRAMME_ONLY )); then
  python3 "$SELF/check-doc-links.py" 'docs/**/*.md' '*.md' 'records/**/*.md' 'applications/**/*.md' '.claude/**/*.md' || FAILED=1
else
  python3 "$SELF/check-doc-links.py" || FAILED=1
fi

# The convention (#156): design documents live in an issue folder named for the
# issue that owns them — or for the parent issue where there is a workstream —
# and testing documents live in a release folder. Both under this application's
# change documents, `3.n.7-changes/` in the programme repository's live checkout
# (`PROGRAMME_DIR`, see `board/records.py`; #485), which is where they moved to.
# A missing checkout fails the check, saying where it looked: a placement check
# that finds no documents because it looked nowhere would report everything in
# place.
#
# **What it finds in the programme's content is reported, not gated, in an
# application.** Those documents belong to the programme repository, so a stray
# one there must not turn this application's CI red. **In the programme
# repository (`--programme`) it is a gate**, over every change-documents folder
# it holds: `records/2.5-changes/` and each application's `3.n.7-changes/`.
#
# The documents already in a flat folder stay there: GitHub does not follow a
# rename and several issue comments point at them. They are listed rather than
# pattern-matched so that the list can only shrink. The list is each
# application's programme profile's, the `## Grandfathered change documents` table
# (`board-profile.py grandfathered <profile>`), file names inside its
# `3.n.7-changes/`. An application reads its own through the loader; the
# programme repository reads every `applications/*/3.*.6-*.md` it holds, because
# it must know them without any application. A folder's `README.md` is not a
# change document, so it needs no listing.
bold "3. placement"
placement_strays() {   # <programme root> <folder>...: prints each stray, returns 1 if any
  local root="$1" folder file rel keep old stray=0
  shift
  for folder in "$@"; do
    if [[ ! -d "$folder" ]]; then
      echo "  MISSING $folder — no change documents folder"
      stray=1
      continue
    fi
    while IFS= read -r file; do
      [[ "$file" == README.md ]] && continue
      rel="${folder#"$root"/}/$file"
      keep=0
      for old in "${GRANDFATHERED[@]}"; do [[ "$rel" == "$old" ]] && keep=1 && break; done
      (( keep )) && continue
      echo "  STRAY   $file (in $folder)"
      echo "          → workstreams/<workstream>/<issue>-<name>/ for a design"
      echo "            releases/<version>/ for a testing document (#156)"
      stray=1
    done < <(find "$folder" -maxdepth 1 -name '*.md' -printf '%f\n' 2>/dev/null | sort)
  done
  return "$stray"
}
if (( PROGRAMME_ONLY )); then
  GRANDFATHERED=()
  FOLDERS=("$HERE/records/2.5-changes")
  READ_OK=1
  for folder in "$HERE"/applications/*/3.*.7-changes; do
    [[ -d "$folder" ]] || continue
    FOLDERS+=("$folder")
    app="$(dirname "$folder")"
    profile_file=("$app"/3.*.6-*.md)
    # An application folder with no profile has no grandfathered list, so none of
    # its change documents is exempt: every one at the top of its folder is a stray.
    # (Infrastructure has a change-documents folder and no profile yet: it is checked
    # with an empty list, and fails only if a document is put at the top of it.)
    [[ ! -e "${profile_file[0]}" ]] && continue
    if [[ ${#profile_file[@]} -ne 1 ]]; then
      echo "  AMBIGUOUS several programme profiles in $app (3.n.6-*.md)"
      READ_OK=0
      continue
    fi
    if ! KEEP="$("$PROFILE" grandfathered "${profile_file[0]}")"; then
      READ_OK=0
      continue
    fi
    while IFS= read -r name; do
      [[ -n "$name" ]] && GRANDFATHERED+=("${folder#"$HERE"/}/$name")
    done <<< "$KEEP"
  done
  if (( READ_OK )) && placement_strays "$HERE" "${FOLDERS[@]}"; then
    echo "  every change document is in an issue or release folder"
  else
    FAILED=1
  fi
elif LIVE="$("$SELF/../board/board-records.py" live)" \
   && CHANGES="$("$SELF/../board/board-records.py" change-documents)" \
   && KEEP="$("$PROFILE" get profile.grandfathered_changes)"; then
  GRANDFATHERED=()
  while IFS= read -r name; do
    [[ -n "$name" ]] && GRANDFATHERED+=("${CHANGES#"$LIVE"/}/$name")
  done <<< "$KEEP"
  if placement_strays "$LIVE" "$CHANGES"; then
    echo "  every change document is in an issue or release folder"
  else
    echo "  (reported only: the programme's content does not fail this application's check)"
  fi
else
  FAILED=1
fi

# An application's documents are R.G.N in the programme's one numbering, R its
# document range: R.1 overview, R.2 design, R.3 development and operation, R.4
# reference. document-map.py holds the pattern, so the map and this gate cannot
# disagree. The programme's own documents are numbered by its docs/1.5 and are
# not an application's range, so there is nothing for it to read.
if (( PROGRAMME_ONLY )); then
  echo "  not applicable here: the programme's documents are not an application's range"
elif "$SELF/document-map.py" --names; then
  echo "  every document in docs/ is named R.G.N (G in 1-4, R the document range) or is the README"
else
  FAILED=1
fi

# 4. the document map is derived, so a stale one is always wrong and always
# fixed by regenerating. A **gate**, unlike step 7 (a measure): there is no judgement in it
# and no writing to do, only `document-map.py --write`.
#
# It was wired into nothing until 2026-09-11 — not this script, not the
# pre-commit hook, not CI, not verify.sh — so `docs/4.1.6` went stale silently.
# Found by ticking #349's own box asking whether the map lists every heading:
# it did not, because the commit before it added ten and did not regenerate.
# A derived artefact with no check is the shape #326 and #340 are also about.
echo
bold "4. the document map"
if (( PROGRAMME_ONLY )); then
  echo "  not applicable here: the map is an application's, read through its technical profile"
elif MAP_OUT="$("$SELF/document-map.py" --check 2>&1)"; then
  echo "  the document map lists every heading in every document"
elif [[ "$MAP_OUT" == *"is out of date"* ]]; then
  echo "  STALE   the document map (the technical profile's documents.map)"
  echo "          → run programme/scripts/docs/document-map.py --write and commit it"
  FAILED=1
else
  # Not staleness (an unreadable profile, a duplicate heading, a misnamed
  # document): regenerating would not help, so show what it said.
  echo "  FAILED  the document map could not be checked:"
  printf '%s\n' "$MAP_OUT" | sed 's/^/          /'
  FAILED=1
fi

# 5. The application's own checks, from the technical profile's `hooks.check_docs`,
# run in the order given. A **gate**: each is a rule about the application's own
# content (Tile Lite Elite's: every API error documented, every script log event
# declared), and a failure fails this script. Run bare, as 6 is: piping one
# through `sed` to indent it reported `sed`'s exit status and nothing else,
# which is how it could be a gate and still never fail.
echo
bold "5. the application's checks"
if (( PROGRAMME_ONLY )); then
  echo "  not applicable here: they are an application's, the technical profile's hooks.check_docs"
  CHECKS=""
elif ! CHECKS="$("$PROFILE" get hooks.check_docs)"; then
  echo "  cannot read hooks.check_docs from the technical profile"
  FAILED=1
  CHECKS=""
fi
# Each entry is a block of `name=value` lines and an empty line (board-profile.py),
# read by name, so key order and empty values cannot shift one into another.
CHECK_NAME="" CHECK_COMMAND=""
run_check() {
  [[ -n "$CHECK_NAME$CHECK_COMMAND" ]] || return 0
  if [[ -z "$CHECK_NAME" || -z "$CHECK_COMMAND" ]]; then
    echo "  an entry of hooks.check_docs lacks its name or command: '$CHECK_NAME' '$CHECK_COMMAND'"
    FAILED=1
  else
    echo "  $CHECK_NAME"
    # shellcheck disable=SC2086 # the command is a path and its arguments
    if ! "$HERE/"$CHECK_COMMAND; then FAILED=1; fi
  fi
  CHECK_NAME="" CHECK_COMMAND=""
}
while IFS= read -r line; do
  case "$line" in
    name=*) CHECK_NAME="${line#name=}" ;;
    command=*) CHECK_COMMAND="${line#command=}" ;;
    "") run_check ;;
  esac
done <<< "$CHECKS"
run_check

# 6. mermaid — #340. markdownlint sees a fenced block as opaque, so a diagram
# that does not parse renders as an error box on GitHub and is caught by
# nothing. Mermaid's own grammar is used, because only it agrees with what
# GitHub renders.
#
# **A gate where it can run, silent where it cannot.** The parse needs `mermaid`
# and `jsdom` -- 146MB, six seconds to install -- and whether CI pays that is
# still open on #340. So a machine that has them enforces the check, and one
# that does not says so and passes. The pins live in the mermaid folder's package.json.
bold "6. mermaid diagrams"
if ! node "$SELF/mermaid/check.mjs"; then FAILED=1; fi

# 7. history signals -- #427 R8. A measure, not a gate: the lines in the
# numbered documents carrying a phrase that marks history or argument (the programme's docs/1.5).
# It reports and never fails, because a phrase can be used legitimately; a
# person reads the list. It should fall. Run bare, as 5 and 6 are.
echo
bold "7. history signals (a measure; --list in doc-signals.py shows them)"
if (( PROGRAMME_ONLY )); then
  echo "  not applicable here: it reads an application's numbered documents"
else
  "$SELF/doc-signals.py"
fi

# 8. design map -- delphside/tile-lite-elite#406. The generated design map is
# current when the hash of docs/design-map/ in its header matches. Plain
# Python, no Docker: only `design-map.py --write` runs the Structurizr image.
echo
bold "8. design map"
if (( PROGRAMME_ONLY )); then
  echo "  not applicable here: it reads an application's design map"
elif ! "$SELF/design-map/design-map.py" --check; then
  echo "          → run programme/scripts/docs/design-map/design-map.py --write and commit it"
  FAILED=1
fi

echo
if (( FAILED )); then
  bold "FAILED"
else
  bold "OK"
fi
exit "$FAILED"
