# 71 Journey questions

This file holds the functional questions the journeys raise, Q1 to Q15. The functional views are introduced in [`71-functional.md`](71-functional.md), and the design in [`71-02-overview.md`](71-02-overview.md).

Functional, so answered before the technical decisions:

## Q1 Aborting changes nobody's rating

Answered: GAME-5 (owner,
2026-10-14).

## Q2 Who may force-resign a seat

Answered: the creator alone, GAME-6
(owner, 2026-10-14), as the code does (`caller_may_manage_game`,
common.rs). An administrator ends a stuck game with force-end instead.

## Q3 A departing seat's tiles go back to the bag

Answered: one rule for
every departure, GAME-7 (owner, 2026-10-14).

## Q4 A suggested move is played, not suggested

Answered: the service shows
it and does not play it, and asking makes the game unrated, RATE-4 (owner,
2026-10-15). What follows is the question as raised. `suggest_move` (games.rs)
enumerates the legal moves, applies the best-scoring one with
`apply_place_move` (or `apply_pass` when there is none), runs any bot turns
and returns the new state. docs/1.0 has no rule for it, and `preview_move`,
which only reports a candidate's legality and score, has no use case.
Proposed: decide whether the use case is "play the best move for me" or
"show me a suggestion". If it plays, a rule says the move is the seat's own
for scoring and rating; if it only shows, the code changes.

## Q5 The email rules are not in docs/1.0

