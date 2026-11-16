# 71 Handover

**What a thread taking over #71 needs, and where it lives.** The role is the
design authority for Application & Game Architecture, which runs #71
because #71 dominates the workstream ([1.7](../../../../../../docs/1.7-roles-and-responsibilities.md)).
This file says where the state is and what is open; the state itself is in the
documents and issues it names. Written 2026-10-14, at the handover after the
decision backlog was cleared, and brought up to date on 2026-11-16 for the v4
thread.

Issue numbers here are Tile Lite Elite's (`delphside/tile-lite-elite`) unless
written otherwise.

## Read first

1. #71's body: the allocation table, the Decisions table, and the code-review
   findings routed from #460.
2. The functional set, in order: [`71-functional.md`](71-functional.md) (the use
   case, how to read the journeys, and the lifecycles),
   [`71-journeys-u1-u3.md`](71-journeys-u1-u3.md),
   [`71-journeys-u4-u6.md`](71-journeys-u4-u6.md), and
   [`71-journey-questions.md`](71-journey-questions.md) (Q1 to Q15, all
   answered).
3. [`71-01-as-is.md`](71-01-as-is.md), then
   [`71-02-overview.md`](71-02-overview.md): the table of the design's files,
   the *Pending decisions* paragraph after it, then the goal and the
   work-package sections. The other technical files are read as the work needs
   them: [`71-03-version.md`](71-03-version.md),
   [`71-04-seats.md`](71-04-seats.md), [`71-05-wire.md`](71-05-wire.md),
   [`71-05b-wire-types.md`](71-05b-wire-types.md),
   [`71-06-engine.md`](71-06-engine.md), [`71-06b-engine-bots.md`](71-06b-engine-bots.md), [`71-07-client.md`](71-07-client.md),
   [`71-08-storage.md`](71-08-storage.md),
   [`71-09-open-questions.md`](71-09-open-questions.md) and
   [`71-10-documents-changed.md`](71-10-documents-changed.md).
4. [`71-life-histories.md`](71-life-histories.md): the entity and event matrix
   and the open G questions; [`71-impact.md`](71-impact.md); and the test
   approach, [`71-test-approach.md`](71-test-approach.md) with one
   `71-test-wp-*.md` per work package.
5. [`71-delivery.md`](71-delivery.md): `release/1.0.0` for #268 and #269.
6. Tile Lite Elite's [4.1.0 rules](https://github.com/delphside/tile-lite-elite/blob/main/docs/4.1.0-rules.md),
   which the journeys cite.

## Where state lives

- **This folder** is a change document in `delphside/programme`. A web session
  changes it through a short-lived `claude/` branch with one pull request,
  merged by the thread once the required checks pass, with a *Review* section
  saying none is needed ([1.2](../../../../../../docs/1.2-change-lifecycle.md) §2.2).
- **Living documents** (Tile Lite Elite's `docs/4.x`) change in
  `delphside/tile-lite-elite`, on the project branch, with a pull request the
  owner reviews and approves before it merges.
- **Decisions** are issues D56 to D72 (#442 to #479), applied in the documents
  and closed once applied.
- **Single writer.** This thread writes this folder, #71's body and the Decision
  issues. Other threads, the local WSL sessions included, send changes through
  the coordinator.

## Open, and whose move it is

| item | waits on |
| --- | --- |
| Q5's email rules move to 4.1.0 when #439 lands | #439 |
| DEL-2 refusing to close an account while a passed invitation names it: principle 9 calls it acceptable | owner, on #439 |
| #439's open rows: friends and blocking (the old address is told of a change: R6, NOTE-1) | owner, on #439 |
| closing your own account, suspension, support requests and complaints | #296 (R1 to R5) |
| The as-is design map (#406) is on Tile Lite Elite main (delphside/tile-lite-elite#523). Check-docs step 8 starts checking it when #522 moves the `programme/` pin; if it reports stale, regenerate with `programme/scripts/docs/design-map/design-map.py --write` | #522 |
| [`71-map-change.md`](71-map-change.md) is a prototype: WP A and WP C only. The format's three gaps are closed (programme #41), and [`71-map-diagrams.md`](71-map-diagrams.md) is generated from it with `design-map.py --change`. WP A's to-be is drawn and designed (programme #60 and #62): the layering, per-game latest-state channels, `game-wire`'s two message enums, the seat list and the bot list ([71-06-engine.md](71-06-engine.md#the-model) and [71-06b-engine-bots.md](71-06b-engine-bots.md#the-bots-the-server-runs)). Tile Lite Elite runs the mode from `../programme` until its `programme/` pin moves past programme #41. A package's drawing shows only its own lines (owner, 2026-11-15) | — |
| #538: the move generator finds only moves whose first tile is on an anchor (with AT on the board and B, O in the rack it offers OAT, misses BOAT). It affects bots, suggestions and opening moves, so WP A's engine design takes it into account once triaged | owner, triage of #538 |
| A compiling sketch of `game-wire`'s types (links, both message enums, `Bot<L>`, engine levels) is in the project files at `notes/71/game-wire-sketch/`; WP A's code branch starts from it. Brought into line with the design on 2026-11-16: seat ids, the `Player`/`System` split, `GameEnd`, G2, G3 and G6 | WP A Development |
| #542 entity life histories: WP A's matrix and runtime state tables are in [`71-life-histories.md`](71-life-histories.md). G1 to G7 are answered and written into the design and WP A's tests (programme #211, 2026-11-16) | — |
| WP A's to-be check: seven design-review rounds, applied in programme #211; the last found nothing material. What remains for WP A to leave Design and Test Approach is the test manager's sign-off of `71-test-wp-a.md`, which gained boxes, and the bot account's `players` row in [*Open questions*](71-09-open-questions.md#open-questions) | test manager; Claude |
| #585 *Hints, which make a game unrated*: triaged, kept beside #71 (owner, 2026-11-12); WP A removes `suggest_move` until it is built (G7) | owner, when and whether |
| #268 waits on #606 *#402 WP A: API errors to the scheme*: Core adopts #402's error body (owner, 2026-11-16, superseding D65) | #606 |

## Settled on 2026-11-15

Each is written into the design (programme #189, #191, #194, #197), so the
files are the authority; this list says only where to look.

- Bot moves are paced by a capped client playback queue that plays only
  moves ([71-07](71-07-client.md)).
- Every score change is a move record, end-of-game rack adjustments included,
  carried on the finishing turn's event ([71-05b](71-05b-wire-types.md)).
- G1: a seat has a fixed `id` and a turn-order `number` ([71-04](71-04-seats.md)).
- G4: an account on the bot list cannot be deleted, and a bad bot list stops
  start-up ([71-06b](71-06b-engine-bots.md)).
- `GameCommand` is split into `Player(GameMessage)` and
  `System(SystemMessage)` ([71-03](71-03-version.md)).
- A package's drawing shows only its own lines in a Component view
  ([406's format](../406-architecture-views/406-map-format.md#a-packages-drawing)).

## A tooling defect met on the way

`scripts/programme/board/roadmap-diagram.py --project 71 --write-issue 71`
reads issues with `gh issue view`, which is GraphQL and refused in cloud
sessions, so it finds no body. Its row pattern also matches the Decisions
table, drawing two false packages. On 2026-10-14 the diagram in #71's body was
regenerated through a REST shim with those two removed by hand.
