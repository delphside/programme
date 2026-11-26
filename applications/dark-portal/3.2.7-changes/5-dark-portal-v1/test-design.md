# Test design specification: consumable profiles

Project: delphside/dark-portal#7 *#5 WP B Del 2 of 5: consumable profiles* · type of change: `functional` · route: `Production Release` · release: not yet set

## 1. Rules

Taken from the design documents at 8472ecf (app 0.1.0),
delphside/dark-portal#7's body and its Decisions table. The documents are drafts
for delphside/dark-portal#7's design.
The first version took them at 47c862a. A rule, condition, outcome or approach
item that begins *changed* took a new meaning from what the build settled; a new
ID is one the build added; the earlier wording is in git history.

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
| EV-1 | *changed*: An ID in C that is not live is `posted`: its quantity, certain. An ID at or below the highest live ID is still posted, and logged as a warning naming it. An ID that ended and reappears, whatever its value, is logged the same way and left out: no event, no live row and no place in the queue, so no other listing's place counts its units. The check is against every listing record. | 5.2.2 |
| EV-2 | *changed*: A reduced listing is `partly_sold`: the drop, certain, priced at the listing's current price. One behind an intact listing is a sale too, and is logged as a warning naming it. | 5.2.2 |
| EV-3 | *changed*: A gone listing in the front is `sold`: the quantity it had when last seen, inferred. | 5.2.2 |
| EV-4 | *changed*: A gone listing behind an intact one is unsold, certain. Its event carries `tie = true` where **every** intact listing ahead of it has the gone listing's price and the same first-seen hour. Only an `expired` or `cancelled` event can be a tie. | 5.2.2; 5.4.5 `tie` |
| EV-5 | An unsold listing `expired` (inferred) where its posting hour is known and posting hour + 12, 24 or 48 lies in [C − span, C], the **shortest** such duration recorded; or where its posting hour is unknown and the lower bound of its last band (`SHORT` 0, `MEDIUM` 30 min, `LONG` 2 h, `VERY_LONG` 12 h) is **under** span hours. | 5.2.2; 5.4.5 *Types* |
| EV-6 | Every other unsold listing was `cancelled`, inferred. | 5.2.2 |
| EVW | Each gone listing writes exactly one event, `sold`, `expired` or `cancelled`. `rule` is the rule that chose the kind (EV-3, EV-5 or EV-6; EV-1 and EV-2 for their own events); `tie` marks EV-4's exception; every event carries `hour`, `id`, `item`, `kind`, `units`, `unit_price`, `tier`, `rule`, `tie` and `span`, keyed (`hour`, `id`, `kind`). | 5.2.2; 5.4.2; 5.4.5 |
| EV-7 | A live listing's quantity or price that changes other than by a sale keeps the listing as it is now, and a warning names it. A quantity that rises counts as *intact*; a price that changes is kept, and the marks go by quantity alone. Its units sold are the drops and, where it sells, the quantity it then held, so they can exceed its first quantity. | 5.2.2 *A live listing that changes*; 5.4.5 `units_sold` |
| L1 | A live listing is one `live_listing` row and one `listing_hour` row per hour seen. `posted` and `posting_*` are null for a listing in the first snapshot collected or first seen after a gap. An intact listing adds a history row and makes no event. | 5.2.2 *A missed hour*, matrix; 5.4.2; 5.4.5 |
| L2 | *changed*: When a listing ends, its `listing_record` is written and its live and history rows are deleted. The record holds `quantity` when first seen; `first_seen`, `last_seen`, `posted`; `duration` (set only on expiry with a known posting hour); `posting_*` (only where `posted` is known); `ended` (the first hour missing); `outcome`, `outcome_tier`, `tie`; `units_sold` over its life: every drop in its quantity and, where it sold, the quantity it then held, so after a rise it can exceed `quantity`; `end_*` (the queue at the last hour seen); and `end_units_undercut`, the units in listings with higher IDs at a lower price still listed at its last hour. | 5.2.2 *The listing record*; 5.4.2; 5.4.5 |
| L3 | The first snapshot collected has nothing to compare with: its listings become live with no posting hour and it writes no events. Its hour is held, with prices and depth, and with its flows and span null. | 5.2.2 *The events*; 5.4.5 |
| L4 | A rebuild replays bronze in order from its first hour and gives the same silver and gold as an incremental run from that hour. | 5.1.1 *Restarts and recovery*, *Data layers* |
| C0 | `dp collect` collects the *current hour*, fixed when it starts: the hour starting in which it runs, or the hour before where it starts within that hour's retry window (a run delayed to 11:10 takes 10:00). | 5.2.1 *The snapshot* |
| C1 | If bronze holds the current hour's file, `dp collect` exits `0` at once. | 5.2.1 step 1 |
| C2 | A cached token is reused while it has more than the token margin (1 h) left; a token lasts 24 h. A request refused (401) with a cached token takes a new token once. | 5.2.1 step 2, *When it fails*; 5.4.1 |
| C3 | `GET …commodities?namespace=dynamic-eu`. If `last-modified`'s hour is before the current hour, wait the poll interval (2 min) and repeat until the retry window closes (:25 past the next hour); the hour is then a gap, recorded by `dp transform`. If it is the hour after the current one, Blizzard has moved on: the current hour is a gap, exit `75`. If it is later still, the host's clock is wrong: exit `2`. | 5.2.1 steps 3–4; 5.4.1 |
| C4 | The snapshot is parsed as a stream and written under a temporary name; `dp collect` then takes the lock and renames it to `bronze/commodities/eu/YYYY-MM-DDTHH.parquet`, with 5.4.2's columns. | 5.2.1 step 5; 5.4.2 |
| C5 | An unknown listing field is logged as a warning naming it. | 5.2.1 |
| C6 | *changed*: `dp items` fetches each item ID in bronze's snapshot files with no response in bronze's item files (`static-eu`, `en_GB`), at 50 a second, and writes one `bronze/items/YYYY-MM-DDTHHMMSS.parquet` per run that fetched any, renamed into place under the lock, with `status`. A blip (C8) pauses the whole fetch for the backoff or the `Retry-After` and puts the item at the back of the queue; an item is asked at most 3 times in a run (item attempts), then left to the next run. A 401 takes a new token once and asks again, then is left to the next run; a 400, 403, 408, 500, other status or unreadable body is left to the next run; each of these gives the step exit `3`. A 404 is data, not an error: written with status 404 and no body, logged as a warning, and asked again only by `dp daily`. The profile shows the item's ID until it has a response. Run alone, `dp items` has a pivot of its own, its first request: a failure before it, such as bronze unreadable, stops it with that error's exit, and after it each item is a unit of work the run carries on past. | 5.2.1 *Item data*, *When it fails*; 5.4.1; 5.4.2; 5.4.5 |
| C7 | Requests stay within Blizzard's 36,000 an hour and 100 a second. | 5.2.1 *Limits* |
| C8 | *changed*: A blip is 1.10's: a timeout, an unreachable Blizzard, or a 429, 502, 503 or 504. It is retried with backoff from 30 s, doubling to 5 min, or after the response's `Retry-After`. Any other status, 408 and 500 included, is unexpected. Timeouts are 60 s for the snapshot and 10 s otherwise. | 5.2.1; 5.4.1; 1.10 |
| C9 | The hourly timer starts at :35; the daily timer at 00:50 UTC. The timers are persistent. | 5.4.1; 5.1.1 *Restarts and recovery* |
| C10 | The item fetch ends 10 min, the lock wait, before the next hourly timer start, :25 past: no request starts unless its HTTP timeout (10 s) ends before then, and the items not reached wait for the next run. | 5.2.1 *Item data* |
| H0 | *changed*: `dp hourly` runs `collect`, `items`, `transform` and `export`, in that order, and runs the last three whatever `collect` returned. Each can be run alone. It exits with `collect`'s exit where that is not `0`; otherwise `3` where a later step failed; otherwise `0`. Where the lock is held past the lock wait the later steps do not run, and the exit is `collect`'s where that is not `0`, otherwise `75`. | 5.1.1; 5.2.1 *When it fails* |
| H1 | *changed*: Every `dp` subcommand that writes takes the VM-wide lock (`DP_LOCK_FILE`), whether a timer or a person starts it. It waits up to 10 minutes, then exits `75`. `dp collect` takes it only to rename its file, so polling holds no lock; `dp hourly` then holds it, without release, from that rename through `export`. Where `collect` took none (its hour was collected already, or it failed first), `dp hourly` takes it for `items`. An ad hoc query takes no lock and is bounded by `DP_ADHOC_MEMORY_LIMIT` and `DP_ADHOC_THREADS`. | 5.1.1; 5.2.1; 5.4.1 |
| H2 | The pivot is the bronze file. A snapshot error ends `dp collect` with its exit; an `items`, `transform` or `export` error is logged with its type and gives that step exit `3`. | 5.1.1; 5.2.1 *When it fails* |
| H3 | *changed*: `dp transform` processes every bronze hour after the high-water mark (`processed`'s latest hour), in order, one commit per hour. It records each hour missing between two snapshots held in `meta.gap` with `found_at`, in the later hour's transaction; a latest hour not yet collected is found by a later run. A failed hour is reprocessed by the next run. | 5.1.1; 5.2.1; 5.2.2; 5.4.2 |
| H4 | An hour already processed is never processed again. | 5.4.2 `processed` key; 5.1.1 |
| H5 | After a missed hour, the comparison runs from the live listings to C; events are dated to C with the span. | 5.2.2 *A missed hour* |
| H6 | The hour's gold rows (`item_hour`, `price_level_hour`) are written once its events are in: prices and depth from the live listings, flows from the events. | 5.2.2 matrix |
| H7 | The hourly and daily jobs run DuckDB with `memory_limit` 1 GB and `threads` 1. Ad hoc: 1 thread, and 4 GB in production, 8 GB outside it. `DP_CONTAINER_MEMORY` is the ad hoc limit plus 1 GB: 5 GB and 9 GB. | 5.4.1 |
| H8 | *changed*: `dp daily` retries itself on exit `75`, with no unit restarting it (`Restart=no`): after the daily retry interval (15 min, from the end of one attempt to the start of the next), for as long as the next attempt would start before the earlier of 03:00 UTC on the day the run started and the daily retries span (130 min) after the run's start. It exits with the last attempt's status, so `75` where the retries ran out; a start at or after 03:00 UTC, such as a persistent timer's catch-up, makes one attempt. The hourly unit does not restart either; its next timer start is its retry. | 5.1.1 *Restarts and recovery*; 5.4.1 |
| H9 | A reboot loses no hour that can still be fetched: a run missed while the host was down starts when it is back, and `dp collect` takes the current hour as C0 fixes it. | 5.1.1 *Restarts and recovery*; 5.2.1 |
| H10 | *changed*: One hourly processing bound, 5 min, covers the `transform` and `export` of an hour together, and a run over it is logged as a warning. A run's own work (opening the lake, the reference rebuild, the export's table rewrites and `profiles.sql`) counts against the bound, shared equally across the hours the run processed. `dp transform` or `dp export` run alone counts its own time against the same bound. | 5.4.1 |
| H11 | A bronze file that is unreadable (`BRONZE_HOUR_UNREADABLE`), or holds a repeated ID, a null, another hour than its name or an unknown time left (`BRONZE_HOUR_INVALID`), is unexpected: `dp transform` stops at that hour with exit `70`, keeping the hours before it, and every run stops there until the file is repaired. | 5.2.1 *When it fails* |
| TM | Every job's final line carries `total_seconds` and each step's seconds, for the steps the run reached: for `dp hourly`, `collect_seconds`, `items_seconds`, `transform_seconds` and `export_seconds`; for `dp daily`, `close_seconds`, `export_seconds`, `push_seconds`, `expiry_seconds`, `temporary_seconds` and `items_retry_seconds`, with `attempts`, the count; a single-step command carries its total. A step the run never reached has no key, never null or `0`: under `dp hourly` where the lock is held past the wait, only `collect_seconds` and the total; under `dp daily` every step after the close has its key once the close has ended, one skipped or left included, which shows a time near zero, and only the total and `attempts` where the run ends before. The step times are the last attempt's, and `total_seconds` the whole run's. | 5.3.2 *What the timings are for*; owner, 2026-11-26 |
| U1 | The units: the hourly timer starts at :35 UTC and the daily at 00:50 UTC, both persistent; both services have `Restart=no`; `RuntimeMaxSec` is 55 min for the hourly (the item fetch's end, 50 min after the start, and the 5 min bound) and 165 min for the daily (the 130 min retries span, the 10 min lock wait, the 15 min day close bound and the 10 min after-close allowance), each derived from 5.4.1's settings. `dp-run` run by hand while its job's run is live exits `75`; with the lock file missing, a `DP_ENV_FILE` that names no environment or a stopped container holding the name, the run by hand exits `2`, and `dp-run` never makes the lock file. A unit that shows `failed` is a run that did not complete; a run over its limit is stopped, and the next timer start repeats what it left. | 5.3.2 *When a job fails*, *Install the units*, *`dp-run`'s exit statuses*; 5.4.1; 5.1.1 |
| P1 | The profile view has a row for each item with an `item_hour` row at the latest hour: every commodity listed then (about 10,500) and each whose listings all ended in that hour. The view is filterable by name, class and subclass. | 5.2.3 *Which items*; 5.4.2 *Views and macros*; delphside/dark-portal#7 decision 3 |
| P2 | Lowest is the lowest unit price in the latest snapshot. | 5.2.3 |
| P3 | *changed*: Fill price for N is the average unit price of the cheapest N units, with the units it covers; where fewer than N are listed, it covers all and says how many; where none are, both the price and the units are null. N below 1, or not a whole number, is refused. It is held to two decimal places of copper, rounded half away from zero. | 5.2.3; 5.4.2; 5.4.5 |
| P4 | *changed*: Default N is the median hourly `sold_estimate_units` over the default N window (7 days) ending at the hour, rounded up, at least 1; where the window holds no hour to count, it is 1. A window ending at an hour holds that hour and the hours before it, to the window's length: 168 hours for 7 days. An item with no row in a held hour counts that hour as 0 (P14). | 5.2.3 *The price now*; 5.4.2 `default_n`; 5.4.1 |
| P5 | *changed*: Prices are shown beside the vendor sell price (`vendor_sell_price`, 0 where the body gives none). A profile does not show `purchase_price` or `vendor_sells`. | 5.2.3; 5.4.5 |
| P6 | *changed*: The depth ladder runs from the lowest price up: units at the price, units at or below, and hours = units at or below ÷ the mean hourly sold estimate over the hours held in the 24 h turnover window; null (*no sales seen*) where the window sold nothing. It stops at the first price whose hours reach 48, which it shows, or at the last price. | 5.2.3; 5.4.1 |
| P7 | Flows per hour: posted (EV-1), sold floor (EV-2), sold estimate (floor + EV-3), expired (EV-5), cancelled (EV-6). Posted and the floor are lower bounds; R7's turnover per hour is shown as the sold floor, with the estimate beside it. | 5.2.3 *Flows* |
| P8 | Hourly history for the hourly keep: lowest, fill price for any N, units listed, ladder and flows. | 5.2.3; delphside/dark-portal#7 decision 5 |
| P9 | `dp daily` writes `item_day`: the lowest of any hour; the median hourly fill price at the default N at 00:00 that day (`DECIMAL(18, 2)`), over the hours with any listed, null where none had; posted, floor and estimate, each summing the day's hours that are not null; `hours_held`. A day is closed once each of its hours is processed or recorded as a gap; the hours before the first snapshot collected are not the day's, so the first day closes on the hours it has. `dp daily` closes every day that can be closed and is not (DC). | 5.2.3 *History*; 5.4.2; 5.4.5 |
| P10 | A missed hour shows as a gap, never as a zero. | 5.2.3 |
| P11 | *changed*: The `profile` view gives each item with a row at the latest hour: the reference columns (`name` is the ID until there is a response), `lowest`, `units_listed`, the fill price at default N and the units it covers, and each flow's total over every hour held in the turnover window. | 5.4.2 |
| P12 | *changed*: The views and macros are defined once in `sql/profiles.sql` over the gold and reference table names, with the three windows read from settings macros that `dp` makes; `dp` loads it over the lake; `export/profiles.sql` is views named as those tables over the export's files, the settings macros, then `sql/profiles.sql` unchanged, so a client computes nothing of its own. A client sets `export_dir` to the export's folder first; unset, the views read the working folder. | 5.1.1; 5.4.2; 5.2.3 *Clients* |
| P13 | An item with no listings in an hour, but listings the hour before, has an `item_hour` row with no lowest price (`lowest` null) and its flows. | 5.2.3 *History*; 5.4.5 |
| P14 | *changed*: A median or a mean of hourly flows, the default N (P4) and the depth ladder's divisor (P6), counts only the hours held with a span of 1, since an hour after a gap holds the flows of several; an item with no row in such an hour counts it as 0. A total, a day's (P9) or the profile's (P11), takes every held hour, and so does a day's median fill price. An hour is *held* in gold where any item has a row for it. | 5.2.3 *The price now*, *History*; 5.2.2 *Times* |
| P15 | `hourly_history` gives each `item_hour` row with the item's name, `daily_summary` each `item_day` row with the item's name, and `held_hour` the hours gold holds with their span. | 5.4.2 *Views and macros* |
| X1 | Exit `0`: done, with at most warnings. | 1.10; 5.2.1 |
| X2 | Exit `75`: a timeout, 429, 502, 503 or 504 when the retry window closes; `last-modified` still before the current hour when it closes; `last-modified` in the hour after the current one, the current hour a gap; the lock wait running out. | 5.2.1 *When it fails* |
| X3 | *changed*: Exit `2`: a new token refused (401), including after a cached one was refused; 403 or 404 on the snapshot; a `last-modified` whose hour is two or more after the current one; disk full; DuckDB out of memory (`OUT_OF_MEMORY`) in `dp transform` run alone or in opening the lake in `dp export` run alone, and in `dp daily` before its pivot (DX). | 5.2.1 *When it fails*; 5.1.1 *Restarts and recovery* |
| X4 | *changed*: Exit `70`: Blizzard answers 400, 500 or another status, a body the parser cannot use, or no `last-modified`; DuckDB failing to write a bronze file in `dp collect` (`BRONZE_WRITE_FAILED`, out of memory included), and in `dp items` before its first request, or failing to read bronze there (`BRONZE_READ_FAILED`). | 5.2.1 |
| X5 | *changed*: Exit `3`: an item lookup (401 included, 404 not), the transform or the export failed after the pivot; DuckDB failing to write the item responses in `dp items` after its first request; `dp export` run alone out of memory in reading the committed hours, rewriting `item_day` or `item` or writing an hour. | 5.2.1 |
| X6 | Before the pivot a failure leaves no temporary or partial file. Usage errors exit `64`; a signal is unexpected; errors are 1.10's result object; a business error is logged at `INFO`, a technical one at `WARN`. | 1.10 |
| DX | *changed*: `dp daily`'s pivot is the day's commit. It exits `75` where the lock is held past the wait, the day before cannot yet be closed or too little time is left before the daily deadline to close; `2` where a technical, fundamental error stops it before the pivot (a full disk, or DuckDB out of memory in opening the lake or in the close) and `70` on an unexpected error there; `3` where the export, a push, a deletion, the clearing of temporary files or an item retry fails after it, or is left because the daily deadline passed, which the next run repeats; otherwise `0`, an item answering 404 again included. | 5.1.1 *Restarts and recovery*; 5.4.2 *The daily deadline* |
| K1 | *changed*: `dp daily` deletes lake rows older than their keep (hourly gold 4 weeks; daily, silver and `meta` kept), then their files by DuckLake's snapshot expiry and file clean-up, every night whether or not a row was deleted, so a clean-up that failed is repeated. The expiry removes the snapshots older than the lake snapshot keep (7 days), so a past state is queryable for that time; the clean-up then deletes the files no remaining snapshot holds. A keep deletes what is older than it, by the hour or day the row or file is for. | 5.4.2 *Expiry*; 5.4.1 |
| K2 | *changed*: `dp daily` pushes bronze to the bucket under its host paths, and `daily/item_day.parquet` and `daily/item.parquet`, copies of the export's, every run. It deletes host bronze *snapshot* files older than 7 days once the bucket holds them (K5), or with no bucket (`DP_BUCKET` empty) once past the keep; item files are kept. The bucket keeps `bronze/` a year by its lifecycle rule, and `daily/` indefinitely. | 5.1.1; 5.4.2 *The bucket*, *Expiry*; 5.4.1 |
| K3 | `dp daily` deletes export hour files older than the hourly keep. | 5.4.2 *Expiry* |
| K4 | `dp daily` asks again for each item whose latest response is a 404. | 5.1.1; 5.2.1 *Item data* |
| K5 | The push: what the bucket holds is what `state/bucket-pushed.txt` records, a first line naming the bucket (`DP_BUCKET`), then one host path to a line, each recorded once its push has succeeded; a record of another bucket, or without the line, is read as empty, so nothing is taken to be in this bucket and no host snapshot is deleted on it. Each object is one HTTPS `PUT` to the write-only pre-authenticated URL in `DP_BUCKET_ACCESS_FILE` (read only where `DP_BUCKET` is set), which is a secret. A blip (C8, with the bucket's `Retry-After`) is asked again after the backoff, up to 3 attempts for one object in a run, each upload bounded at 5 min; an object put after being asked again is a warning (`PUSHED_AFTER_RETRIES`, named in `objects_pushed_after_retries`) and the run exits `0`. A 500 or any other unexpected status is that object's own error and the push carries on; a bronze file that cannot be read on the host is skipped the same way; both exit `3`. What every later object would meet, a bucket still down after the attempts or the access refused (`BUCKET_ACCESS_REFUSED`), ends the push, and the error says how many objects were left. | 5.4.2 *The bucket*; 5.3.2 *The bucket's access*; 5.4.1; 1.10 |
| K6 | `dp daily` removes the `*.tmp` files a killed run left in bronze, except one a running run may still be writing: a file is stale only after its work's end plus the lock wait plus the temporary file margin (2 min). A snapshot's work ends at the close of the retry window of the hour in its name plus the snapshot HTTP timeout; an item run's, at the end of its fetch. Every DuckDB connection spills to a folder of its own, `state/duckdb-tmp/<pid>-<16 hex random>`, which the job removes when the connection closes; `dp daily` removes one that nothing has touched for the daily run time limit plus the temporary file margin (167 min). | 5.4.2 *Expiry*, *The lake*; 5.4.1 |
| DL | `dp daily` holds the lock from its start. The daily deadline is the lock wait before the next hourly run starts (01:25 for an attempt that takes the lock at any time from 00:50 to 01:34). After the close the order is the export, the push, the deletions, the stale temporary files, then asking again for items. The deadline gates the push, the lake's row deletion and file clean-up (together) and asking again for the items that answered 404: past it none starts, and a push never starts an attempt or a wait that could end after it; each left is one error saying what and how many, and the run exits `3`. The export runs past the deadline, and so do the deletion of export hour files (K3), the deletion of host bronze snapshots (K2) and the clearing of stale temporary files and spill folders (K6). The daily after-close allowance (10 min) is the time for these and for the lake deletion once started. Nothing times the export: one still running when the run reaches the daily run time limit (165 min) is stopped there, and the next run repeats it. The close is timed: over the day close bound (15 min) it is a warning (`DAY_CLOSE_OVER_BOUND`) and is not aborted. An attempt holding the lock with less than the day close bound plus the allowance, 25 min, before its deadline closes nothing, releases the lock and exits `75` (`DAILY_TOO_LATE_TO_CLOSE`); one with that or more closes. | 5.4.2 *The daily deadline*; 5.4.1; 5.1.1 |
| DC | A day is closed where `meta.day_closed` has a row for it or `item_day` has rows for it, as in a lake rebuilt with `item_day` restored: such a day is never recomputed, and the close only records it in `meta.day_closed`, in the transaction of the days it closes. `meta.day_closed` records every day closed, one with no item row included. A day whose 00:00 is past the hourly keep but whose later hours are in the lake is closed. A closable day never closed with no hour left (every hour past the hourly keep) cannot be closed: `dp daily` warns naming it (`DAY_EXPIRED_UNCLOSED`), lists it in `days_expired_unclosed` and records it in `meta.day_expired` in the close's transaction, so the warning is given once. An hour of the day before neither processed nor a gap stops the run before it does anything else, exit `75`. The run's report is a warning whenever any warning was raised in it (`DAY_EXPIRED_UNCLOSED`, `DAY_CLOSE_OVER_BOUND` or `PUSHED_AFTER_RETRIES`), logged as it is raised, and an error where a step failed. | 5.4.2 *gold*, *meta*; 5.1.1 *Data layers* |
| E1 | *changed*: `dp export` writes, each under a temporary name then renamed: a `price_level_hour` and an `item_hour` file per committed hour within the hourly keep that the export lacks, oldest first (an hour with no rows has a file with the columns and no rows); `item_day.parquet` and `item.parquet` rewritten only where the table differs from the file; `profiles.sql` rewritten only where its text differs. A run with nothing new writes nothing. It removes any `*.tmp` file a killed run left, under the lock. A copy taken mid-run may be uneven; the next copy levels it. | 5.4.2 *The export*; 5.1.1; delphside/dark-portal#7 decision 8 |
| SEC | *changed*: The client secret comes from `DP_BLIZZARD_CLIENT_SECRET_FILE`, and the bucket's pre-authenticated URL from `DP_BUCKET_ACCESS_FILE`; neither ever appears in logs, bronze or the export. | 5.4.1; 5.3.2 |
| REF | *changed*: Reference is fetched once per item in stage 1; `reference.item` takes the latest response with status 200 per item from bronze, by `fetched_at` then file name. A 404 is no answer: an item with only 404s has no row, and one whose latest response is a 404 after a 200 keeps the 200's. `name`, `class` and `subclass` are null where the body lacks them; `vendor_sell_price` is 0 where it lacks `sell_price`; `purchase_price` is Blizzard's, kept as given (0 stays 0), null only where the body lacks it; `vendor_sells` is `BOOLEAN` true, false or null, and null (unknown) for every item now. `dp transform` rebuilds it once a run, after the hours, as its own transaction, writing nothing where the rebuilt table equals the one held; a bad item file fails that step, not an hour. | 5.1.1; 5.4.2 *reference*; 5.4.5; delphside/dark-portal#7 decision 11 (owner, 2026-11-26) |
| BK | The backup is what the bucket holds and keeps: bronze, pushed by `dp daily` and kept a year, and the daily history (`daily/item_day.parquet`, `daily/item.parquet`), pushed by `dp daily` and kept indefinitely. The restore from it after a lost host, its steps and its drill, are in delphside/dark-portal#38 *Restore Dark Portal after a lost host*. | 5.1.1 *Restarts and recovery*, *Data layers*; 5.4.2 *The bucket* |

### Checked for contradiction

- **X-c4, the `unsold` state.** The diagram keeps the state; the prose says
  it is a step, not a state. Wording only.

## 2. Conditions, grouped into dimensions

- **D1, mark** (complete): D1.1 intact · D1.2 reduced ·
  D1.3 gone · D1.4 *changed*: quantity up on a live ID, intact with a warning
  naming it · D1.5 *changed*: an ended ID reappearing, whatever its value ·
  D1.6 price changed on a live ID, quantity the same: kept, no event, a warning
  · D1.7 price changed and quantity down: reduced, the drop priced at the new
  price · D1.8 a raised listing then sold: `units_sold` above its first
  quantity · D1.9 an ended ID reappearing above the highest live ID · D1.10 an
  ended ID reappearing at a price below the head's.
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
  · D10.2 equal, at :00:00, :31:40 or :59:59 · D10.3 the hour after it, at
  :00:00 or :59:59 · D10.4 missing ·
  D10.5 the host's time zone not UTC · D10.6 a run started inside the previous
  hour's retry window (11:10), that hour unfetched · D10.7 the same, that hour
  collected · D10.8 a run started after that window (11:30) · D10.9 a run in the
  previous hour's window while Blizzard already serves the current hour · D10.10
  two hours or more after it.
- **D11, Blizzard's answer** (not complete): D11.1 200 · D11.2 timeout · D11.3
  429 · D11.4 502, 503, 504 · D11.5 *changed*: 500, unexpected ·
  D11.6 an unusable body · D11.7 401 for a new token · D11.8 401 with a cached
  token, then a new token accepted · D11.9 401 with a cached token, then the new
  token refused · D11.10 403 or 404 · D11.11 an unknown field · D11.12 429 with
  `Retry-After` · D11.13 400, or another status (418) · D11.14 408
  (unexpected) · D11.15 Blizzard unreachable (a blip).
- **D12, a blip** (complete): D12.1 clears before :25 · D12.2 persists to :25.
- **D13, token** (complete): D13.1 none · D13.2 61 min left · D13.3 60 · D13.4
  59.
- **D14, an item** (complete): D14.1 has a response · D14.2 absent, fetch ok ·
  D14.3 absent, blip still failing at the fetch's end · D14.4 absent, 404 ·
  D14.5 absent, 401 then a new token accepted · D14.6 absent, 401 then the new
  token refused · D14.7 absent, 400, 403, 408, 500 or an unreadable body ·
  D14.8 latest response a 404, at `dp daily`: answers 200 · D14.9 the same,
  answers 404 again · D14.10 a blip pauses the whole fetch, the item goes to
  the back and is asked again, and answers · D14.11 asked a third time and
  still a blip: left to the next run · D14.12 a request whose 10 s timeout would
  end after :25 (started at :24:51) · D14.13 one that would end before it
  (started at :24:49) · D14.14 `dp items` run alone with bronze unreadable,
  before its first request.
- **D15, disk** (complete): D15.1 room · D15.2 full during the write.
- **D16, lock** (complete): D16.1 free · D16.2 held, released inside 10 min ·
  D16.3 held for 10 min or more · D16.4 held by a retrying hourly run when `dp
  daily` starts · D16.5 a person's writing subcommand · D16.6 `collect` polling
  a late snapshot while another environment's job runs · D16.7 another job
  asking for the lock between `collect`'s rename and the end of `export` ·
  D16.8 `dp hourly` where `collect` took none (its hour collected already, or
  it failed first): the lock taken for `items` · D16.9 that lock held past the
  wait.
- **D17, transform** (complete): D17.1 high-water mark at
  the previous hour · D17.2 k hours behind · D17.3 hour already processed ·
  D17.4 a failure part-way through an hour · D17.5 the latest hour not yet
  collected, no later snapshot held · D17.6 an hour missing between two held ·
  D17.7 a bronze file unreadable · D17.8 one holding a repeated ID · D17.9 one
  holding a null · D17.10 one holding another hour than its name · D17.11 one
  holding an unknown time left.
- **D18, `dp hourly`'s path and exit** (complete): D18.1 a fresh collection,
  every step 0 · D18.2 collect exits 0 at step 1 · D18.3 collect exits 75, 2 or
  70, later steps 0 · D18.4 collect exits 75 and a later step fails · D18.5
  collect 0 and a later step fails · D18.6 collect exits 0 at step 1 and the
  lock is held past the wait: later steps not run, exit 75 · D18.7 collect
  exits 2 or 70 and the lock is held past the wait: later steps not run, that
  exit · D18.8 collect exits 75 and the lock is held past the wait: 75.
- **D19, N** (complete): D19.1 1 · D19.2 inside a level · D19.3 exactly the
  units listed · D19.4 more than listed · D19.5 0 or negative · D19.6 default ·
  D19.7 an average with more than two decimals, below and at a half · D19.8
  *changed*: nothing listed, the price and units both null · D19.9 N not a
  whole number (1.5).
- **D20, default N history** (complete): D20.1 168 held hours, odd middle ·
  D20.2 a .5 median · D20.3 all 0 · D20.4 48 hours held · D20.5 gaps in the
  window · D20.6 an hour with span > 1 in the window · D20.7 the first hour
  (span null) in the window · D20.8 the window's edges: the hour itself and the
  hour 167 before, both in, and the hour 168 before, out · D20.9 no span-1 hour
  in the window · D20.10 the item has no row in some held span-1 hours of the
  window (counted as 0) · D20.11 the item has no row in a held hour with span >
  1 (left out).
- **D21, ladder** (complete): D21.1 ends at the last price · D21.2 reaches 48 h
  exactly · D21.3 crosses 48 h · D21.4 no sales in the window · D21.5 a single
  price · D21.6 fewer than 24 hours held in the window · D21.7 an hour with span
  > 1 in the window · D21.8 the item has no row in some held span-1 hours of the
  turnover window (counted as 0).
- **D22, an item's listings in C** (complete): D22.1 some · D22.2 none, some the
  hour before · D22.3 none, none the hour before · D22.4 first appearance ·
  D22.5 none in any hour of a day.
- *changed*: **D23, the reference's price and vendor columns** (complete): D23.1
  `purchase_price` present and above 0, kept as given · D23.2 present and 0,
  kept as 0 · D23.3 absent from the body: null · D23.4 `vendor_sells` null for
  every item, with a body that has a `purchase_price` and one that has none ·
  D23.5 the profile shows `vendor_sell_price` and neither `purchase_price` nor
  `vendor_sells` · D23.6 `sell_price` absent: `vendor_sell_price` 0.
- **D24, age against keep, by the row's or file's hour or day** (complete):
  D24.1 within · D24.2 exactly the keep · D24.3 older · D24.4 at 00:50, the hour
  4 weeks before that day's 00:00, and the hour after it · D24.5 a lake
  snapshot exactly 7 days old, and one older · D24.6 a file clean-up that
  failed the night before, with no row deleted tonight.
- **D25, bucket** (complete): D25.1 set, holds the file · D25.2 set, not yet
  holding it · D25.3 empty · D25.4 the daily history pushed · D25.5 host item
  files past 7 days · D25.6 `DP_BUCKET` set, so `DP_BUCKET_ACCESS_FILE` is read
  · D25.7 `DP_BUCKET` empty, so it is not read · D25.8 the pushed record names
  another bucket, or lacks the first line · D25.9 a path recorded only after its
  push succeeded.
- **D26, export** (complete): D26.1 one hour · D26.2
  catch-up of k hours · D26.3 failure, then the next run · D26.4 a lacking hour
  older than the hourly keep · D26.5 copied mid-run · D26.6 `item_day` and
  `item` equal their files, so not rewritten · D26.7 one differs, so rewritten ·
  D26.8 `profiles.sql` text the same · D26.9 its text differs · D26.10 a `*.tmp`
  file left by a killed run, removed under the lock · D26.11 `export_dir` set ·
  D26.12 `export_dir` unset · D26.13 an hour with no rows: a file with the
  columns and no rows · D26.14 a run with nothing new.
- **D27, day** (complete): D27.1 24 hours held · D27.2
  hours missed · D27.3 an hour neither processed nor a gap when `dp daily` runs
  · D27.4 that hour processed before a retry · D27.5 not closable before 03:00,
  closed the next night with the following day · D27.6 the first hour collected
  inside the day (null flows) · D27.7 hours with nothing listed · D27.8 the
  first day, starting mid-day · D27.9 a day with `item_day` rows and no
  `meta.day_closed` row (a restore): recorded, not recomputed · D27.10 a day
  with no item row at all: closed, to no rows, once · D27.11 a closable day
  never closed, every hour of it past the hourly keep · D27.12 the same on the
  next night · D27.13 a day whose 00:00 is past the hourly keep but whose later
  hours are in the lake · D27.14 a closed day on the next run: not recomputed ·
  D27.15 a rebuilt lake: days warned of are not rebuilt · D27.16 migration 5 on
  a lake that holds `item_day` rows: those days recorded closed.
- **D28, the error that stops a run** (complete): D28.1 usage · D28.2
  fundamental · D28.3 blip run out · D28.4 unexpected · D28.5 signal · D28.6 `dp
  transform` run alone out of memory: exit 2 · D28.7 `dp export` run alone out
  of memory: in opening or migrating the lake, exit 2; in reading the committed
  hours or rewriting `item_day` or `item`, an error for no hour, and in writing
  an hour, an error for that hour, after which the export writes no more, exit 3
  · D28.8 either `dp transform` or `dp export` under `dp hourly`: that step's
  failure, and the run exits as H0 says · D28.9 DuckDB failing to write a bronze
  file in `dp collect`, out of memory included: `BRONZE_WRITE_FAILED`,
  unexpected, exit 70 · D28.10 `dp items` where DuckDB fails to write:
  before its first request, `BRONZE_WRITE_FAILED`, exit 70; after it, a
  carried error, exit 3 and the items not written fetched next run · D28.11
  `dp items` where DuckDB fails to read bronze before its first request:
  `BRONZE_READ_FAILED`, exit 70.
- **D29, `dp daily`'s exit** (complete): D29.1 lock held past the wait · D29.2
  the day before not closable · D29.3 disk full · D29.4 unexpected · D29.5 a
  push fails · D29.6 a deletion fails · D29.7 an item retry fails · D29.8 an
  item answers 404 again · D29.9 all done · D29.10 too little time to close ·
  D29.11 the deadline passed before the push · D29.12 the bucket's access
  refused · D29.13 out of memory in opening the lake or in the close: exit 2
  (5.1.1 *Restarts and recovery*) · D29.14 out of memory in the export: an
  error, exit 3 (5.1.1 *Restarts and recovery*).
- *changed*: **D30, an hour's `transform` and `export` time** (complete): D30.1
  under 5 min · D30.2 exactly 5 min · D30.3 over 5 min · D30.4 `dp transform`
  run alone, its own time · D30.5 `dp export` run alone, its own time · D30.6 a
  run of several hours, its own work shared equally across them (5.4.1) · D30.7
  a run whose own work alone (lake opening, reference rebuild, table rewrites,
  `profiles.sql`) is over the bound.
- **D31, `dp daily`'s retries** (complete): D31.1 an attempt exits 75, the next
  starts 15 min after its end and exits 0 · D31.2 the next attempt would start
  at 02:59:59 (before 03:00) · D31.3 at 03:00:00 · D31.4 a run started by hand
  at 00:10, so the span ends at 02:20: an attempt ending 02:04:59, and one
  ending 02:05:00 · D31.5 a run started by hand at 01:30, so 03:00 is the end ·
  D31.6 a persistent timer's catch-up at 03:30: one attempt · D31.7 a first
  attempt exiting 2, 3 or 70: no retry · D31.8 the retries run out: the exit is
  75 · D31.9 an attempt of 3 min: the interval counts from its end ·
  D31.10 a run started at 22:00 (03:00 of its day past): one attempt.
- **D32, the daily deadline and the close gate** (complete): D32.1 the lock
  taken at 00:52, 33 min before the 01:25 deadline: closes · D32.2 at 01:00:00,
  exactly 25 min: closes · D32.3 at 01:00:01: closes nothing, exit 75 · D32.4
  at 01:27, past the deadline: closes nothing, exit 75 · D32.5 at 01:40, whose
  deadline is 02:25: closes · D32.6 a close of 16 min (over the day close
  bound) · D32.7 the deadline passes during the push · D32.8 a push attempt or
  backoff wait that could end after the deadline · D32.9 the order after the
  close · D32.10 an export still running when the run reaches the daily run
  time limit, which nothing else times: stopped there, and the next run writes
  what it lacks.
- **D33, the push** (complete): D33.1 every object accepted · D33.2 a 503 then
  accepted · D33.3 a 429 with `Retry-After` honoured · D33.4 three blips on
  one object ends the push, the later objects left and counted (5.4.2 *The
  bucket*) · D33.5 a 500 on one object, the rest pushed · D33.6 a
  bronze file unreadable on the host, the rest pushed · D33.7 access refused,
  the push ended with the count left · D33.8 an upload over 5 min · D33.9 the
  pushed URL never in the log, bronze or the export.
- **D34, stale files** (complete): D34.1 a snapshot `*.tmp` before its retry
  window closes plus the snapshot timeout, the lock wait and the margin ·
  D34.2 the same, after · D34.3 an item run's `*.tmp` before its fetch end plus
  the lock wait and the margin · D34.4 after · D34.5 a spill folder untouched
  for under 167 min · D34.6 for over · D34.7 a running job's spill folder ·
  D34.8 two connections of one job, each with its own folder · D34.9 a
  connection closed, its folder removed.
- **D35, a job's timings** (complete): D35.1 `dp hourly` run through, a failed
  step included, with every step's time · D35.2 `dp daily` with two attempts ·
  D35.3 a single-step command · D35.4 `dp hourly` where the lock is held past
  the wait: `collect_seconds` and the total only · D35.5 `dp daily` once its
  close has ended, with no bucket, with a step left past the deadline or with a
  step failing: all six step keys, a skipped or left step near zero, and
  `attempts` · D35.6 `dp daily` that ends before its close has ended (the lock
  held past the wait, too late to close, the day before not closable, the close
  failing): the total and `attempts` only (5.3.2 *What the timings are for*).
- **D36, reference** (complete): D36.1 two 200s: the later `fetched_at` wins ·
  D36.2 the same time: the later file name wins · D36.3 only 404s: no row ·
  D36.4 a 200 then a 404: the 200 kept · D36.5 `name`, `class` or `subclass`
  absent: null · D36.6 the rebuilt table equals the one held: nothing written
  · D36.7 a bad item file: the step fails, the hours are committed · D36.8 no
  response: the profile shows the ID.
- **D37, units and `dp-run`** (complete): D37.1 the timers' start and
  persistence · D37.2 `Restart=no` · D37.3 `RuntimeMaxSec` against the settings
  · D37.4 a run over it · D37.5 a run by hand while its job is live · D37.6 a
  stopped container holding the name · D37.7 the lock file missing · D37.8
  `dp`'s own statuses reach the unit unchanged · D37.9 `dp-run`'s own mapping
  (5.3.2 *`dp-run`'s exit statuses*): `-h` or `--help` 0; usage 64; a missing
  setting, a `DP_ENV_FILE` whose name (less any `.env`) is not a letter or digit
  followed by letters, digits, `_`, `.` and `-`, or the lock file missing 2; the
  docker daemon unreachable, `docker ps` failing or a run of the same job live
  75; docker's 125, 126 and 127 2; anything else, such as 137, 70.

## 3. Outcomes

| ID | Outcome |
| --- | --- |
| O1 | `posted`: units = quantity, `certain`, `EV-1`, hour C, span. |
| O2 | A warning naming the ID is logged; the event is still written; the run exits `0`. |
| O3 | *changed*: `partly_sold`: units = the drop, priced at the listing's current price, `certain`, `EV-2`. |
| O4 | *changed*: `sold`: units = the quantity when last seen, `inferred`, `EV-3`, `tie` false. |
| O5 | `expired`: `inferred`, `EV-5`, `tie` per EV-4. `duration` is the shortest matching D where the posting hour is known, and null where the band decided. |
| O6 | `cancelled`: `inferred`, `EV-6`, `tie` per EV-4; `duration` null. |
| O7 | Exactly one event per gone listing, and none of kind `unsold`. |
| O8 | Intact: no event, one `listing_hour` row, `last_seen` = C. |
| O9 | The `listing_record` has the values L2 says; the live and history rows are deleted. |
| O10 | `posted` and every `posting_*` are null. |
| O11 | The event's hour is C's; `span` = C − the last hour held. |
| O12 | *changed*: `meta.gap` has one row per hour missing between two snapshots held, with `found_at`, written by `dp transform` in the later hour's transaction. |
| O13 | A whole bronze file at the final name; no temporary file. |
| O14 | Exit `0` at step 1: no request made and nothing written. |
| O15 | Exit `75`, nothing written; the hour later recorded as a gap. |
| O16 | Exit `0` with a warning (a cleared retry, a renewed token or the field's name). |
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
| O29 | *changed*: The ladder rows, the row it stops at and the hours, null where there are no sales seen. |
| O30 | The flows have the expected values, with floor ≤ estimate. |
| O31 | No `item_hour` row for a missed hour; the next row carries the span. |
| O32 | `item_day` has the expected values, including `hours_held` and `default_n`. |
| O33 | The profile has a row per item, showing the ID where there is no reference. |
| O34 | Rows and files older than their keep are deleted; those at or within it are kept; the lake's files are cleaned up. |
| O35 | Host bronze is deleted as K2 says. |
| O36 | *changed*: The export files are as E1 says and always whole; nothing is written where nothing differs. `profiles.sql` over the export gives the same numbers as `dp` over the lake. |
| O37 | The lock is waited for up to 10 min, then the run exits `75` with nothing changed. |
| O38 | Exit `70` or `64`; the result object's fields are present. |
| O39 | The token is reused or renewed, as expected. |
| O40 | Backoff of 30, 60, 120, 240, 300 s, or the `Retry-After`; a 2-minute poll; timeouts of 60 and 10 s. |
| O41 | A rebuild from bronze equals an incremental build from the same first hour. |
| O42 | The secret is absent from logs, bronze and the export. |
| O43 | An ad hoc query takes no lock and runs with the `DP_ADHOC_*` limits. |
| O44 | *changed*: The reappearing ID, whatever its value: a warning naming it; no event, no live row, no place in any queue; its record unchanged. |
| O45 | Exit `2` before any file is written (wrong clock, or 403, 404). |
| O46 | *changed*: `dp daily` itself runs another attempt 15 min after one ends `75`, and none starts at or after the earlier of 03:00 and 130 min after its start; it exits with the last attempt's status; no unit restarts it. |
| O47 | Item 404: a row with status 404 and a null body; a warning naming the item; no error, so no exit `3` from it; not asked again by later hourly runs; asked by `dp daily`. |
| O48 | A sell-out hour: an `item_hour` row with `lowest` null and the hour's flows. No row in a following hour with no listings. |
| O49 | The first hour: live rows with `posted` null; no event rows; `item_hour` and `price_level_hour` with prices and depth, flows and `span` null; `processed` holds it. |
| O50 | *changed*: `items`, `transform` and `export` run after any `collect` result, unless the lock is held past the wait (O66). |
| O51 | *changed*: `fill_price` with N below 1 or not whole raises an error and returns no value. |
| O52 | A day is not closed while any of its hours is neither processed nor a gap; it is closed once all are, by the first `dp daily` after, with any other closable day. |
| O53 | *changed*: `dp hourly`'s exit: `collect`'s where not `0`, else `3` where a later step failed, else `0`; where the lock is held past the wait, `collect`'s where not `0`, else `75`. |
| O54 | *changed*: `dp daily`'s exit as DX; on `3`, the day stays closed and the next run repeats the failed or left step; on `75`, nothing changed. |
| O55 | Hours with span > 1 or null are left out of default N and the ladder's mean. |
| O56 | *changed*: Null: the fill price and the units it covers with nothing listed; `median_fill_price` where no hour had any listed. |
| O57 | The bucket holds the bronze files under their host paths and `daily/item_day.parquet` and `daily/item.parquet`, equal to the export's; host item files are never deleted. |
| O58 | The first day is closed on the hours it has, by the first `dp daily` after its last hour, with `hours_held` counting them; the run exits `0` and pushes and deletes as on any night. |
| O59 | No lock is held while polling; it is taken for the rename, and under `dp hourly` held until `export` ends. |
| O60 | A run started inside the previous hour's window collects that hour, or exits `0` at step 1 if it is held; after the window, the current hour. |
| O61 | `default_n` is 1 where the window holds no hour to count. |
| O62 | *changed*: No warning where an hour's `transform` and `export`, with the run's own work shared across its hours, took 5 min or less; over it, a warning naming the hour and its time, and the run completes with exit `0`. A step run alone is judged on its own time. |
| O63 | A changed live listing is kept as it is now: a raised quantity or a changed price alone gives no event and a warning naming the ID; a drop at a changed price gives `partly_sold` at the new price; `units_sold` can exceed `quantity`. |
| O64 | The transform stops at the invalid or unreadable hour with exit `70`, the earlier hours kept; every later run stops there until the file is repaired. |
| O65 | No gap for a latest hour not yet collected; a gap row for an hour between two held, written with the later hour. |
| O66 | Where the lock is held past the wait, `items`, `transform` and `export` do not run, and nothing is written by them. |
| O67 | One attempt where the run starts at or after 03:00 UTC. |
| O68 | An attempt with 25 min or more before its deadline closes; with less it closes nothing, releases the lock, logs `DAILY_TOO_LATE_TO_CLOSE` and exits `75`. |
| O69 | Past the deadline nothing the deadline gates starts: each left step is one error saying what and how many, and the run exits `3`; a close over 15 min is a warning (`DAY_CLOSE_OVER_BOUND`) and completes. |
| O70 | `meta.day_closed` has a row for each closed day (empty days and `item_day`-only days included), written in the close's transaction; a day held in `item_day` is never recomputed; `meta.day_expired` has a row for a day warned of, so the warning (`DAY_EXPIRED_UNCLOSED`) is given once. |
| O71 | The run's report is a warning where any of `DAY_EXPIRED_UNCLOSED`, `DAY_CLOSE_OVER_BOUND` or `PUSHED_AFTER_RETRIES` was raised, logged as raised, and an error where a step failed. |
| O72 | The push is as K5 says: the record holds a path once its push succeeded; an object put after retries is a warning and exit `0`; an object's own failure is exit `3` with the others pushed; refused access ends the push and says how many were left; the URL is in no log. |
| O73 | A stale `*.tmp` or spill folder is removed; one younger than its threshold is kept, as are a running job's. |
| O74 | The job's final line holds `total_seconds` and the seconds of each step that ran, and `attempts` for `dp daily`, the keys by case as D35 says. |
| O75 | `reference.item` holds the values REF says: `purchase_price` as given, 0 included, null only where absent; `vendor_sells` null; nothing written where the rebuild equals the table. |
| O76 | The units are as U1 says; a status passes through `dp-run` as the job's own, and docker's own statuses map as 5.3.2 lists; a run by hand while its job is live exits `75`. |
| O77 | A held span-1 hour in which the item has no row counts as 0 in the median, the mean and so in default N and the ladder's hours. |
| O78 | The item fetch makes no request that could end after :25, and the items not reached are fetched next run. |
| O79 | `OUT_OF_MEMORY` is technical, fundamental. `dp transform` run alone exits `2`. `dp export` run alone exits `2` where it stops in opening or migrating the lake, and `3` where it is an error (reading the committed hours, rewriting `item_day` or `item`, or writing an hour), after which it writes no more. Under `dp hourly` it is that step's failure, and the run exits as H0 says. In `dp daily`, opening the lake and the close exit `2` and the export is an error, exit `3`. In `dp collect`, a DuckDB error writing a bronze file is `BRONZE_WRITE_FAILED`, unexpected, exit `70`, out of memory included. In `dp items`, DuckDB failing to write is `BRONZE_WRITE_FAILED`, exit `70` before its first request and a carried error, exit `3`, after it; DuckDB failing to read bronze is `BRONZE_READ_FAILED`, exit `70`. |

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
| S29 | Item lookup blips, gets 401 (new token accepted, or refused), or 400, 403, 408, 500 or an unreadable body; the next run fetches it | D14.3, D14.5–7 | O20 where the new token is accepted; otherwise O19, O33 with the ID, then O20 |
| S30 | Item pacing | C6, C7 | ≤ 50 a second |
| S31 | Lock held, then released at 9 min; held for 11 | D16.2–3 | completes; O37 |
| S32 | Ad hoc query during the hourly run | H1, H7 | O43 |
| S33 | Catch-up of 3 hours | D17.2, D26.2 | O21, O36 |
| S34 | Transform fails mid-hour; the next run repairs it | D17.4 | O23, O19, then O21 |
| S35 | Reprocessing a committed hour | D17.3 | O22 |
| S36 | `dp hourly`'s order and exit, after each collect result, and with the lock held past the wait | D18, D16.8–9 | O50, O53, O66 |
| S37 | Price now (TD-J) | D19.1–4, D19.7, D23 | O26, O27 (half away from zero); the vendor sell price shown, no `purchase_price` or `vendor_sells` |
| S38 | N = 0, N = −1 and N = 1.5, then N = 1 | D19.5, D19.9 | O51, then O27 |
| S39 | Default N (TD-J, TD-J3, TD-J4, TD-J5) | D20.1–11 | O28, O55, O61, O77 |
| S40 | Ladder (TD-J, TD-J2, TD-J3, TD-J5) | D21 | O29, O55, O77 |
| S41 | Hidden sale; floor ≤ estimate | P7 | O30 |
| S42 | Keep boundaries at `dp daily`, lake and export, by the row's or file's hour; the lake snapshot keep | D24 | O34 |
| S43 | Day close (TD-L) | D27.1–7, D22.5 | O32, O52, O56 |
| S44 | `dp daily` blocked by a retrying hourly run, or by a day not yet closable | D16.4, D29.1–2, D31.1 | O37, O46, O54 |
| S45 | Export: one hour, catch-up, failure then repair, an hour past the keep, a mid-run copy, nothing new, a stale `*.tmp`, `export_dir` and the `profiles.sql` cross-check | D26 | O36, O19 |
| S46 | Host bronze and the daily history, by bucket state | D25 | O35, O57 |
| S47 | Rebuild from bronze | L4 | O41 |
| S48 | Profile view, filter, latest 200 response, missing reference, flows as totals over the window (an hour after a gap included), turnover shown as floor, the history and summary views | P1, P11, P14, P15 | O33, O30 |
| S49 | Secret scan | SEC | O42 |
| S50 | Unexpected error, signal, bad flag | D28.1–5 | O38 |
| S51 | Cached token refused: a new token accepted; or refused too | D11.8–9 | O16; O17 |
| S52 | A `last-modified` two hours or more after the current hour (the host's clock behind), or 403 or 404 on the snapshot; then put right | D10.10, D11.10 | O45, then O13 |
| S53 | 429 with `Retry-After: 120` | D11.12 | O40 |
| S54 | Item 404; hourly runs skip it; `dp daily` asks again: 404 again, then 200 | D14.4, D14.8–9 | O47; `dp daily` exits 0; then O20, the 200 winning in reference |
| S55 | An ended ID reappears, in any value (TD-D4) | D1.5, D1.9–10 | O44 |
| S56 | A person's `dp transform` while the hourly run holds the lock | D16.5 | O37, then completes |
| S57 | Host back at 11:10 after missing the 10:35 run; and at 11:30 | D10.6, D10.8 | O60: hour 10 collected; at 11:30, hour 11 polled and hour 10 a gap |
| S58 | `collect` polls a late snapshot while another environment's transform runs; another job asks for the lock mid-`dp hourly` | D16.6–7 | O59 |
| S59 | `dp daily`'s failures after the pivot, then the next run | D29.3–7, D29.9 | O54, then O32, O35 |
| S60 | A day not closable until after 03:00 | D27.5, D31.2–3 | O46, then O52 the next night |
| S61 | Blizzard already serving hour 11 for a run taking hour 10: at 11:10, and at 10:35 served 11:00:00 or 11:59:59; the 11:35 run follows | D10.3, D10.9 | O15, O12; then O13 for hour 11 |
| S62 | The first day, collection starting at 14:00 on D − 1 | D27.8, D20.9 | O58, O32, O61 |
| S63 | An hour's `transform` and `export` together under, at and over 5 min; a step alone; the run's own work shared | D30 | O62 |
| S64 | A live listing that changes (TD-M) | D1.4, D1.6–8 | O63, O3, O4 |
| S65 | Bronze hour invalid or unreadable | D17.7–11 | O64 |
| S66 | A latest hour not yet collected; an hour missing between two held | D17.5–6 | O65, O12 |
| S67 | `dp hourly` where `collect` took no lock, and the lock held past the wait | D16.8–9, D18.6–8 | O66, O53 |
| S68 | `dp daily` retries itself (TD-N) | D31 | O67, O46 |
| S69 | The close gate and the deadline (TD-N) | D32 | O68, O69 |
| S70 | Closed-day records, a day expired unclosed, run warnings | D27.9–16 | O70, O71 |
| S71 | The bucket push (TD-P) | D33, D25.6–9 | O72, O71 |
| S72 | Stale temporary files and spill folders | D34 | O73 |
| S73 | A job's timings | D35 | O74 |
| S74 | Reference rebuild and its columns (TD-O) | D23, D36 | O75 |
| S75 | The units and `dp-run` | D37 | O76 |
| S76 | Item fetch: a blip pauses it, three attempts, the fetch end (TD-Q) | D14.10–14 | O78, O19 |
| S77 | DuckDB out of memory and bronze failures, by step | D28.6–11, D29.13–14 | O79 |

## 6. Refusals and successes

| Refused | Then succeeds |
| --- | --- |
| S25: a new token refused, exit 2 | the right secret, exit 0 |
| S51: a cached token refused and the new one too, exit 2 | the right secret, exit 0 |
| S26: 500, an unusable body or no `last-modified`, exit 70 | a good response, exit 0 |
| S27: disk full, exit 2 | room, exit 0 |
| S52: the host's clock behind (a `last-modified` two hours or more after the current hour) or 403/404, exit 2 | the clock put right, a 200, exit 0 |
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
| S38: N = 0, N = −1 and N = 1.5 refused | N = 1 answered |
| S20: already collected, exit 0 | the next hour collects |
| S61: Blizzard has moved on, exit 75, hour 10 a gap | the 11:35 run collects hour 11, exit 0 |
| S67: the lock held past the wait, exit 75 | the lock free, every step runs |
| S68: an attempt exits 75 | a later attempt closes the day, exit 0 |
| S69: too little time to close, exit 75 | a retry with 25 min or more closes it |
| S65: a bronze hour invalid, exit 70 | the file repaired, the transform goes on |
| S71: access refused, exit 3 | a renewed URL, and the next run pushes |
| S76: an item left after three blips | the next run fetches it |

## 7. Coverage, both ways

| Rule | Scenarios |
| --- | --- |
| R1 | S37, S48; UT1; PD1 |
| R2 | S11, S42, S43, S60, S62; UT3, UT4; PD2, PD6 |
| R7 | S40, S41, S48; UT2; PD3 |
| R8v | S1, S2, S41; UT3; PD4 |
| T1 | S17 |
| T2 | S1, S11, S12, S14 |
| TR | S1, S2 |
| Q1 | S1, S16 |
| Q2 | S1, S2 |
| Q3 | S1, S2, S16 |
| EV-1 | S1, S7, S10, S11, S55 |
| EV-2 | S1, S2, S8, S64 |
| EV-3 | S1, S2, S3, S4, S6, S64 |
| EV-4 | S1, S4, S5, S6 |
| EV-5 | S9, S10, S11, S13, S14 |
| EV-6 | S1, S9, S10, S11, S13 |
| EVW | S1, S4, S6 |
| EV-7 | S64 |
| L1 | S1, S10, S11 |
| L2 | S15, S64 |
| L3 | S10, S62 |
| L4 | S47; TT6 |
| C0 | S17, S20, S57, S61 |
| C1 | S20 |
| C2 | S18, S19, S29, S51 |
| C3 | S17, S21, S52, S61 |
| C4 | S18, S27, S58 |
| C5 | S28 |
| C6 | S18, S29, S30, S54, S76 |
| C7 | S30 |
| C8 | S22, S23, S24, S53, S76 |
| C9 | TT1, TT8, TT10, S75 |
| C10 | S76 |
| H0 | S36, S67 |
| H1 | S31, S32, S44, S56, S58, S67 |
| H2 | S27, S29, S34, S36, S45 |
| H3 | S11, S21, S33, S34, S61, S66; PD5 |
| H4 | S35 |
| H5 | S11, S12 |
| H6 | S1, S16 |
| H7 | S32; TT3 |
| H8 | S44, S60, S68; TT8 |
| H9 | S57; TT10 |
| H10 | S63; TT1, TT3 |
| H11 | S65 |
| TM | S73; TT3 |
| U1 | S75; TT11 |
| P1 | S29, S48; UT1 |
| P2 | S37 |
| P3 | S3, S37, S38 |
| P4 | S39, S62 |
| P5 | S37 |
| P6 | S40 |
| P7 | S1, S2, S41, S48 |
| P8 | S42 |
| P9 | S43, S60, S62 |
| P10 | S11, S43; PD5 |
| P11 | S48 |
| P12 | S45, S48; UT1 |
| P13 | S3 |
| P14 | S39, S40, S43, S48 |
| P15 | S48 |
| X1 | S7, S22, S28 |
| X2 | S21, S23, S31, S61 |
| X3 | S25, S27, S51, S52, S77 |
| X4 | S26, S77 |
| X5 | S29, S34, S45, S77 |
| X6 | S27, S50 |
| DX | S44, S54, S59, S60, S68, S69 |
| K1 | S42 |
| K2 | S46, S59, S71; TT8; PD6 |
| K3 | S42 |
| K4 | S54 |
| K5 | S71; TT8 |
| K6 | S72 |
| DL | S69; TT8, TT11 |
| DC | S70 |
| E1 | S33, S45; TT7 |
| SEC | S25, S49, S71 |
| REF | S18, S48, S54, S74 |
| BK | S46; TT8; PD6 |

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
| S29 | C6, C2, C8, H2, X5, P1 |
| S30 | C6, C7 |
| S31 | H1, X2 |
| S32 | H1, H7 |
| S33 | H3, E1 |
| S34 | H2, H3, X5 |
| S35 | H4 |
| S36 | H0, H1, H2 |
| S37 | P2, P3, P5, REF, R1 |
| S38 | P3 |
| S39 | P4, P14 |
| S40 | P6, P14, R7 |
| S41 | P7, R7, R8v |
| S42 | K1, K3, P8, R2 |
| S43 | P9, P10, P14, R2 |
| S44 | H1, H8, DX |
| S45 | E1, P12, H2, X5, K3 |
| S46 | K2, BK |
| S47 | L4 |
| S48 | P1, P7, P11, P12, P14, P15, REF, R1, R7 |
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
| S61 | C0, C3, H3, X2 |
| S62 | P9, P4, L3, R2 |
| S63 | H10 |
| S64 | EV-7, EV-1, EV-2, EV-3, L2 |
| S65 | H11 |
| S66 | H3 |
| S67 | H0, H1 |
| S68 | H8, DX |
| S69 | DL, DX |
| S70 | DC, P9 |
| S71 | K5, K2, SEC |
| S72 | K6 |
| S73 | TM |
| S74 | REF |
| S75 | U1, C9 |
| S76 | C6, C8, C10 |
| S77 | X3, X4, X5, H0, DX |

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
- The timers' schedule and persistence are systemd's, so they are tested as
  [TT] on E5. `dp daily`'s own retries, deadline and close gate run on the
  injected clock, so they are [AUTO]; so is a test that reads the units'
  `Restart` and `RuntimeMaxSec` and the timers' start against the settings.

**How time is manipulated.** By an injected clock covering the run's start (the
current hour), the poll, the :25 window, backoff and `Retry-After`, the token
margin, the lock wait, an hour's processing time against its 5-minute bound,
00:50, the 15-minute daily retry, the 130-minute retries span, 03:00, the daily
deadline, the day close bound and the item fetch's end. The documents name no
clock seam (G19), left to Development.

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
  - *changed*: **TD-D4**, 104 ends at h11 (record written). At h12 C holds
    `104` again: a warning naming it, no event, no live row, the record
    unchanged. Variants: an ended ID reappearing above the highest live ID
    (`120`); and `104` at a price below the head's, where the head's
    `units_ahead` and every later listing's `units_ahead` and
    `units_at_or_below` are as if it were absent.
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
  - A run at 11:10 taking hour 10, Blizzard serving 11:05:00: Blizzard has
    moved on, so exit 75 and no file; `dp transform` records hour 10 as a gap,
    and the 11:35 run writes `T11` (S61).
  - For a run at 10:35, 10:00:00 and 10:59:59 both give `T10`; 11:00:00 and
    11:59:59 exit 75 with hour 10 a gap (S61); 12:00:00 exits 2 (S52).
  - A second run at 10:50 exits 0 with no request.
  - 2026-07-01 under `TZ=Europe/London` gives the UTC hour.
- **TD-J, price now.**
  - Listings `501 100×2`, `502 100×1`, `503 110×4`, `504 120×3`. Levels: 100 → 3
    (cumulative 3), 110 → 4 (7), 120 → 3 (10).
  - Fill price: N = 1 → 100.00; N = 4 → 102.50; N = 5 → 104.00; N = 10 → 110.00;
    N = 12 → 110.00 for 10 units, saying 10. N = 9 → 980 ÷ 9 = 108.888… →
    108.89. For a half, a world of `601 100×7` and `602 101×1` at N = 8: 801 ÷ 8
    = 100.125 → 100.13 (half away from zero, where half even gives 100.12).
    The vendor sell price is shown, and neither `purchase_price` nor
    `vendor_sells` (D23.5).
  - Default N over the 168 hours of the window ending at the hour: 83 values of
    2 and 85 of 3 give 3; 84 of each give 2.5, so 3; all 0 gives 1; 48 hours
    held give the median of those 48; with 20 gaps, the median of the 148 held;
    with no hour held in the window, 1.
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
  one span-3 hour at 9: the mean is 2 (44 ÷ 22), not 53 ÷ 23.
- **TD-J4, the window's edges.** Span-1 hours from h − 168 to h, with estimate 0
  at h − 168, 9 at h, and 84 of 2 and 83 of 3 between. The window is h − 167 to
  h, 168 hours: the median is 2.5, so default N is 3. A window holding h − 168,
  or leaving out h, gives 2.
- **TD-J5, items with no row.** The item has a row, sold estimate 4, in 80 of
  the 168 span-1 hours of the default N window and none in the other 88, all
  held (other items have rows there). The median counts 88 zeros and 80 fours:
  0, so default N is 1 (4 if only its own rows were counted). For the ladder,
  a turnover window of 24 span-1 hours holds rows with estimate 4 in 12 and
  none in 12: the mean is 48 ÷ 24 = 2 an hour. An hour with span 3 in which it
  has no row is left out of both.
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
    22. 05:00 has span 3, and its flows count in the day's posted, floor and
    estimate.
  - 23:00 failed in the transform at 00:35: `dp daily` at 00:50 exits 75 and
    does not close D, nor push or delete; its retries at 01:05 and 01:20 exit
    75; the 01:35 run processes 23:00 and the 01:50 retry closes D, exit 0.
  - The transform fails every hour from 22:00 to 03:00: every retry to 03:00
    exits 75; the next night's run closes D and D + 1.
  - 06:00 to 08:00 have nothing listed: `median_fill_price` over the other 21; a
    day with nothing listed in any hour has it null.
  - The first hour collected is 14:00 on D − 1, and its flows are null. The
    hours before it are not D − 1's, so `dp daily` at 00:50 on D closes D − 1 on
    its 10 hours: `hours_held` 10, posted, floor and estimate over 15:00 to
    23:00, and exit 0 with its push and deletions (S62). Its `default_n` at
    D − 1 00:00, with no hour in the window, is 1; so is `default_n` at 14:00,
    whose only hour has span null.
  - `dp daily` after closing D: a failed bucket push exits 3 with D closed; the
    next run pushes, exit 0. A full disk before the commit exits 2 with D not
    closed.
  - **Closed-day records** (D27.9–16): a lake rebuilt from bronze with
    `item_day` restored for D − 3: D − 3 is recorded in `meta.day_closed`, its
    rows unchanged. A day with no item row in any hour is closed to no rows,
    once, with a `meta.day_closed` row. D − 40, with every hour past the hourly
    keep and never closed: one warning naming it, `days_expired_unclosed` 1, a
    `meta.day_expired` row, the run a warning with exit 0; the next night, no
    warning. A day whose 00:00 is four weeks and an hour ago but whose 23:00 is
    in the lake is closed.

- **TD-M, a live listing that changes.** Live after h10: `800 100×5`, `801
  110×4`, `802 120×3`, all first seen h9. C (h11): `800 100×7`, `801 115×4`,
  `802 125×2`.
  - 800: quantity up, intact, no event, a warning naming 800. 801: price
    changed, same quantity, intact, no event, a warning naming 801. 802: price
    and quantity changed, behind intact listings: `partly_sold`, units 1,
    `unit_price` 125, a warning naming it.
  - At h12, 800 is gone from the front: `sold`, units 7 (the quantity last
    seen); its record has `quantity` 5 and `units_sold` 7.
- **TD-N, `dp daily`'s time.** A clock of 00:50 on day D, with the lock held.
  - Retries: attempts 00:50, 01:15, 01:40, then every 25 min (a 10 min lock
    wait and the 15 min interval) while the next start is before 03:00: an
    attempt ending at 02:44:59 gives one at 02:59:59; one ending at 02:45:00
    gives none, and the last status, `75`, is the exit. Started by hand at
    00:10 the end is 02:20, not 03:00; at 01:30, 03:00 not 03:40; at 03:30 or
    22:00, one attempt.
  - The gate: the lock taken at 00:52 (33 min before 01:25) closes; at
    01:00:00 (25 min) closes; at 01:00:01 closes nothing and exits 75 with
    `DAILY_TOO_LATE_TO_CLOSE`; at 01:27 the deadline is 01:25, so it closes
    nothing; at 01:40 the deadline is 02:25, so it closes.
  - The deadline: a push that would start or wait past it does not, and each
    step left (the push, the lake's deletions and the item retry) is an error
    saying what and how many, exit 3. A close of 16 min logs
    `DAY_CLOSE_OVER_BOUND` and completes, and the run is a warning with exit 0.
    The export runs past the deadline, as do the deletion of export hour files,
    the deletion of host snapshots and the clearing of stale temporary files and
    spill folders; nothing times the export, and one still running at the daily
    run time limit is stopped there and repeated by the next run.
- **TD-O, reference.** Bodies: `501` with `sell_price` 50 and `purchase_price`
  55 (kept as 55); `502` with `purchase_price` 0 (kept as 0); `503` with
  neither (`vendor_sell_price` 0, `purchase_price` null); `504` with no name,
  class or subclass (nulls). Two 200s for 501, the later `fetched_at` winning,
  and at one `fetched_at` the later file name; a 404 after a 200 for 502 keeps
  the 200's; an item with only 404s has no row. `vendor_sells` is null in every
  row. A second rebuild with no new file writes nothing.
- **TD-P, the push.** Two new bronze files A and B and the two `daily/` files.
  A's first attempt answers 503 and its second accepts: A is in the record and
  `objects_pushed_after_retries`, a warning, exit 0. A 429 with `Retry-After:
  120` waits 120 s, not the backoff. B answers 500: B is not recorded, the
  `daily/` files are pushed, exit 3. A bronze file unreadable on the host is
  skipped likewise. Access refused (403) on A ends the push, saying how many
  were left, exit 3. The record names another bucket: nothing is taken as
  pushed, and no host snapshot is deleted.
- **TD-Q, the item fetch's end.** A fetch at :24:49 with an item left starts
  it (its 10 s timeout ends at :24:59); at :24:51 it does not, and the item is
  fetched next run. An item answering 503 three times in a run is left to the
  next run, after pausing the fetch each time.

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
- *changed*: TT3 (E5, load), over TT1's 72 hours, with an ad hoc query running
  at E5's `DP_ADHOC_*`: passes where every hourly run's `transform` and
  `export` together, with the run's own work shared across its hours, finish
  inside 5.4.1's hourly processing bound (5 min, H10), and the peak memory of
  every hourly and daily run stays inside its 1 GB `memory_limit` (H7), and
  fails otherwise. Beside it, reported, not judged: per hour,
  `price_level_hour` and `listing_record` rows and bytes, projected to 4 weeks
  and a year against delphside/dark-portal#5's figures and the capacity plan,
  and every job's `total_seconds` and step seconds (TM), read against the
  hourly bound, the daily deadline and the two run time limits.
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
- *changed*: TT8 (E5): `dp daily` at 00:50: `item_day` written, aged rows and
  export files deleted, bronze and `daily/` pushed to a test bucket and host
  snapshot files deleted, item files kept; again with `DP_BUCKET` empty. Hold
  the lock across 00:50: `dp daily` itself retries every 15 min after each
  attempt ends, none starting at or after 03:00, and its unit, with `Restart=no`, shows
  the last attempt's status; a close attempt made late in the window closes
  nothing and exits 75 (H8, DL).
- TT9 (E5): a wrong client secret exits 2; a Blizzard outage past the retry
  window exits 75 with the hour recorded as a gap.
- TT10 (E6): deploy by delphside/dark-portal#11's rehearsal path from
  production's level, and the next hourly run lands. Reboot across :35, back
  before :25 past the next hour: the timer runs the missed job when the host is
  back and it collects the previous hour (S57).
- TT11 (E5), the units (U1): `systemctl list-timers 'dp-*'` shows both timers
  with the :35 and 00:50 UTC starts and persistence; both services show
  `Restart=no`; `RuntimeMaxSec` is 55 min and 165 min, as 5.4.1's settings
  derive them; a run started by hand while its job is live exits 75, with the
  live run going on; with the lock file missing it exits 2; a run by hand with
  a stopped container holding the job's name exits 2; a run stopped at its
  limit shows `failed` and
  the next timer start repeats what it left, a daily export stopped part-way
  included (D32.10); `DP_ENV_FILE` naming no environment exits 2.

The restore's steps and its drill are in delphside/dark-portal#38 *Restore Dark
Portal after a lost host*. BK is tested here for what reaches the bucket and
stays there (S46, TT8, PD6), and the rebuild from bronze by L4 (S47, TT6).

**[PD]**, from the export the owner pulls and what he reads, since production
reads are his; one per row of delphside/dark-portal#7's post-deployment checks:

- PD1 (R1): the owner compares three commodities' lowest and fill price with the
  in-game auction house within the same hour.
- PD2 (R2): after a week, every hour collected has an `item_hour`, a missed hour
  is a gap, and each completed day has an `item_day`; the 4-week keep is checked
  after 4 weeks.
- PD3 (R7): one commodity's ladder matches the in-game units at each price
  within the hour, and shows hours of depth.
- PD4 (R8v): every hour shows the sold floor and estimate for each item, the
  floor never above the estimate.
- PD5 (gaps; H3, P10): every `meta.gap` row in the first week is explained:
  the owner lists them with the runs' logs, and Claude matches each.
- PD6 (keeps; R2, K2, BK): the owner reads the bucket's lifecycle rules and
  lists host bronze, and gives Claude the result: the rule on `bronze/` is
  1 year, `daily/` has none, and host bronze holds no snapshot file older than
  7 days.

## 9. Test names

All of these are **[AUTO]**.

### Events and lifecycle

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
- `gap_is_written_in_the_later_hours_transaction`
- `latest_hour_not_yet_collected_is_no_gap`
- `listing_first_seen_after_a_gap_has_no_posting_hour_or_queue_at_posting`
- `first_snapshot_writes_live_listings_and_no_events`
- `first_hour_is_held_with_prices_and_depth_and_null_flows_and_span`
- `queue_orders_by_price_then_newest_id_first`
- `fronts_are_judged_per_item`
- `queue_place_counts_units_ahead_and_at_or_below`
- `ended_listing_writes_its_record_and_removes_its_live_rows`
- `listing_record_counts_units_sold_over_its_life`
- `undercut_counts_higher_ids_at_a_lower_price_still_listed`
- `quantity_rise_on_a_live_id_is_intact_with_no_event_and_a_warning`
- `price_change_on_a_live_id_is_kept_with_no_event_and_a_warning`
- `quantity_drop_at_a_changed_price_is_a_sale_at_the_new_price`
- `units_sold_of_a_raised_listing_can_exceed_its_first_quantity`
- `partly_sold_event_is_priced_at_the_listings_current_price`
- `sold_event_carries_the_quantity_last_seen`
- `reappearing_id_above_the_highest_live_id_is_logged_and_left_out`
- `reappearing_id_takes_no_place_in_any_queue`
- `only_an_expired_or_cancelled_event_can_carry_a_tie`

### Collection

- `snapshot_hour_is_the_utc_hour_starting_of_last_modified`
- `collect_in_a_collected_hour_exits_0_without_a_request`
- `current_hour_is_fixed_when_collect_starts`
- `run_inside_the_previous_hours_retry_window_collects_that_hour`
- `run_after_the_previous_hours_retry_window_collects_its_own_hour`
- `collect_polls_without_the_lock_and_takes_it_only_to_rename`
- `stale_snapshot_is_polled_every_2_minutes_until_it_refreshes`
- `snapshot_unrefreshed_by_25_past_exits_75_and_writes_nothing`
- `last_modified_in_the_hour_after_the_current_one_exits_75_as_a_gap`
- `last_modified_two_or_more_hours_ahead_exits_2`
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
- `item_lookup_400_403_408_500_or_unreadable_is_fetched_next_run`
- `item_blip_pauses_the_whole_fetch_and_sends_the_item_to_the_back`
- `item_is_asked_at_most_three_times_in_a_run`
- `item_fetch_starts_no_request_that_could_end_after_25_past`
- `items_run_alone_with_unreadable_bronze_stops_before_its_first_request`
- `status_408_is_unexpected_and_not_a_blip`
- `unreachable_blizzard_is_a_blip`
- `item_404_is_recorded_with_its_status_and_logged_as_a_warning`
- `item_whose_latest_response_is_404_is_not_asked_again_hourly`
- `profile_shows_the_item_id_until_its_response_arrives`
- `item_fetch_is_paced_at_50_a_second`
- `secret_never_appears_in_logs_bronze_or_export`

### Scheduling and the hourly run

- `writing_subcommand_waits_for_the_lock_up_to_10_minutes`
- `writing_subcommand_exits_75_when_the_lock_wait_runs_out`
- `persons_transform_waits_for_the_hourly_runs_lock`
- `hourly_holds_the_lock_from_the_rename_through_export`
- `ad_hoc_query_takes_no_lock_and_uses_its_own_limits`
- `hourly_takes_the_lock_for_items_where_collect_took_none`
- `hourly_skips_later_steps_and_exits_75_where_the_lock_is_held_past_the_wait`
- `hourly_exits_collects_status_where_the_lock_is_held_and_collect_failed`
- `hourly_runs_collect_items_transform_export_in_order`
- `hourly_runs_items_transform_and_export_after_any_collect_result`
- `hourly_exits_with_collects_status_where_it_is_not_0`
- `hourly_exits_3_where_collect_succeeded_and_a_later_step_failed`
- `transform_catches_up_every_bronze_hour_in_order`
- `failed_transform_hour_rolls_back_whole_and_exits_3`
- `next_run_reprocesses_a_failed_hour`
- `reprocessing_a_committed_hour_changes_nothing`
- `gold_hour_takes_prices_from_live_listings_and_flows_from_events`
- `hour_processed_over_5_minutes_is_logged_as_a_warning`
- `hour_processed_in_5_minutes_or_less_logs_no_warning`
- `transform_and_export_of_an_hour_are_judged_together_against_5_minutes`
- `runs_own_work_counts_against_the_bound_shared_across_its_hours`
- `transform_run_alone_counts_its_own_time_against_the_bound`
- `export_run_alone_counts_its_own_time_against_the_bound`
- `invalid_bronze_hour_stops_the_transform_with_exit_70_keeping_earlier_hours`
- `unreadable_bronze_hour_stops_the_transform_with_exit_70`
- `every_job_reports_total_seconds_and_its_step_seconds`
- `daily_reports_attempts_and_its_step_seconds`
- `hourly_with_the_lock_held_past_the_wait_reports_only_collect_seconds_and_the_total`
- `daily_after_its_close_reports_all_six_step_seconds_and_attempts_for_a_step_skipped_or_left`
- `daily_ending_before_its_close_reports_only_the_total_and_attempts`

### Profiles

- `lowest_is_the_cheapest_unit_price_in_the_latest_snapshot`
- `fill_price_averages_the_cheapest_n_units_across_listings`
- `fill_price_for_more_units_than_listed_says_how_many`
- `fill_price_is_held_to_two_decimal_places`
- `fill_price_rounds_half_away_from_zero`
- `fill_price_is_null_where_nothing_is_listed`
- `fill_price_refuses_n_below_one`
- `default_n_is_the_rounded_up_median_over_the_hours_held_in_7_days`
- `default_n_is_at_least_one`
- `default_n_is_1_where_the_window_holds_no_hour_to_count`
- `default_n_window_holds_the_hour_and_the_167_before`
- `medians_and_means_over_hours_count_only_held_hours_with_span_1`
- `totals_over_hours_take_every_held_hour_including_one_after_a_gap`
- `purchase_price_is_kept_as_blizzard_gives_it`
- `purchase_price_zero_is_kept_as_zero`
- `purchase_price_is_null_only_where_the_body_lacks_it`
- `vendor_sells_is_null_for_every_item`
- `profile_shows_the_vendor_sell_price_and_neither_purchase_price_nor_vendor_sells`
- `vendor_sell_price_is_zero_where_the_body_gives_none`
- `name_class_and_subclass_are_null_where_the_body_lacks_them`
- `reference_item_with_only_404s_has_no_row`
- `reference_keeps_the_200_after_a_later_404`
- `reference_rebuild_writes_nothing_where_the_table_is_equal`
- `bad_item_file_fails_the_reference_step_and_not_an_hour`
- `fill_price_refuses_n_that_is_not_whole`
- `fill_price_with_nothing_listed_has_null_units_too`
- `item_with_no_row_in_a_held_hour_counts_as_0_in_the_default_n_median`
- `item_with_no_row_in_a_held_hour_counts_as_0_in_the_ladders_mean`
- `depth_ladder_hours_are_null_for_no_sales_seen`
- `profile_shows_units_listed_and_the_units_the_fill_price_covers`
- `hourly_history_and_daily_summary_carry_the_item_name`
- `held_hour_is_an_hour_where_any_item_has_a_row`
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
- `first_day_closes_on_the_hours_from_the_first_snapshot`
- `daily_closes_every_closable_day_not_yet_closed`
- `profile_shows_every_item_at_the_latest_hour`
- `profile_flows_are_totals_over_the_turnover_window`
- `items_filter_by_name_class_and_subclass`
- `latest_200_item_response_wins_in_reference`

### Retention and export

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
- `daily_retries_itself_after_75_every_15_minutes_from_the_end_of_an_attempt`
- `daily_starts_no_attempt_at_or_after_03_00`
- `daily_starts_no_attempt_after_the_retries_span_from_its_start`
- `daily_ends_with_the_last_attempts_status`
- `daily_started_after_the_retries_end_makes_one_attempt`
- `daily_does_not_retry_after_2_3_or_70`
- `daily_attempt_with_25_minutes_before_its_deadline_closes`
- `daily_attempt_with_less_than_25_minutes_closes_nothing_and_exits_75`
- `daily_attempt_after_its_deadline_closes_nothing`
- `daily_close_over_15_minutes_is_a_warning_and_completes`
- `daily_starts_no_gated_step_after_its_deadline`
- `daily_push_starts_no_attempt_or_wait_that_could_end_after_the_deadline`
- `daily_export_deletions_of_files_and_clearing_run_past_the_deadline`
- `daily_does_the_export_push_deletions_stale_files_then_items_in_that_order`
- `daily_records_every_closed_day_in_meta_day_closed`
- `daily_records_a_day_held_in_item_day_and_never_recomputes_it`
- `daily_closes_a_day_with_no_item_row_once`
- `daily_warns_once_of_a_day_that_expired_unclosed`
- `daily_closes_a_day_whose_midnight_is_past_the_keep_but_whose_hours_remain`
- `daily_report_is_a_warning_when_any_warning_was_raised`
- `daily_warnings_are_logged_when_raised`
- `daily_pushes_each_bronze_file_once_and_the_daily_files_every_run`
- `daily_push_records_a_path_only_after_its_push_succeeded`
- `daily_push_of_another_buckets_record_is_read_as_empty`
- `daily_push_retries_a_blip_with_backoff_up_to_three_attempts`
- `daily_push_honours_the_buckets_retry_after`
- `daily_push_after_retries_is_a_warning_with_exit_0`
- `daily_push_500_is_that_objects_error_and_the_rest_are_pushed`
- `daily_push_skips_a_bronze_file_it_cannot_read`
- `daily_push_ends_where_access_is_refused_and_says_how_many_were_left`
- `daily_push_upload_is_bounded_at_5_minutes`
- `daily_bucket_access_file_is_read_only_where_a_bucket_is_set`
- `bucket_access_url_never_appears_in_logs_bronze_or_the_export`
- `daily_removes_a_stale_tmp_only_after_its_works_end_the_lock_wait_and_the_margin`
- `daily_keeps_a_tmp_a_running_job_may_still_write`
- `daily_removes_a_spill_folder_untouched_for_the_run_time_limit_and_margin`
- `daily_keeps_a_running_jobs_spill_folder`
- `each_duckdb_connection_spills_to_its_own_folder_removed_at_close`
- `daily_expires_lake_snapshots_older_than_7_days`
- `daily_repeats_a_failed_file_clean_up_whether_or_not_a_row_was_deleted`
- `daily_exits_75_when_the_lock_wait_runs_out`
- `daily_exits_2_on_a_full_disk_without_closing_the_day`
- `daily_exits_3_when_a_step_after_the_close_fails_and_the_next_run_repeats_it`
- `daily_out_of_memory_in_opening_the_lake_or_the_close_exits_2`
- `daily_export_out_of_memory_is_an_error_and_exits_3`
- `daily_export_stopped_part_way_is_written_again_by_the_next_run`
- `export_writes_every_committed_hour_it_lacks`
- `export_skips_a_lacking_hour_older_than_the_hourly_keep`
- `failed_export_exits_3_and_the_next_run_repairs_it`
- `export_rewrites_item_day_and_item_only_where_they_differ`
- `export_rewrites_profiles_sql_only_where_its_text_differs`
- `export_writes_nothing_where_nothing_is_new`
- `export_removes_a_stale_tmp_under_the_lock`
- `export_hour_with_no_rows_is_a_file_with_columns_and_no_rows`
- `exported_views_read_the_export_dir_variable_or_the_working_folder`
- `export_files_appear_only_whole`
- `exported_profiles_sql_carries_sql_profiles_unchanged`
- `exported_profiles_sql_gives_the_same_profile_as_the_lake`

### Units and `dp-run`

- `units_have_restart_no_and_the_settings_run_time_limits`
- `timers_start_at_35_and_00_50_utc_and_are_persistent`
- `dp_run_by_hand_while_its_job_is_live_exits_75`
- `dp_run_with_the_lock_file_missing_exits_2_and_does_not_make_it`
- `dp_run_with_a_stopped_container_holding_the_name_exits_2`
- `dp_run_with_an_environment_name_outside_the_pattern_exits_2`
- `dp_run_help_exits_0`
- `dp_run_with_docker_ps_failing_exits_75`
- `dp_run_with_no_subcommand_or_an_unknown_option_exits_64`

### Rebuild and errors

- `rebuild_from_the_first_bronze_hour_equals_the_incremental_run`
- `unexpected_error_exits_70`
- `bad_flag_exits_64`
- `rebuild_with_item_day_restored_records_those_days_and_does_not_recompute`
- `migration_5_records_the_days_item_day_holds_as_closed`
- `transform_out_of_memory_exits_2_when_run_alone`
- `export_out_of_memory_opening_the_lake_exits_2_when_run_alone`
- `export_out_of_memory_reading_the_committed_hours_is_an_error_for_no_hour`
- `export_out_of_memory_writing_an_hour_is_an_error_for_that_hour_and_stops_the_export`
- `hourly_carries_an_out_of_memory_step_as_exit_3`
- `bronze_write_failure_in_collect_is_unexpected_exit_70_out_of_memory_included`
- `items_bronze_write_failure_before_the_first_request_exits_70`
- `items_bronze_write_failure_after_the_first_request_is_a_carried_error_exit_3`
- `items_bronze_read_failure_before_the_first_request_exits_70`

## 10. Gaps

The gaps closed in the documents, each with the rule or condition that
covers it:

- G7, a changed live listing: 5.2.2 *A live listing that changes* (EV-7, D1.4,
  D1.6 to D1.8).
- G30, the out-of-memory exit: 5.2.1 *When it fails*, and for `dp daily` 5.1.1
  *Restarts and recovery* (X3 to X5, D28.6 to D28.11, D29.13, D29.14).
- G31, the equal share of a run's own work: 5.4.1 (H10, D30.6).
- G32, the end of a push: 5.4.2 *The bucket* (K5, D33.4).
- G33, the timings of a step that did not run: 5.3.2 *What the timings are
  for* (TM, D35.4 to D35.6).
- G34, `dp-run`'s status mapping: 5.3.2 *`dp-run`'s exit statuses* (U1, D37.9).
- G36, the profile view's rows: 5.2.3 *Which items* (P1, P11).
- G37, an export that overruns the allowance: 5.4.2 *The daily deadline*, where
  nothing times it and the daily run time limit stops it (DL, D32.10).

The gaps open now; none blocks the test design, and each says why:

| Gap | What would make the missing test fail | What it would take to close it | Why it is acceptable for now |
| --- | --- | --- | --- |
| G19 No clock seam | Every timed test (poll, :25, backoff, token margin, lock wait, the processing bound, 00:50, the retries span, 03:00, the daily deadline, the day close bound and the item fetch's end) needs the clock injected; none is named. | Name it in Development. | A Development matter; part 8 says what it must cover. |
| G28 E3 to E6 are not yet built (delphside/dark-portal#11) | [AUTO], [UT] and [TT] have nowhere to run. | delphside/dark-portal#11's packages land first. | Designed; delphside/dark-portal#7's Development waits on delphside/dark-portal#11. |
| G29 "Lower bound" | Not directly observable. | Accept the structural tests (`listing_posted_and_bought_between_snapshots_shows_in_no_flow`, floor ≤ estimate). | Inherent. |
| G35 `vendor_sells` true and false (until R5) | No code can set the flag until R5's setter exists, so `true` and `false` have no source to test through. | Build R5's setter (stage 3). | Only the column's type and the null for every item are tested now (D23.4). |
