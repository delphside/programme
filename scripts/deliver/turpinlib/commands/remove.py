"""`turpin remove APP < request`: on the builder, remove each candidate the controller chose,
through the Artifacts API, with the builder's removal credential (design §3, §6).

Called by `prune`, on `[turpin.build].on`. The controller chooses; this only removes, and
only while the tag still names the digest it chose, never a digest in `keep`, and never an
image that carries a tag outside this prune's (shared with a commit that is kept). Each
candidate is independent: one that fails is an error, the others are removed, and the exit
is 3, so `turpin prune` run again retries what is left. A call repeated after a dropped
connection is safe: what is gone is `already-gone`.

The request (one JSON object on the first line of standard input):

    login        the builder's credential kind, `[turpin.build].login`
    candidates   the candidates repository's name
    removes      the candidates chosen: each `commit`, `image` and `digest`
    keep         the digests releases holds, which are never removed

It prints a line per candidate: `removed`, `shared`, `tag-moved` or `already-gone`, then the
tag (`shared` and `tag-moved` left it, and are no error).
"""

from __future__ import annotations

import sys

from .. import remote
from ..cli import Args, Context
from ..model import (Build, ComponentKind, ProgrammeError, Reason, RepositoryKind, Result)
from ..registry import connect

USAGE = "usage: turpin remove APP < request\n"
MIN_ARGS = MAX_ARGS = 1
FLAGS: dict[str, str] = {}
WHAT = "remove"


def run(args: Args, ctx: Context) -> Result:
    app = remote.application(args.positional[0])
    body = remote.read_request(WHAT)
    watcher = remote.Watcher()
    login = remote.login_kind(body, WHAT)
    candidates = remote.repository(body, "candidates", RepositoryKind.CANDIDATES, WHAT)
    keep = [remote.digest_of(text, WHAT) for text in remote.field(body, "keep", list, WHAT)]
    removes = []
    for entry in remote.field(body, "removes", list, WHAT):
        if not isinstance(entry, dict) or not isinstance(entry.get("image"), str):
            raise remote.unreadable(WHAT, "a removal names no image")
        removes.append((remote.commit_of(entry.get("commit"), WHAT), entry["image"],
                        remote.digest_of(entry.get("digest"), WHAT)))
    removing = {connect.candidate_tag(commit, image) for commit, image, _ in removes}
    ctx.start_log(app)
    port = connect.connect(app, connect.component_of(ComponentKind.BUILDER, login, removal=True), ctx.log)
    errors: list[ProgrammeError] = []
    done = 0
    for commit, image, digest in removes:
        watcher.check(f"interrupted after {done} of {len(removes)} candidates: the rest were not touched; "
                      f"run turpin prune again")
        tag = connect.candidate_tag(commit, image)
        try:
            outcome = port.remove_candidate(candidates, Build(commit, {image: digest}), image, keep, removing)
        except ProgrammeError as exc:
            errors.append(exc)
            ctx.log.event("remove-failed", tag=tag, result=exc.result.to_json())
            print(f"turpin: not removed {tag}: {exc.result.message}", file=sys.stderr)
        else:
            done += 1
            print(f"{outcome.value} {tag}")
    if errors:
        return remote.done_with_errors(
            Reason.PRUNE_REMOVE_FAILED,
            f"{len(errors)} of {len(removes)} candidates could not be removed, and the others were: "
            f"run turpin prune again", errors)
    return Result.ok()
