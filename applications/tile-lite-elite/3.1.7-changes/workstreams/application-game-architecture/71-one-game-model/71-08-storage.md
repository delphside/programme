# 71 Storage

This file holds migration, the database schema and which modules change. It
follows [`71-07-client.md`](71-07-client.md) and is followed by
[`71-09-open-questions.md`](71-09-open-questions.md).

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
showing". This one identifies the *shape*, changes only when we change it, and
answers "can this reader understand this blob at all".

Without it, a reader meeting an old blob has no way to know that is what
happened — it deserializes into something plausible and wrong, or fails with
an error about a missing field that says nothing about the real cause. With
it, a future change can branch on the number and convert, so the games survive
the change instead of being thrown away.

Which is the point: this deletion is licensed because nobody else is mid-game
today, and that will not be true forever. Adding the field costs a line now
and is impossible to add retrospectively — an unversioned blob stays
unversioned, and version 1 can only be declared while we are already
rewriting every row.

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
| `games` | add `version`, `turn` and `last_scoring_turn`, all `integer not null default 0`, `last_activity_at integer not null`, which RET-3's countdown reads, and `rated integer not null default 1`, which a suggestion clears (RATE-4) (see *Open questions* in `71-09-open-questions.md`). `snapshot_json` changes shape and gains `schema_version` (#302, below) |
| `game_participants` | drop `display_name`. Add `state text not null`, `invitation_id text`, `hidden_by_player integer not null default 0`. Keep `outcome`, `bingo_count`, `score` — stats read them without loading a snapshot |
| `game_invitations` | gains `addressee_id text`: the player who may accept, set at send when the address is one an account has verified, or later when a link is claimed or the address is verified; null while the link is still the credential, so a set addressee also means the link is spent (see *Who may accept* in `71-04-seats.md`).[^d72] An index on the invited address over open rows with no addressee serves the pass on verification. It stays the record of who was asked and what they said, which DEL-2 reads |
| `player_ratings`, `rating_history` | the key becomes `(player_id, edition)` and `subject_kind` goes, in one migration with the rest of Core.[^d58] An edition is the game's `variant` (`games.variant`, 4.2), so a game is rated in the edition it was played in, bot against bot included. The rating step sums an account's per-seat changes into one update, and a seat's change against another of its own seats cancels, so a bot that holds several seats in one game needs no special case and a game it plays only against itself nets zero (`settle_ratings`, `stats.rs`). A bot's rows move to the id of its account, and every existing row becomes English (International)'s; other editions start at 1500 |
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
separate from `version` is in the design's *So that this is the last deletion*.

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
