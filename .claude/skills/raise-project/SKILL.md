---
name: raise-project
description: Raise a project issue with the seven headings, set its fields and fold the requirements it takes. Use when a project is being raised, or a requirement is being converted into one.
---

# Raising a project

The mechanics only. **What goes in the project is a judgement**, set by
`CLAUDE.md` and
[1.2](../../../docs/1.2-change-lifecycle.md) and agreed with the owner.

The order: agree the grouping, write the body, create the issue, set its
fields, fold its requirements, regenerate the *context header* (the generated
block at the top of an issue, see *Afterwards*) and check.

## Before anything

**Triage follows `CLAUDE.md`**: joint with the owner, except where Claude
triages alone. Where triage is joint and the grouping has not been agreed, ask
the owner. Raising a project folds and closes requirements, which is hard to
reverse.

**Straight to project is allowed** when the change certainly needs doing and how
it is grouped or split into projects is decided: no requirement needs raising
first.

**Converting a requirement** is raising the project and folding the requirement
into it, as in *Folding the requirements it takes*. Its body is never
rewritten into the project's
([1.2 §2.11](../../../docs/1.2-change-lifecycle.md#211-what-a-project-is)), and
it keeps its type.

## The seven headings

A project with no parent and no sub-projects is a *standalone project*, which
carries all seven and a `Route`. A parent and a work package owe different
halves:

| Heading | Parent | Work package |
| --- | --- | --- |
| Requirements | owns | links |
| Design | owns | links, adding only what is its own |
| Non-functional design | owns | answers, or points at the parent's |
| Test approach | points at its packages' | owns |
| Dependencies and related work | owns | links |
| Deliveries | owns the list, each row a sub-project or straight to `main`, and points at each package for its subsection | owns its delivery's subsection: the artefacts by route, then the steps |
| Post-deployment checks | only for a requirement no delivery satisfies | owns, because a check is answered per delivery |

`board-check.py` asks each for what it owes, telling them apart by the parent
link. Each heading holds the content or a link to the document that holds it,
never both:

```markdown
## Requirements

**Source requirements**: #NNN *title*, #NNN *title*.

| | From | |
| --- | --- | --- |
| R1 | #NNN *title* | what must be true when this is done |

## Design

## Non-functional design

Capacity, failure, limits and timeouts, secrets and access: each answered, or
*none, because…*. A limit says where its number came from.

## Test approach

### Functional user tests — Preview

- [ ] **owner** —

### Technical tests — Rehearsal

- [ ] **Claude** —

## Dependencies and related work

**waits on #NNN** *title*: why.
**is needed by #NNN** *title*: why.

## Deliveries

| # | What it delivers | Route | Milestone | Work package or steps |
| --- | --- | --- | --- | --- |

### Delivery 1 — <what it delivers>

| Route | In this delivery | Artefacts | Branch | PR |
| --- | --- | --- | --- | --- |
| **Production Release** | yes/no | | **always yes** | **always yes** |
| **Application Tooling** | yes/no | | yes | yes |
| **Docs and Programme Tooling** | yes/no | | | |
| **Other** | yes/no | | | |

Steps: the runbook, in order, after the table.

## Post-deployment checks against requirements

| Requirement | How the check is done | |
| --- | --- | --- |
```

The Deliveries subsections follow
[1.2 *Deliveries: one subsection per delivery, a table per subsection*](../../../docs/1.2-change-lifecycle.md#deliveries-one-subsection-per-delivery-a-table-per-subsection).
A Docs and Programme Tooling delivery says whether each application's pin
moves, and where one does, ends with the move.
A delivery's steps live in one place: the subsection of the work package that
carries it, or the parent's where the project has no sub-project
([1.2 §2.14](../../../docs/1.2-change-lifecycle.md#214-the-delivery-runbook)).

Each `waits on` and `is needed by` is also set as a GitHub dependency link
(`addBlockedBy`), one link serving both ends: the context header shows the
links, and `board-check.py` reports a line with none behind it. It reads
only the *Dependencies and related work* section.

The two test headings are written exactly as the template has them, because the
tooling finds them by name. Write *None.* under one that does not apply, and
keep the heading. What each heading holds, and how a post-deployment check is
answered, is in [1.2 §2](../../../docs/1.2-change-lifecycle.md#2-the-rules).

**Once an option is chosen, only it stays in the body**, and the reasoning goes
in a comment.

## Source requirements

| | Is | Changes when |
| --- | --- | --- |
| *Source requirements* | the issues this project took, by number and title | a requirement moves in or out |
| the *Requirements table* | R1…Rn, what must be true when this is done | scoping merges, splits or drops them |

- The source list matches the `Requirement` sub-issues exactly. The `From`
  column says which source produced an R, and goes incomplete the moment
  scoping merges or drops one.
- A decision is not a source requirement, because nothing folds a decision. Name
  it in the `From` column of the rows it produced.
- A project raised directly keeps the line and says `none: raised directly as
  a project, so R1 and R2 are its own`. An absent line cannot be told from an
  unanswered one.
- A requirement parented here but not listed, or listed but parented elsewhere,
  is a defect: it sits under a project whose body does not claim it.

## Work packages

A work package is carried by a sub-project or by the parent, and a milestone is
what groups packages that go live together
([1.2 §1.1](../../../docs/1.2-change-lifecycle.md#11-what-a-milestone-says)).
Whether a delivery needs a sub-project is
[1.2 *The model, and the four cases that follow from it*](../../../docs/1.2-change-lifecycle.md#the-model-and-the-four-cases-that-follow-from-it).
Case A, one package, is the common shape and takes none.

## Naming

The forms, and what `WP A`, `Del 1 of 2` and `pt 1 of 2` mean, are in
[1.2 *Naming*](../../../docs/1.2-change-lifecycle.md#naming). A release's
dependency update project is created from
[`dependency-update-project.md`](../../../docs/templates/dependency-update-project.md).

**A branch is named for the work package, not the parent**, and its commits say
`Refs` the work package, as
[1.2 §2.5](../../../docs/1.2-change-lifecycle.md#25-tracking-a-change-to-production)
sets out. Splitting a project that already has a branch means renaming the
branch to the package it now carries before the next commit, or
`board-status.py` reports the package *not started* after it has merged.

## Writing the body

**Never hard-wrap a paragraph in an issue body.** GitHub renders a single
newline in an issue body as a line break, so a wrapped paragraph comes out
ragged. One paragraph is one line, however long; headings, table rows, list
items, block quotes and fenced code keep their own lines.

## Creating it

Write the body to a file and pass the file, never `--body`: the shell evaluates
the backticks in a body passed inline, and silently swallows whole spans.

**Set the type at creation**, so no window exists in which the issue is
untyped. `gh issue create --type` is refused by the older `gh` in a cloud
session, so the main path is the REST create, which takes the type by name:

```bash
# The application's repository, from its technical profile (identity table).
REPO=$(programme/scripts/board/board-profile.py get profile.identity.repository)   # owner/name
gh api -X POST "repos/$REPO/issues" -f title="..." -F body=@/tmp/body.md \
  -f type=Project --jq '[.number,.node_id]|@tsv'
```

`-f type=Requirement` for a requirement. In the programme's own checkout there
is no technical profile: the repository is `delphside/programme`
(`programme.repository` in `config/programme.toml`), so set
`REPO=delphside/programme`. Where `gh` accepts it,
`gh issue create -R "$REPO" --type Project --title "..." --body-file /tmp/body.md`
does the same.

`board-check.py` treats an untyped issue as a requirement and reports it as
untyped, but an ad-hoc filter on type (a `jq select`, say) drops it silently.

## Setting fields

| New issue | Fields | Stage |
| --- | --- | --- |
| a requirement | none beyond its stage | `Requirement State` `Triage` |
| a project | `Workstream`, `Type of change`, `Effort`, `Priority` | `Project State` `Scope` |
| a work package or standalone project | those, and `Route`, the route of its delivery | `Project State` `Scope` |
| a parent | those, never `Route` | `Project State` `Scope` |
| a release's dependency update project | the fields [1.2 §2.2.1](../../../docs/1.2-change-lifecycle.md#221-business-as-usual-updates) lists | the stage it lists |

**Set the stage in the same call as the rest.** `board-check.py` reports a
requirement with no stage, and an unset `Requirement State` is read as
`Triage`, so a requirement left without one hides in that state.

**The cloud path is REST**, which sets a field by its option name:

```bash
gh api -X POST "repos/$REPO/issues/$NUM/issue-field-values" --input - <<'JSON'
{"issue_field_values":[
  {"field_id":46162136,"value":"Scope"},
  {"field_id":46217763,"value":"<workstream>"}
]}
JSON
```

The REST field IDs are numbers: `Project State` 46162136, `Workstream`
46217763, `Priority` 46090971, `Type of change` 46117082, `Effort` 46090974,
`Requirement State` 46185224 and `Route` 46415058. Read the ID of any other
field from an issue that holds it, with
`gh api repos/$REPO/issues/N/issue-field-values`.

**Locally, four GraphQL mutations set fields and the type**, each on the
issue's node ID (`$id`, the `node_id` the create printed, or read from
`repos/$REPO/issues/N`):

| Mutation | Use it to | Input shape |
| --- | --- | --- |
| `setIssueFieldValue` | set several fields at once | `issueFields:[{fieldId:"…",singleSelectOptionId:"…"}]`, a list |
| `updateIssueFieldValue` | set one field | `issueField:{fieldId:"…",singleSelectOptionId:"…"}`, nested; `fieldId` at the top level is rejected |
| `deleteIssueFieldValue` | clear a field | `fieldId:"…"` directly; `clearIssueFieldValue` does not exist |
| `updateIssue` | change the type of an existing issue | `issueTypeId:"…"` |

```bash
gh api graphql -f query='mutation($i:ID!){setIssueFieldValue(input:{issueId:$i,issueFields:[
  {fieldId:"<field>",singleSelectOptionId:"<option>"}
]}){issue{number}}}' -f i="$id"
```

The singular `createIssueFieldValue` refuses when a value already exists. When a
mutation is rejected, read its input type:
`gh api graphql -f query='{__type(name:"IssueFieldCreateOrUpdateInput"){inputFields{name}}}'`.

| Type | ID |
| --- | --- |
| Requirement | `IT_kwDOEyOvmc4yo-D-` |
| Project | `IT_kwDOEyOvmc4yo-D_` |

| Field or option | ID |
| --- | --- |
| `Workstream` | `IFSS_kgDOAsE6Iw` |
| … Process Definition | `IFSSO_kgDOBNJpTg` |
| … Programme Tooling | `IFSSO_kgDOBP3fBQ` |
| … Operations & Infrastructure | `IFSSO_kgDOBNJpTA` |
| … Capacity & Performance | `IFSSO_kgDOBNJpSw` |
| … TLE: Application Architecture | `IFSSO_kgDOBNJpRg` |
| … TLE: Delivery Tooling | `IFSSO_kgDOBNJpTQ` |
| … TLE: Security & Access | `IFSSO_kgDOBNJpSg` |
| … TLE: Client | `IFSSO_kgDOBNJpSA` |
| … TLE: Client Distribution | `IFSSO_kgDOBNJpSQ` |
| … TLE: Game Rules | `IFSSO_kgDOBNQ2zQ` |
| … TLE: Engine Player | `IFSSO_kgDOBNJpRw` |
| … DP: Application Architecture | `IFSSO_kgDOBRoupw` |
| … DP: Market Analysis | `IFSSO_kgDOBRouqA` |
| … DP: Client | `IFSSO_kgDOBRouqQ` |
| … DP: Delivery Tooling | `IFSSO_kgDOBRovkQ` |
| `Type of change` | `IFSS_kgDOAr-w2g` |
| … documentation | `IFSSO_kgDOBM-znA` |
| … tooling | `IFSSO_kgDOBM-zng` |
| … bug | `IFSSO_kgDOBM-zmA` |
| … cosmetic | `IFSSO_kgDOBM-zmw` |
| … functional | `IFSSO_kgDOBM-zmQ` |
| `Route` | `IFSS_kgDOAsQ80g` |
| … Production Release | `IFSSO_kgDOBNeykw` |
| … Application Tooling | `IFSSO_kgDOBPfgTQ` |
| … Docs and Programme Tooling | `IFSSO_kgDOBPfgTg` |
| … DEPRECATED Repository Change, never set | `IFSSO_kgDOBNeylA` |
| … Other | `IFSSO_kgDOBNeylg` |
| `Priority` | `IFSS_kgDOAr9K2w` |
| … Urgent | `IFSSO_kgDOBM8AMw` |
| … High | `IFSSO_kgDOBM8ANA` |
| … Medium | `IFSSO_kgDOBM8ANQ` |
| … Low | `IFSSO_kgDOBM8ANg` |
| `Effort` | `IFSS_kgDOAr9K3g` |
| … High | `IFSSO_kgDOBM-0yw` |
| … Medium | `IFSSO_kgDOBM-0zA` |
| … Low | `IFSSO_kgDOBM-0zw` |
| `Requirement State` | `IFSS_kgDOAsC7CA` |
| … Triage | `IFSSO_kgDOBNJ-sg` |
| … Scope, Options and Dependencies | `IFSSO_kgDOBNJ-sw` |
| … On Hold | `IFSSO_kgDOBNQ6Fg` |
| … Ready for Project | `IFSSO_kgDOBNJ-tA` |
| … Candidate Project 1 | `IFSSO_kgDOBNJ9nA` |
| … Candidate Project 2 | `IFSSO_kgDOBNJ9nQ` |
| … Candidate Project 3 | `IFSSO_kgDOBNJ9ng` |
| `Project State` | `IFSS_kgDOAsBg2A` |
| … Scope | `IFSSO_kgDOBNDpUw` |
| … Q3 | `IFSSO_kgDOBNUxFg` |
| … Q2 | `IFSSO_kgDOBNUxFw` |
| … Q1 | `IFSSO_kgDOBNUxGA` |
| … Design and Test Approach | `IFSSO_kgDOBNUxGQ` |
| … Development | `IFSSO_kgDOBNDpVA` |
| … User testing | `IFSSO_kgDOBNDpVQ` |
| … Deployment | `IFSSO_kgDOBNDpVg` |
| … Post-deployment | `IFSSO_kgDOBNDpVw` |
| … Project Closedown | `IFSSO_kgDOBNU2qA` |

The `non-functional` option of `Type of change` is not cached: name it in the
REST call, or read its ID with the query that follows. The programme's own
Delivery Tooling workstream is not cached either.

**These IDs are a cache and can go stale.** If one is rejected, re-read them at
organisation level, as `board/sources.py` does:

```bash
gh api graphql -f query='{organization(login:"'"${REPO%/*}"'"){issueFields(first:50){nodes{... on IssueFieldSingleSelect{id name options{id name}}}}}}'
```

After setting `Project State`, read the issue back: the IDs of `Deployment` and
`Development` differ in one character and are easily confused.

## Folding the requirements it takes

Requirements only: a `Project` absorbed into another follows *Moving
requirements between projects*. For each requirement, in order:

1. Copy its content into the project.
2. Make it a sub-issue of the project.
3. Label it `folded`.
4. Close it as `completed` with a comment naming the project.
5. Remove its milestone, if it has one: a folded requirement carries none.

```bash
gh api graphql -f query='mutation($p:ID!,$c:ID!){addSubIssue(input:{issueId:$p,subIssueId:$c}){issue{number}}}' -f p="$pid" -f c="$cid"
gh issue edit NNN -R "$REPO" --add-label folded
gh issue close NNN -R "$REPO" --reason completed --comment "Folded into #$NUM *<title>*, which owns this requirement from here."
gh issue edit NNN -R "$REPO" --remove-milestone
```

`$pid` and `$cid` are the node IDs of the project and the requirement, read as
`node_id` from `repos/$REPO/issues/N`. Where GraphQL is refused (`gh issue edit`
and `gh issue close` use it too), REST does each step. The sub-issue call takes
the requirement's numeric issue ID, the `id` of `repos/$REPO/issues/NNN`:

```bash
gh api -X POST repos/$REPO/issues/$NUM/sub_issues -F sub_issue_id=<id>
gh api -X POST repos/$REPO/issues/NNN/labels -f 'labels[]=folded'
gh api -X POST repos/$REPO/issues/NNN/comments -f body="Folded into #$NUM *<title>*, which owns this requirement from here."
gh api -X PATCH repos/$REPO/issues/NNN -f state=closed -f state_reason=completed
gh api -X PATCH repos/$REPO/issues/NNN -F milestone=null
```

## Moving requirements between projects

A requirement is folded into the project that takes it, once; nothing else is
folded. It can move on afterwards, from one project to another. Document the
move in both projects: the receiving one names the source (`#NNN *title*`, so
the trail survives), the losing one records that it has gone and where.

Move the sub-issue link with it, using `replaceParent:true` (REST:
`-F replace_parent=true` on the `sub_issues` call), or the requirement sits
under a project whose body no longer claims it:

```bash
gh api graphql -f query='mutation($p:ID!,$c:ID!){addSubIssue(input:{issueId:$p,subIssueId:$c,replaceParent:true}){issue{number}}}' -f p="$pid" -f c="$cid"
```

A project whose requirements have all moved out owns nothing and is closed.
Say in the comment which projects took what, and pick the close reason that
fits: *duplicate* where it was genuinely the same work seen twice, *not
planned* otherwise.

Two things must not happen to an absorbed project:

| Not this | Why |
| --- | --- |
| `addSubIssue` on the project itself | a `Project` sub-issue means a work package: `board-check.py` then asks the absorbing project for a parent's obligations and the absorbed one for a work package's |
| the `folded` label, and closing as `completed` | `folded` marks a requirement, and nothing was completed |

## Afterwards

```bash
programme/scripts/board/board-context.py --write N    # the context header, for N's whole family
programme/scripts/board/board-check.py                # has it done what its phase claims?
programme/scripts/board/roadmap-diagram.py --write    # only where the profile sets documents.roadmap
```

In the programme's own checkout the scripts are `scripts/board/…`. Never write
the context header by hand: it is generated from the family's fields,
milestones, pull requests and dependency links, and rewritten whole, so a hand
edit inside its markers is lost. Set the facts and regenerate.

Where the profile sets `documents.roadmap` (Tile Lite Elite's `docs/4.1.5`),
commit the regenerated roadmap: the diagram is derived, and a stale copy is
wrong.

## Where a project's documentation is committed

Documentation for a project belongs on `main` unless the project has a branch.
Check the branch before committing.
