<!-- markdownlint-disable-file MD013 -->

# Test design specification: the deliver tool

Project: delphside/programme#117 · type of change: `tooling` · route: `Docs and Programme Tooling` · release: not applicable

This specification derives the tests for `deliver` from its stated rules, without reading the implementation. Its sources are:

- the design, `records/2.5-changes/programme-tooling/117-generic-deliver-tool/design.md` (2026-10-28 revision);
- #117's body;
- delphside/tile-lite-elite#545, #555 and #556;
- docs/1.2 *Making a release, then deploying it* and §2.5;
- docs/1.9.

**(H)** marks a rule taken from the agreed handover rather than from a document.

Each test has one of two kinds:

- **[CI]** is a bats test in `scripts/tests/deliver-*.bats`. It uses a dummy application, stub hooks, `registry:2`, and stubbed `ssh` and `gh`.
- **[REH]** is a technical test on Tile Lite Elite's rehearsal.

The gates for the `production` role are tested in CI only. On real hosts they are shown only by 0.10.2's first production deploy, which is a post-deployment check and not a test (part 8).

## 1. Rules

| | rule | source |
| --- | --- | --- |
| R1 | The tool names no application and no machine. Anything that differs comes from `app-profile.toml` or a hook. | G1; §2 |
| R2 | The registry address is never in the profile. Each role reads `DELIVER_REGISTRY` from its own local configuration. | §5 |
| R3 | `build [REF]` is non-interactive and refuses a REF that is not a commit on the remote. It builds from a clean worktree with the `build` hook, or `docker buildx bake` by default. It labels each image `org.opencontainers.image.revision` = SHA and `.version` = the version file. It pushes each image as `SHA-IMAGE` and prints the digests, an index digest for a multi-arch build. | §4 |
| R4 | An image whose `SHA-IMAGE` is already present is not rebuilt. A failed registry query refuses. Releases is immutable. | §4; §6 |
| R5 | The payload goes into `payload_image` at `/deliver/`, from the pinned submodule and the app repository. It holds nothing secret. Joined files come from the payload and never from a working tree. An environment may name its own `join`. | §2; §5 |
| R6 | `deploy ENV REF` checks REF against the environment's role. For preview, test and rehearsal, REF is a full or short SHA or a version, resolved in candidates. For production it is a version with a record, pulled from releases. The deploy runs over ssh, or locally where `host = "control-node"`, and then `settle` for production. Gates key on the role, never the name. | §2; §4 |
| R7 | Every image is pulled by digest. Its revision label must equal the SHA, and the running containers' `RepoDigests` must match. | §6 |
| R8 | The environment's lock (`flock`) must be free and is held to the end. `--wait` waits for the lock and for a hook's exit 75. | §4; §6; §9 |
| R9 | A deploy refuses unless the state file shows the last deploy finished. The way out is `deliver rollback` or a fresh deploy of the previous REF. | §6; §9 |
| R10 | `pre-deploy` is a gate. It can be set aside with `--set-aside`, where the profile marks it overridable. | §5; §6 |
| R11 | A deploy runs these steps in order: lock, then state, then pull by digest, then payload, then `pre-deploy`, then the new deploy folder, then `save-state`, then `migrate`, then host files, then the `current` switch, then `compose up`, then `smoke`, then finished, then pruning host images. Compose runs with a fixed project name, `--project-directory current`, the host `.env` and then `current/deliver.env`, and `--no-build`. | §9 |
| R12 | A failure after `save-state` runs `restore-state`, switches back to `previous` and reinstalls its host files, then exits 1. | §6; §9 |
| R13 | Host files are installed with their modes, followed by `systemctl daemon-reload`. Units marked `enable` are enabled and restarted. `deliver status` compares the host's copies with the payload, as a check. | §6; §9 |
| R14 | A host keeps only its current and previous image sets. | §9; §11 |
| R15 | A rehearsal cycle is the deploys to a rehearsal-role environment since the last release was made. Its first deploy must be production's current record, pulled from candidates by the same digests. `--off-level REASON` sets this aside. | §6 |
| R16 | `release` releases the commit that the rehearsal-role environment runs. It refuses unless that environment's last deploy finished and its `smoke` passed. The owner confirms by typing the version, or with `--expect VERSION`. `--skip-rehearsal REASON` sets this aside, is recorded, and raises the retrospective issue. | §4; §6; §8 |
| R17 | The release commit must be on `origin/main`. With `--emergency REASON` it must instead descend from the newest release tag, and none of its commits after that tag may be on `main`. | §6 |
| R18 | Every check in `required_checks` must be green on the commit. | §6 |
| R19 | The version is read from the version file at the commit. No tag or record may exist for it, and it must be higher than the newest release tag of any prefix. | §4; §6 |
| R20 | Parents aside, every open issue in milestone VERSION must be carried by a `Refs #N` since the previous release tag. Every work package those commits carry must be in the milestone. Otherwise the release refuses. | §6; docs/1.2 |
| R21 | `release-check` is a gate. It can be set aside with `--set-aside` where overridable. | §6 |
| R22 | The release runs in this order: gates and confirmation, then copy, then `VERSION-record`, then the annotated tag `vVERSION`, then the GitHub Release, then the bump, then the milestone. A copy already present with the same digest is a no-op. The version is spent at the tag. A rerun after the tag checks that the tag's record matches and resumes at the GitHub Release. A failure after the tag exits 3. | §7 |
| R23 | The record has the §7 fields, `record: 1`, and the tag's message is the record. A reader refuses an unknown record version. A tag without JSON is history only. | §7 |
| R24 | The bump goes to the next patch above both the released version and `main`'s own. An emergency that holds `main`'s number moves `main` on, and moves the open issues of that milestone with it. | §7 |
| R25 | The GitHub Release notes run from the previous release tag of any prefix. The next milestone is opened. | §7 |
| R26 | A production deploy needs a record for VERSION, with its digests pulled from releases. `--unrecorded REASON` instead copies `SHA-IMAGE` to releases with no record. No version is spent, and settle moves nothing. | §4; §6 |
| R27 | `settle` acts only on what the record carries. A Production Release work package goes to Post-deployment with a comment. A carried non-project issue is closed as completed with a comment. The milestone is closed. Each action checks first, so settle is safe to rerun. If settle fails, it lists the items left, the deploy stands, and the exit is 3. | §8; §6 |
| R28 | Rollback switches to `previous` and runs `restore-state`. With no previous deploy it refuses and names the fallback. | §9 |
| R29 | A hook listed in `required_hooks` that is missing or not executable refuses. Any other missing hook is a no-op. A hook's exit means 0 passed, 75 not yet, and anything else refused or failed. Hooks receive `DELIVER_APP`, `_ENV`, `_ROLE`, `_SHA`, `_VERSION`, `_STATE` and `_IMAGE_<NAME>`. A hook of kind check that exits non-zero is reported and changes nothing. | §5 |
| R30 | Every override takes a reason. The reason goes into the record where there is one, and always into the run log. | §4 |
| R31 | Every command writes a run log on its own machine, naming each gate it ran. A command that ends with a gate unrun refuses. Exits are 0 done; 1 refused, failed with nothing changed, or rolled back; 3 live but a later step failed. | §4 |
| R32 | `--check` runs every gate and changes nothing. | §4 |
| R33 | Each role has its own registry access, and no role's credential can do another role's writes. | §2; §11 |
| R34 | Nothing secret is written to a profile, record, tag or log. | §11 |
| R35 | Every pull completes within the environment's `pull_timeout`, or the deploy refuses before any change. | §9; §11 |
| R36 | `prune` removes candidates that are older than the newest release, not released, and not in any environment's current or previous deploy. It never removes releases. | §4 |
| R37 | `env create\|destroy NAME` works from the profile's template: a user, a state folder, a `.env` with secrets at a hidden prompt, a Compose project, and the hooks. | §4 |
| R38 | `host-install` installs or updates `deliver-host`, `jq`, the login adapter's tools and the single `sudo` rule. | §4; §9 |
| R39 | The login adapters are `oci-instance-principal`, `oci-api-key` and `docker-config`. Hosts log in by instance principal. | §2; owner 2026-10-28 |
| R40 | `status ENV` shows the digests, the matching record, the deploy state and host-file equality. `list ENV` shows the records beside what ENV runs. | §4 |
| R41 | Tile Lite Elite's move: the first `deliver` deploy to rehearsal takes `--off-level`. The fallback before 0.10.2 runs in production is `deploy.sh` at production's previous commit. 0.10.2 is the first release with a record. The board reads `v` as released and `prod-` as history. | §10; (H) |

