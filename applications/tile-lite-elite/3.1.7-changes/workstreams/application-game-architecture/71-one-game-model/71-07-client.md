# 71 The client

This file holds the client: the defect it shares with the server, how its
composition is keyed, the three tile states, deriving against accumulating and
where its state lives. It follows
[`71-06b-engine-bots.md`](71-06b-engine-bots.md) and is followed by
[`71-08-storage.md`](71-08-storage.md). Tokio and `watch`, which the server
side of this design uses, are explained in
[`71-06-engine.md`](71-06-engine.md); Dioxus and WebAssembly, which the client
is built on, are explained here, once.

## As-is

The client is `crates/ui`: Dioxus, compiled to WebAssembly for the browser, and
natively for a desktop build. Its state is in `RootApp` (`app.rs`, 5,522 lines).

### Worth keeping

- **`should_apply_update`** (`app.rs`) is one pure, unit-tested rule: a
  different game ID always applies; for the same game only a strictly greater
  `version` wins. HTTP responses and WebSocket frames have no ordering between
  them, and this keeps a late one from replacing a newer state.
- **The socket loops** (`subscribe_to_game_events_impl`, native and WebAssembly
  versions) stop when `websocket_game_id` no longer names their game, so a
  connection left over from a game the player has left cannot write to the
  selected one.
- **`clear_session_state`** deselects and resets together, the right shape:
  the login modal had appeared over the previous player's board.
- **`rack_order`** is the one value already matched rather than cleared: the
  render body rebuilds it when its length differs from the rack's
  (`app.rs`, near `unordered_rack_tiles`).
- **Three tile states are already drawn.** A staged tile is
  `tile-face tile-face-staged` (`board_view.rs`); a tile of the last move has
  `board-cell-last-move` on its cell, from `last_move_board_indices`
  (`views/home.rs`, unit-tested on `positions`); other tiles are `tile-face`.
- **The client runs the rules.** `client_rules.rs` adapts the DTOs to
  `rules-shared`, which validates and scores a staged word before anything is
  sent (`app.rs`, the move preview).
- **Nearly everything is derived on render**: 80 `use_signal`, 3 `use_effect`
  and no `use_memo` across the crate.
- **`e2e/tests/ui-state.spec.ts`** states the rule from outside the client:
  after any event that changes which game is selected, every dependent pane
  matches the new selection, including when the new selection is nothing.

### To move away from

- **No selection state.** `selected_id` is read back out of the loaded DTO
  (`game().as_ref().map(|current| current.id.clone())`, `app.rs`), so
  `game: Signal<Option<GameStateDto>>` holds both *what is selected* and *what
  has been loaded*. "Selected, not loaded yet" cannot be said, and "nothing
  selected" means discarding the DTO, so deselecting and clearing the panes
  are the same action and one can happen without the other.
- **A placeholder game keeps the board mounted.** With nothing selected the
  view uses `empty_live_game()` and carries `is_live: game().is_some()`
  separately (`app.rs`), so nothing forces a dependent pane to recompute when
  the selection changes; only a remembered call does.
- **The same reset is written five ways.**
  - `reset_composer_state` clears 7 signals and is called from 10 sites, one of
    them `clear_session_state`.
  - `clear_session_state` clears those 7, plus session, game, summaries and
    socket, and has 3 callers.
  - `on_clear_staged` is inline and clears 5 of the 7, omitting `exchange_mode`
    and `exchange_selected`.
  - `on_remove_game` does `game.set(None)` when the removed game is the
    selected one, and nothing else.
  - The `rack_order` reset is a bare `if` in the render body.
- **Nothing on the update path resets anything.** `apply_game_update` compares
  versions and swaps the DTO, and its 21 call sites in `app.rs`, with the two
  socket loops, never touch the composer. A server-pushed change, including one
  that ends the game, leaves a half-composed move in place. Two cases of the
  e2e file fail for this and are `test.fixme`: *aborting a game clears the move
  being composed*, and *Remove after composing a move leaves nothing behind*.
