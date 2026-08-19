# Logs and backups: what we keep, where it lives, and how we know it works

Covers **#174** (container logs) and **#175** (no backup leaves the VM), designed
as one workstream because they answer the same question about different data:
*what survives, for how long, and who can read it.* #176 (nothing watches the
disk) is adjacent and referenced where it touches; it is not designed here.

Named for the leading issue, against the convention of one note per change —
they can be split if review prefers it, but the retention argument, the storage
argument and the "expose a condition, let OCI alert" argument are shared, and
splitting them would leave three cross-references where there is now one
document.

*Nothing here is built. This is the shape proposed for review.*

## The state today, measured 2026-08-18

```text
container log lines, last 24h        2,922
  web  — Caddy admin API             2,858   (98%)
  web  — everything else                45
  server — the whole application        19

container log volume                 751 KB/day
journal (system logs)                43 M, capped at 50 M, oldest entry 9 days old
/var/log/syslog*                     5 weekly files, gzipped, ~1.3 M
production database                  1.7 M + 3.3 M WAL
pre-deploy snapshots                 5 files, 2.5 M, on the VM being protected
disk                                 45 G total, 5.7 G used (13%)
RAM                                  954 M, 437 M available
```

Four things are wrong, and they are independent:

1. **Container logs die at every deploy.** `json-file` writes inside the
   container; `deploy.sh` recreates it. Redeploying to fix a problem destroys
   the evidence of the problem.
2. **They carry personal data** — display names, and email addresses including
   those of people who are not users.
3. **They are 98% noise**, so nothing about their size means anything.
4. **Every copy of the database is on the machine that would be lost**, and the
   copies only happen when we deploy.

---

## Part 1 — What we log

### Identifiers only

> **Log identifiers, never names or addresses.** `player_id` and `game_id` are
> sufficient to diagnose. `scripts/admin.sh` resolves an id to a person on the
> rare occasion a human needs to know who it was.

Owner, 2026-08-18: *"Agree only ids stored. If we get an invalid email we don't
need to record it. If we have to diagnose an issue we can always add extra
logging for that specific purpose."*

That last clause is the part that makes the rule affordable: the logs do not
have to anticipate every investigation, because a targeted, temporary log line
is a one-line change and a deploy away.

#### What changes

| where | logs today | becomes |
| --- | --- | --- |
| `auth.rs:47` player registered | `player_id`, `display_name` | `player_id` |
| `auth.rs:101` player logged in | `player_id`, `display_name` | `player_id` |
| `auth.rs:71` login rejected | `display_name`, `reason` | `reason` only — the name may not be an account at all |
| `auth.rs:352` reset for unknown email | **the email address** | the event and nothing else |
| `email.rs:160/165/168` mail sent/failed | recipient address, subject | `player_id`, message kind |

Everything else in the server already logs identifiers only: `game_id`,
`player_id`, `invitation_id`, `seat`, `winner_seat`.

#### What we are not doing, and why it matters that it is written down

**No HTTP access logs exist today.** Caddy's `log` directive is not configured,
and the server's `TraceLayer` emits at `debug` under an `info` filter. So no IP
addresses and no request paths are recorded anywhere.

That is a decision by accident, and it should become one on purpose: **if access
logging is ever added, IP addresses are omitted or truncated**, and the same
rule applies to the client's URL, which carries game and player ids.

#### The limit of the claim

`player_id` is **pseudonymous, not anonymous** — we hold the table that resolves
it. This minimises what a leaked log is worth and shortens the retention
conversation; it does not put the logs outside data protection. Stating that here
so nobody later reads "ids only" as "not personal data".

### Where the events are written down

One place, as asked: **`docs/4.7-log-events.md`** — 4.x is reference, per the
numbering convention.

With JSON output the catalogue *is* the schema: for each event, the `target`, the
message, the level, and its fixed set of fields. That serves both readers — a
person looking for what a line means, and a parser needing to know what fields
exist.

**Keeping it true is the open question.** 3.3's own rule is that a document the
code disagrees with means one of them is wrong, and a catalogue maintained by
memory drifts within a month. Options:

| | cost |
| --- | --- |
| a test extracting every `tracing::` call site and comparing the set to the document | a source scan that is fiddly to write and must be updated whenever an event is added — which is the point |
| review discipline | free, and the failure is silent |

Recommended: the test. Flagged for review because it is a judgement about how
much machinery a hobby project should carry.

---

## Part 2 — How we log it

### JSON, because "deserialise" was the requirement

`tracing_subscriber::fmt().json()` with `.with_ansi(false)`, selected by
environment so development keeps its colours:

```text
TILE_LITE_ELITE_LOG_FORMAT=json     set in docker-compose.yml and .preview.yml
unset                                human-readable, as now — cargo run, dx serve
```

