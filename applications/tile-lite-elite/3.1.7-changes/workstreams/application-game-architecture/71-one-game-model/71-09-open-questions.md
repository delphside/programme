# 71 Open questions

This file holds the questions the design leaves open or records as settled. It
follows [`71-08-storage.md`](71-08-storage.md) and is followed by
[`71-10-documents-changed.md`](71-10-documents-changed.md).

## Open questions

**Core writes the log; undo reads it later.**[^d61] Every `Applied` appends one
row to `game_events (game_id, version, event, created_at)`, written by `publish`
and never rewritten, and `game_moves` becomes what is read from it. The row
holds the same serialised event that goes over the wire, so there is one
serialisation rather than a second format to keep in step. Current state stays
authoritative and behaviour never reads the log; undo (WP E) is its first
reader. Because nothing is rewritten, `created_at` is when a change happened.
That alone does not give RET-3 a true last activity, because a chat and a hide
are logged too, and #460 found they should not count. So `games` carries
`last_activity_at`, set by the one handler for the events that count and left
alone by the rest; which events count is RET-3's. A keep (`KeepRequested`) sets
it, as RET-3's "keep" requires.

**The freshness counter is `version`**, on `GameSession`, moved by any change —
a resignation, an abort and a timeout each take one, and none is a move. Records
carry the version they happened at. `move_number` stays what it is, the sequence
number of a move record, and `turn` is game state alongside them (see
[*What the composition is keyed on*](71-07-client.md#what-the-composition-is-keyed-on)).

**State fields and message fields are different things**, which resolves the
ratings. `rating_before` and `rating_after` describe what *this game did* to a
seat's rating, and are populated only once it is settled: they are facts about
an event, so they belong on the message, not in the state and not in the
identity. `current_rating` is neither — it is the player's standing now, read
from another table and joined in for display. That is a projection, and a game
object should not carry it at all.

**And a display name is the same kind of thing**, which makes it a rule rather
than two observations:

> **User details — name, email, rating — are always a lookup, never copied into
> game data.** A game holds a `player_id` and nothing else about the person.

`ParticipantState` holds a `String` today, copied in when the seat is claimed
and written into `snapshot_json`. Renaming yourself changes one row and leaves
a stale copy in every game you are in, which a freshly started client shows too
— the copy is what the server sends. That is how the rule was found: in
production, by somebody renaming herself and nobody else seeing it.

Three things go, and the third is the work:

- `ParticipantState.display_name`
- `ChatMessageRecord.display_name`, whose `player_id` is already there
- **prose descriptions.** `format!("{display_name} was retired for exceeding the
  move time limit")` cannot be re-resolved by anybody, because by then it is a
  sentence. Descriptions become structured — a kind, and the ids it refers to —
  and are rendered where they are displayed.

That last one earns its cost twice. It is the same principle as the rest of
this design (a client should be handed facts, not the server's rendering of
them), and it is the only way a description is ever readable in a language
other than the one the server was written in — which matters for a service
already shipping Spanish dictionaries.

**A change to user details is a `GameMessage` like any other**, sent once per
game that player is in. It bumps the version, records the event and publishes,
through the same handler as a move.

**It carries nothing to apply**, and that is the point rather than a wrinkle.
The game never stored the name, so there is nothing in the game to update — the
message exists only to say *the rendering of this game is out of date*. The
fresh name arrives because building the DTO resolves it, which is what the
lookup rule bought.

So the fan-out lives in `update_player_details`: find the player's games, send
one message to each. Nothing new in the handler, no "reload" signal, and
nothing for a client to learn — it receives the same update it receives when
somebody passes.

It also leaves the log honest. A version bump with no event behind it would be
unexplained the next time anybody reads the history; `UpdateUserDetails` says
why the number moved without saying what changed, which is all anybody needs.
And it does not disturb undo, which walks back the last *move* rather than the
last event.

An earlier draft of this design said the opposite — a bare reload, and the
version must *not* move because the game had not changed. That contradicts the
first thing this design argues. The complaint at the top is precisely that *the
version does not move for everything a client can see*, and a name is
something a client can see. Once names resolve at the point the DTO is built,
a rename genuinely changes the state a client should be showing, and saying so
is what the version is for.

It is also required rather than tidy. `should_apply_update` takes an incoming
state only when its version is higher, so an update carrying the same version
is an update every client correctly ignores. Sending the data without moving
the version would be sending nothing.

**And it scales the right way, which is the reverse of what I assumed.** A
bare reload is work proportional to *everyone connected*, arriving as a
request storm from clients that mostly did not care. Bumping the affected
games is work proportional to *the games that one player is in* — a handful,
touched at the rate people rename themselves, which is rarely. The targeted
version is the cheap one at any population worth worrying about, and it is
also the one that needs no round trip: the client is handed the answer rather
than told to go and ask.

**The harness runs the bots — there is no proxy.** An earlier draft of this
design put a "bot proxy" between the server and the bots. That was a mistake in
its own terms: if the DTOs are invisible and the environment is the same
wherever an engine runs, then nothing mediates, and naming a layer implies one
this design specifically removes. The harness is a process that runs one or
more bot clients, each a client in its own right.

Running several in one process is an operational convenience — one thing to
start, one place for logs — and not a tier in the architecture. A bot run
singly from somebody's laptop is the same bot.

It answers the reloaded-game question, though: a game whose bot is on turn is
picked up rather than left for whoever happens to touch the game next, which is
what covers it today by accident. For the in-process bot the first yields of
`updates_for` do it, and the bot plays a game already on its turn at start-up
([How the Event stream uses watch](71-06-engine.md#how-the-event-stream-uses-watch)).

An external harness (#10's) learns of a turn the way any client does — from the
message carrying the previous move, or the game starting, on a socket it already
holds for that game. A game left waiting while the harness was down is picked up
by the first yield of its socket for that game. A socket that subscribes to
every seated game also learns of a new seat from the account's seat list
([How the Event stream uses watch](71-06-engine.md#how-the-event-stream-uses-watch));
the shape of the socket is #10's.

**A bot plays as a bot account, wherever the engine runs.** The harness
authenticates as the bot, not as the person running it — so a bot's moves
move a bot's rating, and nothing has to declare after the fact which moves
were whose. A server-run bot's seat carries the same kind of account id; the
in-process glue passes it to the Game service, which checks it as it checks
any caller. The server's settings list the bots it runs
([The bots the server runs](71-06b-engine-bots.md#the-bots-the-server-runs)).

That keeps where the engine runs out of the schema entirely, which is the whole
purpose of [the goal](71-02-overview.md#the-goal). A bot playing from a client
and a bot playing in the server are the same game.

**An external client authenticates as a person before it can assume a bot.**
Everything but `/health`, registering and logging in requires a session, and a
bot session is taken on top of a human one. The in-process bot holds no session:
its link is built with the identity the settings list
([The bots the server runs](71-06b-engine-bots.md#the-bots-the-server-runs)).
For an external bot, rating follows the bot and accountability follows the
person, so one behaving badly has an owner to disable.

It is worth being plain that this is revocation and not prevention:
registration is open, so anybody can create a throwaway account and a bot
beneath it. What it buys is a name against every bot session and something to
switch off — which is the point, because that is how bad behaviour is dealt
with. Shutting out an account is its own piece of work and this feeds it: an
external bot has an owner, and the owner is who you stop.

Rate limiting is a separate concern and answers a different question. It
protects the service from load, not from anybody in particular. It exists
(`app/throttle.rs`, 4.1), and a harness meets it like any client: its retry
policy against 429 and `Retry-After` is #10's. It counts only callers outside
the server, and the [in-process bot](71-06-engine.md#the-model)
joins below it.

**Anybody may register a bot** and run it through the harness or their own
client. An external bot's account is an ordinary account with an owner and an
engine, so "my own bot with its own rating" needs no new concept — and the
owner is who you revoke.

**A bot's session follows ACC-1 like anybody's.** A session lasts ten days at
most and ends after forty-eight hours unused, so a long-running harness logs in
again as routine: it answers a 401 by logging in and retrying once, and holds
the credentials to do so.[^d66]

**The harness is #10's, and follows Core** [^d63]. #268 builds `game-wire` and
the test client, which make any client possible; #10 then attaches
`engine-core`, signs in as a bot account and submits moves.

## Open questions about the shapes

**Does `apply` persist, or does its caller?** Written as
[*The one handler*](71-03-version.md#the-one-handler) has it: `apply` mutates in
memory and returns `Applied`; `events::publish` persists and publishes. That
keeps `GameSession` free of the database, and makes `apply` a pure function of
state and message — which is what makes it testable without a pool. The cost is
that a caller can forget to publish. Enforceable by making `Applied`
`#[must_use]`, which is weaker than the type-level guarantee the server side
otherwise gets.

**Can a handler save a game that has been deleted?** A handler holds a clone of
the game's `Arc`
([How the version uses Tokio](71-03-version.md#how-the-version-uses-tokio)),
so it can save after a sweep or an admin delete has removed the game from the
map, which inserts the row again. The live case is `Hide` on a finished game.
Options: (a) the session carries a deleted flag that every save checks under
the game's lock; (b) the deleter takes the game's lock, so a save in progress
finishes first and a later one finds the flag. It may be #408's, which designs
the map's loading and eviction.

**Does a staged word survive onto a game that is over?** `live_composition`
([*The composition is keyed by game and seat*](71-07-client.md#the-composition-is-keyed-by-game-and-seat))
has no condition that fails when the game is `Aborted` or `Finished`, so a
composition whose cells are free and whose tiles are still in the rack stays
live. The two `test.fixme` cases in `e2e/tests/ui-state.spec.ts` fail for this.
Options: (a) a status condition in `live_composition`; (b) a clear on a status
change, which brings back the push model the design retires. Open, for #269.

**What is the hint?** Answered (owner, 2026-11-11): nothing uses `suggest_move`
today. No client calls `POST /games/{game_id}/suggest`. A hint may be offered
later, using it makes the game unrated, and it may come from a different engine
from the one playing. It is a server feature, so that the server knows to make
the game unrated; that is
[delphside/tile-lite-elite#585](https://github.com/delphside/tile-lite-elite/issues/585),
outside #71. Until then #71 leaves `suggest_move` as it is, and a hint, once
built, takes an `engine_limit` permit like any other search in the server.

**What paces the engine's moves?** `ENGINE_TURN_BROADCAST_DELAY` (`games.rs`)
sleeps 120 ms between engine turns so that a person watching an engine game
sees each move; without it an all-engine game finishes before a socket has
opened. A bot that is a client replies as fast as its search returns, and
nothing in [the model](71-06-engine.md#the-model) paces it. Either the bot paces
itself, or the client shows each move for a minimum time, or neither. Open, for
the owner.

**How does the server act as the bot accounts it runs in-process, and do they
need an owner?** Settled by owner, 2026-10-20: see
[The bots the server runs](71-06b-engine-bots.md#the-bots-the-server-runs).

**How does an external harness learn of a game it is newly seated in?** Settled
by owner, 2026-10-20: see
[How the Event stream uses watch](71-06-engine.md#how-the-event-stream-uses-watch).

**Third-party bots in-process?** Settled by owner, 2026-10-20: no; see
[The bots the server runs](71-06b-engine-bots.md#the-bots-the-server-runs).

**Does `turn` need to be persisted separately from `moves.len()`?** Settled by
undo, 2026-08-29: yes. Under undo `turn` walks backwards while `moves` does not
necessarily — an undone move stays in the log, since the log is the record of
what happened and undo is itself an event. So they diverge the first time undo
is used, and `moves.len()` was only ever a coincidence.

[^d61]: Decision #461 (D61): Core lays down the append-only log and writes it.

[^d66]: Decision #466 (D66): bot sessions are not exempt from ACC-1.

[^d63]: Decision #463 (D63): #10 stays its own project and waits on #268 only.
