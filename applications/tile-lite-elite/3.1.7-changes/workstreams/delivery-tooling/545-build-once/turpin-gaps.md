# Turpin: what Tile Lite Elite needed of it

Found while designing delphside/tile-lite-elite#545 *MAIN PROJECT: Build once,
promote through environments*, for Tile Lite Elite's adoption of Turpin
(delphside/programme#117): gaps in the tool that Tile Lite Elite could not meet
as written. delphside/programme#233 *Turpin: close the gaps for Tile Lite Elite*
closes T1 to T7 and T9 to T12; T8 is not needed (Q5); T13 is open. *A first
deploy* is one to a host whose state has no `current`; *an adopted host* runs
the application under another tool before Turpin's first deploy, as Tile Lite
Elite's two VMs run its `deploy.sh`.

| Gap | Tile Lite Elite needed | Status |
| --- | --- | --- |
| T1 | `migrate` to run `server --migrate-only` with the volume and environment the compose file gives the server | fixed: hooks from step 7 of Turpin's §11 get `TURPIN_DEPLOY`, `TURPIN_DEPLOY_DIR` and `TURPIN_COMPOSE` |
| T2 | to apply a changed `.env` and reset rehearsal against the current deploy | fixed: `turpin-host compose APP ENV ARGS...`, holding the environment's lock, refusing with no current deploy |
| T3 | `smoke` and `post-deploy` to know the address to test | fixed: `TURPIN_URL` |
| T4 | one home for the `ssh` alias, `[hosts.X].ssh` | fixed |
| T5 | a per-build argument, `TILE_LITE_ELITE_BUILD_ID`, the short SHA | fixed: `[turpin.build].args` |
| T6 | that a board-key edit in `app-profile.toml`, or a pin move outside the deploy steps, is not a change to the image | fixed: the payload carries only the profile keys a host reads, and where `[ships].carries_payload = true` a pin move ships only where it changes a file the payload carries |
| T7 | on an adopted host, a failed first deploy to leave the old service serving and its host files in place | fixed: the restore returns the old files' content, the containers the deploy stopped and each unit's enabled and active state |
| T8 | a preview on the controller's machine | not needed: preview is a standing environment (Q5) |
| T9 | R9's per-issue question, `Confirm that #N is in this build [y/N]` | fixed: the question per issue, `--confirm N` repeatable, `carries.confirmed` in the record, parents skipped, `--set-aside milestone REASON` kept |
| T10 | to release 0.10.2 while production runs 0.10.1, deployed by `deploy.sh`, where production has no Turpin state | fixed: production's version comes from `/health`, and the release refuses where no tag of that version names the commit |
| T11 | the state folder and its `.env` in place before the first deploy | fixed: `host-install` makes `/var/lib/turpin/APP` and `APP/ENV` (0700, owned by the deploy user) and an empty `.env` (0600) |
| T12 | one home for Tile Lite Elite's specifics | fixed: Turpin's design links to Tile Lite Elite's [design](https://github.com/delphside/programme/blob/main/applications/tile-lite-elite/3.1.7-changes/workstreams/delivery-tooling/545-build-once/design.md) |
| T13 | with `[ships].carries_payload`, an `app-profile.toml` change ships only where a key in the payload's `HOST_READS` changes (`board/shipping.py` judges the file as one path) | open: to be fixed in Turpin before delphside/tile-lite-elite#555 *WP B Del 3 of 4: deploy tooling builds once and promotes* merges |
