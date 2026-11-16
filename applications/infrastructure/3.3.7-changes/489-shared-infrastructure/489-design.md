# Shared infrastructure run as an application

The design for **project #489**, in the Operations & Infrastructure workstream.
It takes requirement #486, which applies D73 (#484): the programme runs a
second application, Dark Portal, and what the applications share becomes an
application of its own. Each application has a host of its own.

This is the design: the as-is, the target, the decisions taken and what
moves where. Work package #557 builds it. Once #557 lands, the design lives in
the documents it names under [*What moves where*](#what-moves-where), and this
note is deleted (owner, 2026-10-14).

## The state at scope

At scope, on 2026-10-27, everything about the hosts was Tile Lite Elite's, and
was described in its own documents:

| what | where it is described | what assumes one application |
| --- | --- | --- |
| two Oracle Always Free VMs, `VM.Standard.E2.1.Micro`: 1 OCPU, 1 GB, x86_64 | docs/3.4 *Building a host* | the instructions build a host for this application |
| ingress TCP 22, 80, 443 and UDP 443 in the subnet's security list | docs/3.4, docs/4.8 | 80 and 443 are published by this application's Caddy container |
| the domain `tileliteelite.com`, registered at GoDaddy, an A record to production | `Caddyfile`'s header comment | one name, one site |
| HTTPS from Caddy's own Let's Encrypt HTTP and TLS-ALPN challenges | docs/3.4, `Caddyfile` | these challenges need ports 80 or 443, which only one process per host can hold |
| OS packages, reboots and Docker kept current | docs/3.4 *Keeping the hosts current*; `check-hosts.sh` | a host change is a delivery of this application, with a letter milestone on its production version |
| capacity: 469 MB used of a 954 MB ceiling, about 480 MB free | `docs/reports/capacity_plan/TLE_CP_2026_09.md` | the plan measures one application |

Since then, before this design was complete, much of the target has arrived:

| what | where it is now |
| --- | --- |
| the repository `delphside/infrastructure` | created 2026-10-16, with no commits; its issues are on the programme board |
| one answer on host changes (R9) | [1.2 §2.15](../../../../docs/1.2-change-lifecycle.md#host-maintenance-is-the-infrastructure-applications), §2.2.1, `CLAUDE.md`, the ship-a-change and triage skills, and each application's 3.n.2 say host maintenance is Infrastructure's dated delivery. Tile Lite Elite's 4.3.4 *Changing production configuration* still says a letter milestone |
| the host read | the programme's `scripts/board/board-hosts.py`, which Tile Lite Elite's `check-hosts.sh` calls and the weekly `host-currency` activity runs ([1.4](../../../../docs/1.4-programme-activities.md)) |
| the hosts each application has | the `[hosts.*]` tables of each application's `app-profile.toml` |
| host maintenance work packages | delphside/infrastructure#1 to #4, raised by `host-currency` |
| Dark Portal's host | its own A1 VM, recorded in Dark Portal's 3.2.2 until Infrastructure has an artefact register |

## The target

| | target |
| --- | --- |
| **who** | the infrastructure application, owned by Operations & Infrastructure, with its own repository `delphside/infrastructure` and its own GitHub project and board |
| **what it holds** | the hosts, networking (domain, DNS, ports, firewall), host security and the hosts' capacity plan. Its programme records live in its folder in `delphside/programme` (#485, R6) |
| **what it serves** | each application, which depends on it only as its host. No application depends on another |
| **how it changes** | a host change is its delivery. Afterwards the application on that host runs its own verification |
| **how it coordinates** | a project that affects an application, by a change or only by its regression testing, raises a requirement in that application's repository and coordinates the work. One team runs every board, so a requirement and its dependency link are enough |

## Decisions

### Where Dark Portal runs: a host of its own

Dark Portal runs on its own Oracle Always Free A1 VM, `aarch64`, built on
2026-10-21 (delphside/dark-portal#6). An ETL and analysis application does not
belong beside a transactional one, and it may want the memory (owner,
2026-10-21, delphside/dark-portal#4). No host is shared between applications (owner, 2026-10-24).

### How Dark Portal is reached: privately

Dark Portal has one user, the owner, so it is not public (owner, 2026-10-14).
Its host takes SSH only, and Dark Portal is reached through an SSH tunnel from
the owner's machine, so nothing needs a certificate. A WoW add-on runs inside
the game client and has no network access of its own, so publishing one would
not make the server public either.

### How infrastructure deliveries are numbered: by date

The infrastructure application keeps its own delivery log, and numbers each
delivery by date and the day's sequence, `YYYY.MM.DD-n` (owner, 2026-10-14).
Its deliveries change packages and configuration, not a build, so a semver's
parts would measure nothing. To apply to docs/5.1's letter-milestone rule and
§2.2.1's routine-update table, which assume host work rides an application's
version.

### Who plans which capacity: both, at different levels

Capacity is planned at two levels (owner, 2026-10-16). The infrastructure
application plans the VMs' resources: memory, CPU and disk on each host,
against the measured footprint of the application on it. Each application plans
its own: rate limiting, its bottlenecks, and what its users can drive it to.
So Tile Lite Elite keeps a capacity plan, without the host totals, and the
hosts' plan takes each application's footprint from it.

### What the programme board carries: Infrastructure's issues

Infrastructure's issues are on the one programme board, beside every other
application's, as its [README](../../README.md) says. R1's "its own GitHub
project and board" is met by the programme board, because one team runs every
board and the board already shows each repository's issues.

### Platforms by workload: when a third application arrives

R8's platforms by workload class are designed when an application arrives that
could share a host. Today's two applications each have a host of their own, one
transactional (Tile Lite Elite) and one batch (Dark Portal), so batch and
transactional work never share a host. R8 leaves #489 as a requirement on hold.

### The hosts' capacity: in each application's plan

Each application's capacity plan carries its own host against its ceiling,
because no host is shared: Tile Lite Elite's 3.1.3 and Dark Portal's 3.2.3
already measure memory, CPU and disk on their own hosts. Infrastructure's 3.3.3
indexes them. A hosts' plan of its own starts when a host is first shared. The
two levels of 2026-10-16 still hold: each application's plan has its host rows
and its own rows (rate limits, bottlenecks).

## What moves where

The host read and the host lists do not move. `board-hosts.py` is already the
programme's; `check-hosts.sh` is Tile Lite Elite's caller of it, run by its
`verify.sh`; and each application's `app-profile.toml` says which hosts are its
own. So no script moves, and #557 changes documents only.

| fact | from | to |
| --- | --- | --- |
| how a host is built: the Oracle account and Pay As You Go, the instance, the SSH alias, the network, Docker, the swapfile and the base packages | Tile Lite Elite's 4.3.4 *Building a host*, steps 1 to 7; Dark Portal's build runbook | `delphside/infrastructure` `docs/6.3.4-hosts.md` *Building a host*, one table of each host's shape |
| networking: the domain, DNS, ports and the security list, and Dark Portal's SSH only | Tile Lite Elite's 4.3.4 and `Caddyfile` header; Dark Portal's 3.2.2 *Not yet recorded* | 6.3.4 *Networking* |
| keeping the hosts current: the host layers, the upgrade and the reboot | Tile Lite Elite's 4.3.4 *Keeping the hosts current* | 6.3.4 *Keeping the hosts current*; Tile Lite Elite keeps its own layers (Dependabot, `cargo audit`, its release) |
| how a host maintenance delivery is made | Tile Lite Elite's 4.3.4 *Changing production configuration*, for packages and reboots | 6.3.4 *Making a host change* |
| the hosts' artefacts: each VM, its host-maintenance packages, journald caps and iptables, the network, the domain, the SSH keys and the Oracle account | Tile Lite Elite's 3.1.2 and Dark Portal's 3.2.2 rows marked `Other, host maintenance`, and the VMs | Infrastructure's 3.3.2; the applications' registers link to it |
| the delivery log | none | Infrastructure's 3.3.1, numbered by date |
| the capacity plans | the applications' | stay; Infrastructure's 3.3.3 indexes them |
| what Infrastructure is | this note | Infrastructure's 3.3.6 profile, and the repository's `README.md` and `CLAUDE.md` |

What stays with an application: building its own stack on a host (its `.env`,
its jobs and units, its first deploy, its HTTPS), and the packages it needs,
which are its Production Release.

## How an application verifies itself after a host delivery

A host maintenance work package carries, in its technical tests, a box for
Claude to run the verification of the application on that host, and to trust
its exit status: Tile Lite Elite's `scripts/deliver/verify.sh`; Dark Portal's,
once its first release builds one, and until then its host's
`check-hosts`-style read and an SSH login. No trigger is automated: a host
delivery is made by hand, so its verification is a step of it.

## The test approach for a host delivery

Each host maintenance work package's test approach is the same:

- the change is made on the host's pair first (rehearsal, or Dark Portal's
  non-production VM), then on production;
- `board-hosts.py` afterwards reports nothing owed for that change, and the
  pair agrees;
- the application on the host verifies itself, as above.

6.3.4 *Making a host change* holds it, and delphside/infrastructure#1 already
follows it.

## Non-functional design

| question | answer |
| --- | --- |
| capacity | the hosts' capacity plan carries each host's resources against its application's footprint: Tile Lite Elite's 954 MB VMs, Dark Portal's 6 GB A1 VM; each application's own plan covers its rate limits and bottlenecks |
| failure | none shared, because no host or component serves both applications; each fails alone |
| limits and timeouts | none new, because nothing is added between a user and an application |
| secrets and access | none new, because Dark Portal's deploy and tunnel use SSH, as Tile Lite Elite's do. Production access stays the owner's to run |
