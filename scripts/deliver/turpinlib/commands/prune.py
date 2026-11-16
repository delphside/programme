"""`turpin prune [--dry-run]`: remove the candidates nobody needs (design §6, R36, R46).

The controller chooses, with its own read-only login and every environment's host state;
the builder removes, on `[turpin.build].on`, with its removal credential: it sends `turpin
remove` the candidates and the digests releases holds (`keep`). The controller never
removes, and never touches releases.

A candidate is removed only if the build started before the newest release was made (its
`created` label), it is not released, and no environment runs it now or ran it before
(current or previous). A tag with no record, or one this tool cannot read, counts its own
date toward the newest release and releases none of its candidates.

Prune has no pivot: each removal is independent of the others (design §6). A failure while
choosing stops with nothing removed; a candidate the builder fails to remove is an error,
the others are removed, and the exit is 3, rerun by `turpin prune`. `--dry-run` sends nothing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .. import gitrepo, hosts, profile, remote
from ..cli import Args, Context
from ..model import (BusinessError, ComponentKind, ErrorType, Outcome, Reason, Repository,
                     RepositoryKind, Result, TechnicalError)
from ..registry import connect
from ..registry.port import BuildImage, RegistryPort
from ..runlog import RunLog

USAGE = "usage: turpin prune [--dry-run]\n"
MIN_ARGS, MAX_ARGS = 0, 0
FLAGS = {"--dry-run": "switch"}


def _when(text: str) -> datetime | None:
    try:
        found = datetime.fromisoformat(text)
    except ValueError:
        return None
    return found if found.tzinfo else found.replace(tzinfo=timezone.utc)


def tag_date(repo: Path, tag: str) -> datetime:
    """When the tag was made, from git."""
    seconds = gitrepo.git(repo, "for-each-ref", f"refs/tags/{tag}", "--format=%(creatordate:unix)").strip()
    return datetime.fromtimestamp(int(seconds or 0), timezone.utc)


def released(repo: Path, prof, log: RunLog) -> tuple[datetime, set[str]]:
    """When the newest release was made, and the digests the releases' records name. A tag
    with no record, or a record version this tool does not read, counts its own date and
    releases nothing (design §10)."""
    try:
        gitrepo.fetch_tags(repo)
    except TechnicalError as exc:
        log.event("fetch-tags-failed", reason=exc.result.reason)   # a stale view only keeps more
    newest: datetime | None = None
    digests: set[str] = set()
    for prefix in (prof.tag_prefix, *prof.history_prefixes):
        for tag in gitrepo.tags(repo, prefix):
            try:
                record = gitrepo.record_of_tag(repo, tag)
            except BusinessError:
                record = None
            made = (_when(record.made) if record is not None else None) or tag_date(repo, tag)
            if newest is None or made > newest:
                newest = made
            if record is not None:
                digests |= {str(d) for d in record.images.values()}
    if newest is None:
        raise BusinessError.make(Reason.PRUNE_NO_RELEASE,
                                 "no release has been made: nothing is old enough to prune")
    return newest, digests


def running(prof, log: RunLog) -> set[str]:
    """The digests any environment runs, now or before: its `current` and its `previous`.
    A host that cannot be read stops the run: not knowing what runs, nothing is removed."""
    digests: set[str] = set()
    for env in prof.environments.values():
        status = hosts.host_status(env.machine, prof.application, env.name, log=log)
        for deploy in (status.deployed.current, status.deployed.previous):
            if deploy is not None:
                digests |= {str(d) for d in deploy.build.images.values()}
    return digests


def choose(port: RegistryPort, prof, newest: datetime, keep: set[str]) -> list[dict[str, str]]:
    """The candidates to remove: built before the newest release, in nobody's keep set, and
    not held by releases under any tag (an `--unrecorded` copy is held under its commit's tag).
    A digest found in releases is added to `keep`, which is sent to the builder."""
    candidates = Repository(RepositoryKind.CANDIDATES, prof.candidates)
    releases = Repository(RepositoryKind.RELEASES, prof.releases)
    chosen = []
    for commit in port.list_versions(candidates):
        for name in prof.images:
            image = port.find_image(candidates, BuildImage(commit, name))
            if image is None or str(image.digest) in keep:
                continue
            created = _when(image.created) if image.created else None
            if created is None or created >= newest:
                continue
            if port.find_image(releases, image.digest) is not None:
                keep.add(str(image.digest))
                continue
            chosen.append({"commit": commit, "image": name, "digest": str(image.digest)})
    return chosen


def run(args: Args, ctx: Context) -> Result:
    repo = profile.repo_dir()
    prof = profile.read_working_tree(repo)
    ctx.start_log(prof.application)
    port = connect.connect(prof.application,
                           connect.component_of(ComponentKind.CONTROLLER, prof.login), ctx.log)
    newest, keep = released(repo, prof, ctx.log)
    keep |= running(prof, ctx.log)
    removes = choose(port, prof, newest, keep)
    ctx.log.event("prune-chosen", count=len(removes))
    if "--dry-run" in args.switches:
        for entry in removes:
            print(f"would remove {connect.candidate_tag(entry['commit'], entry['image'])}")
        return Result.ok()
    if not removes:
        print("nothing to remove")
        return Result.ok()
    request = {"login": prof.build_login.value, "candidates": prof.candidates, "removes": removes,
               "keep": sorted(keep)}
    call = remote.call_turpin(prof.build_on, ["remove", prof.application], log=ctx.log, request=request,
                              retry=True, where="run turpin prune again: what is already removed is skipped")
    if call.code == 3:      # each failure is the builder's to name; the others were removed
        told = call.result
        kind = told.type if told is not None and told.type is not None else ErrorType.BUSINESS
        blip = (bool(told.blip) if told is not None else False) if kind is ErrorType.TECHNICAL else None
        return Result(Outcome.ERROR, kind, blip, Reason.PRUNE_REMOVE_FAILED.value,
                      message="the builder could not remove every candidate chosen, and removed the others: "
                              "run turpin prune again", cause=told)
    return Result.ok()
