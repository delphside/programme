"""`turpin status ENV`: what an environment runs, read from its host (design §6).

The state, the build `current` is, the digests the containers run against it, the
release record those digests match, and the host files against the payload's (a
check). The read is safe to repeat, so a blip is retried.
"""

from __future__ import annotations

from .. import gitrepo, hosts, profile
from ..cli import Args, Context
from ..model import BusinessError, Reason, Result, TechnicalError
from ..runlog import expected_gates

USAGE = "usage: turpin status ENV\n"
MIN_ARGS = MAX_ARGS = 1
FLAGS: dict[str, str] = {}


def environment_of(prof, name: str):
    """The profile's environment `name`, or a business error naming the profile."""
    if name not in prof.environments:
        raise BusinessError.make(Reason.ENVIRONMENT_UNKNOWN, f"the profile has no environment {name}: name one of "
                                 f"{', '.join(sorted(prof.environments)) or 'none'}", metadata={"environment": name})
    return prof.environments[name]


def matching_record(repo, prof, images: dict[str, str], log) -> str | None:
    """The version of the release record whose images are `images`, the last tag's if
    several; a tag with no record, or one this tool cannot read, is passed over."""
    found = None
    try:
        gitrepo.fetch_tags(repo)
    except TechnicalError as exc:
        log.event("fetch-tags-failed", reason=exc.result.reason)   # a stale view is all the record needs
    for prefix in (prof.tag_prefix, *prof.history_prefixes):
        for tag in gitrepo.tags(repo, prefix):
            try:
                record = gitrepo.record_of_tag(repo, tag)
            except BusinessError:
                continue
            if record is not None and {k: str(v) for k, v in record.images.items()} == images:
                found = str(record.version)
    return found


def deploy_line(label: str, deploy) -> str:
    """One deploy the host holds: its number, commit, version, release record and `smoke`."""
    record = f" record {deploy.record.version}" if deploy.record is not None else ""
    smoke = f"smoke passed {deploy.deployed}" if deploy.deployed else "smoke not passed"
    return (f"{label}: deploy {deploy.number} commit {deploy.build.commit} version {deploy.version or '-'}"
            f"{record} {smoke}")


def run(args: Args, ctx: Context) -> Result:
    repo = profile.repo_dir()
    prof = profile.read_working_tree(repo)
    ctx.start_log(prof.application, expected_gates("status"))
    name = args.positional[0]
    env = environment_of(prof, name)
    status = hosts.host_status(env.machine, prof.application, name, log=ctx.log)
    deployed = status.deployed
    print(f"environment: {name} ({env.role.value})")
    print(f"state: {deployed.state or 'none (no turpin deploy yet)'}")
    if deployed.pending is not None:
        print(deploy_line("pending", deployed.pending))
    elif status.pending_number is not None:
        print(f"pending: deploy {status.pending_number} (folder not written)")
    if deployed.request_id is not None:
        print(f"last request: {deployed.request_id} {deployed.outcome}")
    current = deployed.current
    if current is None:
        print("current: none")
        return Result.ok()
    images = {k: str(v) for k, v in current.build.images.items()}
    print(deploy_line("current", current))
    if deployed.previous is not None:
        print(deploy_line("previous", deployed.previous))
    for image, digest in images.items():
        print(f"image {image} {digest}")
    running = sorted(status.running)
    if running == sorted(images.values()):
        print("running: the current digests")
    else:
        print(f"running: DIFFERS from the current digests ({' '.join(running)})")
    print(f"record: {matching_record(repo, prof, images, ctx.log) or 'none matches'}")
    for dest, state in status.host_files:
        print(f"host file {dest}: {state}")
    return Result.ok()
