# 71 Storage

This file holds what the design stores and how: the technologies the storage
rests on (SQLite, sqlx and serde), the migration, the database schema and which
modules change. It follows [`71-07-client.md`](71-07-client.md) and is followed
by [`71-09-open-questions.md`](71-09-open-questions.md).

## As-is

Sources: `crates/server-game/src/persistence.rs` and
`crates/server-game/migrations/`.

### Worth keeping

- **One transaction per save.** `save_game` writes the game row, the seats,
  the moves, the messages and the rating step together, so a game and its
  rating never disagree.
- **Rating is settled once.** `save_game` runs `settle_ratings` only on the
  save that first makes a game finished, gated by the previous status and
  `games.stats_settled_at`, so a re-save never re-rates.
- **Columns for what a query needs.** Stats read `game_participants.outcome`,
  `bingo_count` and `score`, and the sweeps read `status`, `ended_at` and
  `last_activity_by_game`, without loading a snapshot.
- **Migrations are embedded and checked.** `sqlx::migrate!("./migrations")`
  runs at startup, each applied file is checksummed, and
  `applied_schema_version` puts the newest on `/health` for the deploy script
  (`migrations/README.md`).
- **WAL mode.** `connect` sets the write-ahead journal, so readers do not
  wait behind a writer.
- **A rating outlives its game.** `delete_game` leaves `rating_history`
  alone.

### To move away from

- **No foreign keys.** No migration declares one, so `delete_game` and
  `delete_player` delete or null every child row by hand, in the right order.
- **An unversioned snapshot.** `snapshot_json` (`PersistedGame`) has no schema
  version. Changes of shape are absorbed by `#[serde(default)]` and
  `deserialize_i64_flexible`, which never retire, and `load_game` panics
  (`expect`) on a blob it cannot read.
- **History stored twice and rewritten.** The moves and messages are inside
  `snapshot_json` and also in `game_moves` and `game_messages`, which
  `save_game` deletes and reinserts in full on every save, as it does the seats.
- **No log of changes.** Nothing records what happened to a game, only its
  latest state.
- **`version` is not a column.** `turn_number` is one, but `version` lives only
  inside the blob, so finding games by it means deserialising each.
- **Ratings keyed by `(subject_kind, subject_id)`.** `rating_history.game_id`
  is not null, so a point of a deleted game would name nothing.
- **Names copied into rows.** `game_participants.display_name` and
  `game_messages.display_name` copy a player's name at the time.

## The model

The design stores a game as one `games` row whose `snapshot_json` carries a
*schema version*, with the columns the sweeps need beside it and every change
appended to `game_events`. The relations between tables are declared as
foreign keys, so the database deletes what belongs to a deleted row. **Existing
games are deleted rather than migrated**, and the schema version makes this
the last time.

