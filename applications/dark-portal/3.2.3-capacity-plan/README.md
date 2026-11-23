# 3.2.3 Dark Portal capacity plans

Dark Portal's answers to the
[capacity plan template](../../../docs/templates/capacity-plan.md):

- the plans, named `DP_CP_<yyyy>_<mm>.md`, the first being
  [`DP_CP_2026_10.md`](DP_CP_2026_10.md)
- their data, in [`measurements.csv`](measurements.csv)
- their charts, in [`charts/`](charts)

Each plan follows the `capacity-plan` activity in
[1.4](../../../docs/1.4-programme-activities.md), which also says who writes and
reviews it.
[Infrastructure's 3.3.3](../../infrastructure/3.3.3-capacity-plan/README.md)
indexes the plans.

These plans carry Dark Portal's rows against their ceilings: those of its hosts,
`dark-portal` (production) and `dark-portal-nonprod`, and those of its bucket,
the Blizzard API quota and the account's Always Free allowance.

**Where the numbers come from**: every figure is read by hand. A read of
production is Claude's, over SSH, where it can reach production, and the
owner's whenever he chooses (the programme's
[`CLAUDE.md`](../../../CLAUDE.md)). The Oracle Cloud console is the owner's.

| Rows | Source | How it is read |
| --- | --- | --- |
| the hourly job's and the analysis's memory, CPU, time and spill | the `sizing/` test, then `dark-portal` and `dark-portal-nonprod` | the `sizing/` scripts of [Dark Portal's repository](https://github.com/delphside/dark-portal/tree/main/sizing), then the job's own timings, to come with delphside/dark-portal#7 *#5 WP B Del 2 of 5: consumable profiles* |
| stored data on the host | `dark-portal` | `du -sh` of the data directory, to be named with delphside/dark-portal#7 |
| stored data in the bucket | the Oracle Cloud console | the bucket's size, read there |
| Blizzard API quota | the request counts of the collector, which do not exist yet | to come with delphside/dark-portal#7 |
| host memory, CPU and disk | `dark-portal` | [*How the host rows are measured*](#how-the-host-rows-are-measured) |
| Oracle Always Free, account-wide | the Oracle Cloud console | the usage page, read there |

## The rows of *What is consumed, against what ceiling*

The job, production analysis, stored-data-on-the-host and host rows are
`dark-portal`'s. The bucket and Blizzard API quota rows are Dark Portal's own
and belong to no host. The shape of each host is in
[6.3.4](https://github.com/delphside/infrastructure/blob/main/docs/6.3.4-hosts.md#the-hosts).
The memory limits are DuckDB's `memory_limit` setting.

| Resource | Consumed | Ceiling | Headroom |
| --- | --- | --- | --- |
| **the hourly job's memory** | | `memory_limit` 1 GB, from delphside/dark-portal#12 *MAIN PROJECT: Production sizing* | |
| **the hourly job's CPU** | | 1 OCPU through the hour | |
| **the hourly job's time** | | 60 min to the next collection | |
| **ad-hoc analysis memory** (DuckDB, production) | | `memory_limit` 4 GB, from delphside/dark-portal#12 | |
| **ad-hoc analysis spill** (production) | | 5 GB of the host's disk kept free for spill, proposed on delphside/dark-portal#12 | |
| **stored data on the host** | | a few days of bronze (the source snapshots), a number not yet set, from delphside/dark-portal#5 *MAIN PROJECT: Dark Portal v1*; none set for silver and gold | |
| **stored data in the bucket** | | one year of bronze once the lifecycle rule of delphside/dark-portal#5 exists | |
| **Blizzard API quota** | | 36,000 requests an hour, 100 a second (Blizzard's published client limit) | |
| **host memory** | | 6 GB (the VM's shape) | |
| **host CPU** | | 1 OCPU, burstable off (the VM's shape) | |
| **host disk** | | 47 GB (the boot volume) | |
| — Docker images | | | |

The first row is `dark-portal-nonprod`'s, whose VM takes 3 OCPU and 18 GB of the
account's Always Free A1 allowance. The rest are account-wide.

| Resource | Consumed | Ceiling | Headroom |
| --- | --- | --- | --- |
| **ad-hoc analysis memory** (DuckDB, `dark-portal-nonprod`) | | `memory_limit` 8 GB, from delphside/dark-portal#12 | |
| **Oracle Always Free, account-wide** | | | |
| — Ampere A1 cores and memory | | 4 OCPU, 24 GB across all A1 instances (Oracle's Always Free terms) | |
| — block storage | | 200 GB across all volumes (Oracle's Always Free terms) | |
| — Object Storage | | 20 GB across all tiers (Oracle's Always Free terms) | |

## How the host rows are measured

On `dark-portal`:

```bash
free -h && nproc
df -h /
docker system df
vmstat 5 12   # the st column: steal, expected near zero on whole cores
```
