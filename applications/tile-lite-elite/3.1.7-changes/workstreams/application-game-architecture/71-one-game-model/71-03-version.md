# 71 Version

This file holds how one version is moved in one place: the argument, then the
session, the counters, the three categories of change, the message and the one
handler. It follows [`71-02-overview.md`](71-02-overview.md) and is followed by
[`71-04-seats.md`](71-04-seats.md).

## One version, moved in one place

Every change to a game goes through a single handler taking an enum:

```rust
pub enum GameMessage {
    Place { seat: u8, candidate: MoveCandidate },
    Pass { seat: u8 },
    Exchange { seat: u8, tiles: Vec<Tile> },
    Resign { seat: u8 },
    ForceResign { seat: u8 },
    TimeOut { seat: u8 },
    Abort,
    AdminForceEnd,
    SeatAdded { .. },
    SeatInvited { seat: u8, .. },
    InvitationPassed { seat: u8, to: PlayerId },
    InvitationAccepted { seat: u8, .. },
    InvitationDeclined { seat: u8 },
    SeatWithdrawn { seat: u8 },
    KeepRequested,
    UpdateUserDetails { player: PlayerId },
    Start,
    SeatsSwapped { a: u8, b: u8 },
    ChatPosted { player: PlayerId, body: String },
    Hide { seat: u8 },
    ReminderSent { seat: u8 },
}
```

`Start` deals the racks and drops the spent seats in one step. Undo and redo
join the enum with #272. Anything that changes what a client of the game could
be shown is a variant; there is no other way in.

The handler applies the change, advances the version, records the event and
publishes — in that order, in one place. Nothing else writes to a game.

**Two messages save without advancing the version.** `Hide` changes one
player's own list, not the game, and `ReminderSent` records that a reminder
went so it is not sent twice. Neither is anything another client is shown,
so each is saved under the same lock and nothing is published; neither counts
as activity for RET-3.

**A rejected message changes nothing.** The handler validates against the game
as it stands and applies only a message that will succeed, so a refused
exchange or placement leaves the racks and the bag as they were.

**A change has happened only once it is in the database** [^d69]. Under the
game's own lock the handler sets the game's *unsaved* flag, applies the change
in memory, saves it, and clears the flag; only then does it publish. The lock
keeps every other reader out until the flag clears. A save that fails with a
transient error is retried while the player waits, as the error's class
allows. If it still fails, the change did not happen: the player is told to
try again, and the game is reloaded from the database, which clears the flag.
If the reload fails too, the flag stays set and the game refuses every message
until a reload succeeds. Nothing is retried after the player has been
answered, because a save that succeeded later would make a move happen after
the player was told it had not. How many retries, how far apart, and what a
failing database raises beyond this game are #402's. The rules stay in Rust;
the database records the outcome and does not apply it.

That is the whole of the fix for the freshness problem. There is no obligation
to remember, because there is nowhere else to write. The current stopgap,
`announce_invitation_change`, is a convention with nothing enforcing it, and
conventions of that kind have already been forgotten twice.

**The version is a counter, not a description.** A game can return to a state
it already held — two seats swapped and swapped back — so anything
derived from state repeats and a client comparing with `>` silently ignores
the update. A timestamp is the same counter with worse properties. This also
constrains undo: undo cannot set the version back, it produces a *new, higher*
version whose content is an earlier state.

**Locking is per game.** `AppState.games` becomes `HashMap<String,
Arc<RwLock<GameSession>>>`, so the map lock guards insertion and removal and
each game has its own. One game's work stops blocking every other game, which is
what makes an engine search off the request path affordable. No lock is held
across an await on anything slow — an engine search, a database write of another
game. This project owns the map's shape; #408 designs its deadline index,
loading and eviction on top of it [^d70].

**Ordering does not need more than that**, and the reason is not that
out-of-turn messages commute. It is that there is no order to preserve.

