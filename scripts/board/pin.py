"""Whether an application's pin of the programme is behind (docs/1.1).

An application carries the programme as the submodule `programme/`, pinned to a
commit of its own choosing, and a programme change reaches it only when the pin
moves. Whoever runs a programme tool checks the pin first; this is that check,
run at the start of a session so it is not left to memory. **It warns and never
moves the pin** (owner, 2026-11-09: the move stays manual).

Behind means a commit on the programme's `origin/main` that the pin lacks and
that touches a path outside `records/` and `applications/`: the same test
docs/1.1 gives by hand. One fetch of that one branch, with a short timeout; any
failure of git, the network or the layout says nothing, because a start of
session must never wait on this or fail on it.

Quiet where the pin is kept on purpose: on a `release/*` branch under test, on
an `emergency-*` branch, and on a detached HEAD at a tag (an emergency cut from
a release tag). A fetch that fails, by exit status or by timeout, says nothing,
whatever ref an earlier fetch left. Quiet in the
programme's own repository, which has no pin.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from . import profile, records

FETCH_SECONDS = 5
SHOWN = 3
# The paths a programme change reaches an application by: everything but these.
OUTSIDE_RECORDS = (".", ":!records", ":!applications")


def _git(path: Path, *args: str, timeout: float = 5) -> subprocess.CompletedProcess:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    return subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True,
                          timeout=timeout, env=env)


def kept_on_purpose(root: Path) -> bool:
    """A release branch under test, an emergency branch, or a detached HEAD at a tag."""
    head = _git(root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if head.startswith(("release/", "emergency-")):
        return True
    if head == "HEAD":
        return _git(root, "describe", "--exact-match", "--tags", "HEAD").returncode == 0
    return False


def warning(root: Path | None = None) -> str | None:
    """The warning for the application at `root`, or None to say nothing."""
    try:
        root = root or profile.app_root()
        pinned = records.generic(root)
        if not pinned.is_dir():
            return None
        # No gitlink at `programme` in HEAD: this is the programme itself, or a copy.
        pin = _git(root, "rev-parse", "--verify", "-q", "HEAD:" + pinned.name)
        if pin.returncode != 0 or kept_on_purpose(root):
            return None
        sha = pin.stdout.strip()
        # A fetch that fails leaves a ref that may be old, and an old answer is
        # not one to warn on.
        if _git(pinned, "fetch", "--quiet", "origin", "main", timeout=FETCH_SECONDS).returncode != 0:
            return None
        log = _git(pinned, "log", "--oneline", f"{sha}..refs/remotes/origin/main", "--",
                   *OUTSIDE_RECORDS)
        if log.returncode != 0:
            return None
        lines = log.stdout.splitlines()
    except (OSError, subprocess.SubprocessError, SystemExit, profile.ProfileError):
        return None
    if not lines:
        return None
    more = f"; and {len(lines) - SHOWN} more" if len(lines) > SHOWN else ""
    return (f"The programme pin is {len(lines)} commit(s) behind origin/main in what applications "
            f"use ({'; '.join(lines[:SHOWN])}{more}). Move it before running programme tools "
            f"(docs/1.1 *Whoever runs a programme tool from an application checks its pin first*); "
            f"nothing has moved it.")
