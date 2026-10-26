# 3.2.3 Dark Portal capacity plans

Dark Portal's answers to the [capacity plan
template](../../../docs/templates/capacity-plan.md). The plans are named
`DP_CP_<yyyy>_<mm>.md` and kept in this folder, with their data in
`measurements.csv` and their charts in `charts/`. The first follows the memory
sizing test of delphside/dark-portal#12, which gives the first memory, CPU and
disk figures; after that each plan follows the `capacity-plan` activity in
[1.4](../../../docs/1.4-programme-activities.md), which also says who writes and
reviews it.

**Where the numbers come from.**

| Rows | Source | Read by |
| --- | --- | --- |
| the collector's and the analysis's memory | the sizing test of delphside/dark-portal#12, then the host | the owner, over SSH |
| stored data | the size of the stored data on the host | the owner, over SSH |
| Blizzard API quota | the collector's own request counts | the owner, over SSH |
| host memory, CPU and disk | [*How the host rows are measured*](#how-the-host-rows-are-measured) | the owner, over SSH |
| Oracle Always Free, account-wide | the Oracle Cloud console | the owner |

**What is planned here.** The host's memory, CPU and disk are
Infrastructure's to plan
([489 design](../../infrastructure/3.3.7-changes/489-shared-infrastructure/489-design.md#who-plans-which-capacity-both-at-different-levels));
they are held here until Infrastructure has a capacity plan of its own.

## The rows of "What is consumed, against what ceiling"

| Resource | Consumed | Ceiling | Headroom |
| --- | --- | --- | --- |
| **the collector's memory** | | not yet set; DP: Application Architecture sets it | |
| **the analysis's memory** (DuckDB) | | not yet set; DP: Market Analysis sets it | |
| **stored data** | | not yet set; DP: Application Architecture sets retention | |
| **Blizzard API quota** | | 36,000 requests an hour, 100 a second (Blizzard's published client limit) | |

Held until Infrastructure plans them:

| Resource | Consumed | Ceiling | Headroom |
| --- | --- | --- | --- |
| **host memory** | | 6 GB (the VM's shape) | |
| **host CPU** | | 1 OCPU (Oracle CPU), burstable off (the VM's shape) | |
| **host disk** | | 47 GB (the boot volume) | |
| — Docker images | | | |
| **Oracle Always Free, account-wide** | | | |
| — Ampere A1 cores and memory | | 4 OCPU, 24 GB across all A1 instances (Oracle's Always Free terms) | |
| — block storage | | 200 GB across all volumes (Oracle's Always Free terms) | |

## How the host rows are measured

On the host:

```bash
free -h && nproc
df -h /
docker system df
vmstat 5 12   # the st column: steal, expected near zero on whole cores
```