Uniqueness (#439 R2), verification and activating an account are #439's
(R3); how they meet invitations is INV-1 to INV-8. The code differs: `register_player` (auth.rs) creates an
active account and a session at once and takes any email;
`update_player_details` (auth.rs:301-303) and `get_player_by_email`
(persistence.rs:856) say duplicates are allowed, and the former changes the
email with no check. Settled by the owner on 2026-10-15, superseding #439 R7
and R3's short code:

- a pending email blocks nobody, so several accounts may hold it pending, and
  the first to verify keeps it while the others lose it;
- verification is by a link good for a day;
- asking for a new verification link always gives an email, the same one
  or another, so it is also how an email is changed before verification;
- an account not yet active may, signed in, ask for a new link, and may
  reset its password; nothing else;
- a password reset link also verifies a pending email if no other account has
  verified it;
- a reset is asked for, and sign-in made, by User ID or by a verified email,
  since only a verified email is unique (ACC-4, ACC-5);
- an account never verified is removed after 30 days with no activity;
- a changed-from email is released at the change, not when the new one is
  verified.

Proposed: these rules go to docs/1.0 when #439 lands.

## Q6 A User ID is unique, ignoring case

Withdrawn: docs/2.5 already says a
display name is unique after folding, and #301 owns the fuller User ID rules
(mapping, 2 to 30 characters, permitted characters, reserved names, the NFKC
fold), which #363 builds. This question missed both. `register_player` and
`update_player_details` refuse a name another account holds, through
`get_player_by_name` on the folded name. docs/1.0 does not say so. Proposed:
a rule beside ACC-1.

## Q7 Sign-in and reset reveal nothing about who has an account, and a reset ends every session

Answered: ACC-4 to ACC-6, and "Change my password"
joins Manage my account (owner, 2026-10-15). docs/2.5 already described it; the
rules make it testable. What follows is the question as raised. `login_player` gives one answer for an unknown User ID
and a wrong password; `request_password_reset` answers the same for an
unknown email; the link works once, within an hour
(`PASSWORD_RESET_TOKEN_TTL_SECS`), a new request voids older links, and
`reset_password` and `change_password` end every session. ACC-1 says only
that signing in starts a new one, and changing a password is in no use case.
Proposed: rules beside ACC-1, and "Change my password" added to the use
cases.

## Q8 Withdrawing from a seat has a lifecycle arrow and no use case

Answered:
a withdrawn seat is spent, an invitation is never sent again, and a new seat
re-invites, GAME-9; "withdraw from my seat" joins Join a game (owner,
2026-10-15). What follows is the question as raised.
`withdraw_from_seat` (roster.rs) lets the holder of a claimed seat other than
the creator's give it up before the start. The lifecycle makes `Withdrawn`
terminal, but the code unclaims the seat and sets its invitation to
`rejected`, so the creator can send it again. Proposed: a use case, "Withdraw
from a seat", with its own journey, and the code made to match the spent
seat.

## Q9 Roster limits that only the code states

In part answered: the
creator's own seat is withdrawn like any other, GAME-8 (owner, 2026-10-15).
The rest by GAME-9: a named seat must name an existing account, and the
creator may reorder seats in any state until the start (owner, 2026-10-15,
designed for the new lifecycle rather than read from the code). The creator's own seat cannot
be removed, withdrawn or force-resigned (`remove_seat`, `withdraw_seat`,
`force_resign`, game_state.rs); seats can be swapped only once every human
seat is claimed (`swap_seats`); a named seat for an unknown player is refused
(`add_seat_to_game`). GAME-3 and GAME-4 are silent. Proposed: one rule for
the three limits.

## Q10 A seat open to anyone

Answered: the open seat stays, GAME-10 (owner, 2026-10-16). What follows is
the question as raised. `create_game` and `add_seat_to_game` accept an
open claim, an invitation with neither a name nor an email has no invitee,
`list_games` shows every such invitation to every signed-in player
(`get_open_invitations`, relationship `InvitedOpen`), and
`claim_invitation` lets the first accepter win. docs/1.0 has INV-2 for a
link and INV-3 for it working once, and nothing for a seat open to every
player. Proposed: decide whether the open seat survives D72. If it does, a
rule says who sees it and that the first to accept wins; if not, the journey
goes.

## Q11 An administrator's force-end has no arrow, and only DEL-1 says admin actions need the host

Answered: a force-end aborts a game not started and finishes one in play,
GAME-11, and every administrator action needs the host, ADM-1 (owner,
2026-10-16). What follows is the question as raised.
`admin_force_finish` (game_state.rs) takes a game
`Waiting` or `Active` to `Finished`, so a game never started can finish
with no racks dealt. The game lifecycle has no arrow for a force-end.
`require_loopback` (admin.rs) restricts every admin route, while DEL-1 says
it for deletion alone. Proposed: an arrow from Not Started and Active for
the force-end, or the code refusing a game not started, and a rule beside
DEL-1 for the host restriction.

## Q12 Administrator actions with no use case

Answered (owner, 2026-10-16): the admin CLI tidies old data, so it never
deletes a game in play, ADM-2; deleting an account waits for its sessions or
signs it out, DEL-11; "Delete a game" and "Sign a player out" are journeys.
Removing a misbehaving player, a player closing their own account, an
administrator resetting a password, and the support requests and complaints
that lead to them are #296's. What follows is the question as raised.
The admin CLI deletes a game
(`admin_delete_game`, admin.rs:379, `DELETE /admin/games/{id}`), resets a
player's password (`admin_reset_password`, admin.rs:266) and signs a player
out (`admin_sign_out_user`). `admin_delete_user` refuses while the account
has a live session (`has_live_session`) and names signing out as the remedy,
and for games its refusal says only to wait (admin.rs:159-162), though its
comment names deleting them first as the alternative (admin.rs:94-96).
`admin_delete_game` removes a game in any state, Active included, and the
game lifecycle has no arrow for it, as question 11 finds for a force-end.
DEL-1 to DEL-10 mention none of this. Proposed: use cases "Delete a game",
"Reset a player's password" and "Sign a player out" for the administrator,
a rule beside DEL-2 for the live session, and either an arrow from every
game state for an administrator's deletion or a refusal to delete a game
still in play.

## Q13 Some steps change a game's record and move no seat, and the invariant does not treat them alike

Answered: the seated players and the creator may chat, up to 1000
characters, GAME-12 (owner, 2026-10-16); hiding a game and recording a
reminder save without advancing the version, [71-03-version.md](71-03-version.md#one-version-moved-in-one-place).
What follows is the question as raised.
Chat and hiding a game bump the version
(`mark_changed`), hiding without a broadcast on purpose; the reminder
(`send_move_time_reminders`, sweeps_game.rs) sets `reminder_sent_turn` and
saves without bumping it. Only seated players may chat (`post_chat_message`,
game_state.rs) and the unseated creator may not; the length limit is 1000
characters. docs/1.0 states neither. Proposed: say beside the "everything
that changes a game bumps the one version" invariant that per-viewer flags
and the record of a reminder sent are exempt, and a rule for who may chat.

## Q14 Who may read a rating

Answered: the current rating is always visible, and stats and history are
public unless the player, or whoever runs a bot, makes them private, RATE-5 (owner, 2026-10-16). The
private flag needs a column on `players`; which migration carries it is
settled with WP C's schema. What follows is the question as raised.
`get_player_stats` and
`get_player_rating_history`, and for a bot `get_engine_stats` and
`get_engine_rating_history` (ratings.rs), require only a signed-in caller.
ACC-3 says the history belongs to the player and not who may see it.
Proposed: a rule that any signed-in player may read any player's or bot's
rating and history.

## Q15 RET-3 has no definition of "last activity" for a game not started, and nothing implements it

Answered: [docs/4.2.4](https://github.com/delphside/tile-lite-elite/blob/main/docs/4.2.4-persistence.md) already said the roster
and a keep count, and RET-3 now says so, with a chat, a hide, a reminder and
a change of a player's details not counting (owner, 2026-10-16). Still not
built: WP C. What follows is the question as raised.
`expire_old_terminal_games` (sweeps_capacity.rs)
removes only Finished and Aborted games, seven days after `ended_at`;
`last_activity_by_game` is the latest move, or the creation time when there
is none, so editing the roster is not activity. RET-3 says it is not built.
Proposed: define last activity as any change to the game, roster edits and
a keep included, except a chat, a hide or a reminder, which #460 found should
not count. `games.last_activity_at` records it (`71-09-open-questions.md`).