Today's output is worse than merely unstructured: every field is wrapped in ANSI
escape sequences, because `fmt()` colours by default and nothing turns it off in
the container. Any parser has to strip them first.

**Caddy already emits JSON**, so this makes the two containers consistent rather
than introducing a new idea.

#### Human-readable is a rendering, not a second copy

One store, two readings — not two sinks, which would be two things to size and
rotate and two versions of what happened:

```text
journalctl CONTAINER_NAME=tile-lite-elite-server-1 --since "1 hour ago" -o cat \
  | jq -r '"\(.timestamp[11:19]) \(.level) \(.target) \(.fields.message) …"'
```

That reads better than what we have now, because what we have now is the same
line wrapped in eleven escape sequences. The filter goes in `docs/3.4` beside the
`game_id` recipe from #166.

The honest cost: `docker compose logs -f` while watching a deploy shows raw JSON
unless piped. That is the one moment the rendering is inconvenient.

#### Rejected: native journal fields

`tracing-journald` would make fields queryable directly (`journalctl GAME_ID=…`)
with no parsing at all. Rejected on the owner's instruction — *"I would rather
not tie ourselves into systemd to read the logs, json is more flexible"* — and
the reasoning is worth keeping: with JSON, systemd is only transport, and the
same bytes parse identically out of a file, a pipe or object storage if the
transport is ever replaced.

---

## Part 3 — Health checks

### Both services get a real one, and neither talks to the application log

Owner, 2026-08-18: *"We should have health checks for both the web site and the
api server. Health logs should not be in the same log file as application
events."*

#### What is wrong now

| | checks | logs |
| --- | --- | --- |
| server | `curl -f localhost:3000/health` | nothing — the server does not log requests |
| web | `wget --spider 127.0.0.1:2019/config/` — Caddy's **admin API** | every probe, at `info`: **2,858 lines a day** |

The web check is weak as well as loud: the admin API answering proves the process
is alive, not that the site serves. And it makes application events unfindable —
19 real lines hidden among 2,858.

#### What replaces it

**Point the web check at the site it serves**: `wget --spider
http://127.0.0.1/version.txt`. It proves routing, the file server and the static
build, and it is **silent**, because access logging is off. The server's check
already hits `/health` and already logs nothing.

That satisfies the requirement in its strongest form: health checks and
application events are not in the same file because health checks are not in a
file at all.

**Where the health record lives instead:** OCI's external check (#136) already
probes `/health` from three regions and keeps the history — the record we would
be writing locally, kept off the box, which is where a health record belongs.
Docker also keeps the last five probe results in
`docker inspect --format '{{json .State.Health}}'` for the local question.

If review wants health probes recorded locally anyway, the alternative is a
separate Caddy logger writing them under their own syslog identifier so they
land beside, not among, the application events — more configuration, and a record
that duplicates one OCI already keeps.

#### Why this is in the logging design at all

Because it decides every number in Part 4. Fixing it drops container output from
~750 KB/day to roughly 15 KB/day. Sizing the journal before fixing it means
sizing it for a `wget`.

---

## Part 4 — Where logs live, and for how long

### journald as the transport, with the ceiling raised as a backstop

```yaml
# docker-compose.yml and docker-compose.preview.yml, both services
logging:
  driver: journald
```

```ini
# /etc/systemd/journald.conf.d/zz-tile-lite-elite.conf
[Journal]
SystemMaxUse=100M
MaxRetentionSec=7d
```

**Why journald.** The store belongs to the host, so it survives the container
recreation that discards everything today; it already runs, already persists to
`/var/log/journal`, and already rotates. Its rate limit (10,000 messages per 30
seconds) is four orders of magnitude above our traffic.

**Why 7 days.** Owner: *"7d is more than sufficient… although we could increase
the retention period if we needed longer to investigate a particular issue."*
Retention is a knob, and this is where it is set.

**Why 100 M when 7 days needs about 100 KB.** Purely as a backstop. If volume
grows, the *size* cap binds before the age rule and retention silently drops
below the seven days without anything saying so. 100 M keeps seven days true up
to about 14 MB/day. The existing cap is 50 M and was set deliberately — see
below — so this doubles it rather than removing it.

#### The 50 M cap, and why it is being changed rather than deleted

`/etc/systemd/journald.conf.d/50-cap.conf` sets `SystemMaxUse=50M`. It was
written on 2026-07-30 during housekeeping, for a real reason: *59 MB of logs on
a 954 MB box, and journald grows its own footprint with the journal it maps.* The
box still has 954 MB.

The memory cost of a larger journal is file-backed page cache, which the kernel
reclaims under pressure — so 100 M is a bounded, reclaimable cost rather than
anonymous memory. That is the argument for doubling it; it is not an argument for
removing the cap.

