# 71 The client

This file holds the client: the defect it shares with the server, how its
composition is keyed, the three tile states, deriving against accumulating and
where its state lives. It follows [`71-06-engine.md`](71-06-engine.md) and is
followed by [`71-08-storage.md`](71-08-storage.md).

## The client has the same defect

The server's problem is that many writers may move the version and only some
remember to. The client's is the same sentence with different nouns: many
handlers change what is on screen, and only some remember to refresh the panes
that depended on it.

**There is no selection state.** Which game is selected is read back out of the
loaded DTO:

```rust
selected_id: game().as_ref().map(|current| current.id.clone()),   // app.rs
```

So `game: Signal<Option<GameStateDto>>` is doing two jobs — *what is selected*
and *what has been loaded* — and they are not the same fact. There is no way to
say "game X is selected, not loaded yet", and the only way to say "nothing is
selected" is to throw the DTO away. Deselecting and clearing the panes are
therefore the same action, which is exactly why one can happen without the
other.

The board pane is never unmounted. With nothing selected the view falls back to
a placeholder game, and `is_live` is carried separately:

```rust
let game_for_view = game().clone().unwrap_or_else(empty_live_game);
```

Reasonable as a landing view, but it means nothing *forces* a dependent pane to
be recomputed when the selection changes. Only a remembered call does.

### The same job, solved five times

| what | clears | called from |
| --- | --- | --- |
| `reset_composer_state` | 7 signals | **10 sites** |
| `clear_session_state` | those 7, plus session, game, summaries, socket | 3 |
| `on_clear_staged`, inline | 5 of the 7 — omits `exchange_mode`, `exchange_selected` | 1 |
| `on_remove_game` | `game.set(None)` and nothing else | 1 |
| `rack_order` reset | a bare `if` in the render body | — |

`clear_session_state` is already the right shape — deselect *and* reset,
together — because the bug that prompted it was visible: the login modal
appeared over the previous player's board. The other paths never adopted it.

And nothing on the *update* path resets anything. `apply_game_update` compares
versions and swaps the DTO; it never touches the composer. So every
server-pushed change — including one that ends the game — leaves a
half-composed move in place.

### The state, grouped by what makes it invalid

- **Selection** — `selected_game: Option<GameId>`. Intent, and nothing else.
- **Server cache** — `game`, `game_summaries`. Replaced, never edited. Valid
  only for the current selection.
- **Composition** — the seven composer signals. **Valid only against one game,
  and only while it is still that player's turn in it.**
- **Session**, **transport** (`IS_ONLINE`, `websocket_game_id`), and
  **presentation** (`rack_order`, chat visibility) — orthogonal to all of it.

Composition is the only category that goes stale, and it has a key. So rather
than rely on discipline, give it that key:

```rust
selected_game: Option<GameId>,
composition:   Option<Composition>,   // { key: CompositionKey, staged, cursor, exchange, … }
```

### Stop clearing; start matching

The instinct here is the server's answer again — one event type, one handler,
every change through it. It is the wrong answer on this side, and not because
the client deserves less rigour. Dioxus already *is* an update mechanism, so a
reducer would not replace anything; it would sit on top of the framework's own
propagation and duplicate it, at the cost of rewriting a 5,500-line component.

What Dioxus gives free, and what it does not, is worth separating:

- **Propagation — free.** Read a signal in the render body and the component
  re-runs when it changes. This client already leans on that: 80 `use_signal`,
  3 `use_effect`, and **no `use_memo` at all**. Almost everything is recomputed
  on render, which is the idiomatic thing.
- **Invalidation — not free.** Dioxus will faithfully re-render a stale value.
  Nothing tells it `staged_placements` stopped meaning anything when `game`
  changed, because nothing in the code says the two are related.

So the change is to stop clearing and start matching. Store the composition
with its key, and filter it on read:

```rust
let live = composition().filter(|c| c.key == current_key(&selected_game(), &game()));
```

