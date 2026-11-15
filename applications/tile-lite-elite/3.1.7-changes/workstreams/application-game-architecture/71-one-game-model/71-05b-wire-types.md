# 71 The wire types

This is the second of two files on the wire, and it is read second. The first,
[`71-05-wire.md`](71-05-wire.md), holds the as-is, the model, the technologies
(traits and generic types, serde, WebAssembly, Cargo workspaces and axum), why
the DTOs are invisible and the interface layer, and defines the terms this file
uses: the DTO, the view and the interface layer. This file holds
the types that cross the wire: the seat, the game, structured descriptions, the
envelope and the error body. It is followed by
[`71-06-engine.md`](71-06-engine.md).

## The seat, on the wire

```rust
pub struct SeatDto {
    pub number: u8,
    pub player_id: Option<String>,
    pub state: SeatStateDto,          // mirrors SeatState, tagged
    pub rack: Option<SeatRackDto>,    // present only for Playing
    pub score: Option<i32>,
}

#[serde(tag = "kind", rename_all = "snake_case")]
pub enum SeatRackDto {
    Visible { tiles: RackDto },
    Hidden  { count: u8 },
}
```

`ParticipantDto` loses `display_name`, `invitation_status`, `invited_email`,
`resigned`, `rating_before`, `rating_after` and `current_rating`. The first four
are now the seat's state; the last three are facts about an event or a
projection, per the design.

## The game, on the wire

```rust
pub struct GameStateDto {
    pub id: String,
    pub version: i64,
    pub turn: i64,                    // new — game state, shown to the player
    pub status: GameStatus,
    // …variant, language, board_layout, current_seat, winner_seat,
    //   final_bonus_*, bag_count, move_time_limit_seconds, turn_started_at,
    //   board, moves, messages unchanged in shape…
    pub seats: Vec<SeatDto>,          // was `participants`
    pub players: Vec<PlayerRefDto>,   // new — the lookup, resolved at build
}

/// Everything about a person that a game refers to but does not own.
pub struct PlayerRefDto {
    pub id: String,
    pub display_name: String,
    pub current_rating: Option<f64>,
}
```

**`players` is what makes the lookup rule renderable.** The game holds IDs; the
client needs names; resolving at DTO-build time is what makes a rename arrive
without anything being copied into game data. It carries every player the game
mentions — seats, chat authors, event subjects — so a client never has a
dangling ID.

`racks: Vec<RackDto>` disappears from the top level: a rack belongs to a seat,
and hiding one is `SeatRackDto::Hidden`, not an empty rack.

## Every score change is a move record

The server decides every score, so the history carries every change to one
(owner, 2026-11-15). Today a placement records its `score_delta`, but the
end-of-game adjustment does not: `finish_game` (`game_state.rs`) takes each
seat's rack value off its score and gives the seat that went out the others'
total, recording only `final_bonus_seat` and `final_bonus_points`. So a seat's
moves do not sum to its score once a game is over.

