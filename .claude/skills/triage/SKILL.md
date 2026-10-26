---
name: triage
description: Raise, title and triage any issue, whether requirement, project or decision. The minimum fields, how to write a short title that names the thing, what carries a milestone, and when Claude triages alone. Use when raising or retitling an issue, or when sweeping the board for untriaged ones.
---

# Triage

**Triage is joint, except where Claude triages alone.** Raising a project
folds and closes requirements, and setting a stage or a milestone commits to a
shape; none of that is cheap to reverse, so by default Claude presents the
questions and waits.

**Claude triages alone in Process Definition, Programme Tooling and each
application's Delivery Tooling, and for type `tooling` or `documentation` in
any workstream.** Everything else in those areas is Claude's to classify,
scope, group, fold and close, except what still comes to the owner whatever
its workstream ([1.7 *Who decides*](../../../docs/1.7-roles-and-responsibilities.md#who-decides)):

- anything reaching production;
- the product and its rules;
- anything irreversible outside git.

Folding closes issues and un-folding is manual, so triaging alone outside that
scope is the expensive mistake: check the workstream and the type first.

The rules live in [`CLAUDE.md`](../../../CLAUDE.md) and
[`docs/1.2`](../../../docs/1.2-change-lifecycle.md). This skill is the order to
ask in, and the common mistakes.

## The three passes

### 1. The minimum, before anything else

| Field | What it holds |
| --- | --- |
| a clear short description | the title is what is read in a list of forty |
| `Workstream` | who owns it. **Unset is the triage queue** |
| `Priority` | a judgement, deliberately not derived |
| `Type of change` | `bug · functional · non-functional · cosmetic · documentation · tooling` |

The questions behind them, and the triage comment that records the answers,
are 1.2's [*What triage asks*](../../../docs/1.2-change-lifecycle.md#what-triage-asks)
and [`docs/templates/triage-comment.md`](../../../docs/templates/triage-comment.md).

**A title is a short, memorable name that says what the thing is.** It lets
the owner recall an issue from the board without reading the body, so it holds
the key words of the change. It applies to a project's title as much as a
requirement's. Retitle on sight when an existing title fails this test.

**Cut further than feels natural.** Examples:

| Too long | Short |
| --- | --- |
| Monitoring and alarming: closing the remaining gaps | Monitoring and alarming gaps |
| Disaster recovery: untested VM rebuild | Test VM rebuild |
| Desktop client: is it a product, and where to get it | Desktop client download |
| Display name rules | User name format |
| Board tooling: verify matched field values still exist | Project Board: check field values exist |
| Rehearsal and production: infrastructure drift, no update procedure | VM updates |

Four things generalise from the set:

- **Drop the words that describe rather than identify.** A qualifier earns its
  place only if removing it would make two issues look the same.
- **Fold a short answer into the noun phrase; keep the colon only for a
  genuine two-part subject.** *"X: closing the gaps"* becomes *"X gaps"*.
- **Name the actionable subject.** Ask what the issue is for: *updates*, where
  the symptom was *drift*.
- **Pick the word a reader recognises with no other context**, especially
  where an application's own vocabulary would collide. In Tile Lite Elite,
  *board* on its own reads as the game board, so the title says *Project
  Board*; *user name* means more out of context than *display name*. The body
  carries the exact term.

The structural prefix (`#N MAIN PROJECT:`, `#N WP A Del 1 of 2:` and the other
forms in [1.2 *Naming*](../../../docs/1.2-change-lifecycle.md#naming)) is
never cut; these rules apply to what follows it.

### 2. Scope

Options, dependencies, `Effort`. `Requirement State` moves to *Scope, Options
and Dependencies*.

### 3. Project planning

The outcome is one of five:

| Outcome | What it means |
| --- | --- |
| **solo project** | raise it with the `raise-project` skill |
| **grouped project** | fold it into one that exists |
| **straight to `main`** | a pre-approved change, no project |
| **on hold** | `Requirement State` = `On Hold`, and the body says what it waits for |
| **cancelled** | closed, with why |

## What carries a milestone

The rules are
[1.2 §1.1](../../../docs/1.2-change-lifecycle.md#11-what-a-milestone-says); in short:

| Issue | Milestone |
| --- | --- |
| a requirement, ordinarily | none: it is not a thing that ships |
| a requirement done directly, no project raised | `pre-approved` |
| a parent project | none: it has no delivery role |
| a requirement or project done straight on `main` | `pre-approved` |
| a work package shipping in a release | the semver |
| a work package delivering without an image, other than host maintenance | production's current version plus a letter |
| a host-maintenance work package | the infrastructure application's date, `YYYY.MM.DD-n` |
| work packages delivered together | the same milestone |
| a decision | none: it routes work |

**What was done decides.** A change that took a branch and a pull request, or
was applied on a host or in a console, has made a delivery at one point in
time: a milestone and a row in the delivery log (`3.n.1`). Which deliveries
need a sub-project issue is 1.2's table in
[*The model, and the four cases that follow from it*](../../../docs/1.2-change-lifecycle.md#the-model-and-the-four-cases-that-follow-from-it).

**`no-release` is provisional.** It says *not a release* before anybody knows
how the change will reach `main`. Resolve it to `pre-approved`, a letter, a date or a
semver before the issue closes, or the record of how that change was delivered
is lost.

## Common mistakes

**Setting `pre-approved` on a requirement that was folded.** Folded means a
project owns it now; the project carries the milestone and the requirement
carries none. The `folded` label is the signal.

**Answering "does it reach users" from `Type of change`.** It is `Route`:
`Application Tooling and Docs` and `Programme Tooling and Docs` are routes, and
`documentation` and `tooling` are types of change.

## Afterwards

```bash
programme/scripts/board/board-check.py             # has it done the work its stage claims?
programme/scripts/board/board-actions.py           # is it waiting on the owner?
programme/scripts/board/board-actions.py --claude  # is it waiting on Claude?
```

**An issue that is triaged and on nobody's list is the failure to look for.**
The workstream and the stage put it on one.
