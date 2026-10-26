# 71 Handover

**What a thread taking over #71 needs, and where it lives.** The role is the
design authority for Application & Game Architecture, which runs #71
because #71 dominates the workstream ([1.7](../../../../../../docs/1.7-roles-and-responsibilities.md)).
This file says where the state is and what is open; the state itself is in the
documents and issues it names. Written 2026-10-14, at the handover after the
decision backlog was cleared.

Issue numbers here are Tile Lite Elite's (`delphside/tile-lite-elite`) unless
written otherwise.

## Read first

1. #71's body: the allocation table, the Decisions table, and the code-review
   findings routed from #460.
2. [`71-design.md`](71-design.md): the *Pending decisions* table at the top,
   then the work-package sections.
3. [`71-delivery.md`](71-delivery.md): `release/1.0.0` for #268 and #269.
4. [`71-functional.md`](71-functional.md): the use case, the journeys, the
   lifecycles, and *Questions the journeys raise* (Q1 to Q15, all answered).
5. Tile Lite Elite's [4.1.0 rules](https://github.com/delphside/tile-lite-elite/blob/main/docs/4.1.0-rules.md),
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
- **Single writer.** This thread writes this folder, #71's body and the D-issues
  above. Other threads, the local WSL sessions included, send changes through
  the coordinator.

## Open, and whose move it is

| item | waits on |
| --- | --- |
| Q5's email rules move to 4.1.0 when #439 lands | #439 |
| DEL-2 refusing to close an account while a passed invitation names it: principle 9 calls it acceptable | owner, on #439 |
| #439's open rows: friends and blocking (the old address is told of a change: R6, NOTE-1) | owner, on #439 |
| closing your own account, suspension, support requests and complaints | #296 (R1 to R5) |
| The as-is design map (#406) is on Tile Lite Elite main (delphside/tile-lite-elite#523). Check-docs step 8 starts checking it when #522 moves the `programme/` pin; if it reports stale, regenerate with `programme/scripts/docs/design-map/design-map.py --write` | #522 |
| [`71-map-change.md`](71-map-change.md) is a prototype: WP A and WP C only. The format's three gaps are closed (programme #41), and [`71-map-diagrams.md`](71-map-diagrams.md) is generated from it with `design-map.py --change`. WP A's to-be is drawn and designed (programme #60 and #62): the layering, per-game latest-state channels, `game-wire`'s two message enums, the seat list and the bot list ([71-data-model.md §8](71-data-model.md#8--the-engine)). Tile Lite Elite runs the mode from `../programme` until its `programme/` pin moves past programme #41 | owner: how dense a package's drawing may be |
| #538: the move generator finds only moves whose first tile is on an anchor (with AT on the board and B, O in the rack it offers OAT, misses BOAT). It affects bots, suggestions and opening moves, so WP A's engine design takes it into account once triaged | owner, triage of #538 |
| A compiling sketch of `game-wire`'s types (links, both message enums, `Bot<L>`, engine levels) is in the project files at `notes/71/game-wire-sketch/`; WP A's code branch starts from it | WP A Development |
| Split the server-only variants (`TimeOut`, `ForceResign`, `AdminForceEnd`, `ReminderSent`) out of `GameMessage` into a server-side `GameCommand`; recommended, asked on a card in the #71 thread on 2026-10-21 | owner |
| #542 entity life histories: WP A is its first use, so WP A's design gains an entity/event matrix and a state table per entity | Claude, next #71 work |

## A tooling defect met on the way

`scripts/programme/board/roadmap-diagram.py --project 71 --write-issue 71`
reads issues with `gh issue view`, which is GraphQL and refused in cloud
sessions, so it finds no body. Its row pattern also matches the Decisions
table, drawing two false packages. On 2026-10-14 the diagram in #71's body was
regenerated through a REST shim with those two removed by hand.
