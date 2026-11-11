# 71 Seats

This file holds seat state: why it belongs to the seat, what each state carries, the principles for addresses and invitations, how the seat carries them, the seat as written, and access. The design as a whole, and the list of its files, is in [`71-02-overview.md`](71-02-overview.md).

## Seat state belongs to the seat

A seat's invitation state moves onto the seat. `game_invitations` remains the
record of who was asked and when — accept and decline are addressed by
invitation id, and email links carry it — but the seat carries where it has
got to.

That single change removes the reason the version does not move: altering a
seat is altering the game.

**The whole state is composite.** The game has four states of its own — not
started, active, finished, aborted — and every seat has its own lifecycle,
running independently. A roster can hold a claimed seat, one asked and
waiting, one asked and refused, and one never asked, all at once. Nothing may
assume a game is in a single "invitation phase".

```rust
pub struct Seat {
    pub number: u8,
    pub player: Option<PlayerId>,        // resolved when the seat is created; a name is looked up, never stored
    pub invitation: Option<Invitation>,  // fixed when the seat is created
    pub state: SeatState,
}

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
    Visible(Rack),   // the viewer's own seat
    Hidden(u8),      // everyone else's: how many tiles, not which
}
```

**One lifecycle, three ways of filling a seat.** Accept and decline are the
same transitions whether the seat was aimed at a player, at an address, or at
anyone. Only the mechanics differ — what adding the seat sends, and who is
allowed to accept — so the difference is a field the states are read against, not a
set of states.

An earlier draft of this design split them: `UnsentToName → InvitedByName`,
`UnsentToEmail → InvitedByEmail`, `UnsentOpen → Open`. Drawn out, those are
three parallel lanes that never touch, which is the signature of a dimension
that wants factoring out rather than three lifecycles. The three things that
looked like they justified separate states are all predicates on the field:

| | is a |
| --- | --- |
| who may accept — that player, whoever holds the link, anyone | guard |
| which invitations appear in your list — `ByName { you }` | query |
| which may be re-sent — `ByEmail` | guard |
| declining an open seat, which nobody was asked for | guard |

None of them is a transition. The test for a separate state is whether the
legal *moves* differ, and they do not.

**Immutable is what makes the field safe.** The objection to a field like this
before was that it would be a second copy of what the state already held, free
to disagree with it. Fixed at creation it cannot: the seat's purpose is
settled when the seat exists, and a seat aimed somewhere else is a different
seat — which is exactly what "a spent seat is spent" already established.

That does mean **a name is resolved to a player when the seat is added**,
rather than when the invitation is sent. Better feedback anyway: staging a
seat for somebody who does not exist should fail there, not two clicks later.
`create_game` already does this — it resolves every named invitee up front,
*"so a typo'd name fails cleanly instead of leaving a half-built game
behind"* — and `add_seat_to_game` now refuses an unknown name the same way.
What changes is that the resolved player is kept on the seat, rather than
resolved again when the invitation is sent.

The client picking the name from a list of registered players is what stops
anybody meeting that error in normal use, and it is where a typo should be
caught — but it is help, not enforcement. The server resolves the name itself,
because a client is not the only thing that can call it, and an unresolvable
name has to be refused wherever it comes from. The list is currently not
appearing, which is its own defect rather than a reason to soften this.

**`None` starts at `Claimed`.** The creator's own seat and a bot's are filled
on the spot, so they have no invitation and never pass through `Invited`. The
`Option` says so once, instead of every caller checking for a seat kind.

### What each state carries, and what it cannot

- `Departed` has no rack, because TIME-3 returns the tiles to the bag.
- `Claimed` has neither rack nor score, because the deal has not happened.

**There is no empty seat.** A seat is added as one of five kinds — the
creator's own, a bot, by name, by email, or open — and a human seat without
one is refused outright: *"A human seat needs a claim: named, open, or
email."*

**Adding an invited seat sends its invitation** (owner, 2026-10-14). The
client asks for a seat of a kind — by name, by email or open — and the server
creates the invitation, sends it, and returns the game with the seat already
`Invited`, carrying its invitation id. No seat waits unsent, so there is no
state for it and no separate Send. A creator who adds the wrong seat withdraws
it, as with any invitation. Today's staged seat, whose Send changed its status
without moving the game's version, goes with it.

### Principles for addresses and invitations

