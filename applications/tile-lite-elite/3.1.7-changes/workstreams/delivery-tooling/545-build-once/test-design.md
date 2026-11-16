# Tile Lite Elite on Turpin: test approach changes

Proposed changes to the technical tests of delphside/tile-lite-elite#555, for
the test manager, from its [design](design.md). An *S* number is a scenario in
[Turpin's test design](../../../../../../records/2.5-changes/programme-tooling/117-generic-deliver-tool/test-design.md#5-scenarios),
and an *X* number a gap in its
[part 10](../../../../../../records/2.5-changes/programme-tooling/117-generic-deliver-tool/test-design.md#10-gaps).
Every test runs on rehearsal before the merge unless it says otherwise.

## The five tests

| Test today | Proposal | Why |
| --- | --- | --- |
| 1. Rehearsal deploys the stored build; the release step writes the record and bumps `main` | **Split.** Rehearsal deploys the stored build by digest, pulled with its instance principal, and the cold pull is timed (S35, S36). The release step goes to CI (Turpin's release scenarios) and to #555's R3 post-deployment row | the release step spends a version and pushes a tag, so it cannot be rehearsed |
| 2. Production's gates refuse a raw SHA and an unrecorded version, and accept the override with a reason | **Keep**: in CI, and by the owner's two `--check` runs before 0.10.2's deploy (X15) | production is the owner's to reach |
| 3. Rollback restores the previous record's image and state | **Reword**: `turpin rollback rehearsal` restores the previous deploy's image set, joined files and data; run after two Turpin deploys | a rehearsal deploy carries no record |
| 4. The snapshot contract on the real hooks and database (S97's real half, X24) | **Keep**, adding that `deploy.sh`'s `pre-*` snapshots survive, and that `rollback.sh --db-only` restores a `turpin-N.tgz` | the fallback reads the same folder |
| 5. An emergency, descended from the release production runs, passes through rehearsal | **Change** to the gates only: a branch from production's tag, built and deployed to rehearsal, then `turpin release --emergency REASON --check`, which changes nothing. A real emergency stays #555's R6 post-deployment row | a real emergency release spends a version |

## Tests to add

- **The fallback**: the way back of the design's migration (S39), tried on
  rehearsal.
- **A refused deploy restores**: `smoke` refusing, and the database restored
  (S33); `pre-deploy` refusing a database ahead of the build.
- **The host files**: installed, the timers enabled (S34).
- **The backup and the log check, on rehearsal**, through the local-folder
  adapter (`TLE_UPLOAD=local`): started by hand, each leaves its marker in the
  folder, and the backup's database copy opens and passes its integrity check;
  with `TLE_UPLOAD=local-fail` each exits non-zero and leaves the marker
  alone.
- **The lock, with a real backup**: a deploy with `--wait` waits for a running
  backup and goes on, and one without it is refused (S37).
- **Applying a change and resetting**: `turpin-host compose` refuses where
  there is no current deploy, and takes the environment's lock.
- **R9's question**: `turpin release` asks `[y/N]` for an open issue in the
  milestone that no commit names, and skips a parent; `--confirm N` answers
  ahead and the record's `carries.confirmed` holds it. In CI, with Turpin's
  release scenarios.
- **The first deploy on an adopted host**. It
  runs before rehearsal's first Turpin deploy (design §4 step 4.3), on a
  rehearsal made to look like production: the backup and log-check files and
  timers installed by hand, as on production. A failure at `migrate` leaves
  0.10.1 serving, with the server `save-state` stopped started again; a
  failure at `smoke` leaves every host file that was there before. After each,
  the way back is taken and the state folder cleared, so the next deploy is
  again a first one.
- **The OCI CLI's memory peak** on the 1 GB host, during the instance-principal
  login, which nothing has measured.
- **Preview**: every deploy starts from an empty database (functional, on
  preview).
- **The `.env`**: `rehearsal-access.sh grant` writes its key to the state
  folder's `.env` and applies it.
- **The check names**: after the merge, `turpin release --check` passes the
  `ci-passed` gate.

Not tried before production: the HTTP upload through the PAR, proven there
already. #556's post-deployment row covers it: the owner starts the backup
service once by hand after 0.10.2's deploy, and the marker is seen
refreshed.
