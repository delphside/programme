---
name: ship-a-change
description: Take a change through preview, rehearsal and a production release, or deliver a tooling or Other change. Use when a change is ready to go out, or when a release is being cut or run against preview or rehearsal.
---

# Shipping a change

**Whether a change ships is a judgement made elsewhere**: the application's
release document has the steps
(Tile Lite Elite's is
[`docs/4.3.3`](https://github.com/delphside/tile-lite-elite/blob/main/docs/4.3.3-testing-ci-and-release.md)
§1) and [1.2](../../../docs/1.2-change-lifecycle.md) the rules.

## First, the route

The route decides which steps apply. Which artefacts take which route is
[1.2 §2.15 *Route*](../../../docs/1.2-change-lifecycle.md#route), and each
application's artefact register (`3.n.2`) applies it.

| Route | What shipping means |
| --- | --- |
| Production Release | a semver, a branch and pull request, and the full lap (*The lap, for a Production Release*) |
| Application Tooling | a branch and pull request; live at merge, with no deploy |
| Docs and Programme Tooling | straight to `main` (by pull request from a cloud session), with no deploy; the programme's `scripts/deliver/` and its tests are the exception and take Application Tooling's route |
| Other | applied by hand: whatever applying it takes |

A delivery has one route. Work spanning several splits into a delivery each,
and each delivery is one or more work packages. Documentation is the
exception: it rides the branch of the delivery it accompanies, where that has
one ([1.2 §2.15 *Route*](../../../docs/1.2-change-lifecycle.md#route)).

## The lap, for a Production Release

*The lap* is the release's steps in order, each proved by its exit status,
never its output. The application's release document lists the steps for each
kind of release (Tile Lite Elite's is 4.3.3 *Which steps each shape runs*).
Tile Lite Elite's single-delivery release runs these steps, where the numbers
are the sections of its 4.3.3, `SHA` is the commit being released and `VERSION`
the release's version:

| Step | What | Who |
| --- | --- | --- |
| 1.1 | record the change | Claude |
| 1.2 | push, and let CI judge it | Claude |
| 1.9 step 1 | rebase onto `main` | Claude |
| 1.3 | `turpin build SHA`, then `turpin deploy preview SHA` | Claude |
| 1.4 | user testing, on preview | the owner |
| 1.2.4 | at the release build, set the version to match the scope, rename the milestone and each open title carrying the version to it, and check it; a new commit runs 1.2 and 1.3 again before 1.5 | the owner |
| 1.5 | rehearse the release on rehearsal, and run the technical tests | Claude |
| 1.5.3 | regression on rehearsal | Claude runs the suite, the test manager checks the results, the owner judges whether rehearsal passed |
| 1.9 step 3 | fast-forward `main` to the proven branch | Claude |
| 1.6 | read the milestone, then `turpin release`, from the `main` tree | the owner |
| 1.6 | write the release's delivery-log row (`3.n.1`), saying *released, not deployed* ([1.2 §2.14](../../../docs/1.2-change-lifecycle.md#the-delivery-log-row-is-part-of-the-delivery)) | Claude |
| 1.6 | `turpin deploy production VERSION`, from the `main` tree | the owner |
| 1.7 | verify what is live with `verify.sh` | Claude or the owner |
| 1.10 | delete the branch | Claude |

## Tile Lite Elite's traps

**The commit shipped is the commit rehearsed.** `turpin release` refuses a
commit that rehearsal has not run, and preview has no such check
([4.3.3 §1.4](https://github.com/delphside/tile-lite-elite/blob/main/docs/4.3.3-testing-ci-and-release.md#14-user-testing)).
A rebase after the preview deploy is a new commit, so Claude runs 1.3 to 1.5
again; the version commit of 1.2.4 runs 1.2, 1.3 and 1.5, with nothing for 1.4
to judge.

**Read the milestone before `turpin release`**
([4.3.3 §1.6](https://github.com/delphside/tile-lite-elite/blob/main/docs/4.3.3-testing-ci-and-release.md#16-ship-it)):

```bash
gh issue list --milestone X.Y.Z --state open --json number,title,issueType
```

The owner's local `gh` has `issueType` in `--json`; an older one, such as the
cloud session's 2.89.0, does not.

Making the release checks that the milestone holds only what ships
([1.2 *Making the release*](../../../docs/1.2-change-lifecycle.md#making-the-release)).
When `turpin release` asks about an open issue, not a project, that no commit
names, the owner decides, as Tile Lite Elite's `CLAUDE.md` describes: fold the
issue into a work package, move it out of the milestone, or ship it in the
milestone.

**Regression runs with one worker and the rate limits relaxed, then restored.**
Restore the limits always, even when the suite fails. The commands, the
rehearsal URL and a failed cleanup are
[4.3.3 §1.5.3](https://github.com/delphside/tile-lite-elite/blob/main/docs/4.3.3-testing-ci-and-release.md#153-regression-on-rehearsal-then-judge-it)
and the [e2e README](https://github.com/delphside/tile-lite-elite/blob/main/e2e/README.md).

**Run each `turpin` command bare.** Piping it into `tail` reports the pipe's
exit status. Redirect to a file where the output is needed.

## After the production deploy, by hand

| Item | How |
| --- | --- |
| the delivery-log row | Claude completes the row written when the release was made, with its deployed date and outcome |
| post-deployment checks | Claude answers each row on the work package from its reads of production: `passed`, `cannot be tested` or `failed` |

## The other routes

| Route | Tried | Milestone | Delivery-log row | Live |
| --- | --- | --- | --- | --- |
| Application Tooling | its tests and CI, on its branch | the date it merges (`YYYY.MM.DD-n`) | yes | at merge |
| Docs and Programme Tooling | its review rounds; `check-docs.sh` for a document, its tests for a script | none | no; its record is the commit | at the push or merge |
| Other | as applying it allows | the date it is applied (`YYYY.MM.DD-n`); for host maintenance, in the infrastructure application | yes; for host maintenance, in the infrastructure application's log | when applied |

A dated milestone is closed by hand by the local session, because it is not a
semver. A package upgrade and a reboot are two deliveries
([1.2 §2.2.1](../../../docs/1.2-change-lifecycle.md#221-business-as-usual-updates)).

## An emergency

The owner runs each step, in the order of the application's guide to a release
that goes wrong (Tile Lite Elite's is
[4.3.6 §3](https://github.com/delphside/tile-lite-elite/blob/main/docs/4.3.6-when-a-release-goes-wrong.md#3-ship-an-emergency-change)),
and the *emergency* row of
[1.2 *Making a release, then deploying it*](../../../docs/1.2-change-lifecycle.md#making-a-release-then-deploying-it)
says what each command does. Three points the steps turn on:

- Roll back first, where going back can help: it takes seconds and needs no
  build.
- Cut the branch from the commit production runs, never from `main`: `main`
  accumulates tested but unshipped image changes, and shipping it carries them
  beside the fix. After a rollback, the highest release tag is not that commit.
- Merge the fix back into `main`, never by rebase or cherry-pick: rebase
  rewrites `main` and orphans every artefact built from it, and cherry-pick
  leaves production running a commit that is not an ancestor of `main`.
