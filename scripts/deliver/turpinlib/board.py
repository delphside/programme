"""The board model (`scripts/board/release.py`), imported in-process (design §4).

Before the model is called, this sets what `board-release.py`'s `_environment()`
sets: the GitHub repository from `TURPIN_GH_REPO` or the origin URL, and the
programme file where none is named. The model reads git in the current folder,
so a caller runs it inside `in_repo`.
"""

from __future__ import annotations

import contextlib
import os
import sys
from pathlib import Path
from typing import Iterator

from . import settings

SCRIPTS = Path(__file__).resolve().parents[2]   # scripts/, which holds the `board` package


def _import():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    from board import profile, release, repo, sources
    return profile, release, repo, sources


def repo_module():
    """The model's `repo` module."""
    return _import()[2]


def unavailable():
    """The model's `Unavailable`, which it raises for a read it cannot make."""
    return _import()[3].Unavailable


def record_version_unknown():
    """The model's `RecordVersionUnknown`, a kind of `Unavailable`, for a record
    version this tool does not read."""
    return _import()[2].RecordVersionUnknown


def release_module():
    """The model's `release` module, with its environment set."""
    profile, release, repo, sources = _import()
    slug = os.environ.get(settings.ENV_GH_REPO) or repo.origin_slug()
    if not slug:
        raise sources.Unavailable(
            f"cannot tell the GitHub repository (set {settings.ENV_GH_REPO}=owner/name)")
    os.environ[profile.ENV_REPOSITORY] = slug
    if not os.environ.get(profile.ENV_CONFIG):
        own = SCRIPTS.parent / "config" / "programme.toml"
        if own.is_file():
            os.environ[profile.ENV_CONFIG] = str(own)
    return release


@contextlib.contextmanager
def in_repo(path: Path | str) -> Iterator[None]:
    """Run in the application's checkout, where the model reads git."""
    here = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(here)
