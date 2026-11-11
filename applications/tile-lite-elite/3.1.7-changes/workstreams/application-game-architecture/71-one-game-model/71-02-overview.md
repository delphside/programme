# 71 One game model

Design note for issues #9, #10, #26, #71 and #75, and the undo work in #73
that depends on them. **Not yet implemented** — this records the shape agreed
before code. This file follows [`71-01-as-is.md`](71-01-as-is.md) and is
followed by [`71-03-version.md`](71-03-version.md).

The design is one file per subject. The functional set comes first, then the
technical design, 71-01 to 71-10, of which this file is the second:

| File | What it holds |
| --- | --- |
| [`71-functional.md`](71-functional.md) | the use case and the lifecycles, and the key to reading the journeys |
| [`71-journeys-u1-u3.md`](71-journeys-u1-u3.md), [`71-journeys-u4-u6.md`](71-journeys-u4-u6.md) | the journeys U1 to U6 |
| [`71-journey-questions.md`](71-journey-questions.md) | the functional questions the journeys raise, Q1 to Q15 |
| [`71-01-as-is.md`](71-01-as-is.md) | how it works today, and what is wrong with it |
| [`71-02-overview.md`](71-02-overview.md) | this file: the goal, what it makes possible, the non-functional design and the work packages |
| [`71-03-version.md`](71-03-version.md) | one version, moved in one place: the session, the counters, the categories of change, the message and the one handler |
| [`71-04-seats.md`](71-04-seats.md) | seat state: states, addresses and invitations, how the seat carries them, the seat as written, access |
| [`71-05-wire.md`](71-05-wire.md) | the wire: invisible DTOs, the types on the wire, the interface layer |
| [`71-06-engine.md`](71-06-engine.md) | the engine as a client: levels, who calls it, what makes lifting it possible |
| [`71-07-client.md`](71-07-client.md) | the client: its state, its composition key, the three tile states, how updates are centralised |
| [`71-08-storage.md`](71-08-storage.md) | migration, the database schema and the modules that change |
| [`71-09-open-questions.md`](71-09-open-questions.md) | the open questions, and the ones settled |
| [`71-10-documents-changed.md`](71-10-documents-changed.md) | the documents this changes, and the two diagrams that move into 1.2 |

**The documents run top-down, one file per stage.**[^d71]
The functional set is the use case diagram, the journeys and the lifecycles.
The files 71-01 to 71-10 are the technical design, overall first and then a
section scoping each work package. How it is proved is
[`71-test-approach.md`](71-test-approach.md), with one test file per package
written to fit it.

