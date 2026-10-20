#!/usr/bin/env python3
"""board-add.py — put every open issue and pull request in the organisation on
the board.

    scripts/board/board-add.py            # add what is missing
    scripts/board/board-add.py --check    # report what is missing and change nothing

Every repository the organisation holds is read, archived ones aside, so a new
repository needs nothing set up (delphside/tile-lite-elite#485 R2). Which
items need adding, and why only open ones, is `scripts/board/org_sync.py`.
Run hourly by the programme repository's `board-add.yml`.

Refuses (exit 2) when:
  - the organisation's repositories, or one repository's issues or pull
    requests, cannot be read
    -> "board-add: could not read ..."
    Nothing is added on a partial read.

Reports (exit 1), after adding what it can, when:
  - a repository the programme file names (`organisation.repositories`) is
    not among those the organisation lists, because the token cannot see it,
    or it was renamed or archived
    -> "  <repo> is not visible to this token — its items were not read"
  - an item could not be added
    -> "  <repo>#N could not be added"
  and from --check, which adds nothing, when an open item is not on the board
    -> "  <repo>#N (<issue|pull request>) is not on the board"

Exit 0 when the board holds every open item of every repository it must.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from board import org_sync, profile  # noqa: E402
from board.sources import (Unavailable, add_to_project,  # noqa: E402
                           open_items, organisation_repositories)

NAME = "board-add"


def main(argv: list[str]) -> int:
    if "-h" in argv or "--help" in argv:
        print(__doc__)
        return 0
    checking = "--check" in argv
    try:
        repos = organisation_repositories()
        items = [i for repo in repos for i in open_items(repo)]
    except Unavailable as exc:
        print(f"{NAME}: could not read the organisation's issues and pull requests ({exc})",
              file=sys.stderr)
        return 2

    unseen = org_sync.unseen(repos, profile.programme_file().strings("organisation.repositories"))
    for repo in unseen:
        print(f"  {repo} is not visible to this token — its items were not read",
              file=sys.stderr, flush=True)
    tally = org_sync.check(items) if checking else org_sync.apply(items, add_to_project)
    for err, text in tally.lines:
        print(text, file=sys.stderr if err else sys.stdout, flush=True)
    if checking:
        print(f"{NAME}: {tally.missing} missing, {len(unseen)} repository(ies) unseen")
        return 1 if tally.missing or unseen else 0
    print(f"{NAME}: {tally.added} added of {tally.missing} missing, "
          f"{len(unseen)} repository(ies) unseen")
    return 1 if tally.failed or unseen else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
