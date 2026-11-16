"""`turpin promote APP < request`: on the release copier, copy a build's image set from
candidates to releases by digest, then the release's record (design §3 *Operations*, §6, §10).

Called by `release` and by `deploy --unrecorded`, on `[turpin.release].copy_on`, which runs it
with that machine's own login. The registry port refuses to write a version tag or a
`VERSION-record` that releases already holds with other contents, and a copy that is already
there is a no-op, so a call repeated after a dropped connection is safe, and a resumed
release copies only what is missing.

The request (one JSON object on the first line of standard input):

    login        the copier's credential kind, `[turpin.release].copy_login`
    candidates   the candidates repository's name
    releases     the releases repository's name
    commit       the full SHA of the build
    images       each image's name to its digest, as candidates holds it
    version      the release's version, or null for an `--unrecorded` copy (SHA-IMAGE tags)
    record       the release's record, as the tag's message holds it, or null with no version

It prints a line per tag, `copied TAG` or `kept TAG`.
"""

from __future__ import annotations

from .. import remote
from ..cli import Args, Context
from ..model import (Build, ComponentKind, FormError, ReleaseRecord, RepositoryKind, Result, Version)
from ..registry import connect

USAGE = "usage: turpin promote APP < request\n"
MIN_ARGS = MAX_ARGS = 1
FLAGS: dict[str, str] = {}
WHAT = "promote"


def run(args: Args, ctx: Context) -> Result:
    app = remote.application(args.positional[0])
    body = remote.read_request(WHAT)
    watcher = remote.Watcher()
    login = remote.login_kind(body, WHAT)
    candidates = remote.repository(body, "candidates", RepositoryKind.CANDIDATES, WHAT)
    releases = remote.repository(body, "releases", RepositoryKind.RELEASES, WHAT)
    commit = remote.commit_of(body.get("commit"), WHAT)
    images = remote.field(body, "images", dict, WHAT)
    try:
        build = Build(commit, {str(name): remote.digest_of(text, WHAT) for name, text in images.items()})
        version = Version.parse(body["version"]) if body.get("version") is not None else None
        record = ReleaseRecord.from_json(body["record"]) if body.get("record") is not None else None
    except FormError as exc:
        raise exc.unexpected(f"the {WHAT} request") from exc
    except (KeyError, TypeError, AttributeError) as exc:
        raise remote.unreadable(WHAT, "a record or a version is malformed") from exc
    ctx.start_log(app)
    port = connect.connect(app, connect.component_of(ComponentKind.COPIER, login), ctx.log)
    watcher.check("interrupted before the copy began: nothing was changed; run the release again")
    promoted = port.promote(candidates, releases, build, version, record)
    for tag in promoted.written:
        print(f"copied {tag}")
    for tag in promoted.skipped:
        print(f"kept {tag}")
    ctx.log.event("promoted", written=len(promoted.written), kept=len(promoted.skipped))
    return Result.ok()
