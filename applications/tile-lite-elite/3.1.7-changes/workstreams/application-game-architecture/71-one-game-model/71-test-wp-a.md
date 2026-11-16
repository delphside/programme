# 71 Tests: WP A, #268 Core Game Lifecycle

Fitted to [`71-test-approach.md`](71-test-approach.md), which holds the layers
and what each can answer; this file says what WP A uses of them. The scope is
in [`71-02-overview.md`](71-02-overview.md), *Work packages*.

## What it proves

The server half of #71: every change goes through one handler and moves the
version, a refused message changes nothing, the seat lifecycle holds, the wire
is an identity over what a viewer may see, and an engine is a client.

## Which layers it uses

- **Pure function tests** for `apply`, one arm at a time, and the round-trip
  property `game_from_dto(game_to_dto(v)) == v` over generated `GameView`s
  (in `game-wire`), and `view_for` against a viewer holding two seats.
- **Scripted test clients**, two or more, on `game-wire`: one acts, the others
  must see it. This is the layer WP A is built against before WP B exists.
- **An engine run both ways** — through the
  [in-process glue](71-06-engine.md#the-model) and through the external
  transport — on the same position, producing the same move.

A run against `localhost:3000` covers the external transport only: it
exercises HTTP, WebSocket, JSON and the rate limiter. The glue is covered by
the acceptance boxes about the in-process bot and about the same engine
playing the same move both ways.

## The journeys and rules it covers

[U1.2 Change my details](71-journeys-u1-u3.md#u12-change-my-details) as far as a rename reaches games, [U2.1 Create and start a game](71-journeys-u1-u3.md#u21-create-and-start-a-game), [U2.2 Arrange the seats](71-journeys-u1-u3.md#u22-arrange-the-seats), [U3.1 Accept or decline an invitation](71-journeys-u1-u3.md#u31-accept-or-decline-an-invitation), [U3.2 Take an open seat](71-journeys-u1-u3.md#u32-take-an-open-seat), [U3.3 Withdraw from my seat](71-journeys-u1-u3.md#u33-withdraw-from-my-seat), [U4.1 Take a turn](71-journeys-u4-u6.md#u41-take-a-turn), [U4.4 Leave a game in play](71-journeys-u4-u6.md#u44-leave-a-game-in-play) and
[U4.5 Abort a game](71-journeys-u4-u6.md#u45-abort-a-game), and the server's side of [U4.3](71-journeys-u4-u6.md#u43-chat-in-a-game), [U4.6](71-journeys-u4-u6.md#u46-remind-the-player-on-turn), [U5.2](71-journeys-u4-u6.md#u52-remove-a-game-from-my-list) and [U6.1](71-journeys-u4-u6.md#u61-force-end-a-game) to [U6.4](71-journeys-u4-u6.md#u64-delete-a-game), from [`71-functional.md`](71-functional.md): GAME-1 to GAME-4,
RATE-1 to RATE-3, TIME-3, DEL-2, DEL-3, and the tests the code review found
missing (`71-test-approach.md`).

## Its acceptance

- [ ] **Claude** — every `GameCommand` arm, `Player` and `System`, has a test that it moves `version` (except `Hide` and `ReminderSent`, which save without moving it), and a refused one that it changes nothing
- [ ] **Claude** — the round-trip property passes over generated `GameView`s, and `view_for` gives a viewer holding two seats both racks
- [ ] **Claude** — the in-process bot is handed only the games its account holds a seat in, each redacted for its account, and is never answered 429
- [ ] **Claude** — a bot seated in a new game while running plays it: the seat list gains a seat in the game, `updates_for` joins that game's channel before it reads the game, and the glue makes a bot object for the seat
- [ ] **Claude** — a game already on an in-process bot's turn at the server's start-up is played
- [ ] **Claude** — a bot holding two seats in one game plays each seat, and when one seat is removed `updates_for` stays in the game's channel for the other
- [ ] **Claude** — an event for one game reaches no socket of another game
- [ ] **Claude** — a deleted game (the sweep or `admin_delete_game`) ends the bot objects of its seats and leaves every seat list that held it
- [ ] **Claude** — a slow receiver reads the newest state and skips the stale ones, and is given neither an error nor a disconnect
- [ ] **Claude** — a game in which one listed bot holds every seat (a bot showdown) settles with a net rating change of zero for that bot
- [ ] **Claude** — two seats of one listed bot share one account and one rating per edition
- [ ] **Claude** — a scripted second client sees every change the first makes, invitations included, within one update
- [ ] **Claude** — the same engine plays the same move through the glue and through the external transport
- [ ] **Claude** — an engine's `start` refuses a level of 0 or above its maximum, a bot list giving one stops the server at start-up, an engine starts at its default when the bot list gives none, and one with a maximum of 1 plays at level 1
- [ ] **Claude** — G1: a bot seat the start renumbers keeps its bot object and plays on its new number, and a swap writes no seat list
- [ ] **Claude** — G2: a bot object ends on the first view that shows its game finished or aborted, and one made at start-up for a game already over ends on that game's first view
- [ ] **Claude** — G3: an account subscribed over every seated game has an `Invited` seat in its list from the moment it is the seat's addressee, keeps a declined or withdrawn seat until the start, and loses a spent seat at the start; deleting a waiting game takes it from its addressee's list too
- [ ] **Claude** — G4: a bot list naming an account that does not exist, an engine not compiled in, or a level outside that engine's range, stops the server at start-up naming the setting, and deleting a listed bot's account is refused
- [ ] **Claude** — G5: hiding a game and sending a reminder each log a row with the next `seq` and the version unchanged
- [ ] **Claude** — G6: a bot's move whose save fails is submitted once more after `Retry-After` and applied if that save succeeds; a second failure leaves the seat on turn
- [ ] **Claude** — the start drops spent seats, renumbers the rest and checks GAME-3 again after the drop, refusing a game left with fewer than two seats
- [ ] **Claude** — every score change is a move record: a finishing turn's `GameEnd` carries one rack adjustment per seat it changes, and each seat's score equals the sum of its records' `score_delta`
- [ ] **Claude** — ratings settle once, on `Finish::Played`; an abort, and a force-end after the start, change no rating
- [ ] **Claude** — an abort cancels the game's pending invitations
- [ ] **Claude** — a person's move whose save fails answers 503 with `Retry-After`, reloads the game and publishes nothing; a reader that finds `unsaved` reloads first; a failed reload answers 503 to every message until one succeeds
- [ ] **Claude** — every applied change, and a game's creation, appends one `game_events` row with its version, and a duplicate (`game_id`, `seq`) is refused
- [ ] **Claude** — a pre-start event in the log, a chat and a hide included, names the seat by its id, and still names the right seat after a swap and after the start
- [ ] **Claude** — deleting a game deletes its seats, invitations and log rows, sets `rating_history.game_id` to null, and a rating point with no game reads as no game (#66)
- [ ] **Claude** — a message to a game after its deletion is answered as for a game that does not exist and saves nothing: the deleter takes the game's lock and sets `deleted`
- [ ] **Claude** — the Game service refuses, before `apply`, every message from a caller its table does not allow: a force-resign, abort, seat change, start or keep from anyone but the creator (GAME-6, RET-3), a withdrawal by anyone but the creator or the seat's player (GAME-9), an accept or decline by anyone *Who may accept* excludes, and chat by anyone neither seated nor the creator (GAME-12); the addressee's accept and decline and the creator's withdrawal succeed; and the log row of an applied message records its sender in `actor_id`
- [ ] **Claude** — DEL-2: deleting an account that any game names is refused
- [ ] **Claude** — the migration keeps every rating row under its new (`player_id`, `edition`) key, writes `schema_version` 1, and fails on a foreign-key violation (#253, #302)
- [ ] **Claude** — a rename reaches every game the player is in (#80), and moves each one's version
- [ ] **Claude** — a keep sets `last_activity_at`; a chat, a hide and a rename do not (RET-3)
- [ ] **Claude** — `engine_limit` bounds parallel searches, and a search's time starts once its permit is held (#429, D62)
- [ ] **Claude** — each `ApplyError` maps to its `ErrorDto` code (D65)
- [ ] **Claude** — a reconnect yields the game's current view, with no `because` (#142)
- [ ] **Claude** — G7: `POST /games/{game_id}/suggest` is gone, answering 404, and nothing in the server calls the code it ran
