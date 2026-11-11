# Dependency update project

The body of a release's dependency update project. The rule, the title and
the fields are in
[1.2 §2.2.1](../1.2-change-lifecycle.md#221-business-as-usual-updates).

<!--
Claude copies only the fenced block into the project's body when raising it.

Placeholders: `#N` is this project's number; `X.Y.Z` is the release it rides;
`#nnn` is a pull request; `#aaa` is an advisory requirement; `n` in `3.n.6` is
the application's index.

Fixed wording, which the tooling reads: the headings `Test approach`,
`Functional user tests`, `Technical tests`, `Deliveries` and
`Post-deployment checks against requirements`. The user-testing check
(`obligations.py`, `turn.py`) matches the literal
`Functional user tests — Preview`, so that heading keeps `Preview`; the text
after the dash in `Technical tests` names the rehearsal environment from the
application's `3.n.6`, and Tile Lite Elite's is Rehearsal.

1.2 §2.2.1 says what changes from release to release, and what to add for a
row that needs a test this template lacks.
-->

````markdown
## Requirements

**Source requirements**: *the advisory requirements folded in, or "none — raised directly as a project"*.

| Requirement | From | Statement |
| --- | --- | --- |
| R1 | | Every update in the table reaches production in `X.Y.Z` without changing behaviour |
| R2 | *advisory requirements, or "none"* | No finding of the application's advisory check that reaches the application remains in what `X.Y.Z` ships |

| Update | Why | Pull request | Targeted test | Result |
| --- | --- | --- | --- | --- |
| *what moves, from and to which version* | *Dependabot · advisory `#aaa` · planned* | `#nnn` | *the test aimed at the change, or "CI"; for an advisory, the advisory check at the branch tip no longer reports it* | *passed · failed* |

## Design

None: each row is a version change, made as [1.2 §2.2.1](https://github.com/delphside/programme/blob/main/docs/1.2-change-lifecycle.md#221-business-as-usual-updates) says.

## Non-functional design

Capacity, failure, limits and timeouts, secrets and access: none, because a version bump changes none by intent.

## Test approach

### Functional user tests — Preview

None, unless a row a user could notice adds a box here.

### Technical tests — *rehearsal environment*

- [ ] **Claude** — each row's targeted test at its pull request's branch tip: where only a deployed stack can show the change, on the application's user-testing and rehearsal environments where it has them (its `3.n.6`); otherwise where the table says (CI)
- [ ] **Claude** — the release's regression run, at a `main` tip that includes every merged row; Claude moves a row merged after the run to the next release's project, or repeats the run

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
