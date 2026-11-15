#!/usr/bin/env python3
"""board-actions.py — R1: what needs the owner.

    programme/scripts/board/board-actions.py              # what is waiting, longest-quiet first
    programme/scripts/board/board-actions.py --exit-code  # non-zero if anything is waiting
    programme/scripts/board/board-actions.py --role <role>  # one role's list, oldest first

`--role` reads every repository over REST and judges each open item against
the flow table (`model.FLOW`, the daily sweep's own judgement): the role's
items are those it holds and those where it has a part in the state, each with
its age and its bound. The roles are `model.ROLES`, and `author` lists the pull
requests a thread opened; `--workstream` narrows a design authority's list to
one workstream. An unknown role is refused (exit 2).

Built beside `actions.py`, not in place of it, and the two answer different
questions: `actions.py` lists every outstanding action on the board, this lists
only what the owner has to do. A difference between them is expected and is the
point of running both — see the parallel-running section of the #383 design.

Design: programme/records/2.5-changes/programme-tooling/383-one-board-model/
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from board import flow                         # noqa: E402
from board.model import HOLDERS                # noqa: E402
from board.sources import Unavailable, fetch  # noqa: E402
from board.turn import render                 # noqa: E402


def role_list(role: str, workstream: str | None, now: datetime) -> int:
    if role not in HOLDERS:
        print(f"unknown role {role!r}: the roles are {', '.join(HOLDERS)}", file=sys.stderr)
        return 2
    try:
        sweep = flow.survey(now)
    except Unavailable as exc:
        # A source that did not answer is not "nothing is waiting".
        print(f"cannot say: {exc}", file=sys.stderr)
        return 2
    for failure in sweep.failures:
        print(f"cannot say for {failure}", file=sys.stderr)
    print(flow.render_role(sweep, role, workstream), end="")
    return 2 if sweep.failures else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exit-code", action="store_true",
                    help="exit non-zero when something is waiting on the owner")
    ap.add_argument("--no-colour", action="store_true")
    ap.add_argument("--claude", action="store_true",
                    help="the mirror: what is waiting on Claude rather than "
                         "on the owner")
    ap.add_argument("--quick", action="store_true",
                    help="skip the timeline and token reads, which cost a "
                         "query each; ages fall back to last activity")
    ap.add_argument("--role", help="one role's list from the flow table, oldest first: "
                                   + ", ".join(HOLDERS))
    ap.add_argument("--workstream", help="with --role, only this workstream's items")
    ap.add_argument("--now", help="with --role, judge as of this ISO time (for a test)")
    args = ap.parse_args(argv)

    if (args.workstream or args.now) and not args.role:
        ap.error("--workstream and --now need --role")
    if args.role:
        now = flow.parse_time(args.now) if args.now else datetime.now(timezone.utc)
        if now is None:
            ap.error(f"--now {args.now!r} is not an ISO time")
        return role_list(args.role, args.workstream, now)

    started = time.time()
    try:
        # Bodies are needed: the user-testing source counts boxes in one.
        snapshot = fetch(states="OPEN", with_bodies=True)
    except Unavailable as exc:
        # A source that did not answer is not "nothing is waiting on you".
        print(f"cannot say: {exc}", file=sys.stderr)
        return 2

    text, count = render(snapshot, colour=not args.no_colour,
                         dated=not args.quick,
                         who="Claude" if args.claude else "owner")
    print(text)
    print(f"\033[2mfetched in {snapshot.window:.1f}s, "
          f"reported in {time.time() - started:.1f}s total\033[0m")
    return 1 if (args.exit_code and count) else 0


if __name__ == "__main__":
    raise SystemExit(main())
