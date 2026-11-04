# Dependency update project

The body of a release's dependency update project. The rule is
[1.2 §2.2.1](../1.2-change-lifecycle.md#221-business-as-usual-updates).

<!--
Raised once per release, by the first `Production Release` dependency update
to arrive after the previous release was made: a base-image bump, a library
bump, or the fix for an advisory.

- Title: `#N Dependency updates for X.Y.Z`, where X.Y.Z is `main`'s version.
- Fields: `Project State` Development, since there is nothing to scope or
  design; `Route` Production Release; milestone X.Y.Z; `Type of change`
  non-functional; `Effort` Low; `Workstream` the application's security
  workstream.
- Each update: its pull request says `Refs #N` and adds one row to the table.
  An advisory requirement is folded in (the `folded` label, closed) and named
  in the row and in the source requirements.
- An update still open when X.Y.Z is made moves its row to the next release's
  project.

Only the table rows, the source requirements and the ticks change. Delete
this comment once the project is raised.
-->

````markdown
## Requirements

**Source requirements**: *the advisory requirements folded in, or "none — raised directly as a project"*.

| | from | |
| --- | --- | --- |
| R1 | | Every update below reaches production in X.Y.Z without changing behaviour |
| R2 | *advisory requirements* | No reachable advisory remains against what X.Y.Z ships |

| update | why | pull request | targeted test | result |
| --- | --- | --- | --- | --- |
| *what moves, from and to which version* | *Dependabot · advisory #nnn · our choice* | #nnn | *the test aimed at the change, or "CI"* | *passed · failed* |

## Design

None: each row is a version change, made as 1.2 §2.2.1 says.

## Non-functional design

Capacity, failure, limits and timeouts, secrets and access: none, because a version bump changes none by intent. A row that does change one adds a line here.

## Test approach

### Functional user tests — Preview

None.

### Technical tests — Rehearsal

- [ ] **Claude** — each row's targeted test, at its pull request's branch tip, where only a deployed stack can show it
- [ ] **Claude** — the release's regression run, which covers the updates together

## Dependencies and related work

None.

## Deliveries

| # | what it delivers | route | milestone | work package or steps |
| --- | --- | --- | --- | --- |
| 1 | the updates above | Production Release | X.Y.Z | this project |

## Post-deployment checks against requirements

| requirement | how the check is done | |
| --- | --- | --- |
| R1 | the application's verification passes after the production deploy | |
| R2 | the application's advisory check, run against the X.Y.Z tag, finds nothing that reaches it | |
````
