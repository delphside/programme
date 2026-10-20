"""Which open issues and pull requests in the organisation the board is missing.

**The board holds every repository's work** (delphside/tile-lite-elite#485
R2), and nothing GitHub offers does that by itself. A project's auto-add
workflow watches one repository each, is set by hand with no API, and the plan
caps how many a project may have; `board-pr-state.py` adds only the pull
requests of the application it runs in. So this asks every repository the
organisation holds, archived ones aside, and adds what is open and absent.

Open items only: anything closed has already been dealt with, and adding the
organisation's whole history would bury the board.

**A repository the token cannot see is not listed at all**, rather than listed
and empty, so reading every repository cannot say what it missed. The
programme file names the repositories the board must hold
(`organisation.repositories`), and one absent from the listing is reported.

Run by `scripts/board/board-add.py`. The decision is here, apart from GitHub,
so it can be tested on its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable

from .model import OpenItem
from .sources import Unavailable


Item = OpenItem   # the record lives with the others, in model.py


def missing(items: Iterable[Item]) -> list[Item]:
    """The items the board does not hold, in the order they were read."""
    return [i for i in items if not i.on_board]


def unseen(listed: Iterable[str], expected: Iterable[str]) -> list[str]:
    """The repositories the board must hold that the organisation's listing
    left out: the token cannot see them, or they were renamed."""
    have = set(listed)
    return [r for r in expected if r not in have]


@dataclass
class Tally:
    """What a run did or found, and the lines it says."""

    added: int = 0
    missing: int = 0
    failed: int = 0
    # (to stderr, text), in the order they were said
    lines: list[tuple[bool, str]] = field(default_factory=list)

    def say(self, text: str, err: bool = False) -> None:
        self.lines.append((err, text))


def check(items: Iterable[Item]) -> Tally:
    """Report what is missing and change nothing."""
    tally = Tally()
    for i in missing(items):
        tally.missing += 1
        tally.say(f"  {i.name} ({i.kind}) is not on the board")
    return tally


def apply(items: Iterable[Item], add: Callable[[str], str]) -> Tally:
    """Add what is missing. `add(node_id)` raises `Unavailable` when GitHub
    refuses; a failed add is reported and not counted."""
    tally = Tally()
    for i in missing(items):
        tally.missing += 1
        try:
            add(i.node_id)
        except Unavailable:
            tally.failed += 1
            tally.say(f"  {i.name} could not be added", err=True)
            continue
        tally.added += 1
        tally.say(f"  {i.name} ({i.kind}) added")
    return tally
