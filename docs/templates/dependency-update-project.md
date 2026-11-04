# Dependency update project

The body of a release's dependency update project. The rule, the title and
the fields are
[1.2 §2.2.1](../1.2-change-lifecycle.md#221-business-as-usual-updates).

<!--
Only the fenced block is copied, into the project's body when it is raised.

Placeholders: `#N` is this project's number; `X.Y.Z` is the release it rides;
`#nnn` is a pull request or an advisory requirement.

Only the table rows, the source requirements and the ticks change. A row
whose update changes one of the four non-functional answers also adds a line
under Non-functional design.
-->

````markdown
## Requirements

**Source requirements**: *the advisory requirements folded in, or "none — raised directly as a project"*.

| | From | |
| --- | --- | --- |
| R1 | | Every update in the table reaches production in `X.Y.Z` without changing behaviour |
| R2 | *advisory requirements* | No finding of the application's advisory check that reaches the application remains in what `X.Y.Z` ships |

| Update | Why | Pull request | Targeted test | Result |
| --- | --- | --- | --- | --- |
| *what moves, from and to which version* | *Dependabot · advisory `#nnn` · planned* | `#nnn` | *the test aimed at the change, or "CI"* | *passed · failed* |

## Design

None: each row is a version change, made as 1.2 §2.2.1 says.

## Non-functional design

Capacity, failure, limits and timeouts, secrets and access: none, because a version bump changes none by intent.

## Test approach

### Functional user tests — Preview

- [ ] **Claude** — each row's targeted test that only a deployed stack can show, on preview at its pull request's branch tip

### Technical tests — Rehearsal

- [ ] **Claude** — the same targeted tests on rehearsal, at the same branch tip
- [ ] **Claude** — the release's regression run, which covers the updates together

## Dependencies and related work

None.

## Deliveries

| # | What it delivers | Route | Milestone | Work package or steps |
| --- | --- | --- | --- | --- |
| 1 | the updates in the table | Production Release | `X.Y.Z` | this project |

## Post-deployment checks against requirements

| Requirement | How the check is done | |
| --- | --- | --- |
| R1 | the application's verification passes after the production deploy | |
| R2 | the application's advisory check, run against the release's tag, finds nothing that reaches the application | |
````
