# 3.1.3 Tile Lite Elite capacity plans

Tile Lite Elite's answers to the [capacity plan template](../../../docs/templates/capacity-plan.md). The plans are `TLE_CP_<yyyy>_<mm>.md` in this folder, with their data in `measurements.csv` and their charts in `charts/`.

**Who writes it.** Claude measures and writes it; Steve reviews it (delphside/tile-lite-elite#291 R2). The recurrence is a date in delphside/tile-lite-elite#291's body, `Next capacity plan due: <date>`, and writing a plan moves that date on a month.

**Where the numbers come from.** The application posts nothing, because the instance principal is a host credential (D49). Host figures are read on the box; games and accounts come from the admin CLI over loopback. Both are production access, so the owner runs them (the production access rule in the programme's CLAUDE.md).

## The rows of "What is consumed, against what ceiling"

| | consumed | ceiling | headroom |
| --- | --- | --- | --- |
| **memory** | | | |
| — server container | | | |
| — web container | | | |
| **disk** | | | |
| — the database volume | | | |
| — pre-deploy snapshots | | `SNAPSHOT_KEEP` (5) | |
| — Docker images | | | |
| — `/var/log/syslog*`, the journal's plain-file copy ([Tile Lite Elite's 4.3.4](https://github.com/delphside/tile-lite-elite/blob/main/docs/4.3.4-production-environment.md#journald-not-the-container), delphside/tile-lite-elite#438) | | logrotate: 4 weekly, gzipped | |
| **journal** | | | |
| **CPU** | | | |
| **games in the database** | | | |
| **accounts** | | | |
| **Resend email quota**: sent and received alike, the game's email and the service desk's ([#515](https://github.com/delphside/tile-lite-elite/issues/515)) | | 100 a day, 3,000 a month (free plan) | |

## How the disk rows are measured

On the VM (a production read):

```bash
df -h /
docker system df
sudo du -sh /var/lib/docker/volumes/tile-lite-elite-data ~/tile-lite-elite/snapshots
du -ch /var/log/syslog* | tail -1
journalctl --disk-usage
```

## How the email quota row is measured

The owner reads the month's sent and received counts, and the busiest day's, on the usage page of Resend's dashboard. Every email received counts against the quota as well as every email sent, so a flood of inbound mail could stop the game's verification and invitation emails for the rest of the day. Nothing is done about it until the headroom shows a need.