**It is also the best example this workstream has of the problem in Part 6:** a
production setting that would have silently defeated the requirement, made by
hand three weeks ago, recorded nowhere.

#### `/var/log/syslog` stays on

`ForwardToSyslog=yes` is already set, so everything journald receives is also
written to `/var/log/syslog`, rotated weekly by logrotate, four kept and gzipped
— about five weeks in plain files, readable with `grep`, `zgrep`, `zcat | jq` and
anything else that reads a file. **No `journalctl` required**, which is the
non-systemd path the owner asked for, and it costs about 1 MB/day on a 13%-full
disk.

**One point for review.** The journal keeps 7 days and syslog keeps ~5 weeks.
Those agree only if "7 days" means *enough for diagnosis*. If it means *we do not
keep logs about people for longer than a week*, logrotate must match — `daily`,
`rotate 7` — and the difference is a promise versus a capacity choice.

#### Reading, after the change

| question | command |
| --- | --- |
| what is happening now | `docker compose logs -f server` (unchanged) |
| what happened before the last deploy | `journalctl CONTAINER_NAME=tile-lite-elite-server-1 --since "3 days ago"` |
| human-readable | the `jq` filter above |
| without systemd | `zgrep … /var/log/syslog*` |

`docs/3.4:246` says logs are `docker compose logs server` today. That is true only
for the running container — compose can only show containers that still exist,
under any driver — so the document gains the `journalctl` form.

---

## Part 5 — Backups (#175)

### The database is the only irreplaceable thing

Everything else on the VM rebuilds: images come from a `docker save` bundle the
deploy carries, the compose file and Caddyfile are in git, Caddy's certificates
re-issue from Let's Encrypt. **`/data` is the only state that cannot be
regenerated**, which keeps the scope small.

### Snapshot files, not volume images

A block-volume backup is *crash-consistent* — the bytes as they are at that
instant, mid-checkpoint if that is when it lands, with 3.3 M currently sitting in
the WAL. SQLite recovers from that most of the time, and "most of the time" is
not a property to want on the day you need it.

The owner's observation settles it: *"we can take local snapshots as easily as
remote ones, and the local snapshots should not be corrupt."* So the thing we
ship offsite is a **snapshot file**, taken the way `deploy.sh` already takes one.

Volume backups remain useful for rebuilding an *instance* quickly; they are never
the database's source of truth.

### Daily, consistent, verified, generational

```bash
sqlite3 /data/tile-lite-elite.sqlite3 "VACUUM INTO '/tmp/backup.sqlite3'"   # consistent, no downtime, compacted
sqlite3 /tmp/backup.sqlite3 "pragma integrity_check"                        # expect: ok — costs a second at 1.7 M
# on ok:   upload
# on fail: alert, and keep the previous upload
gzip -c /tmp/backup.sqlite3 | curl -T - "<pre-authenticated request URL>"
```

- **`VACUUM INTO`, never `cp`.** `cp` under a hot WAL is the classic way to get a
  backup that restores to a corrupt database.
- **Verify before uploading**, because at this size verification is free and it
  turns "we have backups" into "we have backups that open".
- **Generational, not one slot** — 7 daily plus 4 weekly is about 7 MB at
  today's size. A corruption that goes unnoticed for three days must not have
  eaten every good copy.

### Where it goes

**OCI Object Storage**, written with a pre-authenticated request URL so the VM
needs no OCI CLI and holds no credentials beyond the URL itself.

| rejected | why |
| --- | --- |
| the Rehearsal VM | owner: *"a backup solution that doesn't repurpose another VM"* — and it is #40, production user data on the public-IP box, made nightly. Same tenancy, same region |
| the development laptop | owner: *"my laptop is not part of the production service"* |
| volume backup as the primary | crash-consistent, above |

**Open, and needing the OCI console:** the Always Free allowance for object
storage, and the maximum expiry on a pre-authenticated request. A URL that
quietly expires is exactly how this stops working two months after it is built,
so whatever the maximum is, the expiry date belongs in `docs/3.4` and the upload
must alert on failure rather than exiting quietly.

### Restoring, which is the part that is currently a hypothesis

`rollback.sh` restores a snapshot into a *running* deployment, so that path is
proven. **Restoring onto a new instance is not**, and a backup strategy is a
hypothesis until it has been done once. That drill is part of this work, not a
follow-up: build a throwaway VM, restore the newest backup, confirm the site
serves and the data is there.

---

## Part 6 — The half that does not travel

The compose `logging:` block is in the repository and rides the deploy. The
journald drop-in, the logrotate stanza and the backup job are **VM
configuration** — they do not travel, and a rebuilt host loses them silently.
`50-cap.conf` is the proof: it has shaped production for three weeks and the
repository has never heard of it.