An in-turn move cannot be made until the previous one has been applied and
published, because that is how a client learns it is its turn — so in-turn
moves arrive in an order the game itself created. Everything else is
independent action by separate clients, and which reaches the server first is
luck. **Any order the handler sees is a valid one**, because no other order
was ever the true one.

That is a weaker claim than commutativity and an easier one to keep: the
server owes nobody a reconstruction of what "really" happened first, since
nothing did.

The one place a real order exists is a single client sending two messages back
to back — a move, then resigning out of turn. Those were genuinely ordered by
the person, and two requests in flight together can be processed either way
round.

It costs little. Applied as sent, the move lands and then the seat goes.
Reversed, the seat goes first and the move is refused, because taking a turn
requires it to be your turn and that seat no longer has one. Either way the
player resigns and is ranked identically — a resigner's place depends on when
they left, not on what they scored. What differs is the board: one order plays
the tiles, the other returns them to the bag, and the other players draw from
a different bag as a result.

**Closed by the client waiting, and the server makes waiting worth doing.**
Every message is answered with the resulting state and its version, so a
client knows the change landed rather than merely that it was accepted. A
client that waits for that before sending its next message never has two in
flight, and the window above does not exist for it.

The same version then earns a second keep. The client sees each change twice —
once in the response to its own message, once in the update that goes to
everybody — and the second is discarded as already held, because it carries a
version no higher than the one just applied. Without that the client would
apply its own move twice, or need to recognise its own echo some other way.

