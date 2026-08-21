# Logs and backups: what we keep, where it lives, and how we know it works

The design for **project #174**, in the production operations workstream
(#189). It covers the project's two requirements — **R1** logs that survive a
deploy, and **R2** a database copy that survives the VM — because they answer the
same question about different data: *what survives, for how long, and who can
read it.* Issue #176 (nothing watches the disk) is adjacent and referenced where
it touches; it is not designed here.

**One design for the project**, per the owner, 2026-08-21: *"this is one project
and should have one design even if it covers multiple requirements and
deliveries."* The retention argument, the storage argument and the *expose a
condition, let OCI alert* argument are shared, so splitting would leave three
cross-references where there is now one document.

*Nothing here is built.* Reviewed on PR #177 and **provisionally approved**
2026-08-21.

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

**Keeping it true was the open question, and the owner's answer is better than
either option I offered.** Owner, 2026-08-21: *"Can we be a bit smarter? In the
document have the JSON schema in a form that can be compared mechanically to the
logs. Then the review just has to check that the schema and the documented fields
match, and if they don't then a reader can quickly see the gap."*

**The document becomes the artefact under test**, rather than something a test
tries to keep up with. The schema lives in `docs/4.7-log-events.md` as a fenced
`json` block; a test extracts that block and compares it against the fields the
code actually emits. Divergence fails CI, and the failure names the field.

| what I proposed | what this replaces it with |
| --- | --- |
| scan every `tracing::` call site and compare the *set of events* to the document | serialise each event and compare its **fields** to the schema the document declares |
| a source scan, fiddly and brittle — it must parse Rust to find what is logged | no parsing: the events are constructed in the test and rendered through the real JSON layer, so what is compared is **what would actually be written** |
| tells you an event is missing from the catalogue | tells you an event gained a field nobody documented — **which is the leak this part exists to prevent** |

The second row is why it is smarter and not merely tidier. A source scan proves
the *list* is complete; it says nothing about whether an event quietly acquired a
`display_name`. Comparing the rendered output to a declared schema catches
exactly that, and catches it on the commit that introduces it.

**And it makes review cheap, which was the stated goal.** A reviewer does not
read code to check the catalogue. They read two lists that a machine has already
proved identical, and the only judgement left is whether a documented field
*should* be there — which is the judgement a person is actually for.

*Not a new mechanism*: this is 3.3's rule — *wherever a rule can be checked by
the tooling, check it there* — applied to a document rather than to code, which
is the first time we have pointed it that way round.

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

#### The bucket, and the credential

Settled 2026-08-21, and **measured rather than assumed** — the console questions
this section used to carry are answered below.

| | |
| --- | --- |
| namespace · bucket | `axbbaaptgyab` · `tile-lite-elite-backups` |
| region · compartment | `uk-cardiff-1` (UK West, Newport) · `stephenmor (root)` |
| tier · visibility | Standard · private |
| **credential** | a **bucket-scoped PAR, access type *permit object writes*, object listing off** |
| **on the bucket** | **object versioning on** |

**The credential cannot destroy what it writes**, and that is the whole point of
choosing it. Tested from the production VM on 2026-08-21 against a throwaway
seven-day PAR:

```text
PUT     200  (0.128s)     upload works, and the VM reaches object storage
GET     404               a write PAR cannot read
LIST    404               a write PAR cannot list
DELETE  404               a write PAR cannot delete
HEAD    404               it cannot even confirm an object exists
PUT2    200               but it CAN overwrite an existing name
```

So the threat this whole part exists to answer — *the VM holds the credential,
so whatever can upload can also destroy* — does not apply. An attacker on the
box, or a bug in our own script, cannot delete a backup. Oracle's documentation
says so (*"pre-authenticated requests can't be used to delete buckets or
objects"*) and the 404 above is that sentence observed.

**Three consequences worth stating, because none of them is obvious:**

- **the refusals are 404, not 403.** Object Storage will not distinguish *"you
  may not"* from *"there is nothing there"*, so a leaked write-only URL reveals
  nothing about the bucket's contents — not even whether a guessed name exists
- **overwrite is the one remaining way to damage a backup**, and it returned
  200. **Object versioning is therefore not optional and is also sufficient**: a
  `PUT` over an existing name creates a version and the original bytes survive.
  A retention rule adds nothing against *this* threat — only against a mistake
  made from the console with real credentials
- **revocation is immediate.** Deleting the PAR in the console turned the same
  `PUT` into a **401** on the next attempt. So if the VM is ever compromised,
  one click in the console stops the bleeding without touching the instance

**The restore path is therefore asymmetric by construction.** The VM can write
backups and cannot read them; restoring is done from the console or a laptop
with real credentials. That is a feature and not an inconvenience — it means no
credential on the production host can be used to exfiltrate the database.

#### Capacity, and expiry

**Capacity is a non-issue**, measured 2026-08-21: the production database is
**1.7 MB**. A year of daily backups is ~620 MB uncompressed, against an Always
Free allowance of **20 GB combined** across Standard, Infrequent Access and
Archive — under 1%. The tenancy's *service* limit reads `Unlimited`, which is a
different thing from the free allowance and is the reason a **retention rule
matters as policy** even though capacity does not: an unbounded loop against an
unlimited limit is the one way this turns into a bill.

**Expiry has no maximum.** Oracle: *"Expiration date is required, but has no
limits. You can set them as far out in the future as you want."* So the original
worry — a URL that quietly expires two months after it is built — is ours to
create or avoid, and the opposite one replaces it: a PAR set twenty years out is
a permanent bearer credential nobody revisits.

**The answer is an alarm rather than a long date.** A deliberate expiry recorded
in `docs/3.4`, and the upload alerting on failure, so an expired PAR announces
itself the next morning instead of being discovered when the database is gone.

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

## Part 8 — Test approach

Named as such under D17: a **test approach** states the environment, the tools,
and what is measured against what criteria. It is not a test plan — the standards
reserve that for a management document of scope, schedule and resources, which a
one-developer project does not write.

### The two questions every delivery answers (D15)

| | |
| --- | --- |
| **does this involve functional changes that require user testing?** | **Barely.** Almost nothing here is visible by using the site. The one exception is the health-check change, whose user-facing test is *the site still serves* — which the smoke test already asserts. So preview has very little to look at, and this is the release where `DEPLOY_SKIP_PREVIEW` is close to honest rather than convenient |
| **does this involve technical changes that require technical testing?** | **Almost entirely.** Output format, journal retention, a credential's permissions, a restore from cold. None of it can be judged by a person using the application, and most of it needs production-like hardware or a real host |

**Which is the useful finding**, not a formality: this project's evidence is
nearly all technical, so the effort belongs in rehearsal and in CI, and the
preview step should not be padded out to look busy.

### Environment and tools

| where | what it judges | tools |
| --- | --- | --- |
| **CI** | the log schema matches what the code emits; nothing regressed | `cargo test`, and the new schema-comparison test below |
| **preview** | the stack comes up, logs are readable, a deploy does not discard them | `deploy-preview.sh`, `journalctl`, `jq` |
| **rehearsal** | the things needing a real host: journald retention, the backup upload, the alarm | `journalctl --disk-usage`, `curl`, the backup script itself |
| **a throwaway instance** | the restore, which is the only claim that cannot be tested anywhere else | a fresh VM, the newest backup, and a browser |
| **production** | that the failure alarm actually fires | OCI, and a deliberately broken upload |

### Test tooling this builds

**Two new things, and both are artefacts** (D25). Asked by the owner,
2026-08-21: *"do the artefacts include any scripts written to execute the tests
described in section 8?"* — one was listed, one was not.

**1 · The log-schema comparison test.** Renders every log event through the real
JSON layer and compares the field names against the schema declared in
`docs/4.7-log-events.md`. Owner's idea: *"in the document have the JSON schema in
a form that can be compared mechanically to the logs."*

It is the control that makes *identifiers only* durable rather than aspirational —
a source scan proves the list of events is complete and says nothing about an
event quietly acquiring a `display_name`. This catches that on the commit that
introduces it.

**Its limit, which matters:** it proves the code and the document **agree**, not
that the document is **right**. A `display_name` added to both would pass. The
control for that is a person reading `docs/4.7` — so the schema is not a field
list to skim in review; it is the thing being reviewed.

**2 · A project test script**, `scripts/check-log-hygiene.sh`. Owner,
2026-08-21: *"I see a new test that will run in production, but not one for the
project testing."* Right — the restore script is an **operational** tool that
outlives the project, and the tests that prove *this project's changes work* had
no script at all. I had written them off as one-off confirmations, and three of
them are not.

Run against a preview or rehearsal stack, it asserts:

| claim | how |
| --- | --- |
| **every line is machine-readable** | `journalctl -o cat` over the run, each line through `jq -e .` |
| **no personal data remains** | drive register · login · failed login · reset · invitation, then fail on an `@`, or on the display name used, anywhere in what was written |
| **logs survive a deploy** | deploy twice, assert the oldest entry predates the second deploy |

**The middle row is the one that earns the script.** It is the most important
claim in the project — it is why the offsite copy is safe to make — and by hand
it is a grep and a squint at the right moment, which is exactly the check that
rots. `check-rate-limits.sh` is the precedent: a script written to test a change,
run against rehearsal, kept afterwards because the claim it asserts stays true or
stops being true.

**3 · A restore script**, which the artefact list was also missing. Part 5's drill —
build a throwaway VM, restore the newest backup, confirm the site serves — was
written as a one-off, and a one-off restore proves the backup worked **once**. Six
months later it is a hypothesis again.

So the scriptable half becomes a script: fetch the newest object, verify it
opens, load it into a fresh volume and report. **The VM provisioning stays
manual** — it is a handful of console clicks and scripting it would be building a
deployment tool to test a backup.

That makes the drill re-runnable at each release, or quarterly, at the cost of
one command — and it is the difference between *"we restored it in August"* and
*"we restore it routinely."*

### All three are kept, and each says when it runs

Owner, 2026-08-21: *"are these new scripts temporary or will we keep them after
the project?"*

**All three are permanent, and the test is not how useful they were during the
project — it is whether the claim each asserts is permanent.** Every one of these
is a property that must stay true for as long as the service runs, so a script
that stops running is a property that stops being checked. A genuinely temporary
test artefact asserts something true once: *"the migration converted all 412
rows"* is a one-off; *"no address reaches the log"* is not.

| script | kept because | runs |
| --- | --- | --- |
| the schema comparison test | the log's shape must keep matching what `4.7` declares | **CI, every push.** It costs nothing, so nothing else needs deciding |
| `check-log-hygiene.sh` | personal data must keep out of the logs, and every future logging change is a chance to let it back in | **against rehearsal, in the release path, whenever a release touches the server's logging or auth paths** — and on demand |
| `restore-backup.sh` | a backup that has not been restored recently is a backup nobody has tested | **quarterly, and after any change to the backup mechanism** — the project's own drill is its first run |

**Saying when each runs is not bookkeeping.** A kept script with no trigger
becomes a script nobody has run since the release it was written for — and that
is *worse* than not having it, because it reads as coverage. The repository would
show a test for personal data in the logs, and the logs would have personal data
in them.

**What stays manual, and why.** Stopping the server to prove the health check
fails, and pointing the uploader at a bad URL to prove the alarm fires: both are
destructive one-offs against a live stack, confirming a mechanism rather than a
property. Retention — *seven days is still seven days* — is checked a week after
landing, which no script run during the project can do.

### What is measured, against what criteria

| claim | how it is shown |
| --- | --- |
| the server starts and logs under the new format | preview stack up, `journalctl CONTAINER_NAME=…` returns lines |
| every line is machine-readable | `journalctl -o cat \| jq -e . >/dev/null` over a run |
| no personal data remains | grep the audit's five call sites; a preview run through register / login / failed login / reset / invitation, inspecting what was written |
| logs survive a deploy | deploy preview twice, read across the boundary |
| retention is what we set | `journalctl --disk-usage` and the oldest entry, a week after landing |
| the health check still detects a broken site | stop `server`, confirm the web check fails; break the static root, confirm it fails |
| the backup restores | the new-instance drill in Part 5, run by the restore script |
| the daily backup keeps running | the failure path alerts — tested by pointing it at a bad URL |

| **the log schema and the code agree** | the new test, in CI, on every push |
| **no address or display name reaches the log** | `check-log-hygiene.sh`, against preview and again against rehearsal |
| a leaked write-only credential cannot destroy a backup | **already shown**, 2026-08-21, from the production VM: `PUT 200`, `GET 404`, `LIST 404`, `DELETE 404`, `HEAD 404`, and `401` after revocation |

The existing test suites should pass unchanged; nothing here touches game logic.

---

## Part 9 — Deliveries

**Two deliveries, each an ordered sequence rather than a set** (D22), because a
host step assumes the artifact already deployed and a service step assumes the
host script exists to use it.

### Delivery 1 — logging and health

| # | step | route |
| --- | --- | --- |
| 1 | install the journald drop-in and reload — raising the cap **before** anything writes to journald, so retention is never briefly wrong | applied on the host |
| 2 | release: the `Dockerfile` health check, JSON output, the five call sites, the compose `logging:` block, `docs/4.7`, `docs/3.4` | in the artifact |
| 3 | confirm: deploy a second time and read across the boundary — the claim the project exists for | — |

Step 1 first is the part worth stating. With the driver switched but the old
50 M cap in place, the size limit binds before the age rule and seven days
silently becomes something less — the exact failure Part 4 describes, arrived at
by doing things in the wrong order.

### Delivery 2 — backups

| # | step | route |
| --- | --- | --- |
| 1 | create the write-only pre-authenticated request, listing off, and turn on object versioning | applied to a service we use |
| 2 | install the backup script and its systemd timer | applied on the host |
| 3 | create the alarm that fires when a backup does not arrive | applied to a service we use |
| 4 | the restore drill on a throwaway instance | — |

**Neither delivery is a release on its own.** Delivery 1's step 2 is; everything
else is an application, and gets a dated row in the delivery log with no version
(D6). That is what makes the log worth keeping — five of these seven steps leave
no other trace.

### Sequencing against #71

**All of it goes before #71.** Owner, 2026-08-21: *"we can do those things ahead
of #71, we can do all of it ahead of #71 if that is easier."* It is easier —
splitting the project into an urgent third and a deferred remainder costs a
second pass over the same files, and the deferred half would have been rebased
over whatever #71 does to them.

The argument for the three urgent pieces stands as the reason this project goes
first at all:

| piece | size | why not to wait |
| --- | --- | --- |
| **the health-check fix** | one line in `Dockerfile` | it makes every other number in this document honest, and it is the difference between 19 useful lines a day and 2,922 |
| **personal data out of the logs** | ~5 call sites | every day it waits is another day of email addresses landing in a log that is about to gain seven-day retention *and* an offsite copy. The offsite copy is what changes this from tidiness to something worth doing first |
| **the backup** | a script and a bucket | the only failure in the whole workstream that is **unrecoverable**. Everything else here is discomfort; losing the VM today loses every game ever played, and the exposure grows with each day the site stays up |

**One interaction to be aware of, and it is now the only reason to hold anything
back.** `/status` (Part 7) and the sweep task (#166) touch the same area as #71's
chunk A, so building the endpoint before #71 risks rework. Nothing in the two
deliveries above touches it: the health check is a `Dockerfile` line, the logging
edits are five call sites, and the backup is entirely outside the application. So
**Part 7 is the piece that waits**, and it is adjacent work rather than part of
this project's scope.

---

## Part 10 — Impacted artefacts

Every artefact this project touches, and what it does afterwards that it did not
before (D27). **Provisional** until the test approach is agreed, since the schema
test is itself an artefact.

Named by D26's convention: a repository path where there is one, `production:`
plus an absolute path on the host, and the provider's own name for a cloud
resource.

### In the repository — six modified, two new

The diff carries the detail here; these summaries carry the intent above it.

| artefact | | what it does afterwards |
| --- | --- | --- |
| `Dockerfile` | modified | the web health check fetches `/version.txt` from the site instead of polling Caddy's admin API — it proves routing, the file server and the static build, and writes nothing |
| `crates/server-game/src/main.rs` | modified | the subscriber emits **JSON to stdout**. Human-readable output becomes a rendering applied at reading time rather than the stored form |
| `crates/server-game/src/app/auth.rs` | modified | four events stop carrying `display_name`, and the unknown-email reset stops carrying **the email address**. What is left identifies the account to somebody with database access and to nobody else |
| `crates/server-game/src/email.rs` | modified | mail events carry `player_id` and a message kind rather than the recipient address and subject |
| `docker-compose.yml` · `docker-compose.preview.yml` | modified | both services log through the **journald** driver, so the store belongs to the host and survives the container recreation that discards everything today |
| `docs/4.7-log-events.md` | **new** | the event catalogue, and — because of the test below — the **declared schema** the code is measured against. It is a reference document that is also a gate |
| `crates/server-game/tests/` — the schema comparison | **new** | renders every event through the real JSON layer and fails CI when a field appears that `4.7` does not declare. It proves code and document **agree**; whether the document is **right** is a person's job |
| `scripts/check-log-hygiene.sh` | **new** | the **project's** test: drives the five personal-data paths against a preview or rehearsal stack and fails if an address or a display name reaches the log, if any line is not valid JSON, or if a deploy discarded the history |
| `scripts/restore-backup.sh` | **new** | fetches the newest backup, verifies it opens, and loads it into a fresh volume — so the restore drill is re-runnable rather than a thing done once in August |
| `docs/3.4-production-environment.md` | modified | documents the host artefacts below, the backup procedure, the pre-authenticated request's expiry date, and the restore drill |

### Outside the repository — five, all new but one

**These entries are the record.** There is no diff anywhere, so what is written
here has to be enough to do it again from nothing — which is also what makes this
half of the table the answer to *"what else was on that box?"*

| artefact | | what it does afterwards |
| --- | --- | --- |
| `production:/etc/systemd/journald.conf.d/zz-tile-lite-elite.conf` | **new** | `SystemMaxUse=100M`, `MaxRetentionSec=7d`. Sets seven-day retention and a size backstop that will not bind before the age rule does |
| `production:/etc/systemd/journald.conf.d/50-cap.conf` | modified | the existing 50 M cap, set deliberately on 2026-07-30, doubled rather than deleted — 50 M would bind first and make seven days quietly untrue |
| `production:` the backup script and its systemd timer | **new** | takes a consistent snapshot daily, uploads it under a dated name, alerts on failure and keeps the previous upload if this one fails |
| `OCI bucket tile-lite-elite-backups` | **new**, created 2026-08-21 | holds the backups. Standard tier, private, **object versioning on** — which is what closes the one remaining way a leaked credential could destroy a backup |
| `OCI` write-only pre-authenticated request | **new** | lets the VM upload and nothing else. Tested: it cannot read, list or delete, and deleting it revokes access immediately. Its expiry date is recorded in `docs/3.4` |
| `OCI alarm` — backup did not arrive | **new** | mails the owner when a day passes without a new object. It is what makes the PAR's expiry announce itself rather than being discovered when the database is gone |

**Seventeen artefacts of which six leave no trace in git**, which is the argument
for the table existing at all: a list that had quietly meant *files changed*
would have described half of this project.

**Three of the seventeen are test tooling, and two of those were missing** until
the owner asked twice — first whether the tests in Part 8 produced any scripts,
then noticing that the one added *ran in production* and none tested the project
itself. That is D25's *"the list stays provisional until the test approach
settles"* happening in practice rather than in principle, and it is also the
answer to why the artefact list is worth a heading of its own: nobody spots a
missing row in a paragraph.

---

## Open questions for review

1. **Seven days: promise or capacity?** If a promise, logrotate matches it and
   syslog stops being a five-week archive (Part 4).
   **Answered: capacity.** Owner: *"if we only store ids then it is only
   identifiable with access to the database, in which case the logs don't
   matter."* Right, and it is consistent with *The limit of the claim* above: the
   ids are pseudonymous, so a leaked log on its own identifies nobody, and the
   sensitive copy is the database — which is governed separately and much more
   tightly. **So seven days is a disk-space number and may be tuned freely**,
   logrotate need not be made to match it, and syslog's five-week archive stops
   being a problem to solve.
2. **The catalogue test** — build the source scan, or rely on discipline
   (Part 1)?
   **Answered: neither — the document declares the schema and a test compares
   the emitted fields to it.** Written up in Part 1; it is a better answer than
   either option offered, because it catches an undocumented *field* and not
   merely a missing event.
3. **Health probes recorded locally, or only in OCI** (Part 3)?
   **Answered: OCI only.** Owner: *"I don't see any value in storing health
   checks if OCI records outages."* Agreed — and it removes the largest single
   source of log volume rather than merely bounding it. What is given up is the
   near-miss: a probe that answered slowly is a signal OCI's up/down view does
   not carry. Not worth a local log; if it ever matters, it is a latency metric
   and not a line of text.
4. **Sequencing** — do the three early pieces stand, or does everything wait for
   #71 (Part 9)?
   **Answered: all of it goes before #71.** Owner: *"we can do those things ahead
   of #71, we can do all of it ahead of #71 if that is easier."* It is easier —
   splitting the project into an urgent third and a deferred remainder costs a
   second pass over the same files, and the deferred part would have been rebased
   over whatever #71 does to them.
5. **One note or two** — this covers #174 and #175; splitting is easy if review
   prefers a document per issue.
   **Answered: one.** Owner: *"this is one project and should have one design
   even if it covers multiple requirements and deliveries."* Which is a general
   rule rather than an answer about this document, and it is now recorded as such
   in the glossary under D18 — **the design belongs to the project**, and #174
   and #175 are two requirements of one project, not two projects.

Refs #174, #175, #176, #166, #90, #136, #40
