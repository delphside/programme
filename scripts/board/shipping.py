"""What reaches the image — decided once.

**`programme/docs/1.2-change-lifecycle.md` is the authority**, under *Route* in §2.15: anything
built into the image is Production Release, and everything else in the
repository is one of the two repository routes. This is that rule in the form
code can apply, written as the *exceptions* rather than the members: the list
of things that ship grows whenever a crate is added, and the list of things
that do not is stable.

**The list is the application's.** Since #485 stage 2 it is the technical
profile's `ships.non_shipping` (regular expressions, matched from the start of
a path), and a version-only bump is described by `versions.bump`; nothing here
names a path. Tile Lite Elite's reasons for each entry are in its profile's
comments and the application's artefact register (`3.n.2`),
*What counts as an artefact*: a test exists to hold an artefact to its
behaviour and is delivered with it.

**By path, and that is its limit.** A dependency added only for an example, or
lock-file lines for another platform, change the manifest and lock file and so
count as reaching the image though the bytes do not change (#404, #421).

Owned here since 2026-09-26; it was `shipping-paths.sh`'s `NON_SHIPPING`, which
now asks `programme/scripts/board/board-shipping.py` (#421). Paths in, answers
out; the profile is the only thing read.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Iterable, Sequence

from . import profile, repo

# The programme pin is a path like any other, and `ships.non_shipping` decides it (Tile Lite Elite's
# says `programme$`: the pin is not built into its image), **unless the application sets
# `ships.carries_payload = true`**: its image then carries Turpin's deploy steps from the pinned
# programme (design 117 §8, *The payload*), and a pin move ships exactly where it changes one of
# the files `CARRIED` names, whatever `non_shipping` says of the path `programme`. These are the
# files the payload is made of: `turpinlib/payload.py` reads them from here, so what is carried
# and what ships are one list.
PIN = "programme"
PAYLOAD_DIR = "scripts/deliver/payload"
LIB_DIR = "scripts/deliver/lib"
LIB_FILES = ("common.sh", "toml.sh", "toml.awk")


def carried(path: str) -> bool:
    """Whether a path in the programme is one the payload carries into the image."""
    return path.startswith(PAYLOAD_DIR + "/") or path in {f"{LIB_DIR}/{name}" for name in LIB_FILES}


def carries_payload() -> bool:
    """Whether the application's image carries the payload (`ships.carries_payload`)."""
    return profile.technical().flag("ships.carries_payload")


@lru_cache(maxsize=8)
def _compiled(patterns: tuple[str, ...]) -> "re.Pattern[str]":
    return re.compile("^(" + "|".join(patterns) + ")")


def _non_shipping() -> "re.Pattern[str]":
    return _compiled(tuple(profile.technical().strings("ships.non_shipping")))


def reaches_image(path: str) -> bool:
    """Whether a repository path is built into, or shipped with, the image."""
    return not _non_shipping().match(path)


def image_paths(paths: Iterable[str], pin_ships: bool = False) -> list[str]:
    """The paths, of these, that reach the image, in the order given. Where the application carries
    the payload, the pin is judged by `pin_ships` (whether its move changes what is carried) and
    not by `non_shipping`."""
    if carries_payload():
        return [p for p in paths if p and (pin_ships if p == PIN else reaches_image(p))]
    return [p for p in paths if p and reaches_image(p)]


def pin_ships(old: str, new: str) -> bool:
    """Whether moving the programme pin from `old` to `new` changes a file the payload carries.
    Where the submodule cannot say what changed, it does: the safe direction."""
    changed = repo.programme_paths_between(old, new, PIN)
    return changed is None or any(carried(p) for p in changed)


def pin_move_ships(base: str, head: str) -> bool:
    """Whether the pin moved between `base` and `head` in a way that ships. Never where the
    application does not carry the payload."""
    if not carries_payload():
        return False
    moved = repo.pin_move(base, head, PIN)
    return moved is not None and pin_ships(*moved)


def staged_pin_ships() -> bool:
    """The same for the pin move that is staged."""
    if not carries_payload():
        return False
    moved = repo.staged_pin_move(PIN)
    return moved is not None and pin_ships(*moved)


def touches_image(paths: Iterable[str], pin_moved_the_steps: bool = False) -> bool:
    """Whether a change to these paths reaches the image.

    No paths is *no*: a change that touched nothing changed nothing. `pin_moved_the_steps` counts
    only where the application carries the payload.
    """
    paths = list(paths)
    if carries_payload():
        return bool(image_paths(paths, pin_moved_the_steps))
    return bool(image_paths(paths))


def application_tooling(paths: Iterable[str]) -> list[str]:
    """The paths, of these, that are the application's own scripts, in the order given.

    The folders are the technical profile's `scripts.groups` (#485 stage 2, #447's
    grouping): what acts on the application and the environments it runs in. A
    change there is tried where it runs, on a branch, because `main` is where every
    script is run from, so a commit to `main` touching one is warned about (the
    pre-commit hook; warns, never refuses). The programme's tooling is in the
    programme repository and its tests beside it, and neither is in these folders.
    """
    folders = tuple(profile.technical().strings("scripts.groups"))
    return [p for p in paths if p and p.startswith(folders)]


def version_bump_only(files: Sequence[str], changed_lines: Sequence[str]) -> bool:
    """Whether a change is nothing but the app version moving.

    The files are the profile's `versions.bump.required`, optionally with the
    rest of `versions.bump.files`, and every changed line in them matches
    `versions.bump.line`. It is the one image change that belongs on `main` —
    the version bump after a production deploy, and the minor raised for a
    functional release (docs/4.3.3 §2.4) — and it ships no behaviour. No
    changed lines is *not* a bump: "nothing changed" must not read as
    "nothing disallowed changed".

    Owned here since 2026-09-26; it was the pre-commit hook's own function.
    """
    spec = profile.technical()
    required = spec.strings("versions.bump.required")
    allowed = spec.strings("versions.bump.files")
    line_pattern = re.compile(spec.string("versions.bump.line"))
    got = sorted(f for f in files if f)
    if not all(r in got for r in required) or any(f not in allowed for f in got):
        return False
    lines = [line for line in changed_lines if line and not line.startswith(("+++", "---"))]
    return bool(lines) and all(line_pattern.match(line) for line in lines)


def ships(files: Sequence[str], changed_lines: Sequence[str], pin_moved_the_steps: bool = False) -> bool:
    """Whether a change carries anything to release: it reaches the image, and it
    is more than the version moving. After a release `main` holds the next
    version's bump and nothing else, which ships nothing."""
    return touches_image(files, pin_moved_the_steps) and not version_bump_only(files, changed_lines)