**Ship the files, check them at deploy, apply them from documentation:**

```text
deploy/journald.conf.d/zz-tile-lite-elite.conf     in the repository
deploy.sh → ssh 'systemd-analyze cat-config systemd/journald.conf'  → compare, fail loudly
docs/3.4                                            how a new host gets them
```

Checking is cheap and failing loudly is the whole point. *Applying* on every
deploy would widen `deploy.sh` into host configuration management and would need
`systemctl restart systemd-journald` in the middle of a release.

**A filename trap worth recording:** journald drop-ins are ordered by filename
across all directories, and `/etc` beats `/usr` only for the *same* name. A file
called `99-tile-lite-elite.conf` sorts **before** the vendor's `syslog.conf`
(`9` < `s`) and loses. Hence `zz-`.

---

## Part 7 — Aggregates and capacity (adjacent, #176)

Recorded here because it came out of this discussion and the design must not
contradict it; the work belongs to #176.

**Aggregates outlive the detail, and they do not come from the logs.** #90
already built the mechanism: `database_size_history`, one row per day, in the
database — so it is snapshotted before every deploy, restored by rollback, and
covered by Part 5. It gains columns rather than a new system: disk used and free,
error counts by level, and the sweep counters #166 wants.

**The trap:** the server can measure `/data`'s filesystem from inside the
container, but **cannot see the journal or `/var/log`** — those are outside its
namespace. Log size therefore comes from the report at read time on the host, not
from the daily writer.

**The report derives; the table stores.** Green/amber/red is computed from
thresholds that live in one place, exactly as `roadmap.sh` derives rather than
maintaining. The alert is a flag meaning *look at the capacity report*.

**Where the flag goes.** #166 also needs to expose a condition (sweep freshness).
Two conditions now, a third later, argues for one endpoint carrying named
conditions with a severity each — `/status` — rather than fields accreting on
`/health`, which **LIMIT-4** requires to stay a liveness probe that answers while
everything else refuses.

---

## Part 8 — Evidence

Per 3.3, evidence follows what the change does. This changes the process's
startup path, its output format, production configuration and a data path — so
the evidence is server- and operations-shaped, not gameplay-shaped.

| claim | how it is shown |
| --- | --- |
| the server starts and logs under the new format | preview stack up, `journalctl CONTAINER_NAME=…` returns lines |
| every line is machine-readable | `journalctl -o cat \| jq -e . >/dev/null` over a run |
| no personal data remains | grep the audit's five call sites; a preview run through register / login / failed login / reset / invitation, inspecting what was written |
| logs survive a deploy | deploy preview twice, read across the boundary |
| retention is what we set | `journalctl --disk-usage` and the oldest entry, a week after landing |
| the health check still detects a broken site | stop `server`, confirm the web check fails; break the static root, confirm it fails |
| the backup restores | the new-instance drill in Part 5 |
| the daily backup keeps running | the failure path alerts — tested by pointing it at a bad URL |

The existing test suites should pass unchanged; nothing here touches game logic.

---

## Part 9 — Sequencing, and the case for taking three pieces early

The owner's default is that this workstream goes **behind #71**. That is right
for most of it — and three pieces have a reason to go first that is not
impatience:

| piece | size | why not to wait |
| --- | --- | --- |
| **the health-check fix** | one line in `Dockerfile` | it makes every other number in this document honest, and it is the difference between 19 useful lines a day and 2,922 |
| **personal data out of the logs** | ~5 call sites | every day it waits is another day of email addresses landing in a log that is about to gain seven-day retention *and* an offsite copy. The offsite copy is what changes this from tidiness to something worth doing first |
| **the backup** | a script and a bucket | the only failure in the whole workstream that is **unrecoverable**. Everything else here is discomfort; losing the VM today loses every game ever played, and the exposure grows with each day the site stays up |

The rest — JSON output, the event catalogue, the journald switch, retention, the
capacity report — has no such argument and can follow #71 comfortably.

**One interaction to be aware of.** `/status` (Part 7) and the sweep task (#166)
touch the same area as #71's chunk A, so building the endpoint before #71 risks
rework. The three pieces above touch none of it: the health check is a
`Dockerfile` line, the logging edits are five call sites, and the backup is
entirely outside the application.

---

## Open questions for review

1. **Seven days: promise or capacity?** If a promise, logrotate matches it and
   syslog stops being a five-week archive (Part 4).
2. **The catalogue test** — build the source scan, or rely on discipline
   (Part 1)?
3. **Health probes recorded locally, or only in OCI** (Part 3)?
4. **Sequencing** — do the three early pieces stand, or does everything wait for
   #71 (Part 9)?
5. **One note or two** — this covers #174 and #175; splitting is easy if review
   prefers a document per issue.

Refs #174, #175, #176, #166, #90, #136, #40
