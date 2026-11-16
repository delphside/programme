"""git: fetching, tags, files at a commit, and a tag's release record (design §5).

The record's one parser is the board model's `repo.tag_record`; this module
calls it and turns what it reads into a `ReleaseRecord`. The release tags, the tag a
release pushes and the bump of `main` are the `release` command's git.
"""

from __future__ import annotations

import io
import shutil
import subprocess
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from . import board, hooks, settings
from .model import (BusinessError, FormError, Profile, ProfileError, ProgrammeError, Reason, ReleaseRecord, TechnicalError,
                    UnexpectedError, Version)

# What git prints when a credential, a key or a host name is wrong: fundamental,
# whatever else the text says (checked first).
_FUNDAMENTAL = ("Permission denied", "Host key verification failed", "Could not resolve hostname",
                "Authentication failed", "returned error: 401", "returned error: 403")
# What git prints when the remote cannot be reached for now: a blip.
_UNREACHABLE = ("Could not resolve host", "Connection timed out", "Connection refused",
                "Connection reset", "Connection closed", "Broken pipe", "unable to access",
                "Could not read from remote")


def git(repo: Path | str, *args: str, timeout: int = settings.GIT_CALL_TIMEOUT, detached: bool = False) -> str:
    """The output of `git -C repo args`. A failure is a technical error whose
    metadata holds git's text; the message holds none of it. `detached` starts it in a session of
    its own. Every call holds a Ctrl+C until git has returned (`board.held_interrupt`), since
    `subprocess.run` would kill it, and then raises `KeyboardInterrupt`: a push already running
    runs to its end, and its result is the caller's to read."""
    with board.held_interrupt() as pressed:
        outcome = _git(repo, args, timeout, detached)
    if pressed:
        raise KeyboardInterrupt
    if isinstance(outcome, BaseException):
        raise outcome
    return outcome