**Clearing is a push model**: every writer must participate, and one that does
not is a defect found in testing — which is precisely how we got here, ten
remembered calls and an eleventh site that forgot. **Matching is a pull
model**: nobody participates, and a writer that forgets *cannot* cause the
failure. `on_remove_game` sets the selection to `None` and is finished; the
staged tile disappears because it no longer matches, not because anyone
remembered it.

This is not a new idea in this codebase — it is already done once, inline:

```rust
if rack_order().len() != unordered_rack_tiles.len() {
    rack_order.set((0..unordered_rack_tiles.len()).collect());   // app.rs
}
```

Crude, and the right instinct. It is why `rack_order` is not on the list above.

What survives of the "one transition per invariant" idea is small, and that is
the point:

| kind | where it lives | who maintains it |
| --- | --- | --- |
| derived (`selected_id`, `can_stage_moves`, …) | not stored — computed on render | Dioxus |
| keyed (the composition) | stored with its key, filtered on read | Dioxus |
| side effects (token storage, socket teardown) | one function each | us, and there are about two |

**One consequence, taken deliberately.** Under matching a stale composition is
ignored, not destroyed — so leaving a game mid-turn to check another and coming
back restores the half-typed word. That is better behaviour than clearing it,
and it costs nothing. The bug fix and the small feature are the same change.

### What the composition is keyed on

