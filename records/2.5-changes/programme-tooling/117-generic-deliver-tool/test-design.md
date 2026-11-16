<!-- markdownlint-disable-file MD013 -->

# Test design specification: Turpin

Project: delphside/programme#117 · type of change: `tooling` · route: `Docs and Programme Tooling` · release: not applicable

This specification derives the tests for `turpin` from its stated rules, without reading the implementation. Its sources are:

- the design, `records/2.5-changes/programme-tooling/117-generic-deliver-tool/design.md` (2026-11-14 revision);
- #117's body;
- delphside/tile-lite-elite#545, #555 and #556;
- docs/1.2 *Making a release, then deploying it* and §2.5;
- docs/1.9.

**(H)** marks a rule taken from the agreed handover rather than from a document.

**†** marks a rule, scenario or test that reads production: its host state over ssh, or, for the emergency gate only, its `/health` where it has no `turpin` state. It is the source of production's level (R15) and of the release production runs (R17). The owner decided on 2026-10-29 that this read is a scripted check, named in each application's CLAUDE.md beside `verify.sh`, `check-hosts.sh` and the `/health` reads (X2).

Each test has one of two kinds:

- **[CI]** is a `unittest` test in `scripts/tests/test_turpin_*.py` for the client, `turpinlib`, or a Bats test in `scripts/tests/turpin-*.bats` for `turpin-host` and the payload. It uses a dummy application, stub hooks, `registry:2`, and stubbed `ssh`, `gh` and `oci`; a `unittest` test replaces the registry adapter's bottom-layer functions with stubs.
- **[REH]** is a technical test on Tile Lite Elite's rehearsal.

The gates for the `production` role are tested in CI only. On real hosts they are shown only by 0.10.2's first production deploy and by the owner's `--check` runs, which are post-deployment checks and not tests (part 8).

## 1. Rules

