"""`turpin settle VERSION`: the board to what the record says shipped (design §12).

The record is read from the release's tag; the board model acts on exactly what it lists
and skips what is done, so a rerun is harmless and the command has no pivot. An action
that fails is an error: the others still run, the items left are named, and the exit is 3,
the message naming `turpin settle VERSION`. `settle_version` is also what a production
deploy runs after its pivot.
"""

from __future__ import annotations

import sys
from pathlib import Path

from .. import board, gitrepo, profile
from ..cli import Args, Context
from ..model import (BusinessError, ErrorType, Outcome, Profile, ProfileError, Reason, Result, TechnicalError,
                     Version, read_input)
from ..runlog import RunLog, expected_gates

USAGE = "usage: turpin settle VERSION\n"
MIN_ARGS = MAX_ARGS = 1
FLAGS: dict[str, str] = {}


def settle_version(repo: Path, prof: Profile, version: str, log: RunLog) -> Result:
    """Settle `version` from its tag's record. OK where the board is as the record says;
    a business error (1) where the tag has no record, a profile error (2) where the profile names no
    announcement, an error result (exit 3) where an action failed. A read
    of the board that cannot be made at all is raised, by its type."""
    try:
        gitrepo.fetch_tags(repo)
    except TechnicalError as exc:
        log.event("fetch-tags-failed", reason=exc.result.reason)
    tag = gitrepo.tag_for_version(repo, prof, version)
    if tag is None:
        raise BusinessError.make(Reason.TAG_NOT_FOUND, f"settle: there is no tag for {version}: name a released version",
                                 metadata={"version": version})
    try:
        record = gitrepo.record_of_tag(repo, tag)
    except BusinessError as exc:
        if exc.result.reason != Reason.RECORD_VERSION_UNKNOWN.value:
            raise
        record = None
    if record is None:
        raise BusinessError.make(Reason.SETTLE_NO_RECORD,
                                 f"settle: {tag} has no record this tool reads: nothing to settle",
                                 metadata={"tag": tag})
    if not prof.announcement:
        raise ProfileError.at(Reason.SETTLE_NO_ANNOUNCEMENT, "settle: the profile has no release.announcement: set it",
                              tag=tag)
    try:
        with board.in_repo(repo):
            module = board.release_module()
            done = module.settle(record.to_json(), prof.announcement, tag)
    except board.profile_error() as exc:
        raise TechnicalError.make(Reason.PROFILE_UNREADABLE,
                                  "the board model could not read the profile or the programme file: fix it",
                                  metadata={"exit": str(exc)}) from exc
    except board.unavailable() as exc:
        raise board.board_unavailable(exc) from exc
    log.event("settle", version=version, done=done.get("done", []), left=done.get("left", []))
    if done["settled"]:
        print(f"settled {version}")
        return Result.ok()
    if done.get("why"):
        print(f"  because: {done['why']}", file=sys.stderr)
    left = " ".join(done["left"])
    return Result(Outcome.ERROR, ErrorType.TECHNICAL, False, Reason.SETTLE_INCOMPLETE.value,
                  message=f"settle of {version} failed; left to do: {left}; rerun turpin settle {version}",
                  metadata={"left": done["left"], "done": done["done"]})


def run(args: Args, ctx: Context) -> Result:
    repo = profile.repo_dir()
    prof = profile.read_working_tree(repo)
    ctx.start_log(prof.application, expected_gates("settle"))
    version = str(read_input("VERSION", Version.parse, args.positional[0].removeprefix("v")))
    try:
        return settle_version(repo, prof, version, ctx.log)
    except KeyboardInterrupt:
        raise KeyboardInterrupt(f"interrupted while settling: what was done stays done, and the release is live; "
                                f"run turpin settle {version} to finish") from None
