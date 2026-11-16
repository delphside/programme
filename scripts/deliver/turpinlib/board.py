"""The board model (`scripts/board/release.py`), imported in-process (design §4).

Before the model is called, this sets what `board-release.py`'s `_environment()`
sets: the GitHub repository from `TURPIN_GH_REPO` or the origin URL, and the
programme file where none is named. The model reads git in the current folder,
so a caller runs it inside `in_repo`.
"""

from __future__ import annotations

import contextlib
import os
import signal
import sys
from pathlib import Path
from typing import Any, Iterator

from . import settings
from .model import BusinessError, ProfileError, Reason, TechnicalError
from .runlog import RunLog

SCRIPTS = Path(__file__).resolve().parents[2]   # scripts/, which holds the `board` package


def _import():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    from board import profile, release, repo, sources
    return profile, release, repo, sources


def shipping_module():
    """The model's `shipping` module, which names the programme files the payload carries."""
    _import()
    from board import shipping
    return shipping


def repo_module():
    """The model's `repo` module."""
    return _import()[2]


def profile_error():
    """The model's `ProfileError`, which it raises (a `SystemExit`) for a key missing or malformed."""
    return _import()[0].ProfileError


def model_profile():
    """The model's `profile` module."""
    return _import()[0]


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
        raise TechnicalError.make(
            Reason.BOARD_REPOSITORY_UNKNOWN,
            f"the GitHub repository is not known: set {settings.ENV_GH_REPO}=owner/name")
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


class _Stderr:
    """Where the model's own standard error goes while it is called: the run log, so the
    operator sees the one message `calling` raises (design §4)."""

    def __init__(self, log: RunLog):
        self.log = log

    def write(self, text: str) -> int:
        if text.strip():
            self.log.event("board-stderr", text=text.strip())
        return len(text)

    def flush(self) -> None:
        pass


def board_unavailable(exc: Exception, what: str = "the board could not be read for the settle") -> TechnicalError:
    """The one place a board that cannot answer becomes our error: a blip (75) where the model
    says the failure is transient (`Unavailable.transient`), else fundamental (2): fix the login,
    the repository or git. (A repository it cannot name is configuration, and
    `board.release_module` raises that itself, exit 2.)"""
    blip = bool(getattr(exc, "transient", False))
    hint = "try again later" if blip else "fix the GitHub login, the repository or git, then try again"
    return TechnicalError.make(Reason.BOARD_UNAVAILABLE, f"{what}: {hint}",
                               metadata={"tool_text": str(exc)}, blip=blip)


@contextlib.contextmanager
def held_interrupt() -> Iterator[list[bool]]:
    """Hold a Ctrl+C while a call runs: `subprocess.run` kills its child on one, so a call that must
    run to its end (a push, a model call) runs inside this. The list is non-empty if one arrived; the
    caller raises `KeyboardInterrupt` once the call has returned. One mechanism for every such call."""
    pressed: list[bool] = []
    try:
        previous = signal.signal(signal.SIGINT, lambda *_: pressed.append(True))
    except ValueError:      # not the main thread: nothing to hold
        previous = None
    try:
        yield pressed
    finally:
        if previous is not None:
            signal.signal(signal.SIGINT, previous)


@contextlib.contextmanager
def no_new_calls(pressed: list[bool]) -> Iterator[None]:
    """While a Ctrl+C is held (`pressed` is not empty) the model starts no further `gh` or `git`:
    the call under way ends, and each action after it is left undone for a rerun. `settle` runs
    inside this, so an interruption finishes the action under way and starts no other."""
    sources = _import()[3]
    sources.refuse_new_calls = lambda: bool(pressed)
    try:
        yield
    finally:
        sources.refuse_new_calls = lambda: False


@contextlib.contextmanager
def calling(what: str, log: RunLog, interrupted: str) -> Iterator[None]:
    """Around a call into the board model (design §4, §6): what it raises becomes a result,
    and a Ctrl+C is held until the call ends.

    - `Unavailable` (a read of GitHub or git that could not be made) is a technical error:
      a blip, exit 75, where the model says `transient`, else fundamental, exit 2. It is
      never read as refused or as empty;
    - `RecordVersionUnknown` is a business error: a reader refuses a record it does not know;
    - the model's `ProfileError` is fundamental, exit 2, naming the key;
    - the model's standard error goes to the run log;
    - a Ctrl+C reaches `turpin` alone (the model starts `gh` and `git` in a session of their
      own), so the call already running is let finish, then `KeyboardInterrupt` says
      `interrupted`: the front end exits 130.
    """
    with held_interrupt() as pressed:
        try:
            with contextlib.redirect_stderr(_Stderr(log)):      # type: ignore[type-var]
                yield
        except record_version_unknown() as exc:
            err: BaseException = BusinessError.make(
                Reason.RECORD_VERSION_UNKNOWN,
                f"{what}: a release tag holds a record version this tool does not read",
                metadata={"tool_text": str(exc)})
        except unavailable() as exc:
            err = board_unavailable(exc, f"{what} could not be read")
        except profile_error() as exc:
            err = ProfileError.at(Reason.BOARD_PROFILE_ERROR,
                                  f"{what}: the profile is wrong: fix it ({exc.message})")
        except KeyboardInterrupt:       # any that reaches here (a held one is raised below) says `interrupted`
            raise KeyboardInterrupt(interrupted) from None
        except BaseException:
            if pressed:
                raise KeyboardInterrupt(interrupted) from None
            raise
        else:
            err = None
    if pressed:
        raise KeyboardInterrupt(interrupted)
    if err is not None:
        raise err


@contextlib.contextmanager
def working(repo: Path | str, what: str, log: RunLog, interrupted: str) -> Iterator[Any]:
    """The model's `release` module, in the application's checkout, called under `calling`."""
    with in_repo(repo), calling(what, log, interrupted):
        yield release_module()
