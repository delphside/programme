# Dependency update project

The body of a release's dependency update project. The rule, the title and
the fields are
[1.2 §2.2.1](../1.2-change-lifecycle.md#221-business-as-usual-updates).

<!--
Only the fenced block is copied, into the project's body when it is raised.

Placeholders: `#N` is this project's number; `X.Y.Z` is the release it rides;
`#nnn` is a pull request or an advisory requirement.

What changes from release to release is listed in 1.2 §2.2.1. A row that
needs a test the template does not list adds a box here, and the test approach
then goes to the test manager before that row merges.

An advisory row's targeted test is always the application's advisory check,
run at the pull request's branch tip, no longer reporting the advisory.
-->

````markdown
## Requirements

**Source requirements**: *the advisory requirements folded in, or "none — raised directly as a project"*.

| Requirement | From | Statement |
| --- | --- | --- |
| R1 | | Every update in the table reaches production in `X.Y.Z` without changing behaviour |
| R2 | *advisory requirements* | No finding of the application's advisory check that reaches the application remains in what `X.Y.Z` ships |

| Update | Why | Pull request | Targeted test | Result |
| --- | --- | --- | --- | --- |
| *what moves, from and to which version* | *Dependabot · advisory `#nnn` · planned* | `#nnn` | *the test aimed at the change, or "CI"; for an advisory, the advisory check at the branch tip no longer reports it* | *passed · failed* |

## Design

None: each row is a version change, made as 1.2 §2.2.1 says.

## Non-functional design

Capacity, failure, limits and timeouts, secrets and access: none, because a version bump changes none by intent.

## Test approach

### Functional user tests — Preview

None, unless a row a user could notice adds a box here.

### Technical tests — Rehearsal

- [ ] **Claude** — each row's targeted test at its pull request's branch tip: where only a deployed stack can show it, on the application's user-testing and rehearsal environments where it has them (its `3.n.6`), otherwise the advisory check and CI
- [ ] **Claude** — the release's regression run, at a `main` tip that includes every merged row; a row merged after the run moves to the next release's project, or the run is repeated

## Dependencies and related work

None.

## Deliveries

| # | What it delivers | Route | Milestone | Work package or steps |
| --- | --- | --- | --- | --- |
| 1 | the updates in the table | Production Release | `X.Y.Z` | this project |

## Post-deployment checks against requirements

| Requirement | How the check is done | Result |
| --- | --- | --- |
| R1 | the application's verification passes after the production deploy | |
| R2 | the application's advisory check, run against the release's tag, finds nothing that reaches the application | |
````
