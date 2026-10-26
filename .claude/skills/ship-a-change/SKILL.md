---
name: ship-a-change
description: Take a change through preview, rehearsal and a production release, or deliver a tooling or Other change. Use when a change is ready to go out, when a release is being cut, or when the release's steps are being run against preview or rehearsal.
---

# Shipping a change

The mechanics and the traps. **Whether a change ships is a judgement made
elsewhere**: the application's release document has the steps (Tile Lite
Elite's `docs/4.3.3` §1) and `docs/1.2` the rules.

## First, the route

The route decides which steps apply.

| Route | What shipping means |
| --- | --- |
| **Production Release** | anything in the image, and what the application installs on its production host. Semver, branch, pull request, the full lap |
| **Application Tooling and Docs** | scripts that build, test, deploy, operate or measure the application, and their documents. Branch and pull request; live at merge, with no deploy |
| **Programme Tooling and Docs** | anything else in the repository. Straight to `main` (by pull request from a cloud session); no deploy |
| **Other** | a console, a cloud resource, host maintenance, preview or rehearsal. Whatever applying it takes, plus a row in the delivery log (`3.n.1`; the infrastructure application's for host maintenance) |

**A delivery has one route.** Work spanning several splits into a delivery each,
and each is its own work package. Documentation is the exception: it rides on
the release it accompanies, one milestone, no second row.

**A Requirement never carries a release milestone**, only `pre-approved`. If
the thing shipping is a requirement, it needs a work package to own the
delivery, or the record says a delivery happened with nothing responsible for
it.

## The lap, for a Production Release

*The lap* is the release's steps in order, each proved by its **exit status**,
never its output. The application's release document lists them per shape
(Tile Lite Elite's `docs/4.3.3` *Which steps each shape runs*). Tile Lite
Elite's single-delivery release runs, by section of its 4.3.3:

1. 1.1 record the change, and 1.2 push and let CI judge it (1.2.4 too if
   functional).
2. 1.9 step 1: rebase onto `main`.
3. 1.3 deploy to preview, at the commit you will ship.
4. 1.4 user testing, on preview.
5. 1.5 rehearse the release, and run the technical tests.
6. 1.9 step 3: fast-forward `main` to the proven branch.
7. 1.6 ship it, from the `main` tree: the owner's step.
8. 1.7 verify what is live: `verify.sh`.
9. 1.10 delete the branch.

### Tile Lite Elite's traps, each of which has cost a run

**Preview must be on the commit being shipped.** `deploy.sh` refuses otherwise.
Rebase first, then redeploy preview, then ship.

**The suite runs against preview only when told to, with one worker.** The
engine holds the games map's write lock while searching, so parallel workers
queue and time out. Run it in a subshell, so the next step starts where you
are:

```bash
(cd e2e && PLAYWRIGHT_BASE_URL=http://localhost:8081 npx playwright test --workers=1)
```

**Rehearsal refuses a suite at its rate limits.** Registration is 2/min with a
burst of 3 and the suite registers an account per test:

```bash
./scripts/deliver/rehearsal-limits.sh regression   # before
./scripts/deliver/rehearsal-limits.sh production   # after, always
```

**Leaving them relaxed is worse than forgetting to relax them**, because
`check-rate-limits.sh` then passes against numbers nobody ships.

**A remote run's teardown removes its own accounts.** Where it prints
`CLEANUP FAILED`, remove them by hand:

```bash
./scripts/deliver/clean-test-accounts.sh --prefix T- --target <the rehearsal URL>
```

The rehearsal URL is the variable the application's technical profile
(`app-profile.toml`) names in `environments.rehearsal.url_variable`, set by the
script in `environments.rehearsal.url_from` (or the override in
`environments.rehearsal.env`).

**The owner reads the milestone before deploying.** `deploy.sh` settles every
open issue in it, shipped or not: it closes a non-project, moves a work package
to `Post-deployment` and skips a parent. Move out anything that is not shipping
first.

**Run `deploy.sh` bare.** Piping it into `tail` reports the *pipe's* exit
status. Redirect to a file if you need the output.

## By hand, afterwards

| Item | How |
| --- | --- |
| the delivery-log row | Claude writes it into the delivery log (`3.n.1`); the release does not |
| a lettered milestone | closed by hand by the local session: the letter form is not valid semver, so nothing matches it |
| post-deployment checks | answered by Claude on the work package, each row, from what the owner's production reads return, with `passed`, `cannot be tested` or `failed` |

## The other routes

| Route | Tried | Milestone | Delivery-log row | Live |
| --- | --- | --- | --- | --- |
| Application Tooling and Docs | its tests and CI, on its branch | a letter | yes | at merge |
| Programme Tooling and Docs | none | `pre-approved`, or none | no; its record is the commit | at the push or merge |
| Other | as applying it allows | a letter off **production's** current version; for host maintenance, a date (`YYYY.MM.DD-n`) | yes | when applied |

A package upgrade and a reboot are two deliveries, because either can fail
alone and the record must say which did.

## An emergency

The owner runs it, from the application's release document (Tile Lite Elite's
`docs/4.3.3` §1.13):

1. Roll back first, where going back can help: it takes seconds and needs no
   build.
2. Cut a branch from **the commit production runs, never from `main`**: `main`
   accumulates tested but unshipped image changes, and deploying it ships them
   beside the fix. After a rollback, the highest release tag is not that
   commit.
3. Commit the fix, open a pull request and deploy it, as §1.13 says.
4. **Merge it back** into `main`: not rebase, which rewrites `main` and orphans
   every artefact built from it, and not cherry-pick, which leaves production
   running a commit that is not an ancestor of `main`.
