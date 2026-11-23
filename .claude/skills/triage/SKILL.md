---
name: triage
description: Raise, title and triage any issue, whether requirement, project or decision. The minimum fields, how to write a short title that names the thing, what carries a milestone and when Claude triages alone. Use when raising or retitling an issue, or when sweeping the board for untriaged ones.
---

# Triage

**Triage is joint, except where Claude triages alone.** Raising a project
folds and closes requirements, and setting a stage or a milestone commits to a
shape, and none of that is cheap to reverse. So by default the owner comments
first, and Claude writes the triage comment and sets the fields from his
([1.2 §2.17](../../../docs/1.2-change-lifecycle.md#what-triage-asks)). Until
he has commented, the issue waits for him.

**Claude triages alone**:

- in Process Definition;
- in Programme Tooling;
- in each application's Delivery Tooling;
- for type `tooling` or `documentation`, in any workstream;
- for a dependency advisory, where only whether one can wait goes to the owner
  ([1.2 §2.2.1](../../../docs/1.2-change-lifecycle.md#221-business-as-usual-updates)).

There, Claude classifies, scopes, groups, folds and closes, except what comes
to the owner whatever its workstream
([1.7 *Owner*](../../../docs/1.7-roles-and-responsibilities.md#owner)):

- anything reaching production;
- the product and its rules;
- anything irreversible outside git;
- a new or changed rule;
- anything another role judges he would want to see.

Triaging alone outside that scope is the expensive mistake: check the
workstream and the type first.

[`CLAUDE.md`](../../../CLAUDE.md) and
[`docs/1.2`](../../../docs/1.2-change-lifecycle.md) hold the rules. This skill
gives the order to ask in, the title rules, the milestone table and the common
mistakes.

## The three passes

### 1. The minimum, before anything else

| Field | What it holds |
| --- | --- |
| a short title | the name of the thing, by this pass's title rules |
| `Workstream` | who owns it; unset is the triage queue |
| `Priority` | a judgement |
| `Type of change` | `bug`, `functional`, `non-functional`, `cosmetic`, `documentation` or `tooling` |

Three conditions on the fields
([1.6 *Which level carries which field*](../../../docs/1.6-github-project-board.md#which-level-carries-which-field)):

- A `Decision` issue carries neither `Type of change` nor `Priority`, because
  it routes work.
- A project's `Priority` is required once it is past Scope.
- A requirement's `Route` is known by Candidate Project; a work package or
  standalone project carries one, and a parent never does.

The questions behind the fields, and the triage comment that records the
answers, are 1.2's
[*What triage asks*](../../../docs/1.2-change-lifecycle.md#what-triage-asks)
and
[`docs/templates/triage-comment.md`](../../../docs/templates/triage-comment.md).

**A title is a short, memorable name that says what the thing is.** It lets the
owner recall an issue from the board without reading the body, so it holds the
key words of the change. It holds for every type of issue. Retitle on sight
when an existing title fails this test.

**Cut further than feels natural.** These examples are Tile Lite Elite's titles:

| Too long | Short |
| --- | --- |
| Monitoring and alarming: closing the remaining gaps | Monitoring and alarming gaps |
| Disaster recovery: untested VM rebuild | Test VM rebuild |
| Desktop client: is it a product, and where to get it | Desktop client download |
| Board tooling: verify matched field values still exist | Project Board: check field values exist |
| Rehearsal and production: infrastructure drift, no update procedure | VM updates |

Four things generalise from the set:

- **Drop the words that only describe.** A qualifier earns
  its place only if removing it would make two issues look the same.
- **Fold a short answer into the noun phrase.** Keep the colon only for a
  genuine two-part subject: *X: closing the gaps* becomes *X gaps*.
- **Name the actionable subject.** Ask what the issue is for: *updates*, where
  the symptom was *drift*.
- **Pick the word a reader recognises with no other context**, especially
  where an application's own vocabulary would collide. In Tile Lite Elite,
  *board* on its own reads as the game board, so the title says *Project
  Board*; *user name* means more out of context than *display name*, so
  *Display name rules* became *User name format*. The body carries the exact
  term.

The structural prefix (`#N MAIN PROJECT:`, `#N WP A Del 1 of 2:` and the other
forms in [1.2 *Naming*](../../../docs/1.2-change-lifecycle.md#naming)) is
never cut. These rules apply to what follows it.

### 2. Scope

Claude records the options, the dependencies and the `Effort`, and moves
`Requirement State` to `Scope, Options and Dependencies`.

### 3. Project planning

The outcome is one of five
([1.2 §2.17 *The outcomes*](../../../docs/1.2-change-lifecycle.md#the-outcomes)).
Every outcome but *on hold* ends with the requirement closed:

| Outcome | What it means |
| --- | --- |
| straight to `main` | a pre-approved change, with no project and no milestone; the requirement is closed by hand |
| solo project | raise the project and fold this requirement into it (`raise-project`) |
| grouped project | fold it into one that exists (`raise-project`, *Folding the requirements it takes*) |
| on hold | `Requirement State` is `On Hold`, and the body says what it waits for |
| cancelled | close it as `not planned`, with why |

## What carries a milestone

The rules are
[1.2 §1.1](../../../docs/1.2-change-lifecycle.md#11-what-a-milestone-says); in
short:

| Issue | Milestone |
| --- | --- |
| a requirement | none: it delivers by a project's work package, or straight to `main` |
| a parent project | none: it has no delivery role |
| a change done straight on `main` | none: no single point in time |
| a work package shipping in a release | the semver |
| a work package on the `Application Tooling` or `Other` route | none until it lands, then the day it landed, `YYYY.MM.DD-n`; host maintenance takes the infrastructure application's milestones |
| work packages delivered together | the same milestone |
| a decision | none: it routes work |

**The route decides.** A `Production Release` or `Application Tooling`
delivery takes a branch and a pull request, and an `Other` delivery is applied
on a host or in a console. Each of these is made at one point in time, so each
takes a milestone and a row in the delivery log (`3.n.1`). A cloud session's
own pull request for a Docs and Programme Tooling change is incidental to its
route, which takes no milestone and no row.
Which deliveries need a sub-project issue is 1.2's table in
[*The model, and the four cases that follow from it*](../../../docs/1.2-change-lifecycle.md#the-model-and-the-four-cases-that-follow-from-it).

## Common mistakes

**Setting a milestone on a folded requirement.** The `folded` label marks a
requirement a project owns now: the project carries the milestone.

**Answering "does it reach users" from `Type of change`.** The answer is
`Route`. `Application Tooling` and `Docs and Programme Tooling` are routes,
and `documentation` and `tooling` are types of change.

## Checks after triage

In the programme's own checkout the paths are `scripts/board/…`.

```bash
programme/scripts/board/board-check.py             # has it done the work its stage claims?
programme/scripts/board/board-actions.py           # is it waiting on the owner?
programme/scripts/board/board-actions.py --claude  # is it waiting on Claude?
```

An issue that is triaged and on nobody's list is the failure to look for. Its
workstream and stage put it on one.
