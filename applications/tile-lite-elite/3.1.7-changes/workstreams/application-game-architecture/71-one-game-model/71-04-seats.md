# 71 Seats

This file holds seat state: what is worth keeping from today and what to move
away from, the model, the enum technology as the seat uses it, how a seat is
filled, spent seats and the start, bots as users, the principles for addresses
and invitations and how the seat carries them, the seat as written and access.
It follows [`71-03-version.md`](71-03-version.md) and is followed by
[`71-05-wire.md`](71-05-wire.md).

## As-is

### Worth keeping

- **One authorisation check.** `resolve_viewer_access` (`game_state.rs`) is
  used by every handler that returns a `GameStateDto` and by the `game_events`
  WebSocket, so the rule cannot drift between them. It checks a seat before the
  creator, so a creator who also holds a seat gets the more permissive tier.
- **`game_invitations` is the record of who was asked.** It keeps each
  invitation's status, and accept and decline are addressed by its ID, which
  email links carry (`persistence.rs`, `app/invitations.rs`). DEL-2 reads it.
- **Two per-seat fields.** `removed_by_player` hides a finished game from one
  player's list without touching anyone else's view, and `reminder_sent_turn`
  says whether this turn's time-running-low email is still owed
  (`ParticipantState`, `game_state.rs`).
- **Unknown names are refused when a seat is added.** `add_seat_to_game`
  (`app/roster.rs`) fails on an unregistered name, as creating a game does.
- **A named seat takes the invitee's own spelling** of the name, because names
  match without regard to case (`app/roster.rs`).

### To move away from

- **Seat state is derived from history.** `attach_invitation_status`
  (`game_state.rs`) folds a seat's status out of its most recent
  `game_invitations` row on every read, as `NotSent`, `Pending` or `Rejected`,
  for unclaimed seats of a waiting game only
  (`game_dto_with_invitation_status`, `app/common.rs`). The seat holds nothing,
  so writing a row changes what every tab shows and moves no version.
- **The domain seat is flat.** `ParticipantState` has 11 fields, among them
  `resigned: bool` and a `rack: Rack` that every seat carries, whatever its
  state, with `kind` and `engine_id` marking a bot.
