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
[U4.5 Abort a game](71-journeys-u4-u6.md#u45-abort-a-game), and the server's side of [U4.3](71-journeys-u4-u6.md#u43-chat-in-a-game), [U4.6](71-journeys-u4-u6.md#u46-remind-the-player-on-turn), [U5.2](71-journeys-u4-u6.md#u52-remove-a-game-from-my-list) and [U6.1](71-journeys-u4-u6.md#u61-force-end-a-game) to [U6.4](71-journeys-u4-u6.md#u64-delete-a-game), from [`71-functional.md`](71-functional.md): GAME-1 to GAME-12, RATE-1 to
RATE-3, TIME-3, RET-3, DEL-2, DEL-3, DEL-5, INV-2, INV-3, INV-5 to INV-8,
ADM-2 ([U6.4](71-journeys-u4-u6.md#u64-delete-a-game)), and the tests the
code review found missing (`71-test-approach.md`). INV-1 waits on #439's
verified addresses, and INV-4 is #439's.

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
- [ ] **Claude** — a pre-start event in the log, a chat included, names the seat by its id, and still names the right seat after a swap and after the start
- [ ] **Claude** — deleting a game deletes its seats, invitations and log rows, sets `rating_history.game_id` to null, and a rating point with no game reads as no game (#66)
- [ ] **Claude** — a message to a game after its deletion is answered as for a game that does not exist and saves nothing: the deleter takes the game's lock and sets `deleted`
- [ ] **Claude** — the Game service refuses, before `apply`, every message from a caller its table does not allow: a force-resign, abort, seat change, start or keep from anyone but the creator (GAME-6, RET-3), a withdrawal by anyone but the creator or the seat's player (GAME-9), an accept or decline by anyone *Who may accept* excludes, chat by anyone neither seated nor the creator (GAME-12), a decline of an open seat by a stranger, an accept or decline of an `Invited` seat with no addressee, a hide by a player still claimed or playing in a game not over, and a seatless creator's hide before the game is over; the addressee's accept and decline, a stranger taking an open seat, the creator's withdrawal, a hide by a player who has withdrawn or resigned from a game still running, and a seatless creator's hide of a finished game succeed; and the log row of an applied message records its sender in `actor_id`
- [ ] **Claude** — DEL-2, DEL-3 and DEL-5: deleting an account is refused where it created a game, holds a seat or was invited, with the game Waiting, Active, Finished and Aborted, with its seat withdrawn, resigned or timed out, with an invitation it declined (also after the start has dropped that seat), and with the game hidden from its list; the deletion succeeds once those games are deleted
- [ ] **Claude** — the migration keeps every rating row under its new (`player_id`, `edition`) key, writes `schema_version` 1, and fails on a foreign-key violation (#253, #302)
- [ ] **Claude** — a rename reaches every game the player is in (#80), and moves each one's version
- [ ] **Claude** — a keep sets `last_activity_at`; a chat, a hide and a rename do not (RET-3)
- [ ] **Claude** — `engine_limit` bounds parallel searches, and a search's time starts once its permit is held (#429, D62)
- [ ] **Claude** — each `ApplyError` variant and each sender-check refusal maps to its own `Reason` in #402's body; a failed save is `ServiceBusy` with `Retry-After`, and a deleted game `GameNotFound`
- [ ] **Claude** — a reconnect yields the game's current view, with no `because` (#142)
- [ ] **Claude** — G7: `POST /games/{game_id}/suggest` is gone, answering 404, and nothing in the server calls the code it ran
- [ ] **Claude** — `turn` moves on a place, a pass and an exchange, and on no other change; each published state's `because` is board for a placement, periphery for a chat and game for the rest, and a reconnect carries none
- [ ] **Claude** — an illegal exchange and a placement out of turn are each refused with racks, bag, `version`, `turn` and the log unchanged and nothing published, and the same seat's legal move then applies
- [ ] **Claude** — a timeout, a force-end and a sweep's deletion publish through the same path as a request: subscribers to the game get the new state, or `GameRemoved` and a closed socket
- [ ] **Claude** — GAME-3 at creation: a create with one seat, or none, is refused and creates nothing, and with two it succeeds
- [ ] **Claude** — GAME-9: a create or an added seat naming an account that does not exist is refused and leaves no game or seat behind, and naming an existing account succeeds
- [ ] **Claude** — GAME-9: a spent seat stays spent: accept, decline and withdraw on a `Declined` or `Withdrawn` seat are refused, and inviting the same player again adds a new `Invited` seat
- [ ] **Claude** — the start is refused while any seat is `Invited` and succeeds once it is answered or withdrawn; a second start is refused; after the drop the turn order is the swapped order
- [ ] **Claude** — once a game has left `Waiting` (Active, Finished, Aborted), adding, accepting, declining, claiming, withdrawing and swapping a seat are each refused with `GameNotWaiting`, and each succeeds on a `Waiting` game
- [ ] **Claude** — GAME-8: a creator holding no seat adds, withdraws, swaps, starts, force-resigns, keeps, chats and aborts, and the view shows the creator to the players (GAME-12)
- [ ] **Claude** — GAME-10 and INV-3: two players claiming one open seat, or one link, at once, exactly one is seated and the other is told it is no longer available with nothing changed; a player already seated in the game may take an open seat; every signed-in player sees the game while the seat is open (the listing waits on the owner's placement of it)
- [ ] **Claude** — GAME-4: a player holding two seats is told which seat is on turn, and an invitation to each of them is answered separately
- [ ] **Claude** — INV-2 and INV-5: a claimed link moves its seat to `Invited` with the claimant as addressee, not to `Claimed`; only that addressee may then accept or decline; a verification after the claim leaves the seat alone
- [ ] **Claude** — INV-6: the creator's view shows the typed address, another player's view shows an invited seat with no address, nobody's shows the addressee before acceptance, and inviting answers the same for an unknown address, the creator's own and a seated player's
- [ ] **Claude** — GAME-2: a resignation, a force-resign or a timeout leaving one seat `Playing` finishes the game as `Played`, and one leaving two lets it go on; the scoreless limit and an empty bag with an empty rack also finish it as `Played`
- [ ] **Claude** — GAME-7 and TIME-3: a seat past its move time limit becomes `Departed`, timed out, and a seat within it does not; a timeout, a resignation and a force-resign each return the seat's tiles to the bag
- [ ] **Claude** — RATE-2: in a three-seat game, a seat that resigned is ranked below and rated against every seat that finished; in a four-seat game where two resign and the earlier resigner holds the higher score, the later resigner ranks above the earlier, and both rank below both seats that finished
- [ ] **Claude** — RATE-3: a seat that timed out or was force-resigned has no rating change, is not ranked, and the others' changes equal those of the same game played without it
- [ ] **Claude** — a bot comes on turn and plays after a timeout and after a force-resign hands it the turn, not only after a move
- [ ] **Claude** — an engine search that returns an error, panics or runs past `ENGINE_TURN_TIMEOUT` leaves its seat on turn and the game playable, nothing is returned to the human whose move started it, and a later legal move applies (supersedes #582 *#71 WP G: Test for the engine move timeout*)
- [ ] **Claude** — a bot move whose game was aborted, or whose seat was retired, during its search is refused on arrival and changes nothing
- [ ] **Claude** — GAME-1: an abort from `Waiting` freezes `Invited` and `Claimed` seats, and one from Active freezes `Playing` and `Departed` seats; afterwards every play and seat message is refused and a chat is still accepted
- [ ] **Claude** — GAME-11: a force-end of a game not started aborts it, one in play finishes it with the seats as they stand and a record of the force-end, and one of a game already over is refused
- [ ] **Claude** — GAME-12: a seated player and the creator can each post in a game Waiting, Active, Finished and Aborted; 1,000 characters are accepted, and 1,001 characters or a blank message are refused
- [ ] **Claude** — RET-3: adding, withdrawing, swapping, accepting, declining and claiming a seat each set `last_activity_at`, and a reminder sent does not
- [ ] **Claude** — ADM-2: `admin_delete_game` refuses a game in play and changes nothing, and deletes a game not started and a game over
- [ ] **Claude** — no state or event sent to a client names the account that acted beyond the seat; the log row's `actor_id` does
- [ ] **Claude** — `view_for` gives a viewer's own racks as `Visible` and every other as `Hidden` with its tile count, gives a seatless viewer no rack, and tells a hidden rack from an empty one
- [ ] **Claude** — the migration deletes every game and its moves, messages, seats and invitations, keeps every `players`, `sessions` and `rating_history` row, moves each engine's rating rows to its new bot account, which the listed bot finds at start-up, and makes each player's existing rating English (International)'s, with other editions starting at 1500
- [ ] **Claude** — the mixed roster: one game with an own seat, a bot, a named, an emailed and an open seat goes through creation, a resignation, a timeout, an abort and deletion in the lifecycle suite
- [ ] **Claude** — #106: inviting yourself by name gives a `Claimed` seat, as the creator's own seat is ([71-04](71-04-seats.md#how-a-seat-is-filled))
- [ ] **Claude** — #105: a player withdrawing from their own seat finds the game gone from their list in the same change, and a seat the creator withdraws stays in its player's list until that player hides it ([71-03](71-03-version.md#one-version-moved-in-one-place))
- [ ] **Claude** — INV-8: a spent link shows who sent it and that it is no longer available and never who took it, and the account it passed to, signed in, opens it (waits on the owner's placement of the link page)