| | rule | source |
| --- | --- | --- |
| R1 | The tool names no application and no machine. Anything that differs comes from `app-profile.toml` or a hook. | G1; §2 |
| R2 | The registry address is never in the profile. Each component reads `TURPIN_REGISTRY` from its own local configuration. | §3 |
| R3 | `build [REF]` is non-interactive and refuses a REF that is not a commit on the remote. It builds from a clean worktree with the `build` hook, or `docker buildx bake` by default. It labels each image `org.opencontainers.image.revision` = SHA, `.version` = the version file and `.created` = the build's start, which `build` sets once per build, in RFC 3339 form, UTC, and gives the hook as `TURPIN_CREATED`; the hook writes the labels (the default hook by `--set IMAGE.labels...` on its `bake`, and the same under `--load`), and `build` reads them, before any push, from the configuration of each platform image in each layout, passing over attestation manifests, which carry none, and refuses an image whose labels differ, exit 1, pushing nothing. The hook writes each image as an OCI image layout, which the builder pushes as `SHA-IMAGE` with its own `skopeo` login; it prints the digests, an index digest for a multi-arch build, each equal to the digest the registry stores. | §6; §8 |
| R4 | An image whose `SHA-IMAGE` is already present is not rebuilt. A failed registry query stops the build, exit by type (75 or 2). A version tag or `VERSION-record` that releases already holds with other contents is never written; a copy of the same digest is a no-op. | §6; §9; §3 |
| R5 | The payload goes into `payload_image` at `/turpin/`, from the pinned submodule and the app repository. It holds nothing secret, and its `profile.json` only the profile keys a host reads (R74). Joined files come from the payload and never from a working tree. An environment may name its own `join`. | §3; §8 |
| R6 | `deploy ENV REF` checks REF against the environment's role. For preview, test and rehearsal, REF is a full or short SHA or a version, resolved in candidates. A short SHA that matches more than one candidate refuses. For production it is a version with a record, pulled from releases. The deploy runs over ssh, or locally where `host = "controller"`, and then `settle` for production. Gates key on the role, never the name. | §2; §6 |
| R7 | Every image is pulled by digest. Its revision label must equal the SHA, and the running containers' `RepoDigests` must match. | §9 |
| R8 | The environment's lock (`flock`) must be free and is held to the end. `--wait[=MINUTES]` waits for the lock and for a hook's exit 75, checking each minute, for at most 60 minutes by default. At the limit it stops as a blip, exit 75, naming what it waited for, with nothing changed. | §6; §9; §11 |
| R9 | A deploy refuses unless `state.json` shows the last deploy finished. Exceptions: no state (a first deploy), `preparing` (a deploy stopped before `save-state`, nothing that runs changed), `restored` and `failed, no previous deploy` (a first deploy that failed and was restored) do not refuse, and the next deploy is the way forward. The way out of any other unfinished state is `turpin rollback`; a redeploy refuses until then. This is the deploy column of §11's state table; R57 has the rollback column. | §9; §11 |
| R10 | `pre-deploy` is a gate. It can be set aside with `--set-aside`, where the profile marks it overridable. | §8; §9 |
| R11 | A deploy runs these steps in order: lock, then state, then pull by digest, then payload, then `pre-deploy`, then the new deploy folder, then `changing: deploy` recorded, then `save-state`, then `migrate`, then host files, then `compose up` from `pending`, then `smoke`, then the pivot (one write of `state.json`: `current`, `previous`, finished), then pruning host images. Compose runs with a fixed project name, `--project-directory` the deploy's own folder `deploys/N`, the host `.env` and then `deploys/N/turpin.env`, and `--no-build`. | §11 |
| R12 | A failure from `save-state` on runs `restore-state`, given `pending`'s number, reinstalls `current`'s host files, runs `compose up` from `current` and clears `pending`, keeping its folder; `current` and `previous` move only at the pivot. It then exits by the error's type: 1 for a hook's refusal or failure. On a host's first `turpin` deploy there is no `current`: the failure runs `restore-state`, then leaves every host file that existed before the deploy and removes those it added, runs `compose down` only where its `compose up` was started and otherwise starts again the containers that were running when the deploy began, clears `pending`, keeping its folder, marks the state `failed, no previous deploy`, and exits by the error's type, naming the application's fallback (R68). | §8; §9; §11 |
| R13 | Host files are installed with their modes, followed by `systemctl daemon-reload`. Units marked `enable` are enabled and restarted. A host file the previous deploy installed and this one does not carry is removed. `turpin status` compares the host's copies with the payload, as a check. | §9; §11 |
| R14 | A host keeps only its current and previous image sets. | §11; §13 |
| R15 † | A rehearsal cycle is the deploys to a rehearsal-role environment since the last release was made. Its first deploy must be production's current record, read from the production host's state over ssh and pulled from candidates by the same digests. Production running a build with no record refuses. `--off-level REASON` sets this aside. | §9 |
| R16 | `release` releases the commit that the rehearsal-role environment runs. It refuses unless that environment's last deploy finished and its `smoke` passed. The owner confirms by typing the version, or with `--expect VERSION`. `--skip-rehearsal REASON` sets this aside, is recorded, and raises the retrospective issue. | §6; §9; §10 |
| R17 † | The release commit must be on `origin/main`. With `--emergency REASON` it must instead descend from the tag of the release production runs (its record, read from production's host state; where production has no `turpin` state, the version its `/health` reports, whose tag is the release's, the one naming the commit `/health` reports where two tags carry the version; the carried range of R42 reads it the same way and does not refuse, R70), and none of its commits after that tag may be on `main`. The newest tag is not the test: a release made but not yet run in production does not count. | §9 |
| R18 | Every check in `required_checks` must be green on the commit. | §9 |
| R19 | The version is read from the version file at the commit. No tag or record may exist for it, and it must be higher than the newest release tag of any prefix. | §6; §9 |
| R20 | Parents aside, every open issue in milestone VERSION must be evidenced by a `Refs #N` since the release production runs, or confirmed by a person as in this build (R71). A parent's `Refs` is reported beside its work package and never counted for it (delphside/tile-lite-elite#375). A commit a later commit in the range reverts, and that revert, name nothing. Every work package those commits name whose `Route` is Production Release must be in the milestone; work packages of other routes are left out. With `--emergency`, open issues evidenced only by commits on `main` are left out of the check and moved by step 7. Otherwise the release refuses. `--set-aside milestone REASON` sets the gate aside where the profile's `[release].overridable` lists `milestone`. | §9; docs/1.2 |
| R20a | Every work package in milestone VERSION has a *Functional user tests* or a *Technical tests* heading, and every box under the headings it has is ticked (`release.outstanding`); a package with neither heading refuses. With `--emergency` it is a check: reported, not refused. | §9 |
| R21 | `release-check` is a gate. It can be set aside with `--set-aside` where overridable. | §9 |
| R22 | The release runs in this order: gates and confirmation, then copy, then `VERSION-record`, then the annotated tag `vVERSION`, then the GitHub Release, then the bump, then the milestone. A copy already present with the same digest is a no-op. The version is spent at the tag. A rerun after the tag checks that the tag's record matches and resumes at the GitHub Release. The tag is the release's pivot: a failure before it stops the run, exit by its type, with nothing spent; a failure after it is an error, the later steps still run, and the exit is 3, the message naming `turpin release`. | §10; §6 |
| R23 | The record has the §10 fields, `record: 1`, and the tag's message is the record. A reader refuses an unknown record version. A tag without JSON is history only. | §10 |
| R24 | The bump goes to the next patch above both the released version and `main`'s own. An emergency that holds `main`'s number moves `main` on, and step 7 moves the open issues the gate left out into the next milestone. | §10 |
| R25 | The GitHub Release notes run from the previous release tag of any prefix. The next milestone is opened. | §10 |
| R26 | A production deploy needs a record for VERSION, with its digests pulled from releases. `--unrecorded REASON` instead copies `SHA-IMAGE` to releases with no record. No version is spent, and settle moves nothing. | §6; §9 |
| R27 | `settle` acts only on what the record carries. A carried work package goes to Post-deployment with a comment. Only Production Release work packages are carried, because the milestone gate counts no other route. A carried non-project issue is closed as completed with a comment. The milestone is closed. Each action checks first, so settle is safe to rerun, and it has no pivot. An action that fails is an error: the other actions still run, the items left are listed, the deploy stands, and the exit is 3, the message naming `turpin settle VERSION`. | §12; §9; §6 |
| R28 | Rollback switches to `previous` and runs `restore-state`, given `current`'s number, and restores the previous deploy's host-file set, removing the current deploy's extra files. With no previous deploy it refuses and names the fallback. R57 has the other states. | §11 |
| R29 | A hook listed in `required_hooks` that is missing or not executable refuses. Any other missing hook is a no-op. A hook's exit means 0 passed; 75 not yet, which without `--wait` stops the run, exit 75; and anything else refused or failed, a business error naming the hook, exit 1. Hooks receive `TURPIN_APP`, `_ENV`, `_ROLE`, `_SHA`, `_VERSION`, `_STATE` and `_IMAGE_<NAME>`; `_URL` (the environment's `url`, empty where it has none); `build` also `_CREATED` and `_SHORT_SHA`; from the deploy's step 6 on every hook on the host also `_DEPLOY`, `_DEPLOY_DIR` and `_COMPOSE` (R64), `save-state` also `_CURRENT`, and `restore-state` the `_DEPLOY` of the deploy it undoes (§8). Every hook on a host runs with its input from `/dev/null`. A hook of kind check (`post-deploy`) that exits non-zero is reported as a warning, changes nothing else, and leaves the exit code as it was. | §8; §9 |
| R30 | Every override takes a reason. The reason goes into the record where there is one, and always into the run log. | §6 |
| R31 | Every command writes a run log on its own machine, naming each gate it ran. A command that ends with a gate unrun refuses. Exits are 0 done, with at most warnings; 1 a gate refused or a business error; 2 a fundamental technical error; 75 a blip whose retries ran out, or `--wait` at its limit; a blip over `ssh` is retried where a retry is safe, a deploy or rollback repeated under its `request_id` and so taking effect at most once, and a build not retried; 70 an unexpected error; 3 done with errors, a step after the command's pivot having failed; 64 a usage error (a bad flag or a missing argument); 130 interrupted, the message naming the rerun and, for a command with a pivot, saying whether its change is live. A run that stops before its pivot has undone what it changed. A call that reads data changes something only once its data has arrived whole. | §6 |
| R32 | `--check` runs every gate and changes nothing. | §6 |
| R33 | Each component has its own registry access, and no component's credential can do another role's writes: the builder alone writes and removes candidates, the copier alone writes releases, the controller and the hosts write nothing. | §5; §3; §13 |
| R34 | Nothing secret is written to a profile, record, tag or log. | §13 |
| R35 | Every pull completes within the environment's `pull_timeout`, or the deploy refuses before any change. | §11; §13 |
| R36 | `prune` removes candidates whose `created` label (the build's start) is before the newest release was made, not released, and not in any environment's current or previous deploy. It never removes releases. The controller chooses; R46 says who removes. | §6 |
| R37 | `env create\|destroy NAME` works from the profile's template: a user, a state folder, a `.env` with secrets at a hidden prompt, a Compose project, and the hooks. | §6 |
| R38 | `host-install ENV` installs or updates `turpin-host` and its libraries and the single `sudo` rule on an environment's host, makes its state folder (mode 0700, the deploy user's) and an empty `.env` (mode 0600) where there is none, never overwriting one (R73), installs `jq` where it is missing, and checks that `flock` and the credential kind's tools (`oci`) are present, refusing when one is not. | §6; §11 |
| R39 | The credential kinds are `oci-instance-principal`, `oci-api-key` and `docker-config`. Hosts log in by instance principal. | §3; owner 2026-10-28 |
| R42 | The carried range starts at the release production runs, so a release made while an earlier one is undeployed carries both; an item named only by a commit a later commit in the range reverts is not carried, and a revert of a commit outside the range has no effect. | §9; §10 |
| R43 | Settling a record settles the items of the earlier releases it carries (comment `..., deployed with vV`), closes their milestones, and takes a dropped item out of its milestone with a comment, leaving its state alone; a rerun changes nothing. | §12 |
| R40 | `status ENV` shows the digests, the matching record, the deploy state and host-file equality. `list ENV` shows the records beside what ENV runs. | §6 |
| R44 | Each component has a registry login of its own. A component that only calls `skopeo` (the controller's reads, the copier, the builder's reads and pushes) uses its own auth file, `~/.config/turpin/auth/APP/COMPONENT.json` (directory 0700, file 0600), chosen by `REGISTRY_AUTH_FILE` alone; a component that calls `docker` (a deployer's pull) uses the machine user's own `docker` login; the builder pushes with its own auth file. `DOCKER_CONFIG` is never set, so contexts and builders stay. Components sharing a machine never replace one another's login. The one exception is an environment on the builder's machine (preview on the laptop), which shares the builder's `docker` login: `turpin login` refuses it and names `turpin login builder`, as does a refused pull. A `docker-config` auth file that is missing is refused, naming `turpin login COMPONENT`; a registry refusal names it too. | §3 |
| R45 | The controller reads candidates and releases (digests, tags, records) with its own login, `[turpin].login`, and with no other. | §5; §3 |
| R46 | `prune`: the controller chooses what to remove, and sends `turpin remove` on `[turpin.build].on` a request listing each candidate (commit, image) with its digest (`removes`) and the digests releases holds (`keep`). The builder removes each through the Artifacts API with its removal credential, only while the tag still has the digest sent, and refuses any digest in `keep`. A candidate it fails to remove, or refuses, is an error: the others are removed and the exit is 3. A tag moved to another digest, a tag already gone, and an image that carries a tag outside `removes` (a digest shared with a commit that is kept) are left, which is no error. The controller never removes. `--dry-run` sends nothing. | §6; §3 |
| R47 | `turpin login COMPONENT` makes the `docker-config` login on the component's machine: `skopeo login --authfile` for the controller and copier, that for the builder too, and its `docker login` only where an environment on its machine pulls with that login, each by `turpin login` (passed on by `ssh` where the machine is another); `docker login` for an environment's deployer, by `turpin-host login`. The token is read at a hidden prompt and passed on standard input only: never printed, logged or an argument. | §6; §3; R34 |
| R48 | A domain type checks its own form where the value is made: a `Digest` is `sha256:` and 64 hexadecimal characters, a `Version` is semver, a `Build`'s `commit` is a full 40-character SHA, a `Repository`'s kind is candidates or releases. A value that fails its form, from an argument or the version file, is refused before any registry call, as a business error, exit 1, naming where it came from, with each bad value in its result's `violations` (field, value, limit and reason); a field that fails its form in a request sent to `turpin-host`, or to `turpin` on any machine, is an unexpected error, exit 70. A setting missing or malformed, in a profile, the reading machine's `APP.env` or a host's `.env`, is a fundamental technical error, exit 2, naming the key or the line where the file does not parse, found where it is read. A short SHA is resolved to a full one by *list versions* before it reaches a `Build`; one resolving to no build or to several is a business error then, exit 1, naming the argument. The request's rules (no overwrite, the keep list) are checked before any write. | §3 *Validation and errors*; §8 |
| R49 | The middle layer, through the translators, reads Oracle's answers: a manifest unknown is *absent* on a read and a business error (exit 1) where the operation needed it; a reply that arrives whole but is invalid (an unknown media type, a missing field, a digest other than the one asked for, an OCID of the wrong kind) is an unexpected error, never *absent*. Output not in the tool's format at all (not JSON, no envelope) is an unexpected error the bottom layer finds. An unexpected error exits 70, its message saying it was not expected and is to be raised as an issue, its cause in the log. | §3 *Validation and errors* |
| R50 | An error reaches the user as one of three types. It is raised where it is found (a business error by the top or the middle, a technical error and an unexpected error of output not in its format by the bottom, an unexpected error of an invalid reply by the middle), with the registry address, namespace and OCIDs removed, translated once and keeping its type when wrapped. Where it stops the run it exits by type: business 1, naming which input to fix; technical 75 for a blip, saying to try again later, and 2 for a fundamental one, naming its next step (`turpin login COMPONENT`, the policy, installing the tool or the setting to fix); unexpected 70. A usage error (64) and an interruption (130) are outside the three types. | §3 *Operations*, *Validation and errors*; §6 |
| R51 | The bottom layer retries a blip (a network error, a timeout, HTTP 429 or 5xx), and only in reads, copy, push and delete: three attempts, waiting 2 seconds then 4, each retry logged; retries run out as a technical error, a blip that kept failing, exit 75. A fundamental technical error (authorisation, a missing tool) is never retried. Every `oci` call carries `--no-retry`. `skopeo`'s status is read from its error text; its exit status 2 is never taken as absence. | §3 *Validation and errors*; §13 |
| R52 | Promote writes every image, then the record: a failure before the record leaves no record, and a resumed release copies only what is missing. A remove that fails between its check and its delete leaves the image, and the next `prune` removes it. | §3 *Validation and errors*; §10 |
| R53 | A delete answered `NotAuthorizedOrNotFound` is a fundamental technical error naming the builder's policy, an error in `prune` (R46), unless an earlier attempt of the same delete in this run timed out or got a 5xx; then a fresh find of the image by digest that finds nothing counts as removed. | §3 *Validation and errors* |
| R54 | Pruning a host's deploy folders other than current and previous leaves only each folder's `meta.json`, holding the whole record. | §11 |
| R55 | Each command that changes something has a pivot. `deploy`'s is marking the state `finished`, once `smoke` has passed, so a `smoke` failure after `compose up` from `pending` still restores; `release`'s is the tag; `settle` and `prune` have none. Before the pivot an error stops the run, undoes what changed and exits by its type. After it, or at an action of `settle` or a delete of `prune`, an error is logged at severity *error*, the steps that do not need the failed one still run, and the exit is 3, the message naming the command that reruns what failed. | §6 *Errors, results and the pivot*; §10; §11; §12 |
| R56 | Each error and warning in the run log, and `turpin-host status --json`'s output, is docs/1.10's result object: `outcome` (ok, warning, error or fatal); for an error or a fatal one, `type` and, for a technical one, `blip`; `reason`, upper snake case and unique in its domain; `domain`, `turpin`, or `oracle` for a registry call's cause; `message`, one sentence naming the next step, holding no tool's text and no registry address, namespace or OCID; `metadata`; `violations` for a refused value (field, value, limit and reason); `cause`, the result from below, nested. | §2 *Domain model*; §3 *Validation and errors*; §6 |
| R41 | Tile Lite Elite's move: the first `turpin` deploy to rehearsal takes `--off-level`. The fallback until 0.10.2 has run in production is the written procedure to 0.10.0: stop the `turpin` project, restore the snapshot, then `deploy.sh` at 0.10.0's commit with `DEPLOY_EMERGENCY` and a reason. 0.10.2 is the first release with a record. The board reads `v` as released and `prod-` as history. | §14; (H) |
| R57 | `turpin rollback` acts by `state.json`'s state, as §11's state table gives in its rollback column. None: refuses, naming the fallback. `preparing: STEP`: switches to `previous`, clearing `pending`, or, with no `previous`, refuses, naming the fallback. `changing: deploy`: a restore. `changing: rollback`: the rollback again. `finished` and `restored`: switches to `previous`, or refuses, naming the fallback, where there is none, so a second rollback after a finished one refuses, `previous` having been cleared. `failed, no previous deploy`: refuses, naming the fallback. `failed: the restore did not complete`: the restore again, a first deploy's where there is no `current`. A rollback that switches to `previous` and fails is recorded `failed` and, like one killed part-way, leaves `changing: rollback`, and is run again by `turpin rollback`; a rollback that runs a restore (from `changing: deploy`) and fails marks `failed: the restore did not complete` and is recorded `failed`, and `turpin rollback` runs the restore again; a new deploy refuses meanwhile (R9). A refusal is a gate's, exit 1. | §11 |
| R58 | On taking the lock, before any other step, `turpin-host deploy` and `rollback` read `state.json`'s `last_request`, and act by its outcome when the request's `request_id` is the last one's. `finished`: answered with the recorded result, running nothing, the exit kept (3 where the prune failed). `failed` and `refused`: answered with the recorded result, running nothing. `interrupted` (a deploy only; a rollback is never interrupted): run again. `running` (the request died part-way): refused, exit 1, running nothing, `last_request` left as found, the message naming `turpin status ENV`. Any other `request_id` runs as a new request, which writes its id with `running`. A request refused because the lock is held, and any under `--check`, write nothing. A repeat waits for the lock up to the `--wait` limit, else 60 minutes, and at the limit exits 75; it waits for a hook's *not yet* only where the command's own `wait` says so. A `request_id` is a version 4 UUID, which the host validates before it takes the lock, so a malformed one changes nothing; one that is not is an unexpected error (R48). A repeat answered from the record is, for `turpin`, the request's own result: after a `finished` deploy with exit 3, `turpin` goes on to `settle` on production as it would have. | §11 *The last request*; §6 |
| R59 | `turpin-host` owns the held-open input. It reads the request line, removes any `interrupted.PID` under its own process id, then starts a watcher that reads on to the end of input and there writes that file in the state folder. The file is keyed by process id, not by `request_id`, since a repeat shares its `request_id` with a request that may still be running, and two requests to one environment can run at once, one waiting for the lock. A deploy's steps look for their own file before each step and while they wait: the lock is taken in waits of one second (`flock -w 1`), and a hook's *not yet* is retried, each with a look between. A rollback looks only while it waits for the lock, so one holding the lock runs to its end. On exit, by a trap, `turpin-host` stops its watcher and removes its file; a file left by a killed request is never read. Every hook runs with its input from `/dev/null`, so a hook that reads its input gets end of file at once. | §6 *Interruption*; §11 |
| R60 | A state folder with no `state.json` but a `state` file or a `current` link, the layout of the Bash `turpin`, is refused by every `turpin-host` command that reads the state folder (`deploy`, `rollback`, `status` and `allowlist`), exit 2, naming it, since nothing says what it ran. The owner clears it by hand. | §11 |
| R61 | A gate run on a host is reported to `turpin` as one line on standard error, `@gate NAME RESULT` (`passed`, `refused` or `set-aside`), which `hosts.py` copies into the controller's run log and leaves out of what the operator sees. | §6 |
| R62 | A read of the board or git that cannot be made is never read as refused or as empty. The board model's `Unavailable` carries `transient`, true for a connection error, a timeout, 429 or a 5xx, which `turpin` maps to exit 75, and otherwise exit 2. A `ProfileError` is exit 2; any other exception is unexpected, exit 70. | §4 |
| R63 | The board model starts each `gh` and `git` it runs in a process group of its own, so a Ctrl+C reaches `turpin` alone and a read already running runs to its end. | §4; §6 *Interruption* |
| R64 | A hook on a host, from the deploy's step 6 on, is given `TURPIN_DEPLOY` (the deploy's number; for `restore-state` that of the deploy it undoes), `TURPIN_DEPLOY_DIR` and `TURPIN_COMPOSE`, a command line that runs Compose exactly as the deploy does: the project name, `--project-directory`, the env files and the compose files. `pre-deploy` and `post-deploy` are given none of the three. `TURPIN_CURRENT` is `save-state`'s alone. | §8 |
| R65 | `turpin-host compose APP ENV ARGS...` runs Compose against `current`'s folder with the same arguments as the deploy's (one function makes them), holds the environment's lock, the deploy's own, while it runs, refuses at once where the lock is held, refuses where there is no `current`, and needs no `sudo` rule. | §6; §11 |
| R66 | A hook is given `TURPIN_URL`, its environment's `url`, empty where there is none, on the host and on the controller. | §8 |
| R67 | Where an environment names no `ssh` alias, it is `[hosts.ENV].ssh`; its own `ssh` wins; with neither the profile is refused naming `environments.ENV.ssh`. | §8 |
| R68 | On a host's first deploy the restore (R12) puts back, with its old content, every host file the deploy overwrote, removes only those the deploy added, runs `compose down` only where `compose up` was started, and otherwise starts again each container that was running when the deploy began, after `restore-state`. A container that is gone is left. | §11 |
| R69 | `[turpin.build].args` names build arguments, each taken from `SHA`, `SHORT_SHA`, `VERSION` or `CREATED`; any other source is refused naming the key. The default `build` hook passes each to every image, under `--local` too. | §8 |
| R70 | Where production has no `turpin` state, `turpin release` reads `/health` through `[versions.deployed]` and the environment's `url` for the carried range as well as the emergency gate, and does not refuse; where two tags carry the version it takes the one naming the commit `/health` (or the host's record) reports, else the release prefix's. A `/health` it cannot read refuses. | §9 |
| R71 | An open issue in milestone VERSION that no commit names (parents aside) is a question: `turpin release` asks, per issue, `Confirm that #N is in this build [y/N]`, unless `--expect` or `--check` is given; `--confirm N`, repeatable, answers it without a terminal; an issue left unconfirmed refuses, naming it; a confirmed one is carried and settled like a named one and kept in the record's `carries.confirmed`; `--set-aside milestone` stays. The board model decides which issues need confirming. | §9; §10; owner 2026-11-04 |
| R72 | A move of the application's `programme` pin counts as reaching the image only where it changes `scripts/deliver/payload/` or `scripts/deliver/lib/` between the old pin and the new one; a pin that cannot be compared ships. | §3 |
| R73 | `host-install ENV` makes `/var/lib/turpin/APP/ENV/` owned by the deploy user, mode 0700, and an empty `.env`, mode 0600, where none exists, and never overwrites an existing `.env`; a copier or builder gets neither. | §11 |
| R74 | The payload's `profile.json` holds only the keys a host reads (`application`, `release.required_hooks`, `release.overridable`, `turpin.fallback`, `host_files`, `join`, `ephemeral`), so a change to another key changes nothing the image carries. | §3; §8 |

### Checked for contradiction

- R19 against R22 (a tag exists on a rerun) is reconciled by the resume, if the record matches. The design states both exits: a different record refuses (exit 1) and every step done says so (exit 0).
- R17 against docs/1.2 §1.0 is closed: the design says "a commit on `main`" and corrects §1.0 (design §5).
- R17's release production runs against docs/1.2's "last released tag" is closed by the design's wording. S50 is the case where they differ.
- R27 against docs/1.2 §2.5 is closed: a carried work package of any route advances.

## 2. Conditions, grouped into dimensions

