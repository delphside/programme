# 71 Journeys U4 to U6

This file holds the journeys of U4 Play a game, U5 Follow my games and U6 Look after the service. The functional views are introduced in [`71-functional.md`](71-functional.md), and the design in [`71-02-overview.md`](71-02-overview.md).

## U4 Play a game

Every seated player comes to the service to play the game through. Turns go
round until at most one seat is still playing (GAME-2); the creator and the
clock can each end a seat's part early.

```mermaid
flowchart TD
  s0((start)) --> a1["U4.1 Take a turn"]
  s0 --> a2["U4.2 Ask for a suggested move"]
  a2 --> a1
  s0 --> a3["U4.3 Chat in a game"]
  s0 --> a4["U4.6 Remind the player on turn"]
  s0 --> a5["U4.4 Leave a game in play"]
  s0 --> a6["U4.5 Abort a game"]
```

Journeys: [U4.1 Take a turn](#u41-take-a-turn), [U4.2 Ask for a suggested move](#u42-ask-for-a-suggested-move), [U4.3 Chat in a game](#u43-chat-in-a-game), [U4.4 Leave a game in play](#u44-leave-a-game-in-play), [U4.5 Abort a game](#u45-abort-a-game), [U4.6 Remind the player on turn](#u46-remind-the-player-on-turn).

### U4.1 Take a turn

```mermaid
flowchart TD
  s0((start)) --> p1["Player or bot: told it is their turn (reads)"]
  p1 --> p2["Player: composes a word, which survives other turns<br/>until a tile lands in its cells (client only)"]
  p2 --> p3["Player or bot: places, passes or exchanges"]
  p3 --> v1{"Server: this seat's turn, and the move legal?"}
  v1 -- no --> r1["refused, nothing changes"]
  v1 -- yes --> t1["Server: applied (no transition), version and turn move,<br/>tiles drawn, every client told"]
  t1 --> v2{"Server: does the game end?<br/>GAME-2, the scoreless limit, out of tiles"}
  v2 -- no --> p4["next seat told it is their turn"]
  v2 -- yes --> t2["Server: game Finished, ratings settled<br/>RATE-2, RATE-3"]
```

### U4.2 Ask for a suggested move

```mermaid
flowchart TD
  s0((start)) --> p1["Player: asks for a suggestion on their turn"]
  p1 --> v1{"Server: the game Active, and this human seat on turn?"}
  v1 -- no --> r1["refused, nothing changes"]
  v1 -- yes --> v2["Server: finds the best-scoring legal move for the rack,<br/>or a pass when there is none (reads)"]
  v2 --> t1["Server: the game becomes unrated, version bumps,<br/>every client told; the move is returned, not played<br/>RATE-4"]
  t1 --> p2["Player: plays it, or another, as in Take a turn"]
```

### U4.3 Chat in a game

```mermaid
flowchart TD
  s0((start)) --> p1["Player: writes a message"]
  p1 --> v1{"Server: the caller holds a seat in the game or created it,<br/>and the message is neither blank nor over 1000 characters?<br/>GAME-12"}
  v1 -- no --> r1["refused, nothing changes"]
  v1 -- yes --> t1["Server: message recorded, on or off turn, in any game state<br/>version bumps, every client told (no transition)<br/>RET-1"]
```

### U4.4 Leave a game in play

```mermaid
flowchart TD
  s0((start)) --> d0{"how"}
  d0 -- "player resigns" --> a1["Playing → Departed, resigned<br/>RATE-2"]
  d0 -- "creator force-resigns" --> a2["Playing → Departed, force-resigned<br/>GAME-6, RATE-3"]
  d0 -- "Time: the move limit passes" --> a3["Playing → Departed, timed out,<br/>tiles back to the bag<br/>TIME-3, GAME-7, RATE-3"]
  a1 --> b1["tiles back to the bag<br/>GAME-7"]
  a2 --> b1
  b1 --> v1{"Server: at most one seat still playing?<br/>GAME-2"}
  a3 --> v1
  v1 -- yes --> t1["game Finished, ratings settled"]
  v1 -- no --> t2["if it was their turn, the next seat is told;<br/>a bot's turn runs"]
```

### U4.5 Abort a game

```mermaid
flowchart TD
  s0((start)) --> c1["Creator: aborts, before or after the start<br/>GAME-1"]
  c1 --> t1["Server: pending invitations cancelled"]
  t1 --> t2["Server: game Aborted, seats frozen as they stand<br/>GAME-1"]
  t2 --> t3["no rating changes<br/>GAME-5"]
```

### U4.6 Remind the player on turn

```mermaid
flowchart TD
  s0((start)) --> t0["Time: the hourly pass looks at each Active game (reads)"]
  t0 --> v1{"Server: limit longer than a day, a third of it or less remaining,<br/>and the seat on turn a claimed player not yet reminded this turn?<br/>TIME-4"}
  v1 -- yes --> t1["Server: records that this turn was reminded (no transition)<br/>Q13"]
  t1 --> t2["Server: notifies the player on turn, once, on their devices<br/>TIME-4, NOTE-1"]
```

## U5 Follow my games

A player comes to the service to see where they stand: their games, their
ratings and their history, and to clear what they no longer want listed.

```mermaid
flowchart TD
  s0((start)) --> a1["U5.1 See my games, ratings and history"]
  a1 --> a2["U5.2 Remove a game from my list"]
```

Journeys: [U5.1 See my games, ratings and history](#u51-see-my-games-ratings-and-history), [U5.2 Remove a game from my list](#u52-remove-a-game-from-my-list).

### U5.1 See my games, ratings and history

```mermaid
flowchart TD
  s0((start)) --> p1["Player: opens their list"]
  p1 --> v1{"Server: signed in?<br/>ACC-1"}
  v1 -- no --> r1["refused, asked to sign in"]
  v1 -- yes --> t1["Server: finished and aborted games over 7 days old<br/>Over → removed, with their invitations<br/>RET-1, RET-4"]
  t1 --> v2["Server: lists the games the player is seated in, was invited to<br/>or created, less those they hid, newest activity first (reads)<br/>DEL-5"]
  v2 --> p2["Player: opens a rating, stats or a rating history,<br/>their own, another player's or a bot's"]
  p2 --> v3{"Server: their own, only the current rating,<br/>or the other player's or bot's are public? (reads)<br/>RATE-5"}
  v3 -- no --> r3["shown the current rating only"]
  v3 -- yes --> t3["shown (reads)<br/>ACC-3, DEL-10, RET-2"]
  t3 --> p3["Player: reads times in local time (reads)<br/>CLOCK-4"]
```

### U5.2 Remove a game from my list

```mermaid
flowchart TD
  s0((start)) --> p1["Player: removes a game from their list<br/>DEL-5"]
  p1 --> v1{"Server: the game Finished or Aborted,<br/>and the player seated in it or its creator?"}
  v1 -- no --> r1["refused, nothing changes"]
  v1 -- yes --> t1["Server: the game is marked hidden for this player alone<br/>(no transition); the game, its seats and every other<br/>player's list are untouched, and it still refers to the player<br/>DEL-5, DEL-2, Q13"]
```

## U6 Look after the service

The administrator and the clock keep the service in order: ending games
that cannot end, removing old games and accounts, and signing a player out.
The admin CLI tidies old data (ADM-2); closing your own account and
suspending one are #296's.

```mermaid
flowchart TD
  s0((start)) --> a1["U6.1 Force-end a game"]
  s0 --> a2["U6.2 Delete an account"]
  s0 --> a3["U6.3 Remove expired games"]
  s0 --> a4["U6.4 Delete a game"]
  s0 --> a5["U6.5 Sign a player out"]
```

Journeys: [U6.1 Force-end a game](#u61-force-end-a-game), [U6.2 Delete an account](#u62-delete-an-account), [U6.3 Remove expired games](#u63-remove-expired-games), [U6.4 Delete a game](#u64-delete-a-game), [U6.5 Sign a player out](#u65-sign-a-player-out).

### U6.1 Force-end a game

```mermaid
flowchart TD
  s0((start)) --> a1["Administrator: names a game, on the machine hosting the service<br/>ADM-1"]
  a1 --> v1{"Server: the game exists, and is not already<br/>Finished or Aborted?"}
  v1 -- no --> r1["refused, nothing changes"]
  v1 -- yes --> d1{"Server: the game started?"}
  d1 -- no --> t0["Server: game Not Started → Aborted<br/>a record of the force-end kept<br/>GAME-11"]
  d1 -- yes --> t1["Server: game Active → Finished<br/>seats frozen as they stand, a record of the force-end kept<br/>GAME-11"]
  t0 --> t2
  t1 --> t2["Server: no rating changes<br/>RATE-1"]
  t2 --> t3["Server: version bumps, every client told (no transition)"]
```

### U6.2 Delete an account

```mermaid
flowchart TD
  s0((start)) --> a1["Administrator: names an account or gives its id, in the admin CLI<br/>on the machine hosting the service<br/>ADM-1, DEL-1, DEL-9"]
  a1 --> v1{"Server: the account exists? (reads)<br/>DEL-8"}
  v1 -- no --> r1["reported as not found"]
  v1 -- yes --> v2{"Server: does any game refer to it: created, seated or invited,<br/>in any state, hidden by the player or not? (reads)<br/>DEL-2, DEL-3, DEL-5"}
  v2 -- yes --> r2["refused, naming the games<br/>DEL-6"]
  r2 --> d3{"Administrator: waits, or deletes the blocking games<br/>that are not in play?"}
  d3 -- waits --> w1["Administrator: waits, because every game goes eventually<br/>DEL-4, RET-1, RET-3, TIME-2"]
  d3 -- deletes --> g1["Administrator: deletes them, as in Delete a game<br/>ADM-2"]
  g1 --> a1
  w1 --> a1
  v2 -- no --> v3{"Server: a live session? (reads)<br/>DEL-11"}
  v3 -- yes --> r3["refused until the session ends<br/>or the administrator signs it out<br/>DEL-11"]
  r3 --> w1
  r3 --> s1["Administrator: signs it out, as in Sign a player out"]
  s1 --> a1
  v3 -- no --> t1["Server: sessions, invitations sent and received,<br/>rating and rating history removed, nothing of anyone else's<br/>email Live → None, account closed<br/>DEL-7, ACC-3, DEL-10"]
```

### U6.3 Remove expired games

```mermaid
flowchart TD
  s0((start)) --> d0{"Time: which game?"}
  d0 -- "ended over 7 days ago" --> t1["Server: Over → removed: game, seats, chat, moves and invitations go,<br/>found while the service is in use; rating history stays<br/>RET-1, RET-2, RET-4, ACC-3, DEL-10"]
  d0 -- "not started, idle 7 days" --> t2["Time: the creator is asked what to do (not built)<br/>RET-3, Q15"]
  t2 --> c1["Creator: answers delete, keep or nothing<br/>RET-3"]
  c1 --> d1{"answer"}
  d1 -- delete --> t3["Server: Not Started → removed, the game goes at once<br/>RET-3"]
  d1 -- keep --> t4["Server: counts as activity, thirty days start again (no transition)<br/>RET-3"]
  d1 -- nothing --> t5["Time: the countdown carries on, and thirty days after the last activity<br/>Not Started → removed<br/>RET-3"]
```

### U6.4 Delete a game

```mermaid
flowchart TD
  s0((start)) --> a1["Administrator: names a game, in the admin CLI<br/>ADM-1"]
  a1 --> v1{"Server: the game exists, and is not in play?<br/>ADM-2"}
  v1 -- no --> r1["refused, nothing changes: a game in play<br/>is left to end or time out"]
  v1 -- yes --> t1["Server: Not Started or Over → removed,<br/>with its seats, chat, moves and invitations;<br/>rating history stays<br/>ADM-2, RET-2, DEL-10"]
```

### U6.5 Sign a player out

```mermaid
flowchart TD
  s0((start)) --> a1["Administrator: names an account, in the admin CLI<br/>ADM-1"]
  a1 --> v1{"Server: the account exists? (reads)"}
  v1 -- no --> r1["reported as not found"]
  v1 -- yes --> t1["Server: every session of the account ended<br/>(no transition)<br/>DEL-11"]
```