### Checked for contradiction

- R19 against R22 (a tag exists on a rerun) is reconciled by the resume, if the record matches (gap X9).
- R17 against docs/1.2 §1.0 ("made from `main`'s tip") is gap X3.
- The newest release tag in R17 against docs/1.2's "last released tag" is gap X4.
- R27 against docs/1.2 §2.5 ("a project advances to Post-deployment"), for a carried project of another route, is gap X1.

## 2. Conditions, grouped into dimensions

- **C1 command** (complete over §4): build · deploy · release · settle · rollback · status · list · prune · env create · env destroy · host-install
- **C2 environment role** (complete): preview · test · rehearsal · production
- **C3 host placement** (complete): over ssh · local (`control-node`)
- **C4 REF form** (complete): full SHA · short SHA (unique) · short SHA (ambiguous) · version with record · version without record · other name · absent
- **C5 REF on the remote** (complete): pushed · not pushed
- **C6 candidates for the SHA** (complete): all images present · some · none · registry query fails
- **C7 lock** (complete): free · held
- **C8 state file** (complete): finished · a step recorded (interrupted) · absent (first deploy)
- **C9 hook** (complete, per hook): required and absent · required and not executable · optional and absent · exit 0 · exit 75 · other non-zero
- **C10 hook kind** (complete): gate · step · check
- **C11 deploy failure point** (complete): none · before `save-state` · `save-state` · `migrate` · host files · `compose up` · `smoke`
- **C12 previous deploy on ENV** (complete): exists · none
- **C13 rehearsal cycle position** (complete): first deploy of the cycle · later deploy
- **C14 the first deploy's target** (complete): production's current record · other
- **C15 rehearsal state against the release commit** (complete): runs its digests, finished, smoke passed · runs them, smoke failed · runs them, unfinished · runs another commit · never deployed
- **C16 commit ancestry** (complete): on `origin/main` · not on `main`, descends from the newest tag with no post-tag `main` commit · descends but holds a post-tag `main` commit · does not descend from the newest tag
- **C17 required checks** (complete): all green · one failing · one missing
- **C18 version** (complete): new and higher · tag exists · record exists · equal to or lower than the newest tag of any prefix
- **C19 milestone against carried set** (complete): agree · open issue not carried · carried work package not in the milestone · a parent in the milestone only
- **C20 release progress on a rerun** (complete): nothing done · copied, no tag · tag present with a matching record · tag present with a different record · all steps done
- **C21 owner confirmation** (complete): typed correctly · typed wrongly · `--expect` matching · `--expect` not matching
- **C22 override** (complete over §4): none · `--emergency` · `--skip-rehearsal` · `--unrecorded` · `--off-level` · `--set-aside` (overridable) · `--set-aside` (not overridable) · flag without reason · `--wait` · `--check`
- **C23 settle item** (complete over the record): Production Release work package · non-project issue · milestone · carried project of another route (gap X1) · parent
- **C24 settle progress** (complete): none done · some done · all done · `gh` fails
- **C25 registry credential** (complete): the role's own · another role's
- **C26 image arch** (complete): single · multi-arch index
- **C27 record version** (complete): 1 · unknown · tag without JSON
- **C28 host file** (complete): equal · edited · missing · new in this release · dropped in this release (gap X10)
- **C29 the version on `main` at an emergency** (complete): above the emergency · equal to it

