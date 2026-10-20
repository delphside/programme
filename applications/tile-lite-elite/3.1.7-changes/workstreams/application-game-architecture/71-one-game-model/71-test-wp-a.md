# 71 Tests: WP A, #268 Core Game Lifecycle

Fitted to [`71-test-approach.md`](71-test-approach.md), which holds the layers
and what each can answer; this file says what WP A uses of them. The scope is
in [`71-design.md`](71-design.md), *Work packages*.

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
- **An engine run both ways** — through the in-process glue and through the
  external transport — on the same position, producing the same move.
- **The external transport is tested as the external path.** Pointing the test
  client or a harness at `localhost:3000` still runs HTTP, WebSocket and JSON
  and meets the rate limiter, which is keyed by the caller's address, and it
  makes the bot a loopback caller, which the admin routes trust. It is not the
  route of the server's own bots, which use the glue at the Game service; that
  has its own test.

## The journeys and rules it covers

[U2.1 Create and start a game](71-functional.md#u21-create-and-start-a-game), [U3.1 Accept or decline an invitation](71-functional.md#u31-accept-or-decline-an-invitation), [U4.1 Take a turn](71-functional.md#u41-take-a-turn), [U4.4 Leave a game in play](71-functional.md#u44-leave-a-game-in-play) and
[U4.5 Abort a game](71-functional.md#u45-abort-a-game), from [`71-functional.md`](71-functional.md): GAME-1 to GAME-4,
RATE-1 to RATE-3, TIME-3, DEL-2, DEL-3, and the tests the code review found
missing (`71-test-approach.md`).

## Its acceptance

- [ ] **Claude** — every `GameMessage` arm has a test that it moves `version`, and a refused one that it changes nothing
- [ ] **Claude** — the round-trip property passes over generated `GameView`s, and `view_for` shows a viewer holding two seats both racks
- [ ] **Claude** — the in-process bot is handed only its own game, redacted for its account, and is never answered 429
- [ ] **Claude** — a scripted second client sees every change the first makes, invitations included, within one broadcast
- [ ] **Claude** — the same engine plays the same move through the glue and through the external transport
