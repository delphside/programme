<!-- markdownlint-disable-file MD041 -->
# Post-deployment review: Scripts sub-folders

Work package: `delphside/tile-lite-elite#421` *Scripts sub-folders* (a project
with deliveries 1 and 2 of its own; delivery 3, the application's scripts,
moved to delphside/tile-lite-elite#485 *Programme repository shared by every
application*) · delivery: `main` · reviewed: 2026-11-16

## 1. Was the intended scope delivered?

| In scope | Delivered | Note |
| --- | --- | --- |
| R1 scripts in `application/` and `programme/` folders | Moved | The programme half was delivered in delivery 2 (2026-09-30). The application half moved to delphside/tile-lite-elite#485 R9 on 2026-10-16, where the repository split made the two levels redundant |
| R2 an application-tooling change takes a branch; the hook warns | Moved | To delphside/tile-lite-elite#485 R10, unchanged |
| R3 one PR State writer, in Python | Yes | `sync-pr-state.sh` is gone, replaced by `board-pr-state.py` (94e44d1) |
| R4 Repository Change route split in two | Yes | Delivery 1 (582461b, 752b808, 7ec301c). Its post-deployment check, that a merged tooling package moves on its own, is not met: see section 2 |
| R5 every document classified in one list | Yes | `board/documents.py`, asked through `board-documents.py` |
| R6 CI split by side | Moved | To delphside/tile-lite-elite#485 R11, split by repository instead |

**Anything deferred:** R1, R2 and R6 went to delphside/tile-lite-elite#485
*Programme repository shared by every application*, by the owner on 2026-10-16,
with their post-deployment checks. R4's merge gap went to
delphside/programme#176 *Project Board flow* (section 4).

The recorded passes were re-checked on 2026-11-16 from the Tile Lite Elite
checkout:

- R3: `grep -rn sync-pr-state` finds the name only in historical records
  (`records/2.4-weekly-digest/PRG_WD_2026_W43.md` and the design notes of
  delphside/tile-lite-elite#383 *Project Board tooling: one shared model*,
  which mark it retired). No script, hook or workflow names it.
  `board-pr-state.py --check` could not be re-run: through REST alone it stops
  with "no 'PR State' field on the project", so the 2026-11-09 result of 0
  drifted is not re-confirmed.
- R5: `board-documents.py kind docs/*.md CLAUDE.md AGENTS.md` answers for all
  33 files: 27 application, 4 programme, 2 generated, none unclassified. The
  recorded 28 application documents have since become 27.

## 2. What happened that was not planned for?

- The R4 check is not met for a pull request merged on GitHub.
  delphside/tile-lite-elite#597 *deploy.sh can leave production stopped* was
  delivered by delphside/tile-lite-elite#598 *deploy.sh restarts the server if
  the snapshot fails*, rebase-merged on 2026-11-15. Its note left the date
  milestone and the move to Post-deployment as a box for the local session.
- The project's scope shrank: the repository split removed delivery 3 and
  changed R6.

## 3. Why — what was the cause?

The move is made by the `post-merge` hook, which fires only on a local merge of
a `<N>-branch` into `main`; the hook tells that merge from a pull by its reflog
entry. A cloud session merges on GitHub, where no hook runs, so the move had no
trigger there. R4 was written when the owner merged locally.

## 4. What happens next?

| Finding | Pre-approved change, requirement or project | Or why no change |
| --- | --- | --- |
| R4 not met for a pull request merged on GitHub | delphside/programme#176 *Project Board flow*: the merging thread moves its work package by route, and the next sweep lists a missed one from `Refs #N` (`implementation.md`, events table; test S24) | |
| R4's check stays unanswered here | | #176's tests answer it, so this row closes as moved rather than waiting for another merge |
| `board-pr-state.py --check` not re-run | | The 2026-11-09 pass stands. The check needs the board's field, which REST alone cannot read; the next local run answers it |
| R1, R2 and R6 checks | delphside/tile-lite-elite#485 *Programme repository shared by every application* | Moved, not answered here |

## 5. Areas to consider

- **Scope** — changed on 2026-10-16 (delivery 3 folded into
  delphside/tile-lite-elite#485), recorded in the issue's comment of that day.
- **The milestone** — none was set: both deliveries went straight to `main`.
- **Documentation** — nothing found wrong now. The retired milestone word
  `pre-approved` in the deliveries table is left as the record.
- **Tooling** — a hook that runs on one way of merging is a silent gap in every
  other way.
- **The process** — a "straight to `main`" row survived a project that later
  split by repository without harm.

## 6. Lessons learnt

A move wired to a local hook does not run for work merged on GitHub, so a check
on "the next merge" should name how it merges. Folding delivery 3 into the
repository split was cheaper than finishing a layout the split would undo.
