"""`turpin rollback ENV`: ENV's previous deploy, by the host's state table (design §6, §11).

The host's `turpin-host rollback` takes the lock and acts by the state it finds. The
request is an *idempotent receiver*'s: its `request_id` is made once here and kept across
retries, and a retry sends `repeat` true, so the host answers the repeat from its record
and the rollback takes effect at most once.

A bare host has no payload on disk to name the fallback, so the request carries
`[turpin].fallback`, which the host names on that refusal.

A Ctrl+C closes the host's input. The host reads it only until it holds the lock, so a
rollback that had begun runs to its end and this exits by its result, saying so.
"""

from __future__ import annotations

import uuid

from .. import hosts, profile, settings
from ..cli import Args, Context
from ..model import Outcome, Reason, Result, Role
from ..runlog import expected_gates
from .status import environment_of

USAGE = "usage: turpin rollback ENV\n"
MIN_ARGS = MAX_ARGS = 1
FLAGS: dict[str, str] = {}

NO_FALLBACK = "the application has named no fallback"


def request_for(prof, env, request_id: str, repeat: bool) -> dict:
    """The request `turpin-host rollback` reads (design §6's table)."""
    return {
        "request_id": request_id, "repeat": repeat, "app": prof.application, "env": env.name,
        "role": env.role.value, "login": env.login.value,
        "repo": prof.releases if env.role is Role.PRODUCTION else prof.candidates,
        "lock": env.lock, "project": env.project, "pull_timeout": env.pull_timeout, "wait": None,
        # a repeat waits for the lock the length of time settings.py names (design §11)
        "lock_wait": settings.WAIT_DEFAULT_MINUTES if repeat else None,
        "fallback": prof.fallback or NO_FALLBACK}


def run(args: Args, ctx: Context) -> Result:
    repo = profile.repo_dir()
    prof = profile.read_working_tree(repo)
    ctx.start_log(prof.application, expected_gates("rollback"))
    env = environment_of(prof, args.positional[0])
    request_id = str(uuid.uuid4())      # once per command, kept across its retries
    try:
        call = hosts.call_host(env.machine, ["rollback", prof.application, env.name], log=ctx.log,
                               request=lambda repeat: request_for(prof, env, request_id, repeat),
                               retry=True, where=f"run turpin status {env.name} to see where it stopped")
    except hosts.HostInterrupted:
        # the host reads an interruption only while it waits for the lock (§6, item 3)
        raise KeyboardInterrupt(f"interrupted while waiting for the lock: nothing changed; "
                                f"run turpin rollback {env.name} again") from None
    except KeyboardInterrupt:
        # any other interruption: the call may have reached the host and taken the lock
        raise KeyboardInterrupt(f"interrupted: the call may have reached the host; "
                                f"run turpin status {env.name} to see what it holds") from None
    if call.interrupted:
        # the host ran to its end once it held the lock (§6, item 3)
        return Result(Outcome.WARNING, reason=Reason.INTERRUPTED_AFTER_ROLLBACK_BEGAN.value,
                      message="the interruption came after the rollback began, so it ran to its end: "
                              f"run turpin status {env.name} to see what {env.name} runs")
    return Result.ok()
