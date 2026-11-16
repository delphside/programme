"""`turpin list ENV`: the release records beside what ENV runs (design §6, R40).

One line per release tag, oldest first: version, commit, when it was made, and a mark on the
one whose images are the ones ENV runs now. A tag with no record is history, and says so.
The read is safe to repeat, so a blip reading the host is retried.
"""

from __future__ import annotations

from .. import gitrepo, hosts, profile
from ..cli import Args, Context
from ..model import BusinessError, Reason, Result, TechnicalError
from .status import environment_of

USAGE = "usage: turpin list ENV\n"
MIN_ARGS = MAX_ARGS = 1
FLAGS: dict[str, str] = {}


def run(args: Args, ctx: Context) -> Result:
    repo = profile.repo_dir()
    prof = profile.read_working_tree(repo)
    ctx.start_log(prof.application)
    name = args.positional[0]
    env = environment_of(prof, name)
    try:
        gitrepo.fetch_tags(repo)
    except TechnicalError as exc:
        ctx.log.event("fetch-tags-failed", reason=exc.result.reason)   # a stale view still lists
    deployed = hosts.host_status(env.machine, prof.application, name, log=ctx.log).deployed
    running = {k: str(v) for k, v in deployed.current.build.images.items()} if deployed.current else {}
    prefixes = (prof.tag_prefix, *prof.history_prefixes)
    for tag, version in sorted(gitrepo.release_tags(repo, prefixes).items(), key=lambda item: item[1]):
        try:
            record = gitrepo.record_of_tag(repo, tag)
        except BusinessError as exc:
            if exc.result.reason != Reason.RECORD_VERSION_UNKNOWN.value:
                raise
            print(f"{version}  (a record this tool does not read)")
            continue
        if record is None:
            print(f"{version}  (history: no record)")
            continue
        mark = f"  <- {name} runs this" if {k: str(v) for k, v in record.images.items()} == running else ""
        print(f"{record.version}  {record.commit[:12]}  {record.made}{mark}")
    return Result.ok()
