# 3.2.3 Dark Portal capacity plans

Dark Portal's answers to the
[capacity plan template](../../../docs/templates/capacity-plan.md). The plans
will be `DP_CP_<yyyy>_<mm>.md` in this folder, with their data in
`measurements.csv` and their charts in `charts/`. None is written yet: the first
follows the first collection spike, which measures the empty rows below, and
sets the recurrence.

**Who writes it.** Claude measures and writes it; the owner reviews it.

**Where the numbers come from.** Host figures are read on the `dark-portal`
host; the owner runs the commands over SSH. The Blizzard API figures come from
the collector's own counts, once it exists.

**What is planned here.** Dark Portal's own footprint. The host's memory, CPU
and disk are Infrastructure's to plan
([489 design](../../infrastructure/3.3.7-changes/489-shared-infrastructure/489-design.md#who-plans-which-capacity-both-at-different-levels));
they are held here, like the host in [3.2.2](../3.2.2-artefacts.md#the-host),
until Infrastructure has a capacity plan of its own.

## The rows of "What is consumed, against what ceiling"

| | consumed | ceiling | headroom |
| --- | --- | --- | --- |
| **the collector's memory** | | not yet set (DP: Application Architecture) | |
| **the analysis's memory** (DuckDB) | | not yet set (DP: Market Analysis) | |
| **stored data** | | not yet set: retention is DP: Application Architecture's | |
| **Blizzard API quota** | | 36,000 requests an hour, 100 a second (Blizzard's published client limit) | |

Held until Infrastructure plans them:

| | consumed | ceiling | headroom |
| --- | --- | --- | --- |
| **host memory** | | 6 GB (the VM's shape) | |
| **host CPU** | | 1 OCPU, not burstable (the VM's shape) | |
| **host disk** | | the boot volume's size, not yet read | |
| — Docker images | | | |
| **Oracle Always Free, account-wide** | | | |
| — A1 cores and memory | | 4 OCPU, 24 GB across all A1 instances (Oracle's Always Free terms) | |
| — block storage | | 200 GB across all volumes (Oracle's Always Free terms) | |

## How the host rows are measured

On the host:

```bash
free -h && nproc
df -h /
docker system df
vmstat 5 12   # the st column: steal, expected near zero on whole cores
```
