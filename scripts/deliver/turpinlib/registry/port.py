"""The registry port (design §3 *Operations*): the one interface through which Turpin
reaches the registry, in the domain model's types. It names no tool, protocol or tag
form; an adapter implements it (`ocir/adapter.py`).

An error leaves an operation as one of the three types (docs/1.10): a `BusinessError`
(a request refused on validation, the keep list, no overwrite, or a thing the operation
needed that is not there), a `TechnicalError` (a blip, `blip` true, or a fundamental
one) or an `UnexpectedError`. *Absent* is an answer, not an error: `None`.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Collection, Mapping, Protocol, Sequence

from .. import settings
from ..model import (BusinessError, Build, Component, Digest, FormError, Image, Reason, Repository,
                     ReleaseRecord, TechnicalError, UnexpectedError, Version)

__all__ = ["BuildImage", "ReleaseImage", "Promoted", "Removal", "RegistryPort", "resolve_commit",
           "BusinessError", "TechnicalError", "UnexpectedError"]


@dataclass(frozen=True)
class BuildImage:
    """One image of a commit's build, to be found in candidates."""
    commit: str
    name: str


@dataclass(frozen=True)
class ReleaseImage:
    """One image of a release, to be found in releases."""
    version: Version
    name: str


@dataclass(frozen=True)
class Promoted:
    """What a promotion left in releases: each image's digest, the record where there is
    one, and which of the images and the record it wrote and which were already there."""
    images: Mapping[str, Digest]
    record: ReleaseRecord | None
    written: tuple[str, ...]
    skipped: tuple[str, ...]


class Removal(enum.Enum):
    """How a candidate removal ended; none is an error."""
    REMOVED = "removed"
    TAG_MOVED = "tag-moved"          # the tag no longer names the chosen digest: left
    ALREADY_GONE = "already-gone"    # the tag is not there any more
    SHARED = "shared"                # the image carries a tag this prune does not remove: left


class RegistryPort(Protocol):
    """Turpin's operations on the registry. Every one but `ensure_credentials` runs under
    the credentials that call set."""

    def ensure_credentials(self, component: Component) -> None:
        """Put the component's credentials in place (design §3 *Logins*)."""

    def make_login(self, component: Component, user: str, token: str) -> None:
        """Make the component's `docker-config` login, from the user and the token the
        owner typed (`turpin login`); it names the component's auth file and nothing else."""

    def find_image(self, repository: Repository, what: BuildImage | ReleaseImage | Digest) -> Image | None:
        """The image, or *absent*. Found by a digest, `Image.name` is ''."""

    def list_versions(self, repository: Repository) -> tuple[str, ...] | tuple[Version, ...]:
        """The commits built in candidates (full SHAs, sorted), or the `Version`s in
        releases (sorted)."""

    def store_build(self, repository: Repository, commit: str, layouts: Mapping[str, Path]) -> Build:
        """Push each image's OCI layout as the commit's image, and give the `Build` with the
        digests the registry stores."""

    def read_record(self, repository: Repository, version: Version) -> ReleaseRecord | None:
        """The release's record, or *absent*."""

    def promote(self, candidates: Repository, releases: Repository, build: Build,
                version: Version | None, record: ReleaseRecord | None) -> Promoted:
        """Copy the build's images by digest into releases, then the record; with neither
        a version nor a record (`--unrecorded`), the images as the commit's own tags."""

    def remove_candidate(self, repository: Repository, build: Build, image: str,
                         keep: Collection[Digest], removing: Collection[str]) -> Removal:
        """Remove one image of a build, at the digest the build names, unless it is in the
        keep list (a business error), its tag has moved, or it carries a tag outside
        `removing`, the tags this prune removes (left, no error)."""


def resolve_commit(commits: Sequence[str], short: str, where: str) -> str:
    """The one full SHA `short` starts, from *list versions*; none or several is a
    business error naming `where`, the argument (R48). A short SHA is checked for its
    form before it is looked up."""
    if not re.fullmatch(r"[0-9a-f]+", short) or len(short) < settings.SHORT_SHA_MIN:
        raise FormError("commit", short, f"hexadecimal and at least {settings.SHORT_SHA_MIN} characters",
                        "NOT_A_COMMIT").business(where)
    matches = sorted({c for c in commits if c.startswith(short)})
    if not matches:
        raise BusinessError.make(Reason.SHORT_SHA_NO_BUILD, f"{where}: no build starts with {short}: build it first",
                                 metadata={"source": where})
    if len(matches) > 1:
        raise BusinessError.make(Reason.SHORT_SHA_AMBIGUOUS,
                                 f"{where}: {short} starts {len(matches)} builds: give more of the SHA",
                                 metadata={"source": where, "matches": matches})
    return matches[0]
