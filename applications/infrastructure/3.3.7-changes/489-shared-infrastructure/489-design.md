# Shared infrastructure run as an application

The design for **project #489**, in the Operations & Infrastructure workstream.
It takes requirement #486, which applies D73 (#484): the programme runs a
second application, Dark Portal, and what the applications share becomes an
application of its own. Each application has a host of its own.

*Nothing here is built.* This is the scope-stage design: the as-is, the target,
and the decisions taken. When it is complete, the design moves into
the programme's living documents (owner, 2026-10-14) and this note is deleted.

## The state today

Everything about the hosts is Tile Lite Elite's, and is described in its own
documents:

| what | where it is described | what assumes one application |
| --- | --- | --- |
| two Oracle Always Free VMs, `VM.Standard.E2.1.Micro`: 1 OCPU, 1 GB, x86_64 | docs/3.4 *Building a host* | the instructions build a host for this application |
| ingress TCP 22, 80, 443 and UDP 443 in the subnet's security list | docs/3.4, docs/4.8 | 80 and 443 are published by this application's Caddy container |
| the domain `tileliteelite.com`, registered at GoDaddy, an A record to production | `Caddyfile`'s header comment | one name, one site |
| HTTPS from Caddy's own Let's Encrypt HTTP and TLS-ALPN challenges | docs/3.4, `Caddyfile` | these challenges need ports 80 or 443, which only one process per host can hold |
| OS packages, reboots and Docker kept current | docs/3.4 *Keeping the hosts current*; `check-hosts.sh` | a host change is a delivery of this application, with a letter milestone on its production version |
| capacity: 469 MB used of a 954 MB ceiling, about 480 MB free | `docs/reports/capacity_plan/TLE_CP_2026_09.md` | the plan measures one application |

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

## Non-functional design

| question | answer |
| --- | --- |
| capacity | the hosts' capacity plan carries each host's resources against its application's footprint: Tile Lite Elite's 954 MB VMs, Dark Portal's 6 GB A1 VM; each application's own plan covers its rate limits and bottlenecks |
| failure | none shared, because no host or component serves both applications; each fails alone |
| limits and timeouts | none new, because nothing is added between a user and an application |
| secrets and access | none new, because Dark Portal's deploy and tunnel use SSH, as Tile Lite Elite's do. Production access stays the owner's to run |

## Still to design

- which documents and scripts move from this repository to
  `delphside/infrastructure`: docs/3.4's host sections, `check-hosts.sh`, the
  host rows of docs/4.8, and the host-level part of the capacity plan;
- how `verify.sh` in each application is triggered after a host delivery;
- the test approach for a host delivery.
