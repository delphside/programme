"""git: fetching, tags, files at a commit, and a tag's release record (design §5).

The record's one parser is the board model's `repo.tag_record`; this module
calls it and turns what it reads into a `ReleaseRecord`. The bump of `main` and
the other release steps arrive with the `release` command.
"""

from __future__ import annotations

import io
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from . import board, settings
from .model import (BusinessError, FormError, Profile, Reason, ReleaseRecord, TechnicalError,
                    UnexpectedError)

# What git prints when a credential, a key or a host name is wrong: fundamental,
# whatever else the text says (checked first).
_FUNDAMENTAL = ("Permission denied", "Host key verification failed", "Could not resolve hostname",
                "Authentication failed", "returned error: 401", "returned error: 403")
# What git prints when the remote cannot be reached for now: a blip.
_UNREACHABLE = ("Could not resolve host", "Connection timed out", "Connection refused",
                "Connection reset", "Connection closed", "Broken pipe", "unable to access",
                "Could not read from remote")


def git(repo: Path | str, *args: str, timeout: int = settings.GIT_CALL_TIMEOUT) -> str:
    """The output of `git -C repo args`. A failure is a technical error whose
    metadata holds git's text; the message holds none of it."""
    try:
        done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                              text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    except FileNotFoundError as exc:
        raise TechnicalError.make(Reason.GIT_FAILED, "git is not installed: install it") from exc
    except subprocess.TimeoutExpired as exc:
        raise TechnicalError.make(Reason.GIT_UNREACHABLE, f"git {args[0]} timed out: try again later",
                                  blip=True) from exc
    if done.returncode == 0:
        return done.stdout
    text = done.stderr.strip()
    if any(phrase in text for phrase in _FUNDAMENTAL):
        raise TechnicalError.make(Reason.GIT_REFUSED,
                                  f"git {args[0]} was refused: fix the ssh key, the host key, the host name "
                                  f"or the login for the remote", metadata={"tool_text": text})
    if any(phrase in text for phrase in _UNREACHABLE):
        raise TechnicalError.make(Reason.GIT_UNREACHABLE,
                                  f"git {args[0]} could not reach the remote: try again later",
                                  metadata={"tool_text": text}, blip=True)
    raise TechnicalError.make(Reason.GIT_FAILED, f"git {args[0]} failed: fix the repository",
                              metadata={"tool_text": text, "args": list(args)})


def toplevel(start: Path | str) -> Path:
    """The working tree `start` is in."""
    try:
        return Path(git(start, "rev-parse", "--show-toplevel").strip())
    except TechnicalError as exc:
        raise TechnicalError.wrap(exc, Reason.NOT_IN_REPOSITORY,
                                  f"{start} is not in a git repository: run from the "
                                  f"application's checkout or set {settings.ENV_REPO}") from exc


def show(repo: Path | str, sha: str, path: str) -> str:
    """A file's text at a commit (`git show SHA:path`)."""
    return git(repo, "show", f"{sha}:{path}")


def fetch_tags(repo: Path | str) -> None:
    """`git fetch --tags`, before a tag is read (design §10)."""
    git(repo, "fetch", "--tags", "--quiet", "origin")


def tags(repo: Path | str, prefix: str) -> list[str]:
    """The tags starting with `prefix`."""
    return git(repo, "tag", "--list", f"{prefix}*").split()


def record_of_tag(repo: Path | str, tag: str) -> ReleaseRecord | None:
    """The record a release tag carries, or None for a tag that predates the tool.

    A record version this tool does not know is a business error
    (`RECORD_VERSION_UNKNOWN`) the caller treats by its own table (design §10). A
    record whose fields fail their form is an unexpected error: `turpin` wrote it.
    A git failure is a technical error. The parser is the board model's.
    """
    if not git(repo, "tag", "--list", tag).strip():
        raise BusinessError.make(Reason.TAG_NOT_FOUND, f"there is no tag {tag}: name a release tag")
    with board.in_repo(repo):
        try:
            data = board.repo_module().tag_record(tag)
        except board.record_version_unknown() as exc:
            raise BusinessError.make(Reason.RECORD_VERSION_UNKNOWN,
                                     f"tag {tag} holds a record version this tool does not read",
                                     metadata={"tag": tag, "tool_text": str(exc)}) from exc
        except board.unavailable() as exc:
            raise TechnicalError.make(Reason.GIT_FAILED, f"git could not read tag {tag}: fix the repository",
                                      metadata={"tool_text": str(exc)}) from exc
    if data is None:
        return None
    try:
        return ReleaseRecord.from_json(data)
    except FormError as exc:
        raise exc.unexpected(f"the record on tag {tag}") from exc
    except (KeyError, TypeError, AttributeError) as exc:
        raise UnexpectedError.make(Reason.RECORD_MALFORMED,
                                   f"the record on tag {tag} is malformed: raise it as an issue",
                                   metadata={"tag": tag}) from exc


def bump_main(repo: Path | str, version: str) -> None:
    """Bump `main` to the next patch after the released version (design §10, step 6)."""
    raise NotImplementedError("bump_main arrives with the release command")


def export_paths(repo: Path | str, sha: str, paths: Iterable[str], into: Path) -> bool:
    """The commit's `paths`, written under `into` (`git archive`): the commit's own files, never
    the working tree's. False where the commit is not in the repository or holds none of them."""
    try:
        git(repo, "cat-file", "-e", f"{sha}^{{commit}}")
        done = subprocess.run(["git", "-C", str(repo), "archive", sha, *paths], capture_output=True,
                              timeout=settings.GIT_CALL_TIMEOUT, stdin=subprocess.DEVNULL)
        if done.returncode != 0:
            return False
        with tarfile.open(fileobj=io.BytesIO(done.stdout)) as archive:
            archive.extractall(into, filter="data")
    except (TechnicalError, tarfile.TarError, FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return True


def tag_for_version(repo: Path, prof: Profile, version: str) -> str | None:
    """The tag naming `version` under any of the profile's prefixes, or None."""
    for prefix in (prof.tag_prefix, *prof.history_prefixes):
        if f"{prefix}{version}" in tags(repo, prefix):
            return f"{prefix}{version}"
    return None


def _tag_made(repo: Path, tag: str) -> int:
    return int(git(repo, "for-each-ref", f"refs/tags/{tag}", "--format=%(creatordate:unix)").strip() or 0)


def newest_release_made(repo: Path, prof: Profile) -> str:
    """When the newest release tag, of any prefix, was made, as the host writes `deployed`."""
    newest = 0
    for prefix in (prof.tag_prefix, *prof.history_prefixes):
        for tag in tags(repo, prefix):
            newest = max(newest, _tag_made(repo, tag))
    return datetime.fromtimestamp(newest, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
