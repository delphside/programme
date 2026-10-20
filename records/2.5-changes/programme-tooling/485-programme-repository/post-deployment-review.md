# Post-deployment review: Programme repository

Project: delphside/tile-lite-elite#485 · delivered as `0.9.1a`, 2026-10-16 to
18, with a follow-up package (#527) on 2026-10-20 · reviewed: 2026-10-20, by
Claude; the owner reviews it

- [ ] **owner** — read this review, then #485 moves to Project Closedown and
  closes with #527

## 1. Was the intended scope delivered?

| in scope | delivered | note |
| --- | --- | --- |
| R1 generic assets in one place | yes | the one shared file is a #406 trial, not a generic asset |
| R2 application assets only; one board | yes, late | the documents half passed on 2026-10-18. The board half, every repository's issues on one board, was only met by programme#59 on 2026-10-20 |
| R3 consumed through a submodule | yes | the plugin route was dropped on 2026-10-16: cloud sessions do not load repository-enabled plugins |
| R4 a session loads the rules | yes | for Tile Lite Elite; the other applications have no repository content yet |
| R5 Tile Lite Elite first | yes | |
| R6 records in the programme | yes | `applications/tile-lite-elite/` holds 3.1.1 to 3.1.7 |
| R7 a project spans both repositories | yes | #515's records and #518's branch |
| R8 no application fact in the tooling | partly | the scripts and hooks hold none. The reference reviewer's file table moved to the technical profile (#527: programme#53, tile-lite-elite#532). The other agents and skills still name Tile Lite Elite |
| R9 scripts grouped by purpose | yes | |
| R10 a warning, not a refusal, on `main` | yes, by test | no commit has touched an application script on `main` since the merge; the owner accepted the bats test on 2026-10-20 |
| R11 CI split by repository | yes | |
| all: a production deploy from the moved scripts | not yet | handed to the 0.9.2 release's checks (owner, 2026-10-20) |

**Added during the project, at the owner's direction:** the technical profile
renamed `app-profile.toml` (programme#57, tile-lite-elite#535); the hourly
board sweep (programme#59).

**Deferred:** the remaining agents and skills to programme#58, for Dark
Portal's first use. Issue numbers across repositories to #383 R13.

## 2. What happened that we did not plan for?

1. **The plugin route failed its first trial.** A cloud session does not load
   a plugin a repository enables, so R3 became a submodule. The trial was the
   first step of delivery 2, and nothing had been built on the plugin.
2. **The leak pass missed an agent.** It searched scripts and hooks for
   repository names and paths. The reference reviewer named Tile Lite Elite's
   files in prose, and the post-deployment check found it.
3. **The board took only one repository's items.** GitHub Free allows one
   auto-add rule, and a rule watches one repository. Nothing in the design
   asked how other repositories' items reach the board.
4. **The post-deployment check for R2 tested half of R2.** It listed
   documents and passed; the board clause had no check.
5. **Pull request numbers collide across repositories.** Once the board holds
   items from several repositories, `board-pr-state.py` could read another
   repository's #15 as its own. A review round on programme#59 found it.
6. **Rebase merges broke stacked work.** A submodule pin or a stacked pull
   request pointing at a branch commit points at nothing once that branch is
   merged by rebase. #532 and #57 each needed re-pinning or rebasing after the
   pull request beneath them merged.
7. **The programme repository had no `BOARD_TOKEN` secret.** Delivery 1 gave
   the token access to the repository, but no secret was saved there. Nothing
   noticed until the sweep's first run, which warned and passed green having
   added nothing.
8. **Easier than expected:** the owner's trials of preview, rehearsal and
   rollback from the branch all passed first time; the one fault, a gate test
   hanging on a terminal, was found and fixed in the same round.

## 3. Why — what was the cause?

1. Cloud sessions read `.claude/` from the repository and its submodules, not
   a repository's plugin settings. Found by trying it, as planned.
2. The pass searched for identifiers, and prose names files without them.
3. The design took the board as given: auto-add had always worked because
   there had only been one repository.
4. The check was written for the requirement's first sentence. Nothing
   compares a check against every clause of its requirement.
5. The board code was written when a number named one pull request.
6. A rebase merge gives each commit a new hash, so anything holding the old
   hash is left pointing at an unmerged copy.
7. A workflow without its secret warns and exits 0, so a missing secret looks
   like success. The secret was the first thing the programme repository
   needed from Actions, and nothing listed it as owed.

## 4. What do we do next?

| finding | issue raised | or why not |
| --- | --- | --- |
| agents and skills name Tile Lite Elite | programme#58 | |
| the board missed other repositories | programme#59, merged | |
| a check covered half a requirement | | 1.2's rule changed in this pull request: a check covers each clause of its requirement |
| PR numbers collide across repositories | programme#59, merged | Claude's other board reports still read one repository; #383 R13 covers issue numbers across repositories |
| stacked work and rebase merges | | a cost of stacking, paid twice in a project that stacked by necessity. Pin only to a commit on `main` |
| a missing secret passes green | | the owner saves the secret (2026-10-20). The warning stays: a fork or a fresh repository without the secret should not fail hourly. The first run after setting it is checked by hand |
| the plugin trial | | the plan worked as intended |

## 5. Lessons worth keeping

- **Write a post-deployment check for each clause, not each requirement.** A
  requirement with two halves passed on one.
- **A repository's secrets are part of its creation.** The first workflow that
  needs one should fail its first run loudly, so try it by hand on the day it
  merges.