## 3. Outcomes

| | outcome |
| --- | --- |
| O1 | Exit 1. The run log and stderr name the refusing gate. A before-and-after snapshot of the registry, the host's containers and the state folder, git refs and the `gh` stub log shows no change. |
| O2 | Candidates holds `SHA-IMAGE` for each profile image. Stdout prints each digest. The labels `revision` = SHA and `version` = the version file. |
| O3 | No push reaches the registry log for an image already present, and that image's digest is unchanged. |
| O4 | Exit 0. The containers' `RepoDigests` equal the named digests. `current` points at a new `deploys/<n>`, `previous` at the earlier one, and `state` = finished. |
| O5 | The steps ran from `/deliver/` extracted from `payload_image`. A sentinel in the operator's working-tree copy is never touched. The joined files in `current/` equal the payload's own, or the environment's own `join`. |
| O6 | Hook calls were logged in the order R11 gives, each with the R29 environment variables. |
| O7 | After a failure: `restore-state` was called, `current` = the previous deploy, the previous digests are running, the previous host files are in place, and the exit is 1. |
| O8 | Host files have the payload's content and mode. The stub `systemctl` saw `daemon-reload`, then enable and restart for the marked units. |
| O9 | `status` reports a host file that differs, and is quiet when the files are equal. |
| O10 | Releases holds each digest identical to candidates (skopeo inspect), and holds `VERSION-record`. The annotated tag `vVERSION`'s message parses to the same JSON. Every §7 field is present. |
| O11 | `main` holds the bumped version. The stub `gh` saw the Release, with notes from the previous tag of any prefix, and the next milestone opened. |
| O12 | The override's reason appears in the record field (`emergency`, `rehearsal_skipped`) where there is a record, and always in the run log. |
| O13 | The stub `gh` saw a retrospective issue naming the reason and what was skipped. |
| O14 | Settle: the stub `gh` saw exactly the record's work packages moved to Post-deployment, the issues closed as completed with a comment, and the milestone closed. A rerun makes no new mutation. |
| O15 | The deploy stands (O4 holds), and the exit is 3 with the items left listed. |
| O16 | `--wait` blocks, then proceeds once the lock frees or the hook returns 0. |
| O17 | The registry refuses another role's write. The role's own credential succeeds. |
| O18 | A canary secret, from `.env`, the credential and the hidden prompt, appears in no log, record, tag, profile or terminal echo. |
| O19 | Grep finds no application name in `scripts/deliver/`. A second dummy profile drives every CI scenario. |
| O20 | `--check` exits 0 or 1 with every gate named in the log, and the O1 snapshot shows no change. |
| O21 | The host image list holds exactly the current and previous sets. |
| O22 | Prune leaves every release, every candidate referenced by an environment's current or previous deploy, and every candidate newer than the newest release. It removes the rest. |
| O23 | The run log names every gate that §6 lists for the command. |

## 4. Matrix

