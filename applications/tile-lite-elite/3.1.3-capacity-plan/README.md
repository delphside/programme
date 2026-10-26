# 3.1.3 Tile Lite Elite capacity plans

Tile Lite Elite's answers to the
[capacity plan template](../../../docs/templates/capacity-plan.md). The plans
are `TLE_CP_<yyyy>_<mm>.md` in this folder, with their data in
`measurements.csv` and their charts in `charts/`. Who writes and reviews each
plan is the `capacity-plan` activity in
[1.4](../../../docs/1.4-programme-activities.md). The next one is due on the
date in delphside/tile-lite-elite#291's body, in the form
`Next capacity plan due: <date> — **Claude**`, which Claude moves on a month
once the owner has reviewed the plan.

**Where the numbers come from.** The owner reads every figure by hand. All but
the two quotas are production reads, which are the owner's (the programme's
[`CLAUDE.md`](../../../CLAUDE.md)).

| Rows | Source | Command |
| --- | --- | --- |
| memory, swap and CPU | the production host | `uptime`, `free -m`, `docker stats --no-stream` |
| disk and journal | the production host | [*How the disk and journal rows are measured*](#how-the-disk-and-journal-rows-are-measured) |
| games in the database and accounts | the admin CLI over loopback | `sa --json games list --status <status>` for each status, `sa --json users list`, `sa size`, `sa scheduler-health` |
| Resend email quota | Resend's dashboard | [*How the email quota row is measured*](#how-the-email-quota-row-is-measured) |
| GitHub Actions minutes | the GitHub organisation's billing overview | the month-to-date minutes, read there |

## The rows of "What is consumed, against what ceiling"

| Resource | Consumed | Ceiling | Headroom |
| --- | --- | --- | --- |
| **memory** | | | |
| — server container | | | |
| — web container | | | |
| — swap | | | |
| **disk** | | | |
| — the database volume | | | |
| — pre-deploy snapshots | | `SNAPSHOT_KEEP` (5) | |
| — Docker images | | | |
| — `/var/log/syslog*`, the journal's plain-file copy ([Tile Lite Elite's 4.3.4](https://github.com/delphside/tile-lite-elite/blob/main/docs/4.3.4-production-environment.md#journald-not-the-container)) | | logrotate: 4 weekly, gzipped | |
| **journal** | | 100 MB, 7 days (`SystemMaxUse`, `MaxRetentionSec`) | |
| **CPU** | | | |
| **games in the database** | | | |
| **accounts** | | | |
| **Resend email quota**: sent and received alike, the game's email and the service desk's | | 100 a day, 3,000 a month (free plan) | |
| **GitHub Actions minutes**: private repositories | | 2,000 min a month (GitHub Free) | |

## How the disk and journal rows are measured

On the production host:

```bash
df -h /
docker system df
sudo du -sh /var/lib/docker/volumes/tile-lite-elite-data ~/tile-lite-elite/snapshots
du -ch /var/log/syslog* | tail -1
journalctl --disk-usage
```

## How the email quota row is measured

The owner reads the month's sent and received counts, and the busiest day's,
on the usage page of Resend's dashboard. Received mail counts against the
quota, so a flood of inbound mail could stop the game's verification and
invitation emails for the rest of the day.
