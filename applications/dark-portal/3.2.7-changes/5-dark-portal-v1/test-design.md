# Test design specification: consumable profiles

Project: delphside/dark-portal#7 *#5 WP B Del 2 of 5: consumable profiles* · type of change: `functional` · route: `Production Release` · release: not yet set

## 1. Rules

Taken from the design documents at b473b3d (`docs/5.x` on
`claude/project-thread-01pbpu`), delphside/dark-portal#7's body and its
Decisions table. The documents are drafts for delphside/dark-portal#7's design.

| ID | Rule | Source |
| --- | --- | --- |
| R1 | The current auction price of an item can be seen: its lowest price and its fill price. | 5.1.0; 5.2.3 *The price now*; delphside/dark-portal#7 decision 1 |
| R2 | Price history can be seen hourly for 4 weeks, with a daily summary (low, median, volume) kept indefinitely. | 5.1.0; 5.2.3 *History* |
| R7 | Depth: the units listed at or below each price, and turnover per hour as a lower bound. | 5.1.0; 5.2.3 *Depth*, *Flows* |
| R8v | Volume, estimated from listings vanishing between snapshots, can be seen: a certain floor and an inferred estimate side by side. "Beside each margin" waits for stage 3. | 5.1.0; 5.2.3 *Flows*; delphside/dark-portal#7 decision 2 |
| T1 | A snapshot's hour is the UTC hour starting of its `last-modified`: 01:31:40 is 01:00. | 5.2.2 *Times*; 5.4.5 |
| T2 | An event is dated by the hour of the snapshot that first showed it. An hour is *held* where its snapshot was processed. A comparison's `span` is the elapsed hours since the last snapshot held: 1 unless one was missed, null for the first hour collected. A listing's lifetime is the elapsed hours from its posting hour to the hour it was first missing. | 5.2.2 *Times*; 5.4.5 |
| TR | Tiers: **observed** for facts read from a snapshot; **certain** for posted and partly sold; **inferred** for sold, expired and cancelled. | 5.2.2 *How sure a fact is*, the events table |
| Q1 | An item's queue is ordered by unit price ascending, then auction ID descending; position 1 is the head. `units_ahead`, `units_at_or_below` and `lowest` are as 5.4.5 defines them. | 5.1.1; 5.4.5 |
| Q2 | Silver's live listings, as of the last hour processed, are marked against the current snapshot C: intact (same quantity), reduced (lower quantity) or gone (absent). | 5.2.2 *The events* |
| Q3 | The front is every listing ahead of the item's first intact listing; with none intact, the whole queue. Fronts are per item. | 5.2.2 |
| EV-1 | An ID in C that is not live is `posted`: its quantity, certain. An ID at or below the highest live ID is still posted, and logged as a warning naming it. An ID that ended and reappears is logged the same way and left out. | 5.2.2 |
| EV-2 | A reduced listing is `partly_sold`: the drop, certain. One behind an intact listing is a sale too, and is logged as a warning naming it. | 5.2.2 |
| EV-3 | A gone listing in the front is `sold`: its quantity, inferred. | 5.2.2 |
| EV-4 | A gone listing behind an intact one is unsold, certain. Its event carries `tie = true` where **every** intact listing ahead of it has the gone listing's price and was first seen in the same snapshot as it. | 5.2.2; 5.4.5 `tie` |
| EV-5 | An unsold listing `expired` (inferred) where its posting hour is known and posting hour + 12, 24 or 48 lies in [C − span, C], the **shortest** such duration recorded; or where its posting hour is unknown and the lower bound of its last band (`SHORT` 0, `MEDIUM` 30 min, `LONG` 2 h, `VERY_LONG` 12 h) is **under** span hours. | 5.2.2; 5.4.5 *Types* |
| EV-6 | Every other unsold listing was `cancelled`, inferred. | 5.2.2 |
| EVW | Each gone listing writes exactly one event, `sold`, `expired` or `cancelled`. `rule` is the rule that chose the kind (EV-3, EV-5 or EV-6; EV-1 and EV-2 for their own events); `tie` marks EV-4's exception; every event carries `hour`, `id`, `item`, `kind`, `units`, `unit_price`, `tier`, `rule`, `tie` and `span`, keyed (`hour`, `id`, `kind`). | 5.2.2; 5.4.2; 5.4.5 |
| L1 | A live listing is one `live_listing` row and one `listing_hour` row per hour seen. `posted` and `posting_*` are null for a listing in the first snapshot collected or first seen after a gap. An intact listing adds a history row and makes no event. | 5.2.2 *A missed hour*, matrix; 5.4.2; 5.4.5 |
| L2 | When a listing ends, its `listing_record` is written and its live and history rows are deleted. The record holds `quantity` when first seen; `first_seen`, `last_seen`, `posted`; `duration` (set only on expiry with a known posting hour); `posting_*` (only where `posted` is known); `ended` (the first hour missing); `outcome`, `outcome_tier`, `tie`; `units_sold` over its life; `end_*` (the queue at the last hour seen); and `end_units_undercut`, the units in listings with higher IDs at a lower price still listed at its last hour. | 5.2.2 *The listing record*; 5.4.2; 5.4.5 |
| L3 | The first snapshot collected has nothing to compare with: its listings become live with no posting hour and it writes no events. Its hour is held, with prices and depth, and with its flows and span null. | 5.2.2 *The events*; 5.4.5 |
| L4 | A rebuild replays bronze in order from its first hour and gives the same silver and gold as an incremental run from that hour. | 5.1.1 *Restarts and recovery*, *Data layers* |
| C0 | `dp collect` collects the *current hour*, fixed when it starts: the hour starting in which it runs, or the hour before where it starts within that hour's retry window (a run delayed to 11:10 takes 10:00). | 5.2.1 *The snapshot* |
| C1 | If bronze holds the current hour's file, `dp collect` exits `0` at once. | 5.2.1 step 1 |
| C2 | A cached token is reused while it has more than the token margin (1 h) left; a token lasts 24 h. A request refused (401) with a cached token takes a new token once. | 5.2.1 step 2, *When it fails*; 5.4.1 |
| C3 | `GET …commodities?namespace=dynamic-eu`. If `last-modified`'s hour is before the current hour, wait the poll interval (2 min) and repeat until the retry window closes (:25 past the next hour); the hour is then a gap, recorded by `dp transform`. If it is after the current hour, exit `2`. | 5.2.1 steps 3–4; 5.4.1 |
| C4 | The snapshot is parsed as a stream and written under a temporary name; `dp collect` then takes the lock and renames it to `bronze/commodities/eu/YYYY-MM-DDTHH.parquet`, with 5.4.2's columns. | 5.2.1 step 5; 5.4.2 |
| C5 | An unknown listing field is logged as a warning naming it. | 5.2.1 |
| C6 | `dp items` fetches each item ID in bronze's snapshot files with no response in bronze's item files (`static-eu`, `en_GB`), at 50 a second, and writes one `bronze/items/YYYY-MM-DDTHHMMSS.parquet` per run that fetched any, with `status`. A blip is retried with backoff and then left to the next run; a 401 takes a new token once and asks again, then is left to the next run; a 400, 403, 500, other status or unreadable body is left to the next run; each of these gives the step exit `3`. A 404 is data, not an error: written with status 404 and no body, logged as a warning, and asked again only by `dp daily`. The profile shows the item's ID until it has a response. | 5.2.1 *Item data*, *When it fails*; 5.4.1; 5.4.2; 5.4.5 |
| C7 | Requests stay within Blizzard's 36,000 an hour and 100 a second. | 5.2.1 *Limits* |
| C8 | Blips are retried with backoff from 30 s, doubling to 5 min, or after the response's `Retry-After`. Timeouts are 60 s for the snapshot and 10 s otherwise. | 5.2.1; 5.4.1 |
| C9 | The hourly timer starts at :35; the daily timer at 00:50 UTC. The timers are persistent. | 5.4.1; 5.1.1 *Restarts and recovery* |
| H0 | `dp hourly` runs `collect`, `items`, `transform` and `export`, in that order, and runs the last three whatever `collect` returned. Each can be run alone. It exits with `collect`'s exit where that is not `0`; otherwise `3` where a later step failed; otherwise `0`. | 5.1.1; 5.2.1 *When it fails* |
| H1 | Every `dp` subcommand that writes takes the VM-wide lock (`DP_LOCK_FILE`), whether a timer or a person starts it. It waits up to 10 minutes, then exits `75`. `dp collect` takes it only to rename its file, so polling holds no lock; `dp hourly` then holds it for the steps after. An ad hoc query takes no lock and is bounded by `DP_ADHOC_MEMORY_LIMIT` and `DP_ADHOC_THREADS`. | 5.1.1; 5.2.1; 5.4.1 |
| H2 | The pivot is the bronze file. A snapshot error ends `dp collect` with its exit; an `items`, `transform` or `export` error is logged with its type and gives that step exit `3`. | 5.1.1; 5.2.1 *When it fails* |
| H3 | `dp transform` processes every bronze hour after the high-water mark (`processed`'s latest hour), in order, one commit per hour. It records each missing hour in `meta.gap` with `found_at`. A failed hour is reprocessed by the next run. | 5.1.1; 5.2.1; 5.2.2; 5.4.2 |
| H4 | An hour already processed is never processed again. | 5.4.2 `processed` key; 5.1.1 |
| H5 | After a missed hour, the comparison runs from the live listings to C; events are dated to C with the span. | 5.2.2 *A missed hour* |
| H6 | The hour's gold rows (`item_hour`, `price_level_hour`) are written once its events are in: prices and depth from the live listings, flows from the events. | 5.2.2 matrix |
| H7 | The hourly and daily jobs run DuckDB with `memory_limit` 1 GB and `threads` 1. Ad hoc: 1 thread, and 4 GB in production, 8 GB outside it. `DP_CONTAINER_MEMORY` is the ad hoc limit plus 1 GB: 5 GB and 9 GB. | 5.4.1 |
| H8 | A `dp daily` run that exits `75` is restarted by its systemd service after the daily retry interval (15 min), until the daily retries end (03:00 UTC). | 5.1.1; 5.4.1 |
| H9 | A reboot loses no hour that can still be fetched: a run missed while the host was down starts when it is back, and `dp collect` takes the current hour as C0 fixes it. | 5.1.1 *Restarts and recovery*; 5.2.1 |
| P1 | Every commodity in the EU snapshot has a profile (about 10,500), filterable by name, class and subclass. | 5.2.3; delphside/dark-portal#7 decision 3 |
| P2 | Lowest is the lowest unit price in the latest snapshot. | 5.2.3 |
| P3 | Fill price for N is the average unit price of the cheapest N units, with the units it covers; where fewer than N are listed, it covers all and says how many; where none are, it is null. N below 1 is refused. It is held to two decimal places of copper, rounded half away from zero. | 5.2.3; 5.4.2; 5.4.5 |
| P4 | Default N is the median hourly `sold_estimate_units` over the default N window (7 days) ending at the hour, rounded up, at least 1. | 5.2.3; 5.4.2; 5.4.1 |
| P5 | Prices are shown beside the vendor sell price, and beside the vendor buy price (`purchase_price`) where a vendor sells it, null otherwise. | 5.2.3; 5.4.5 |
| P6 | The depth ladder runs from the lowest price up: units at the price, units at or below, and hours = units at or below ÷ the mean hourly sold estimate over the hours held in the 24 h turnover window; *no sales seen* where the window sold nothing. It stops at the first price whose hours reach 48, which it shows, or at the last price. | 5.2.3; 5.4.1 |
| P7 | Flows per hour: posted (EV-1), sold floor (EV-2), sold estimate (floor + EV-3), expired (EV-5), cancelled (EV-6). Posted and the floor are lower bounds; R7's turnover per hour is shown as the sold floor, with the estimate beside it. | 5.2.3 *Flows* |
| P8 | Hourly history for the hourly keep: lowest, fill price for any N, units listed, ladder and flows. | 5.2.3; delphside/dark-portal#7 decision 5 |
| P9 | `dp daily` writes `item_day`: the lowest of any hour; the median hourly fill price at the default N at 00:00 that day (`DECIMAL(18, 2)`), over the hours with any listed, null where none had; posted, floor and estimate, each summing the day's hours that are not null; `hours_held`. A day is closed once each of its 24 hours is processed or recorded as a gap; `dp daily` closes every day that can be closed and is not. | 5.2.3; 5.4.2; 5.4.5 |
| P10 | A missed hour shows as a gap, never as a zero. | 5.2.3 |
| P11 | The `profile` view gives each item at the latest hour: reference columns, `lowest`, the fill price at default N, and each flow's total over the turnover window. | 5.4.2 |
| P12 | The views and macros are defined once in `sql/profiles.sql` over the gold and reference table names; `dp` loads it over the lake; `export/profiles.sql` is views named as those tables over the export's files, then `sql/profiles.sql` unchanged, so a client computes nothing of its own. | 5.1.1; 5.4.2; 5.2.3 *Clients* |
| P13 | An item with no listings in an hour, but listings the hour before, has an `item_hour` row with no lowest price (`lowest` null) and its flows. | 5.2.3 *History*; 5.4.5 |
| P14 | A measure over hours counts only the hours held with a span of 1, since an hour after a gap holds the flows of several. | 5.2.3 *The price now*; 5.2.2 *Times* |
| X1 | Exit `0`: done, with at most warnings. | 1.10; 5.2.1 |
| X2 | Exit `75`: a timeout, 429, 502, 503 or 504 when the retry window closes; `last-modified` still before the current hour when it closes; the lock wait running out. | 5.2.1 |
| X3 | Exit `2`: a new token refused (401), including after a cached one was refused; 403 or 404 on the snapshot; `last-modified` after the current hour; disk full. | 5.2.1 |
| X4 | Exit `70`: Blizzard answers 400, 500 or another status, a body the parser cannot use, or no `last-modified`. | 5.2.1 |
| X5 | Exit `3`: an item lookup (401 included, 404 not), the transform or the export failed after the pivot. | 5.2.1 |
| X6 | Before the pivot a failure leaves no temporary or partial file. Usage errors exit `64`; a signal is unexpected; errors are 1.10's result object; a business error is logged at `INFO`, a technical one at `WARN`. | 1.10 |
| DX | `dp daily`'s pivot is the day's commit. It exits `75` where the lock is held past the wait or the day before cannot yet be closed; `2` on a full disk and `70` on an unexpected error, before the pivot; `3` where a push, a deletion or an item retry fails after it, which the next run repeats; otherwise `0`, an item answering 404 again included. | 5.1.1 *Restarts and recovery* |
| K1 | `dp daily` deletes lake rows older than their keep (hourly gold 4 weeks; daily, silver and `meta` kept), then their files by DuckLake's expiry and clean-up. A keep deletes what is older than it, by the hour or day the row or file is for. | 5.4.2 *Expiry*; 5.4.1 |
| K2 | `dp daily` pushes bronze to the bucket under its host paths, and `daily/item_day.parquet` and `daily/item.parquet`, copies of the export's. It deletes host bronze *snapshot* files older than 7 days once the bucket holds them, or with no bucket (`DP_BUCKET` empty) once past the keep; item files are kept. The bucket keeps `bronze/` a year by its lifecycle rule, and `daily/` indefinitely. | 5.1.1; 5.4.2 *The bucket*, *Expiry*; 5.4.1 |
| K3 | `dp daily` deletes export hour files older than the hourly keep. | 5.4.2 *Expiry* |
| K4 | `dp daily` asks again for each item whose latest response is a 404. | 5.1.1; 5.2.1 *Item data* |
| E1 | `dp export` writes, each under a temporary name then renamed: a `price_level_hour` and an `item_hour` file per committed hour within the hourly keep that the export lacks; `item_day.parquet` and `item.parquet` rewritten; `profiles.sql`. A copy taken mid-run may be uneven; the next copy levels it. | 5.4.2 *The export*; 5.1.1; delphside/dark-portal#7 decision 8 |
| SEC | The client secret comes from `DP_BLIZZARD_CLIENT_SECRET_FILE` and never appears in logs, bronze or the export. | 5.4.1 |
| REF | Reference is fetched once per item in stage 1; `reference.item` takes the latest response with status 200 per item from bronze. | 5.1.1; 5.4.2 |
| BK | The backup is bronze and the daily history. After a lost host, `item_day` and `item` for what is older than bronze are restored from the bucket, and everything else is rebuilt from bronze. | 5.1.1 *Restarts and recovery*, *Data layers* |

### Checked for contradiction

- **X-c6, measures over hours against the daily and profile sums.** P14 says a
  measure over hours counts only span-1 held hours; 5.4.5 says a day's flows sum
  every hour that is not null, which includes an hour after a gap, and P11's
  totals over the turnover window are not said either way. I read P14 as
  governing rates and medians (P4, P6), and the sums as covering every non-null
  hour, so no event is dropped from a total. Open as G10.
- **X-c7, the lock under `dp hourly`.** H1 says `collect` takes the lock only to
  rename and `dp hourly` "then holds it for the steps after". I read it as held
  without release from the rename to the end of `export`. Where `collect` exits
  at step 1 or without a file, `dp hourly` takes it for `items`.
- **X-c8, an unclosable day and the rest of `dp daily`.** DX puts the push,
  deletions and item retry after the pivot, the day's commit. I read an exit
  `75` for an unclosable day as doing none of them that run.
- **X-c4, the `unsold` state.** The diagram keeps the state; the prose says
  it is a step, not a state. Wording only.

## 2. Conditions, grouped into dimensions

- **D1, mark** (not complete): D1.1 intact · D1.2 reduced · D1.3 gone · D1.4
  quantity up, or price changed, on a live ID (G7) · D1.5 an ended ID
  reappearing.
- **D2, place** (complete): D2.1 front · D2.2 the first intact listing · D2.3
  behind an intact listing · D2.4 no intact listing.
- **D3, the intact listings ahead of a gone one** (complete): D3.1 cheaper ·
  D3.2 same price, first seen in another snapshot · D3.3 same price, same
  snapshot (a tie) · D3.4 several, one cheaper and one a tie · D3.5 several, all
  ties · D3.6 a same-snapshot pair with the gone one in the front.
- **D4, new ID** (complete): D4.1 above the highest live ID · D4.2 at or below
  it · D4.3 above the highest live ID but below the highest ID ever seen.
- **D5, posting hour** (complete): D5.1 known · D5.2 first snapshot · D5.3 first
  seen after a gap.
- **D6, p + D against [C − span, C]** (complete): D6.1 C − span − 1 · D6.2 C −
  span · D6.3 inside · D6.4 C · D6.5 C + 1, for D = 12, 24 and 48 · D6.6 two
  durations inside.
- **D7, last band** (complete): D7.1 `SHORT` · D7.2 `MEDIUM` · D7.3 `LONG` ·
  D7.4 `VERY_LONG`.
- **D8, span** (complete for the boundaries): D8.1 1 · D8.2 2 · D8.3 3 · D8.4 12
  · D8.5 13 · D8.6 14.
- **D9, the sequence** (complete): D9.1 first snapshot · D9.2 follows a held
  hour · D9.3 follows a gap.
- **D10, `last-modified` against the current hour** (complete): D10.1 before it
  · D10.2 equal, at :00:00, :31:40 or :59:59 · D10.3 after it · D10.4 missing ·
  D10.5 the host's time zone not UTC · D10.6 a run started inside the previous
  hour's retry window (11:10), that hour unfetched · D10.7 the same, that hour
  collected · D10.8 a run started after that window (11:30) · D10.9 a run in the
  previous hour's window while Blizzard already serves the current hour (G34).
- **D11, Blizzard's answer** (not complete): D11.1 200 · D11.2 timeout · D11.3
  429 · D11.4 502, 503, 504 · D11.5 500 · D11.6 an unusable body · D11.7 401 for
  a new token · D11.8 401 with a cached token, then a new token accepted · D11.9
  401 with a cached token, then the new token refused · D11.10 403 or 404 ·
  D11.11 an unknown field · D11.12 429 with `Retry-After` · D11.13 400, or
  another status (418).
- **D12, a blip** (complete): D12.1 clears before :25 · D12.2 persists to :25.
- **D13, token** (complete): D13.1 none · D13.2 61 min left · D13.3 60 · D13.4
  59.
- **D14, an item** (complete): D14.1 has a response · D14.2 absent, fetch ok ·
  D14.3 absent, blip still failing at the fetch's end · D14.4 absent, 404 ·
  D14.5 absent, 401 then a new token accepted · D14.6 absent, 401 then the new
  token refused · D14.7 absent, 400, 403, 500 or an unreadable body · D14.8
  latest response a 404, at `dp daily`: answers 200 · D14.9 the same, answers
  404 again.
- **D15, disk** (complete): D15.1 room · D15.2 full during the write.
- **D16, lock** (complete): D16.1 free · D16.2 held, released inside 10 min ·
  D16.3 held for 10 min or more · D16.4 held by a retrying hourly run when `dp
  daily` starts · D16.5 a person's writing subcommand · D16.6 `collect` polling
  a late snapshot while another environment's job runs · D16.7 another job
  asking for the lock between `collect`'s rename and the end of `export`.
- **D17, transform** (complete): D17.1 high-water mark at the previous hour ·
  D17.2 k hours behind · D17.3 hour already processed · D17.4 a failure part-way
  through an hour.
- **D18, `dp hourly`'s path and exit** (complete): D18.1 a fresh collection,
  every step 0 · D18.2 collect exits 0 at step 1 · D18.3 collect exits 75, 2 or
  70, later steps 0 · D18.4 collect exits 75 and a later step fails · D18.5
  collect 0 and a later step fails.
- **D19, N** (complete): D19.1 1 · D19.2 inside a level · D19.3 exactly the
  units listed · D19.4 more than listed · D19.5 0 or negative · D19.6 default ·
  D19.7 an average with more than two decimals, below and at a half · D19.8
  nothing listed.
- **D20, default N history** (complete but for G10): D20.1 168 held hours, odd
  middle · D20.2 a .5 median · D20.3 all 0 · D20.4 48 hours held · D20.5 gaps in
  the window · D20.6 an hour with span > 1 in the window · D20.7 the first hour
  (span null) in the window · D20.8 the window's edges: the hour itself, and the
  hour 168 before (G10) · D20.9 no span-1 hour in the window (G35).
- **D21, ladder** (complete): D21.1 ends at the last price · D21.2 reaches 48 h
  exactly · D21.3 crosses 48 h · D21.4 no sales in the window · D21.5 a single
  price · D21.6 fewer than 24 hours held in the window · D21.7 an hour with span
  > 1 in the window.
- **D22, an item's listings in C** (complete): D22.1 some · D22.2 none, some the
  hour before · D22.3 none, none the hour before · D22.4 first appearance ·
  D22.5 none in any hour of a day.
- **D23, vendor buy price** (complete): D23.1 present · D23.2 null.
- **D24, age against keep, by the row's or file's hour or day** (complete):
  D24.1 within · D24.2 exactly the keep · D24.3 older · D24.4 at 00:50, the hour
  4 weeks before that day's 00:00, and the hour after it.
- **D25, bucket** (complete): D25.1 set, holds the file · D25.2 set, not yet
  holding it · D25.3 empty · D25.4 the daily history pushed · D25.5 host item
  files past 7 days.
- **D26, export** (complete): D26.1 one hour · D26.2 catch-up of k hours · D26.3
  failure, then the next run · D26.4 a lacking hour older than the hourly keep ·
  D26.5 copied mid-run.
- **D27, day** (not complete, G35): D27.1 24 hours held · D27.2 hours missed ·
  D27.3 an hour neither processed nor a gap when `dp daily` runs · D27.4 that
  hour processed before a retry · D27.5 not closable before 03:00, closed the
  next night with the following day · D27.6 the first hour collected inside the
  day (null flows) · D27.7 hours with nothing listed · D27.8 the first day,
  starting mid-day (G35).
- **D28, the error that stops a run** (complete): D28.1 usage · D28.2
  fundamental · D28.3 blip run out · D28.4 unexpected · D28.5 signal.
- **D29, `dp daily`'s exit** (complete): D29.1 lock held past the wait · D29.2
  the day before not closable · D29.3 disk full · D29.4 unexpected · D29.5 a
  push fails · D29.6 a deletion fails · D29.7 an item retry fails · D29.8 an
  item answers 404 again · D29.9 all done.
- **D30, a lost host** (complete for the design): D30.1 bronze covers every day
  · D30.2 days older than bronze in the bucket.

## 3. Outcomes

| ID | Outcome |
| --- | --- |
| O1 | `posted`: units = quantity, `certain`, `EV-1`, hour C, span. |
| O2 | A warning naming the ID is logged; the event is still written; the run exits `0`. |
| O3 | `partly_sold`: units = the drop, `certain`, `EV-2`. |
| O4 | `sold`: units = quantity, `inferred`, `EV-3`, `tie` false. |
| O5 | `expired`: `inferred`, `EV-5`, `tie` per EV-4. `duration` is the shortest matching D where the posting hour is known, and null where the band decided. |
| O6 | `cancelled`: `inferred`, `EV-6`, `tie` per EV-4; `duration` null. |
| O7 | Exactly one event per gone listing, and none of kind `unsold`. |
| O8 | Intact: no event, one `listing_hour` row, `last_seen` = C. |
| O9 | The `listing_record` has the values L2 says; the live and history rows are deleted. |
| O10 | `posted` and every `posting_*` are null. |
| O11 | The event's hour is C's; `span` = C − the last hour held. |
| O12 | `meta.gap` has one row per missing hour, with `found_at`, written by `dp transform`. |
| O13 | A whole bronze file at the final name; no temporary file. |
| O14 | Exit `0` at step 1: no request made and nothing written. |
| O15 | Exit `75`, nothing written; the hour later recorded as a gap. |
| O16 | Exit `0` with a warning (a cleared retry, a renewed token, or the field's name). |
| O17 | Exit `2`; no file; the lake unchanged. |
| O18 | Exit `70`; no file; the lake unchanged. |
| O19 | Exit `3`; the error logged with its type; the rest of the work done. |
| O20 | The items file holds the raw responses; reference is updated; known items are not fetched. |
| O21 | `processed` rows in order; the high-water mark is the latest. |
| O22 | Every table's counts are unchanged by a rerun. |
| O23 | A failed hour is rolled back whole; the high-water mark is unchanged. |
| O24 | `item_hour` has the expected values. |
| O25 | `price_level_hour` has the expected values. |
| O26 | `lowest` has the expected value. |
| O27 | The fill price, to two decimals, and the units covered, with "how many" where short. |
| O28 | `default_n` has the expected value. |
| O29 | The ladder rows, the row it stops at, and the hours or *no sales seen*. |
| O30 | The flows have the expected values, with floor ≤ estimate. |
| O31 | No `item_hour` row for a missed hour; the next row carries the span. |
| O32 | `item_day` has the expected values, including `hours_held` and `default_n`. |
| O33 | The profile has a row per item, showing the ID where there is no reference. |
| O34 | Rows and files older than their keep are deleted; those at or within it are kept; the lake's files are cleaned up. |
| O35 | Host bronze is deleted as K2 says. |
| O36 | The export files are as E1 says and always whole. `profiles.sql` over the export gives the same numbers as `dp` over the lake. |
| O37 | The lock is waited for up to 10 min, then the run exits `75` with nothing changed. |
| O38 | Exit `70` or `64`; the result object's fields are present. |
| O39 | The token is reused or renewed, as expected. |
| O40 | Backoff of 30, 60, 120, 240, 300 s, or the `Retry-After`; a 2-minute poll; timeouts of 60 and 10 s. |
| O41 | A rebuild from bronze equals an incremental build from the same first hour. |
| O42 | The secret is absent from logs, bronze and the export. |
| O43 | An ad hoc query takes no lock and runs with the `DP_ADHOC_*` limits. |
| O44 | The reappearing ID: a warning naming it; no event, no live row; its record unchanged. |
| O45 | Exit `2` before any file is written (wrong clock, or 403, 404). |
| O46 | `dp daily` is started again 15 min after exiting `75`, and not after 03:00. |
| O47 | Item 404: a row with status 404 and a null body; a warning naming the item; no error, so no exit `3` from it; not asked again by later hourly runs; asked by `dp daily`. |
| O48 | A sell-out hour: an `item_hour` row with `lowest` null and the hour's flows. No row in a following hour with no listings. |
| O49 | The first hour: live rows with `posted` null; no event rows; `item_hour` and `price_level_hour` with prices and depth, flows and `span` null; `processed` holds it. |
| O50 | `items`, `transform` and `export` run after any `collect` result. |
| O51 | `fill_price` with N below 1 raises an error and returns no value. |
| O52 | A day is not closed while any of its hours is neither processed nor a gap; it is closed once all are, by the first `dp daily` after, with any other closable day. |
| O53 | `dp hourly`'s exit: `collect`'s where not `0`, else `3` where a later step failed, else `0`. |
| O54 | `dp daily`'s exit as DX; on `3`, the day stays closed and the next run repeats the failed step; on `75`, nothing changed. |
| O55 | Hours with span > 1 or null are left out of default N and the ladder's mean. |
| O56 | Null: the fill price with nothing listed; `median_fill_price` where no hour had any listed. |
| O57 | The bucket holds the bronze files under their host paths and `daily/item_day.parquet` and `daily/item.parquet`, equal to the export's; host item files are never deleted. |
| O58 | After a lost host, the restored and rebuilt lake gives the same `item_day` and `item` as before the loss. |
| O59 | No lock is held while polling; it is taken for the rename, and under `dp hourly` held until `export` ends. |
| O60 | A run started inside the previous hour's window collects that hour, or exits `0` at step 1 if it is held; after the window, the current hour. |

## 4. Matrix

**The mark against the place.** ✗ marks a combination that cannot occur.

| | intact | reduced | gone |
| --- | --- | --- | --- |
| front | ✗ | O3 | O4 |
| the first intact listing | O8 | ✗ | ✗ |
| behind an intact listing | O8 | O3 + O2 | O5 or O6, `tie` per D3 |
| none intact | ✗ | O3 | O4 |

**A gone listing behind an intact one, posting hour known: p + D against the
window.**

| | C − span − 1 | C − span | inside | C | C + 1 | two inside |
| --- | --- | --- | --- | --- | --- | --- |
| known | O6 | O5 | O5 | O5 | O6 | O5, shortest D |

**Posting hour unknown: the last band against the span.** Each cell is the
shortest time left against "under span hours".

| | span 1 | span 2 | span 3 | span 12 | span 13 |
| --- | --- | --- | --- | --- | --- |
| `SHORT` (0) | O5 | O5 | O5 | O5 | O5 |
| `MEDIUM` (0.5 h) | O5 | O5 | O5 | O5 | O5 |
| `LONG` (2 h) | O6 | O6 | O5 | O5 | O5 |
| `VERY_LONG` (12 h) | O6 | O6 | O6 | O6 | O5 |

## 5. Scenarios

The datasets are in part 8.

| ID | Scenario | Conditions | Outcomes |
| --- | --- | --- | --- |
| S1 | Mixed queue (TD-A) | D1.1–3, D2.1–3, D3.1, D4.1, D5.1, D8.1 | O1, O3, O4, O6, O7, O8, O9, O24, O25, O30 |
| S2 | No intact listing (TD-B) | D2.4 | O3, O4, O30 |
| S3 | Sell-out (TD-B2) | D22.2, D22.3, D19.8 | O4, O48, O56 |
| S4 | Tie and its counterparts (TD-C1 to C4) | D3.1–3 | O6 with `tie` true or false; O4 |
| S5 | Several intact ahead (TD-C5, C7) | D3.4–5 | O6, `tie` false then true |
| S6 | A same-snapshot pair, gone one in front (TD-C6) | D3.6 | O4, `tie` false |
| S7 | IDs (TD-D, TD-D3) | D4.1–3 | O1, O2 |
| S8 | Reduced behind intact (TD-D2) | D1.2, D2.3 | O3, O2 |
| S9 | Expiry window at span 1 (TD-E) | D6.1–5, D5.1 | O5, O6 |
| S10 | First snapshot (TD-F) | D9.1, D5.2, D7 | O49, O10; then O5, O6 by band, with `span` 1 |
| S11 | Two missed hours (TD-G) | D8.3, D9.3, D6.1–4, D5.3 | O11, O12, O31, O5, O6, O10 |
| S12 | One missed hour | D8.2 | O11, O12 |
| S13 | Band against span (TD-K, and TD-G's 607) | D5.3, D7, D8.1–5 | O5, O6, per the matrix |
| S14 | Long outage (TD-G2) | D8.6, D6.6 | O5, `duration` 12 |
| S15 | Listing records (TD-A, TD-E, TD-H2) | L2 | O9 |
| S16 | Queue places, two items (TD-H) | Q1, Q3 | O25, positions |
| S17 | The hour from `last-modified` (TD-I) | D10.1–2, D10.5 | C3's poll, the file's name |
| S18 | First collection | D13.1, D11.1, D14.2 | O13, O20, O39 |
| S19 | Token margin | D13.2–4 | O39 |
| S20 | Rerun in a collected hour, and at 11:10 with hour 10 held | C1, D10.7 | O14, O60 |
| S21 | Never refreshed by :25; the next hour runs | C3, D12.2 | O15, then O12 |
| S22 | 503 twice, then 200 | D11.4, D12.1 | O16, O40 |
| S23 | Timeout, 429, 502, 503 or 504 until :25 | D11.2–4, D12.2 | O15 |
| S24 | Hung requests | D11.2 | O40 |
| S25 | 401 for a new token, then the right secret | D11.7 | O17, then O13; O42 |
| S26 | 400, 418, 500, an unusable body or no `last-modified`, then a good one | D11.5–6, D11.13, D10.4 | O18, then O13 |
| S27 | Disk full, then room | D15 | O17, then O13 |
| S28 | Unknown field | D11.11 | O16 |
| S29 | Item lookup blips, gets 401 (new token accepted, or refused), or 400, 403, 500 or an unreadable body; the next run fetches it | D14.3, D14.5–7 | O20 where the new token is accepted; otherwise O19, O33 with the ID, then O20 |
| S30 | Item pacing | C6, C7 | ≤ 50 a second |
| S31 | Lock held, then released at 9 min; held for 11 | D16.2–3 | completes; O37 |
| S32 | Ad hoc query during the hourly run | H1, H7 | O43 |
| S33 | Catch-up of 3 hours | D17.2, D26.2 | O21, O36 |
| S34 | Transform fails mid-hour; the next run repairs it | D17.4 | O23, O19, then O21 |
| S35 | Reprocessing a committed hour | D17.3 | O22 |
| S36 | `dp hourly`'s order and exit, after each collect result | D18 | O50, O53 |
| S37 | Price now (TD-J) | D19.1–4, D19.7, D23 | O26, O27 (half away from zero) |
| S38 | N = 0 and N = −1, then N = 1 | D19.5 | O51, then O27 |
| S39 | Default N (TD-J, TD-J3) | D20.1–8 | O28, O55 |
| S40 | Ladder (TD-J, TD-J2, TD-J3) | D21 | O29, O55 |
| S41 | Hidden sale; floor ≤ estimate | P7 | O30 |
| S42 | Keep boundaries at `dp daily`, lake and export, by the row's or file's hour | D24 | O34 |
| S43 | Day close (TD-L) | D27.1–7, D22.5 | O32, O52, O56 |
| S44 | `dp daily` blocked by a retrying hourly run, or by a day not yet closable | D16.4, D29.1–2 | O37, O46, O54 |
| S45 | Export: one hour, catch-up, failure then repair, an hour past the keep, a mid-run copy, and the `profiles.sql` cross-check | D26 | O36, O19 |
| S46 | Host bronze and the daily history, by bucket state | D25 | O35, O57 |
| S47 | Rebuild from bronze | L4 | O41 |
| S48 | Profile view, filter, latest 200 response, missing reference, flows as totals over the window, turnover shown as floor | P1, P11 | O33 |
| S49 | Secret scan | SEC | O42 |
| S50 | Unexpected error, signal, bad flag | D28 | O38 |
| S51 | Cached token refused: a new token accepted; or refused too | D11.8–9 | O16; O17 |
| S52 | Clock ahead, or 403 or 404 on the snapshot; then put right | D10.3, D11.10 | O45, then O13 |
| S53 | 429 with `Retry-After: 120` | D11.12 | O40 |
| S54 | Item 404; hourly runs skip it; `dp daily` asks again: 404 again, then 200 | D14.4, D14.8–9 | O47; `dp daily` exits 0; then O20, the 200 winning in reference |
| S55 | An ended ID reappears (TD-D4) | D1.5 | O44 |
| S56 | A person's `dp transform` while the hourly run holds the lock | D16.5 | O37, then completes |
| S57 | Host back at 11:10 after missing the 10:35 run; and at 11:30 | D10.6, D10.8 | O60: hour 10 collected; at 11:30, hour 11 polled and hour 10 a gap |
| S58 | `collect` polls a late snapshot while another environment's transform runs; another job asks for the lock mid-`dp hourly` | D16.6–7 | O59 |
| S59 | `dp daily`'s failures after the pivot, then the next run | D29.3–7, D29.9 | O54, then O32, O35 |
| S60 | A day not closable until after 03:00 | D27.5 | O46, then O52 the next night |
| S61 | Blizzard already serving hour 11 at 11:10, for a run taking hour 10 | D10.9 | exit `2` as written (G34) |
| S62 | The first day, collection starting at 14:00 | D27.8, D20.9 | none stated (G35) |
| S63 | A lost host, after bronze has expired (TT11) | D30 | O58, O41 |

## 6. Refusals and successes

| Refused | Then succeeds |
| --- | --- |
| S25: a new token refused, exit 2 | the right secret, exit 0 |
| S51: a cached token refused and the new one too, exit 2 | the right secret, exit 0 |
| S26: 500, an unusable body or no `last-modified`, exit 70 | a good response, exit 0 |
| S27: disk full, exit 2 | room, exit 0 |
| S52: clock ahead or 403/404, exit 2 | the clock put right, a 200, exit 0 |
| S21 and S23: exit 75 | the next hour, exit 0; the gap recorded |
| S29: an item fails, exit 3 | the next run fetches it |
| S54: an item answers 404, recorded | `dp daily` asks again and it answers 200 |
| S34: the transform fails, exit 3 | the next run catches up |
| S45: the export fails, exit 3 | the next run writes every hour it lacks |
| S31 and S56: lock held for 11 min, exit 75 | lock free, completes |
| S44: `dp daily` exits 75 at 00:50 | its retry at 01:05, or the first after the day can close, closes it |
| S59: `dp daily` exits 2 or 3 | the next run closes the day, or repeats the failed step |
| S60: no retry closes the day before 03:00 | the next night's run closes both days |
| S29: an item's new token is refused, exit 3 | the next run, with the right secret, fetches it |
| S38: N = 0 and N = −1 refused | N = 1 answered |
| S20: already collected, exit 0 | the next hour collects |

## 7. Coverage, both ways

| Rule | Scenarios |
| --- | --- |
| R1 | S37, S48; UT1; PD1 |
| R2 | S11, S42, S43, S60; UT3, UT4; PD2 |
| R7 | S40, S41, S48; UT2; PD3 |
| R8v | S1, S2, S41; UT3; PD4 |
| T1 | S17 |
| T2 | S1, S11, S12, S14 |
| TR | S1, S2 |
| Q1 | S1, S16 |
| Q2 | S1, S2 |
| Q3 | S1, S2, S16 |
| EV-1 | S1, S7, S10, S11, S55 |
| EV-2 | S1, S2, S8 |
| EV-3 | S1, S2, S3, S4, S6 |
| EV-4 | S1, S4, S5, S6 |
| EV-5 | S9, S10, S11, S13, S14 |
| EV-6 | S1, S9, S10, S11, S13 |
| EVW | S1, S4, S6 |
| L1 | S1, S10, S11 |
| L2 | S15 |
| L3 | S10, S62 |
| L4 | S47, S63; TT6 |
| C0 | S17, S20, S57, S61 |
| C1 | S20 |
| C2 | S18, S19, S29, S51 |
| C3 | S17, S21, S52, S61 |
| C4 | S18, S27, S58 |
| C5 | S28 |
| C6 | S18, S29, S30, S54 |
| C7 | S30 |
| C8 | S22, S23, S24, S53 |
| C9 | TT1, TT8, TT10 |
| H0 | S36 |
| H1 | S31, S32, S44, S56, S58 |
| H2 | S27, S29, S34, S36, S45 |
| H3 | S11, S21, S33, S34 |
| H4 | S35 |
| H5 | S11, S12 |
| H6 | S1, S16 |
| H7 | S32; TT3 |
| H8 | S44, S60; TT8 |
| H9 | S57; TT10 |
| P1 | S29, S48; UT1 |
| P2 | S37 |
| P3 | S3, S37, S38 |
| P4 | S39, S62 |
| P5 | S37 |
| P6 | S40 |
| P7 | S1, S2, S41, S48 |
| P8 | S42 |
| P9 | S43, S60, S62 |
| P10 | S11, S43 |
| P11 | S48 |
| P12 | S45; UT1 |
| P13 | S3 |
| P14 | S39, S40 |
| X1 | S7, S22, S28 |
| X2 | S21, S23, S31 |
| X3 | S25, S27, S51, S52, S61 |
| X4 | S26 |
| X5 | S29, S34, S45 |
| X6 | S27, S50 |
| DX | S44, S54, S59, S60 |
| K1 | S42 |
| K2 | S46, S59; TT8; PD6 |
| K3 | S42 |
| K4 | S54 |
| E1 | S33, S45; TT7 |
| SEC | S25, S49 |
| REF | S18, S48, S54 |
| BK | S63; TT11 |

| Scenario | Rules |
| --- | --- |
| S1 | Q1, Q2, Q3, TR, EV-1–4, EV-6, EVW, L1, H6, P7, R8v, T2 |
| S2 | Q2, Q3, TR, EV-2, EV-3, P7, R8v |
| S3 | EV-3, P13, P3 |
| S4 | EV-3, EV-4, EVW |
| S5 | EV-4 |
| S6 | EV-3, EV-4, EVW |
| S7 | EV-1, X1 |
| S8 | EV-2 |
| S9 | EV-5, EV-6 |
| S10 | L1, L3, EV-1, EV-5, EV-6 |
| S11 | T2, H3, H5, EV-1, EV-5, EV-6, L1, P10, R2 |
| S12 | T2, H5 |
| S13 | EV-5, EV-6 |
| S14 | EV-5, T2 |
| S15 | L2 |
| S16 | Q1, Q3, H6 |
| S17 | T1, C0, C3 |
| S18 | C2, C4, C6, REF |
| S19 | C2 |
| S20 | C0, C1 |
| S21 | C3, H3, X2 |
| S22 | C8, X1 |
| S23 | C8, X2 |
| S24 | C8 |
| S25 | X3, SEC |
| S26 | X4 |
| S27 | C4, X3, X6, H2 |
| S28 | C5, X1 |
| S29 | C6, C2, H2, X5, P1 |
| S30 | C6, C7 |
| S31 | H1, X2 |
| S32 | H1, H7 |
| S33 | H3, E1 |
| S34 | H2, H3, X5 |
| S35 | H4 |
| S36 | H0, H2 |
| S37 | P2, P3, P5, R1 |
| S38 | P3 |
| S39 | P4, P14 |
| S40 | P6, P14, R7 |
| S41 | P7, R7, R8v |
| S42 | K1, K3, P8, R2 |
| S43 | P9, P10, R2 |
| S44 | H1, H8, DX |
| S45 | E1, P12, H2, X5 |
| S46 | K2 |
| S47 | L4 |
| S48 | P1, P7, P11, REF, R1, R7 |
| S49 | SEC |
| S50 | X6 |
| S51 | C2, X3 |
| S52 | C3, X3 |
| S53 | C8 |
| S54 | C6, K4, DX, REF |
| S55 | EV-1 |
| S56 | H1 |
| S57 | C0, H9 |
| S58 | H1, C4 |
| S59 | DX, K2 |
| S60 | P9, H8, DX, R2 |
| S61 | C0, C3, X3 |
| S62 | P9, P4, L3 |
| S63 | BK, L4 |

## 8. Approach

**The kinds of test**, from docs/1.9:

- **[AUTO]** is an automated component, integration or system test. It runs in
  Dark Portal's own regression environment, E3, once delphside/dark-portal#11
  builds it, on `aarch64`. The crate's CI also builds `x86_64`
  (delphside/dark-portal#7's artefacts).
- **[UT]** is a functional user test, run by the owner on E4 Functional testing.
- **[TT]** is a technical test, run by Claude on E5 Technical and load testing,
  or E6 Deployment rehearsal.
- **[PD]** is a post-deployment check on production.

**What runs, and where.**

- **[AUTO] component**: `profiles.sql` and the transform's SQL, on an in-process
  DuckDB and DuckLake in a temporary directory, fed bronze Parquet written from
  the constructed snapshots.
- **[AUTO] integration**: the `dp` subcommands against a local stub of Blizzard
  (token, commodities, item), with a temporary `DP_DATA_DIR`, lock file, secret
  file and bucket.
- **[AUTO] system**: about 30 constructed hours through `dp hourly`, then `dp
  daily`, then a fresh DuckDB loading `export/profiles.sql` over a copy of
  `export/`.

**What is real, and what is stubbed.**

- Real: DuckDB, DuckLake, Parquet, the filesystem and the lock file.
- Stubbed: Blizzard, the clock, the bucket, and a failed write for a full disk.
- The timers' schedule, persistence and the daily retry are systemd's, so they
  are tested as [TT] on E5, not [AUTO].

**How time is manipulated.** By an injected clock covering the run's start (the
current hour), the poll, the :25 window, backoff and `Retry-After`, the token
margin, the lock wait, 00:50, the 15-minute daily retry and 03:00. The documents
name no clock seam (G19), left to Development.

**What state each test starts from.**

- An empty data folder with the migrations applied.
- Silver is reached by replaying hours. The expiry and band boundaries (TD-E,
  TD-K) are the exception: they seed `live_listing` and `listing_hour` directly,
  which couples those tests to 5.4.2's schema.
- Expected values are computed by hand; S45 and S47 are cross-checks by a second
  route.

**The datasets.** Prices are in copper. A listing is written `id price×qty band
[first seen]`. Each dataset is its own world, with h9 held unless stated.

- **TD-A, the mixed queue.**
  - Live after h10: `102 100×3`, `101 100×5`, `103 110×4`, `104 120×2`, all
    first seen and posted h9. The highest live ID is 104.
  - C (h11): `101 100×2`, `103 110×4`, and a new `105 105×6`.
  - Events: 102 sold, 3, `EV-3`; 101 partly sold, 3; 103 intact; 104 cancelled,
    2, `EV-6`, `tie` false, since 9 + 12 = 21 lies outside [10, 11]; 105 posted,
    6, no warning. No `unsold` row.
  - Flows: posted 6, floor 3, estimate 6, expired 0, cancelled 2.
  - `item_hour`: lowest 100, units listed 12, listings 3. Price levels: 100 → 2,
    105 → 6, 110 → 4.
  - 105's queue at posting: lowest 100, position 2, units ahead 2, units at or
    below 8.
  - Records: 102 quantity 3, sold, `units_sold` 3, `duration` null; 104
    cancelled, `units_sold` 0. After 101 goes from the front at h12, its record
    has `quantity` 5 and `units_sold` 5.
- **TD-B, no intact listing.** Live: `201 50×2`, `202 60×3`, `203 70×4`. C: `202
  60×1`. 201 sold 2; 202 partly sold 2; 203 sold 4. Floor 2, estimate 8.
- **TD-B2, a sell-out.** An item's listings hold 9 units at h10. C (h11) has
  none: sold 9, and an `item_hour` row with `lowest` null, units listed 0 and
  estimate 9; `fill_price(item, h11, 1)` is null. h12 also has none: no row.
- **TD-C, the ties**, each its own world, with C at h11.
  - **C1.** `302 200` and `301 200`, both first seen h10. 302 intact, 301 gone:
    cancelled, `tie` **true**.
  - **C2.** `310 200` (first seen h10) and `305 200` (h9). 310 intact, 305 gone:
    `tie` false.
  - **C3.** 305 intact and 310 gone: 310 is in the front, so sold.
  - **C4.** `303 190` intact, `304 200` gone: `tie` false.
  - **C5.** `320 180` (h9) and `322 200` (h10) intact; `321 200` (h10) gone: not
    every intact listing ahead is a tie, so `tie` false.
  - **C6.** `302 200` gone and `301 200` intact, both h10: 302 is in the front,
    so sold, `tie` false.
  - **C7.** `333 200` and `332 200` intact, `331 200` gone, all h10: every
    intact listing ahead is a tie, so `tie` true.
- **TD-D, the IDs.**
  - On TD-A, C also holds a new `100`: at or below 104, so posted and a warning
    naming 100; exit 0. A new `106` is posted with no warning.
  - **TD-D2**: 104 drops from 2 to 1 behind the intact 103: partly sold, 1, and
    a warning naming 104.
  - **TD-D3**: 110 ended last hour, so the highest live ID is 104. A new `107`
    is posted with no warning, as written.
  - **TD-D4**: 104 ends at h11 (record written). At h12 C holds `104` again: a
    warning naming it, no event, no live row, the record unchanged.
- **TD-E, the expiry window at span 1.** Seed an intact `400 250` and `401
  300×1` posted h0, gone at C.
  - D = 12: C at h11 → cancelled (p + D = C + 1); h12 → expired, `duration` 12;
    h13 → expired; h14 → cancelled.
  - D = 24: h23, h24, h25 and h26 give the same four results; D = 48: h47 to h50
    likewise.
- **TD-F, the first snapshot.**
  - h10 is the first snapshot collected: `500 90 VERY_LONG`, `501 100 MEDIUM`,
    `502 110 SHORT`, `503 120 LONG`, `504 130 VERY_LONG`. Live rows with
    `posted` and `posting_*` null; no event rows; `item_hour` with `lowest` 90,
    units listed 5 and listings 5, flows and `span` null; `processed` holds h10.
  - At h11 (span 1): 500 intact; 501 and 502 expired, `duration` null; 503 and
    504 cancelled. A new `505` has posted h11.
- **TD-G, two missed hours.**
  - h10 held; h11 and h12 missed; C is h13, span 3, window [10, 13]. `600 50`
    intact.
  - Gone listings: posted h1 (1 + 12 = 13) expired; h0 (12) expired; h23 the day
    before (11) expired; h22 (10 = C − span) expired; h21 (9) cancelled; h10
    (22) cancelled.
  - A new `605 SHORT` is dated h13, span 3, `posted` and `posting_*` null.
  - `meta.gap` holds h11 and h12, with no `item_hour` rows for them.
  - At h14: 605 gone behind 600, so expired by its band; a new `606` has posted
    h14.
  - **607**: `LONG`, first seen h13; h14 and h15 missed; gone at h16 with span
    3: expired (2 h < 3).
- **TD-G2, a long outage.** The last hour held is h10, C is h24, span 14. A gone
  listing posted h0 has 12 and 24 inside [10, 24]: expired, `duration` 12.
- **TD-H, two items interleaved by price.**
  - Item X: `700 100`, `702 150`; item Y: `701 120`, `703 130`. Fronts,
    positions and units ahead are per item.
  - **TD-H2**: X also has `708 145×1`, first seen h10 with 702. `710 140×5` and
    `711 130×2` are posted at h11. At h12 all are listed; 702 is gone at h13:
    `end_units_undercut` 8 (708 counts, having a higher ID; 700 does not).
- **TD-I, collection times.**
  - A run at 10:35: `last-modified` 09:31:40 is polled every 2 min; 10:31:40 is
    written as `T10`. With 09:31:40 served to 11:25, the run still polls for
    hour 10 at 11:10 (the hour is fixed at its start) and exits 75 at 11:25.
  - A run at 11:10, bronze lacking `T10`, Blizzard serving 10:31:40: written as
    `T10`. With `T10` held: exit 0, no request. A run at 11:30: polls for hour
    11.
  - G34: a run at 11:10 taking hour 10, Blizzard serving 11:05:00: exit 2 as
    written.
  - 10:00:00 and 10:59:59 both give `T10`; 11:00:00 exits 2 (S52).
  - A second run at 10:50 exits 0 with no request.
  - 2026-07-01 under `TZ=Europe/London` gives the UTC hour.
- **TD-J, price now.**
  - Listings `501 100×2`, `502 100×1`, `503 110×4`, `504 120×3`. Levels: 100 → 3
    (cumulative 3), 110 → 4 (7), 120 → 3 (10).
  - Fill price: N = 1 → 100.00; N = 4 → 102.50; N = 5 → 104.00; N = 10 → 110.00;
    N = 12 → 110.00 for 10 units, saying 10. N = 9 → 980 ÷ 9 = 108.888… →
    108.89. For a half, a world of `601 100×7` and `602 101×1` at N = 8: 801 ÷ 8
    = 100.125 → 100.13 (half away from zero, where half even gives 100.12).
    Vendor buy price 300, then null.
  - Default N over the 168 hours of the window ending at the hour: 83 values of
    2 and 85 of 3 give 3; 84 of each give 2.5, so 3; all 0 gives 1; 48 hours
    held give the median of those 48; with 20 gaps, the median of the 148 held.
  - Ladder, total sold estimate 48 over 24 hours held (2 an hour): 1.5, 3.5 and
    5 hours, ending at the last price. Total 0: *no sales seen* at every level,
    ending at the last price.
- **TD-J2, the ladder cut-off.** Levels with cumulative units 3, 7, 12, 15.
  - Total estimate 6 over 24 held hours (0.25 an hour): 12, 28 and 48 hours; the
    48 row is shown and the ladder stops; 15 is not shown.
  - Total 5 over 20 held hours: the same rows, since the divisor is hours held.
  - Cumulative 3, 7, 13, 15 at 0.25 an hour: 12, 28, 52; the 52 row is shown and
    the ladder stops.
- **TD-J3, hours that are not span 1.** The default N window holds 165 span-1
  hours with estimate 2, one hour after a 3-hour gap (span 3) with estimate 30,
  and the first hour collected (span null): default N is 2, the span-3 and first
  hours left out. The ladder over a turnover window of 22 span-1 hours at 2 and
  one span-3 hour at 9: the mean is 2 (44 ÷ 22), not 53 ÷ 23. Edge: an estimate
  of 7 at the hour itself and 0 elsewhere moves the median only if the hour is
  in the window (G10).
- **TD-K, band against span.** Gone listings behind an intact one, posting hour
  unknown, `duration` null in each:
  - `SHORT` and `MEDIUM` at span 1: expired.
  - `LONG` at span 2: cancelled; at span 3: expired.
  - `VERY_LONG` at span 12: cancelled; at span 13: expired.
- **TD-L, a day.** One item over day D.
  - 24 hours held, lowest 100 except 95 at 05:00; fill price at `default_n(item,
    D 00:00)` 104.00 in 12 hours and 106.00 in 12: `lowest` 95,
    `median_fill_price` 105.00, `hours_held` 24.
  - The same day with 03:00 and 04:00 missed: `hours_held` 22, the median over
    22.
  - 23:00 failed in the transform at 00:35: `dp daily` at 00:50 exits 75 and
    does not close D, nor push or delete; its retries at 01:05 and 01:20 exit
    75; the 01:35 run processes 23:00 and the 01:50 retry closes D, exit 0.
  - The transform fails every hour from 22:00 to 03:00: every retry to 03:00
    exits 75; the next night's run closes D and D + 1.
  - 06:00 to 08:00 have nothing listed: `median_fill_price` over the other 21; a
    day with nothing listed in any hour has it null.
  - The first hour collected at 14:00 on D − 1 is summed as nothing: posted,
    floor and estimate cover the later hours (and D − 1 itself is G35).
  - `dp daily` after closing D: a failed bucket push exits 3 with D closed; the
    next run pushes, exit 0. A full disk before the commit exits 2 with D not
    closed.

**[UT] on E4**, the owner's moves, from delphside/dark-portal#7's checkboxes:

- UT1: after 24 hours of collection, pull the export, open the notebook (which
  loads `profiles.sql`) and find linen cloth and two other commodities by name
  and class.
- UT2: for those three, compare the lowest and the fill price for 20 and 200
  units with the in-game auction house within the same hour; read one depth
  ladder against the in-game listing.
- UT3: read the hourly history and flows: the sold floor never above the
  estimate, and a stopped hour shown as a gap, not a zero.
- UT4: read one completed day's summary: lowest, median fill price, posted and
  sold units.

**[TT]**, Claude's moves, from delphside/dark-portal#7's checkboxes and the
rules:

- TT1 (E5): 72 hours hourly with E5's own Blizzard client, at :35: every hour
  processed or recorded as a gap.
- TT2 (E5): the first `dp items` fetches about 10,500 items at 50 a second
  (about 3.5 min) with no 429.
- TT3 (E5, load): each run's time and peak memory against 1 GB and 1 thread,
  inside `DP_CONTAINER_MEMORY`, with an ad hoc query running at E5's
  `DP_ADHOC_*`; per hour, `price_level_hour` and `listing_record` rows and
  bytes, projected to 4 weeks and a year against the capacity plan. The time is
  reported, not judged (G26).
- TT4 (E5): kill a run after the bronze file and before the commit: the next run
  processes both hours, matching an uninterrupted run.
- TT5 (E5): stop the timer for two hours: the gaps are recorded, the next
  comparison has span 3, no events are dated to the missed hours. Start the run
  twice in one hour: the second does nothing.
- TT6 (E5): rebuild silver and gold from a week of bronze copied from the
  bucket, and compare with an incremental run **from that week's first hour**
  (L4); a comparison with the long-running lake would differ at the first hour.
- TT7 (E5): pull the export by rsync from another machine mid-run and read it
  with DuckDB: every file whole; the notebook's numbers equal `dp`'s.
- TT8 (E5): `dp daily` at 00:50: `item_day` written, aged rows and export files
  deleted, bronze and `daily/` pushed to a test bucket and host snapshot files
  deleted, item files kept; again with `DP_BUCKET` empty. Hold the lock across
  00:50: it exits 75 and its service restarts it every 15 min until 03:00.
- TT9 (E5): a wrong client secret exits 2; a Blizzard outage past the retry
  window exits 75 with the hour recorded as a gap.
- TT10 (E6): deploy by delphside/dark-portal#11's rehearsal path from
  production's level, and the next hourly run lands. Reboot across :35, back
  before :25 past the next hour: the timer runs the missed job when the host is
  back and it collects the previous hour (S57).
- TT11 (E5): a restore drill for BK: delete the lake and export, restore
  `item_day` and `item` from `daily/` for days older than the bronze copied
  back, rebuild the rest, and compare with the lake before (G36).

**[PD]**, run from the export the owner pulls, since production reads are his;
one row per requirement in delphside/dark-portal#7:

- PD1 (R1): the owner compares three commodities' lowest and fill price with the
  in-game auction house within the same hour.
- PD2 (R2): after a week, every hour collected has an `item_hour`, a missed hour
  is a gap, and each completed day has an `item_day`; the 4-week keep is checked
  after 4 weeks.
- PD3 (R7): one commodity's ladder matches the in-game units at each price
  within the hour, and shows hours of depth.
- PD4 (R8v): every hour shows the sold floor and estimate for each item, the
  floor never above the estimate.
- PD5: every `meta.gap` row is explained.
- PD6 (K2): the bucket's lifecycle rule is 1 year, and host bronze holds no file
  older than 7 days.

## 9. Test names

All of these are **[AUTO]**.

**Events and lifecycle**

- `new_id_not_live_is_posted_certain`
- `new_id_at_or_below_highest_live_id_is_posted_and_logged_as_a_warning`
- `new_id_above_highest_live_id_is_no_warning_even_below_one_ended`
- `ended_id_reappearing_is_logged_and_left_out`
- `quantity_drop_is_a_certain_partial_sale_of_the_drop`
- `quantity_drop_behind_an_intact_listing_is_a_sale_logged_as_a_warning`
- `listing_gone_from_the_front_is_sold_inferred`
- `every_gone_listing_is_sold_when_none_is_intact`
- `gone_listing_writes_exactly_one_event_and_no_unsold_row`
- `listing_gone_behind_a_cheaper_intact_listing_carries_no_tie`
- `listing_gone_behind_a_same_price_listing_from_another_snapshot_carries_no_tie`
- `listing_gone_behind_a_same_price_listing_from_its_snapshot_carries_a_tie`
- `tie_needs_every_intact_listing_ahead_to_share_its_price_and_snapshot`
- `sold_listing_never_carries_a_tie`
- `expiry_matches_when_posting_plus_duration_is_the_current_hour` (12, 24, 48)
- `expiry_matches_at_the_window_start_current_hour_minus_span`
- `posting_plus_duration_before_the_window_is_cancelled`
- `posting_plus_duration_after_the_current_hour_is_cancelled`
- `expiry_records_the_shortest_matching_duration`
- `unknown_posting_hour_expires_on_a_short_or_medium_band`
- `long_band_is_cancelled_at_span_2_and_expired_at_span_3`
- `very_long_band_is_cancelled_at_span_12_and_expired_at_span_13`
- `intact_listing_adds_a_history_row_and_no_event`
- `events_after_missed_hours_are_dated_to_the_current_hour_with_their_span`
- `missing_bronze_hours_are_recorded_as_gaps_by_the_transform`
- `listing_first_seen_after_a_gap_has_no_posting_hour_or_queue_at_posting`
- `first_snapshot_writes_live_listings_and_no_events`
- `first_hour_is_held_with_prices_and_depth_and_null_flows_and_span`
- `queue_orders_by_price_then_newest_id_first`
- `fronts_are_judged_per_item`
- `queue_place_counts_units_ahead_and_at_or_below`
- `ended_listing_writes_its_record_and_removes_its_live_rows`
- `listing_record_counts_units_sold_over_its_life`
- `undercut_counts_higher_ids_at_a_lower_price_still_listed`

**Collection**

- `snapshot_hour_is_the_utc_hour_starting_of_last_modified`
- `collect_in_a_collected_hour_exits_0_without_a_request`
- `current_hour_is_fixed_when_collect_starts`
- `run_inside_the_previous_hours_retry_window_collects_that_hour`
- `run_after_the_previous_hours_retry_window_collects_its_own_hour`
- `collect_polls_without_the_lock_and_takes_it_only_to_rename`
- `stale_snapshot_is_polled_every_2_minutes_until_it_refreshes`
- `snapshot_unrefreshed_by_25_past_exits_75_and_writes_nothing`
- `last_modified_after_the_current_hour_exits_2`
- `missing_last_modified_exits_70`
- `snapshot_403_or_404_exits_2`
- `snapshot_400_or_an_unlisted_status_exits_70`
- `cached_token_is_reused_with_more_than_the_margin_left`
- `token_is_renewed_at_or_inside_the_margin`
- `cached_token_refused_once_takes_a_new_token`
- `new_token_refused_after_a_cached_one_exits_2`
- `refused_client_secret_exits_2`
- `snapshot_lands_in_its_hours_bronze_file_by_rename`
- `blip_cleared_by_retry_exits_0_with_a_warning`
- `timeout_429_502_503_504_until_25_past_exits_75`
- `retry_backoff_doubles_from_30_seconds_to_5_minutes`
- `retry_after_is_honoured`
- `snapshot_request_times_out_at_60_seconds_others_at_10`
- `blizzard_500_exits_70_and_writes_nothing`
- `unusable_body_exits_70_and_leaves_no_bronze_file`
- `full_disk_exits_2_and_leaves_no_partial_file`
- `unknown_listing_field_is_logged_by_name`
- `items_new_to_bronze_are_fetched_raw_once`
- `failed_item_lookup_exits_3_and_is_retried_next_run`
- `item_lookup_401_takes_a_new_token_once_and_asks_again`
- `item_lookup_refused_new_token_exits_3_and_is_fetched_next_run`
- `item_lookup_400_403_500_or_unreadable_is_fetched_next_run`
- `item_404_is_recorded_with_its_status_and_logged_as_a_warning`
- `item_whose_latest_response_is_404_is_not_asked_again_hourly`
- `profile_shows_the_item_id_until_its_response_arrives`
- `item_fetch_is_paced_at_50_a_second`
- `secret_never_appears_in_logs_bronze_or_export`

**Scheduling and the hourly run**

- `writing_subcommand_waits_for_the_lock_up_to_10_minutes`
- `writing_subcommand_exits_75_when_the_lock_wait_runs_out`
- `persons_transform_waits_for_the_hourly_runs_lock`
- `hourly_holds_the_lock_from_the_rename_through_export`
- `ad_hoc_query_takes_no_lock_and_uses_its_own_limits`
- `hourly_runs_collect_items_transform_export_in_order`
- `hourly_runs_items_transform_and_export_after_any_collect_result`
- `hourly_exits_with_collects_status_where_it_is_not_0`
- `hourly_exits_3_where_collect_succeeded_and_a_later_step_failed`
- `transform_catches_up_every_bronze_hour_in_order`
- `failed_transform_hour_rolls_back_whole_and_exits_3`
- `next_run_reprocesses_a_failed_hour`
- `reprocessing_a_committed_hour_changes_nothing`
- `gold_hour_takes_prices_from_live_listings_and_flows_from_events`

**Profiles**

- `lowest_is_the_cheapest_unit_price_in_the_latest_snapshot`
- `fill_price_averages_the_cheapest_n_units_across_listings`
- `fill_price_for_more_units_than_listed_says_how_many`
- `fill_price_is_held_to_two_decimal_places`
- `fill_price_rounds_half_away_from_zero`
- `fill_price_is_null_where_nothing_is_listed`
- `fill_price_refuses_n_below_one`
- `default_n_is_the_rounded_up_median_over_the_hours_held_in_7_days`
- `default_n_is_at_least_one`
- `default_n_window_ends_at_the_hour`
- `measures_over_hours_count_only_held_hours_with_span_1`
- `vendor_buy_price_is_null_where_blizzard_gives_none`
- `depth_ladder_accumulates_units_at_or_below_each_price`
- `depth_ladder_divides_by_the_mean_hourly_sold_estimate_over_hours_held`
- `depth_ladder_shows_no_sales_seen_without_sales`
- `depth_ladder_shows_the_first_price_reaching_48_hours_and_stops`
- `depth_ladder_stops_at_the_last_price`
- `sold_estimate_is_the_floor_plus_units_gone_from_the_front`
- `sold_floor_never_exceeds_sold_estimate`
- `turnover_per_hour_is_shown_as_the_sold_floor_beside_the_estimate`
- `listing_posted_and_bought_between_snapshots_shows_in_no_flow`
- `missed_hour_has_no_item_hour_rather_than_zeros`
- `sold_out_item_has_an_hour_row_with_no_lowest_and_its_flows`
- `daily_close_takes_the_lowest_hour_and_median_fill_price_at_midnights_default_n`
- `daily_close_counts_the_hours_held`
- `daily_median_fill_price_skips_hours_with_nothing_listed`
- `daily_flows_sum_the_hours_that_are_not_null`
- `day_closes_only_once_every_hour_is_processed_or_a_gap`
- `daily_closes_every_closable_day_not_yet_closed`
- `profile_shows_every_item_at_the_latest_hour`
- `profile_flows_are_totals_over_the_turnover_window`
- `items_filter_by_name_class_and_subclass`
- `latest_200_item_response_wins_in_reference`

**Retention and export**

- `keep_deletes_only_what_is_older_than_it`
- `keep_is_measured_by_the_hour_or_day_a_row_or_file_is_for`
- `daily_deletes_hourly_gold_older_than_4_weeks`
- `daily_keeps_daily_gold_silver_and_meta`
- `daily_deletes_export_hour_files_older_than_the_hourly_keep`
- `daily_deletes_host_snapshot_files_older_than_7_days_once_the_bucket_holds_them`
- `daily_keeps_host_item_files`
- `daily_pushes_item_day_and_item_to_the_bucket`
- `daily_keeps_host_bronze_the_bucket_lacks`
- `daily_deletes_host_bronze_older_than_7_days_without_a_bucket`
- `daily_asks_again_for_items_whose_latest_response_is_404`
- `daily_exits_0_when_an_item_answers_404_again`
- `daily_exits_75_when_the_day_before_cannot_close`
- `daily_exits_75_when_the_lock_wait_runs_out`
- `daily_exits_2_on_a_full_disk_without_closing_the_day`
- `daily_exits_3_when_a_step_after_the_close_fails_and_the_next_run_repeats_it`
- `export_writes_every_committed_hour_it_lacks`
- `export_skips_a_lacking_hour_older_than_the_hourly_keep`
- `failed_export_exits_3_and_the_next_run_repairs_it`
- `export_rewrites_item_day_and_item`
- `export_files_appear_only_whole`
- `exported_profiles_sql_carries_sql_profiles_unchanged`
- `exported_profiles_sql_gives_the_same_profile_as_the_lake`

**Rebuild and errors**

- `rebuild_from_the_first_bronze_hour_equals_the_incremental_run`
- `unexpected_error_exits_70`
- `bad_flag_exits_64`

## 10. Gaps

Every gap below is open at Design and Test Approach; none blocks the test
design, and each says why. Those marked † change behaviour or a requirement and
need the owner's agreement.

| Gap | What would make the missing test fail | What it would take to close it | Why it is acceptable for now |
| --- | --- | --- | --- |
| G7 A raised or re-priced ID | An ID in C with a higher quantity, or a different price, has no mark: neither intact nor reduced. | Give each a rule, such as a warning and treating it as intact. | Blizzard's model allows neither; only bad data shows it. |
| G10 The window's edge, and sums over hours | "Ending at the hour" does not say whether the hour itself is in the window: TD-J3's edge case gives a different default N each way, and `default_n(item, D 00:00)` for `item_day` with it. P14 counts only span-1 hours in a measure over hours, while a day's flows sum every non-null hour and the profile's totals are not said either way (X-c6): a total after a gap differs by that hour's flows. | Say the window is the hour and the 167 before (or the 168 before); say P14 covers rates and medians and the totals take every held hour. | The tests assert the readings in X-c6 and part 8; either answer changes one expected value. |
| G19 No clock seam | Every timed test (poll, :25, backoff, token margin, lock wait, 00:50, 03:00) needs the clock injected; none is named. | Name it in Development. | A Development matter; part 8 says what it must cover. |
| G26 No bound on the hourly run | TT3 can only report a time. delphside/dark-portal#11's deploy window (:40 to :10) assumes one. | State a bound and its source (`DP_CP_2026_10`, or delphside/dark-portal#12's timing) in 5.4.1. | TT3 records the time; nothing fails meanwhile. |
| G28 E3 to E6 are not yet built (delphside/dark-portal#11) | [AUTO], [UT] and [TT] have nowhere to run. | delphside/dark-portal#11's packages land first. | Designed; delphside/dark-portal#7's Development waits on delphside/dark-portal#11. |
| G29 "Lower bound" | Not directly observable. | Accept the structural tests (`listing_posted_and_bought_between_snapshots_shows_in_no_flow`, floor ≤ estimate). | Inherent. |
| G32 The indefinite keeps and the backup † (pending) | The bucket keeps `daily/item_day.parquet` and `daily/item.parquet` indefinitely, so R2's daily history survives a lost host; silver (kept indefinitely) still cannot be rebuilt beyond bronze's year. | The owner agrees the design, and that silver older than a year is lost with the host. | The owner's decision is pending; nothing is at risk until a year after go-live. |
| G34 An early refresh read as a wrong clock | A run inside hour 10's retry window (a delayed 11:10 run, or the 10:35 run still polling at 11:20) takes hour 10; if Blizzard has already refreshed to hour 11, `last-modified` is after the current hour and the run exits `2`, "the host's clock is wrong", a fundamental error, though the clock is right and hour 10 is merely a gap. S61 asserts 2 as written. | Say that a `last-modified` in the hour after the current one makes the current hour a gap (exit `75`), and only a later one exits `2`. | Blizzard refreshes at about :31:40, after :25, so it needs an early refresh; the exit is loud and the 11:35 run collects hour 11. |
| G35 The first day, and an empty window | Collection starting at 14:00 on D − 1 leaves 00:00 to 13:00 neither processed nor gaps, so D − 1 can never be closed: by DX, `dp daily` on D exits `75` until 03:00, and does no push or deletion that night (X-c8). Whether D − 1 gets an `item_day`, and what default N is with no span-1 hour in its window (the first hour, and `default_n(item, D − 1 00:00)` before any hour), is unstated. S62 has no outcome. | Say the hours before the first snapshot are not the day's (closable from its first held hour, or the first day is not closed), and that default N with no hour in the window is 1. | Once per environment; the second night's run closes D normally. |
| G36 No restore procedure | BK says `item_day` and `item` older than bronze are restored from the bucket, but not by what (a `dp` subcommand, or by hand), nor how restored days meet the rebuilt ones, nor whether rebuilding `item` from bronze's item files keeps the restored items. TT11 cannot be written to steps. | Name the restore's steps or command, and the rule where restored and rebuilt rows meet. | Nothing is restored from `daily/` until bronze has expired, a year after go-live; with G32. |
