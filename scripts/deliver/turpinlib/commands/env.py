"""`turpin env create|destroy NAME`: an ephemeral environment on this machine (design §6, R37).

The work is `turpin-host env`'s, which reads the profile `TURPIN_PROFILE` names, makes or
removes the user, the state folder, the `.env` (its secrets asked for at a hidden prompt) and
the Compose project, and runs the `env-*` hooks. This runs it on this machine with the
person's own terminal, since the prompt is the person's, and maps its exit status.
"""

from __future__ import annotations

from .. import hosts
from ..cli import Args, Context
from ..model import Result

USAGE = "usage: turpin env create|destroy NAME\n"
MIN_ARGS = MAX_ARGS = 2
FLAGS: dict[str, str] = {}


def run(args: Args, ctx: Context) -> Result:
    hosts.call_attached(["env", *args.positional], f"turpin env {' '.join(args.positional)}")
    return Result.ok()
