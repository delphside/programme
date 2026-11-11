"""How large a document or an issue body may grow before it is restructured.

The programme's docs/1.5 *A document stays under 25 KB* owns the rule. This is
its one implementation (docs/1.10 *One place for each rule*): the documents'
measure, `scripts/docs/doc-size.py`, and `board-check.py`'s section on issue
bodies both ask here, so the two cannot disagree about the number.

A measure, not a gate: an oversized document is reported, and the weekly
`document-review` proposes how to split it (docs/1.4). Pure: paths and sizes
in, findings out.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Sequence

# About 25 KB (owner, 2026-11-11). Counted in bytes of UTF-8, as a file's size
# is, so a document and an issue body are measured alike. GitHub refuses an
# issue body over 65,536 characters, so a body reported here still has room.
LIMIT_BYTES = 25 * 1024


# What the limit leaves out: what docs/1.4's `document-review` leaves out, since
# that is where a restructure is proposed. A log or a report records a moment
# and is never reworked; a test fixture is data; a change folder's documents
# belong to their project, except its README and an activity's runbook.
# Generated documents are the caller's to leave out, from the technical profile.
_EXEMPT = (
    re.compile(r"(^|/)(tests?|fixtures?)/"),
    re.compile(r"^records/2\.4-weekly-digest/"),
    re.compile(r"(^|/)3\.\d+\.3-capacity-plan/"),
    re.compile(r"-delivery-log\.md$"),
    re.compile(r"-report\.md$"),
    # The design map, drawn by design-map.py from the Structurizr sources.
    re.compile(r"(^|/)docs/\d+\.2\.0-design-map\.md$"),
)
_CHANGE_FOLDER = re.compile(r"^records/2\.5-changes/|(^|/)3\.\d+\.7-changes/")


def exempt(path: str) -> bool:
    """Whether a document, by its path in its repository, is outside the limit."""
    if any(p.search(path) for p in _EXEMPT):
        return True
    if _CHANGE_FOLDER.search(path):
        name = path.rsplit("/", 1)[-1]
        return not (name == "README.md" or "runbook" in name)
    return False


@dataclass(frozen=True)
class Oversized:
    name: str       # a path, or `#N title` for an issue
    size: int       # bytes


def size_of(text: str) -> int:
    return len(text.encode("utf-8"))


def oversized(items: Iterable[tuple[str, int]],
              limit: int = LIMIT_BYTES) -> list[Oversized]:
    """The items over the limit, largest first."""
    found = [Oversized(name, size) for name, size in items if size > limit]
    return sorted(found, key=lambda o: (-o.size, o.name))


def kb(size: int) -> str:
    return f"{size / 1024:.0f} KB"


def render(found: Sequence[Oversized], what: str, colour: bool = True) -> str:
    """One line per oversized item, under a heading naming what was measured."""
    bold = (lambda s: f"\033[1m{s}\033[0m") if colour else (lambda s: s)
    dim = (lambda s: f"\033[2m{s}\033[0m") if colour else (lambda s: s)
    yellow = (lambda s: f"\033[33m{s}\033[0m") if colour else (lambda s: s)
    green = (lambda s: f"\033[32m{s}\033[0m") if colour else (lambda s: s)

    out = [f"{bold('SIZE')}  {dim(f'{what} over {kb(LIMIT_BYTES)}: restructure at the weekly document-review')}"]
    if not found:
        out.append(f"  {green('ok')} {dim(f'no {what} over the limit')}")
        return "\n".join(out)
    for o in found:
        out.append(f"  {yellow('!')} {kb(o.size):>7}  {o.name}")
    return "\n".join(out)