**Deploy: C2 × C4** (✓ accepted · ✗ refused · ? gap)

| | full SHA | short SHA unique | short SHA ambiguous | version with record | version without record | other name / absent |
| --- | --- | --- | --- | --- | --- | --- |
| preview, test, rehearsal | ✓ | ✓ | ? X15 | ✓, resolved in candidates | ✓ if the build exists, by its SHA | ✗ |
| production | ✗; `--unrecorded` ✓ (X8) | ✗ | ✗ | ✓ from releases | ✗; `--unrecorded` ✓ | ✗ |

### Release: C15 × C22

| | none | `--skip-rehearsal` | `--emergency` |
| --- | --- | --- | --- |
| runs, finished, smoke passed | ✓ | ✓ (recorded, retrospective raised) | ✓ if C16 allows |
| smoke failed / unfinished / other commit / never | ✗ | ✓ | ✗ unless also `--skip-rehearsal` |

### Release: C16 × emergency flag

| | on `origin/main` | descends, clean | descends, holds post-tag `main` | does not descend |
| --- | --- | --- | --- | --- |
| no flag | ✓ | ✗ | ✗ | ✗ |
| `--emergency` | ✗, because it holds `main` after the tag (X4) | ✓ | ✗ | ✗ |

**Release rerun: C20.** Nothing done: full run. Copied, no tag: the copy is a no-op and the run resumes at the record. Tag with a matching record: resume at the GitHub Release. Tag with a different record: ✗ (X9). All done: X9.

**Failure point: C11 × C12.** Before `save-state` with a previous deploy: O1, nothing changed. Before `save-state` with none: O1. From `save-state` on, with a previous deploy: O7. With none: ? X5.

## 5. Scenarios

