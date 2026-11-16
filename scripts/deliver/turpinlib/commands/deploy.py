"""`turpin deploy ENV REF`: a commit's or a release's images to an environment (design §6, §9, §11).

The controller resolves REF (the `ref` gate), runs the gates that read the registry, the
board's tags and the hosts' states (`production-record`, `rehearsal-level`), and sends the
host one request, which the host answers by §11's steps. The request is an *idempotent
receiver*'s: its `request_id` is made once here and kept across retries, and a retry sends
`repeat` true, so the host answers it from its record and the deploy takes effect at most
once.

The pivot is the host's step 10 (`finished`). Before it, an error stops the run by its
type and the host has undone what it changed. After it, a failure is an error, the steps
that do not need it still run, and the exit is 3, the message naming what reruns it:
the host's prune (the next deploy), `settle` on production (`turpin settle VERSION`), and
`post-deploy`, a check whose failure is only a warning.

A Ctrl+C closes the host's input: before the pivot the host undoes the deploy, after it
the change stays live. The message says which, and only says "nothing changed" where the
host confirms it.
"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import Any

from .. import gates, gitrepo, hooks, hosts, profile, remote, settings
from ..cli import Args, Context
from ..model import (ComponentKind, Environment, ErrorType, FormError, Outcome, Profile, ProgrammeError, Reason,
                     Result, Role)
from ..registry import connect
from ..registry.port import RegistryPort
from ..runlog import RunLog, expected_gates, state_folder
from . import settle
from .status import environment_of

USAGE = ("usage: turpin deploy ENV REF [--wait[=MIN]] [--check] [--set-aside GATE REASON]\n"
         "                         [--unrecorded REASON] [--off-level REASON]\n")
MIN_ARGS = MAX_ARGS = 2
FLAGS = {"--wait": "optional", "--check": "switch"}
GATE_FLAGS = ("--set-aside", "--unrecorded", "--off-level")


def wait_minutes(args: Args) -> int | None:
    """`--wait[=MIN]`: the minutes to wait for the lock and for a hook's *not yet*."""
    if "--wait" not in args.values:
        return None
    text = args.values["--wait"]
    if text == "":
        return settings.WAIT_DEFAULT_MINUTES
    if not text.isdigit():
        raise FormError("--wait", text, "a number of minutes", "NOT_MINUTES").business("--wait")
    return int(text)


def open_registry(prof: Profile, log: RunLog) -> RegistryPort:
    """The controller's own registry login (read only), made on the first read."""
    return connect.connect(prof.application, connect.component_of(ComponentKind.CONTROLLER, prof.login), log)


def request_for(prof: Profile, env: Environment, resolved: gates.Resolved, request_id: str, repeat: bool, *,
                wait: int | None, check: bool, set_aside: list[tuple[str, str]]) -> dict[str, Any]:
    """The request `turpin-host deploy` reads (design §6's table)."""
    return {
        "request_id": request_id, "repeat": repeat, "app": prof.application, "env": env.name,
        "role": env.role.value, "sha": resolved.commit, "version": resolved.version,
        "images": {name: str(digest) for name, digest in resolved.images.items()},
        "repo": prof.releases if env.role is Role.PRODUCTION else prof.candidates,
        "login": env.login.value,
        # the builder's login where the environment is on the builder's machine, else the environment's own
        "login_component": profile.login_component(prof, env),
        "payload_image": resolved.commit_profile.payload_image or "",
        "pull_timeout": env.pull_timeout, "lock": env.lock, "project": env.project, "wait": wait,
        # a repeat waits for the lock the length of time `--wait` or settings.py names (design §11)
        "lock_wait": wait if wait is not None else (settings.WAIT_DEFAULT_MINUTES if repeat else None),
        "check": check, "local": resolved.local,
        "record": resolved.record.to_json() if resolved.record is not None else None,
        "set_aside": [{"gate": gate, "reason": reason} for gate, reason in set_aside],
        "host_files": env.host_files, "env_join": list(env.join)}


def copy_unrecorded(prof: Profile, log: RunLog, resolved: gates.Resolved) -> None:
    """`--unrecorded`: each image by digest into releases as `SHA-IMAGE`, by `turpin promote` on the
    release copier, with its login (R33). A copy already there is a no-op, so a blip is retried."""
    request = {"login": prof.copy_login.value, "candidates": prof.candidates, "releases": prof.releases,
               "commit": resolved.commit, "images": {name: str(digest) for name, digest in resolved.images.items()},
               "version": None, "record": None}
    log.event("step", name="copier", where=prof.copy_on)
    remote.call_turpin(prof.copy_on, ["promote", prof.application], log=log, request=request, retry=True,
                       where=f"run turpin deploy production {resolved.commit} --unrecorded again")


def post_deploy(repo: Path, env: Environment, resolved: gates.Resolved, prof: Profile, log: RunLog) -> Result | None:
    """The application's `post-deploy` check, from the commit's hooks, run on the controller.
    A failure is a warning: the deploy stands."""
    with tempfile.TemporaryDirectory() as tmp:
        if not gitrepo.export_paths(repo, resolved.commit, ["turpin/hooks"], Path(tmp)):
            return None
        try:
            path = hooks.find_hook(Path(tmp) / "turpin" / "hooks", "post-deploy")
            if path is None:
                return None
            result = hooks.run_hook(path, hooks.HookEnv(
                app=prof.application, env=env.name, role=env.role.value, sha=resolved.commit,
                version=resolved.version, state=str(state_folder(prof.application)),
                images={name: str(digest) for name, digest in resolved.images.items()}), cwd=repo)
        except ProgrammeError as exc:
            text = (f"check post-deploy could not run: {exc.result.message} (the deploy stands; "
                    f"turpin rollback {env.name} undoes it)")
            log.event("check-failed", name="post-deploy", reason=exc.result.reason)
            return Result(Outcome.WARNING, reason=Reason.POST_DEPLOY_REPORTED.value, message=text)
    if result.passed:
        return None
    log.event("check-failed", name="post-deploy", code=result.code)
    return Result(Outcome.WARNING, reason=Reason.POST_DEPLOY_REPORTED.value,
                  message=f"check post-deploy reported exit {result.code} (the deploy stands; "
                          f"turpin rollback {env.name} undoes it)")