**Every update goes to every client of its game.** Choosing recipients within a
game by who a change affects would be fragile and buys nothing — no change to a
game is invisible to everybody, and the cost of not choosing is a refetch
nobody needed. Each game has its own channel
([The engine](71-06-engine.md#the-engine)), so an update reaches no other game's
clients. Per-viewer concerns stay where they are: redaction decides what each
connection may see, and hiding a game is a flag on a seat.

## The session

```rust
pub struct GameSession {
    pub id: GameId,
    pub status: GameStatus,
    // …variant, language, board_layout, rules, state, bag, moves, messages,
    //   move_time_limit_seconds, turn_started_at are unchanged…
    pub seats: Vec<Seat>,                 // was `participants: Vec<ParticipantState>`
    pub current_seat: u8,
    pub turn: i64,                        // was `turn_number`; game state, walks back under undo
    pub version: i64,                     // every change, of any kind. Never decreases
    pub last_scoring_turn: i64,           // replaces `consecutive_scoreless_turns`
}
```

**Two counters, and only one of them is monotonic.**

| | what it counts | monotonic? |
| --- | --- | --- |
| `version` | every change a client can see, including chat and a rename | **yes, always** |
| `turn` | turns taken since the game started — **game state** | **no**: undo takes it back, redo returns it |

`turn` is game state: it is what undo walks, what the scoreless rule reads
(derived, in
[*Deriving beats accumulating*](71-07-client.md#deriving-beats-accumulating-and-the-scoreless-rule-is-the-case))
and what a player is shown (owner, 2026-08-29). Because it can return to a value
it already held, it keys nothing — the same reason the design gives for
`version` being a counter rather than a description.

## Which changes move which counter

| change | `version` | `turn` |
| --- | --- | --- |
| a word placed | ✓ | ✓ |
| a pass | ✓ | ✓ |
| an exchange | ✓ | ✓ |
| a chat message | ✓ | — |
| an invitation sent, accepted, declined | ✓ | — |
| a rename (`UpdateUserDetails`) | ✓ | — |
| a resignation, force-resign, timeout | ✓ | — |
| undo, redo | ✓ | ✓ back / ✓ forward |
| a seat added, removed, reordered, hidden | ✓ | — |

## Three categories of change

| category | what is in it | changed by |
| --- | --- | --- |
| **board** | the tiles played on the board, and nothing else | a placement; undo or redo of one |
| **the game** | the board, plus racks, scores, the turn, resignations and timeouts | everything above, plus pass, exchange, resign, force-resign, timeout, start, abort |
| **periphery** | chat messages | posting a message |

**The categories are not counters.** `version` moves for all three and answers
*is what I hold stale*. What a category decides is what to do, and that is a
property of the **event**: the envelope carries it —
`State { game, because: Option<GameEventDto> }` — so a client classifies the
event rather than comparing numbers:

| the client is told | it does |
| --- | --- |
| a **board** event | redraw the board; a staged word whose cells are now taken is discarded by [the occupancy check](71-07-client.md#the-composition-is-keyed-by-game-and-seat) |
| a **game** event | redraw the panes — racks, scores, whose turn. Notify if it is now this player's turn |
| a **periphery** event | a chat badge. Nothing else moves |
| **nothing** — a refetch or a reconnect | rebuild everything, because there is no event to classify |

**Exchange is the case that shows why.** It changes the game and not the board:
a staged word survives it, but the exchanging seat's rack does not, which is why
the rack is checked on its own
([*The composition is keyed by game and seat*](71-07-client.md#the-composition-is-keyed-by-game-and-seat)).

## The message

`GameMessage` is in the design and is defined in `game-wire`
([the interface layer](71-05-wire.md#the-interface-layer)). What it needs alongside it is the
result:

```rust
pub struct Applied {
    pub version: i64,          // the version this change produced
    pub event: GameEvent,      // what happened, structured — for the log and the client
    pub finished: bool,        // the caller settles ratings and stats on the edge
}

pub enum ApplyError {
    NotYourTurn { seat: u8 },
    SeatNotPlaying { seat: u8 },
    GameNotActive,
    GameNotWaiting,            // a seat message (invite, accept, claim) after the start
    IllegalMove(rules_shared::MoveError),
    Unknown(String),
}
```

**A bot's turn is noticed from the game's channel, not from `Applied`.** Every
change publishes the new state, which names the seat on turn, so a bot comes on
turn after a timeout, a force-resign or a seat leaving just as it does after a
move, and no caller of `apply` hands it anything
([the engine](71-06-engine.md#the-engine)).

## The one handler

```rust
impl GameSession {
    /// The only method that mutates a game. Validates, applies, advances the
    /// version, records the event — in that order.
    pub fn apply(&mut self, message: GameMessage, now: i64)
        -> Result<Applied, ApplyError>;
}
```

Everything else on `GameSession` becomes a reader. The methods that mutate
today — `maybe_run_engine_turn`, the action handlers, the invitation writers —
either disappear into `apply` or become callers of it.

**Enforced by visibility, not by discipline.** `seats`, `state`, `bag`,
`version` and `turn` become private to the module holding `apply`, with readers
for what the outside needs. A second writer then does not compile, which is the
difference between this and `announce_invitation_change`.

Two other ways in are named so that they are not mistaken for writers.
`GameSession::from_snapshot` builds a game from its stored row, which is how
persistence loads one; it validates the snapshot and changes nothing. Tests
build games through `GameSession::new` and `apply`, the public path, so a test
cannot reach a state the handler could not produce.

**What a failed save leaves** is nothing [^d69]. `GameSession` carries an
`unsaved: bool`, which `apply` sets. `events::publish`, under the game's write
lock, saves the change `apply` made and clears the flag, then publishes. A save
error that `ApiProblem::from_sqlx` classes as transient is retried in place,
within #402's bounds. One that still fails answers 503 with `Retry-After`,
replaces the session with `GameSession::from_snapshot` of the stored row, and
publishes nothing; a reader that finds `unsaved` set does the same reload before
it reads, and a game whose reload fails answers 503 to every message. The
database is the source of truth for #408.

[^d69]: Decision #469 (D69): the database holds what has happened. A failed
    save is retried by its error's class, then fails into a reload, under the
    game's lock, with an unsaved flag for any reader the failure leaves behind
    (owner, 2026-10-14). Database failure in general is #402's.

[^d70]: Decision #470 (D70): #71 Core owns the games map; #408 builds on it.