| | scenario | conditions | outcomes | kind |
| --- | --- | --- | --- | --- |
| S1 | Build an unpushed commit; push it; build; build again. | C5, C6 none→all | O1, then O2, then O3 | CI |
| S2 | Build with the operator's tree dirty. | C5 | O2; the image content is the commit's | CI |
| S3 | Build with only one of two images present; build with the registry query failing. | C6 some, fails | O3 for the present one, O2 for the other; then O1 | CI |
| S4 | Build with no `build` hook, then with one. | C9 | buildx bake, then the hook is called | CI |
| S5 | Multi-arch build, then a deploy of it. | C26 | O2 with an index digest; O4 matches it | CI (buildx + qemu) |
| S6 | Deploy to rehearsal a SHA with no build; build; deploy over ssh. | C6, C3 ssh | O1, then O4, O5, O6, O8 | CI |
| S7 | Deploy to preview on the control node, with the preview's own `join`. | C2 preview, C3 local | O4; the joined files are `docker-compose.preview.yml` and `Caddyfile.preview` from the payload; no ssh call | CI |
| S8 | A registry tag repointed so the digest's revision label is another SHA; then a true image. | R7 | O1, then O4 | CI |
| S9 | Deploy while the lock is held; release it; deploy; `--wait` while held. | C7, C22 | O1, then O4, then O16 | CI |
| S10 | `pre-deploy` exits 1, then 75, then 75 with `--wait` returning 0 later, then 0. | C9 | O1, O1, O16, O4 | CI |
| S11 | A required hook missing, then not executable, then present; an optional hook missing. | C9 | O1, O1, O4; the optional one is a no-op | CI |
| S12 | `--set-aside pre-deploy R` where overridable and where not. | C22 | O4 + O12; O1 | CI |
| S13 | A deploy is killed after `save-state`, then rerun, then `deliver rollback`, then deployed. | C8 | O1 (it names the step), then O7-like restore, then O4 | CI |
| S14 | `migrate` fails; `smoke` exits non-zero; a host-file install fails; `compose up` fails. | C11, C12 exists | O7 each | CI; REH for TLE's real hooks (S33) |
| S15 | A new host file; an edited one; status before and after. | C28 | O8, then O9 then quiet | CI; REH (S34) |
| S16 | Three deploys in a row on one host. | R14 | O21 | CI |
| S17 | A rehearsal cycle's first deploy is a SHA, not production's record; then production's record; then a SHA with `--off-level R`; a later deploy in the cycle with any SHA. | C13, C14 | O1, O4, O4 + O12, O4 | CI |
| S18 | Release while rehearsal runs another commit; with smoke failed; unfinished; then passed. | C15 | O1 ×3, then O10, O11 | CI |
| S19 | Release with `--skip-rehearsal R` against a rehearsal that never deployed. | C22 | O10, O12, O13 | CI |
| S20 | Release a commit not on `main`; then the same commit with `--emergency R`, cut from the newest tag; then an emergency commit holding a post-tag `main` commit; then one not descending from the tag. | C16 | O1, O10 + O12, O1, O1 | CI |
| S21 | Release with a required check failing, then missing, then green. | C17 | O1, O1, O10 | CI |
| S22 | Release where the version file names a version whose tag exists; whose record exists; one lower than a `prod-` tag; then a new, higher version. | C18 | O1 ×3, O10 | CI |
| S23 | Milestone with an open uncarried issue; a carried work package not in it; a parent only; then agreeing. | C19 | O1, O1, O10, O10 | CI |
| S24 | `release-check` exits 1; `--set-aside release-check R` where overridable; exits 0. | C9, C22 | O1, O10 + O12, O10 | CI |
| S25 | The owner types the wrong version; `--expect` mismatched; typed correctly. | C21 | O1, O1, O10 | CI (pty) |
| S26 | Release fails at the record push; rerun. Fails at the GitHub Release; rerun. Rerun when all is done. A tag holding a different record. | C20 | O1-like with nothing spent, then O10; exit 3, then O11 without a second tag; X9; O1 | CI |
| S27 | Normal bump; an emergency when `main` holds the emergency's number. | C29 | O11; `main` moves to the next patch and the milestone's open issues move | CI |
| S28 | A reader given record version 2; a text tag `v0.10.1`; a `prod-` tag. | C27 | O1; history only, not deployable as a record | CI |
| S29 | Production deploy of a version with no record; with `--unrecorded R` by SHA; of a recorded version; of a raw SHA without a flag. | C2 production, C4 | O1; `SHA-IMAGE` in releases, no tag, O12, settle moves nothing; O4 + O14; O1 | CI |
| S30 | Production deploy where settle's `gh` fails partway; then `deliver settle VERSION` is rerun; then rerun again. | C24 | O15; O14; no new mutation | CI |
| S31 | Rollback with a previous deploy; with none. | C12 | O7; O1 naming the fallback | CI |
| S32 | Each command's run log and exit codes; `--check` on deploy and release. | R31, R32 | O23, O20 | CI |
| S33 | TLE's real hooks on rehearsal: snapshot, `--migrate-only`, `/health` within 60 s; smoke failure injected. | R12, R29 | O4; then O7 with the database restored | REH |
| S34 | Host files on the rehearsal VM: the backup script and timer installed, the unit enabled; a file edited by hand. | R13 | O8 with real systemd; O9 | REH |
| S35 | Instance-principal pull on rehearsal; rehearsal's identity trying to read releases or write candidates. | R33, R39 | pull ✓; refused | REH |
| S36 | A measured pull on rehearsal within `pull_timeout`; in CI, a throttled pull beyond it. | R35 | REH: within; CI: O1 | REH + CI |
| S37 | A deploy waits on the lock held by the application's own heavy run (the backup). | R8 | O1, then O16 | REH |
| S38 | A reboot of the rehearsal VM mid-deploy, then rerun. | R9 | O1 naming the step reached | REH |
| S39 | TLE's move: the first `deliver deploy` to rehearsal with `--off-level "first deliver deploy"`; then `deploy.sh` at production's previous commit puts rehearsal back. | R41 | O4 + O12; the old compose and image names running, with `/health` | REH |
| S40 | Release copy by the copier with skopeo; another role's credential writing releases. | R33 | O10; O17 | CI (htpasswd per role) |
| S41 | `env create` with secrets at a hidden prompt, then `env destroy`. | R37 | the user, the state folder, `.env` and the project exist, then are gone; hooks called; O18 | CI (pty) |
| S42 | `host-install` on a bare host container, then again. | R38 | `deliver-host`, `jq` and the sudo rule present; then updated | CI; REH |
| S43 | Prune with a mix of candidates. | R36 | O22 | CI |
| S44 | A canary secret through every command. | R34 | O18 | CI |
| S45 | The tool contains no application name; a second dummy app runs S1, S6 and S18. | R1, R2 | O19; a profile without `DELIVER_REGISTRY` in local config refuses | CI |
| S46 | `status` and `list` on an environment after two deploys. | R40 | the digests, the matched record, the state, host-file equality; the records beside the current one | CI |
| S47 | The board reads `v0.10.2` as released and `prod-*` as history. | R41 | the board scripts' output | CI |

## 6. Refusals and successes

