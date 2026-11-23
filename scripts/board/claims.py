"""The files a pull request claims, and which pull requests share one.

Pure: no GitHub, no clock. `board-overlap.py` reads the pull requests and
hands their facts here.

A pull request claims the files it expects to change in one line of its body,
`Claims: path, path, …`. A path is relative to the repository root, bare or in
backticks; one ending `/` claims the directory and everything below it. Paths
are split on commas and white space, so a path with a space in it is not
supported. Only the first `Claims:` line counts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_LINE = re.compile(r"^[ \t]*Claims:(.*)$", re.MULTILINE)
_SEPARATORS = re.compile(r"[,\s]+")


def _clean(path: str) -> str:
    path = path.strip().strip("`'\"")
    while path.startswith("./"):
        path = path[2:]
    return path


def parse_claims(body: str | None) -> tuple[str, ...]:
    """The paths on the body's first `Claims:` line, in order and without
    repeats; none when there is no such line."""
    found = _LINE.search(body or "")
    if found is None:
        return ()
    paths = (_clean(p) for p in _SEPARATORS.split(found.group(1)))
    return tuple(dict.fromkeys(p for p in paths if p))


def touches(a: str, b: str) -> bool:
    """Whether two paths name a common file: they are equal, or one is a
    directory (it ends `/`) that holds the other."""
    a, b = _clean(a), _clean(b)
    return a == b or (a.endswith("/") and b.startswith(a)) or (b.endswith("/") and a.startswith(b))


def shared(first, second) -> tuple[str, ...]:
    """The paths two sets have in common, sorted. Where one is a directory
    holding the other, the one inside it, which is the more specific."""
    out = set()
    for a in first:
        for b in second:
            if touches(a, b):
                out.add(max(_clean(a), _clean(b), key=len))
    return tuple(sorted(out))


@dataclass(frozen=True)
class Pull:
    """An open pull request, as far as an overlap needs it."""

    repo: str
    number: int
    title: str
    changed: tuple[str, ...] = ()
    claimed: tuple[str, ...] = ()

    @property
    def ref(self) -> str:
        return f"{self.repo}#{self.number}"

    @property
    def paths(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys((*self.changed, *self.claimed)))


def against(paths, pulls) -> list[tuple[Pull, tuple[str, ...]]]:
    """Each pull request whose changed or claimed files include any of `paths`,
    with the paths shared, in the order given."""
    found = []
    for pull in pulls:
        common = shared(paths, pull.paths)
        if common:
            found.append((pull, common))
    return found


def pairs(pulls) -> list[tuple[Pull, Pull, tuple[str, ...]]]:
    """Each pair of pull requests in the same repository that share a file,
    the lower number first."""
    ordered = sorted(pulls, key=lambda p: (p.repo, p.number))
    found = []
    for i, one in enumerate(ordered):
        for two in ordered[i + 1:]:
            if one.repo != two.repo:
                continue
            common = shared(one.paths, two.paths)
            if common:
                found.append((one, two, common))
    return found
