#!/usr/bin/env python3
"""board-review-record.py — what a pull request's *Review rounds* section leaves the digest unable to read.

    board-review-record.py < body-file                  # a pull request body on stdin
    board-review-record.py --pr OWNER/REPO#N            # the body, read through GitHub's REST API,
                                                        # from an application's checkout, whose
                                                        # profile sets the read's time limit
    board-review-record.py --exit-code ...              # exit 1 when it finds anything

Reads the section with the weekly digest's own parser (`board/digest.py`) and
prints one line per finding, `WARN review record: <finding>`, or `ok review
record` when there is none. A section opening `None owed` has none. The findings
are in `digest.record_problems`: no section, no line the digest reads, a round
line it does not read, a heading that is not `####`, a document with no `doc:`
line, `doc:` fields it does not read, a round with no cost line, a finding by
a reviewer its round's cost line gives no figure for, several `doc:`
lines with no `####` heading, a finding naming a reviewer the digest does not
know, no owner line, and cost figures or `(count …)` markers it does not read.

A check run to report, so it exits 0 whatever it finds (docs/1.10):

    0   completed, with findings or without; with --exit-code, without
    1   with --exit-code only: it found something
    2   could not judge: GitHub refused the read, or there is no such pull request
    64  usage error: a bad flag, or a --pr that is not OWNER/REPO#N
    70  unexpected error (`profile.run`)
    75  could not judge, and a retry may work: GitHub did not answer in time

It changes nothing, so it has no pivot.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from board import profile  # noqa: E402
from board.digest import record_problems  # noqa: E402
from board.sources import Unavailable, rest_get  # noqa: E402

EX_USAGE = 64
EX_TEMPFAIL = 75
_PR = re.compile(r"([\w.-]+)/([\w.-]+)#(\d+)")


class _Parser(argparse.ArgumentParser):
    def error(self, message: str):
        self.print_usage(sys.stderr)
        print(f"board-review-record.py: {message}", file=sys.stderr)
        raise SystemExit(EX_USAGE)


def _body(pr: str | None) -> str:
    """The body to judge: stdin, or the pull request's through REST."""
    if pr is None:
        return sys.stdin.read()
    owner, name, number = _PR.fullmatch(pr).groups()
    data = rest_get(f"repos/{owner}/{name}/pulls/{number}")
    if data is None:
        raise Unavailable(f"there is no pull request {pr}")
    return data.get("body") or ""


def main(argv: list[str]) -> int:
    ap = _Parser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pr", metavar="OWNER/REPO#N", help="read this pull request's body instead of stdin")
    ap.add_argument("--exit-code", action="store_true", help="exit 1 when it finds anything")
    args = ap.parse_args(argv)
    if args.pr is not None and not _PR.fullmatch(args.pr):
        ap.error(f"--pr takes OWNER/REPO#N, not {args.pr!r}")
    try:
        body = _body(args.pr)
    except Unavailable as exc:
        print(f"board-review-record.py: cannot judge: {exc}", file=sys.stderr)
        return EX_TEMPFAIL if exc.transient else 2
    problems = record_problems(body)
    for problem in problems:
        print(f"WARN review record: {problem}")
    if not problems:
        print("ok review record: nothing the digest would leave unread")
    return 1 if problems and args.exit_code else 0


if __name__ == "__main__":
    raise SystemExit(profile.run(main, sys.argv[1:]))