| gate (design §6) | refusal | then success | kind |
| --- | --- | --- | --- |
| build: clean worktree of a commit on the remote | unpushed commit → O1 (S1) | pushed → O2 | CI |
| build: never overwritten | registry query fails → O1 (S3) | query answers → O3 for present images, O2 for missing ones | CI |
| deploy: by digest, revision label, `RepoDigests` | label ≠ SHA → O1 (S8) | true image → O4 | CI |
| deploy: lock | held → O1 (S9) | freed → O4; `--wait` → O16 | CI; REH S37 |
| deploy: interrupted not built upon | state shows a step → O1 (S13) | after rollback, deploy → O4 | CI; REH S38 |
| deploy: `pre-deploy` | exit 1 or 75 → O1 (S10) | exit 0 → O4; `--set-aside` where overridable → O4 + O12 | CI |
| deploy: failure keeps the previous running | `migrate`/`smoke` fails → O7 (S14) | both pass → O4 | CI; REH S33 |
| rehearsal deploy: starts at production's level | first deploy ≠ production's record → O1 (S17) | production's record → O4; `--off-level` → O4 + O12 | CI; REH S39 |
| release: rehearsal passed | another commit, smoke failed, or unfinished → O1 (S18) | passed and confirmed → O10; `--skip-rehearsal` → O10 + O12 + O13 | CI |
| release: commit on `origin/main` | not on `main` → O1 (S20) | on `main` → O10; `--emergency` → O10 + O12 | CI |
| release: emergency ships nothing unreleased | holds a post-tag `main` commit, or does not descend → O1 (S20) | clean cut from the tag → O10 | CI |
| release: CI passed | a check failing or missing → O1 (S21) | green → O10 | CI |
| release: version spent once and forward | tag, record, or not higher → O1 (S22) | new and higher → O10 | CI |
| release: milestone shipping list | uncarried issue, or work package outside → O1 (S23) | moved, then rerun → O10 | CI |
| release: `release-check` | exit 1 → O1 (S24) | exit 0 → O10; `--set-aside` → O10 + O12 | CI |
| release: the owner's confirmation (§4) | wrong version typed → O1 (S25) | right → O10 | CI |
| production deploy: a record exists | no record → O1 (S29) | recorded version → O4; `--unrecorded` → O4 + O12 | CI only; real: 0.10.2's post-deployment check |
| after a production deploy: settle (check) | `gh` fails → O15 (S30) | rerun → O14 | CI only; real: 0.10.2's post-deployment check |
| any time: host files (check) | edited file → O9 report (S15) | restored → quiet | CI; REH S34 |
| required hook present (§5) | missing or not executable → O1 (S11) | present → O4 | CI |
| gate count (§4) | not provokable from outside (X9b) | O23 on every run | CI |

## 7. Coverage, both ways

| rule | scenarios |
| --- | --- |
| R1 | S45 |
| R2 | S45 |
| R3 | S1, S2, S4, S5 |
| R4 | S1, S3, S40 |
| R5 | S6, S7, S44 |
| R6 | S6, S7, S29 |
| R7 | S5, S8 |
| R8 | S9, S10, S37 |
| R9 | S13, S38 |
| R10 | S10, S12 |
| R11 | S6 |
| R12 | S14, S33 |
| R13 | S15, S34 |
| R14 | S16 |
| R15 | S17, S39 |
| R16 | S18, S19, S25 |
| R17 | S20 |
| R18 | S21 |
| R19 | S22 |
| R20 | S23 |
| R21 | S24 |
| R22 | S26 |
| R23 | S26, S28 |
| R24 | S27 |
| R25 | S18 |
| R26 | S29 |
| R27 | S29, S30 |
| R28 | S31 |
| R29 | S10, S11, S6 |
| R30 | S12, S17, S19, S20, S29 |
| R31 | S32 |
| R32 | S32 |
| R33 | S35, S40 |
| R34 | S41, S44 |
| R35 | S36 |
| R36 | S43 |
| R37 | S41 |
| R38 | S42 |
| R39 | S35 |
| R40 | S46 |
| R41 | S39, S47 |

| scenario | rules |
| --- | --- |
| S1 | R3, R4 |
| S2 | R3 |
| S3 | R4 |
| S4 | R3 |
| S5 | R3, R7 |
| S6 | R5, R6, R11, R29 |
| S7 | R5, R6 |
| S8 | R7 |
| S9 | R8 |
| S10 | R8, R10, R29 |
| S11 | R29 |
| S12 | R10, R30 |
| S13 | R9 |
| S14 | R12 |
| S15 | R13 |
| S16 | R14 |
| S17 | R15, R30 |
| S18 | R16, R25 |
| S19 | R16, R30 |
| S20 | R17, R30 |
| S21 | R18 |
| S22 | R19 |
| S23 | R20 |
| S24 | R21 |
| S25 | R16 |
| S26 | R22, R23 |
| S27 | R24 |
| S28 | R23 |
| S29 | R6, R26, R27, R30 |
| S30 | R27 |
| S31 | R28 |
| S32 | R31, R32 |
| S33 | R12, R29 |
| S34 | R13 |
| S35 | R33, R39 |
| S36 | R35 |
| S37 | R8 |
| S38 | R9 |
| S39 | R15, R41 |
| S40 | R4, R33 |
| S41 | R34, R37 |
| S42 | R38 |
| S43 | R36 |
| S44 | R5, R34 |
| S45 | R1, R2 |
| S46 | R40 |
| S47 | R41 |

## 8. Approach

**CI.** Every test builds its own world and leaves nothing behind. That world is:

- a temp git repository with a bare remote, and a version file;
- a dummy application, "acme", with two images, `payload_image`, a `required_hooks` list and a second environment `join`;
- stub hooks that log their argv and environment and exit as each test sets;
- `registry:2` as a CI service. For S40 it runs with an htpasswd user per role and a proxy that refuses writes outside each role's repositories;
- a "host" container reached through a stub `ssh` that runs `deliver-host` inside it, with Docker-in-Docker for compose, `RepoDigests` and pulls;
- stub `systemctl` and `sudo` inside the host container;
- a stub `gh` that answers checks, milestones and issue types from fixture files and logs every mutation.