- **The scoreless rule is an accumulator.** `consecutive_scoreless_turns: u8`
  (`game_state.rs`, server) is reset by any placement and incremented by a pass
  and by an exchange, against `SCORELESS_TURN_LIMIT` (6).

## The model

The client holds four groups of state, by what makes each invalid:

- The *selection*, `selected_game: Option<GameId>`: intent, and nothing else.
- The *server cache*, `game` and `game_summaries`: replaced, never edited, and
  valid only for the current selection.
- The *composition*, the seven composer signals: the move a player is building
  from staged tiles, a cursor and an exchange choice. Valid only against one
  game and seat, while its cells are free and its tiles still in the seat's
  rack.
- The **session**, the **transport** (`IS_ONLINE`, `websocket_game_id`) and the
  **presentation** (`rack_order`, chat visibility), which are orthogonal to all
  of it.

The composition is the only group that goes stale, and it has a *composition
key*, the game and the seat. The rule is **stop clearing, start matching**: the
composition is stored with its key and filtered on read, so a *live
composition* is one whose key matches the current selection and whose cells and
tiles are still as it left them. Nothing clears it, so a writer that forgets
cannot cause the failure.

The server cache has one writer, `on_server_state`, which is
`should_apply_update` with nothing after it. The rest follows from what Dioxus
does and does not do for the client.

## Dioxus

### The Dioxus technology

Dioxus is a Rust framework for user interfaces in the style of React. This file
describes version 0.6.3, the one in `Cargo.lock` (`dioxus`, `dioxus-core`,
`dioxus-signals`, `dioxus-web`); #290 (WP F) moves the client to 0.7, and its
tests are what show that what is used here still holds.

- A *component* is a function, marked `#[component]`, that returns an `Element`
  built with the `rsx!` macro. Its arguments are its *props*, which must be
  `Clone` and `PartialEq` so that Dioxus can tell whether a child needs to run
  again.
- Running a component produces a *virtual DOM*, a tree that describes the
  interface. Dioxus compares it with the previous one and changes only the
  difference in the real page, through `dioxus-web` in a browser. A `key`
  attribute on repeated elements says which is which between renders.
- A *hook* is a function named `use_…` that keeps state for a component between
  runs. Hooks are called on every run, in the same order, never inside a
  condition.
- `use_signal(|| initial)` returns a `Signal<T>`, a small `Copy` handle to a
  value the runtime holds, so it can be moved into closures and async blocks.
  `signal()` clones the value and `signal.read()` borrows it. Either, called
  while a component renders, makes the component a *subscriber*; `peek()` reads
  without subscribing. `set`, `write` and `with_mut` replace or change the value
  and mark every subscriber to run again.
- Subscription happens only by reading while rendering. A read in an event
  handler or in an async task subscribes nothing.
- `use_memo` caches a value computed from signals and recomputes it when they
  change; `use_effect` runs code after a render and again when the signals it
  read change; `spawn` runs a future, here an HTTP call, tied to the component
  that started it.
- `Signal::global(|| initial)` makes a `GlobalSignal`, a signal that is not
  tied to one component.

### How the client uses Dioxus

#### Propagation is free, invalidation is not

- **Propagation, free.** Read a signal in the render body and the component
  runs again when it changes. The client leans on that everywhere: derived
  values such as `can_start`, `can_stage_moves` and `selected_id` are computed
  on render, which is the idiomatic thing, and not stored.
- **Invalidation, not free.** Dioxus renders a stale value faithfully. Nothing
  tells it that `staged_placements` stopped meaning anything when `game`
  changed, because nothing in the code says the two are related.

The server's answer, one event type and one handler, is the wrong answer on this
side, and not because the client deserves less rigour. Dioxus is already an
update mechanism, so a reducer would not replace anything; it would sit on top
of the framework's own propagation and duplicate it, at the cost of rewriting a
5,500-line component.

#### Stop clearing; start matching