There are many journeys through addresses and invitations, so each one, and
each rule, is checked against these principles rather than argued case by
case. The owner confirmed them on 2026-10-14 under D72.[^d72]

1. **No address to account, nor account to address.** Nothing anyone can do
   turns an address into a user id, or a user id into an address. The creator
   sees an id only once the invitation is accepted, and inviting, recovering
   an account and a closed link all answer the same whether or not the address
   belongs to anybody. This is what OWASP calls preventing account
   enumeration.
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

What they settle. The owner answered the invitation rows on 2026-10-14; the two #439 rows and the DEL-2 row are still open.

| point | principle | answer |
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

### How the seat carries them

**Who may accept is settled by the address, then by the link.**[^d72] The
rules are INV-1 to INV-8 in `docs/1.0`, and the address's two state machines,
with a table of how each drives the other, are in `71-functional.md`, *An
address and its invitations*. This is how the seat carries them.

- **At send.** When the address is one an account has verified and still
  holds, the seat is invited to that player, `Invited { addressee:
  Some(player) }`, and the email is a notification linking to the application, not the invitation (INV-1).
  Otherwise the addressee is `None` and the email carries the link (INV-2).
- **A link followed.** The person signs in, or registers and activates, and
  only then does the server apply `InvitationPassed { seat, to }` for that
  account. The seat stays `Invited`, now with an addressee, and the link is
  spent, because a link can only claim a seat whose addressee is `None`
  (INV-3). The game's own lock makes the claim atomic: of two at once, the
  second finds an addressee and is refused with `InvitationNotAvailable`.
- **An address verified.** The account service finds the open invitations to
  that address with no addressee and applies `InvitationPassed` to each game in
  turn, through the same handler, so a link claimed a moment earlier wins and
  the pass is a no-op for that seat (INV-4).
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

**A spent link says so, and nothing more** (INV-8). Its page shows who sent the
invitation and that it is no longer available. Followed by the account it
passed to, signed in, it opens the invitation instead, which covers the player
whose verification passed it before they used the link.

**Withdrawing an invitation spends its seat** with `SeatWithdrawn`, which
closes the invitation and kills its link; RET-3 does the same for a whole game
(INV-7). No seat is removed before the start, which drops the spent ones.

**An address change rebinds nothing.** Once a seat has an addressee it is
about a player, not an address. If the addressee later changes address the
invitation stays theirs, and whoever takes the old address gets nothing.

**Signing in as the wrong one of your own accounts passes the invitation to
that account.** That is the price of INV-2 passing at sign-in rather than at
acceptance, and it is accepted: the account is still the person's, and they
can decline there.

**Every rule holds at the API.** Third-party clients are allowed, so nothing
here lives in a client; a client can only offer what the API permits.

**What #439 owns.** Verifying, uniqueness, pending addresses,
and the migration that takes existing addresses as verified are #439's. #71
needs one query from it, the account that has verified an address and still
holds it, and one event, an address verified. Until #439 delivers no address is
verified, so every emailed invitation is a link and the design works unchanged.

**A spent seat is spent** (GAME-9, owner, 2026-10-15). Declining and
withdrawing are both terminal, whoever withdraws: the creator, any seat
including their own (GAME-8), or the player holding it. The seat keeps the
name of whoever said no or walked away, if anybody had, and its invitation is
never sent again. A creator who wants to invite anybody, the same person
included, adds a new seat.

That is what lets `Claimed` carry nothing but the player. Three earlier
attempts at this section were answers to "where does a withdrawn seat go back
to" — an invitation id on `Claimed`, a `claim` field, a `Filled` enum. The
question was wrong. Nothing goes back, so nothing has to be remembered, and
**the pre-start lifecycle is acyclic**: a seat only ever moves forward.

It also keeps what a creator wants to see. A seat reading "Bob declined" or
"Carol withdrew" says what happened; one that quietly reverted does
not.

**Starting clears the spent seats.** A game begins with only the seats that
are going to play, so `Declined` and `Withdrawn` are dropped rather than
blocking the start or waiting for the creator to tidy them away. Adding a
replacement stays optional: a creator short of a player can add a seat and
invite somebody, or start with fewer. Before the start the client lets the
creator hide spent seats, so only the seats still in play show; that is a view
choice, and the service keeps them until the start drops them (owner,
2026-10-14).