Interruption is a hook that kills its parent. `pull_timeout` is tested through a throttling proxy, and time is not otherwise manipulated. Confirmation prompts and hidden prompts run under a pty. Each gate's test is first shown to fail by disabling the reason, as docs/1.9 requires. Each check's test includes its quiet case.

**[REH].** Claude runs S33 to S39 and the real halves of S14, S15 and S42 on Tile Lite Elite's rehearsal VM. They use the real OCI registry, instance-principal login, systemd and TLE's own hooks, and they run before the merge (docs/1.9 *What tests the tooling*).

**Production role.** The production-role gates (S29, S30, and R26 and R27 generally) are tested in CI only. On a real host they are shown by 0.10.2's first production deploy, a post-deployment check against #555 and #556:

- the deploy log names the version and digests;
- settle moved exactly the record's work packages;
- `deliver status production` matches the record.

Work package #555's test-approach box "exercised against rehearsal standing in for production" is replaced by this.

### Only a real host can show

- instance-principal login and the OCI IAM split;
- the measured pull time and the 1 GB footprint, including the OCI CLI's peak (#554);
- systemd units really enabled;
- the state surviving a reboot;
- the lock shared with the backup;
- TLE's database snapshot, restore and migration;
- the `deploy.sh` fallback.

Everything else runs in CI.

## 9. Test names

### Build

- `build_refuses_a_commit_not_on_the_remote`
- `build_ignores_the_operators_dirty_tree`
- `build_labels_revision_and_version`
- `build_pushes_each_image_as_sha_dash_image`
- `build_never_pushes_over_an_image_already_stored`
- `build_refuses_when_the_registry_cannot_be_queried`
- `build_without_a_hook_uses_buildx_bake`
- `multi_arch_build_deploys_by_index_digest`

### Deploy

- `deploy_refuses_an_image_whose_label_is_another_sha`
- `deploy_runs_the_payload_from_the_image_not_the_tree`
- `preview_joins_its_own_files_from_the_payload`
- `deploy_refuses_while_the_lock_is_held`
- `deploy_with_wait_proceeds_when_the_lock_frees`
- `pre_deploy_not_yet_refuses_without_wait_and_waits_with_it`
- `missing_required_hook_refuses_and_missing_optional_hook_is_skipped`
- `set_aside_works_only_for_an_overridable_hook`
- `interrupted_deploy_is_refused_until_rolled_back`
- `failed_migrate_restores_state_previous_images_and_host_files`
- `failed_smoke_restores_state_previous_images_and_host_files`
- `host_files_installed_with_modes_and_units_enabled`
- `status_reports_a_host_file_that_differs`
- `host_keeps_only_current_and_previous_images`
- `rehearsal_cycle_must_start_from_productions_record`
- `off_level_override_is_recorded`

### Release

- `release_refuses_a_commit_rehearsal_did_not_pass`
- `skip_rehearsal_records_reason_and_raises_retrospective`
- `release_refuses_a_commit_not_on_main`
- `emergency_must_be_cut_from_the_newest_release_tag`
- `emergency_refuses_a_commit_carrying_unreleased_main`
- `release_refuses_while_a_required_check_is_not_green`
- `release_refuses_a_spent_or_lower_version`
- `release_refuses_a_milestone_that_disagrees_with_the_commits`
- `release_check_refusal_stops_the_release`
- `release_refuses_a_mistyped_confirmation`
- `release_record_in_registry_equals_the_tag_message`
- `release_rerun_resumes_after_the_tag_without_repeating`
- `release_failure_before_the_tag_spends_nothing`
- `emergency_release_moves_main_and_its_milestone_on`
- `unknown_record_version_is_refused`
- `pre_tool_tags_are_read_as_history_only`

### Production and settle

- `production_refuses_a_version_without_a_record`
- `unrecorded_override_copies_without_spending_a_version`
- `production_refuses_a_raw_sha`
- `settle_acts_on_exactly_what_the_record_carries`
- `settle_failure_exits_3_and_the_deploy_stands`
- `settle_rerun_changes_nothing`
- `rollback_without_a_previous_deploy_names_the_fallback`

### Logs, access and housekeeping

- `every_run_log_names_each_gate_it_ran`
- `check_mode_changes_nothing`
- `only_the_release_copier_can_write_releases`
- `no_secret_reaches_a_log_record_tag_or_screen`
- `pull_beyond_timeout_refuses_before_change`
- `prune_keeps_releases_and_deployed_candidates`
- `env_create_and_destroy_leave_nothing_behind`
- `host_install_installs_dependencies_and_sudo_rule`
- `tool_names_no_application`
- `registry_address_never_comes_from_the_profile`
- `board_reads_v_tags_as_released_and_prod_tags_as_history`

### [REH]