The key is **the game and the seat**, and nothing else. A composition stays live
while its cells are still empty and its tiles are still in the seat's rack; it
is discarded when a tile is played in one of its cells or a tile it uses leaves
the rack (owner, 2026-08-29). Both are comparisons against the state the client
already holds, so nothing is stored or bumped to maintain them.
[*The composition is keyed by game and seat*](#the-composition-is-keyed-by-game-and-seat)
has the code.

`version` cannot serve. It moves for any change, including an opponent's chat
message, and keying on it would wipe a half-typed word every time somebody
typed in the panel. That is the same failure as clearing, arrived at from the
other direction. `turn` cannot serve either: undo takes it back, so a
composition keyed on turn 8 would match again after an undo and redo, against a
board that has moved on.

**Composing does not need the turn; submitting does.** A player can arrange a
word while waiting (#88), and the client offers Submit only on that seat's
turn. The server refuses a move out of turn whatever the client does.

`turn` still comes back as game state, separate from `version`: undo walks it,
the scoreless rule reads it and the player is shown it.

### How we will know the client is right

`e2e/tests/ui-state.spec.ts` states the rule from outside the client: **after
any event that changes which game is selected, every dependent pane matches the
new selection — including when the new selection is nothing.** Eight cases,
written against the intended behaviour rather than the current one. Six pass
today. Two fail, and they are the bug that prompted this section:

- *aborting a game clears the move being composed* — it does not; the staged
  tile survives onto a game that is over.
- *Remove after composing a move leaves nothing behind* — it does not; the
  staged tile is left drawing on an empty board with no game selected.

The Remove case was mutation-tested: deleting `game.set(None)` from
`on_remove_game` turns *Remove clears the board and rack* red with seven rack
tiles still on screen, so the passing tests are holding something up rather
than passing vacuously.

### This is delivered in Core Client UI

Raised as **#157**, which carries the reproduction and the two handlers it
lands in. Client-only: no server change, no API version move, no migration. The
staged tile left behind after a game is removed is a symptom of how state
changes are managed today, so the fix is this section's, the composition key,
delivered in #269 (Core Client UI) rather than as a separate release.[^d57] The
fault stays live until #269 ships, and the two `test.fixme` cases in
`e2e/tests/ui-state.spec.ts` are #269's acceptance tests.

## The composition is keyed by game and seat

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

**Both conditions compare against the state the DTO already carries** — the
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
cells free but may make the word illegal — a cross-word that no longer exists,
or a connection that has become something else.

| | |
| --- | --- |
| the cells are taken | the tiles come back to the rack. There is nowhere for them to be |
| the cells are free but the word is now illegal | **the tiles stay**, and the client says so |

The client already runs the rules engine — `client_rules.rs` validates and
scores before sending — so it can re-validate on every board change and mark the
word rather than silently dismantling it.

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

**`last_move_cells` is computed from the DTO's move list.** Once
`MoveRecordDto.description` becomes structured and the seat model changes, the
computation has to be checked rather than assumed — it is exactly the kind of
derived value that keeps working until it quietly does not, and nothing
currently asserts it.

**The staged state must survive board changes that do not touch its cells.**
That is the section above, and it interacts here: under the current *clear on
any change* behaviour the staged class simply disappears, which no test would
notice because disappearing is what it is supposed to do eventually.

## An enhancement this makes cheap, not part of the change

*"Just played"* means the **last move**. A player returning after several moves
sees only the most recent one highlighted, and what they actually want is
everything that happened while they were away.

The client knows the version it held before the update — `should_apply_update`
compares against it — so *"since the version I last held"* is derivable, **if
move records carry the version they happened at**:

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

Today the game carries an accumulator:

```rust
pub consecutive_scoreless_turns: u8,     // SCORELESS_TURN_LIMIT = 6
```

Replaced by a mark:

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
whose content is an earlier state — so every field is restored together, and a
derived quantity is right the moment its inputs are. An accumulator restored the
same way is also right; the difference appears if undo is ever implemented as
*applying an inverse* rather than restoring, where every accumulator needs its
own decrement and one that is forgotten is silently wrong. Deriving means there
is nothing to forget.

**The honest caveat**: as the design has undo — restore, not inverse — the
accumulator would also survive, so this is not a fix for a bug that exists. It
is choosing the shape that stays correct under a change of undo strategy, at a
cost of nothing.

**One thing it does not change.** *Scoreless* still means what it means today —
a pass, an exchange, or a placement scoring zero — and each is a turn, so
`turn` advances for all three. If any of those ever stops advancing the turn,
this derivation breaks silently, which is worth a test rather than a comment.

## The client

### Where the state lives

```rust
selected_game: Signal<Option<GameId>>,        // intent
cache:         Signal<Option<GameStateDto>>,  // what the server last said
composition:   Signal<Option<Composition>>,   // keyed, see below

pub struct Composition {
    pub key: CompositionKey,
    pub staged: Vec<StagedPlacementView>,
    pub cursor: Option<usize>,
    pub direction: Option<DirectionDto>,
    pub blank_letter: Option<String>,
    pub exchange: Option<HashSet<usize>>,
}

pub struct CompositionKey {
    pub game: GameId,
    pub seat: u8,             // no counter: see [*The composition is keyed by game and seat*](#the-composition-is-keyed-by-game-and-seat)
}
```

The seven composer signals become one optional struct with a key. `selected_id`
stops being read back out of the loaded DTO, which is what currently makes
*deselect* and *clear the panes* the same action.

### How updates are centralised

**One entry point for anything the server says.** `apply_game_update` is called
from **23 sites** in `app.rs` today; each is a place that could forget
something. It becomes one:

```rust
/// The only function that writes `cache`. Every response and every socket
/// frame arrives here.
fn on_server_state(&mut self, incoming: GameStateDto, because: Option<GameEventDto>) {
    if !should_apply(self.cache.peek().as_ref(), &incoming) { return; }  // as today
    self.cache.set(Some(incoming));
    // nothing else. No clearing, no cascade.
}
```

**And nothing clears the composition.** It is filtered on read:

```rust
fn live_composition(&self) -> Option<Composition> {
    let key = self.current_key()?;              // from selected_game + cache
    self.composition.peek().clone().filter(|c| c.key == key)
}
```

That is the design's *stop clearing, start matching*, made concrete: a writer
that forgets cannot cause the failure, because no writer participates.

**Two side effects stay explicit**, because they are not state: storing the
session token, and tearing down the socket. Everything else is derived on
render, which is what Dioxus does for free.

### What this does not become

Not a reducer over an event enum. Dioxus already propagates; a reducer would
sit on top of that and duplicate it, at the cost of rewriting a 5,500-line
component. The centralisation that is worth having is **one writer of the
server cache**, not one writer of everything.

[^d57]: Decision #443 (D57): fixed in #269 by the composition key.
