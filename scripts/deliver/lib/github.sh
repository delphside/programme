#!/usr/bin/env bash
# github.sh: every call `deliver` makes to GitHub, through `gh api` alone, so a
# test can stub the one command. Reads are GETs or named GraphQL queries; the
# writes are the milestone, the issues, the board's Project State, and the
# Release. Needs GH_REPO (owner/name) set by the caller.

Q_MILESTONE_ITEMS='query MilestoneItems($owner: String!, $name: String!, $title: String!) {
  repository(owner: $owner, name: $name) {
    milestones(first: 5, query: $title) { nodes { number title state
      issues(first: 100, states: OPEN) { nodes { number
        issueType { name }
        parent { number }
        subIssues(first: 1) { totalCount }
        projectItems(first: 3) { nodes { fieldValueByName(name: "Route") { ... on ProjectV2ItemFieldSingleSelectValue { name } } } }
      } } } } } }'

Q_ISSUE_INFO='query IssueInfo($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) { issue(number: $number) {
    number state issueType { name } parent { number } milestone { title }
    subIssues(first: 1) { totalCount }
    projectItems(first: 3) { nodes { fieldValueByName(name: "Route") { ... on ProjectV2ItemFieldSingleSelectValue { name } } } }
  } } }'

Q_PROJECT_STATE='query ProjectState($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) { issue(number: $number) {
    projectItems(first: 3) { nodes { id
      project { id field(name: "Project State") { ... on ProjectV2SingleSelectField { id options { id name } } } }
      fieldValueByName(name: "Project State") { ... on ProjectV2ItemFieldSingleSelectValue { name } } } } } } }'

M_SET_PROJECT_STATE='mutation SetProjectState($project: ID!, $item: ID!, $field: ID!, $option: String!) {
  updateProjectV2ItemFieldValue(input: {projectId: $project, itemId: $item, fieldId: $field, value: {singleSelectOptionId: $option}}) { projectV2Item { id } } }'

gh_owner() { printf '%s' "${GH_REPO%%/*}"; }
gh_name()  { printf '%s' "${GH_REPO##*/}"; }

# gh_repo_slug: GH_REPO from the environment, else the origin URL.
gh_repo_slug() {
  if [[ -n "${DELIVER_GH_REPO:-}" ]]; then GH_REPO="$DELIVER_GH_REPO"; return 0; fi
  local url; url="$(git -C "$REPO" remote get-url origin 2>/dev/null)" || return 1
  [[ "$url" == *github.com* ]] || return 1
  GH_REPO="$(printf '%s' "$url" | sed -E 's#^.*github\.com[:/]##; s#\.git$##')"
}

gh_check_runs() {      # SHA -> JSON {check_runs:[{name,conclusion}]}
  gh api "repos/$GH_REPO/commits/$1/check-runs?per_page=100"
}

# gh_milestone_items VERSION -> JSON array of the open issues in the milestone:
# {number,type,parent,subs,route}; "null" if there is no such milestone.
gh_milestone_items() {
  local out
  out="$(gh api graphql -f query="$Q_MILESTONE_ITEMS" -F owner="$(gh_owner)" -F name="$(gh_name)" -F title="$1")" || return 1
  jq -c --arg t "$1" '[.data.repository.milestones.nodes[] | select(.title == $t)] | if length == 0 then null else
    .[0].issues.nodes | map({number, type: (.issueType.name // ""), parent: (.parent.number // null),
      subs: (.subIssues.totalCount // 0), route: (([.projectItems.nodes[].fieldValueByName.name // empty] | .[0]) // "")}) end' <<< "$out"
}

gh_issue_info() {      # N -> {number,state,type,parent,milestone,subs,route} or null
  local out
  out="$(gh api graphql -f query="$Q_ISSUE_INFO" -F owner="$(gh_owner)" -F name="$(gh_name)" -F number="$1")" || return 1
  jq -c '.data.repository.issue | if . == null then null else
    {number, state, type: (.issueType.name // ""), parent: (.parent.number // null),
     milestone: (.milestone.title // null), subs: (.subIssues.totalCount // 0),
     route: (([.projectItems.nodes[].fieldValueByName.name // empty] | .[0]) // "")} end' <<< "$out"
}

gh_milestones() {      # -> JSON array [{number,title,state}]
  gh api "repos/$GH_REPO/milestones?state=all&per_page=100"
}
gh_milestone_number() {  # TITLE -> number or empty
  gh_milestones | jq -r --arg t "$1" '[.[] | select(.title == $t)] | .[0].number // empty'
}
gh_milestone_create()  { gh api -X POST "repos/$GH_REPO/milestones" -f title="$1" >/dev/null; }
gh_milestone_close()   { gh api -X PATCH "repos/$GH_REPO/milestones/$1" -f state=closed >/dev/null; }
gh_issue_set_milestone() { gh api -X PATCH "repos/$GH_REPO/issues/$1" -F milestone="$2" >/dev/null; }
gh_issue_comments()    { gh api "repos/$GH_REPO/issues/$1/comments?per_page=100"; }
gh_issue_comment()     { gh api -X POST "repos/$GH_REPO/issues/$1/comments" -f body="$2" >/dev/null; }
gh_issue_close()       { gh api -X PATCH "repos/$GH_REPO/issues/$1" -f state=closed -f state_reason=completed >/dev/null; }
gh_issue_create()      { gh api -X POST "repos/$GH_REPO/issues" -f title="$1" -f body="$2" >/dev/null; }
gh_release_exists()    { gh api "repos/$GH_REPO/releases/tags/$1" >/dev/null 2>&1; }
gh_release_create()    {   # TAG PREV_TAG
  local args=("$1" --repo "$GH_REPO" --verify-tag --title "$1" --generate-notes)
  [[ -z "${2:-}" ]] || args+=(--notes-start-tag "$2")
  gh release create "${args[@]}" >/dev/null
}

# gh_project_state N -> the current Project State name (or empty).
gh_project_state() {
  gh api graphql -f query="$Q_PROJECT_STATE" -F owner="$(gh_owner)" -F name="$(gh_name)" -F number="$1" \
    | jq -r '.data.repository.issue.projectItems.nodes[0].fieldValueByName.name // empty'
}
# gh_set_project_state N NAME
gh_set_project_state() {
  local out item project field option
  out="$(gh api graphql -f query="$Q_PROJECT_STATE" -F owner="$(gh_owner)" -F name="$(gh_name)" -F number="$1")" || return 1
  item="$(jq -r '.data.repository.issue.projectItems.nodes[0].id // empty' <<< "$out")"
  project="$(jq -r '.data.repository.issue.projectItems.nodes[0].project.id // empty' <<< "$out")"
  field="$(jq -r '.data.repository.issue.projectItems.nodes[0].project.field.id // empty' <<< "$out")"
  option="$(jq -r --arg n "$2" '.data.repository.issue.projectItems.nodes[0].project.field.options[] | select(.name == $n) | .id' <<< "$out" | head -1)"
  [[ -n "$item" && -n "$project" && -n "$field" && -n "$option" ]] || return 1
  gh api graphql -f query="$M_SET_PROJECT_STATE" -F project="$project" -F item="$item" -F field="$field" -F option="$option" >/dev/null
}