- `rehearsal_pulls_by_instance_principal_and_cannot_read_releases`
- `rehearsal_smoke_failure_restores_the_database`
- `rehearsal_backup_timer_installed_and_enabled`
- `deploy_waits_for_the_backup_lock`
- `interrupted_state_survives_a_reboot`
- `first_deliver_deploy_takes_off_level_and_deploy_sh_can_return`

## 10. Gaps

**Status, 2026-10-28.** The design was revised after this list was drawn up. X1 to X13 and X16 are closed there: settle moves any carried work package; production's record comes from its host's state; "on `main`" stands and docs/1.2 §1.0 is corrected; an emergency descends from the release production runs; a first deploy's failure is defined; `[release].overridable` names the gates; `--wait` has a 60-minute limit; `--unrecorded` takes a full SHA; a rerun's exits are stated; dropped host files are removed; prune counts from the newest release's time; an ambiguous short SHA refuses; a check leaves the exit code alone. X14 and X15 stay as written.

Each gap is a question for the owner.

| gap | what it would take to close it | why it is acceptable for now |
| --- | --- | --- |
| X1 Settle's table covers Production Release work packages and non-project issues. A carried project of another route, such as an Application Tooling package that a `Refs` in the release names, matches no row. docs/1.2 §2.5 says "a project advances to Post-deployment". A test asserting either fails against the other. | Add a row for any carried project, or say that the milestone gate keeps them out. | Not acceptable: S30's fixture must pick one. |
| X2 How the rehearsal-cycle gate learns production's current record is unstated: production's host state over ssh, the last settled tag, or `status production`. When production runs a pre-tool release with no record, only §10 says what to do (`--off-level`), not the generic rule. | One line in §6. | S17 stubs the source, so it is writable but not pinned. |
| X3 docs/1.2 §1.0 says "a release is made from `main`'s tip". The gate accepts any commit on `origin/main`. | Owner picks one, and the other document is fixed. | S20 asserts "on `main`"; a "tip" test would be added. |
| X4 The emergency must descend from the *newest* release tag. Today that is `v0.10.1`, which never ran in production. An emergency on production's 0.10.0 would therefore ship 0.10.1's changes. docs/1.2 says "the last released tag". | Say "newest made" or "production's", and fix docs/1.2 or the design. | S20 is testable as written. The question is about intent. |
| X5 A first deploy to an environment that fails after `save-state` has no `previous` to switch back to. The restore and the exit are unstated. | One line in §9. | It bites on 0.10.2's first production deploy, where `deploy.sh` is the fallback. |
| X6 `--set-aside GATE`: no profile key is shown that marks a hook overridable, and nothing says how GATE is named. | Add the key to §5's example. | S12 assumes a key and the hook's name. |
| X7 `--wait` has no limit or interval, whether for the lock or for exit 75. Dark Portal's window can be 50 minutes. The limits-and-timeouts answer omits it. | State the limit and where its number came from. | The test asserts only that it proceeds. |
| X8 `--unrecorded`: the REF form (a SHA?) is unstated. Whether it needs a rehearsal pass, and what happens when `SHA-IMAGE` is already in releases (an immutable store), are also unstated. | One line in §4. | S29 assumes a SHA and a no-op copy. |
| X9 A release rerun where the tag's record differs (a different commit), and a rerun where every step is done: neither exit is stated. Also, a command "ending with a gate unrun refuses" cannot be provoked from outside, and §4 gives no per-command gate list beyond §6. | State both exits. A test hook or a documented gate list would let a test provoke the gate count. | The runs log is asserted against §6 (O23). The self-check is reviewed, not tested. |
| X10 A host file present in the previous release and dropped in this one: removed or left? On rollback, the current release's extra files: removed or left? | One line in §9. | No TLE host file is being dropped in 0.10.2. |
| X11 Prune's "older than the newest release" does not say older by what: push time, the commit's date, or the version. | One word in §4. | Capacity is not pressing for 0.10.2. |
| X12 A short SHA matching two candidates: refuse? | One line in §4. | Rare. The test assumes a refusal. |
| X13 The exit for the `post-deploy` check's non-zero is unstated: 0, or 3 like settle? | One line in §4. | The test asserts only "reported, nothing changed". |
| X14 The `oci-api-key` adapter (Dark Portal's copier) is exercised by no Tile Lite Elite test. | Dark Portal's adoption (#15) tests it. | Dark Portal is out of scope here. |
| X15 The production-role gates are shown on a real host only by 0.10.2's first production deploy (post-deployment check), not before the merge. #555's test approach still says "rehearsal standing in for production". | #555's box is changed to point at the CI tests and the post-deployment check. | Agreed by the coordinator: production reads and deploys are the owner's, and the rehearsal identity cannot read releases. |
| X16 #117's body has no list of the owner's decisions, though the design says "listed in #117's body". Its test approach names `deploy --list`, which is not a command (`list ENV`). | Edit #117's body. | Documentation only. |

Derived by a fresh `test-designer` agent that read no implementation (docs/1.9).