- **The domain seat has no field for invitation status.** `ParticipantDto`
  carries `invitation_status` and `ParticipantState` does not, so
  `DTO → domain → DTO` loses it (a DTO is a data transfer object, defined in
  [*The model*](71-05-wire.md#the-model) of the wire).
- **The list of registered players is currently not appearing**, which is its
  own defect and not this design's: the client reads it from `search_players`
  (`app.rs`), which calls `GET /players/search` (`search_players`,
  `app/auth.rs`). The design neither causes it nor fixes it.
- **Names are copied.** `display_name` is stored on the seat, and
  `invited_email` on a seat created with `SeatClaim::Email`, until claimed.
- **`ViewerAccess` holds one seat.** `Participant { seat_number }` comes from
  `.find(...)` in `resolve_viewer_access`, so a player holding two seats has
  one of their own racks hidden, and `Creator` is a tier below `Participant`.

## The model

A *seat* is one place at a game, and its *seat state* is where that place has
got to. The state is a field of the seat, one value of an enum that carries what
that state has, and every other seat field is true of every seat in every state.
The game has four states of its own (not started, active, finished, aborted)
and every seat has its own lifecycle, running independently, so a roster can
hold a claimed seat, one asked and waiting, one asked and refused and one never
asked, all at once. Nothing may assume a game is in a single invitation phase.

An *invitation* says how a seat is to be filled: by name, by email or open. It
is fixed when the seat is created. A seat is *spent* when it is declined or
withdrawn: both are terminal, and its invitation is never sent again. A seat is
*pending* while it is `Invited`, because it might still be filled.

A seat's invitation state moves onto the seat. `game_invitations` remains the
record of who was asked and when, because accept and decline are addressed by
invitation ID and email links carry it, but the seat carries where it has got
to. Altering a seat is then altering the game, which is why the version moves.

```rust
/// How this seat is to be filled. `None` for the creator's own seat and for a
/// bot's — they are filled on the spot and never invited.
pub enum Invitation {
    ByName  { player: PlayerId },
    ByEmail { email: String },
    Open,
}

pub enum SeatState {
    Invited   { id: InvitationId, addressee: Option<PlayerId> }, // None until a link or a verified address names one
    Claimed   { player: PlayerId },
    Declined  { player: PlayerId },                             // terminal
    Withdrawn { player: Option<PlayerId> },                     // terminal; None if withdrawn before anyone was named
    Playing   { player: PlayerId, rack: SeatRack, score: i32 },
    Departed  { player: PlayerId, score: i32, how: Departure },
}

pub enum Departure { Resigned, ForceResigned, TimedOut }

pub enum SeatRack {
    Visible(Rack),   // the viewer's own seat, or the server's own view
    Hidden(u8),      // everyone else's: how many tiles, not which
}
```

## Rust enums

The enum technology, with *making invalid states unrepresentable*, is explained
in [`71-03-version.md`](71-03-version.md#the-enum-technology), the first file to
rely on it.

### How the seat uses enums

`SeatState` is the enum, and a seat's `state` field holds it. The states that
cannot have a thing do not carry it:

- `Departed` has no rack, because TIME-3 returns the tiles to the bag.
- `Claimed` has neither rack nor score, because the deal has not happened.

Three smaller enums say the same for a choice: `Invitation` how a seat is to be
filled, `Departure` how a player left and `SeatRack` whether the rack is
visible or only counted. `Option` says whether a seat has an invitation at all
(*`None` starts at `Claimed`*, in [*How a seat is filled*](#how-a-seat-is-filled)) and whether a withdrawn seat ever had a
player.

A caller reads the state with a `match`, so adding a state makes the compiler
list the places that must decide what to do with it. The lifecycle is drawn in
[the functional views](71-functional.md#lifecycles).

## How a seat is filled

**One lifecycle, three ways of filling a seat.** Accept and decline are the same
transitions whether the seat was aimed at a player, at an address or at anyone.
Only the mechanics differ, which are what adding the seat sends and who is
allowed to accept, so the difference is a field the states are read against and
not a set of states. States split by how the seat is filled, such as
`UnsentToName`, `UnsentToEmail` and `UnsentOpen`, would be three parallel lanes
that never touch, which is a dimension to factor out. What looks like it
justifies separate states is a predicate on the field:

| Question | Is a |
| --- | --- |
| who may accept — that player, whoever holds the link, anyone | guard |
| which invitations appear in your list — `ByName { you }` | query |
| which may be re-sent — `ByEmail` | guard |
| declining an open seat, which nobody was asked for | guard |

None of them is a transition. The test for a separate state is whether the
legal *moves* differ, and they do not.

**Immutable is what makes the field safe.** It is not a second copy of what the
state holds, free to disagree with it: fixed at creation, the seat's purpose is
settled when the seat exists, and a seat aimed somewhere else is a different
seat, which is what GAME-9's spent seat already means.

So **a name is resolved to a player when the seat is added**, and not when the
invitation is sent. Staging a seat for somebody who does not exist fails there,
not two clicks later. `create_game` resolves every named invitee up front,
*"so a typo'd name fails cleanly instead of leaving a half-built game
behind"*, and `add_seat_to_game` refuses an unknown name the same way. The
resolved player is kept on the seat and is not resolved again when the
invitation is sent.

The client picking the name from a list of registered players is where a typo
is caught, which is help and not enforcement. The server resolves the name
itself, because a client is not the only thing that can call it, and an
unresolvable name is refused wherever it comes from.

**`None` starts at `Claimed`.** The creator's own seat and a bot's are filled
on the spot, so they have no invitation and never pass through `Invited`. The
`Option` says so once, instead of every caller checking for a seat kind.

**Every seat has a kind.** A seat is added as one of five kinds (the creator's
own, a bot, by name, by email or open), and a human seat without one is refused
outright: *"A human seat needs a claim: named, open, or email."*

**Adding an invited seat sends its invitation** (owner, 2026-10-14). The
client asks for a seat of a kind (by name, by email or open) and the server
creates the invitation, sends it, and returns the game with the seat already
`Invited`, carrying its invitation ID. No seat waits unsent, so there is no
state for it and no separate Send. A creator who adds the wrong seat withdraws
it, as with any invitation.

## Spent seats, and the start

**A spent seat is spent** (GAME-9, owner, 2026-10-15). Declining and
withdrawing are both terminal, whoever withdraws: the creator, any seat
including their own (GAME-8), or the player holding it. The seat keeps the
name of whoever said no or walked away, if anybody had, and its invitation is
never sent again. A creator who wants to invite anybody, the same person
included, adds a new seat.

That is what lets `Claimed` carry nothing but the player. Nothing goes back, so
nothing has to be remembered, and **the pre-start lifecycle is acyclic**: a seat
only ever moves forward.

It also keeps what a creator wants to see. A seat reading "Bob declined" or
"Carol withdrew" says what happened; one that quietly reverted would not.

**Starting clears the spent seats.** A game begins with only the seats that
are going to play, so `Declined` and `Withdrawn` are dropped rather than
blocking the start or waiting for the creator to tidy them away. Adding a
replacement stays optional: a creator short of a player can add a seat and
invite somebody, or start with fewer. Before the start the client lets the
creator hide spent seats, so only the seats still in play show; that is a view
choice, and the service keeps them until the start drops them (owner,
2026-10-14). `Declined` and `Withdrawn` are drawn inside **Game: Not Started**,
and they exist only there.

That makes `can_start` a statement about what is still *pending* rather than
about every seat: no seat may be `Invited`, and everything that is not spent
must be `Claimed`. One is never coming and the other might.

**Start is the last moment renumbering is free.** Dropping seats renumbers the
ones that remain, and seat numbers are the turn order. Before the start no
move has been recorded against a seat number, so nothing refers to the old
ones; a moment later the log does, and the same tidy-up would be a rewrite.

It follows that **a game must still have two seats left** (GAME-3), checked
when it is created and again at start, after the spent seats are dropped. A
roster whose seats turned out to be spent, down to one or none, cannot start.
GAME-3 is what lets GAME-2's finish condition (at most one seat still playing)
read one remaining seat as everybody else having left.

Who declined is not lost. `game_invitations` keeps the record of who was asked
and what they said, which is what DEL-2 reads: an account that turned down a
game still cannot be deleted while that game exists, even though the seat has
gone. `Declined`, `Withdrawn` and every state from `Claimed` on name a player.
`Invitation::ByEmail` names no account at all, so nothing is protected, and the
link keeps working whether or not anybody has registered.

**Whose turn it is stays an integer on the game**, a flag on no seat. Marking
the seat would mean every seat changing on every turn, all of them having to
agree, and no fact recorded that `current_seat` does not already hold. "Is it
mine" is a comparison.

A game exposes an iterator over its seats, and the questions callers actually
ask are answered from it:

```rust
game.seats()                                   // Iterator<Item = &Seat>
game.any_seat_is(Invited)                      // → still waiting on someone
game.count_of(Declined)
game.can_start()                               // nothing pending, a seat left
```

## Bots are users

A bot has an account like anyone else, and a seat it holds
is `Claimed` then `Playing`, so `SeatKind::Engine`, `engine_id` on the seat,
and any separate "engine is ready" state all go. What engine a bot runs is a
fact about that user, not about the seat, and `can_start` treats every seat
alike. Every caller would otherwise write `kind == Human && player_id.is_none()`
and remember that engines are exempt.

One account per engine, so a rating stays what it is now: today the rated
subject is the `engine_id`, and "Greedy 1" and "Greedy 2" are seat labels
sharing one rating row. Keeping one account per engine preserves that meaning
exactly, and makes a bot-versus-bot game one account holding two seats, the
same shape as a person doing it, per GAME-4, rather than a case of its own.
`player_ratings.subject_kind` then has one kind and can go.

## The lifecycles are in the functional views

The state machine for the game and its seats, and how its arrows line up with
the messages in [*The message*](71-03-version.md#the-message), are in
[`71-functional.md`](71-functional.md),
[*Lifecycles*](71-functional.md#lifecycles), where the journeys are checked
against them.[^d71]

## Addresses and invitations

### Principles

There are many journeys through addresses and invitations, so each one, and
each rule, is checked against these principles rather than argued case by
case. The owner confirmed them on 2026-10-14 under D72.[^d72]

1. **No address to account, nor account to address.** Nothing anyone can do
   turns an address into a user ID, or a user ID into an address. The creator
   sees an ID only once the invitation is accepted, and inviting, recovering
   an account and a closed link all answer the same whether or not the address
   belongs to anybody. The Open Worldwide Application Security Project (OWASP)
   calls this preventing account enumeration.
2. **One holder at a time, and no past.** An address belongs to at most one
   account at a time, and nothing records who held it before.
3. **The inbox is the proof.** Only verifying an address, which proves you
   read its inbox, grants anything tied to it. A pending address grants
   nothing and blocks nobody: several accounts may hold it pending, and the
   first to verify keeps it.
4. **A link is a bearer credential.** It works once, the first claim wins, and
   following it never verifies an address.
5. **One crossing.** Verification is the only event that carries the account
   side into the invitation side.
6. **Once named, an invitation stays with its player.** Nothing that happens to
   an address moves it afterwards.
7. **Nothing is accepted on a player's behalf.**
8. **Every race has one winner, decided in one place.** Every change to an
   invitation goes through its game's handler, under the game's lock.
9. **Nothing waits for ever.** An invitation never outlives its waiting game
   (RET-3) and a pending address blocks nobody, so nothing one person holds
   open can block another indefinitely.
10. **The server decides.** Every rule holds at the REST API; a client only
    presents what the API allows.

What they settle. The owner answered the invitation rows on 2026-10-14; the
two #439 rows and the DEL-2 row are still open.

| Point | Principle | Answer |
| --- | --- | --- |
| a link's invitation, once passed: accepted or held | 7 | held for acceptance |
| what a closed link's page shows | 1 | the inviter and that it is closed, never who took it |
| who sees the invited address | 1 | the creator only |
| inviting your own address, or a seated player's | 1 | no special case, since a different answer would reveal the holder |
| recovery answering the same whether or not the address is known (#439) | 1 | the same answer |
| registering a held address says "not available" (#439) | 1 | an exception as it stands: it reveals that an address is held, though not by whom. The usual cure is to answer "check your email" every time and tell the holder by email instead |
| a spent link followed by the account it passed to | 6 | it opens the invitation, since that account is already the named player |
| who can see which account claimed a link | 1 | support, to answer someone surprised that their address's invitation was taken; never the creator or other players |
| closing an account while a passed invitation names it, refused by DEL-2 | 9 | acceptable: RET-3 ends it, and the player can decline |
| how the verifier hears of a passed invitation | 3 | by email linking to the application, not the invitation, when they are not signed in (INV-2) |

### Who may accept

**Who may accept is settled by the address, then by the link.**[^d72] The rules
are INV-1 to INV-8 in
[Tile Lite Elite's rules](https://github.com/delphside/tile-lite-elite/blob/main/docs/4.1.0-rules.md#invitations-by-address),
and the address's two state machines, with a table of how each drives the other,
are in
[*An email and its invitations*](71-functional.md#an-email-and-its-invitations).
This is how the seat carries them.

- **At send.** When the address is one an account has verified and still
  holds, the seat is invited to that player,
  `Invited { addressee: Some(player) }`, and the email is a notification
  linking to the application, not the invitation (INV-1). Otherwise the
  addressee is `None` and the email carries the link (INV-2).
- **A link followed.** The person signs in, or registers and activates, and
  only then does the server apply `InvitationPassed { seat, to }` for that
  account. The seat stays `Invited`, now with an addressee, and the link is
  spent, because a link can only claim a seat whose addressee is `None`
  (INV-2, INV-3). The game's own lock makes the claim atomic: of two at once,
  the second finds an addressee and is refused with `InvitationNotAvailable`.
- **An address verified.** The account service finds the open invitations to
  that address with no addressee and applies `InvitationPassed` to each game in
  turn, through the same handler, so a link claimed a moment earlier wins and
  the pass is a no-op for that seat (INV-2, INV-3).
- **Accepting.** A seat with an addressee can be accepted or declined only by
  that player, and passing never accepts for them (INV-5). `Open` seats are
  unchanged: anyone may claim one.

**The addressee is the creator's blind spot until it accepts.** The creator
sees the address they typed; other players see an invited seat; the event for
`InvitationPassed` names the seat and nobody else. Inviting answers the same
whether the address matched a player or not, the creator's own address and a
seated player's included (INV-6). Support can see the addressee, so someone
surprised that an invitation to their address was taken can raise it with the
creator and then with support.

**A spent link says so, and shows nothing else** (INV-8). Its page shows who
sent the invitation and that it is no longer available. Followed by the account
it passed to, signed in, it opens the invitation instead, which covers the
player whose verification passed it before they used the link.

**Withdrawing an invitation spends its seat** with `SeatWithdrawn`, which
closes the invitation and kills its link; RET-3 does the same for a whole game
(INV-7). The start drops the spent seats, and until then none is removed.

**An address change rebinds nothing.** Once a seat has an addressee it is
about a player, not an address. If the addressee later changes address the
invitation stays theirs, and whoever takes the old address gets nothing.

**Signing in as the wrong one of your own accounts passes the invitation to
that account.** That is the price of INV-2 passing at sign-in rather than at
acceptance, and it is accepted: the account is still the person's, and they
can decline there.

**Every rule holds at the API.** Third-party clients are allowed, so nothing
here lives in a client; a client can only offer what the API permits.

**What #439 owns.** Verifying, uniqueness, pending addresses and the migration
that takes existing addresses as verified are #439's. #71 needs one query from
it, the account that has verified an address and still holds it, and one event,
an address verified. Until #439 delivers no address is verified, so every
emailed invitation is a link and the design works unchanged.

## The seat

`ParticipantState` is replaced. The fields that survive do so because they are
true of every seat in every state; the rest move into the state that owns them.

```rust
pub struct Seat {
    pub number: u8,
    pub player: Option<PlayerId>,         // resolved when the seat is created; a bot is a player
    pub invitation: Option<Invitation>,   // fixed at creation; None for own seat and bots
    pub state: SeatState,
    pub hidden_by_player: bool,           // "removed from my list" — per seat, not per game
    pub reminder_sent_turn: Option<i64>,
}
```

`display_name` is gone, because a name is a lookup. `resigned: bool` is gone:
`SeatState::Departed { how: Departure::Resigned, .. }` says it, and says which
of the three ways it happened. `score` and `rack` move inside the states that
have them, which is what stops a `Claimed` seat carrying a rack it cannot have.
`kind` and `engine` are gone: a bot is a user account, and the account says
which engine it runs ([*Bots are users*](#bots-are-users)).

`SeatState`, `Invitation`, `Departure` and `SeatRack` are the types in
[the model](#the-model).

## Access

```rust
pub struct ViewerAccess {
    pub player: Option<PlayerId>,
    pub seats: Vec<u8>,        // every seat this account holds
    pub is_creator: bool,
}
```

**Access is a set of seats, not a tier.** GAME-4 says a player may hold more
than one seat, so what a viewer may see is the union of what their seats may
see, plus whether they created the game. `Creator` stops being a rank below
participant: an account can be the creator *and* hold two seats.

Three units, easily blurred and worth keeping apart. A *seat* plays: it holds
tiles, takes turns, is invited. An *account* is entitled: what may be seen is a
function of which seats it holds. A *connection* is addressed: it is where a
message is delivered. An account may have several connections and they all see
the same thing, so a client is always an account, never a seat.

A person who wants to play twice in practice registers two accounts and runs
two clients, which keeps the seats genuinely independent. The multi-seat path
exists chiefly because a bot account holds every seat its engine plays. Somebody
who does hold two seats gets view-switching without it being built: each client
chooses which seat to show, so two windows on one account can show one seat
each. How the wire redacts for a viewer is in
[*DTOs are invisible*](71-05-wire.md#dtos-are-invisible) of the wire.

[^d72]: Decision #479 (D72): how an emailed invitation behaves once an address
    identifies one account. It supersedes D59 (#445).

[^d71]: Decision #472 (D71): one file per stage, functional views before the
    technical design; work packages scoped as sections of this design, and a
    test file per package fitted to the overall test approach.