def after_the_pivot(result: Result, rerun: str) -> Result:
    """A step after the pivot that raised: an error, not a stop, naming what reruns it."""
    return Result(Outcome.ERROR, result.type, result.blip, result.reason, result.domain,
                  f"{result.message.rstrip('.')}; rerun {rerun}", result.metadata, result.violations, result)


def combine(found: list[Result]) -> Result:
    """The deploy's own result once it is live: ok, a warning, or done with errors (3)."""
    if not found:
        return Result.ok()
    failed = [r for r in found if r.outcome is Outcome.ERROR]
    if not failed:
        return found[0] if len(found) == 1 else Result(Outcome.WARNING, reason=found[0].reason,
                                                        message="; ".join(r.message for r in found), errors=tuple(found))
    first = failed[0]
    return Result(Outcome.ERROR, first.type, first.blip, first.reason, first.domain,
                  "; ".join(r.message for r in found), {"errors": len(failed)}, (), None, tuple(found))


def run(args: Args, ctx: Context) -> Result:
    repo = profile.repo_dir()
    prof = profile.read_working_tree(repo)
    name, ref = args.positional
    env = environment_of(prof, name)
    check = "--check" in args.switches
    wait = wait_minutes(args)
    ctx.start_log(prof.application, expected_gates("deploy", env.role, check))
    log = ctx.log
    log.event("deploy", env=name, role=env.role.value, ref=ref)
    rerun = f"turpin deploy {name} {ref}"
    registry_port: list[RegistryPort] = []
    copied: list[str] = []      # set once the copy to releases (`--unrecorded`) has been started

    def registry() -> RegistryPort:
        if not registry_port:
            registry_port.append(open_registry(prof, log))
        return registry_port[0]

    try:
        gates.check_flags_for_role(log, env, "--unrecorded" in args.reasons, "--off-level" in args.reasons)
        gates.host_files_conflict(prof, env)
        resolved = gates.resolve(log, repo, prof, env, ref, registry=registry, unrecorded="--unrecorded" in args.reasons)
        if env.role is Role.PRODUCTION:
            gates.production_record(
                log, prof, resolved, registry, unrecorded_reason=args.reasons.get("--unrecorded"),
                copy=None if check else lambda found: (copied.append(found.commit), copy_unrecorded(prof, log, found)))
        if env.role is Role.REHEARSAL:
            gates.rehearsal_level(log, repo, prof, env, resolved, off_level_reason=args.reasons.get("--off-level"))
    except KeyboardInterrupt:
        raise KeyboardInterrupt(
            "interrupted before the host was called: nothing that runs changed and the change is not live; "
            + ("the copy of the images to releases was started (one already there is a no-op); " if copied else "")
            + f"run {rerun} again") from None

    request_id = str(uuid.uuid4())      # once per command, kept across its retries
    try:
        call = hosts.call_host(
            env.machine, ["deploy", prof.application, name], log=log, retry=True,
            request=lambda repeat: request_for(prof, env, resolved, request_id, repeat, wait=wait, check=check,
                                               set_aside=args.set_aside),
            where=f"run turpin status {name} to see where it stopped")
    except hosts.HostInterrupted:
        # the host read the interruption and undid what it had changed (§6, item 4)
        raise KeyboardInterrupt(f"interrupted: the host stopped and the change is not live; "
                                f"run {rerun} again") from None
    except KeyboardInterrupt:
        # any other interruption: the call may have reached the host and gone past its pivot
        raise KeyboardInterrupt(f"interrupted: the call may have reached the host; "
                                f"run turpin status {name} to see what it holds") from None
    if check:
        print("check: every gate passed; nothing changed")
        return Result.ok()

    errors: list[Result] = []
    if call.code == 3:      # the host's prune failed after its pivot: the deploy stands (§11)
        told = call.result
        errors.append(Result(Outcome.ERROR, ErrorType.TECHNICAL, False,
                             told.reason if told is not None and told.reason else Reason.DEPLOY_LIVE_WITH_ERRORS.value,
                             message="the deploy is live, but a step after it failed on the host: "
                                     "the next deploy repeats it",
                             cause=told))
    settles = env.role is Role.PRODUCTION and resolved.record is not None
    if call.interrupted:
        # the host ran past its pivot before it read the interruption: no further step is started (§6, item 4)
        raise KeyboardInterrupt(
            f"interrupted after the deploy went live: {name} runs the new build; "
            + (f"run turpin settle {resolved.version} to settle the board; " if settles else "")
            + "the post-deploy check was not run")
    if settles:
        try:
            outcome = settle.settle_version(repo, prof, resolved.version, log)
        except ProgrammeError as exc:
            outcome = after_the_pivot(exc.result, f"turpin settle {resolved.version}")
        except KeyboardInterrupt:
            raise KeyboardInterrupt(f"interrupted while settling: the deploy is live; "
                                    f"run turpin settle {resolved.version} to finish") from None
        if outcome.outcome is not Outcome.OK:
            errors.append(outcome)
    try:
        warning = post_deploy(repo, env, resolved, prof, log)
    except KeyboardInterrupt:
        raise KeyboardInterrupt("interrupted during the post-deploy check: the deploy is live") from None
    if warning is not None:
        errors.append(warning)
    return combine(errors)