**Clearing is a push model**: every writer must participate, and one that does
not is a defect found in testing, which is how ten remembered calls and the
sites that forgot came about. **Matching is a pull model**: nobody
participates, and a writer that forgets cannot cause the failure.
`on_remove_game` sets the selection to `None` and is finished; the staged tile
disappears because it no longer matches, not because anything remembered it.

Matching is not new in this codebase. The `rack_order` reset
([worth keeping](#worth-keeping)) is the same idea, inline, and is why it is not
one of the composition's signals.

What survives of "one transition per invariant" is small:

| kind | where it lives | who maintains it |
| --- | --- | --- |
| derived (`selected_id`, `can_stage_moves`, …) | not stored, computed on render | Dioxus |
| keyed (the composition) | stored with its key, filtered on read | Dioxus |
| side effects (token storage, socket teardown) | one function each | the code, about two of them |

**One consequence, taken deliberately.** Under matching a stale composition is
ignored, not destroyed, so leaving a game mid-turn to check another and coming
back restores the half-typed word. That is better behaviour than clearing it
and costs nothing: the bug fix and the small feature are the same change.

#### Where the state lives

```rust
selected_game: Signal<Option<GameId>>,        // intent
cache:         Signal<Option<GameStateDto>>,  // what the server last said
composition:   Signal<Option<Composition>>,   // keyed

pub struct Composition {
    pub key: CompositionKey,                  // game and seat
    pub staged: Vec<StagedPlacementView>,
    pub cursor: Option<usize>,
    pub direction: Option<DirectionDto>,
    pub blank_letter: Option<String>,
    pub exchange: Option<HashSet<usize>>,
}
```

The seven composer signals become one optional struct with a key, whose
fields are in [the composition key](#the-composition-is-keyed-by-game-and-seat).
`selected_id` stops being read back out of the loaded DTO, which is what makes *deselect* and
*clear the panes* the same action today.

#### How updates are centralised

**One entry point for anything the server says.** `apply_game_update` is called
from 21 sites in `app.rs` today, each a place that could forget something. It
becomes one:

```rust
/// The only function that writes `cache`. Every response and every socket
/// frame arrives here.
fn on_server_state(&mut self, incoming: GameStateDto, because: Option<GameEventDto>) {
    if !should_apply(self.cache.peek().as_ref(), &incoming) { return; }  // as today
    self.cache.set(Some(incoming));
    // nothing else. No clearing, no cascade.
}
```

**And nothing clears the composition.** It is read through
`live_composition`, in
[the key's section](#the-composition-is-keyed-by-game-and-seat), so a writer
that forgets cannot cause the failure, because no writer participates.

**Two side effects stay explicit**, because they are not state: storing the
session token, and tearing down the socket. Everything else is derived on
render.

#### What this does not become

Not a reducer over an event enum. The centralisation that is worth having is
**one writer of the server cache**, not one writer of everything.

## WebAssembly

### The WebAssembly technology

WebAssembly (wasm) is a compact binary instruction format that a browser runs
in a sandbox beside JavaScript, at close to native speed. Rust compiles to it
with the `wasm32` target; this client's browser build is that.

- A wasm module cannot reach the page, the network or storage itself. It calls
  browser functions through JavaScript glue that `wasm-bindgen` generates
  (0.2.103 in `Cargo.lock`), and `web-sys` and `js-sys` give Rust names to
  those functions.
- A default build runs on the browser's main thread, the one that also draws
  the page: it has no operating-system threads, so Tokio's multi-thread runtime
  is not there, and a long computation holds the page still until it returns.

### How the client uses WebAssembly

- **One crate, two targets.** `cfg(target_arch = "wasm32")` selects `gloo-net`
  for HTTP and WebSocket, `gloo-storage` for the token and `gloo-timers`; the
  native build selects `reqwest`, `tokio-tungstenite` and `tokio`.
- **The rules run in the browser.** `rules-shared` is compiled into the wasm
  module, and `client_rules.rs` validates and scores a staged word with it.
  Where a dictionary is compiled in natively, on wasm it is fetched
  (`load_client_dictionary`). The composition's
  [validity re-check](#the-composition-is-keyed-by-game-and-seat) is this code
  run on every board change.
- **A search in the browser would run on the main thread** unless moved to a
  worker, which bears on where an engine can run
  ([lifting the engine](71-06b-engine-bots.md#what-makes-lifting-it-possible)).

## The composition key

### What the composition is keyed on

The key is **the game and the seat**, and nothing else. A composition stays live
while its cells are still empty and its tiles are still in the seat's rack; it
is discarded when a tile is played in one of its cells or a tile it uses leaves
the rack (owner, 2026-08-29). Both are comparisons against the state the client
already holds, so nothing is stored or bumped to maintain them.

`version` cannot serve. It moves for any change, including an opponent's chat
message, and keying on it would wipe a half-typed word every time somebody
typed in the panel. That is the same failure as clearing, arrived at from the
other direction. `turn` cannot serve either: undo takes it back, so a
composition keyed on turn 8 would match again after an undo and redo, against a
board that has moved on.

`turn` still comes back as game state, separate from `version`: undo walks it,
the scoreless rule reads it and the player is shown it.

### The composition is keyed by game and seat

A staged word is displaced only when a tile is played in one of its own cells
(owner, 2026-08-29). An opponent playing elsewhere takes nothing away, so no
counter is part of the key:

```rust
pub struct CompositionKey {
    pub game: GameId,
    pub seat: u8,
}

fn live_composition(&self) -> Option<Composition> {
    let game = self.cache.peek().as_ref()?;
    let c    = self.composition.peek().clone()?;
    (c.key.game == game.id
        && c.staged.iter().all(|s| game.board[s.index].letter.is_none())
        && staged_tiles_still_held(&c, game))
        .then_some(c)
}
```

**Both conditions compare against the state the DTO already carries**: the
cells are empty, the tiles are still in the rack. The rack check covers what
the board check cannot: a rack changes without the board changing, after an
exchange or a timeout returning tiles to the bag, and a composition names tiles
by rack position. Nothing is stored, nothing is bumped, and nothing can be
forgotten in a handler.

**Composing does not need the turn; submitting does.** A composition survives
an opponent's turn, so a player can arrange a word while waiting (#88, carried
by this project). The client offers Submit only when `current_seat` is the
key's seat, and the server refuses anything else with `ApplyError::NotYourTurn`.

**Validity is a separate question from survival**, and conflating them would
throw work away. An opponent playing *adjacent* to a staged word leaves its
cells free but may make the word illegal: a cross-word that no longer exists,
or a connection that has become something else.

| | |
| --- | --- |
| the cells are taken | the tiles come back to the rack. There is nowhere for them to be |
| the cells are free but the word is now illegal | **the tiles stay**, and the client says so |

The client already runs the rules engine, so it can re-validate on every board
change and mark the word rather than silently dismantling it.

## Three tile states, and all three already exist

Owner, 2026-08-29: *"we will need to make sure that staged, just played, and
previously played tiles are easily distinguished"*, and *"we currently
distinguish tile played in the last move."*

Both are true, and this is a **requirement to preserve rather than to build**.
An earlier revision of this section said the board could draw only two states,
from reading the tile-face classes alone. The third is on the **cell**:

| state | drawn as | driven by |
| --- | --- | --- |
| **staged** | `tile-face tile-face-staged` | the composition |
| **just played** | `board-cell-last-move` on the cell | `last_move_cells: HashSet<usize>` |
| **previously played** | `tile-face` | the board |

So what this change owes is that all three survive it. Two things put that at
risk, and neither is obvious from the type definitions:

**`last_move_cells` is computed from the DTO's move list.**
`last_move_board_indices` reads the `positions` of `moves.last()`. Once
`MoveRecordDto` changes with the seat model and `description` becomes
structured, the computation has to be checked rather than assumed: it is exactly
the kind of derived value that keeps working until it quietly does not. Its unit
tests build records by hand, so they would not notice.

**The staged state must survive board changes that do not touch its cells.**
Under the current *clear on any change* behaviour the staged class simply
disappears, which no test would notice because disappearing is what it is
supposed to do eventually.

### An enhancement this makes cheap, not part of the change

*"Just played"* means the **last move**. A player returning after several moves
sees only the most recent one highlighted, and what they actually want is
everything that happened while they were away.

The client knows the version it held before the update, because
`should_apply_update` compares against it, so *"since the version I last held"*
is derivable, **if move records carry the version they happened at**:

```rust
pub struct MoveRecordDto {
    pub version: i64,      // new — which version this move produced
    // …the rest as today; `description` becomes structured…
}
```

One field, no server state, and the log wants it anyway. Worth listing
separately rather than folding in: it is a change to what a player sees, and it
should be somebody's decision rather than something that arrives with a
refactor.

## Deriving beats accumulating, and the scoreless rule is the case

Owner, 2026-08-29: *"is turn useful for the terminating condition where there
are multiple non-scoring turns?"* Yes, and it is the better shape.

The game carries an accumulator, `consecutive_scoreless_turns` (see
[to move away from](#to-move-away-from)). It is replaced by a mark:

```rust
pub last_scoring_turn: i64,
// the rule, at the point of use:
let scoreless = self.turn - self.last_scoring_turn;
```

**Three things get better, and the third is the one that matters under undo.**

**It is checkable.** `turn - last_scoring_turn` can be verified against the move
log; `consecutive_scoreless_turns` is a number that can only be trusted. A
count that nothing can contradict is a count that can be wrong for a long time.

**The rule stops being baked into the stored value.** Changing the limit from
six to eight is a comparison changing, not stored counters meaning something
new.

**And it survives undo without unwinding.** Undo produces a new higher version
whose content is an earlier state, so every field is restored together, and a
derived quantity is right the moment its inputs are. An accumulator restored the
same way is also right; the difference appears if undo is ever implemented as
*applying an inverse* rather than restoring, where every accumulator needs its
own decrement and one that is forgotten is silently wrong. Deriving means there
is nothing to forget.

**The honest caveat**: as the design has undo, restore and not inverse, the
accumulator would also survive, so this is not a fix for a bug that exists. It
is choosing the shape that stays correct under a change of undo strategy, at a
cost of nothing.

**One thing it does not change.** *Scoreless* still means what it means today:
a pass or an exchange, each a turn, so `turn` advances for both, and any
placement ends the run. If either ever stops advancing the turn, this
derivation breaks silently, which is worth a test rather than a comment.

## How the client will be known to be right

`e2e/tests/ui-state.spec.ts` states the rule from outside the client: **after
any event that changes which game is selected, every dependent pane matches the
new selection, including when the new selection is nothing.** Eight cases,
written against the intended behaviour rather than the current one. Six pass
today. Two are `test.fixme` and are the bug that prompted this design:

- *aborting a game clears the move being composed*: the staged tile survives
  onto a game that is over.
- *Remove after composing a move leaves nothing behind*: the staged tile is
  left drawing on an empty board with no game selected.

The Remove case was mutation-tested: deleting `game.set(None)` from
`on_remove_game` turns *Remove clears the board and rack* red with seven rack
tiles still on screen, so the passing tests are holding something up rather
than passing vacuously.

## This is delivered in Core Client UI

Raised as **#157**, which carries the reproduction and the two handlers it
lands in. Client-only: no server change, no API version move, no migration. The
staged tile left behind after a game is removed is a symptom of how state
changes are managed today, so the fix is the composition key, delivered in #269
(Core Client UI) rather than as a separate release.[^d57] The fault stays live
until #269 ships, and the two `test.fixme` cases in
`e2e/tests/ui-state.spec.ts` are #269's acceptance tests.

[^d57]: Decision #443 (D57): fixed in #269 by the composition key.