**Pending decisions.** Where the design is not final it says so and names
the Decision issue that will settle it. They are answered in the order
[docs/1.2](../../../../../../docs/1.2-change-lifecycle.md#decisions) sets.
None is open as of 2026-10-14; the functional questions the journeys raise are
in [`71-journey-questions.md`](71-journey-questions.md).

The design map this project starts from is Tile Lite Elite's
`docs/4.2.0-design-map.md`, in
[#406's format](../406-architecture-views/406-map-format.md).

## The goal

One goal, from which everything here follows:

> **Engine code cannot tell whether it is running in the server or in a
> client.**

Two things have to be true for that. The engine must be handed the same
objects wherever it runs, and it must be driven the same way. Neither is true
today, and the reasons turn out to be the same reasons a client sometimes
never hears that a game changed: they are set out in
[`71-01-as-is.md`](71-01-as-is.md#what-is-wrong-now).

## What this makes possible

**Undo.** With one sequence covering every change, the history is keyed and
undo becomes "return the game to the state it held at version N", published as
a new higher version. The events already exist in substance; what they lack is
a key that orders *every* change rather than only the ones that write a row.
Undo is not in this change, but this change is what it waits for.

**A benchmark and a load generator over the real path**, once an engine can
run as an external client, and the option of running bots off the server
entirely — which is the largest CPU cost the server currently carries.

## What does not change

The rules engine, the dictionaries, the scoring, the rating algorithm, and how
a move is validated. This design is about who holds the state, who is told when
it changes, and how a turn reaches the thing that takes it.

## How we will know

- **A round-trip property test** over every type crossing the wire, `GameView`
  among them. Written first: it states what "invisible" means precisely
  enough to know when the move is finished.
- **An engine run both ways** against the same position, through the
  in-process glue and the external transport, producing the same move.
- **The existing lifecycle suite**, which already walks a game from creation
  through resignation, abort, timeout and retention, and should pass unchanged
  except where it asserts a behaviour this design deliberately alters — **plus a
  game holding every kind of seat at once**, which it has never had.

The mixed roster belongs *in* the lifecycle suite rather than beside it, and
that is a decision rather than a filing convenience. Every scenario there
builds a uniform roster, so the composite case — the ordinary one in a game
with more than two players — is the one nothing has ever walked. Making it a
separate test would leave the lifecycle suite still proving the uniform case
and nothing else; putting it inside means creation, resignation, abort, timeout
and retention are each exercised against a roster that is genuinely mixed.

It is also the test that checks the claim this design rests on. *The whole state
is composite* — the game has four states of its own and every seat has its own
lifecycle, running independently — and nothing may assume a game is in a single
invitation phase. A suite that only ever sees uniform rosters cannot tell
whether that holds.

`issue-71-mixed-roster-coverage` covered part of this against the old seat
model and was dropped on 2026-08-17, since `SeatState` replaces what it
asserted. The gap it found is real and gets wider here: there are now more
states to mix.

## Non-functional design

**Capacity.** One process on a two-core VM. Engine searches are the largest CPU
cost the server carries, and moving them off the request path removes the
accidental bound on them, so a bound replaces it: `engine_limit`, default 2
because the VM has two cores [^d62], taken by every search and every hint.
Memory is unchanged in kind: every live game is held in the map as
today, one lock each. The whole-state-per-update wire costs a few kilobytes per
message per connection, which is what is sent today. Each game has its own
`watch` channel holding the latest state, so a change costs that game's
receivers only, however many games and players there are
([The engine](71-06-engine.md#the-engine)).

**Assumption: routing.** Every connection for a game must reach the server that
owns the game, because the channels are in-process; bots on another server are
ordinary external clients over HTTPS. Routing clients to that server belongs to
a future identity and routing application, outside #71.

**Failure.** A refused message changes nothing. An engine that errors, panics
or overruns leaves its seat on turn for the move time limit. A failed save is
retried if transient, then reloads the game, and the change did not happen
[^d69]; a game that cannot be reloaded refuses messages until it can. A
client that misses an update catches up on reconnect, because every message
carries the whole state and its version.

**Limits and timeouts.** `ENGINE_TURN_TIMEOUT` (5 s) bounds a search, as today,
counted from when its `engine_limit` permit (2, from the core count) is held;
`MAX_ENGINE_TURNS_PER_TRIGGER` goes with the loop it bounded. The move time
limit is the game's own setting. Request throttling is unchanged
(`app/throttle.rs`).

**Secrets and access.** No new secret. An external bot is an account with an
owner and authenticates as one, so a harness holds a session token like any
client; how long that session lives is ACC-1's, with no exemption for bots
(D66). The in-process bot holds no session: its link is built with the identity
the settings list (`TILE_LITE_ELITE_BOTS`, proposed), and the programme owner,
who owns the list, is accountable for the bots on it. What a connection may see
is the union over the seats its account holds; an event never names who
acted on a seat beyond the seat itself.

## Work packages

The design in 71-01 to 71-10 is delivered in six packages (D56, #442), and a
seventh, WP G, ships ahead of them. Each section
says what the package takes from the design, and what it waits on. A package's
requirements are on its issue; its tests are in its own test file.

**The split serves three ends** (owner, 2026-09-02): packages small enough to
manage, the core proven before anything is built on it, and deliveries that can
ship separately. Two rules draw the line between Core and Additional:

- **Core takes nothing that can be done later at no extra cost.** The question
  for each requirement is whether deferring it costs more: deferring #253 means
  a second migration over the same tables, so it is Core's; deferring #68 or #87
  costs nothing, so they are Additional's.
- **Every schema change belongs in Core**, because a migration is expensive to
  repeat and risky to interleave.[^d64] Undo's history table is laid down in
  Core even though undo itself is WP E.

What Core does not take falls to the others: Additional Game Lifecycle takes
every other server change apart from undo and redo, and Additional Client UI
every other game-related client change, including whatever Additional Game
Lifecycle needs. Anything game-related outside #71 must be independent of it
and doable at any time (owner, 2026-09-02).

Core Client UI is filled by Core's design, not from the backlog: it holds the
client changes Core's server changes require.

### WP A, #268 Core Game Lifecycle

**Takes**: [*One version, moved in one
place*](71-03-version.md#one-version-moved-in-one-place), with every
`GameMessage` variant except undo and redo; per-game locking; the seat model and
its lifecycle; [*DTOs are invisible*](71-05-wire.md#dtos-are-invisible),
including the opponent tile count and the shared error body (D65); [*The engine
is a client*](71-06-engine.md#the-engine-is-a-client), with the in-process glue
under the bot; the append-only game log (D61);
[*Migration*](71-08-storage.md#migration), with the schema version, foreign keys
and the rating key; the user-details lookup rule; and the code-review findings
routed from #460 to it. It takes #142, #80, #106, #105, #429 and the invitation
that outlives its game, each true by construction here [^d67]. It also builds
the `game-wire` crate and the test client.

**Waits on**: nothing still open. It builds the test client and stops short of
the harness, which is #10's (D63). Its tests:
[`71-test-wp-a.md`](71-test-wp-a.md). What each event does to each entity it
touches is in [`71-life-histories.md`](71-life-histories.md) (#542).

### WP B, #269 Core Client UI

**Takes**: [*The client has the same
defect*](71-07-client.md#the-client-has-the-same-defect) — one writer of the
server cache, matching rather than clearing, the composition keyed by game and
seat — and whatever client change WP A's wire change forces, with #152 and #88,
both composition behaviour [^d67]. It also changes how a creator fills the seats
(owner, 2026-10-14). Today the client adds seats, then sends the invitations,
then starts. Instead each seat goes its own way: added and invited at once, then
declined or withdrawn, and replaced by a new seat, independently of the others,
until the creator has a set of claimed seats and starts the game. Ships with WP
A.

**Waits on**: WP A's wire shapes. Its tests:
[`71-test-wp-b.md`](71-test-wp-b.md).

### WP C, #270 Additional Game Lifecycle

**Takes**: the scheduled jobs that are not yet built — RET-3's countdown and a
message reaching a player who is not looking — each through the one handler, as
[*Arrows with no command*](71-functional.md#do-the-arrows-match-the-messages)
requires.

**A player who is not looking is reached by Web Push** (#87; owner,
2026-10-17). It is the W3C Push API with VAPID (RFC 8292): the client's
service worker subscribes, the server stores the subscription and sends to it
when an event the player has chosen happens, and a send the push service
answers with 404 or 410 removes the subscription, as RFC 8030 says it is gone.
On iPhone it works only once the site is added to the home screen, which is
the client's to explain (WP D). The VAPID key pair is a server secret, held
like the others the server already has.

**Schema needs**, which ship in WP A's migration (D64):
`games.last_activity_at`, already in WP A's schema; `push_subscriptions` and
`notification_preferences` for Web Push; and `players.stats_private` for RATE-5.
Which events ping is data in `notification_preferences`, keyed by event kind, so
choosing or adding one changes no schema. **Which events ping, and whether a
player may change it, is NOTE-1's table** (4.1.0; owner, 2026-10-17), each cell
Always, On, Off or Never. The server holds it in one Rust module of its own
(owner, 2026-10-17): an event-kind enum and one exhaustive match giving each
kind its email and notification values, so a missing event or an invalid value
does not compile, and a unit test reads the table against NOTE-1's.
`notification_preferences` stores only a player's departures from an On or Off;
Always and Never have no row. The module gets a row in 4.4.1 when WP C builds
it. RET-3's question to the creator is shown in the games list and not sent
([4.2.4](https://github.com/delphside/tile-lite-elite/blob/main/docs/4.2.4-persistence.md)),
so it needs no marker. Columns in
[`71-08-storage.md`](71-08-storage.md#database).

**Waits on**: WP A. Its tests: [`71-test-wp-c.md`](71-test-wp-c.md).

### WP D, #271 Additional Client UI

**Takes**: the client work WP C implies, and #84, #146 and #239.

**Schema needs**: none of its own. #84's groups and counts derive from the games
list and its "remove all" uses `hidden_by_player`; #146 is layout; #239 reads
the move records already sent.

**Waits on**: WP B and WP C. Its tests: [`71-test-wp-d.md`](71-test-wp-d.md).

### WP E, #272 Undo and Redo

**Takes**: [*What this makes possible*](#what-this-makes-possible), undo — a
new, higher version whose content is an earlier state, with `turn` walking back.

**Schema needs**: none of its own. It reads `games.version`, `turn` and
`last_scoring_turn`, `game_events` and the snapshot's schema version, all WP
A's; undo and redo are new messages and events in columns that hold JSON.

**Waits on**: WP A, which writes the history it reads (D61). Its tests:
[`71-test-wp-e.md`](71-test-wp-e.md).

### WP F, #290 dioxus 0.7

**Takes**: nothing from this design; it is the framework upgrade WP B and WP D
are written against.

**Schema needs**: none; it changes the client framework only.

**Waits on**: nothing in #71. Its tests: [`71-test-wp-f.md`](71-test-wp-f.md).

### WP G, #582 Test for the engine move timeout

**Takes**: #572, a test of today's engine timeout, outside D56's split (owner,
2026-11-11). It ships ahead of the other packages and is superseded by WP A's
own timeout test.

**Waits on**: nothing. Its test is the change itself, on #582.

[^d71]: Decision #472 (D71): one file per stage, functional views before the
    technical design; work packages scoped as sections of this design, and a test
    file per package fitted to the overall test approach.

[^d62]: Decision #462 (D62): `engine_limit` bounds parallel searches and hints;
    the default stays 2, the VM's core count. The search's time starts once
    the permit is held, and the engine is sent a stop signal (owner, 2026-10-14).

[^d69]: Decision #469 (D69): the database holds what has happened. A failed
    save is retried by its error's class, then fails into a reload, under the
    game's lock, with an unsaved flag for any reader the failure leaves behind
    (owner, 2026-10-14). Database failure in general is #402's.

[^d64]: Decision #464 (D64): `release/1.0.0` for #268 and #269, carrying every
    schema change the project needs.

[^d67]: Decision #467 (D67): each requirement folded before the packages existed
    goes to the package whose design makes it true.
