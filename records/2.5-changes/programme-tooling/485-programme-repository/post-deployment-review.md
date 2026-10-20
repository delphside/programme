# Post-deployment review: Programme repository

Project: delphside/tile-lite-elite#485 · three deliveries: 1 by hand
(2026-10-16), 2 as `0.9.1a` (2026-10-16 to 18), 3 as work package #527
(2026-10-20) · reviewed: 2026-10-20, by Claude; the owner reviews it

- [ ] **owner** — save the token as the `BOARD_TOKEN` Actions secret in the
  programme repository
- [ ] **Claude** — record on #485's R10 row the owner's acceptance of the
  bats test (decision card, 2026-10-20)
- [ ] **Claude** — run the board sweep by hand once `BOARD_TOKEN` is saved in
  the programme repository, and record on #485's R2 check whether it added
  the other repositories' items
- [ ] **Claude** — once tile-lite-elite#535 merges, answer #527's checks and
  update 3.1.2 and 3.1.6
- [ ] **owner** — read this review; after the boxes above are ticked, #485
  moves to Project Closedown and closes with #527

## 1. Was the intended scope delivered?

| in scope | delivered | note |
| --- | --- | --- |
| R1 generic assets in one place | yes | the one shared file is a #406 trial, not a generic asset |
| R2 application assets only; one board | documents yes; board not yet shown | the documents half passed on 2026-10-18. The board half has a sweep (programme#59) whose first run had no token |
| R3 consumed through a submodule | yes | |
| R4 a session loads the rules | yes | for Tile Lite Elite; the others have no skills or agents of their own yet |
| R5 Tile Lite Elite first | yes | |
| R6 records in the programme | yes | `applications/tile-lite-elite/` holds 3.1.1 to 3.1.7 |
| R7 a project spans both repositories | yes | #515's records and #518's branch |
| R8 no application fact in the tooling | partly | scripts and hooks hold none; the reference reviewer's table is in the technical profile (#527: programme#53, tile-lite-elite#532); the other agents and skills still name Tile Lite Elite |
| R9 scripts grouped by purpose | yes | |
| R10 a warning, not a refusal, on `main` | yes, by test | no commit has touched an application script on `main` since the merge; the owner accepted the bats test on a decision card on 2026-10-20 |
| R11 CI split by repository | yes | |
| all: a production deploy from the moved scripts | not yet | handed to the 0.9.2 release's checks (owner, 2026-10-20) |

**Added during the project, at the owner's direction:** the board sweep
(programme#59, merged); the technical profile renamed `app-profile.toml`
(programme#57 merged, tile-lite-elite#535 open).

**Deferred:** the remaining agents and skills to programme#58, for Dark
Portal's first use. The board reports and `PR State` for other repositories
to programme#63. Issue numbers across repositories to #383 R13.

## 2. What happened that we did not plan for?

1. **The cloud loads more than the design assumed.** Stage 1's trial found a
   cloud thread loads every project repository's skills and agents from the
   checkout beside it, and runs no repository's `settings.json` hooks. A
   setup script per repository replaced the hooks there.
2. **Planned work slipped out of delivery 2 untracked.** The design listed
   the reference reviewer's file table as stage 2 work. It did not ship, and
   only #514's left-out list recorded that, not #485, so nothing tracked it
   until the R8 check failed.
3. **The board took only one repository's items.** GitHub Free allows one
   auto-add rule, and a rule watches one repository. Nothing in the design
   asked how other repositories' items reach the board.
4. **The post-deployment check for R2 tested half of R2.** It listed
   documents and passed; the board clause had no check.
5. **Pull request numbers collide across repositories.** With several
   repositories on the board, `board-pr-state.py` could read another
   repository's #15 as its own. Review round 1 on programme#59 found it.
6. **Rebase merges broke stacked work.** A pin or a stacked pull request
   pointing at a branch commit points at nothing once that branch merges by
   rebase. #532 and #57 each needed re-pinning or rebasing.
7. **The programme repository had no `BOARD_TOKEN` secret.** Delivery 1 gave
   the token access to the repository but saved no secret there. The sweep's
   first run warned and passed green having added nothing.

Easier than expected: the owner's trials of preview, rehearsal and rollback
from the branch passed first time, apart from one gate test that hung on a
terminal and was fixed in the same round (#514).

## 3. Why — what was the cause?

1. The design read the documentation on plugins and hooks; the trial was
   the first run in the project's cloud environment, which clones every
   repository side by side.
2. The scope was cut at merge, but the cut was not written into the issue.
3. The design took the board as given: auto-add had always worked because
   there had been only one repository.
4. The check was written for the requirement's first sentence. Nothing
   compared a check against every clause.
5. The board code was written when a number named one pull request.
6. A rebase merge gives each commit a new hash.
7. A workflow without its secret warns and exits 0, so a missing secret looks
   like success, and nothing listed the secret as owed when the repository
   was made.

## 4. What do we do next?

| finding | issue raised | or why not |
| --- | --- | --- |
| the cloud loads sibling checkouts | | recorded in the design; the setup script is the answer |
| planned work slipped untracked | #527 | the R8 check caught it, which is its purpose; a second record of left-out work would be one more thing to keep in step |
| the board missed other repositories | programme#59, merged; programme#63 for the reports | |
| a check covered half a requirement | | 1.2 and the raise-project skill changed in this pull request: a check covers each clause |
| PR numbers collide across repositories | programme#59, merged | |
| stacked work and rebase merges | | a one-off: the changes had to land in that order |
| a missing secret passes green | | the boxes above save the secret and check the run. The warning stays, so a repository without the secret does not fail hourly |

## 5. Areas to consider

- **Tooling:** a run that does nothing and passes green (finding 7) is the
  silent failure this prompt warns of.
- **The process:** the clause rule (finding 4) was a gap in the rule
  itself.

## 6. Lessons worth keeping

- **A post-deployment check covers every clause of its requirement.** R2
  passed on its first half.
- **Whoever merges a workflow that needs a secret runs it by hand that day**
  and confirms it did its work.