def _git(repo, args, timeout, detached):
    """`git`'s output, or the error it is to raise."""
    try:
        done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                              text=True, timeout=timeout, stdin=subprocess.DEVNULL, start_new_session=detached)
    except FileNotFoundError:
        return TechnicalError.make(Reason.GIT_FAILED, "git is not installed: install it")
    except subprocess.TimeoutExpired:
        return TechnicalError.make(Reason.GIT_UNREACHABLE, f"git {args[0]} timed out: try again later", blip=True)
    if done.returncode == 0:
        return done.stdout
    text = done.stderr.strip()
    if any(phrase in text for phrase in _FUNDAMENTAL):
        return TechnicalError.make(Reason.GIT_REFUSED,
                                   f"git {args[0]} was refused: fix the ssh key, the host key, the host name "
                                   f"or the login for the remote", metadata={"tool_text": text})
    if any(phrase in text for phrase in _UNREACHABLE):
        return TechnicalError.make(Reason.GIT_UNREACHABLE,
                                   f"git {args[0]} could not reach the remote: try again later",
                                   metadata={"tool_text": text}, blip=True)
    return TechnicalError.make(Reason.GIT_FAILED, f"git {args[0]} failed: fix the repository",
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


def tag_version(tag: str, prefixes: Sequence[str]) -> Version | None:
    """The version a release tag of any of `prefixes` names, or None where it is no semver."""
    for prefix in prefixes:
        if prefix and tag.startswith(prefix):
            try:
                return Version.parse(tag[len(prefix):])
            except FormError:
                return None
    return None


def release_tags(repo: Path | str, prefixes: Sequence[str]) -> dict[str, Version]:
    """Every release tag of any prefix that names a semver, with its version."""
    found: dict[str, Version] = {}
    for prefix in prefixes:
        for tag in tags(repo, prefix) if prefix else ():
            version = tag_version(tag, prefixes)
            if version is not None:
                found[tag] = version
    return found


def newest_release_tag_version(repo: Path | str, prefixes: Sequence[str]) -> Version | None:
    """The highest version among the release tags of any prefix."""
    return max(release_tags(repo, prefixes).values(), default=None)


def is_ancestor(repo: Path | str, ancestor: str, descendant: str) -> bool:
    """Whether `ancestor` is `descendant` or lies behind it (`git merge-base --is-ancestor`)."""
    try:
        done = subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", ancestor, descendant],
                              capture_output=True, text=True, timeout=settings.GIT_CALL_TIMEOUT,
                              stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TechnicalError.make(Reason.GIT_FAILED, "git merge-base could not run: fix the repository") from exc
    if done.returncode not in (0, 1) or (done.returncode == 1 and done.stderr.strip()):
        raise TechnicalError.make(Reason.GIT_FAILED, "git merge-base failed: fix the repository",
                                  metadata={"tool_text": done.stderr.strip()})
    return done.returncode == 0


def nearest_release_tag(repo: Path | str, sha: str, prefixes: Sequence[str],
                        below: Version | None = None) -> str | None:
    """The release tag of the highest version among those reachable from `sha`, and lower than
    `below` where given (a release being made, or resumed, is not its own predecessor)."""
    reachable = {tag: version for tag, version in release_tags(repo, prefixes).items()
                 if (below is None or version < below) and is_ancestor(repo, f"{tag}^{{commit}}", sha)}
    return max(reachable, key=reachable.__getitem__, default=None)


def commits_between(repo: Path | str, first: str, last: str) -> set[str]:
    """The commits reachable from `last` and not from `first`."""
    return set(git(repo, "rev-list", f"{first}..{last}").split())


def origin_has_tag(repo: Path | str, tag: str) -> bool:
    """Whether `origin` holds the tag (`git ls-remote`)."""
    return bool(git(repo, "ls-remote", "--tags", "origin", f"refs/tags/{tag}").strip())


def push_tag(repo: Path | str, tag: str, sha: str, message: str) -> None:
    """The annotated tag `tag` at `sha`, whose message is `message`, made and pushed to
    `origin`. The push is held against a Ctrl+C (`git`), so it runs to its end; it is spent
    if and only if `origin` holds the tag. A push that failed deletes the local tag again; after a
    Ctrl+C the push's own result is read from `origin`, and the tag is deleted only where
    `origin` lacks it. `KeyboardInterrupt` is raised either way."""
    with tempfile.TemporaryDirectory(prefix="turpin-tag-") as scratch:
        file = Path(scratch) / "message"
        file.write_text(message + "\n")
        git(repo, "tag", "-a", "-F", str(file), tag, sha)
    try:
        git(repo, "push", "-q", "origin", f"refs/tags/{tag}", detached=True)
    except KeyboardInterrupt:
        try:
            spent = origin_has_tag(repo, tag)
        except (TechnicalError, KeyboardInterrupt):
            spent = False
        if not spent:
            git(repo, "tag", "-d", tag)
        raise
    except BaseException:
        git(repo, "tag", "-d", tag)
        raise


def push_existing_tag(repo: Path | str, tag: str) -> None:
    """Make sure `origin` holds the local tag `tag` (a run that was killed after making it, before
    its push, leaves it only here): pushing what is already there changes nothing."""
    git(repo, "push", "-q", "origin", f"refs/tags/{tag}", detached=True)


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


def bump_main(repo: Path | str, released: Version, app: str, state: str) -> bool:
    """Bump `main` to the next patch after the released version (design §10, step 6):
    skipped, and False, where `main` already holds that or higher. The change is the
    version-only one `[versions.bump]` allows: the pattern's group replaced in the app's
    version file and in each file `versions.bump.required` lists, then the `bump` hook, in a
    worktree of `origin/main`; the subject is `versions.stamp_form` filled from
    `versions.api`. Pushed to `main` by the owner's git login."""
    from . import profile       # profile imports this module, so the import waits for the call
    git(repo, "fetch", "-q", "origin", "main")
    new = Version(released.major, released.minor, released.patch + 1)
    tree = Path(tempfile.mkdtemp(prefix="turpin-bump-"))
    try:
        git(repo, "worktree", "add", "-q", "--detach", str(tree), "origin/main")
        own = profile.version_in_tree(tree)
        if own > released or own == new:
            return False
        data = profile.profile_data(tree)
        versions = data.get("versions") or {}
        file, pattern = profile.version_source(tree)
        files = list(dict.fromkeys([*((versions.get("bump") or {}).get("required") or []), file]))
        for name in files:
            path = tree / name
            try:
                text = path.read_text()
            except OSError as exc:
                raise BusinessError.make(Reason.BUMP_FAILED, f"cannot read {name}, which the bump changes: "
                                         f"fix versions.bump.required", metadata={"file": name}) from exc
            found = pattern.search(text)
            if not found:
                raise BusinessError.make(Reason.BUMP_FAILED, f"{name} has no line the version pattern matches: "
                                         f"fix versions.bump.required", metadata={"file": name})
            path.write_text(text[:found.start(1)] + str(new) + text[found.end(1):])
        hook = hooks.find_hook(tree / "turpin" / "hooks", "bump")
        if hook is not None:
            sha = git(tree, "rev-parse", "HEAD").strip()
            hooks.run_hook(hook, hooks.HookEnv(app=app, env="release", role="controller", sha=sha,
                                               version=str(new), state=state), cwd=tree).require()
        subject = f"bump the version to {new} after releasing {released}"
        form = versions.get("stamp_form")
        if form:
            api = _api_version(tree) if "<M.N>" in form else ""
            subject = form.replace("<X.Y.Z>", str(new)).replace("<M.N>", api).replace("<subject>", subject)
        git(tree, "add", "-A")
        git(tree, "commit", "-q", "-m", subject)
        git(tree, "push", "-q", "origin", "HEAD:main", detached=True)
        return True
    finally:
        try:
            git(repo, "worktree", "remove", "--force", str(tree))
        except ProgrammeError:
            pass
        shutil.rmtree(tree, ignore_errors=True)


def _api_version(tree: Path) -> str:
    """The API version in a tree, read by the board model (`profile.current_version`, from the tree's
    own profile) for the stamp's `<M.N>`. A profile with no `versions.api`, a file that cannot be
    read and a file with no match are all the model's or a profile error, fundamental (exit 2):
    the stamp is never made with a guessed version."""
    try:
        found = board.model_profile().current_version("api", tree, own=True)
    except board.profile_error() as exc:
        raise ProfileError.at(Reason.BOARD_PROFILE_ERROR,
                              f"the stamp needs the API version: fix versions.api ({exc.message})") from exc
    if not found:
        raise ProfileError.at(Reason.BOARD_PROFILE_ERROR,
                              "the stamp needs the API version, which versions.api's file does not give: "
                              "fix versions.api or the file")
    return found
