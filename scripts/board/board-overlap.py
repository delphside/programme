#!/usr/bin/env python3
"""board-overlap.py — which open pull requests name or change the same files.

    board-overlap.py --files PATH... [--repo OWNER/REPO]   # before editing: who else has these?
    board-overlap.py --pr OWNER/REPO#N                     # that pull request's files, the others'
    board-overlap.py --all                                 # every pair of open pull requests that
                                                           # share a file, in each repository the
                                                           # programme file names
    board-overlap.py --exit-code ...                       # exit 1 when anything overlaps

A pull request's files are the ones it changes (GitHub's `/files`) and the ones
it names, on the `Claims:` line of its body (`board/claims.py` says the form).
`--files` and `--pr` list each other open pull request of the repository, which
is the application's (its profile's) unless `--repo` names another, with a file
in common, one line each:

    OVERLAP OWNER/REPO#N TITLE — PATH, PATH

A `--pr` that is closed or merged is not compared: it prints one line saying so
and exits 0. `--files` with `--repo` needs no profile, so it runs in the
programme's own checkout; the rest read the application's profile, and `--all`
the programme file.

`--all` prints `OVERLAP OWNER/REPO#N and #M — PATH, PATH` for each such pair. With
nothing to report it prints `ok overlap: none`. Paths are relative to the
repository's root; one ending `/` is a directory and everything below it.

It reads open pull requests and each one's files by REST, so a cloud session's
token can run it: per repository, a call for each hundred open pull requests
and a call for each hundred files of each.

A check run to report, so it exits 0 whatever it finds (docs/1.10):

    0   completed, with findings or without; with --exit-code, without
    1   with --exit-code only: it found an overlap
    2   could not judge: GitHub refused a read, or the live checkout is missing
    64  usage error: a bad flag, or a --pr that is not OWNER/REPO#N
    65  there is no such pull request as the --pr names, or no such repository as
        the --repo names
    70  unexpected error, or no profile or programme file where one is needed
        (`profile.run`)
    75  could not judge, and a retry may work: GitHub did not answer in time

It changes nothing, so it has no pivot.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from board import profile, records  # noqa: E402
from board.claims import Pull, against, pairs, parse_claims  # noqa: E402
from board.cli import EX_DATAERR, EX_TEMPFAIL, PR_REF, REPO, Parser  # noqa: E402
from board.sources import NotFound, Unavailable, rest_get, rest_list  # noqa: E402

# The programme file beside this script: the pinned copy's, in an application's
# checkout, and the repository's own in the programme's.
OWN_PROGRAMME_FILE = Path(__file__).resolve().parents[2] / "config" / "programme.toml"


class NoSuch(Exception):
    """The pull request or repository the user named is not there."""


def _pull(repo: str, raw: dict) -> Pull:
    """A pull request from GitHub's REST form, its files read. A renamed file
    counts under both its names."""
    number = raw["number"]
    changed = []
    for f in rest_list(f"repos/{repo}/pulls/{number}/files"):
        changed += [f["filename"], *([f["previous_filename"]] if f.get("previous_filename") else [])]
    return Pull(repo, number, raw.get("title") or "", tuple(dict.fromkeys(changed)),
                parse_claims(raw.get("body")))


def open_pulls(repo: str, named: bool = False, leaving_out: int | None = None) -> list[Pull]:
    """Every open pull request of `repo` (`owner/name`) with its files, except
    number `leaving_out`, whose files are not read. `named` says the user named
    the repository, so that its absence is `NoSuch`."""
    try:
        raws = rest_list(f"repos/{repo}/pulls?state=open")
    except NotFound as exc:
        if named:
            raise NoSuch(f"there is no repository {repo}, or this token cannot see it") from exc
        raise
    return [_pull(repo, raw) for raw in raws if raw["number"] != leaving_out]


def _one(ref: str) -> tuple[Pull | None, str]:
    """The named pull request with its files, or None and the line to print
    when it is not open."""
    owner, name, number = PR_REF.fullmatch(ref).groups()
    repo = f"{owner}/{name}"
    raw = rest_get(f"repos/{repo}/pulls/{number}")
    if raw is None:
        raise NoSuch(f"there is no pull request {ref}")
    state = raw.get("state", "open")
    if state != "open":
        return None, f"ok overlap: {ref} is {'merged' if raw.get('merged') else state}, so nothing was compared"
    return _pull(repo, raw), ""


def _line(pull: Pull, common) -> str:
    return f"OVERLAP {pull.ref} {pull.title} — {', '.join(common)}"


def report(args) -> tuple[list[str], str]:
    """The lines to print, none when nothing overlaps, and what to say then."""
    nothing = "ok overlap: none"
    if args.all:
        return [f"OVERLAP {one.ref} and #{two.number} — {', '.join(common)}"
                for repo in profile.watched_repositories()
                for one, two, common in pairs(open_pulls(repo))], nothing
    if args.pr:
        mine, said = _one(args.pr)
        if mine is None:
            return [], said
        others = open_pulls(mine.repo, leaving_out=mine.number)
        return [_line(p, c) for p, c in against(mine.paths, others)], nothing
    repo = args.repo or profile.repository_name()
    return [_line(p, c) for p, c in against(args.files, open_pulls(repo, named=bool(args.repo)))], nothing


def main(argv: list[str]) -> int:
    ap = Parser(prog="board-overlap.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    what = ap.add_mutually_exclusive_group(required=True)
    what.add_argument("--files", nargs="+", metavar="PATH", help="the files you plan to change")
    what.add_argument("--pr", metavar="OWNER/REPO#N", help="this pull request's own files")
    what.add_argument("--all", action="store_true", help="every pair of open pull requests sharing a file")
    ap.add_argument("--repo", metavar="OWNER/REPO", help="with --files: the repository (default: this application's)")
    ap.add_argument("--exit-code", action="store_true", help="exit 1 when anything overlaps")
    args = ap.parse_args(argv)
    if args.pr is not None and not PR_REF.fullmatch(args.pr):
        ap.error(f"--pr takes OWNER/REPO#N, not {args.pr!r}")
    if args.repo is not None and (args.files is None or not re.fullmatch(REPO, args.repo)):
        ap.error("--repo takes OWNER/REPO, and only with --files")
    if args.repo or args.pr:
        # no profile is read for a named repository, but the read's time limit is the programme file's
        os.environ.setdefault(profile.ENV_CONFIG, str(OWN_PROGRAMME_FILE))
    try:
        lines, nothing = report(args)
    except NoSuch as exc:
        print(f"board-overlap.py: {exc}", file=sys.stderr)
        return EX_DATAERR
    except records.NoLiveCheckout as exc:
        print(f"board-overlap.py: cannot judge: {exc.code}", file=sys.stderr)
        return 2
    except Unavailable as exc:
        print(f"board-overlap.py: cannot judge: {exc}", file=sys.stderr)
        return EX_TEMPFAIL if exc.transient else 2
    for line in lines:
        print(line)
    if not lines:
        print(nothing)
    return 1 if lines and args.exit_code else 0


if __name__ == "__main__":
    raise SystemExit(profile.run(main, sys.argv[1:]))