That makes `can_start` a statement about what is still *pending* rather than
about every seat: no seat may be `Invited`, because it might
still be filled, and everything that is not spent must be `Claimed`. Spent and
pending stop being the same thing — one is never coming, the other might.

**Start is the last moment renumbering is free.** Dropping seats renumbers the
ones that remain, and seat numbers are the turn order. Before the start no
move has been recorded against a seat number, so nothing refers to the old
ones; a moment later the log does, and the same tidy-up would be a rewrite.

It follows that **a game must still have two seats left** (GAME-3), checked
when it is created and again at start, after the spent seats are dropped. A
roster whose seats turned out to be spent, down to one or none, cannot start.
GAME-3 is what lets GAME-2's finish condition — at most one seat still playing —
read one remaining seat as everybody else having left.

Who declined is not lost. `game_invitations` keeps the record of who was asked
and what they said, which is what DEL-2 reads: an account that turned down a
game still cannot be deleted while that game exists, even though the seat has
gone.

And the diagram stops approximating. `Declined` and `Withdrawn` are drawn
inside **Game: Not Started**, which was true of where they can be *reached*;
with this rule it is true of where they can *exist*.

**Whose turn it is stays an integer on the game**, not a flag on the seat.
Marking the seat would mean every seat changing on every turn, all of them
having to agree, and no fact recorded that `current_seat` does not already
hold. "Is it mine" is a comparison.

**This all matters for DEL-2**, which blocks deleting an account a game still
refers to. `Declined`, `Withdrawn` and every state from `Claimed` on name a
player. `Invitation::ByEmail` names no account at all, which is correct: there
is nothing to protect, and the link keeps working whether or not anybody has
registered.

A game exposes an iterator over its seats, and the questions callers actually
ask are answered from it:

```rust
game.seats()                                   // Iterator<Item = &Seat>
game.any_seat_is(Invited)                      // → still waiting on someone
game.count_of(Declined)
game.can_start()                               // nothing pending, a seat left
```

**Bots are users.** A bot has an account like anyone else, and a seat it holds
is `Claimed` then `Playing` — so `SeatKind::Engine`, `engine_id` on the seat,
and any separate "engine is ready" state all go. What engine a bot runs is a
fact about that user, not about the seat, and `can_start` stops special-casing
them.

One account per engine, so a rating stays what it is now: today the rated
subject is the `engine_id`, and "Greedy 1" and "Greedy 2" are seat labels
sharing one rating row. Keeping one account per engine preserves that meaning
exactly, and makes a bot-versus-bot game one account holding two seats — the
same shape as a person doing it, per GAME-4, rather than a case of its own.
`player_ratings.subject_kind` then has one kind and can go.

Without that, every caller writes `kind == Human && player_id.is_none()` and
remembers that engines are exempt.

### The lifecycles are in the functional views

The state machine for the game and its seats, and how its arrows line up with
the messages above, are in [`71-functional.md`](71-functional.md),
*Lifecycles*, where the journeys are checked against them.[^d71]

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

`display_name` is gone — that is the lookup rule. `resigned: bool` is gone:
`SeatState::Departed { how: Departure::Resigned, .. }` says it, and says which
of the three ways it happened. `score` and `rack` move inside the states that
have them, which is what stops a `Claimed` seat carrying a rack it cannot have.
`kind` and `engine` are gone: a bot is a user account, and the account says
which engine it runs (*Bots are users* in the design).

`SeatState`, `Invitation`, `Departure` and `SeatRack` are as
[`71-04-seats.md`](71-04-seats.md) gives them, and are not repeated here.

## Access

```rust
pub struct ViewerAccess {
    pub player: Option<PlayerId>,
    pub seats: Vec<u8>,        // every seat this account holds — not one
    pub is_creator: bool,
}
```

`Creator` stops being a rank below participant: an account can be the creator
*and* hold two seats. What a viewer may see is the union over `seats`, which is
the live defect the design names — today `.find(...)` returns one seat, so a
player holding two has one of their own racks hidden from them.

[^d72]: Decision #479 (D72): how an emailed invitation behaves once an address
    identifies one account. It supersedes D59 (#445).

[^d71]: Decision #472 (D71): one file per stage, functional views before the
    technical design; work packages scoped as sections of this design, and a test
    file per package fitted to the overall test approach.
