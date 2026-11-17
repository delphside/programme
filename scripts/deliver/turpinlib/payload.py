"""Assembling the payload (design §3 *Repositories and what they hold*): the files a host
runs to deploy an image set, which `build` puts in `<worktree>/.turpin-payload/` for the
Dockerfile to copy to `/turpin/` in the payload image. It holds nothing secret.

- the deploy steps and their libraries come from the `programme` submodule at the commit
  the built commit pins (the running tool's own where it pins none), read with
  `git archive`, so a deploy runs what that commit was built and tested with;
- the hooks, the joined files and the host files come from the built commit's tree, never
  the operator's working tree;
- `profile.json` is the commit's profile cut to the keys a host reads (the board's `shipping.HOST_READS`), so a change to
  any other key (a board key, say) changes nothing the image carries.
"""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import tarfile
import tempfile
import tomllib
from pathlib import Path

from . import board, gitrepo
from .model import BusinessError, Reason, TechnicalError

TOOL = Path(__file__).resolve().parents[1]      # scripts/deliver: the running tool's own steps


def pinned_programme(repo: Path, sha: str) -> str | None:
    """The commit the application pins its `programme` submodule at, in commit `sha`."""
    found = gitrepo.git(repo, "ls-tree", sha, "programme").split()
    return found[2] if len(found) >= 3 and found[1] == "commit" else None


def _tool_files(repo: Path, sha: str, into: Path) -> Path:
    """The folder holding `payload/` and `lib/` of the tool this commit was built with."""
    shipping = board.shipping_module()
    pinned = pinned_programme(repo, sha)
    if pinned is None:
        return TOOL
    programme = repo / "programme"
    try:
        archive = subprocess.run(["git", "-C", str(programme), "archive", pinned,
                                  shipping.PAYLOAD_DIR, shipping.LIB_DIR],
                                 capture_output=True, check=True, stdin=subprocess.DEVNULL).stdout
    except (subprocess.CalledProcessError, OSError) as exc:
        raise TechnicalError.make(Reason.GIT_FAILED,
                                  f"the programme submodule does not hold the commit {pinned[:12]} that "
                                  f"{sha[:12]} pins: run git submodule update --init") from exc
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(into, filter="data")
    return into / "scripts" / "deliver"


def _copy_listed(tree: Path, names: list[str], into: Path, what: str) -> None:
    for name in names:
        source = tree / name
        if not source.exists():
            raise BusinessError.make(Reason.NOT_IN_REPOSITORY, f"the profile lists {what} {name}, "
                                     f"which the commit does not have", metadata={"file": name})
        target = into / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)


def assemble(repo: Path, tree: Path, sha: str, dest: Path) -> None:
    """Write the payload of commit `sha`, checked out in `tree`, to `dest`."""
    try:
        profile = tomllib.loads((tree / "app-profile.toml").read_text())
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise BusinessError.make(Reason.PROFILE_UNREADABLE, "cannot read the profile at the commit",
                                 metadata={"commit": sha}) from exc
    if dest.exists():
        shutil.rmtree(dest)
    for part in ("lib", "join", "host_files", "hooks"):
        (dest / part).mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="turpin-tool-") as scratch:
        tool = _tool_files(repo, sha, Path(scratch))
        shutil.copytree(tool / "payload", dest, dirs_exist_ok=True)
        for name in board.shipping_module().LIB_FILES:
            shutil.copy2(tool / "lib" / name, dest / "lib" / name)
    if (tree / "turpin" / "hooks").is_dir():
        shutil.copytree(tree / "turpin" / "hooks", dest / "hooks", dirs_exist_ok=True)
    (dest / "profile.json").write_text(json.dumps(board.shipping_module().host_profile(profile), default=str))
    turpin = profile.get("turpin") or {}
    joins = set(turpin.get("join") or [])
    for env in (profile.get("environments") or {}).values():
        joins |= set(env.get("join") or [])
    _copy_listed(tree, sorted(joins), dest / "join", "join")
    _copy_listed(tree, [h["src"] for h in turpin.get("host_files") or []], dest / "host_files", "host file")
