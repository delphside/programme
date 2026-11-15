#!/usr/bin/env python3
"""board-inbox.py — R2: what has been said and decided since you last looked.

    programme/scripts/board/board-inbox.py            # the last seven days
    programme/scripts/board/board-inbox.py 2          # a different window, in days
    programme/scripts/board/board-inbox.py --open     # what the owner said that Claude has not answered
    programme/scripts/board/board-inbox.py --open --all         # no cap on the list
    programme/scripts/board/board-inbox.py --open --issue 452   # the same, for one issue, quickly

`--issue` and `--all` only qualify `--open`; without it they are refused.

Replaces `inbox.sh`. It exists because a conversation only works if both sides
can see it -- owner, 2026-08-18, after replying to a comment and having to say
so out loud.

**Seven days by default**, not because a week is the natural rhythm but because
the current one will not last. Owner, same day: *"Right now I am working on this
most days, but that won't last forever."* A default sized for today's cadence
would be exactly wrong on the first day it changed.

**Stateless.** No "last read" file to go stale, drift between machines, or need
clearing when it is wrong. You pass the window.

**`--open` is the to-do list** (#454): the owner's comments with no later comment
from Claude on the same issue, from the floor (`comments.to_do_floor` in the
programme file) on. It does not use the window. It shows the 12 that have waited
longest, one line each, then one line counting the rest; `--all` shows them all.
With `--issue` it reads that one issue and nothing else, by the same rules and
the same comment read as the whole board (`inbox.read_waiting`), which is what
the check before Claude comments runs. `--ids` adds GitHub's id to each line.

Design: programme/records/2.5-changes/programme-tooling/383-one-board-model/
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from board.inbox import CAP, build, read_waiting, render, render_waiting      # noqa: E402
from board.sources import Unavailable, comments_since, fetch, reports_since     # noqa: E402


def open_comments(args: argparse.Namespace) -> int:
    limit = 10**6 if args.all else CAP
    try:
        threads = read_waiting(args.issue)
    except Unavailable as exc:
        print(f"board-inbox: {exc}", file=sys.stderr)
        return 1
    print(render_waiting(threads, colour=not args.no_colour, limit=limit, ids=args.ids))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("days", nargs="?", type=int, default=7,
                        help="how many days back to look (default 7)")
    parser.add_argument("--no-colour", action="store_true")
    parser.add_argument("--open", action="store_true",
                        help="the owner's comments Claude has not answered, from the to-do floor (comments.to_do_floor) on")
    parser.add_argument("--all", action="store_true", help="with --open: no cap on the list")
    parser.add_argument("--issue", type=int, help="with --open: only this issue")
    parser.add_argument("--ids", action="store_true", help="with --open: add each comment's GitHub id")
    args = parser.parse_args()

    # Refused, not ignored: `--issue 5` alone read the last seven days and
    # printed it as if it were issue 5's (#455-R10).
    for flag, given in (("--issue", args.issue is not None), ("--all", args.all),
                        ("--ids", args.ids)):
        if given and not args.open:
            parser.error(f"{flag} needs --open")

    if args.open:
        return open_comments(args)

    if args.days < 1:
        print("board-inbox: the window is a whole number of days, at least 1",
              file=sys.stderr)
        return 2

    since = (datetime.now(timezone.utc) - timedelta(days=args.days)) \
        .strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        # Both states: a thread on a closed issue is still a thread, and the
        # events section is about issues that closed.
        # Pull requests too: a review comment names a PR, and without them the
        # thread arrives as a bare number. `inbox.sh` had the same blank,
        # because `gh issue list` does not return pull requests either.
        opened = fetch("OPEN", with_bodies=False, with_pull_requests=True,
                       pr_states="[OPEN, CLOSED, MERGED]")
        closed = fetch("CLOSED", with_bodies=False, with_pull_requests=False)
        remarks = comments_since(since)
        reports = reports_since(since)
    except Unavailable as exc:
        # Refuse rather than report a quiet week. `inbox.sh` reported nothing on
        # a day four issues opened and four closed, because a malformed call
        # failed into /dev/null and looked exactly like silence.
        print(f"board-inbox: {exc}", file=sys.stderr)
        return 1

    inbox = build(opened.issues + closed.issues, remarks, since, reports)
    print(render(inbox, colour=not args.no_colour))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
