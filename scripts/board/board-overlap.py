#!/usr/bin/env python3
"""board-overlap.py — which open pull requests claim or change the same files.

    board-overlap.py --files PATH... [--repo OWNER/REPO]   # before editing: who else has these?
    board-overlap.py --pr OWNER/REPO#N                     # that pull request's files, the others'
    board-overlap.py --all                                 # every pair of open pull requests that
                                                           # share a file, in each repository the
                                                           # programme file names
    board-overlap.py --exit-code ...                       # exit 1 when anything overlaps

A pull request's files are the ones it changes (GitHub's `/files`) and the ones
it claims, in the `Claims:` line of its body (`board/claims.py` says the form).
`--files` and `--pr` list each other open pull request of the repository, which
is the application's (its profile's) unless `--repo` names another, with a file
in common, one line each:

    OVERLAP OWNER/REPO#N TITLE — PATH, PATH

`--all` prints `OVERLAP OWNER/REPO#N and #M — PATH, PATH` for each such pair. With
nothing to report it prints `ok overlap: none`. Paths are relative to the
repository's root; one ending `/` is a directory and everything below it.

It reads open pull requests and each one's files by REST, so a cloud session's
token can run it: per repository, a call for each hundred open pull requests
and a call for each hundred files of each.

A check run to report, so it exits 0 whatever it finds (docs/1.10):

    0   completed, with findings or without; with --exit-code, without
    1   with --exit-code only: it found an overlap
    2   could not judge: GitHub refused a read, or there is no such pull request
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
from board.claims import Pull, against, pairs, parse_claims  # noqa: E402
from board.sources import Unavailable, rest_get, rest_list  # noqa: E402

EX_USAGE = 64
EX_TEMPFAIL = 75
_REPO = r"[\w.-]+/[\w.-]+"
_PR = re.compile(rf"({_REPO})#(\d+)")


class _Parser(argparse.ArgumentParser):
    def error(self, message: str):
        self.print_usage(sys.stderr)
        print(f"board-overlap.py: {message}", file=sys.stderr)
        raise SystemExit(EX_USAGE)


def _pull(repo: str, raw: dict) -> Pull:
    """A pull request from GitHub's REST form, its files read. A renamed file
    counts under both its names."""
    number = raw["number"]
    changed = []
    for f in rest_list(f"repos/{repo}/pulls/{number}/files"):
        changed += [f["filename"], *([f["previous_filename"]] if f.get("previous_filename") else [])]
    return Pull(repo, number, raw.get("title") or "", tuple(dict.fromkeys(changed)),
                parse_claims(raw.get("body")))


def open_pulls(repo: str) -> list[Pull]:
    """Every open pull request of `repo` (`owner/name`) with its files."""
    return [_pull(repo, raw) for raw in rest_list(f"repos/{repo}/pulls?state=open")]


def _one(ref: str) -> Pull:
    repo, number = _PR.fullmatch(ref).groups()
    raw = rest_get(f"repos/{repo}/pulls/{number}")
    if raw is None:
        raise Unavailable(f"there is no pull request {ref}")
    return _pull(repo, raw)


def _line(pull: Pull, common) -> str:
    return f"OVERLAP {pull.ref} {pull.title} — {', '.join(common)}"


def report(args) -> list[str]:
    """The lines to print, none when nothing overlaps."""
    if args.all:
        return [f"OVERLAP {one.ref} and #{two.number} — {', '.join(common)}"
                for repo in profile.watched_repositories()
                for one, two, common in pairs(open_pulls(repo))]
    if args.pr:
        mine = _one(args.pr)
        others = [p for p in open_pulls(mine.repo) if p.number != mine.number]
        return [_line(p, c) for p, c in against(mine.paths, others)]
    repo = args.repo or profile.repository_name()
    return [_line(p, c) for p, c in against(args.files, open_pulls(repo))]


def main(argv: list[str]) -> int:
    ap = _Parser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    what = ap.add_mutually_exclusive_group(required=True)
    what.add_argument("--files", nargs="+", metavar="PATH", help="the files you plan to change")
    what.add_argument("--pr", metavar="OWNER/REPO#N", help="this pull request's own files")
    what.add_argument("--all", action="store_true", help="every pair of open pull requests sharing a file")
    ap.add_argument("--repo", metavar="OWNER/REPO", help="with --files: the repository (default: this application's)")
    ap.add_argument("--exit-code", action="store_true", help="exit 1 when anything overlaps")
    args = ap.parse_args(argv)
    if args.pr is not None and not _PR.fullmatch(args.pr):
        ap.error(f"--pr takes OWNER/REPO#N, not {args.pr!r}")
    if args.repo is not None and (args.files is None or not re.fullmatch(_REPO, args.repo)):
        ap.error("--repo takes OWNER/REPO, and only with --files")
    try:
        lines = report(args)
    except Unavailable as exc:
        print(f"board-overlap.py: cannot judge: {exc}", file=sys.stderr)
        return EX_TEMPFAIL if exc.transient else 2
    for line in lines:
        print(line)
    if not lines:
        print("ok overlap: none")
    return 1 if lines and args.exit_code else 0


if __name__ == "__main__":
    raise SystemExit(profile.run(main, sys.argv[1:]))
