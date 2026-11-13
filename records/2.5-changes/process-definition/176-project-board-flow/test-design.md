<!-- markdownlint-disable-file MD013 -->

# Test design specification: Project Board flow

Project: delphside/programme#176 · type of change: `tooling` · route: `Docs and Programme Tooling` (delivery 2; deliveries 1 and 3 are `Other`) · release: not applicable

This specification derives the tests for the board flow from its stated rules, without reading the implementation. Its sources are:

- #176's body, R1 to R14;
- [design.md](design.md), [options.md](options.md) and [implementation.md](implementation.md) in this folder;
- docs/1.2 §2.15 (*Option colour says whose turn it is*, *Who moves a project's state*) and §2.23;
- docs/1.8 *A Ticket's state*;
- docs/1.1, the `Unavailable` rule;
- docs/1.9.

**(H)** would mark a rule taken from the handover rather than a document. None is needed: every *agreed but not yet written down* item was found in the three design files, so no rule here is marked (H).

Each test has one of two kinds:

- **[CI]** is a Python test in `scripts/board/tests/`. It builds its own world through a stubbed REST source, which holds five repositories with issues, issue fields, timelines, sub-issues, dependency links, pull requests and commits. It refuses GraphQL as a cloud session's proxy does, and logs every write.
- **[TT]** is a technical test, run once by Claude against the real repositories before the merge. Programme tooling has no environment between CI and `main` (docs/1.9 *What tests the tooling*).

Delivery 1 (the fields and the view) is the owner's steps. Delivery 3 (the daily trigger, the pinned issue and the session-start hook) has its own work package; its [TT]s are listed here so that one document holds them.

## 1. Rules

### From #176's body

| ID | Rule |
| --- | --- |
| R1 | Every open item, in every state, has exactly one named next mover: the owner, a role's thread, or a tool. |
| R2 | Every move has a trigger (event, schedule or person). A wait has a stated bound, past which someone is told. |
| R3 | The board model is the single source of what needs doing: per type and state, the mover, what it owes and the trigger. Every to-do list is derived from it. |
| R4 | The model's answers can be read wherever a mover runs: a cloud thread (REST only) or WSL. |
| R5 | The design covers every issue type (Requirement, Project, work package, Decision, pull request, Ticket) and every repository. |
| R6 | Names and the shape of the practice come from an industry standard where one exists (Kanban, ITIL). |
| R7 | An item in an invalid state is moved to a valid starting state, and the board is written to match. An item with no type becomes a Requirement. An item with no state gets its type's starting state, pull requests included. A requirement with no workstream is the owner's, at triage. Any other item with no workstream is found, and either given one or raised with the owner. |
| R8 | Flow recovers from any degree of stoppage, from a black start to every thread running. Every item that is not progressing is found and picked up. |
| R9 | Before picking up an item, a mover can tell whether it is already being worked, and by whom. Recovery restarts only what has stalled. |
| R10 | A requirement is triaged when it is raised: by the raising thread where Claude triages alone, or by asking the owner at once where triage is joint. |
| R11 | Each `Requirement State` has a next mover and a bound (7 days). Past the bound, the requirement appears on that mover's list and in the `board-sweep`, with how long it has sat. |
| R12 | Each workstream's thread stays on top of its open issues, and the sweep nudges a thread whose issues are past R11's bound. A requirement stays at Scope only while it waits on something specific named under its dependencies. One waiting on the owner has a `Decision` issue. |
| R13 | A workstream's thread progresses a requirement until it rests in one of the ten listed resting states. |
| R14 | The owner can see which resting state each requirement is in, and which wait on him, without reading the issues. |

### From design.md (M)

| ID | Rule |
| --- | --- |
| M1 | *Age* is the time in the current state. *Stalled* means age past the bound, or a claim whose thread has not moved the item within the bound. *Resting* means a wait on something named, with no move owed by the holder. |
| M2 | Requirement: unset reads as `Triage`. Unset and `Triage`: the workstream thread moves it (the owner first where triage is joint); bound 1 day. Scope: the workstream thread; 7 days. Waiting on a `Decision`: resting, under the Decision's bounds. `On Hold`: resting, reviewed at each sweep. `Ready for Project`: the coordinator; no bound. `Candidate Project 1`: one sweep. `Candidate Project 2` and `3`: no bound. |
| M3 | R13's resting states map as follows: the closed reasons and *folded* are closed. Both kinds of hold are `On Hold`, told apart by whether the dependency section links an issue. *Waiting for planning* is `Ready for Project` or a candidate slot. *Waiting on a Decision* is `Turn` = `Hold` plus a dependency link. *Waiting on the owner's approval* of scope or of project scoping is `Turn` = `Owner`. |
| M4 | Project, mover and bound per phase:<br>• `Scope`: design authority, 7 days.<br>• `Q3` to `Q1`: coordinator, no bound.<br>• `Design and Test Approach`: design authority, 7 days without a move.<br>• `Development`: technical lead, 7 days without a commit.<br>• `User testing`: owner or technical lead, 7 days.<br>• `Deployment`: technical lead or release manager, no bound.<br>• `Post-deployment`: technical lead, review due after 7 days.<br>• `Project Closedown`: technical lead (for a parent, the design authority), 7 days. |
| M5 | A parent runs Scope to `Design and Test Approach`, rests while its packages run (under the packages' bounds), then returns for `Post-deployment` and `Project Closedown`. |
| M6 | Decision: the turn alternates. `Asked` is the owner's, `Feedback Provided` Claude's, `Documented Ready for Sign-Off` the owner's, `Decided` Claude's, `Actioned` the owner's. The bound is 7 days per step. A Decision raised without a state gets a starting state. |
| M7 | Pull request: its state is derived from GitHub and never typed; bound 7 days in any state. Its turn comes from `PR State` and is shown in `board-actions.py`, not the view. It carries no issue fields. Its claim is the thread that owns its branch. |
| M8 | Ticket: `New` and `In progress` are the owner's. `Waiting on sender` is the sender's. `Pending` waits for the review date in its last note. Each state has a bound. |
| M9 | `Turn` (`Owner` · `Claude` · `Hold`) is on every open issue. The model writes it wherever it can derive the mover. A thread sets it only where the model cannot (an approval, a hold). An item with no `Turn` is lost, and the sweep finds it. The owner's view filters on `Owner` and groups by issue type. |
| M10 | `Turn` = `Owner` carries a comment saying what is to be approved. |
| M11 | A `Hold` has a reason the model can check: an issue linked under *Dependencies and related work*, or a named event with a review date. A hold is reviewed at its bound. |
| M12 | Bounds: 7 days for every state where the owner or a thread owes a move; 1 day for triage; none for the queues and `Deployment`. |
| M13 | `Claimed by` names the role, then a link to the thread holding it now; the role alone where no thread exists. A claim is stale once the item is past its bound with no move, and the sweep then offers it to the role's current thread. A recovering sweep restarts only items with no live claim. |
| M14 | On each sweep: no type becomes Requirement, no state becomes the type's starting state, and a non-requirement with no workstream is raised with the owner. |
| M15 | A specific question for the owner is a `Decision` issue, except during the first discussion. |

### From options.md (P)

| ID | Rule |
| --- | --- |
| P1 | Option 4: events make the moves they can, each mover pulls its own list, and the sweep finds what an event missed or a mover left past its bound. |
| P2 | The reconciliation sweep runs daily and writes each item's `Turn`. The weekly `board-sweep` keeps its planning, which has no bound. |
| P3 | Events, sweep and lists all read one model. |

### From implementation.md (I)

| ID | Rule |
| --- | --- |
| I1 | One flow table in `model.py` maps type and state to role, `Turn` and bound. Every caller reads it, the bounds live there and nowhere else in code, and the documents link to it. |
| I2 | `board-flow.py` is plain Python over REST. It reads every open issue and pull request in the five repositories; writes R7's fixes and each item's `Turn`; clears stale claims; rewrites the pinned stalled-list issue in the programme repository; and returns the stalled items by role. |
| I3 | The coordinator's daily cloud trigger runs it and nudges each stalled item's role thread, or starts one. When nothing is stalled it ends without a message. The Monday trigger stays. The run time keeps clear of 21:10 to 22:10 UTC. No GitHub Actions job is added. |
| I4 | Reconciliation keeps no history, so a missed day is tolerated and the next run corrects it. |
| I5 | Events: the raising thread sets the starting state and `Turn`; the merging thread moves its work package by route; a missed merge is caught by the next sweep through `Refs #N`; `deploy.sh` moves what it ships, and a missed deploy is caught by the next sweep. `pr-state.yml` is unchanged. Infrastructure pull requests' movers are derived from REST. |
| I6 | `Turn` is a single select: `Owner` green, `Claude` blue, `Hold` yellow. `Claimed by` is text. The owner creates both. |
| I7 | `board-actions.py --role <role>` lists one role's items, oldest first, with age and bound, from the same table. Threads run it at start and at each wake (cloud and WSL session-start hooks). The owner's list adds every `Turn` = `Owner` item to its three existing sources. |
| I8 | Writes are one call per item that changed. |
| I9 | A failed run writes what it reached and exits non-zero, naming the item and the call. The pinned issue says when the last complete run was. A field the model cannot read is *not visible*, never a default. |
| I10 | Each REST call is cut at 120 s. |
| I11 | Nothing secret is added: the sweep runs with the session's own repository-scoped REST access. |

Merge rule from CLAUDE.md and docs/1.2 §2.1: a merge moves a Production Release package to `Deployment` and a tooling-route one to `Post-deployment`. It is cited with I5.

### Checked for contradiction

- **R11 against M2 and M12:** R11 gives every `Requirement State` a 7-day bound, while M12 sets 1 day for triage and none for the queues. Reconciled by the owner's later answer (design.md Q3, 2026-11-13). The tests assert M12. R11's text in the body should say so.
- **R11 and R12 against P2 and I3:** R11 and R12 say `board-sweep`; the design moves listing and nudging to the daily `board-flow.py` run. Read as: the daily run lists and nudges, and the weekly `board-sweep` keeps planning. See G25.
- **R7 (pull requests included) against I5 and the known-gaps table:** `PR State` cannot be written over REST, and infrastructure has no workflow. Accepted as a known gap (#383 R15). For infrastructure the tests assert a derived mover, not a written state.
- **Still open, each in part 10:**
  - R1 against M2, M4 and M8 (more than one mover in a state, `Hold` naming nobody, a tool mover): G1, G2;
  - M9 against M3 and M10 (a derivable state carrying a thread-set `Owner` or `Hold`): G3;
  - R12 against M2 and docs/1.2 §2.23 (Scope against `On Hold`): G4;
  - M14 against docs/1.2 §2.23 (unset against `Triage`): G5;
  - M13 against I2 (offer against clear): G9.

## 2. Conditions, grouped into dimensions

**D1 — item type** *complete (R5)*

- **D1.1** Requirement
- **D1.2** single-package Project
- **D1.3** parent with sub-projects
- **D1.4** work package
- **D1.5** Decision
- **D1.6** pull request with `PR State`
- **D1.7** pull request with none (infrastructure)
- **D1.8** Ticket
- **D1.9** issue with no type

**D2 — repository** *complete*

- **D2.1** programme
- **D2.2** tile-lite-elite
- **D2.3** dark-portal
- **D2.4** infrastructure
- **D2.5** service-desk

**D3 — state as found** *complete*

- **D3.1** a valid option of its type's field
- **D3.2** none
- **D3.3** a value not in the flow table (a renamed option)
- **D3.4** not visible (the read failed)

**D4 — age against bound** *complete*

- **D4.1** well within
- **D4.2** one minute under
- **D4.3** exactly at
- **D4.4** one minute past
- **D4.5** far past (30 days)
- **D4.6** the state has no bound
- **D4.7** age unreadable

**D5 — `Turn` as found** *complete*

- **D5.1** unset
- **D5.2** equal to the derived value
- **D5.3** different from the derived value
- **D5.4** thread-set `Owner` with an approval comment
- **D5.5** `Hold` with an open linked dependency
- **D5.6** `Hold` whose linked dependency has closed
- **D5.7** `Hold` with a named event, review date to come
- **D5.8** `Hold` with a named event, review date passed
- **D5.9** `Hold` with no reason

**D6 — claim** *complete*

- **D6.1** none
- **D6.2** role only
- **D6.3** role and a thread link, within the bound
- **D6.4** role and a thread link, past the bound with no move (stale)
- **D6.5** malformed

**D7 — workstream** *complete*

- **D7.1** set
- **D7.2** unset on a Requirement
- **D7.3** unset on another type

**D8 — source behaviour** *complete*

- **D8.1** every call succeeds
- **D8.2** a read fails (`Unavailable`)
- **D8.3** a write is refused (403)
- **D8.4** a call hangs past 120 s
- **D8.5** GraphQL refused throughout

**D9 — missed event** *complete over I5*

- **D9.1** a merged pull request with `Refs #N` to a Production Release work package
- **D9.2** the same, tooling-route work package
- **D9.3** `Refs` to a parent only
- **D9.4** pull request not merged
- **D9.5** work package already moved
- **D9.6** a deploy not followed by its move

**D10 — caller** *complete*

- **D10.1** `board-flow.py`
- **D10.2** `board-actions.py` (the owner's list)
- **D10.3** `board-actions.py --role`
- **D10.4** `board-actions.py --claude`
- **D10.5** `board-check.py`

**D11 — run history** *complete*

- **D11.1** first run
- **D11.2** a rerun with nothing changed
- **D11.3** a rerun after a failed run
- **D11.4** a run after a missed day

**D12 — stalled set** *complete*

- **D12.1** empty
- **D12.2** items for several roles
- **D12.3** an item whose role has no permanent thread

## 3. Outcomes

| ID | Outcome |
| --- | --- |
| O1 | The write log shows the issue type set to `Requirement` on each untyped issue, and no type write to any pull request. |
| O2 | The write log shows the type's starting state written to each stateless issue: Requirement as G5 settles, Project `Scope`, Ticket `New`, Decision as G6 settles. |
| O3 | The run's output and the pinned issue's body list each non-requirement with no workstream as raised with the owner. A requirement with no workstream is not listed as missing one. |
| O4 | The write log shows `Turn` set to the value the flow table derives, once per item that changed. |
| O5 | The write log shows no write for the item, or for the whole run where stated. |
| O6 | The item is in the stalled output and the pinned issue's body, under the role the flow table names, with its age and its bound. |
| O7 | The item is in neither the stalled output nor the pinned issue's body. |
| O8 | Stale claim: the stalled output offers the item to its role's current thread, and the claim is handled as G9 settles. |
| O9 | The pinned issue's body is rewritten by this run and states the time of the last complete run. |
| O10 | The exit is non-zero; stderr names the item and the call that failed; writes made before the failure stand; and the pinned issue's last-complete-run time is the previous run's. |
| O11 | The item is reported *not visible*. No `Turn` or state is written to it, and it is not judged stalled on a default value. |
| O12 | `--role R` prints exactly the items whose mover is R, oldest first, each with age and bound. With none, it says so plainly. |
| O13 | The owner's list holds every `Turn` = `Owner` item, plus its three existing sources unchanged. |
| O14 | Across callers, for one world: every open item has exactly one mover; the stalled set equals the past-bound items on the role lists; `board-check.py` agrees. |
| O15 | The run completes with GraphQL refused, and its result matches the same world's expected answer. |
| O16 | The work package's `Project State` is written `Deployment` (Production Release) or `Post-deployment` (tooling route), and nothing else moves. |
| O17 | Quiet: the stalled output is empty, the pinned issue says nothing is stalled and gives the run's time, and the exit is the clean status (G21). |
| O18 | The item is reported to its role as an invalid or released hold, with the reason. |
| O19 | `--role` with an unknown role is refused with an error naming it. |

## 4. Matrix

**D1 × D4: stalled or not** (✓ listed as stalled · – not listed · n/a cannot occur · ? gap)

| | within / 1 min under / at | 1 min past / far past | no bound |
| --- | --- | --- | --- |
| Requirement, unset or `Triage` (1 day) | – | ✓ | n/a |
| Requirement, Scope (7 days) | – | ✓ | n/a |
| Requirement, `Ready for Project`, `Candidate 2` and `3` | n/a | n/a | – |
| Requirement, `Candidate 1` | ? G8 | ? G8 | n/a |
| Requirement, `On Hold` | – while its reason holds | ? M2 vs M11 (G2) | n/a |
| Project, Scope, `Design and Test Approach`, `User testing`, `Project Closedown` | – | ✓ | n/a |
| Project, `Q3` to `Q1`, `Deployment` | n/a | n/a | – |
| Project, `Development` | – (commit age) | ✓ (commit age, G11) | n/a |
| Project, `Post-deployment` | – | ? G12 | n/a |
| Parent waiting on packages | – | – while packages are open (G10) | n/a |
| Decision, any state | – | ✓ | n/a |
| Pull request, any state | – | ✓ | n/a |
| Ticket, `New` or `In progress` | – | ✓ | n/a |
| Ticket, `Pending` | – before the review date | ✓ after it | n/a |
| Ticket, `Waiting on sender`, `Resolved`, `Refused` | ? G7 | ? G7 | ? G7 |

"At" is not stalled, because *stalled* is "past" the bound (M1).

**D5 × derivability: what the sweep writes to `Turn`**

| | the state's mover is derivable | not derivable |
| --- | --- | --- |
| unset | O4 (the derived value) | lost item: reported (S16) |
| equal to derived | O5 | n/a |
| different from derived | O4 (overwritten) | n/a |
| thread-set `Owner` with comment | ? G3 | O5, kept |
| `Hold`, reason valid and open | ? G3 | O5, resting |
| `Hold`, reason released or missing | O18 | O18 |

## 5. Scenarios

| ID | Scenario | Conditions | Outcomes | Kind |
| --- | --- | --- | --- | --- |
| S1 | One untyped issue in each of the five repositories; a stateless Requirement, Project and Ticket; an infrastructure pull request with no `PR State`. Run, then run again. | D1.1–D1.9, D2.1–D2.5, D3.2, D11.1–2 | O1, O2, O4; then O5 | CI |
| S2 | A world of typed issues and pull requests only; then add one untyped issue (the check shown to fail first). | D1.6, D1.7, D1.9 | O5 with no type write to any pull request; then O1 for the one | CI |
| S3 | An unset Requirement and a `Triage` one, each at 23 h 59 min, 24 h and 24 h 01 min. | D1.1, D3.1–2, D4.2–4 | O7, O7, O6 under the workstream's design authority | CI |
| S4 | A Project with no workstream; then its workstream is set. A Requirement with no workstream. | D7.1–3 | O3 for the Project, then O7; the Requirement not listed as missing a workstream | CI |
| S5 | Requirement bound walk: Scope at 6 d 23 h 59 min, 7 d and 7 d 00 h 01 min; `Ready for Project` and `Candidate 2` and `3` at 90 days. | D4.2–6 | O7, O7, O6; O7 for the queues | CI |
| S6 | `Candidate Project 1` at 2 days and at 8 days. | D4 | as G8 settles | CI, blocked by G8 |
| S7 | Project bound walk: each of Scope, `Design and Test Approach`, `User testing` and `Project Closedown` 1 minute under and 1 minute past 7 days; `Q1` and `Deployment` at 90 days. | D1.2, D4.2, D4.4, D4.6 | O7 then O6 per phase; O7 for `Q1` and `Deployment` | CI |
| S8 | `Development` with the field moved 30 days ago: last branch commit 1 day ago, then 8 days ago. | D1.4, D4 | O7, then O6 under the technical lead | CI, depends on G11 |
| S9 | A parent at its resting phase for 30 days with an open package; then the last package closes, and 8 days pass. | D1.3 | O7; then O6 under the design authority | CI, depends on G10 |
| S10 | A Decision in each of its five states, with `Turn` unset; each at 6 days and at 8 days. A Decision with no state. | D1.5, D5.1, D4 | O4 alternating `Owner`/`Claude` as M6; O7 then O6 under owner or Claude; the stateless one as G6 settles | CI |
| S11 | Pull requests in `Drafting`, `Awaiting review` and `Changes requested`, at 6 and 8 days. | D1.6, D4 | `Awaiting review` on the owner's list, the rest under the author's role; O6 at 8 days; no issue-field write to any pull request | CI |
| S12 | An infrastructure pull request with no `PR State`: a review requested of the owner; then a draft. | D1.7, D8.5 | mover owner, then author role, derived from REST | CI |
| S13 | Tickets: `New` and `In progress` at 6 and 8 days; `Pending` with its review date tomorrow, then yesterday; `Waiting on sender` at 30 days. | D1.8, D4 | O7, O6 under the owner; O7, O6; `Waiting on sender` as G7 settles | CI |
| S14 | Items in derivable states (a Project at `Development`, a Decision at `Asked`) with `Turn` unset, then wrong, then right. | D5.1–3 | O4, O4, O5 | CI |
| S15 | A Requirement at Scope carrying a thread-set `Turn` = `Owner` with an approval comment, past and within the bound. | D5.4 | as G3 settles; `Turn` not overwritten if the thread's value wins | CI, depends on G3 |
| S16 | An open item in a state whose mover the table cannot derive, with no `Turn`; then `Turn` set (quiet case). | D5.1 | reported as lost to its role or the owner; then O7 | CI |
| S17 | `Hold` reasons, each 30 days old: an open linked dependency; its dependency then closes; no reason; a named event with its review date tomorrow, then yesterday. | D5.5–9 | O7; O18; O18; O7; O18 | CI |
| S18 | A Requirement at `On Hold` with a linked issue; then with no dependency named. | D1.1, D5 | `Turn` = `Hold` (O4); then O18 | CI |
| S19 | A Requirement at Scope with `Turn` = `Hold` linked to a `Decision` at `Asked`; the Decision is `Actioned` and closed. | D1.1, D1.5, D5.5–6 | The Requirement O7 and the Decision on the owner's list; then the Requirement on its role's list (O18) | CI |
| S20 | Claims: within bound; stale; role only; malformed. | D6.2–5 | O7 with the claim shown; O8; O6 under the role, naming no thread; as G15 settles | CI |
| S21 | Black start: every type in every repository, nothing moved for 30 days, plus three items within bound holding live claims. One run. | D4.5, D6.3, D12.2 | O6 for every past-bound item, by role; O7 for the three | CI |
| S22 | Quiet case: everything within its bound. Then age one item 1 minute past its bound (the check shown to fail first). | D12.1 | O17; then O6 | CI |
| S23 | The pinned issue's body after two runs with different stalled sets. | D11 | O9 each time; the body holds the second set only | CI |
| S24 | Missed merges: a merged pull request `Refs #N` to a Production Release package at `Development`; one to a tooling-route package; `Refs` to a parent only; an unmerged pull request; a package already moved. | D9.1–5 | O16; O16; O5; O5; O5 | CI |
| S25 | A read fails at the third repository; then a rerun with the source healthy. | D8.2, D11.3 | O10; then the run completes, corrects the rest, and O9 shows the new complete-run time | CI |
| S26 | A `Turn` write is refused (403) in one repository; then permitted. | D8.3 | O10, and the item not reported as fixed; then O4 | CI |
| S27 | A REST call hangs past the limit. | D8.4 | the call cut, then O10 | CI, depends on G20 |
| S28 | One item's `issue_field_values` cannot be read; the rest can. | D3.4, D4.7 | O11 for it, normal results for the rest | CI |
| S29 | GraphQL refused for every call: `board-flow.py`, the owner's list and `--role`. | D8.5 | O15 for each | CI |
| S30 | Missed day: world W run on day 1 and day 3, against W run on day 3 alone. | D11.4 | identical end state and stalled set | CI |
| S31 | An immediate rerun with nothing changed. | D11.2 | O5 for every item; only the pinned body is rewritten | CI |
| S32 | `--role` for a workstream's design authority, for a role with nothing, for an unknown role, then a valid role again. | D10.3 | O12; O12 (says so); O19; O12 | CI |
| S33 | The owner's list over a world holding a `Turn` = `Owner` requirement, a `Decision` at `Asked`, a pull request awaiting review, and a work package in `User testing` with an unticked **owner** box. | D10.2 | O13 | CI |
| S34 | Cross-check: one world through all five callers. | D10.1–5 | O14 | CI |
| S35 | Flow-table completeness: every option of `Requirement State`, `Project State`, `Decision State`, `PR State` and `Ticket State` has a mover and a bound (or "none"). Remove one row and see the test fail. An item carrying a value not in the table. | D3.3 | the table check passes, then fails on the removed row; the item reported, not defaulted (G17) | CI |
| S36 | The table's bounds: 1 day for unset and `Triage`; 7 days for each owed state; none for `Q3` to `Q1`, `Ready for Project`, `Candidate 2` and `3`, and `Deployment`. | — | the values as stated | CI |
| S37 | Stalled output by role, including a role with no permanent thread. | D12.2–3 | grouped by role; the threadless role named alone | CI |
| TT1 | From a cloud session, a full run against the five repositories, once delivery 1's fields exist. | D2, D8.5 | completes; calls and duration recorded against about 400 calls and the rate limit; pinned issue rewritten (O9) | TT |
| TT2 | From WSL, immediately after TT1. | D11.2 | O5 except the pinned body; the same stalled set | TT |
| TT3 | `--role` for one design authority, and the owner's list, from a cloud session and from WSL. | D10.2–3 | identical lists in both places | TT |
| TT4 | A throwaway issue raised in programme with no type and no state; one run; then closed as not planned. | D1.9 | typed `Requirement`, starting state and `Turn` written | TT |
| TT5 | `Turn` and `Claimed by` written and read over REST on one issue in each of the five repositories. | D2 | written and read back in each | TT |
| TT6 | The write log of TT1 inspected for pull requests. | D1.6–7 | no issue-field write to a pull request | TT |
| TT7 | (Delivery 3) The coordinator's daily trigger, on a day with nothing stalled. | D12.1 | runs `board-flow.py`, ends without a message, outside 21:10 to 22:10 UTC | TT |
| TT8 | (Delivery 3) A day with a stalled item for a role with a thread and for one without. | D12.2–3 | the thread nudged; a thread started for the other | TT |
| TT9 | (Delivery 3) A cloud session's start. | D10.3 | its role's list shown | TT |

## 6. Refusals and successes

In a sweep, the "refusal" is the item being reported, and the "success" is it going quiet once the reason is removed.

| Refused or reported | Then succeeds |
| --- | --- |
| S2: an untyped issue is typed | S2: a world with none makes no type write |
| S4: Project with no workstream raised | S4: workstream set, then quiet |
| S16: lost item reported | S16: `Turn` set, then quiet |
| S17: `Hold` with no reason reported | S17: `Hold` with an open link stays quiet |
| S22: an item 1 minute past its bound listed | S22: the same item within its bound, quiet |
| S25: a read failure exits non-zero | S25: the rerun completes |
| S26: a refused write exits non-zero | S26: the permitted write lands |
| S32: unknown role refused | S32: a known role lists |
| S35: a missing table row fails | S35: the full table passes |

## 7. Coverage, both ways

| Rule | Scenarios |
| --- | --- |
| R1 | S10, S11, S14, S16, S34, S35 (G1, G2) |
| R2 | S3, S5, S7, S10, S11, S13, S35, S36 |
| R3 | S32, S34, S35 |
| R4 | S12, S28, S29, TT1, TT2, TT3, TT5 |
| R5 | S1, S10, S11, S12, S13, S21, S35, TT1, TT5 |
| R6 | none: by review of the documents (G26) |
| R7 | S1, S2, S4, S26, TT4 (G5, G6, G17) |
| R8 | S21, S22, S25, S30 |
| R9 | S20, S21 |
| R10 | S3 (the 1-day backstop; the thread's own act is a post-deployment check) |
| R11 | S3, S5, S23 |
| R12 | S17, S18, S19, S32, S37, TT8 (G4) |
| R13 | S15, S17, S18, S19 |
| R14 | S15, S33 (G24) |
| M1 | S3, S5, S7, S20, S22 |
| M2 | S3, S5, S6, S18, S19 |
| M3 | S15, S18, S19 |
| M4 | S7, S8 |
| M5 | S9 |
| M6 | S10 |
| M7 | S11, S12, TT6 |
| M8 | S13 |
| M9 | S14, S15, S16 |
| M10 | S15 |
| M11 | S17 |
| M12 | S3, S5, S7, S36 |
| M13 | S20, S21, S37 |
| M14 | S1, S4 |
| M15 | S19 |
| P1 | S24, S21 |
| P2 | S14, S31 |
| P3 | S34 |
| I1 | S34, S35, S36 |
| I2 | S1, S21, S23, TT1 |
| I3 | S37, TT7, TT8 |
| I4 | S25, S30 |
| I5 | S12, S24 (G13) |
| I6 | S11, TT5, TT6 |
| I7 | S32, S33, TT3, TT9 |
| I8 | S1, S14, S31, TT2 |
| I9 | S25, S26, S28 |
| I10 | S27 |
| I11 | S29, TT1 |

| Scenario | Rules |
| --- | --- |
| S1 | R5, R7, M14, I2, I8 |
| S2 | R7, M7 |
| S3 | R2, R10, R11, M1, M2, M12 |
| S4 | R7, M14 |
| S5 | R2, R11, M1, M2, M12 |
| S6 | M2 |
| S7 | R2, M1, M4, M12 |
| S8 | M4 |
| S9 | M5 |
| S10 | R1, R2, R5, M6 |
| S11 | R1, R2, R5, M7, I6 |
| S12 | R4, R5, M7, I5 |
| S13 | R2, R5, M8 |
| S14 | R1, M9, P2, I8 |
| S15 | R13, R14, M3, M9, M10 |
| S16 | R1, M9 |
| S17 | R12, R13, M11 |
| S18 | R12, R13, M2, M3 |
| S19 | R12, R13, M2, M3, M15 |
| S20 | R9, M1, M13 |
| S21 | R5, R8, R9, M13, P1, I2 |
| S22 | R8, M1 |
| S23 | R11, I2 |
| S24 | P1, I5 |
| S25 | R8, I4, I9 |
| S26 | R7, I9 |
| S27 | I10 |
| S28 | R4, I9 |
| S29 | R4, I11 |
| S30 | R8, I4 |
| S31 | P2, I8 |
| S32 | R3, R12, I7 |
| S33 | R14, I7 |
| S34 | R1, R3, P3, I1 |
| S35 | R1, R2, R3, R5, I1 |
| S36 | R2, M12, I1 |
| S37 | R12, M13, I3 |
| TT1 | R4, R5, I2, I11 |
| TT2 | R4, I8 |
| TT3 | R4, I7 |
| TT4 | R7 |
| TT5 | R4, R5, I6 |
| TT6 | M7, I6 |
| TT7 | I3 |
| TT8 | R12, I3 |
| TT9 | I7 |

Every scenario serves a rule. R6 has no scenario (G26).

## 8. Approach

**What runs, and where.**

- [CI] tests are component tests of `board-flow.py`, `board-actions.py` (owner's list, `--role` and `--claude`) and `board-check.py`. Each is run in-process or as a subprocess against the stubbed REST source.
- [TT] tests run the real scripts against the five real repositories: TT1 to TT6 from a cloud session (TT2 and TT3 also from WSL) before the merge; TT7 to TT9 in delivery 3's work package.

**What is real, and what is stubbed.** In CI the flow table, the model and the scripts are real. GitHub is the stubbed REST source, which:

- serves each issue's type, `issue_field_values`, timeline (`issue_field_changed` events), sub-issues, `blocked_by` links, body (its *Dependencies and related work* section), comments, and pull requests with reviews, merge state, `Refs` in their bodies, and branch commits;
- refuses every GraphQL call;
- logs every write with its target and value;
- can be set to fail a given read, refuse a given write with 403, or hang a given call.

The pinned issue is an issue in the stub's programme repository.

**How time is manipulated.** The run is given a fixed *now*, and every timeline event and commit in the world is dated relative to it, so boundaries are exact to the minute. If the scripts take no injectable clock, that is a finding for the build. The 120 s cut is tested with a hanging stub call and a shortened limit (G20).

**What state each test starts from.** Each test builds its own world in a temporary directory and leaves nothing behind. Each check's test includes its quiet case, and each new check (stalled, lost, missing workstream, invalid hold, table completeness) is shown to fail first by breaking what it watches (S2, S16, S22, S35). Every write that can fail open (the `Turn` write, R7's writes, the merge move and the pinned-issue rewrite) has a CI test of its failure (S25, S26, S27).

**Whose move.**

- **owner:** delivery 1. Create `Turn` (`Owner` green, `Claude` blue, `Hold` yellow) and `Claimed by` (text) as organisation issue fields, and the board view filtering `Turn` = `Owner` grouped by issue type. Then confirm the view shows a test item set to `Owner`. These are organisation settings, out of a cloud session's reach. TT1 to TT6 wait on this.
- **Claude:** every [CI] test, TT1 to TT9, and reading the fields over REST (TT5) as the check that delivery 1 landed.
- **owner:** decide G22 before TT1, TT2 and TT4 write to the real repositories.

### Post-deployment checks (checks, not tests)

One per requirement. Each is answered after a week of daily runs.

| Requirement | Check |
| --- | --- |
| R1 | **Claude:** the pinned issue and a REST read show every open issue with a `Turn`, apart from items reported *not visible*. |
| R2 | **Claude:** each item listed as stalled during the week was past a bound the flow table states. |
| R3 | **Claude:** the owner's list, each `--role` list and the stalled list agree for one day's board, and 1.2, 1.6 and 1.7 link to the table rather than restating it. |
| R4 | **Claude:** a cloud thread ran `--role` at start and at wake during the week. |
| R5 | **Claude:** every type in every repository appeared on some list during the week. |
| R6 | **Claude:** the vocabulary in 1.2 and 1.6 names its source (Kanban, ITIL). |
| R7 | **Claude:** no open issue is untyped or stateless one day after it was raised. |
| R8 | **owner:** one stalled item was picked up within a day of the coordinator's nudge. |
| R9 | **Claude:** no item was started by two threads; claims named the working thread. |
| R10 | **Claude:** each requirement raised in the week had its minimum fields, or an owner question, on the day it was raised. |
| R11 | **Claude:** no requirement sat past its bound without appearing on the stalled list. |
| R12 | **Claude:** each stalled requirement's thread was nudged, or a thread was started. |
| R13 | **Claude:** each open requirement is either owed a move within its bound or rests in one of the R13 states. |
| R14 | **owner:** the view shows him what waits on him without opening an issue. |

## 9. Test names

### Starting states and types (R7)

- `untyped_issue_in_each_repository_becomes_a_requirement`
- `pull_request_is_never_given_an_issue_type`
- `stateless_project_starts_at_scope`
- `stateless_ticket_starts_at_new`
- `rerun_writes_nothing_once_states_are_valid`
- `project_without_workstream_is_raised_with_the_owner`
- `requirement_without_workstream_is_left_for_triage`
- `unknown_state_value_is_reported_not_defaulted`

### Bounds and stalling

- `triage_is_stalled_one_minute_past_a_day`
- `triage_at_exactly_a_day_is_not_stalled`
- `scope_requirement_is_stalled_past_seven_days_under_its_design_authority`
- `queues_and_candidate_slots_two_and_three_never_stall`
- `project_phases_stall_past_seven_days`
- `q1_and_deployment_never_stall`
- `development_age_is_read_from_the_last_branch_commit`
- `parent_waiting_on_open_packages_does_not_stall`
- `decision_stalls_past_seven_days_on_whoevers_turn_it_is`
- `pull_request_stalls_past_seven_days_in_any_state`
- `pending_ticket_stalls_after_its_review_date`
- `nothing_stalled_publishes_an_empty_list_and_exits_clean`
- `one_item_past_its_bound_breaks_the_quiet_list`

### Turn and holds

- `decision_turn_alternates_owner_and_claude`
- `derivable_turn_is_written_and_a_wrong_one_corrected`
- `correct_turn_is_not_rewritten`
- `item_with_no_derivable_turn_and_none_set_is_reported_lost`
- `hold_with_an_open_dependency_rests`
- `hold_whose_dependency_closed_returns_to_its_role`
- `hold_without_a_reason_is_reported`
- `hold_past_its_review_date_is_reported`
- `on_hold_requirement_derives_turn_hold`
- `requirement_waiting_on_a_decision_rests_while_the_decision_is_listed_for_the_owner`
- `pull_request_awaiting_review_is_the_owners_and_carries_no_issue_field`
- `infrastructure_pull_request_mover_is_derived_from_rest`

### Claims and recovery

- `live_claim_within_bound_is_not_offered`
- `stale_claim_is_offered_to_the_roles_current_thread`
- `role_only_claim_names_the_role_alone`
- `black_start_lists_every_past_bound_item_by_role_and_nothing_else`
- `role_without_a_permanent_thread_is_listed_by_role`

### Missed events

- `merged_refs_moves_a_production_release_package_to_deployment`
- `merged_refs_moves_a_tooling_package_to_post_deployment`
- `refs_to_a_parent_moves_nothing`
- `unmerged_pull_request_moves_nothing`

### Failure and reach

- `read_failure_keeps_earlier_writes_and_names_the_item_and_call`
- `refused_write_exits_non_zero_and_is_not_reported_as_fixed`
- `hung_call_is_cut_and_treated_as_a_failure`
- `failed_run_leaves_the_last_complete_run_time_unchanged`
- `unreadable_field_is_not_visible_and_never_defaulted`
- `whole_run_succeeds_with_graphql_refused`
- `missed_day_ends_in_the_same_state_as_a_single_run`
- `immediate_rerun_writes_only_the_pinned_issue`

### Lists and the single source

- `role_list_holds_exactly_its_items_oldest_first_with_age_and_bound`
- `role_with_nothing_says_so`
- `unknown_role_is_refused`
- `owners_list_adds_turn_owner_items_and_keeps_its_three_sources`
- `every_open_item_has_exactly_one_mover_across_all_lists`
- `stalled_set_matches_past_bound_items_on_the_role_lists`
- `flow_table_covers_every_option_of_every_state_field`
- `flow_table_bounds_are_a_day_for_triage_seven_elsewhere_none_for_queues`

### [TT]

- `cloud_session_runs_the_sweep_against_all_five_repositories`
- `wsl_rerun_after_cloud_run_writes_nothing_new`
- `role_list_is_the_same_from_cloud_and_wsl`
- `raised_untyped_issue_is_typed_and_started_by_the_real_sweep`
- `turn_and_claimed_by_round_trip_over_rest_in_each_repository`
- `real_sweep_writes_no_issue_field_to_a_pull_request`
- `daily_trigger_ends_silently_when_nothing_is_stalled` (delivery 3)
- `daily_trigger_nudges_or_starts_the_roles_thread` (delivery 3)
- `cloud_session_start_shows_its_roles_list` (delivery 3)

## 10. Gaps

Each is a question for the owner, or for the design authority. Settled on 2026-11-13 in [implementation.md](implementation.md#details-settled-from-the-test-design), except G1, G4 and G25, which change requirement wording.

| Gap | What would make the missing test fail | What it would take to close it | Why it is acceptable for now |
| --- | --- | --- | --- |
| G1 R1 says "exactly one" mover, but `Design and Test Approach` (design authority, test manager, owner), `User testing` (owner, technical lead), `Deployment` (technical lead, release manager) and joint `Triage` (owner first, then the thread) each name more than one. | `every_open_item_has_exactly_one_mover` would fail on any of these states, or pass only by picking one arbitrarily. | Name one mover per state in the flow table (for example, the holder, with the others' boxes on the owner's list), or restate R1 as "one holder". | Blocks S34's invariant for these states only. |
| G2 A `Hold` or `On Hold` item has "nobody, until its trigger" (M2), against R1. `Turn` has no value for a tool mover (R1 allows tools; `Deployment` waits for one). | The invariant test cannot say who the mover of a held item is; a held item past its review date has no named list to appear on. | State that the hold's reviewer, the role holding the item, is its mover at the review bound, and which `Turn` a tool's wait takes (`Hold`?). | S17 asserts O18 "reported to its role", an assumption to confirm. |
| G3 The model writes `Turn` wherever the state's mover is derivable (M9), yet a Requirement at Scope (derivable: Claude) waiting on the owner's approval carries a thread-set `Owner` (M3, M10), and a Scope one waiting on a Decision carries `Hold`. | S15 cannot say whether the sweep overwrites the thread's `Owner` with `Claude`. If it does, R14's approvals vanish daily; if it does not, a wrong `Turn` is never corrected. | A precedence rule: a thread-set `Owner` with an approval comment, or a `Hold` with a valid reason, is kept; otherwise the derived value wins. | S15 is blocked until settled. |
| G4 R12: "stays at Scope only while it waits on something specific, named under its dependencies". M2 and docs/1.2 §2.23: a waiting requirement moves to `On Hold`. | Whether a Scope requirement with a named dependency past 7 days is stalled or resting cannot be asserted. | Reword R12, or confirm Scope + `Turn` = `Hold` + a dependency is the sanctioned form (M3). | S19 assumes the M3 form. |
| G5 R7 and M14 write a stateless requirement's "starting state", but docs/1.2 §2.23 keeps unset ("nobody has looked") apart from `Triage` ("somebody is looking"). | S1 cannot say whether the sweep writes `Triage`; writing it erases the inbox signal. | Say whether unset is a valid starting state for a Requirement (so nothing is written) or §2.23 changes. | S3 tests the bound on both values, which is the same either way. |
| G6 A Decision raised without a state gets "a starting state" (M6), which is not named. | S10's stateless Decision has no expected value. | Name it (presumably `Asked`) in the flow table and 1.2. | One case. |
| G7 Tickets: no bound or `Turn` is stated for `Waiting on sender` (the sender's move), `Resolved` or `Refused` (who closes, and when), and `Pending`'s bound is "the review date", not 7 days. | S13 cannot assert those states. | Rows in the flow table, and 1.8 updated, as design.md says it must be. | The owner's states are covered. |
| G8 `Candidate Project 1`'s bound is "one sweep", written when the sweep was weekly; the sweep is now daily (P2). | S6 cannot say whether 2 or 8 days is stalled. | State the bound in days. | S6 is blocked. |
| G9 A stale claim: the sweep "offers it to the role's current thread" (M13), but I2 says it "clears stale claims". | S20 cannot assert the claim field after the run. | Pick one: clear the field and list the item, or keep it and list it as offered. | S20 asserts the listing, which both readings share. |
| G10 Which `Project State` a parent holds while its packages run, and how the model tells "resting on packages" from "stalled at design". | S9 cannot set up the parent's state, and the 7-day bound would list every running parent. | State the parent's resting state and rule: open sub-projects suspend its bound. | S9 is blocked. |
| G11 `Development`'s bound is "7 days without a commit", but the branch to read is not named (the project's delivery branch from its pull request? Its name?). | S8 cannot build a world. | Name the source: the work package's open pull request's head commit, read over REST. | S8 depends on it. |
| G12 `Post-deployment`'s review is "due after 7 days"; whether it is stalled at 7 days or at a later bound is unstated. | S7 cannot assert `Post-deployment`. | State the stall bound (for example, 7 days after due). | Today's `REVIEW_DUE_DAYS` reminder stands meanwhile. |
| G13 A missed deploy is corrected by "the next sweep" (I5), but no source is given for what a deploy shipped (release record, closed milestone, tag). | No scenario can be written for D9.6. | Name the source the sweep reads. | `deploy.sh` makes the move today. |
| G14 The result of an invalid `Hold` (no reason, released dependency, review date passed) is not stated: listed for the role, `Turn` rewritten, or both. | S17 asserts O18, which may be wrong. | State the outcome. | The listing is the minimum either reading gives. |
| G15 A malformed `Claimed by`, or a claim naming a role other than the state's mover, has no stated result. | S20's malformed case has no expected value. | State that it is reported and treated as no claim. | One case. |
| G16 A pull request's claim is "the thread that owns its branch" (M7), but how the model knows that is unstated. | No test can show a pull request's claim. | Name the source (for example, the branch name's prefix). | Pull requests' movers are covered through `PR State`. |
| G17 Whether a value not in the flow table (a renamed option) is an "invalid state" under R7, and what is written. | S35's second half has no expected value. | State that it is reported, never rewritten, as 1.6 says of renamed options. | Reporting is asserted. |
| G18 What `board-flow.py` does when the pinned issue does not exist (delivery 3 creates it after delivery 2 merges). | Untested. | State it: refuse, or create the issue. | TT1 runs after delivery 3, or the issue is made by hand first. |
| G19 Whether an item already on one of the owner's three existing sources and also carrying `Turn` = `Owner` appears once or twice. | S33 cannot assert the count. | State it (once). | Minor. |
| G20 The 120 s cut (I10) can only be tested quickly if the limit can be injected. | S27 would take two minutes per run, or not run. | A setting for the limit, per docs/1.10. | The figure itself is reviewed. |
| G21 No exit status is stated for `board-flow.py` beyond "non-zero on failure". The coordinator must tell *clean*, *stalled found* and *failed* apart, and docs/1.2 §2.16 makes a stall report a check. | S22 and S25 cannot assert codes, and a run that fails could look like one that found stalls. | State them, as `board-hosts.py` does (0 clean, 1 finding, 2 unreadable). | S22 asserts the output, not the code. |
| G22 No read-only mode is stated, so TT1, TT2 and TT4 write `Turn` and R7's fixes to the real repositories before the merge. Programme tooling has no environment between. | A bug found by TT1 would already have written to every open issue. | Either a `--dry-run` that writes nothing and prints what it would write, or the owner accepts that TT1 is the first real run. | Writes are reversible issue-field values. |
| G23 *Stalled* includes "a mover that is not running" (M1), which REST cannot observe; only the bound can show it. | No test can show a stopped thread except through the bound. | Accept that a stopped thread is detected only at the bound. | That is how R8 is met in every scenario. |
| G24 R14 asks which of the ten resting states each requirement is in. `Turn` shows `Owner` or `Hold`, and the view filters on `Owner` only, so telling the two `On Hold` kinds and the planning wait apart still needs the issue or another column. | The R14 post-deployment check may fail. | Confirm the view's columns (state, dependency link) or a derived list. | The owner judges R14's check. |
| G25 R11 and R12 say the `board-sweep` lists and nudges; the design moves both to the daily run, and the weekly `board-sweep` keeps planning. | No test checks that the weekly sweep shows stalled requirements. | Reword R11 and R12, or have the weekly sweep read the pinned issue. | The pinned issue is visible at the weekly sweep. |
| G26 R6 (names from Kanban and ITIL) is a property of the documents, not of the code. | No test can fail. | None: a review by the document reviewers. | By review. |

Derived by a fresh `test-designer` agent that read no implementation (docs/1.9).
