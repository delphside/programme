# Benchmark run: runbook for rehearsal and production

The owner's steps for the `benchmark-run` activity
([1.4](../../../../../docs/1.4-programme-activities.md)), run by hand. It runs
Tile Lite Elite's engine timing benchmark on rehearsal and on production from
**one binary**, so the two rows differ only by machine. Production access is
the owner's, so every step here is his. How to read the result is Tile Lite
Elite's
[4.3.10](https://github.com/delphside/tile-lite-elite/blob/main/docs/4.3.10-benchmarking.md).

The run uses one of the VM's two cores for about five seconds. Players on
production may see a slower engine move while it runs.

## Before starting

- The development machine has the SSH keys `deploy-rehearsal.sh` and
  `deploy.sh` use.
- No pending reboot needs to come first: the row records the hypervisor's
  steal time. If a VM has just been rebooted, wait five minutes so its
  containers settle.

```bash
cd ~/tile-lite-elite/main
git pull --ff-only && git submodule update --init
git status --short        # expect nothing, or the row is recorded as -dirty
```

## 1. Rehearsal, with a reference run here

```bash
./scripts/measure/bench-rehearsal.sh
```

It builds the benchmark, runs it on this machine, copies it to rehearsal, runs
it there and appends both rows to `engine_timing_results.csv`.

**Check:**

- exit 0;
- a line `==> recorded to crates/server-game/examples/engine_timing_results.csv`;
- the rehearsal row printed beside the last one for the same host.

## 2. Production, with the same binary

Do not rebuild between step 1 and this step. Run steps 2 and 3 in the same
shell, because step 3 uses `$OUT`.

```bash
COMMIT=$(git rev-parse --short HEAD)
[ -n "$(git status --porcelain -- . \
  ':!crates/server-game/examples/engine_timing_results.csv' \
  ':!crates/server-game/examples/moves')" ] && COMMIT="$COMMIT-dirty"
PROD=ubuntu@$(grep -oP 'DEPLOY_HOST="\$\{DEPLOY_HOST:-\K[^}]+' scripts/deliver/deploy.sh)
KEY=${DEPLOY_SSH_KEY:-~/.ssh/oracle_tile_lite_elite}
OUT=$(mktemp)
scp -q -i "$KEY" target/release/examples/engine_timing_bench "$PROD:/tmp/engine_timing_bench"
ssh -n -i "$KEY" "$PROD" 'cd /tmp && ./engine_timing_bench 30 official' > "$OUT"
ssh -n -i "$KEY" "$PROD" 'rm -f /tmp/engine_timing_bench'
ROW=$(grep '^row: ' "$OUT" | sed "s/^row: //; s/,unknown,/,$COMMIT,/")
[ -n "$ROW" ] && printf '%s\n' "$ROW" \
  >> crates/server-game/examples/engine_timing_results.csv
HOST=$(printf '%s' "$ROW" | cut -d, -f3 | tr -c 'A-Za-z0-9' '-')
sed -n 's/^MOVES //p' "$OUT" \
  > "crates/server-game/examples/moves/$(printf '%s' "$ROW" | cut -d, -f1)-$HOST.csv"
```

The commit is labelled `-dirty` as `bench-rehearsal.sh` labels it, and the
per-move rows are saved beside step 1's, as 4.3.10 *The raw measurements*
says.

**Check:**

- the last line of the CSV starts with today's timestamp;
- it carries `$COMMIT`, not `unknown`;
- it names the production host.

If `ROW` is empty, the run did not finish: read `$OUT`.

```bash
tail -1 crates/server-game/examples/engine_timing_results.csv
ssh -n -i "$KEY" "$PROD" 'ls /tmp/engine_timing_bench' # expect: No such file
curl -fsS https://tileliteelite.com/health; echo " exit $?"  # expect: exit 0
```

## 3. Send the rows back

```bash
git diff --no-color crates/server-game/examples/engine_timing_results.csv
```

Paste the three added rows into the thread the run was asked for in; Claude
commits them by pull request and logs the activity. Then put the file back, so `main` stays clean:

```bash
git checkout -- crates/server-game/examples/engine_timing_results.csv
rm -f "$OUT"
```

The per-move files under `crates/server-game/examples/moves/` are not
committed and may stay.