At the end of a game the server adds one move record per seat whose score the
adjustment changes, with `move_type` `rack_adjustment` and the change as its
`score_delta`. They come from the event of the turn that ends the game: a
placement that goes out, or the pass or exchange that reaches the scoreless
limit, carries them in `ended`
([*Structured descriptions*](#structured-descriptions)). That turn is one
`Applied` and one logged event, so the log holds them. A seat's score is then
always the sum of its records' `score_delta`. These records are not turns, so
the scoreless count
([*Deriving beats accumulating*](71-07-client.md#deriving-beats-accumulating-and-the-scoreless-rule-is-the-case))
skips them, and so does any lookup of the last move, such as the "just played"
cells and the score change beside a seat. Playback steps through them like any
other record, so the final step shows the adjustment.

## Structured descriptions

`MoveRecordDto.description` and the prose in events are replaced:

```rust
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum GameEventDto {
    Placed    { seat: u8, main_word: String, score: i32, ended: Option<GameEnd> },
    Passed    { seat: u8, ended: Option<GameEnd> },
    Exchanged { seat: u8, count: u8, ended: Option<GameEnd> },
    Resigned      { seat: u8 },
    ForceResigned { seat: u8 },
    TimedOut      { seat: u8 },
    SeatInvited   { seat: u8 },
    InvitationPassed   { seat: u8 },
    InvitationAccepted { seat: u8 },
    InvitationDeclined { seat: u8 },
    SeatWithdrawn { seat: u8 },
    SeatAdded     { seat: u8 },
    SeatsSwapped  { a: u8, b: u8 },
    SeatHidden    { seat: u8 },
    ReminderSent  { seat: u8 },
    Started, Aborted, Finished { winner: Option<u8> },
    UserDetailsUpdated { player: String },
    ChatPosted    { seat: Option<u8>, player: String },
}

impl GameEventDto {
    /// Which of the three categories this change belongs to. The client reads
    /// it to decide what to redraw; nothing on the server branches on it.
    pub fn category(&self) -> ChangeCategory {
        use GameEventDto::*;
        match self {
            Placed { .. }                          => ChangeCategory::Board,
            ChatPosted { .. }                      => ChangeCategory::Periphery,
            _                                      => ChangeCategory::Game,
        }
    }
}

pub enum ChangeCategory { Board, Game, Periphery }

/// The end a turn caused: going out, or reaching the scoreless limit.
pub struct GameEnd { pub winner: Option<u8>, pub adjustments: Vec<RackAdjustment> }
pub struct RackAdjustment { pub seat: u8, pub score_delta: i32 }
```

**`Finished` is the event of a game that ends without a turn**, an
administrator's force-end after the start. A turn that ends the game says so in `ended`, and a
resignation or timeout that leaves one seat playing keeps its own event, so a
client reads the end from the state's `status`, not from one event.

**`ForceResigned` does not say who did it.** Every client of the game receives
the event, and which administrator acted is not theirs to know; the server's own
log records it.

**Undo and redo are classified by what they undo**, not by being undo —
undoing a placement is a board change, undoing a pass is a game change. That
falls out if the event carries what it reversed, which it must anyway for the
log to be readable.

Seat numbers and player IDs, not sentences. The client renders them, which is
the only way any of it is readable in a language other than the one the server
was written in — and this service already ships Spanish dictionaries.

## The envelope

```rust
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum ServerMessageDto {
    /// The whole state, redacted for this recipient. Sent on connect, on
    /// reconnect, and after every change.
    State { game: GameStateDto, because: Option<GameEventDto> },
    /// The account's full list of seats: the first message of a subscription
    /// to every seated game, then one whenever the list changes.
    Seats { seats: Vec<SeatRefDto> },
    /// The game no longer exists; nothing more follows for it.
    GameRemoved { game_id: String },
}

pub struct SeatRefDto { pub game_id: String, pub seat: u8 }
```

`ExternalLink` maps each `GameUpdate`
([the interface layer](71-05-wire.md#the-interface-layer)) to a
`ServerMessageDto` one to one: `Game` to `State`, `Seats` to `Seats`,
`GameRemoved` to `GameRemoved`. A refused submission is an HTTP error
(`ErrorDto`, next), so the envelope has no variant for it. Which socket carries
`Seats` for an external harness, one per account or a separate route, is #10's.

**Whole state, never a diff.** A diff needs the client to hold the prior version
and needs the server to know which one it holds; the state is small, and the
client's version comparison, `should_apply_update`
([as-is](71-07-client.md#worth-keeping)), already discards what it has.
`because` is what the log records and what a client shows in the move list —
it is not applied.

## The error body, shared by every endpoint

One shape for every error any endpoint returns, designed here in Core because
Core rewrites the contract anyway, so it changes once (#380 R8).[^d65] Today's
`ApiError` body, `{ message, blocking_games }`, becomes one case of it.

```rust
pub struct ErrorDto {
    pub code: ErrorCode,                 // stable and machine-readable; the message may change
    pub message: String,                 // for a person, never parsed
    pub correlation_id: Option<String>,  // #402 fills it; Core only reserves the field
    pub detail: Option<ErrorDetail>,     // e.g. the games blocking a deletion
}
```

`ApplyError` maps onto `code`, so a client tells a stale submission from an
illegal move without reading prose. Every response carries the same headers,
the API version among them, and #402 adds the correlation ID to them.

[^d65]: Decision #465 (D65): #71 Core designs the shared error body and
    response header.