- **C1 command** (complete over §6): build · deploy · release · settle · rollback · status · list · prune · env create · env destroy · host-install
- **C2 environment role** (complete): preview · test · rehearsal · production
- **C3 host placement** (complete): over ssh · local (`controller`)
- **C4 REF form** (complete): full SHA · short SHA (unique) · short SHA (ambiguous, refused: X12) · version with record · version without record · other name · absent
- **C5 REF on the remote** (complete): pushed · not pushed
- **C6 candidates for the SHA** (complete): all images present · some · none · registry query fails
- **C7 lock** (complete): free · held · held beyond the `--wait` limit
- **C8 `state.json` state** (complete): `finished` · `restored` · `preparing: STEP` · `changing: STEP` (killed by SIGKILL, or cut off by a reboot), before and after `compose up` from `pending` · `changing` from a rollback (killed part-way) · absent (first deploy) · `failed, no previous deploy` · `failed: the restore did not complete`
- **C9 hook** (complete, per hook): required and absent · required and not executable · optional and absent · exit 0 · exit 75 · other non-zero
- **C10 hook kind** (complete): gate · step · check
- **C11 deploy failure point** (complete): none · before `save-state` · `save-state` · `migrate` · host files · `compose up` · `smoke`
- **C12 previous deploy on ENV** (complete): exists · none
- **C13 rehearsal cycle position** (complete): first deploy of the cycle · later deploy
- **C14 the first deploy's target** (complete): production's current record, read from its host state · other · production runs a build with no record (†)
- **C15 rehearsal state against the release commit** (complete): runs its digests, finished, smoke passed · runs them, smoke failed · runs them, unfinished · runs another commit · never deployed
- **C16 commit ancestry** (complete): on `origin/main` · not on `main`, descends from the release production runs with no post-tag `main` commit · descends but holds a post-tag `main` commit · does not descend from the release production runs
- **C16a newest tag against the release production runs** (complete): the same tag · the newest tag is a release made but not run (0.10.1 made, 0.10.0 runs)
- **C17 required checks** (complete): all green · one failing · one missing
- **C18 version** (complete): new and higher · tag exists · record exists · equal to or lower than the newest tag of any prefix
- **C19 milestone against carried set** (complete): agree · open issue not carried · carried work package not in the milestone · a parent in the milestone only · a parent's `Refs` beside its only work package · a parent's `Refs` with two work packages in the milestone · an open issue evidenced only on `main` (emergency)
- **C20 release progress on a rerun** (complete): nothing done · copied, no tag · tag present with a matching record · tag present with a different record · all steps done
- **C21 owner confirmation** (complete): typed correctly · typed wrongly · `--expect` matching · `--expect` not matching
- **C22 override** (complete over §6): none · `--emergency` · `--skip-rehearsal` · `--unrecorded` · `--off-level` · `--set-aside` (overridable, including `milestone`) · `--set-aside` (not overridable) · flag without reason · `--wait` · `--check`
- **C23 settle item** (complete over the record): Production Release work package · non-project issue · milestone · work package of another route, referenced in the release's commits but in its own date milestone · parent
- **C24 settle progress** (complete): none done · some done · all done · `gh` fails
- **C25 registry credential** (complete): the component's own · another component's
- **C26 image arch** (complete): single · multi-arch index
- **C27 record version** (complete): 1 · unknown · tag without JSON
- **C28 host file** (complete): equal · edited · missing · new in this release · dropped in this release · on rollback, extra in the current release
- **C29 the version on `main` at an emergency** (complete): above the emergency · equal to it
- **C30 post-deploy check** (complete): exit 0 · non-zero, with the deploy otherwise exit 0 · non-zero, with the deploy otherwise exit 3
- **C31 source of production's level** (complete, †): host state over ssh, agreeing with the last settled record · host state over ssh, differing from it
- **C32 test boxes of a work package in the milestone** (complete): all ticked · one unticked · neither heading · one unticked, with `--emergency`
- **C33 a value's form, in an argument or the version file** (complete over the two forms an argument carries): valid · a bad version · a non-hexadecimal commit · a short commit resolving to one build · a short commit resolving to none or to several
- **C34 Oracle's reply** (complete): valid · whole but invalid (an unknown media type, a missing field, a digest other than the one asked for, an OCID of the wrong kind) · not in the tool's format at all · a manifest unknown on a read · a manifest unknown where the operation needed it
- **C35 one call's attempts** (complete over the retry rule): success · a network error then success · 503 then success · 429 on every attempt · 503 on every attempt · a timeout on every attempt · authorisation refused · `skopeo` exit 2 with a network error's text
- **C36 failure part way** (complete): promote, none · promote, after some images, before the record · promote, at the record · remove, between its check and its delete
- **C37 a delete answered `NotAuthorizedOrNotFound`** (complete): on its first attempt · after an attempt that timed out or got a 5xx, the fresh find finding nothing · the same, the fresh find finding the image
- **C38 deploys on a host** (complete): two or fewer · more than two
- **C39 where a step fails, against its command's pivot** (complete over the four commands that name one): deploy, before `save-state` · deploy, after `save-state`, at `smoke` · deploy, after `finished` (the host's prune; settle on production) · release, before the tag · release, after the tag · settle, one action of several · prune, one delete of several
- **C40 the type of an error that stops the run** (complete over the types): business · technical, fundamental · technical, a blip whose retries ran out · unexpected
- **C41 a result's fields** (complete over R56): a cause nested from a registry call · `violations` on a refused value · a tool's error text holding an identifier · `turpin-host status --json` with no error
- **C42 the last request on taking the lock** (complete over §11 *The last request*): a different `request_id` · the last one's with outcome `finished` · `finished` with the exit 3 of a failed prune · `failed` · `refused` · `interrupted` (a deploy only) · `running` · a `request_id` that is not a version 4 UUID
- **C43 the repeat's wait** (complete): the lock free · the lock held beyond the limit · a hook's *not yet*, with and without `--wait`
- **C44 an image's labels in its layout, read before any push** (complete): `revision`, `version` and `created` as the build set them · `revision` another SHA · `version` not the version file · `created` not `TURPIN_CREATED`
- **C45 a read of the board or git** (complete over R62): made · a connection error · a timeout · 429 · a 5xx · authorisation refused · a `ProfileError` · another exception
- **C46 where an interruption finds the host** (complete over R59): between two steps · waiting on the lock · waiting on a hook's *not yet* · a hook reading its input

## 3. Outcomes