- A *schema version* is a small integer in `snapshot_json` naming the shape
  of the blob, which a reader checks before anything else
  ([*So that this is the last deletion*](#so-that-this-is-the-last-deletion)).
- A *variant object* is the reader for one schema version: it reads a whole
  blob of that version and converts it to the current one.
- *Append-only* is the rule for `game_events`: a row is written once and
  removed only with its game.

## SQLite

### The SQLite technology

SQLite is a database that runs inside the application's own process and keeps
everything in one file, rather than a server the application talks to
([sqlite.org](https://www.sqlite.org/about.html)). The server links it in:
sqlx's SQLite driver bundles it through `libsqlite3-sys` 0.30.1 in
`Cargo.lock`. The features this design relies on:

- A *transaction* groups statements so that all take effect or none does. A
  change is durable once the commit returns.
- *Write-ahead logging* (WAL) is a journal mode in which a writer appends to a
  log file and readers carry on reading the last committed state. There is
  still one writer at a time: a second writer waits. The mode is stored in the
  database file.
- A *foreign key* is a column declared to hold the key of a row in another
  table. Its `on delete` action says what happens to the referencing row when
  the referenced one goes: `cascade` deletes it, `set null` empties the
  column. SQLite checks and acts on foreign keys only on a connection where
  `PRAGMA foreign_keys` is on, a per-connection setting that cannot be changed
  inside a transaction.
- `DROP TABLE` on a table that foreign keys point at first deletes its rows as
  if by `DELETE`, so the `on delete` actions fire. This matters to a migration
  that rebuilds tables.
- `ALTER TABLE` cannot add a constraint to an existing column. Adding one
  means building a new table, copying the rows, dropping the old table and
  renaming the new one
  ([SQLite's guidance](https://www.sqlite.org/lang_altertable.html#otheralter)).
- Column types are *affinities*: `integer` and `text` say what a value is
  converted to, not what the column can hold. A timestamp is an `integer` of
  Unix seconds here, so a comparison or a sort is on a number.
- `insert ... on conflict do update` is an upsert: one statement that inserts
  a row or updates the one with the same key.

### How storage uses SQLite

- Every write path is one transaction, as `save_game` is today. The new `save`
  writes the `games` row, the seat rows and, for an `Applied`, the
  `game_events` row together, so a game and its log never disagree.
- WAL stays, with the pool of five connections `connect` opens.
- Foreign keys are declared in the table definitions
  ([Database](#database)), and the connection options turn the pragma on
  explicitly rather than relying on a default.
- The migration that adds them rebuilds the tables that have rows to keep
  (`players`, `player_ratings`, `rating_history`, `sessions`), and a rebuilt
  parent must not be dropped while the pragma is on, or its `on delete`
  actions would delete or null the children, which is what the migration must
  not do ([Migration](#migration)). The migration file therefore opts out of
  sqlx's transaction (first line `-- no-transaction`), turns the pragma off,
  rebuilds, runs `PRAGMA foreign_key_check` to prove nothing dangles and turns
  it on again.
- `game_events` has the primary key (`game_id`, `version`), so an event
  written twice is refused by the database rather than by the caller.

## sqlx

### The sqlx technology

sqlx is the Rust library the server uses to talk to the database
([docs.rs](https://docs.rs/sqlx/0.8.6/sqlx/)). `Cargo.lock` pins 0.8.6;
delphside/tile-lite-elite#576 plans 0.9, and this file describes 0.8.6.

- A *pool* (`Pool<Sqlite>`) holds a set of open connections and lends one to
  each query or transaction. `max_connections` caps it, and a request that
  finds none free waits.
- `sqlx::query(sql).bind(value)` runs a statement with parameters (`?1`), so a
  value is never spliced into the SQL text. The queries are checked when they
  run, not when the server is built: sqlx also has macros that check a query
  against a live database at build time, which the server does not use.
- `pool.begin()` starts a transaction, which is rolled back if dropped before
  `commit`.
- A *migrator* applies numbered `.sql` files in order, records each in the
  `_sqlx_migrations` table with a checksum, and refuses to start if an applied
  file has changed. `sqlx::migrate!` embeds the files at build time. Each file
  runs in a transaction unless its first line is `-- no-transaction`.
- `SqliteConnectOptions` sets what each connection is opened with: the journal
  mode, `foreign_keys`, and the busy timeout, which is how long a writer waits
  for the lock before failing.

### How storage uses sqlx

`persistence.rs` stays the one module that touches the database, with runtime
queries and `migrate!` as today. The migrations directory gains the one
migration of this design, and its `README.md` rules (never edit an applied
file, add a file to change the schema) apply to every later one. The
`-- no-transaction` migration is the exception the rules do not mention, and
the README gains a line for it.

## serde

serde is explained in
[`71-05-wire.md`](71-05-wire.md#the-serde-technology), the first file to rely
on it.

### How storage uses serde

`snapshot_json` is written with `serde_json::to_string` and read with
`from_str`. The schema version is the field a reader looks at first; the
reader for each version is a variant object
([Migration](#so-that-this-is-the-last-deletion)). The wire's tagged enums are
in [`71-05-wire.md`](71-05-wire.md).

## Migration

The schema and the shape of `snapshot_json` both change. **Existing games are
deleted rather than migrated.** Users, ratings and rating history are kept:
they belong to the player rather than the game, and they are what makes
deleting games acceptable at all.

Before the migration runs, check that nobody else is mid-game:

```bash
./scripts/admin.sh games list --status active
```

It shows every game still in play with its seats and their players. Waiting
games matter less — nobody is mid-move — but they are visible the same way.

This is a **breaking wire change**, so the api major version moves: an old
client cannot read the new shapes, and should be told to update rather than
left to fail.

### So that this is the last deletion

`snapshot_json` gains a **schema version**: a small integer naming the shape
of the blob, written by whatever wrote it and read before anything tries to
interpret it.

It is deliberately not the `version` already in there. That one counts state
changes within a game and answers "is this snapshot newer than the one I am
showing". This one identifies the *shape*, changes only when the shape does, and
answers "can this reader understand this blob at all".

Without it, a reader meeting an old blob has no way to know that is what
happened — it deserializes into something plausible and wrong, or fails with
an error about a missing field that says nothing about the real cause. With
it, a future change can branch on the number and convert, so the games survive
the change instead of being thrown away.

Which is the point: this deletion is licensed because nobody else is mid-game
today, and that will not be true forever. Adding the field costs a line now
and is impossible to add retrospectively — an unversioned blob stays
unversioned, and version 1 can only be declared while every row is
being rewritten anyway.

The habit exists in a weaker form already: 4.4 records `#[serde(default)]` on
fields added since, which recovers a single missing field but cannot express
a change of shape, and gives a reader no way to tell an old blob from a new
one with a field omitted.

**A later shape is read by a variant object, one per schema version** (owner,
2026-09-02). Each reads a whole version and converts it to the current one, so a
version retires as a unit: once no blob of it remains, which retention makes
foreseeable, its reader goes. A per-field shim such as
`deserialize_i64_flexible` never retires, because nothing records when the
last old blob has gone.

## Database

| table | change |
| --- | --- |
| `games` | add `version`, `turn` and `last_scoring_turn`, all `integer not null default 0`, `last_activity_at integer not null`, which RET-3's countdown reads, and `rated integer not null default 1`, which a suggestion clears (RATE-4) (see *Open questions* in `71-09-open-questions.md`). `snapshot_json` changes shape and gains `schema_version` (#302, [*So that this is the last deletion*](#so-that-this-is-the-last-deletion)) |
| `game_participants` | drop `display_name`. Add `state text not null`, `invitation_id text`, `hidden_by_player integer not null default 0`. Keep `outcome`, `bingo_count`, `score` — stats read them without loading a snapshot |
| `game_invitations` | gains `addressee_id text`: the player who may accept, set at send when the address is one an account has verified, or later when a link is claimed or the address is verified; null while the link is still the credential, so a set addressee also means the link is spent (see *Who may accept* in `71-04-seats.md`).[^d72] An index on the invited address over open rows with no addressee serves the pass on verification. It stays the record of who was asked and what they said, which DEL-2 reads |
| `player_ratings`, `rating_history` | the key becomes `(player_id, edition)` and `subject_kind` goes, in one migration with the rest of Core.[^d58] An edition is the game's `variant` (`games.variant`, 4.2), so a game is rated in the edition it was played in, bot against bot included. The rating step sums an account's per-seat changes into one update, and a seat's change against another of its own seats cancels, so a bot that holds several seats in one game needs no special case and a game it plays only against itself nets zero (`settle_ratings`, `stats.rs`). A bot's rows move to the id of its account, and every existing row becomes English (International)'s; other editions start at 1500. `rating_history.game_id` becomes nullable, which the set-null rule below needs |
| `game_events` | new: `game_id`, `version`, `event` (the serialised `GameEventDto`), `created_at`; primary key (`game_id`, `version`). Appended once per `Applied`, never updated or deleted except with its game (RET-1).[^d61] |
| `players` | gains `stats_private integer not null default 0`: whether the player's stats and rating history are hidden from others (RATE-5) |
| `push_subscriptions` | new, for Web Push (WP C): `id`, `player_id`, `endpoint text not null unique`, `p256dh text not null`, `auth text not null`, `created_at`. One row per device a player has allowed; a send answered 404 or 410 deletes it |
| `notification_preferences` | new: `player_id`, `event_kind text not null`, `enabled integer not null`; primary key (`player_id`, `event_kind`). A missing row means the event kind's default, so a new kind needs no migration |
| `game_moves`, `game_messages` | drop `display_name` from messages; descriptions become structured. `game_moves` is no longer rewritten on every save: it is read from `game_events`, or dropped where nothing needs it as a table |

**Foreign keys arrive with this migration (#253).** Every table is rewritten
anyway, so the constraints 4.2 says are missing are declared now, matching the
deletes `persistence.rs` does by hand today, and `PRAGMA foreign_keys = ON` is
set on every connection:

| reference | on delete |
| --- | --- |
| `game_moves`, `game_messages`, `game_participants`, `game_invitations` → `games` | cascade |
| `sessions`, `password_reset_tokens`, `game_invitations`, `player_ratings`, `rating_history`, `push_subscriptions`, `notification_preferences` → `players` | cascade |
| `game_participants.player_id`, and any other reference from game history to a player → `players` | set null — the seat is unclaimed, not deleted |
| `rating_history.game_id` → `games` | set null — the point outlives its game (RET-2, DEL-10) |

The last row is #66's fix: `RatingPointDto.game_id` becomes `Option<String>`, so
a client is told plainly that the game has gone rather than handed an id that
names nothing.

**`schema_version` is a field of `snapshot_json`** (#302), an integer whose
first value is 1, read before anything else in the blob. A reader matches on it
and has one deserialiser per version it still accepts; a version it does not
know is an error naming the version, not a missing-field error. Why it is
separate from `version` is in
[*So that this is the last deletion*](#so-that-this-is-the-last-deletion).

**`version` and `turn` become columns** rather than living only inside
`snapshot_json`, because a sweep needs to find games by state without
deserialising every snapshot, and because a column can be indexed.

**Migration is a deletion.** This design settles it: existing games are deleted,
users and ratings kept. So the migration is a schema rewrite plus
`delete from games`, and the risk is entirely in what it must *not* delete —
`players`, `player_ratings`, `rating_history`, `sessions`. The rating tables are
rekeyed rather than kept as they are, so the migration checks that every row
survives the move to `(player_id, edition)`.

## Modules

| module | what happens to it |
| --- | --- |
| `game_state.rs` | `ParticipantState` → `Seat`; gains `apply` and `view_for`; loses every other mutator. Its private fields are what enforce the single writer |
| `app/games.rs` (1,030 lines) | the action handlers become thin: parse, build a `GameMessage`, call `apply`, publish. `run_engine_turns` and `MAX_ENGINE_TURNS_PER_TRIGGER` go |
| `app/roster.rs` (391) | seat add/remove/swap become `GameMessage`s |
| `app/invitations.rs` (442) | send/accept/decline become `GameMessage`s; the table write stays, the seat write moves into `apply` |
| `app/events.rs` (105) | gains `publish(Applied)` — persist, publish, one place — and `updates_for`, the one redacted subscription, that a socket and the in-process glue both use; the channels and their rules are in [How the Event stream uses watch](71-06-engine.md#how-the-event-stream-uses-watch) |
| `app/sweeps_game.rs` (301), `app/scheduler_jobs.rs` (297) | timeouts and reminders go through `apply` rather than writing rows, which is what makes them visible to clients. A scheduler job is a caller like any other |
| `app/sweeps_capacity.rs` (81) | expiring a finished or aborted game deletes it rather than changing it, so it does not call `apply`; it goes through the Event stream ([How the Event stream uses watch](71-06-engine.md#how-the-event-stream-uses-watch)) |
| `app/admin.rs` (430) | force-resign and force-end become `GameMessage`s; `admin_delete_game` goes through the Event stream ([How the Event stream uses watch](71-06-engine.md#how-the-event-stream-uses-watch)) |
| `stats.rs`, `app/ratings.rs` | unchanged in substance; read `Applied.finished` instead of inspecting status transitions |
| `crates/ui/src/app.rs` (5,522) | section 7 |
| `crates/engine-core` | **unchanged.** The trait already takes a request and returns an action; what changes is who calls it |

[^d72]: Decision #479 (D72): how an emailed invitation behaves once an address
    identifies one account. It supersedes D59 (#445).

[^d58]: Decision #444 (D58): editions and bots as accounts change the rating key
    once, in Core.

[^d61]: Decision #461 (D61): Core lays down the append-only log and writes it.
