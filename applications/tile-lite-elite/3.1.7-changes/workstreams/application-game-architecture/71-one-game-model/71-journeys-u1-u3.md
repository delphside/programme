# 71 Journeys U1 to U3

This file holds the journeys of U1 Manage my account, U2 Set up a game, and U3
Join a game. It follows [`71-functional.md`](71-functional.md) and is followed
by [`71-journeys-u4-u6.md`](71-journeys-u4-u6.md).

How to read a journey, and the key to its swimlanes, questions and rule ids, is
in [*Reading the journeys*](71-functional.md#reading-the-journeys).

## U1 Manage my account

A player comes to the service to have an account and keep it theirs. Every
action here is one sitting; none depends on a game.

```mermaid
flowchart TD
  s0((start)) --> a1["U1.1 Register and sign in"]
  s0 --> a2["U1.4 Reset my password"]
  a2 --> a1
  a1 --> a3["U1.2 Change my details"]
  a1 --> a4["U1.3 Change my password"]
```

Journeys: [U1.1 Register and sign in](#u11-register-and-sign-in), [U1.2 Change
my details](#u12-change-my-details), [U1.3 Change my
password](#u13-change-my-password), [U1.4 Reset my
password](#u14-reset-my-password).

### U1.1 Register and sign in

A new account is active once its email is verified, and every email is
unique. Registering and signing in share the end of the journey.

References: User IDs,
[docs/2.5](https://github.com/delphside/tile-lite-elite/blob/main/docs/4.2.5-authentication.md).
Emails: their rules are not yet in docs/1.0,
[Q5](71-journey-questions.md#q5-the-email-rules-are-not-in-docs10).

```mermaid
flowchart TD
  s0((start)) --> d0{"Player: has an active account?"}
  d0 -- no --> p1["Player: gives a User ID, an email and a password"]
  p1 --> v2{"Server: is the User ID free, and the email address<br/>not verified by another account?<br/>a pending email blocks nobody<br/>Q5"}
  v2 -- no --> r2["refused, nothing created"]
  v2 -- yes --> t1["Server: account created, not yet active<br/>email None → Pending for this account,<br/>verification link emailed, good for a day<br/>Q5"]
  t1 --> d1{"Player: follows the link within its day?<br/>Q5"}
  d1 -- no --> p3["Player: signs in to the account, not yet active,<br/>and asks for a new link, giving an email,<br/>the same one or another<br/>Q5"]
  p3 --> v5{"Server: is that email not verified by another account?<br/>Q5"}
  v5 -- no --> r5["refused, nothing changes"]
  v5 -- yes --> t7["Server: that email Pending for this account,<br/>any other it held released, earlier links stop,<br/>a new link emailed, good for a day<br/>Q5"]
  t7 --> d1
  d1 -- "no, and nothing for 30 days" --> t6["Time: 30 days with no activity, never verified<br/>account removed, its User ID and email freed<br/>Q5"]
  d1 -- yes --> v4{"Server: still not verified by another account?<br/>the first to verify keeps it<br/>Q5"}
  v4 -- no --> t2["Server: email Pending → None for this account,<br/>which stays not yet active<br/>Q5"]
  t2 --> p3
  v4 -- yes --> t3["Server: email Pending → Live, account active<br/>other accounts lose it as pending<br/>open invitations to it Open → Passed, including one<br/>whose link was followed before registering<br/>INV-2, INV-4"]
  d0 -- yes --> p2["Player: signs in with User ID or verified email,<br/>and password, and chooses whether<br/>the device stays logged in<br/>ACC-2, ACC-4"]
  t3 --> p2
  p2 --> v3{"Server: the credentials right?<br/>ACC-4"}
  v3 -- no --> r3["refused, with one answer for an unknown<br/>User ID or email and a wrong password"]
  v3 -- yes --> t4["Server: session starts, to end at 10 days<br/>or after 48 hours unused (no transition)<br/>ACC-1"]
  t4 --> d2{"Player: an existing account, arrived by an invitation link?"}
  d2 -- yes --> t5["Server: invitation Open → Passed to this account<br/>INV-2, INV-3"]
```

### U1.2 Change my details

References: User IDs,
[docs/2.5](https://github.com/delphside/tile-lite-elite/blob/main/docs/4.2.5-authentication.md).
A game holds no copy of a player's details,
[71-09-open-questions.md](71-09-open-questions.md#open-questions) *User details
are always a lookup*. Emails,
[Q5](71-journey-questions.md#q5-the-email-rules-are-not-in-docs10).

```mermaid
flowchart TD
  s0((start)) --> p1["Player: signed in, changes the User ID, the email,<br/>or whether their stats and history are private<br/>ACC-1"]
  p1 --> d0{"Server: which?"}
  d0 -- "privacy" --> t5["Server: stats and history private or public<br/>(no transition)<br/>RATE-5"]
  d0 -- "User ID" --> v1{"Server: not blank, and not another account's<br/>ignoring case?"}
  v1 -- no --> r1["refused, nothing changes"]
  v1 -- yes --> t1["Server: User ID changed (no transition)<br/>each game the player is in bumps its version<br/>and is announced; the game holds no copy of the name"]
  d0 -- "email" --> v2{"Server: is the new email address<br/>not verified by another account?<br/>a pending email blocks nobody<br/>Q5"}
  v2 -- no --> r2["refused, nothing changes"]
  v2 -- yes --> t2["Server: new email None → Pending for this account,<br/>old email Live → None at once,<br/>verification link emailed, good for a day<br/>Q5"]
  t2 --> d1{"Player: follows the link within its day?<br/>Q5"}
  d1 -- no --> p3["Player: asks for a new link, giving an email,<br/>the same one or another<br/>Q5"]
  p3 --> v2
  d1 -- yes --> v3{"Server: still not verified by another account?<br/>the first to verify keeps it<br/>Q5"}
  v3 -- no --> t3["Server: new email Pending → None<br/>for this account, which has no email<br/>until it gives another<br/>Q5"]
  v3 -- yes --> t4["Server: new email Pending → Live,<br/>other accounts lose it as pending<br/>open invitations to the new one Open → Passed<br/>INV-4, Q5"]
```

### U1.3 Change my password

```mermaid
flowchart TD
  s0((start)) --> p1["Player: signed in, gives the current password and a new one"]
  p1 --> v1{"Server: the current password right?<br/>ACC-6"}
  v1 -- no --> r1["refused, nothing changes"]
  v1 -- yes --> t1["Server: password changed, every session ended,<br/>this one included (no transition)<br/>ACC-6"]
  t1 --> p2["Player: signs in again, as in Register and sign in"]
```

### U1.4 Reset my password

```mermaid
flowchart TD
  s0((start)) --> p1["Player: gives the User ID of the account,<br/>or its verified email<br/>ACC-5"]
  p1 --> v2{"Server: an account with that User ID and an email,<br/>or with that email Live? (reads)<br/>ACC-5"}
  v2 -- no --> a1["the same answer is given, and nothing is sent<br/>ACC-5"]
  v2 -- yes --> t1["Server: earlier links stop working, a new link is emailed<br/>to the account's email, verified or pending<br/>(no transition)<br/>ACC-5"]
  t1 --> p2["Player: follows the link and gives a new password"]
  p2 --> v3{"Server: link unused and within its hour?<br/>ACC-5"}
  v3 -- no --> r2["refused, one answer for unknown, used and expired"]
  v3 -- yes --> t2["Server: password changed, link used,<br/>every session ended (no transition)<br/>ACC-6"]
  t2 --> d3{"Server: the email was pending,<br/>and not verified by another account?<br/>Q5"}
  d3 -- yes --> t3["Server: the link verifies it, as in Register and sign in:<br/>email Pending → Live, account active<br/>Q5"]
  d3 -- no --> p3["Player: signs in again, as in Register and sign in<br/>ACC-1"]
  t3 --> p3
```

## U2 Set up a game

The creator comes to the service to get a game under way with the people they
want. Seats fill independently until the creator starts with the claimed ones
(GAME-9); the invitees' side of it is [U3 Join a game](#u3-join-a-game), and
aborting is in [U4 Play a game](71-journeys-u4-u6.md#u4-play-a-game), since it
can happen before or after the start.

```mermaid
flowchart TD
  s0((start)) --> a1["U2.1 Create and start a game"]
  a1 -. "while seats fill" .-> a2["U2.2 Arrange the seats"]
  a2 -.-> a1
  a1 -- "gives up" --> a4["U4.5 Abort a game"]
```

Journeys: [U2.1 Create and start a game](#u21-create-and-start-a-game), [U2.2
Arrange the seats](#u22-arrange-the-seats), and [U4.5 Abort a
game](71-journeys-u4-u6.md#u45-abort-a-game) under Play a game.

### U2.1 Create and start a game

```mermaid
flowchart TD
  s0((start)) --> c1["Creator: chooses edition, time limit and seats<br/>GAME-3, TIME-1, TIME-2"]
  c1 --> v1{"Server: at least two seats,<br/>every named seat a registered player?"}
  v1 -- no --> r1["refused, nothing created"]
  v1 -- yes --> t1["Server: game Not Started<br/>own and bot seats Claimed;<br/>invited seats Invited, their invitations sent"]
  t1 --> i1["invitees answer, as in Accept or decline an invitation;<br/>the creator may arrange the seats meanwhile"]
  i1 --> c3["Creator: starts the game"]
  c3 --> v2{"Server: no seat Invited,<br/>two or more left once spent seats drop?<br/>GAME-3"}
  v2 -- no --> r2["refused, nothing changes"]
  v2 -- yes --> t4["Server: spent seats dropped, seats renumbered<br/>Claimed → Playing, racks dealt, game Active"]
```

### U2.2 Arrange the seats

An invited seat's invitation is sent as the seat is added, as in [U2.1 Create
and start a game](#u21-create-and-start-a-game). The creator can also hide
`Declined` and `Withdrawn` seats so the list shows only the seats still in play.
Hiding is the client's alone: the service keeps those seats until the start
drops them.

```mermaid
flowchart TD
  s0((start)) --> c1["Creator: chooses add, withdraw or swap"]
  c1 --> v1{"Server: the creator's game, still Not Started?"}
  v1 -- no --> r1["refused, nothing changes"]
  v1 -- yes --> d0{"which?"}
  d0 -- add --> c2["Creator: names a bot, a player, an email or an open seat<br/>GAME-4, GAME-10"]
  c2 --> v2{"Server: a named player exists?<br/>GAME-9"}
  v2 -- no --> r2["refused, nothing changes"]
  v2 -- yes --> t1["Server: seat appended and numbered<br/>a bot's seat Claimed,<br/>any other Invited, its invitation sent<br/>the same player or bot may hold several seats<br/>GAME-4"]
  c1 -. "hide a Declined or Withdrawn seat<br/>(client only, no service call)" .-> h1["the seat leaves the creator's view"]
  d0 -- withdraw --> c3["Creator: withdraws a seat, their own included<br/>Invited or Claimed<br/>GAME-8, GAME-9"]
  c3 --> t2["Server: seat Withdrawn, any invitation closed and its link dead;<br/>the seat stays, spent, until the start drops it<br/>GAME-9, INV-7"]
  d0 -- swap --> c4["Creator: swaps two seats"]
  c4 --> t3["Server: the two seats exchange places, whatever their states,<br/>and with them turn order (no transition)<br/>GAME-9"]
  t1 --> t4["Server: version bumps, everyone watching is told<br/>(no transition)"]
  t2 --> t4
  t3 --> t4
  t4 --> n0["a game left below two seats waits: it is checked again at the start<br/>GAME-3"]
```

## U3 Join a game

A player comes to the service to take part in somebody else's game. They
answer an invitation, or take a seat open to anyone, and may leave a claimed
seat before the start.

```mermaid
flowchart TD
  s0((start)) --> a1["U3.1 Accept or decline an invitation"]
  s0 --> a2["U3.2 Take an open seat"]
  a1 --> a3["U3.3 Withdraw from my seat"]
  a2 --> a3
```

Journeys: [U3.1 Accept or decline an
invitation](#u31-accept-or-decline-an-invitation), [U3.2 Take an open
seat](#u32-take-an-open-seat), [U3.3 Withdraw from my
seat](#u33-withdraw-from-my-seat).

### U3.1 Accept or decline an invitation

```mermaid
flowchart TD
  s0((start)) --> p1["Player: sees an invitation addressed to them (reads)<br/>INV-1, INV-2, INV-5"]
  p1 --> d1{"Player: accepts?"}
  d1 -- yes --> v1{"Server: the game still Not Started,<br/>and the invitation associated with this player?<br/>INV-5, INV-7"}
  d1 -- no --> v2{"Server: the same checks"}
  v1 -- no --> r1["refused, nothing changes"]
  v2 -- no --> r1
  v1 -- yes --> t1["Server: seat Invited → Claimed<br/>version bumps, everyone watching is told"]
  v2 -- yes --> t2["Server: seat Invited → Declined, dead for good<br/>version bumps, everyone watching is told<br/>GAME-9, DEL-3"]
```

### U3.2 Take an open seat

```mermaid
flowchart TD
  s0((start)) --> p1["Player: sees games with a seat open to anyone (reads)<br/>GAME-10"]
  p1 --> p2["Player: accepts the seat, whether or not already seated in that game<br/>GAME-4"]
  p2 --> v1{"Server: the game still Not Started,<br/>and the seat still unclaimed?<br/>INV-3, INV-7"}
  v1 -- no --> r1["refused: no longer available, nothing changes"]
  v1 -- yes --> t1["Server: seat Invited → Claimed, named for the claimant<br/>version bumps, everyone watching is told<br/>of two at once, one wins<br/>GAME-10"]
```

### U3.3 Withdraw from my seat

```mermaid
flowchart TD
  s0((start)) --> p1["Player: withdraws from a seat they hold"]
  p1 --> v1{"Server: the game still Not Started,<br/>and the seat Claimed by this player?"}
  v1 -- no --> r1["refused, nothing changes"]
  v1 -- yes --> t1["Server: seat Claimed → Withdrawn, spent for good<br/>version bumps, everyone watching is told<br/>GAME-9"]
```
