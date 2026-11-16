# Questions for the owner: Tile Lite Elite on Turpin

Six questions, all answered, for delphside/tile-lite-elite#545, *Build once, promote through
environments*, that its [design](https://github.com/delphside/programme/blob/main/applications/tile-lite-elite/3.1.7-changes/workstreams/delivery-tooling/545-build-once/design.md) cannot settle. #545 delivers
through two work packages: #555, the deploy tooling (route Application
Tooling, delivered when its branch lands), and #556, the image (route
Production Release, shipped in release 0.10.2). *Turpin* is the programme's
build, release and deploy tool (delphside/programme#117), and a *T* number is a
gap in it, in [turpin-gaps.md](https://github.com/delphside/programme/blob/main/applications/tile-lite-elite/3.1.7-changes/workstreams/delivery-tooling/545-build-once/turpin-gaps.md).

Each question stands alone: its terms are glossed in it, its options are
numbered with what each constrains and costs, and the last line is the answer.

## Q1. The package for R8 and R10

**Which work package carries R8 and R10?** Neither is in a work package's
requirements.

- *R8* (#545, owner 2026-10-27): the deploy installs every file the
  application puts on its host from the release, not only the image (the
  backup script, the log-check script and its schema document, and their
  systemd units and timers), reloads systemd, and `verify.sh` checks the
  host's copies against the release.
- *R10* (#545, from #552): the delivery tooling and the issue forms stop naming
  the retired milestones `pre-approved`, `no-release`, `patch`, `minor` and
  `major` (`deploy.sh`'s placeholder gate and its test, the example in
  `issue-mentions.sh`, the two issue forms), while an open issue a release
  mentions with no milestone is still reported.

1. **R8 in #556, its `verify.sh` half in #555; R10 in #555.** The host files
   travel in the image, so they are Production Release artefacts; `verify.sh`,
   the forms and `issue-mentions.sh` are laptop tooling; `deploy.sh`'s
   placeholder gate goes when `deploy.sh` retires in 0.10.3. Constrains:
   nothing. Costs: a post-deployment row more in each package.
2. **Both in #555.** Constrains: an Application Tooling package would carry
   artefacts that reach the image, against the rule that a route belongs to the
   artefact. Costs: nothing in the work; a misfiled route.

**Answer**: option 1, decided by the rule that a route belongs to its artefact (2026-11-16).

## Q2. R9's confirmation

**Does R9's per-issue confirmation survive?** *R9* (#545, owner 2026-11-04):
the milestone check informs rather than alarms. Where an issue in the
release's milestone is named by no commit, it asks `Project tle#N has this
milestone but is not explicitly mentioned in a commit. Confirm that #N is in
this build [y/N]`, in place of today's claim that the issue "was not built";
and it skips a parent project with sub-projects. Turpin has it ([T9](https://github.com/delphside/programme/blob/main/applications/tile-lite-elite/3.1.7-changes/workstreams/delivery-tooling/545-build-once/turpin-gaps.md)).

1. **Accept Turpin's refusal.** `turpin release` refuses, naming each open
   issue in the milestone that no commit in the release names. The fix is a
   commit saying `Refs #N`, or `--set-aside milestone REASON`, which the
   release record keeps.
   Constrains: R9's wording, rewritten to this. Costs: a set-aside covers the
   whole milestone.
2. **Turpin gains a per-issue confirmation** (T9's fix). Constrains:
   delphside/programme#117's design and test design. Costs: a Turpin change
   before 0.10.2.

**Answer**: option 2 (the owner, 2026-11-16). R9 stands as agreed. Turpin has it (T9): `turpin release` asks the question per issue, `--confirm N` answers ahead, the record keeps `carries.confirmed`, and `--set-aside milestone REASON` stays.

## Q3. The timers on rehearsal

**Does rehearsal get the backup and log-check timers?** Turpin installs the host
files on every host whose role is rehearsal or production.

- *The backup*: nightly, it copies production's database to OCI (Oracle Cloud
  Infrastructure) Object Storage through a *PAR*, a pre-authenticated request:
  a URL that lets its holder write objects to one bucket and do nothing else.
- *The log check*: nightly, it validates the day's journal against the log
  events schema.
- *The marker*: an object each one overwrites on success.
- *The alarm*: the OCI monitoring alarm that fires when production's marker
  stops being refreshed.
- *#554*: the work package that set up the image registry by hand in the OCI
  console: its repositories, policy and credentials.

Rehearsal has no PAR, so its backup fails every night.

1. **Install them on rehearsal and let them fail there.** The failure lands in
   rehearsal's journal; the alarm watches production's marker only.
   Constrains: nothing. Costs: a nightly error on rehearsal. Keeps the
   rehearsal tests of the timers and of a deploy waiting for the backup.
2. **Give rehearsal a PAR to a bucket of its own.** Constrains: #554's console
   artefacts gain a bucket and a PAR. Costs: one more credential to renew.
3. **Turn host files off on rehearsal** (`host_files = false`). Constrains:
   nothing. Costs: the timers and the backup's lock are first tried on
   production.

**Answer**: option 1, extended (the owner, 2026-11-16). The backup and the log check send every object through one upload function; `TLE_UPLOAD` in each host's `.env` chooses its adapter: production uploads through the PAR, rehearsal writes into a local folder and reports success, or failure where a test sets it. Only the upload through the PAR is not tried before production; a post-deployment row in #556 covers it.

## Q4. Applying a changed `.env`, and resetting rehearsal

**How is a changed `.env` applied, and rehearsal reset?** Each host's settings
and secrets are in its `.env`. `rehearsal-access.sh` and `rehearsal-limits.sh`
edit it, and `seed-rehearsal.sh` restores a database, each then running
`docker compose up -d`; `deploy-rehearsal.sh reset` runs `docker compose
down -v`, deleting rehearsal's database. Under Turpin the compose files live in
a deploy folder only Turpin tracks ([T2](https://github.com/delphside/programme/blob/main/applications/tile-lite-elite/3.1.7-changes/workstreams/delivery-tooling/545-build-once/turpin-gaps.md)), and the old
folder's compose file would start the old images.

1. **Turpin gains `turpin-host compose`** (T2's fix). Constrains:
   delphside/programme#117. Costs: a small Turpin change; until it lands, the
   scripts refuse their `up` step.
2. **A Tile Lite Elite helper** reads Turpin's state file and repeats Turpin's
   Compose arguments. Constrains: Tile Lite Elite would follow Turpin's private
   layout. Costs: a second copy of the arguments, which drifts.
3. **Redeploy the same commit** after each change. Constrains: nothing. Costs:
   a snapshot and a restart for each key; and no reset, since a deploy keeps
   the data.

**Answer**: option 1 (the owner, 2026-11-16). `turpin-host compose` exists (T2).

## Q5. Preview's lifetime

**Is preview a standing environment?** *Option 4* of #545 (agreed 2026-10-26):
a preview is made from a branch's build when needed and destroyed after, so no
preview inherits an earlier one's data; one exists at a time, on today's port.
Turpin's ephemeral environments do not fit a preview on the laptop
([T8](https://github.com/delphside/programme/blob/main/applications/tile-lite-elite/3.1.7-changes/workstreams/delivery-tooling/545-build-once/turpin-gaps.md)).

1. **A standing environment whose every deploy starts empty**: the
   `save-state` hook takes its snapshot, then empties the volume. Constrains:
   nothing. Costs: a preview seeded with production data is seeded after the
   deploy.
2. **`turpin env create preview`**, once T8 is fixed. Constrains:
   delphside/programme#117. Costs: a Turpin change; a Linux user per preview
   on the laptop.

**Answer**: option 1 (the owner, 2026-11-16), which meets #545's option 4 without a Turpin change; T8 is not needed.

## Q6. The pin and the profile in the image

**Do a pin move and a profile edit change the image?** The *pin* is the
programme commit that Tile Lite Elite's `programme/` submodule holds; the
programme's tools reach Tile Lite Elite when it moves. The *payload*, the files
a host runs to deploy, is built into the server image and carries the deploy
steps from the pin and the whole of `app-profile.toml`
([T6](https://github.com/delphside/programme/blob/main/applications/tile-lite-elite/3.1.7-changes/workstreams/delivery-tooling/545-build-once/turpin-gaps.md)). A path that reaches the image is a Production Release
artefact, so as written every pin move, and every profile edit, the board's
keys included, waits for a release.

1. **Accept it.** Constrains: pin moves and profile edits ride releases.
   Costs: the programme's board and document tools lag on Tile Lite Elite until
   the next release.
2. **T6's fix**: Turpin carries only the profile keys a host reads, and
   `[ships]` counts a pin move as shipping only where it changes the deploy
   steps. Constrains: delphside/programme#117 and the board's shipping rule.
   Costs: a small change to each.

**Answer**: option 2 (the owner, 2026-11-16). Tile Lite Elite sets `[ships].carries_payload = true` in #555, once its image carries the payload.
