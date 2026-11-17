#!/usr/bin/env python3
"""board-flow.py — the daily sweep: who holds each open item, and what has stalled.

    programme/scripts/board/board-flow.py             # sweep, write, publish the stalled list
    programme/scripts/board/board-flow.py --dry-run   # say what it would write; write nothing

Reads every open issue and pull request in the programme's repositories over
REST (so it runs from a cloud session), judges each against the flow table
(`model.FLOW`), and:

  * writes R7's starting types and states, and each issue's `Turn`, one call per
    item that changed. A pull request is never given a type or an issue field;
  * keeps a thread-set `Owner` with an approval comment, and a `Hold` whose
    reason still holds; a `Turn` that is what the sweep last wrote, or any other,
    is overwritten by the derived value;
  * keeps a stale claim and offers the item to the role's current thread;
  * moves a work package whose release milestone closed; a merged pull request
    that names a package still before its merge is only listed, under "needs a
    look";
  * rewrites the body of the pinned stalled-list issue (titled by
    `flow.STALLED_LIST_TITLE`, in the programme repository), says it did, and
    prints the same list by role. The body ends with the ledger: each item's state, when the
    sweep first saw it there, and the `Turn` the sweep last wrote.

It refuses, naming it, when the pinned issue is missing. The ledger is all it
remembers between runs; a dry run reads it and writes nothing, the ledger
included.

Exit status (docs/1.10 *What a script's exit status means*): 0 nothing is
stalled and nothing needs a look; 1 something is (a check reporting, not a
gate); 2 it could not finish: a read or a write failed, or the pinned issue is
missing. A failed run never exits 1. It keeps the last complete run's list in the
pinned issue and rewrites only the ledger, with the writes it made.

Design: programme/records/2.5-changes/process-definition/176-project-board-flow/
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from board import flow, profile  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true",
                    help="print each write the run would make; write nothing")
    ap.add_argument("--now", help="judge as of this ISO time instead of now (for a test)")
    args = ap.parse_args(argv)
    now = flow.parse_time(args.now) if args.now else datetime.now(timezone.utc)
    if now is None:
        ap.error(f"--now {args.now!r} is not an ISO time")
    return flow.run(now, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(profile.run(main, sys.argv[1:]))