| | outcome |
| --- | --- |
| O1 | Exit 1. The run log and stderr name the refusing gate. A before-and-after snapshot of the registry, the host's containers and the state folder (`state.json`'s `last_request` apart, which records the outcome after the lock), git refs and the `gh` stub log shows no change. |
| O2 | Candidates holds `SHA-IMAGE` for each profile image. Stdout prints each digest. The labels `revision` = SHA, `version` = the version file and `created` = the build's start, the same on every image of the build. |
| O3 | No push reaches the registry log for an image already present, and that image's digest is unchanged. |
| O4 | Exit 0. The containers' `RepoDigests` equal the named digests. `state.json` names a new `deploys/<n>` as `current` and the earlier one as `previous`, and `state` = finished. |
| O5 | The steps ran from `/turpin/` extracted from `payload_image`. A sentinel in the operator's working-tree copy is never touched. The joined files in `current/` equal the payload's own, or the environment's own `join`. |
| O6 | Hook calls were logged in the order R11 gives, each with the R29 environment variables. |
| O7 | After a failure: `restore-state` was called with `pending`'s number and the data is as before the deploy, `current` unchanged and `pending` cleared, its folder kept, the previous digests are running, the previous host files are in place, and the exit is by the error's type (1 for a hook's refusal or failure). |
| O8 | Host files have the payload's content and mode. The stub `systemctl` saw `daemon-reload`, then enable and restart for the marked units. |
| O9 | `status` reports a host file that differs, and is quiet when the files are equal. |
| O10 | Releases holds each digest identical to candidates (skopeo inspect), and holds `VERSION-record`. The annotated tag `vVERSION`'s message parses to the same JSON. Every §10 field is present. `set_aside` is `[]` when no gate was set aside. |
| O11 | `main` holds the bumped version. The stub `gh` saw the Release, with notes from the previous tag of any prefix, and the next milestone opened. |
| O12 | The override's reason appears in the record field (`emergency`, `rehearsal_skipped`, `set_aside`) where there is a record, and always in the run log. |
| O13 | The stub `gh` saw a retrospective issue naming the reason and what was skipped. |
| O14 | Settle: the stub `gh` saw exactly the record's work packages moved to Post-deployment, and nothing done to a work package of another route, the issues closed as completed with a comment, and the milestone closed. A rerun makes no new mutation. |
| O15 | The deploy stands (O4 holds), and the exit is 3 with the items left listed. |
| O16 | `--wait` blocks, then proceeds once the lock frees or the hook returns 0. |
| O17 | The registry refuses another component's write. The component's own credential succeeds. |
| O18 | A canary secret, from `.env`, the credential and the hidden prompt, appears in no log, record, tag, profile or terminal echo. |
| O19 | Grep finds no application name in `scripts/deliver/`. A second dummy profile drives every CI scenario. |
| O20 | `--check` exits 0 or 1 with every gate named in the log, and the O1 snapshot shows no change. |
| O21 | The host image list holds exactly the current and previous sets. |
| O22 | Prune leaves every release, every candidate referenced by an environment's current or previous deploy, and every candidate newer than the newest release. It removes the rest. |
| O23 | The run log names every gate that §9 lists for the command. |
| O24 | After a first deploy fails past `save-state`: `restore-state` was called, `state` = `failed, no previous deploy`, `save-state` was given no `TURPIN_CURRENT`, the new containers were stopped, `pending` and `pending`'s host files were removed, its folder kept for the next prune, the exit is by the error's type, and stderr names the application's fallback. |
| O25 | The host-file set equals the intended deploy's set exactly: files the intended deploy carries have the payload's content and mode, and files it does not carry are absent. |
| O26 | Exit 3. What was done before the failed step stands, the steps that do not need it ran, the run log holds its result at severity *error*, and the message names the command that reruns it. |
| O27 | A repeat answered from `last_request`: the recorded exit, the run log saying it was answered from the record, nothing run (O1's snapshot shows no change, and `last_request` is as it was). |
| O28 | A rollback ran to its end: `restore-state` was given the number of the deploy being left, `previous`'s digests are running and its host files are in place, `current` is the former `previous`, `previous`, `pending` and `target` are cleared, the state is `restored`, exit 0. |
| O29 | The run log names each gate that ran on the host with its result (`passed`, `refused` or `set-aside`), and the operator's screen holds no `@gate` line. |

## 4. Matrix

**Deploy: C2 × C4** (✓ accepted · ✗ refused · ? gap)

| | full SHA | short SHA unique | short SHA ambiguous | version with record | version without record | other name / absent |
| --- | --- | --- | --- | --- | --- | --- |
| preview, test, rehearsal | ✓ | ✓ | ✗ (X12; S58) | ✓, resolved in candidates | ✓ if the build exists, by its SHA | ✗ |
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
| `--emergency` | ✗, because it holds `main` after the tag | ✓ | ✗ | ✗ |

In this matrix "the tag" is the release production runs, not the newest tag. S50 is the case where they differ.

**Release rerun: C20.** Nothing done: full run. Copied, no tag: the copy is a no-op and the run resumes at the record. Tag with a matching record: resume at the GitHub Release. Tag with a different record: ✗, exit 1. All done: says so, exit 0.

**Failure point: C11 × C12.** Before `save-state` with a previous deploy: O1, nothing changed. Before `save-state` with none: O1. From `save-state` on, with a previous deploy: O7. With none: O24 (S57).

**The host's state against a new deploy and against `turpin rollback`** (R9 for
the first column, R57 for the second; design §11's state table). Each cell gives
the table's outcome and the scenario that shows it. A rollback's exit 0 is O28;
a refusal is exit 1, O1.

| state | a new deploy | `turpin rollback` |
| --- | --- | --- |
| none | runs: S57's first deploy to a bare environment | refuses, naming the fallback: S98 |
| `preparing: STEP` | runs, numbering past `pending`'s folder: S94, S95 | switches to `previous`, clearing `pending`: S99 case 1; with no `previous`, refuses, naming the fallback: S99 case 2 |
| `changing: deploy` | refuses, naming the step and `turpin rollback ENV`: S13 | a restore: S96 cases 1 and 2 |
| `changing: rollback` | refuses, naming the step and `turpin rollback ENV`: S100 | the rollback again, after a kill: S96 case 3; after a failure that did not kill it: S101 |
| `finished` | runs: S16 | switches to `previous`: S31; with none, refuses, naming the fallback: S31 |
| `restored` | runs: S13, S97 | after a restore, switches to `previous`: S97 case 2; after a finished rollback, refuses, naming the fallback: S102 |
| `failed, no previous deploy` | runs: S57, S94 | refuses, naming the fallback: S103 |
| `failed: the restore did not complete` | refuses, naming `turpin rollback ENV`: S95 | the restore again, a first deploy's where there is no `current`: S96's first deploy; where there is a `current`: S104 |

**The last request: C42 outcome × kind of request** (R58; design §11 *The last
request*). The cells are what a repeat of the same `request_id` gets. A
different `request_id` runs as a new request under the table above: S93's last
case.

| outcome | a deploy | a rollback |
| --- | --- | --- |
| `finished` | answered with the recorded result, running nothing: S93 case 1; with the exit 3 of a failed prune, answered with exit 3: S105 | answered with the recorded result: S93 case 2 |
| `failed` | answered with the recorded result: S106 case 1 | answered with the recorded result: S106 case 2 |
| `refused` | answered with the recorded refusal: S94 case 1 | answered with the recorded refusal: S93 case 3 |
| `interrupted` | run again: S91 case 1, S94 case 2, S108 case 2 | never written: S90's rollback |
| `running` | refused, naming `turpin status ENV`, `last_request` as found: S94 case 4 | the same: S107 |

The repeat's wait, and a `request_id` that is not a version 4 UUID, have
scenarios of their own: S108 and S109.

## 5. Scenarios

| | Scenario | Conditions | Outcomes | Kind |
| --- | --- | --- | --- | --- |
| S1 | Build an unpushed commit; push it; build; build again. | C5, C6 none→all | O1, then O2, then O3 | CI |
| S2 | Build with the operator's tree dirty. | C5 | O2; the image content is the commit's | CI |
| S3 | Build with only one of two images present; build with the registry query failing. | C6 some, fails | O3 for the present one, O2 for the other; then the build stops, exit 75 (a blip) or 2 (fundamental), with the registry unchanged | CI |
| S4 | Build with no `build` hook, then with one; each again under `--local`. | C9 | `docker buildx bake --builder turpin` with OCI output per target, its layouts pushed, then the hook is called and its layouts pushed; under `--local`, `bake --builder turpin --load` and the hook given `TURPIN_LOCAL=1`, nothing pushed | CI |
| S5 | Multi-arch build, then a deploy of it. | C26 | O2 with an index digest; O4 matches it | CI (buildx + qemu) |
| S6 | Deploy to rehearsal a SHA with no build; build; deploy over ssh. | C6, C3 ssh | O1, then O4, O5, O6, O8 | CI |
| S7 | Deploy to preview on the controller, with the preview's own `join`. | C2 preview, C3 local | O4; the joined files are `docker-compose.preview.yml` and `Caddyfile.preview` from the payload; no ssh call | CI |
| S8 | A registry tag repointed so the digest's revision label is another SHA; then a true image. | R7 | O1, then O4 | CI |
| S9 | Deploy while the lock is held; release it; deploy; `--wait` while held. | C7, C22 | O1, then O4, then O16 | CI |
| S10 | `pre-deploy` exits 1, then 75, then 75 with `--wait` returning 0 later, then 0. | C9 | O1; O1's snapshot with exit 75; O16; O4 | CI |
| S11 | A required hook missing, then not executable, then present; an optional hook missing. | C9 | O1, O1, O4; the optional one is a no-op | CI |
| S12 | `--set-aside pre-deploy R` where overridable and where not. | C22 | O4 + O12; O1 | CI |
| S13 | A deploy is killed after `save-state`, then rerun, then `turpin rollback`, then deployed. | C8 | O1 (it names the step), then O7-like restore, then O4 | CI |
| S14 | `migrate` fails; `smoke` exits non-zero; a host-file install fails; `compose up` fails. | C11, C12 exists | O7 each | CI; REH for TLE's real hooks (S33) |
| S15 | A new host file; an edited one; status before and after. | C28 | O8, then O9 then quiet | CI; REH (S34) |
| S16 | Three deploys in a row on one host. | R14 | O21 | CI |
| S17 † | A rehearsal cycle's first deploy is a SHA, not production's record; then production's record; then a SHA with `--off-level R`; a later deploy in the cycle with any SHA. | C13, C14 | O1, O4, O4 + O12, O4 | CI |
| S18 | Release while rehearsal runs another commit; with smoke failed; unfinished; then passed. | C15 | O1 ×3, then O10, O11 | CI |
| S19 | Release with `--skip-rehearsal R` against a rehearsal that never deployed. | C22 | O10, O12, O13 | CI |
| S20 † | Release a commit not on `main`; then the same commit with `--emergency R`, cut from the tag of the release production runs; then an emergency commit holding a post-tag `main` commit; then one not descending from that tag. S50 is the case where that tag is not the newest. | C16 | O1, O10 + O12, O1, O1 | CI |
| S21 | Release with a required check failing, then missing, then green. | C17 | O1, O1, O10 | CI |
| S22 | Release where the version file names a version whose tag exists; whose record exists; one lower than a `prod-` tag; then a new, higher version. | C18 | O1 ×3, O10 | CI |
| S23 | Milestone with an open uncarried issue; a carried work package not in it; a parent only; then agreeing. | C19 | O1, O1, O10, O10 | CI |
| S24 | `release-check` exits 1; `--set-aside release-check R` where overridable; exits 0. | C9, C22 | O1, O10 + O12 (the record's `set_aside` names `release-check`), O10 (`set_aside` is `[]`) | CI |
| S25 | The owner types the wrong version; `--expect` mismatched; typed correctly. | C21 | O1, O1, O10 | CI (pty) |
| S26 | Release fails at the record push; rerun. Fails at the GitHub Release; rerun. Rerun when all is done. A tag holding a different record. | C20 | O1-like with nothing spent, then O10; exit 3, then O11 without a second tag; "all steps done", exit 0, no mutation; O1 | CI |
| S27 | Normal bump; an emergency when `main` holds the emergency's number. | C29 | O11; `main` moves to the next patch and the milestone's open issues move | CI |
| S28 | A reader given record version 2; a text tag `v0.10.1`; a `prod-` tag. | C27 | O1; history only, not deployable as a record | CI |
| S29 | Production deploy of a version with no record; with `--unrecorded R` by SHA; of a recorded version; of a raw SHA without a flag. | C2 production, C4 | O1; `SHA-IMAGE` in releases, no tag, O12, settle moves nothing; O4 + O14; O1 | CI |
| S30 | Production deploy of a record carrying a Production Release work package and a non-project issue, where the release's commits also reference an Application Tooling work package in its own date milestone, and settle's `gh` fails partway; then `turpin settle VERSION` is rerun; then rerun again. | C23, C24 | O15; O14, with the Production Release work package moved and the Application Tooling one untouched; no new mutation | CI |
| S31 | Rollback with a previous deploy; with none. | C12 | `restore-state` called, `previous`'s digests and host files in place, `current` now the former `previous` and `previous` cleared, the state `restored`, exit 0; O1 naming the fallback | CI |
| S32 | Each command's run log and exit codes; `--check` on deploy and release. | R31, R32 | O23, O20 | CI |
| S33 | TLE's real hooks on rehearsal: snapshot, `--migrate-only`, `/health` within 60 s; smoke failure injected. | R12, R29 | O4; then O7 with the database restored | REH; the snapshot contract on the real hooks is delphside/tile-lite-elite#555's (S97's real half, part 8) |
| S34 | Host files on the rehearsal VM: the backup script and timer installed, the unit enabled; a file edited by hand. | R13 | O8 with real systemd; O9 | REH |
| S35 | Instance-principal pull on rehearsal; rehearsal's identity trying to read releases or write candidates. | R33, R39 | pull ✓; refused | REH |
| S36 | A measured pull on rehearsal within `pull_timeout`; in CI, a throttled pull beyond it. | R35 | REH: within; CI: O1 | REH + CI |
| S37 | A deploy waits on the lock held by the application's own heavy run (the backup). | R8 | O1, then O16 | REH |
| S38 | A reboot of the rehearsal VM mid-deploy, then rerun. | R9 | from `save-state` on, O1 naming the step reached; before it, the rerun admitted and giving O4 | REH |
| S39 † | TLE's move: the first `turpin deploy` to rehearsal with `--off-level "first turpin deploy"`; then `deploy.sh` at production's previous commit puts rehearsal back. | R41 | O4 + O12; the old compose and image names running, with `/health` | REH |
| S40 | Release copy by the copier with skopeo; another component's credential writing releases. | R33 | O10; O17 | CI (htpasswd per component) |
| S41 | `env create` with secrets at a hidden prompt, then `env destroy`. | R37 | the user, the state folder, `.env` and the project exist, then are gone; hooks called; O18 | CI (pty) |
| S42 | `host-install` on a bare host container, then again. | R38 | `turpin-host`, `jq` and the sudo rule present; then updated | CI; REH |
| S43 | Prune with a mix of candidates, including one built from a commit dated after the newest release but whose `created` label is before it. | R36 | O22; the `created` label decides | CI |
| S44 | A canary secret through every command. | R34 | O18 | CI |
| S45 | The tool contains no application name; a second dummy app runs S1, S6 and S18. | R1, R2, R48 | O19; `build` with `TURPIN_REGISTRY` missing from the dummy app's `APP.env` exits 2, naming the key; so does `turpin-host deploy` on a host whose `.env` lacks it | CI |
| S46 | `status` and `list` on an environment after two deploys. | R40 | the digests, the matched record, the state, host-file equality; the records beside the current one | CI |
| S47 | The board reads `v0.10.2` as released and `prod-*` as history. | R41 | the board scripts' output | CI |
| S48 † | The source of production's level. The stub `ssh` to production returns a host state whose record is 0.10.2, while the last settled record is 0.10.1. A rehearsal's first deploy of the cycle at the last settled record's digests; then at the host-state record's digests. | C13, C14, C31 | O1, with the run log showing the ssh read; then O4 | CI |
| S49 † | Production's host state shows a build with no record. A rehearsal's first deploy by SHA; then the same with `--off-level R`. | C14 | O1 naming the gate; then O4 + O12 | CI |
| S50 † | Emergency where 0.10.1 is made and 0.10.0 is what production runs, production having no `turpin` state, so the stub `/health` reports 0.10.0: a commit cut from `v0.10.1`; then one cut from `v0.10.0`. Then a production with `turpin` state, whose record (read from the stub ssh host state) names a release that is not the newest tag: the same two cuts. | C16, C16a | O1 (it holds `main` commits after the release production runs); O10 + O12; the same results | CI |
| S51 | A parent whose `Refs` is the only evidence: with one work package in the milestone; then with two. | C19 | O1 for both (the work packages are unevidenced), the first naming the parent's count beside it; then each work package referenced, O10 | CI |
| S52 | An emergency (C29 = equal to the emergency's number) where an open issue in the milestone is evidenced by no commit; then where it is evidenced only by a commit on `main` after the tag. | C19, C29 | O1 naming the milestone gate; then O10 + O12, step 6 moves the issue to the next milestone, and `carries` excludes it | CI |
| S53a | The release's commits reference an Application Tooling work package that is in a date milestone, not in milestone VERSION; then a Production Release work package that is not in milestone VERSION. | C19 | O10, the tooling work package neither counted nor carried; then O1 naming the milestone gate | CI |
| S53b | A work package in milestone VERSION with an unticked test box; one with neither heading; all ticked; then `--emergency` with an unticked box. | C32 | O1 naming the tests-passed gate; O1; O10; O10 with the unticked box reported | CI |
| S53 | `--set-aside milestone R`, five cases: (1) the milestone disagrees, no flag; (2) the flag without a reason; (3) the flag where the profile does not list `milestone` in `overridable`; (4) the flag with a reason where it is overridable; (5) the milestone agreeing, no flag. | C22, C19 | O1; O1; O1; O10 + O12, with the record's `set_aside` = `[{"gate":"milestone","reason":R}]` and `carries` the milestone's open items; O10 with `set_aside` empty | CI |
| S54 | `--wait=1` with the lock held beyond the limit; with a hook returning 75 beyond it; with the lock freed within it. | C7, C9, C22 | exit 75, naming the lock, and O1's snapshot shows no change; the same, naming the hook; O16 then O4 | CI |
| S55 | A host file the previous deploy installed and this one drops; then `status`. | C28 | O25 (the dropped file is gone, the others have the payload's mode); `status` is quiet | CI; REH half of S34 |
| S56 | A rollback from a release that added a host file (and the unit it enables) to the previous release's set. | C28, C12 exists | S31's first outcome and O25 (the extra file and unit are gone, the previous set is back) | CI |
| S57 | A first deploy to a bare environment: failing at `migrate`; at `smoke`; at `compose up`; and before `save-state`. Then a fresh deploy of the same REF after the restore. | C11, C12 none, C8 | O24 for the first three; O1 for the last; the fresh deploy is not refused by the state check and gives O4 | CI |
| S58 | A short SHA matching two candidates; then the longer prefix. | C4 ambiguous | O1 naming the gate and the candidates it matched; then O4 | CI |
| S59 | The `post-deploy` check exits 1 after a deploy that is otherwise exit 0; then after one that is otherwise exit 3 (settle failed); then it exits 0. | C30 | the failure reported, exit 0 and exit 3 unchanged, no other mutation; then quiet | CI |
| S60 | Production runs 0.10.1; 0.10.2 is made with #1 #2 #3 and not deployed; 0.10.3 is made with #1 #3 #4. | R42 | the record carries #1 #2 #3 #4, `releases` holds 0.10.2 | CI |
| S61 | As S60, with #2 reverted on `main` between the releases; the release is made, then deployed. | R42, R43 | the record carries #1 #3 #4 and drops #2 with a note at release; settle comments #1 #3 as deployed with 0.10.3, comments #2 and removes it from 0.10.2, closes both milestones; 0.10.2's tag is unchanged | CI |
| S62 | A revert of a commit outside the range; a Production Release work package of the earlier milestone; the settle rerun. | R42, R43 | the revert's own `Refs` count; the work package passes the gate in 0.10.2 and is refused in another; the rerun changes nothing | CI |
| S63 | Reverts by count (a revert of a revert, a third revert, a short sha); production's release unreadable or untagged; a resumed release. | R42 | a revert of a revert keeps the change, three leave it out, a short sha matches; the release is refused at the milestone gate; the record keeps `releases` | CI |
| S64 | An earlier release in the range made before the tool (a text tag) with open items in its milestone; an emergency cut from an undeployed release. | R42, R43 | items named in the range are carried and settled, the others dropped and removed; the emergency lists the release in its range | CI |
| S65 | A feature built, rehearsed, released and deployed to production, with the stub registry enforcing which login each call carries. | R44, R33 | the builder's login pushes, the copier's writes releases and the record, the hosts' pull, no call is made without a login, and the controller's reads carry the controller's | CI |
| S66 | The copier, builder and controller each log in with `turpin login`, in turn, with different users; then a release. A builder with no login made. | R44 | three auth files, each keeping its own user, and the builder's `docker` login made once where an environment on its machine shares it, and not otherwise; no `DOCKER_CONFIG` set; the release works; the build refuses, naming `turpin login builder`; a copier refused by the registry is told to `turpin login copier`; a refused pull on preview names `turpin login builder` | CI |
| S67 | A release with the controller's login absent; then made for the wrong role; then right. A local preview build and deploy with no controller login. | R45 | O1 naming `turpin login controller`; O1 (releases refused to it); O10; the preview deploy needs none | CI |
| S68 | `prune` with the builder on another machine; on the controller's own; a removal attempted with the controller's credential. | R46, R33 | the removal runs on the builder's machine through the Artifacts API with the builder's removal credential, the controller's calls are reads, and the controller's removal is refused | CI |
| S69 | `prune --dry-run`; a remove request whose tag has moved to another digest; one naming a tag already gone; one naming a digest in its `keep` list. | R46 | nothing sent and nothing changed (O1's snapshot); the moved tag is left, which is no error, exit 0; the gone tag is a no-op; the kept digest is refused, left in candidates, an error, exit 3 | CI |
| S70 | `turpin login` with a canary token, for the builder, for a deployer on another machine over `ssh` (the builder's file landing on its own machine), and for preview, which is refused as sharing the builder's login; then with an empty token. | R47, R34 | the canary is in no output, log, argument or file (the `ssh` log too); the auth directory is 0700 and the file 0600; the empty token is refused and writes nothing | CI |
| S71 | Each C33 value, as an argument and, for a version, in the version file; a short commit resolving to one build; then a profile with a required key missing, one with `pull_timeout` not a number and an `APP.env` with a line that does not parse; then a `turpin promote` request whose digest fails its form. | C33; R48 | each bad form refused before any bottom-layer call (the stub records none), and a short commit resolving to none or several after a `list tags` call only: a business error, exit 1, naming where the value came from; each profile fault a fundamental technical error, exit 2, naming the key or the line, before the setting is used; the request an unexpected error, exit 70; the resolving short commit reaches the `Build` as the full SHA | CI (unittest) |
| S72 | Middle layer: the stub's reply, whole but invalid in each way C34 lists; then output not in the tool's format at all. | C34 | an unexpected error each time, never *absent*: the invalid replies found by the middle layer, the malformed output by the bottom; exit 70, the message saying it was not expected and is to be raised as an issue, the cause in the log | CI (unittest) |
| S73 | Middle layer: a manifest unknown on inspect during a build; then for a digest a promote needs. | C34 | *absent*, and the build goes on to build it; then a business error with the digest in its `metadata`, exit 1 | CI (unittest) |
| S74 | Bottom layer: a read answered 503, then success; another meeting a network error, then success. | C35 | two attempts each, the second 2 seconds after the first; the read succeeds; the run log shows the retry and both attempts | CI (unittest) |
| S75 | Bottom layer: a copy answered 429 on every attempt; a read answered 503 on every attempt. | C35 | three attempts each, waiting 2 seconds then 4, each retry logged, then a technical error, a blip, saying to try again later; exit 75 | CI (unittest) |
| S76 | Bottom layer: a read whose authorisation is refused; a `skopeo` call exiting 2 with a network error's text; the argv of every `oci` call the stub records. | C35 | a fundamental technical error after one attempt, naming `turpin login COMPONENT`, exit 2; the `skopeo` exit 2 read as a blip from its text, never *absent*; every `oci` call carries `--no-retry` | CI (unittest) |
| S77 | A delete answered 503, then `NotAuthorizedOrNotFound`, the fresh find finding nothing; then the same with the find finding the image. | C37 | the first counted as removed, exit 0; the second a fundamental technical error naming the builder's policy, the other deletes made, exit 3 | CI (unittest) |
| S78 | A delete answered `NotAuthorizedOrNotFound` on its first attempt. | C37 first | a fundamental technical error naming the builder's policy; not counted as removed; the other deletes made, exit 3 | CI (unittest) |
| S79 | Every failing call of S72 to S78, with the stub's error text holding a registry address, a namespace and an OCID. | C34, C35, C37 | none of the three in the screen output, the run log or any `message`; the log keeps the cause, of domain `oracle`, the tool's text in its `metadata` with them removed | CI (unittest) |
| S80 | A promote failing after the first image, before the record; then the release rerun. | C36 promote | no `VERSION-record` in releases; the rerun copies only the missing images, then pushes the record, exit 0 | CI (unittest) |
| S81 | A remove whose delete fails after its check passed; then `prune` again. | C36 remove | the image left, an error, exit 3; the next `prune` removes it | CI (unittest) |
| S82 | Four deploys to one environment. | C38 | the two oldest folders hold only `meta.json`, each with its whole record; current and previous are whole | CI (bats) |
| S83 | Bottom layer: a read that exceeds the call's timeout on every attempt. | C35 timeout | the call stopped at the timeout and retried as a blip, three attempts, each logged; then a technical error saying to try again later, exit 75 | CI (unittest) |
| S84 | A production deploy whose `settle` fails at one item of three; then `turpin settle VERSION`. | C39 deploy after `finished`, settle one action | O4 and O26: the other two items settled, the message naming `turpin settle VERSION`; then the item settled, exit 0 | CI |
| S85 | A deploy whose `smoke` fails after `compose up` from `pending`; then one whose host prune fails after `finished`; then one whose pull fails before `save-state`. | C39 deploy | O7; O4 and O26, the next deploy's prune removing what was left; exit by type with nothing that runs changed (O1's snapshot of the containers and state) | CI (bats) |
| S86 | A release failing at the GitHub Release, after the tag; a release failing at the `VERSION-record` push, before it. | C39 release | O26: the bump and the next milestone done, the message naming `turpin release`, whose rerun makes the GitHub Release only; then exit by type, no tag, nothing spent | CI |
| S87 | `prune` with three candidates chosen, the second delete answered 503 on every attempt. | C39 prune one delete | O26: the first and third removed, the second left, the message naming `turpin prune` | CI (unittest) |
| S88 | A command stopped by each C40 type: a short `--commit` resolving to no build; authorisation refused; 503 on every attempt; an Oracle reply with an unknown media type. | C40 | exits 1, 2, 75 and 70, each run log's last result `fatal` with that `type`, and `blip` true only for the third | CI (unittest) |
| S89 | A promote's missing digest answered by the registry with a manifest unknown and an error text holding a registry address; a `turpin promote` request with a bad digest; `turpin-host status --json` on a finished deploy. | C41 | the logged result's `cause` is the API error's result, of domain `oracle`, `reason` in upper snake case, its `metadata` the tool's text with the address removed, and no `message` holds tool text or the address; the bad digest's result has one `violations` entry with field, value, limit and reason; the status is one result object, `outcome` ok, the status in `metadata` | CI |
| S90 | A misspelt flag; then a production deploy given SIGINT during its gates, one given SIGINT while `turpin-host deploy` runs `smoke` and one given SIGINT during `settle`; then a `deploy --wait` given SIGINT while the host waits on the lock; then a `rollback` given SIGINT after its first step; then a `prune` given SIGINT after its first delete. | R31, R50: exits 64, 130 | exit 64 naming the flag, nothing run; exit 130, nothing that runs changed (O1's snapshot), the message saying the change is not live and naming `turpin deploy`; the host restores the previous deploy (O7-like), `settle` is not started, exit 130, the message saying the change is not live and naming `turpin deploy`; the action under way finished and no other started, exit 130, the message saying the change is live and naming `turpin settle VERSION`; the host stops waiting, nothing that runs changed, exit 130, the message saying the change is not live and naming `turpin deploy`; the rollback runs to its end, the previous deploy restored and `previous` cleared, exit 0, the message saying the interruption came after the rollback began; the first image removed and no other delete started, exit 130, the message naming `turpin prune` | CI (bats) |
| S91 | A production deploy whose `ssh` connection the stub drops while `turpin-host deploy` runs `smoke`; one whose stub `ssh` refuses the key with exit 255; one whose stub `ssh` fails host key verification; a `turpin-host allowlist` whose stub drops the connection part-way through the list; a `turpin status ENV` whose first `turpin-host status --json` call is dropped. | R31, R50: a lost connection retried where a retry is safe; exit 2 for a refused key or host key | the host restores the previous deploy and records the outcome `interrupted`; `turpin` retries with the same `request_id`, the host runs it, and it finishes, exit 0; exit 2, nothing run on the host, the message naming the key to fix; exit 2, the message naming the `known_hosts` entry; the allowlist unchanged by the dropped call, then retried and merged, exit 0; the call retried and the status shown, exit 0 | CI (bats) |
| S92 | A `turpin status ENV` whose stub `ssh` drops every `turpin-host status --json` call; one whose stub `ssh` hangs past the timeout on every attempt. | R31, R50: exit 75 | three attempts each, waiting 2 seconds then 4, each retry logged with the call's duration, then the message saying to try again later and naming `turpin status ENV` to rerun, exit 75 | CI (bats) |
| S93 | A production deploy whose stub `ssh` drops the connection after the state is marked `finished`; a `rollback` whose stub drops the connection after it took the lock; a rollback with no previous deploy whose stub drops the connection after the host refused; a second deploy of the build already current and finished, with a new `request_id`, whose stub drops the connection before the host takes the lock. | R31, R50 | the retry with the same `request_id` answered from the record, nothing run again, `turpin` carrying on to `settle`, exit 0; the retry waiting on the lock, then answered from the record, the rollback run once, exit 0; the retry answered with the recorded refusal, exit 1, naming the fallback; the retry run, the deploy run once, exit 0 | CI (bats) |
| S94 | A production deploy whose `smoke` refuses, the host restoring, its stub `ssh` dropping the connection once the outcome is recorded; a first deploy to a host whose stub drops the connection after `save-state` and before its pivot; a deploy refused because another request holds a shared lock, then the holder's connection dropped after its pivot; a deploy cut off by a reboot after step 2, `last_request` left `running`, then its repeat; a new deploy after one killed in `preparing`; a deploy under `--check`. | R31, R50 | the retry answered with the recorded refusal, nothing run again, exit 1; the retry run, the outcome `interrupted` before it, the state `failed, no previous deploy` not refusing, exit 0; the refusal writing nothing to `last_request`, the holder's retry answered from its own record, exit 0; the repeat refused, nothing run, naming `turpin status ENV`, exit 1; the new deploy not refused by the state gate, exit 0; `last_request` unchanged | CI (bats) |
| S95 | A deploy whose restore fails, then a new deploy; a deploy killed during step 6, on a host with pruned folders, then a new deploy; a deploy failing during step 6. | C8, R9 | the new deploy refused, naming the step and `turpin rollback ENV`, exit 1; the part-written folder numbered past and every pruned folder's `meta.json` kept, the new deploy giving O4, its prune removing the part-written folder, or cutting it to its `meta.json` where that was written; the failing deploy's folder removed, O1 | CI (bats) |
| S96 | A deploy killed after `save-state` and before `compose up`, then `turpin rollback`; one killed after `compose up` from `pending`, then `turpin rollback`; a rollback killed part-way, then `turpin rollback` again; a first deploy whose restore fails, then a new deploy. | R9, C8 | the first two rollbacks each a restore: `restore-state` run, `current`'s digests running and its host files in place, `current` and `previous` unchanged, `pending` removed, the state `restored`, exit 0; the rollback run again to its end, as S31's first case; the new deploy refused, naming `turpin rollback ENV`, exit 1, then `turpin rollback` running the first deploy's restore again, the state `failed, no previous deploy` | CI (bats) |
| S97 | On a host with a finished deploy, a deploy killed during `save-state`, then `turpin rollback`; on a host with two finished deploys, a deploy failing at `migrate` and restored, then `turpin rollback`; two finished deploys, then six deploys failing at `migrate` and restored, then `turpin rollback`. | R12, R28, R29, C11 `save-state` | `restore-state` given `pending`'s number finding no complete snapshot and restoring nothing, the data as before the deploy, the state `restored`; the rollback's `restore-state` given `current`'s number, restoring the snapshot taken before `current`'s `migrate`, never the restored deploy's; the same after the six, `current`'s snapshot kept by every `save-state`; in each case the stub's log showing `save-state` given `TURPIN_DEPLOY` as `pending`'s number and `TURPIN_CURRENT` as `current`'s | CI (bats), with stub hooks that do what design §8 says; the contract itself, on Tile Lite Elite's real hooks and database, is delphside/tile-lite-elite#555's (part 8) |
| S98 | `turpin rollback` on a bare host that has never deployed. | R57, C8 none | O1: exit 1, naming `[turpin].fallback`, nothing created in the state folder | CI (bats) |
| S99 | A deploy killed in step 6 (state `preparing`) on a host with two finished deploys, then `turpin rollback`; the same on a host with one finished deploy, which has no `previous`. | R57, C8 `preparing`, C12 | case 1: O28, with `restore-state` given `current`'s number and `pending` cleared; case 2: O1 naming the fallback, exit 1, the state still `preparing` | CI (bats) |
| S100 | A rollback killed part-way, then a new deploy; then `turpin rollback`; then the deploy again. | R9, R57, C8 `changing` from a rollback | the deploy refused, naming the step reached and `turpin rollback ENV`, exit 1, O1; the rollback run again to its end, O28; the deploy giving O4 | CI (bats) |
| S101 | A rollback whose `restore-state` exits 1 at its second step, not killed; then a new deploy; then the cause removed and `turpin rollback` again. | R57, C8 `changing` from a rollback | exit 1; the state left `changing: rollback` at that step, `last_request` `failed`, nothing undone; the deploy refused, naming `turpin rollback ENV`, exit 1, O1; then O28 | CI (bats) |
| S102 | Two finished deploys, then `turpin rollback`, then `turpin rollback` again, then a new deploy. | R57, C8 `restored`, C12 | O28; then O1 naming the fallback, exit 1, since the first rollback cleared `previous`, the state still `restored`; then O4 | CI (bats) |
| S103 | A first deploy to a bare environment failing at `migrate` (S57), then `turpin rollback`. | R57, C8 `failed, no previous deploy` | O1 naming the fallback, exit 1, the state still `failed, no previous deploy` | CI (bats) |
| S104 | A deploy on a host with a `current` failing at `migrate`, its restore failing too (the stub `restore-state` exits 1 once); then a new deploy; then `turpin rollback`. | R57, C8 `failed: the restore did not complete` | the state `failed: the restore did not complete`, `pending` and `target` kept; the deploy refused, naming `turpin rollback ENV`, exit 1; the restore run again: `restore-state` given `pending`'s number, `current`'s host files and digests in place, `pending` and `target` cleared, the state `restored`, `current` and `previous` unchanged, exit 0 | CI (bats) |
| S105 | A deploy whose host prune fails after the pivot, the stub `ssh` dropping the connection once the exit 3 is recorded; the repeat under the same `request_id`, the deploy being to production. | R58, C42 `finished` with exit 3 | the repeat answered with exit 3, O27: no second prune, no step run; `turpin` goes on to `settle`, once, as if the first answer had arrived, the exit staying 3 | CI (bats) |
| S106 | Case 1: a deploy whose `migrate` fails and whose restore succeeds, the stub `ssh` dropping the connection once the outcome is recorded; the repeat. Case 2: S101's failed rollback, the connection dropped the same way; the repeat. | R58, C42 `failed` | the outcome `failed`; the repeat answered with the recorded result, exit 1 naming the hook, O27, `restore-state` not called again; case 2 the same, with the rollback's recorded result | CI (bats) |
| S107 | A rollback cut off by a reboot after it took the lock, `last_request` left `running`; then its repeat. | R58, C42 `running` | the repeat refused, nothing run, exit 1, naming `turpin status ENV`, `last_request` left `running` as found (O27's snapshot) | CI (bats) |
| S108 | Case 1: a repeat of a deploy while the original holds the lock, under `--wait=1`. Case 2: a deploy whose `pre-deploy` exits 75, without `--wait`, then its repeat with the hook still answering 75, then its repeat with the hook answering 0. | R58, R8, C43 | case 1: exit 75 at the limit, naming the lock, nothing changed (O1's snapshot); case 2: exit 75 at once, the hook not waited for, nothing changed (O1's snapshot) and `last_request` `interrupted`; the repeat run again, not answered from the record, again exit 75 at once; the last repeat run again to O4. The default of 60 minutes is asserted only by review (X7) | CI (bats) |
| S109 | A request sent straight to `turpin-host deploy` with `request_id` `not-a-uuid`; one with a version 1 UUID; then one with a version 4 UUID. | R48, R58, C42 not a version 4 UUID | exit 70 each time, the message saying it was not expected and is to be raised as an issue, nothing run, the lock never taken (the stub `flock` log is empty) and `last_request` unchanged; then O4 | CI (bats) |
| S110 | An interruption on the host. Case 1: a deploy A holds the lock through a slow `migrate`; a second deploy B, with `--wait`, waits for it and is given SIGINT. Case 2: a deploy holding its own lock whose `pre-deploy` answers 75 under `--wait`, given SIGINT between two retries. Case 3: a hook that reads its input. Case 4: a rollback waiting for the lock, which a deploy holds, given SIGINT. Case 5: a rollback holding the lock, given SIGINT (S90's rollback). Case 6: after the cases, an `interrupted.PID` planted by a killed request, then a deploy. | R59, C46 | case 1: B's `interrupted.PID` written when its input ends, B stopping at its next one-second wait, never taking the lock, exit 130; A runs to O4, unaffected; case 2: the host stopping at its next look, the hook not run again, nothing changed (O1's snapshot), exit 130; case 3: the hook reads end of file at once and receives none of the request line; case 4: the rollback stops at its next wait, exit 130, the deploy running to O4; case 5: the rollback runs to its end, O28, as S90's rollback says; case 6: every `interrupted.PID` of an exited request is gone (the trap), the planted file never read, the deploy giving O4 | CI (bats) |
| S111 | A build, with `TURPIN_CREATED` an RFC 3339 UTC time. Case 1: a hook writing layouts with all three labels as set. Case 2: the default hook, with no `build` hook in the profile, and again under `--local`. Case 3: a multi-arch layout whose index holds two platform images, each labelled, and an attestation manifest with no labels. Case 4: the same with one platform image's `revision` another SHA. Case 5: a hook whose layout has `version` not the version file; one whose `created` is not `TURPIN_CREATED`. | R3, R29, C44 | case 1: O2, with `created` equal on both images and equal to the `TURPIN_CREATED` the hook logged; case 2: the same, the labels set by the `bake` call's `--set IMAGE.labels...` arguments (the stub's log), and the loaded images carrying them under `--local`; case 3: O2, the attestation manifest passed over, not refused; cases 4 and 5: exit 1 naming the image and the label, nothing pushed (the registry log empty) | CI (unittest) |
| S112 | A state folder holding the Bash `turpin`'s `state` file and no `state.json`; the same with a `current` link; then the folder cleared by hand. Each tried with `turpin-host deploy`, `rollback`, `status` and `allowlist`. | R60 | exit 2 for each request, naming the file or link, nothing changed (O1's snapshot); then the deploy giving O4 | CI (bats) |
| S113 | A deploy to rehearsal over ssh, where `pre-deploy` passes; then one where it refuses; then one with `--set-aside pre-deploy R`. | R61, R31 | O29: the controller's run log names each host gate with `passed`, `refused` and `set-aside`; the operator's stderr holds no `@gate` line | CI (bats) |
| S114 | A release whose stub `gh` read fails with a connection error; with a timeout; with 429; with a 503; with authorisation refused; with a `ProfileError` from a malformed profile key; with an unexpected exception. | R62, C45 | exit 75 for the first four, naming the read, the gate neither refused nor passed and nothing changed (O1's snapshot); exit 2 for the authorisation and the `ProfileError`; exit 70 for the last | CI (unittest) |
| S115 | A release given SIGINT to `turpin`'s process group while its stub `gh` read is running. | R63, R62, C45 | the stub `gh` is in a process group other than `turpin`'s, is not signalled, and runs to its end; `turpin` then stops before the pivot, exit 130, nothing changed (O1's snapshot) | CI (unittest) |
| S116 | On a host with a `current`, a deploy killed after `save-state` (state `changing: deploy`), then `turpin rollback` whose `restore-state` exits 1; the failed rollback's repeat under its `request_id`; then a new deploy; then the cause removed and `turpin rollback` again. | R57, R58, C8 `changing: deploy`, C42 `failed` | exit 1; the state `failed: the restore did not complete`, `pending` and `target` kept, `last_request` `failed`; the repeat answered with its recorded result, O27; the deploy refused, naming `turpin rollback ENV`, exit 1; then the restore run again, `restore-state` given `pending`'s number, the state `restored`, exit 0 | CI (bats) |
| S117 | Two commits whose `web` image has one digest, one of them pruned; then both pruned in one `prune`. | R46 | the first: the image is left, which is no error, the other commit's tag still in candidates and named in the run log; the second: the image is removed with both tags, exit 0 | CI (unittest) |
| S118 | A deploy to rehearsal: the hooks' environments. Case 1: `save-state`, `migrate` and `smoke` are given `TURPIN_DEPLOY`, `TURPIN_DEPLOY_DIR` and `TURPIN_COMPOSE`; `pre-deploy` none; `TURPIN_CURRENT` only on `save-state`. Case 2: a `migrate` hook that runs `eval "$TURPIN_COMPOSE config"`. Case 3: a rollback's `restore-state`. | R64 | Case 2: Compose is run with the project and compose files of the deploy's own `compose up`. Case 3: the undone deploy's number and folder. | CI |
| S119 | `turpin-host compose` on a host with a `current`; with none; with `current` removed from the record; with the environment's lock held by another process. | R65 | runs Compose with the deploy's project and compose files; refuses naming no current deploy, exit 1; refuses for the lock, running nothing | CI |
| S120 | A deploy to an environment with a `url`, then one with none; the controller's `post-deploy`. | R66 | every hook is told `TURPIN_URL`, empty for none | CI |
| S121 | A profile whose production names no `ssh` and has `[hosts.production].ssh`; one that names both; one that names neither; a `[hosts]` entry of another name. | R67 | the hosts alias; the environment's own; refused naming the key; refused | CI |
| S122 | A first deploy to a host that runs the old server and has hand-installed files. Case 1: `migrate` fails. Case 2: `compose up` fails, one file hand-installed, one not. Case 3: the host-file step fails before any file is installed. | R68, R12 | Case 1: the files untouched, the stopped server started again, no `compose down`. Case 2: the hand-installed file stays, the other is removed, `compose down` runs. Case 3: every file stays, the server runs, no `compose down` | CI |
| S123 | A build with `[turpin.build].args` naming `SHORT_SHA`, `SHA` and `VERSION`; one naming another source; none. | R69 | each image's bake is given the arguments, under `--local` too; refused naming the key; none passed | CI |
| S124 | A release where production has no `turpin` state, `/health` reporting `0.10.0+SHA`; with two tags of one version, `/health` naming the commit of the second; with the host's record naming it; with no commit reported; with `/health` unreadable. | R70, R17, R42 | the range starts at the tag of the release `/health` names, not refused; the tag naming the commit; the release prefix's; refused | CI |
| S125 | A release with an open issue in the milestone that no commit names. Case 1: `--expect`. Case 2: `--expect --confirm N`. Case 3: no `--expect`, the answer `y`; then `n`, empty and end of input. Case 4: a parent in the milestone; `--set-aside milestone`; `--confirm` for an issue a commit names. | R71, R20 | Case 1: refused naming it. Case 2: released, the record's `carries.confirmed` holding N and `issues` too. Case 3: asked once per issue; released, or refused naming it, with nothing changed. Case 4: no question; carried as it stands; a note | CI |
| S126 | A commit moving the `programme` pin over a programme commit that changes only documents; one changing `scripts/deliver/payload/`; one changing `scripts/deliver/lib/`; a pin that cannot be compared; the same with a shipping path in the commit. | R72 | does not reach the image; reaches it; reaches it; reaches it; reaches it by the path | CI |
| S127 | `turpin host-install` for an environment on an empty host; again with an existing `.env` of other content and mode; for a copier. | R73 | the folder 0700 and an empty `.env` 0600; the `.env` unchanged; neither | CI |
| S128 | A build of a commit whose profile has board keys, `environments` and `versions` as well as the host's keys. | R74 | the payload's `profile.json` holds only the keys a host reads | CI |

## 6. Refusals and successes

| gate (design §9) | refusal | then success | kind |
| --- | --- | --- | --- |
| build: clean worktree of a commit on the remote | unpushed commit → O1 (S1) | pushed → O2 | CI |
| build: never overwritten | registry query fails → O1 (S3) | query answers → O3 for present images, O2 for missing ones | CI |
| deploy: by digest, revision label, `RepoDigests` | label ≠ SHA → O1 (S8) | true image → O4 | CI |
| deploy: lock | held → O1 (S9) | freed → O4; `--wait` → O16 | CI; REH S37 |
| deploy: killed or rebooted, not built upon | state shows a step → O1 (S13); a rollback left part-way (S100); a restore that failed (S95) | after rollback, deploy → O4 | CI; REH S38 |
| rollback: there is a deploy to go back to | none, a first deploy's failure, a second rollback, or a `previous` absent → O1 naming the fallback (S98, S99 case 2, S102, S103; S31) | `previous` present → O28 (S31, S99 case 1) | CI |
| deploy and rollback: a failed restore | a new deploy → O1, exit 1, naming `turpin rollback ENV` (S95, S104, S116) | the restore again → the state `restored` (S104, S116); `failed, no previous deploy` for a first deploy's (S96's first deploy) | CI |
| deploy and rollback: a repeat of a request left `running` | the repeat → O1, exit 1, naming `turpin status ENV` (S94 case 4, S107) | once the owner has judged with `status`, a new command (a new `request_id`) runs under the state table (S94's new deploy) | CI |
| deploy: `pre-deploy` | exit 1 or 75 → O1 (S10) | exit 0 → O4; `--set-aside` where overridable → O4 + O12 | CI |
| deploy: failure keeps the previous running | `migrate`/`smoke` fails → O7 (S14) | both pass → O4 | CI; REH S33 |
| rehearsal deploy: starts at production's level † | first deploy ≠ production's record, or production runs a build with no record → O1 (S17, S48, S49) | production's record from its host state → O4; `--off-level` → O4 + O12 | CI; REH S39 |
| deploy: a short SHA is unambiguous | matches two candidates → O1 (S58) | longer prefix → O4 | CI |
| deploy: `--wait` is bounded | beyond the limit → O1 (S54) | within it → O16 | CI |
| deploy: a first deploy's failure | no `previous` → O24 (S57) | — (a failure case, not a gate) | CI |
| release: rehearsal passed | another commit, smoke failed, or unfinished → O1 (S18) | passed and confirmed → O10; `--skip-rehearsal` → O10 + O12 + O13 | CI |
| release: commit on `origin/main` | not on `main` → O1 (S20) | on `main` → O10; `--emergency` → O10 + O12 | CI |
| release: emergency ships nothing unreleased | holds a post-tag `main` commit, or does not descend from the release production runs → O1 (S20, S50) | clean cut from that tag → O10 | CI |
| release: CI passed | a check failing or missing → O1 (S21) | green → O10 | CI |
| release: version spent once and forward | tag, record, or not higher → O1 (S22) | new and higher → O10 | CI |
| release: tests passed | a work package with an unticked box, or with neither heading → O1 (S53b) | all ticked → O10; `--emergency` with an unticked box → O10, the box reported (S53b) | CI |
| release: milestone shipping list | uncarried issue, or work package outside → O1 (S23); a parent's `Refs` with one or two work packages → O1 (S51), the first naming the parent's count beside it | moved, then rerun → O10; each work package referenced → O10 (S51); emergency with an issue evidenced on `main` → O10 (S52); `--set-aside milestone R` → O10 (S53) | CI |
| release: `release-check` | exit 1 → O1 (S24) | exit 0 → O10; `--set-aside` → O10 + O12 | CI |
| release: the owner's confirmation (§6) | wrong version typed → O1 (S25) | right → O10 | CI |
| production deploy: a record exists | no record → O1 (S29) | recorded version → O4; `--unrecorded` → O4 + O12 | CI only; real: the owner's `--check` runs and 0.10.2's first production deploy (part 8) |
| after a production deploy: settle (check) | `gh` fails → O15 (S30) | rerun → O14 | CI only; real: 0.10.2's post-deployment check |
| `post-deploy` (check) | exit non-zero → reported, exit unchanged (S59) | exit 0 → quiet | CI |
| build: the image's labels are the commit's | `revision`, `version` or `created` differs in a layout → O1, nothing pushed (S111) | all three true → O2 | CI |
| deploy and rollback: the state folder is this tool's | `state` file or `current` link without `state.json` → O1's snapshot, exit 2, naming it, for `deploy`, `rollback`, `status` and `allowlist` (S112) | cleared by hand → O4 | CI |
| any gate that reads the board or git: the read can be made | cannot be made → 75 for a blip, 2 otherwise, never refused nor empty (S114) | made → the gate answers | CI |
| any time: host files dropped by a release | a dropped file left on the host (not provokable from outside; S55's O25 assertion is the evidence) | removed → O25 (S55) | CI; REH half of S34 |
| any time: host files (check) | edited file → O9 report (S15) | restored → quiet | CI; REH S34 |
| required hook present (§8) | missing or not executable → O1 (S11) | present → O4 | CI |
| gate count (§6) | not provokable from outside (X9b) | O23 on every run | CI |
| `state.json` written whole by rename | not provokable from outside (X9c): a kill falls between two writes, never inside one | S13, S94 and S96 find a whole record after a kill | CI, reviewed |

## 7. Coverage, both ways

| rule | scenarios |
| --- | --- |
| R1 | S45 |
| R2 | S45 |
| R3 | S1, S2, S4, S5, S111 |
| R4 | S1, S3, S40 |
| R5 | S6, S7, S44 |
| R6 | S6, S7, S29, S58 |
| R7 | S5, S8 |
| R8 | S9, S10, S37, S54, S108 |
| R9 | S13, S38, S57, S95, S96, S100 |
| R10 | S10, S12, S53 |
| R11 | S6 |
| R12 | S14, S33, S57, S85, S97, S122 |
| R13 | S15, S34, S55, S56 |
| R14 | S16 |
| R15 † | S17, S39, S48, S49 |
| R16 | S18, S19, S25 |
| R17 † | S20, S50, S52, S124 |
| R18 | S21 |
| R19 | S22 |
| R20 | S23, S51, S52, S53, S53a, S125 |
| R20a | S53b |
| R21 | S24 |
| R22 | S26, S86 |
| R23 | S26, S28 |
| R24 | S27 |
| R25 | S18 |
| R26 | S29 |
| R27 | S29, S30, S84 |
| R28 | S31, S56, S97, S102 |
| R29 | S6, S10, S11, S33, S57, S59, S97, S111 |
| R30 | S12, S17, S19, S20, S29, S49, S53 |
| R31 | S32, S59, S88, S90, S91, S92, S93, S94, S113 |
| R32 | S32 |
| R33 | S35, S40, S65, S68 |
| R34 | S41, S44, S70 |
| R35 | S36 |
| R36 | S43, S68 |
| R37 | S41 |
| R38 | S42 |
| R39 | S35 |
| R42 | S60, S61, S62, S63, S64, S124 |
| R43 | S61, S62, S64 |
| R40 | S46 |
| R41 | S39, S47 |
| R44 | S65, S66 |
| R45 | S65, S67 |
| R46 | S68, S69, S87, S117 |
| R47 | S70 |
| R48 | S45, S71, S89, S109 |
| R49 | S72, S73 |
| R50 | S75, S76, S79, S88, S90, S91, S92, S93, S94 |
| R51 | S74, S75, S76, S83 |
| R52 | S80, S81 |
| R53 | S77, S78 |
| R54 | S82 |
| R55 | S84, S85, S86, S87 |
| R56 | S79, S89 |
| R57 | S31, S96, S97, S98, S99, S100, S101, S102, S103, S104, S116 |
| R58 | S93, S94, S105, S106, S107, S108, S109, S116 |
| R59 | S90, S110 |
| R60 | S112 |
| R61 | S113 |
| R62 | S114, S115 |
| R63 | S115 |
| R64 | S118 |
| R65 | S119 |
| R66 | S120 |
| R67 | S121 |
| R68 | S122 |
| R69 | S123 |
| R70 | S124 |
| R71 | S125 |
| R72 | S126 |
| R73 | S127 |
| R74 | S128 |

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
| S17 † | R15, R30 |
| S18 | R16, R25 |
| S19 | R16, R30 |
| S20 † | R17, R30 |
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
| S31 | R28, R57 |
| S32 | R31, R32 |
| S33 | R12, R29 |
| S34 | R13 |
| S35 | R33, R39 |
| S36 | R35 |
| S37 | R8 |
| S38 | R9 |
| S39 † | R15, R41 |
| S40 | R4, R33 |
| S41 | R34, R37 |
| S42 | R38 |
| S43 | R36 |
| S44 | R5, R34 |
| S45 | R1, R2, R48 |
| S46 | R40 |
| S47 | R41 |
| S48 † | R15 |
| S49 † | R15, R30 |
| S50 † | R17 |
| S51 | R20 |
| S52 | R20, R17 |
| S53 | R20, R30, R10 |
| S53a | R20 |
| S53b | R20a |
| S54 | R8 |
| S55 | R13 |
| S56 | R28, R13 |
| S57 | R12, R9, R29 |
| S58 | R6 |
| S59 | R29, R31 |
| S60 | R42 |
| S61 | R42, R43 |
| S62 | R42, R43 |
| S63 | R42 |
| S64 | R42, R43 |
| S65 | R33, R44, R45 |
| S66 | R44 |
| S67 | R45 |
| S68 | R33, R36, R46 |
| S69 | R46 |
| S70 | R34, R47 |
| S71 | R48 |
| S72 | R49 |
| S73 | R49 |
| S74 | R51 |
| S75 | R50, R51 |
| S76 | R50, R51 |
| S77 | R53 |
| S78 | R53 |
| S79 | R50, R56 |
| S80 | R52 |
| S81 | R52 |
| S82 | R54 |
| S83 | R51 |
| S84 | R27, R55 |
| S85 | R12, R55 |
| S86 | R22, R55 |
| S87 | R46, R55 |
| S88 | R31, R50 |
| S89 | R48, R56 |
| S90 | R31, R50, R59 |
| S91 | R31, R50 |
| S92 | R31, R50 |
| S93 | R31, R50, R58 |
| S94 | R31, R50, R58 |
| S95 | R9 |
| S96 | R9, R57 |
| S97 | R12, R28, R29, R57 |
| S98 | R57 |
| S99 | R57 |
| S100 | R9, R57 |
| S101 | R57 |
| S102 | R28, R57 |
| S103 | R57 |
| S104 | R57 |
| S105 | R58 |
| S106 | R58 |
| S107 | R58 |
| S108 | R8, R58 |
| S109 | R48, R58 |
| S110 | R59 |
| S111 | R3, R29 |
| S112 | R60 |
| S113 | R31, R61 |
| S114 | R62 |
| S115 | R62, R63 |
| S116 | R57, R58 |
| S117 | R46 |
| S118 | R64 |
| S119 | R65 |
| S120 | R66 |
| S121 | R67 |
| S122 | R68, R12 |
| S123 | R69 |
| S124 | R70, R17, R42 |
| S125 | R71, R20 |
| S126 | R72 |
| S127 | R73 |
| S128 | R74 |

## 8. Approach

**CI.** Every test builds its own world and leaves nothing behind. That world is:

- a temp git repository with a bare remote, and a version file;
- a dummy application, "acme", with two images, `payload_image`, a `required_hooks` list and a second environment `join`;
- stub hooks that log their argv and environment and exit as each test sets;
- `registry:2` as a CI service. For S40 it runs with an htpasswd user per component and a proxy that refuses writes outside each component's repositories;
- a "host" container reached through a stub `ssh` that runs `turpin-host` inside it, with Docker-in-Docker for compose, `RepoDigests` and pulls;
- stub `systemctl` and `sudo` inside the host container;
- a stub `gh` that answers checks, milestones and issues (one fixture, in REST's shape) from files and logs every mutation. It refuses GraphQL, as a cloud session's token is refused, except the three calls that set an issue field, so the board model's REST route is the one these tests drive; its GraphQL route is read in `scripts/board/tests/test_release_sources.py`.

S13 kills the run with a hook that sends SIGKILL to its parent. S90's interruption is SIGINT sent to the `turpin` process's group, as Ctrl+C at a terminal sends it; the stub `ssh` passes standard input through, so a call sees its input close. `pull_timeout` is tested through a throttling proxy, and time is not otherwise manipulated. Confirmation prompts and hidden prompts run under a pty. Each gate's test is first shown to fail by disabling the reason, as docs/1.9 requires. Each check's test includes its quiet case.

**[REH].** Claude runs S33 to S39 and the real halves of S14, S15, S42 and S55 on Tile Lite Elite's rehearsal VM. The real half of S97 is delphside/tile-lite-elite#555's, run with its keyed hooks. They use the real OCI registry, instance-principal login, systemd and TLE's own hooks, and they run before the merge (docs/1.9 *What tests the tooling*).

**Production role.** The production-role gates (S29, S30, and R26 and R27 generally) are tested in CI only. On a real host they are shown by the owner's `--check` runs and by 0.10.2's first production deploy, post-deployment checks against #555 and #556. Production access is the owner's to run, so each of these is a check the owner runs, and Claude works from what comes back:

- **owner** — `turpin deploy production <raw SHA> --check` refuses, naming the production record gate, and changes nothing (R32, R26). Run it before the deploy;
- **owner** — `turpin deploy production <an unrecorded version> --check` refuses, naming the same gate, and changes nothing (R32, R26). Run it before the deploy;
- **Claude** — read the deploy log of 0.10.2's first production deploy: it names the version and digests;
- **Claude** — read the board after settle: it moved exactly the record's work packages;
- **owner** — run `turpin status production` (a production read): it matches the record.

The refusal is shown first and the successful deploy follows, as the other gates do. These checks match the post-deployment box of delphside/tile-lite-elite#555. Work package #555's test-approach box "exercised against rehearsal standing in for production" is replaced by the CI tests and these checks.

### Only a real host can show

- instance-principal login and the OCI IAM split;
- the pull time, measured by delphside/tile-lite-elite#555's first deploy, and the 1 GB footprint, including the OCI CLI's peak (#554);
- systemd units really enabled;
- the state surviving a reboot;
- the lock shared with the backup;
- TLE's database snapshot, restore and migration;
- the snapshot contract on Tile Lite Elite's real hooks and database (design
  §8): `save-state` keys the snapshot to `TURPIN_DEPLOY`, marks it complete and
  keeps `TURPIN_CURRENT`'s, and `restore-state` restores nothing without a
  complete one. S97's first two cases are run against the real hooks. The real
  keyed hooks are written in delphside/tile-lite-elite#555, which owns the test;
  CI's S97 uses stub hooks that do what the contract says;
- the `deploy.sh` fallback.

Everything else runs in CI.

## 9. Test names

A test of what `turpin` decides is a `unittest` test; one of what a host does (`turpin-host` and the payload's deploy steps) is a Bats test.

### Build

- `build_refuses_an_image_whose_labels_differ_and_pushes_nothing` (S111)
- `build_gives_every_image_the_same_created_label` (S111)
- `the_default_hook_sets_the_labels_by_bake_and_under_load` (S111)
- `build_passes_over_an_attestation_manifest_and_checks_each_platform_image` (S111)
- `build_refuses_a_commit_not_on_the_remote`
- `build_ignores_the_operators_dirty_tree`
- `build_labels_revision_and_version`
- `build_pushes_each_image_as_sha_dash_image`
- `build_never_pushes_over_an_image_already_stored`
- `build_refuses_when_the_registry_cannot_be_queried`
- `build_without_a_hook_bakes_oci_layouts_or_loads_them_under_local`
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
- `killed_deploy_is_refused_until_rolled_back`
- `failed_migrate_restores_state_previous_images_and_host_files`
- `failed_smoke_restores_state_previous_images_and_host_files`
- `host_files_installed_with_modes_and_units_enabled`
- `status_reports_a_host_file_that_differs`
- `host_keeps_only_current_and_previous_images`
- `rehearsal_cycle_must_start_from_productions_record` †
- `off_level_override_is_recorded`
- `rehearsal_level_is_read_from_production_host_state_over_ssh` †
- `rehearsal_first_deploy_refuses_when_production_runs_a_build_with_no_record` †
- `deploy_wait_gives_up_at_the_limit_and_refuses`
- `dropped_host_file_is_removed`
- `rollback_removes_the_current_releases_extra_host_files`
- `first_deploy_failing_after_save_state_restores_and_names_the_fallback`
- `first_deploy_failing_before_save_state_changes_nothing`
- `deploy_after_a_failed_first_deploy_proceeds`
- `ambiguous_short_sha_refuses`
- `post_deploy_check_failure_is_reported_and_leaves_the_exit_code`

### Hooks, `compose`, adopted hosts and the payload

- `every_hook_from_step_7_on_is_told_its_deploy_its_folder_and_the_compose_command_the_deploy_runs` (S118, T1)
- `a_hook_running_turpin_compose_runs_compose_as_the_deploy_does` (S118)
- `rollbacks_restore_state_is_told_the_deploy_it_undoes_with_that_deploys_compose_command` (S118)
- `a_hook_is_told_its_environments_url_and_empty_where_it_has_none` (S120, T3)
- `turpin_host_compose_runs_compose_against_currents_folder_as_the_deploy_does` (S119, T2)
- `turpin_host_compose_refuses_where_there_is_no_current_deploy` (S119)
- `turpin_host_compose_refuses_while_the_environments_lock_is_held` (S119)
- `an_environment_with_no_ssh_alias_takes_the_one_in_hosts` (S121, T4)
- `build_arguments_name_a_turpin_value_each` (S123, T5)
- `the_default_hook_passes_the_profiles_build_arguments_taken_from_turpin_values` (S123)
- `a_first_deploy_failing_before_the_host_files_leaves_the_hand_installed_files_and_starts_the_stopped_server_again` (S122, T7)
- `a_first_deploy_failing_after_the_host_files_keeps_what_was_there_and_removes_only_what_it_added` (S122)
- `a_failure_at_the_host_files_before_any_is_installed_leaves_every_file_there` (S122)
- `a_release_reads_health_where_production_has_no_turpin_state_and_does_not_refuse` (S124, T10)
- `two_tags_of_one_version_the_one_naming_the_commit_health_reports_is_taken` (S124)
- `two_tags_of_one_version_the_one_naming_the_hosts_record_commit_is_taken` (S124)
- `two_tags_of_one_version_with_no_commit_to_go_by_take_the_release_prefix` (S124)
- `an_unconfirmed_issue_refuses_naming_it_and_asks_nobody_under_expect` (S125, T9)
- `confirm_answers_the_question_without_a_terminal_and_the_record_keeps_it` (S125)
- `without_expect_each_unconfirmed_issue_is_asked_about_and_yes_confirms_it` (S125)
- `without_expect_anything_but_yes_leaves_the_issue_unconfirmed_and_refuses` (S125)
- `an_issue_no_commit_names_is_a_question_a_confirmation_answers` (the board model, S125)
- `a_parent_is_never_asked_about` (the board model, S125)
- `set_aside_still_carries_the_milestone_as_it_stands` (the board model, S125)
- `a_pin_move_changing_only_documents_ships_nothing`, `a_pin_move_changing_the_payload_ships`, `a_pin_move_changing_the_libraries_ships` (S126, T6)
- `an_environment_gets_its_state_folder_for_the_deploy_user_and_an_empty_env` (S127, T11)
- `a_rerun_never_overwrites_an_existing_env` (S127)
- `the_payload_carries_only_the_profile_keys_a_host_reads` (S128, T6)

### Release

- `release_refuses_a_commit_rehearsal_did_not_pass`
- `skip_rehearsal_records_reason_and_raises_retrospective`
- `release_refuses_a_commit_not_on_main`
- `emergency_must_descend_from_the_release_production_runs`
- `emergency_cut_from_the_release_production_runs_passes_when_a_newer_tag_exists`
- `emergency_refuses_a_commit_carrying_unreleased_main`
- `release_refuses_while_a_required_check_is_not_green`
- `release_refuses_a_spent_or_lower_version`
- `release_refuses_a_milestone_that_disagrees_with_the_commits`
- `a parent's Refs is shown beside its only work package and never counted for it`
- `parent_refs_does_not_count_with_two_work_packages`
- `an unticked test box refuses the release; an emergency reports it; ticked, it is made`
- `the tests-passed gate is a check under --emergency: the release is made and says what was not ticked`
- `emergency_leaves_out_issues_evidenced_only_on_main_and_moves_them`
- `set_aside_milestone_needs_a_reason_and_an_overridable_profile`
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
- `settle_advances_a_carried_work_package_of_any_route`
- `settle_failure_exits_3_and_the_deploy_stands`
- `settle_rerun_changes_nothing`
- `rollback_without_a_previous_deploy_names_the_fallback`

### Range and carried releases

- `a release made while an earlier one is undeployed carries both`
- `a Production Release work package of an earlier release in the range passes the gate; elsewhere it refuses`
- `deploying it settles both, closes both milestones; a rerun changes nothing`
- `the owner's scenario: #2 reverted between the releases is not carried, is removed from 0.10.2 and its state left alone`
- `a revert of a commit outside the range has no effect`
- `a revert of a revert keeps the change`, `three reverts leave the change out`, `a revert naming the commit by a short sha is matched`
- `production's release unreadable, or without a tag, refuses the release`
- `a rerun that resumes the release keeps carries.releases`
- `a release made before the tool, in the range, has its milestone's open items gated, settled and closed`
- `an emergency range still starts at production's tag, and lists a release made in it`

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

### Registry adapter

- `a_bad_value_is_refused_before_any_call_and_a_short_sha_resolves_first`
- `an_invalid_oracle_reply_is_unexpected_and_found_in_the_middle_layer`
- `manifest_unknown_is_absent_on_a_read_and_a_business_error_where_needed`
- `a_503_then_success_is_retried_and_logged`
- `429_or_503_three_times_runs_out_as_a_technical_error`
- `a_call_past_its_timeout_is_retried_then_technical`
- `a_refused_authorisation_is_never_retried_and_oci_calls_carry_no_retry`
- `not_authorized_or_not_found_after_a_5xx_is_removed_only_if_the_image_is_gone`
- `not_authorized_or_not_found_on_a_first_delete_names_the_policy`
- `no_registry_address_namespace_or_ocid_in_any_error`
- `a_promote_failing_before_the_record_leaves_none_and_resumes`
- `a_remove_failing_after_its_check_is_retried_by_the_next_prune`

### Host state, interruption and repeated requests

Bats tests, in `scripts/tests/turpin-*.bats`.

- `a_pruned_deploy_folder_keeps_only_its_meta_json` (S82)
- `a_misspelt_flag_exits_64_naming_it_and_runs_nothing` (S90)
- `sigint_during_the_gates_changes_nothing_and_says_the_change_is_not_live` (S90)
- `sigint_before_the_pivot_restores_and_says_the_change_is_not_live` (S90)
- `sigint_during_settle_finishes_the_action_and_says_the_change_is_live` (S90)
- `sigint_while_the_host_waits_for_the_lock_changes_nothing` (S90)
- `sigint_during_a_rollback_lets_it_run_to_its_end` (S90)
- `sigint_during_prune_finishes_the_delete_and_starts_no_other` (S90)
- `a_dropped_connection_is_retried_under_the_same_request_id` (S91)
- `a_refused_key_or_host_key_exits_2_naming_the_fix` (S91)
- `a_dropped_allowlist_or_status_call_is_retried_and_merged_once` (S91)
- `a_status_call_that_keeps_failing_exits_75_naming_the_rerun` (S92)
- `a_repeat_after_the_pivot_is_answered_from_the_record` (S93)
- `a_repeat_of_a_rollback_waits_for_the_lock_then_is_answered` (S93)
- `a_repeat_of_a_refused_rollback_gets_the_recorded_refusal` (S93)
- `a_new_request_id_for_the_current_build_runs_as_new` (S93)
- `a_repeat_of_a_refused_deploy_gets_the_recorded_refusal` (S94)
- `a_repeat_of_an_interrupted_first_deploy_runs_again` (S94)
- `a_request_refused_for_the_lock_writes_nothing_to_last_request` (S94)
- `a_repeat_of_a_request_left_running_is_refused_naming_status` (S94)
- `a_new_deploy_after_a_kill_in_preparing_runs` (S94)
- `check_mode_leaves_last_request_alone` (S94)
- `a_failed_restore_refuses_the_next_deploy_naming_rollback` (S95)
- `a_kill_in_step_6_leaves_a_folder_the_next_deploy_numbers_past` (S95)
- `a_failure_in_step_6_removes_its_folder` (S95)
- `rollback_restores_a_deploy_killed_before_or_after_compose_up` (S96)
- `a_rollback_killed_part_way_is_run_again` (S96)
- `rollback_reruns_a_first_deploys_failed_restore` (S96)
- `restore_state_finds_no_complete_snapshot_and_restores_nothing` (S97)
- `rollback_restores_currents_snapshot_never_the_restored_deploys` (S97)
- `save_state_keeps_currents_snapshot_through_six_failed_deploys` (S97)
- `rollback_on_a_bare_host_refuses_naming_the_fallback` (S98)
- `rollback_from_preparing_switches_to_previous_or_refuses_without_one` (S99)
- `a_new_deploy_after_a_rollback_left_part_way_is_refused_naming_rollback` (S100)
- `a_rollback_that_fails_is_run_again_and_blocks_a_deploy_meanwhile` (S101)
- `a_second_rollback_refuses_naming_the_fallback` (S102)
- `rollback_after_a_failed_first_deploy_refuses_naming_the_fallback` (S103)
- `rollback_after_a_failed_restore_runs_the_restore_again_from_current` (S104)
- `a_repeat_of_a_finished_request_whose_prune_failed_is_answered_with_exit_3` (S105)
- `a_repeat_of_a_failed_deploy_or_rollback_gets_the_recorded_result` (S106)
- `a_repeat_of_a_rollback_left_running_is_refused_naming_status` (S107)
- `a_repeat_waiting_for_the_lock_past_the_limit_exits_75` (S108)
- `a_repeat_does_not_wait_for_a_hooks_not_yet_without_wait` (S108)
- `a_request_id_that_is_not_a_version_4_uuid_is_an_unexpected_error` (S109)

- `an_interruption_while_the_host_waits_for_the_lock_stops_at_the_next_wait` (S110)
- `an_interruption_between_hook_retries_stops_at_the_next_look` (S110)
- `a_hook_reading_its_input_gets_end_of_file_at_once` (S110)
- `an_interrupted_request_waiting_for_the_lock_leaves_the_holder_to_finish` (S110)
- `a_rollback_waiting_for_the_lock_stops_and_one_holding_it_runs_to_its_end` (S110)
- `an_interrupted_file_is_removed_on_exit_and_a_stale_one_is_never_read` (S110)
- `a_hook_not_yet_past_the_wait_is_recorded_interrupted_and_its_repeat_runs` (S108)
- `a_rollback_that_runs_a_restore_and_fails_marks_the_restore_incomplete` (S116)
- `a_state_folder_in_the_bash_turpins_layout_is_refused_by_deploy_rollback_status_and_allowlist` (S112)
- `a_host_gate_is_reported_to_the_controllers_run_log_only` (S113)

### Errors, results and the pivot

- `each_error_type_stops_the_run_with_its_own_exit`
- `a_settle_failure_after_a_live_deploy_exits_3_and_names_the_rerun`
- `a_smoke_failure_after_the_switch_still_restores`
- `a_release_failure_after_the_tag_carries_on_and_exits_3`
- `one_failed_delete_in_prune_leaves_the_others_removed_and_exits_3`
- `a_registry_error_nests_its_oracle_cause_in_the_result`
- `a_refused_value_is_listed_in_violations`
- `no_tool_text_or_identifier_reaches_a_message`
- `host_status_json_is_one_result_object`
- `a_board_or_git_read_that_cannot_be_made_exits_75_or_2_never_refused_or_empty` (S114)
- `an_unexpected_exception_in_a_read_exits_70` (S114)
- `a_gh_read_runs_in_its_own_process_group_and_finishes_when_turpin_is_interrupted` (S115)

### [REH]

- `rehearsal_pulls_by_instance_principal_and_cannot_read_releases`
- `rehearsal_smoke_failure_restores_the_database`
- `rehearsal_backup_timer_installed_and_enabled`
- `deploy_waits_for_the_backup_lock`
- `recorded_step_survives_a_reboot`
- `first_turpin_deploy_takes_off_level_and_deploy_sh_can_return`
- `tle_real_hooks_key_snapshots_to_the_deploy_and_restore_nothing_without_a_complete_one` (S97's real half, owned by delphside/tile-lite-elite#555)

## 10. Gaps

**Status, 2026-11-15.** The design was revised after this list was drawn up, and the scenarios now assert its wording. Closed in the design, and by these scenarios:

- The design's answers to the build questions: the host-side interruption by
  S110, the old layout by S112, the build's labels by S111, a gate on a host in
  the controller's run log by S113, and the board read by S114 and S115; and the
  request's own result after a repeat, by S105 and S109.
- #185's material: the interruption of §6 by S90; the keyed snapshots of §8 by
  S97, whose real half is X24; the host's state table by part 4's two matrices
  (R9, R57, S98 to S104); and *the last request* by R58 and its matrix (S93,
  S94, S105 to S109).

- X1 by S30 (a carried work package of another route is in the fixture) and the settle test `settle_advances_a_carried_work_package_of_any_route`.
- X3 by S20: "on `main`" stands, and docs/1.2 §1.0 is corrected (design §5).
- X4 by S20 and S50: an emergency descends from the release production runs, not the newest tag.
- X5 by S57 and the C11 × C12 matrix cell: `restore-state`, state `failed, no previous deploy`, exit by the error's type, naming the fallback.
- X6 by S12 and S53: `[release].overridable` names the gates, and `milestone` is the tool's own.
- X7 by S54: the 60-minute limit is tested at `--wait=1`; the default of 60 is asserted only by review.
- X8 by S29: `--unrecorded` takes a full SHA, and a copy already present is a no-op where the digests match. Not yet covered: another digest refuses (no test reaches it).
- X9 by S26: a different record refuses (exit 1), and all steps done exits 0. The gate count (X9b) stays untestable from outside.
- X10 by S55 and S56.
- X11 by S43, which asserts the `created` label, the build's start time
  (design §6).
- X12 by S58 and X13 by S59.
- X17 (the next deploy after a failed first deploy proceeds) by S57, and X18 (`--wait` at its limit stops, exit 75, naming what it waited for) by S54.
- X16 no longer applies: #117's body now has a decisions list.

Still open, each a question for the owner:

| gap | what it would take to close it | why it is acceptable for now |
| --- | --- | --- |
| X2 † Production's level, and the release production runs, are read from production's host state over ssh; the emergency gate alone reads its `/health` where it has no `turpin` state. | Closed: the owner decided on 2026-10-29 that the read is a scripted check, named in each application's CLAUDE.md. | S17, S20, S39, S48, S49 and S50 (R15 and R17) stand as written. |
| X9b A command "ending with a gate unrun refuses" cannot be provoked from outside, and §6 gives no per-command gate list beyond §9. | A test hook or a documented gate list. | The run log is asserted against §9 (O23). The self-check is reviewed, not tested. |
| X9c `state.json` is replaced whole by rename, so a kill leaves the old record or the new one (design §11). | A way to kill the host between the write and the rename, or inside the rename. | The test is not provokable from outside. Reviewed, not tested; S13, S94 and S96 show a whole record after a kill. |
| X14 The `oci-api-key` adapter (Dark Portal's copier) is exercised by no Tile Lite Elite test. | Dark Portal's adoption, delphside/dark-portal#15, carries the test: the key missing, then present, with the refusal shown before the success. | Dark Portal is out of scope here. |
| X15 The production-role gates are shown on a real host only by the owner's `--check` runs and 0.10.2's first production deploy (part 8), not before the merge. The real-host statement is: `turpin deploy production <raw SHA> --check` and `turpin deploy production <unrecorded version> --check` both refuse, naming the gate, and change nothing. It matches the post-deployment box of delphside/tile-lite-elite#555. | #555's test-approach box is changed to point at the CI tests and the post-deployment check. | Accepted at the test manager's sign-off on #117, 2026-10-28: production reads and deploys are the owner's, and the rehearsal identity cannot read releases. |

Accepted gaps, closed by the rehearsal run rather than by CI (part 8). The
stubs stand in for the real tools; what a stub cannot show, the rehearsal run
on the real stack does.

| gap | what would close it | why it is acceptable |
| --- | --- | --- |
| X19 The CI world is stubs, not `registry:2` and Docker-in-Docker: `skopeo`, `oci`, `docker`, `ssh`, `gh`, `curl`, `sudo`, `systemctl`, `useradd` and `userdel` are PATH stubs over folders, and the "machines" are folders. | A rehearsal run of the real tool against a real registry and host. | The rehearsal run (part 8) covers what a stub cannot show. |
| X20 S5 (multi-arch: a real `buildx` build and the index digest kept by the copy) is stubbed only through `STUB_ARCH`, which salts the digest. | The same rehearsal run: a multi-arch build, copy and pull on the real stack. | The copy is `skopeo copy --all --preserve-digests`, whose behaviour the stub cannot vouch for. |
| X21 S36 (a slow pull) is a delayed-pull stub, not a throttling proxy. | The rehearsal run's measured pull on a real host (`pull_timeout`). | The timeout path is exercised; the number is measured on the host. |
| X22 S40 (each component's registry credential writes only its own repositories) uses the stub's `STUB_WRITE_ONLY`, not a registry's access control; the stub also records which machine each registry write ran on (`where.log`), so a copy made on the wrong machine fails the test. | The rehearsal run, with the real credentials of the builder, the copier and the hosts. | The tool's part (which machine, which login) is asserted; the registry's enforcement is not the tool's. |
| X23 S65 to S70 (each component's login is its own, the controller cannot remove) rest on the stub registry reading a role from the auth file a `skopeo` call names and from the stub machine's `docker` login, not on a registry's policy or the real tools' handling of `REGISTRY_AUTH_FILE`, `~/.docker` contexts, `buildx` builders and credential stores. | The rehearsal run, with the laptop's real `docker` and `skopeo` and the real users and groups: `turpin login` for each component, then a build (with a `docker-container` builder named `turpin`, per design §5, the default builder unchanged), a release and a `prune`; the laptop's `docker context ls` unchanged. | The tool's part (which file, which machine, `DOCKER_CONFIG` untouched) is asserted; the registry's enforcement is not the tool's. |
| X24 S97's first two cases on Tile Lite Elite's real hooks and database: the snapshot keyed to `TURPIN_DEPLOY`, marked complete, `TURPIN_CURRENT`'s kept, nothing restored without a complete one. CI's S97 uses stub hooks that do what the contract says. | The test owned by delphside/tile-lite-elite#555, run on rehearsal with its keyed hooks. | The contract's wording is tested in CI against stubs; whether the real hooks keep it is shown only where they run (part 8). |

Derived by a fresh `test-designer` agent that read no implementation (docs/1.9).
