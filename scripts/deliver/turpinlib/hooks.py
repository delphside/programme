"""Running the application's hooks (design §8).

A hook is an executable in the application's `turpin/hooks/`. It runs with the
§8 environment, in a process group of its own so a Ctrl+C reaches `turpin`
alone (§6 *Interruption*), with its input from `/dev/null`.

| Exit | Meaning |
| --- | --- |
| 0 | passed |
| 75 | not yet: `--wait` retries; else the run stops as a blip, exit 75 |
| other | refused, or the step failed: a business error naming the hook, exit 1 |
| killed by a signal | an unexpected error, exit 70 (docs/1.10) |
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from .model import BusinessError, Reason, TechnicalError, UnexpectedError

HOOK_NOT_YET = 75


@dataclass(frozen=True)
class HookEnv:
    """What each hook is given. `images` maps an image name to its digest;
    `created` is for `build` only, and `local` under `--local` only."""
    app: str
    env: str
    role: str                 # an environment's role, or `controller` or `ephemeral`
    sha: str
    version: str
    state: str                # the state folder
    images: Mapping[str, str] = field(default_factory=dict)
    created: str | None = None
    local: bool = False
    url: str = ""             # the environment's `url`, empty where it has none (TURPIN_URL)
    extra: Mapping[str, str] = field(default_factory=dict)   # e.g. TURPIN_DEPLOY, TURPIN_CURRENT

    def environ(self) -> dict[str, str]:
        """The process environment: this machine's, with the hook's `TURPIN_*` on top."""
        values = {"TURPIN_APP": self.app, "TURPIN_ENV": self.env, "TURPIN_ROLE": self.role,
                  "TURPIN_SHA": self.sha, "TURPIN_VERSION": self.version,
                  "TURPIN_STATE": self.state, "TURPIN_URL": self.url}
        for name, digest in self.images.items():
            values["TURPIN_IMAGE_" + re.sub(r"[^A-Z0-9]", "_", name.upper())] = str(digest)
        if self.created is not None:
            values["TURPIN_CREATED"] = self.created
        if self.local:
            values["TURPIN_LOCAL"] = "1"
        values.update(self.extra)
        return {**os.environ, **values}


@dataclass(frozen=True)
class HookResult:
    name: str
    code: int
    output: str               # standard output: `build` names its layouts there

    @property
    def passed(self) -> bool:
        return self.code == 0

    @property
    def not_yet(self) -> bool:
        return self.code == HOOK_NOT_YET

    def require(self) -> None:
        """Raise unless it passed: 75 is a blip (try later, or `--wait`); a hook killed
        by a signal is unexpected; any other failure is a business error naming the hook."""
        if self.passed:
            return
        if self.code < 0 or self.code > 128:   # killed by a signal, or a shell's 128 + n
            raise UnexpectedError.make(Reason.HOOK_KILLED,
                                       f"hook {self.name} was killed (status {self.code}): raise it as an issue",
                                       metadata={"hook": self.name, "exit": self.code})
        if self.not_yet:
            raise TechnicalError.make(Reason.HOOK_NOT_YET,
                                      f"hook {self.name} says not yet: try again later, or use --wait",
                                      metadata={"hook": self.name}, blip=True)
        raise BusinessError.make(Reason.HOOK_REFUSED, f"hook {self.name} refused (exit {self.code})",
                                 metadata={"hook": self.name, "exit": self.code})


def find_hook(hooks_dir: Path, name: str, required: bool = False) -> Path | None:
    """The hook's file. A required hook missing or not executable refuses; any other
    missing hook is a no-op (None)."""
    path = hooks_dir / name
    if not path.is_file():
        if required:
            raise BusinessError.make(Reason.HOOK_MISSING, f"required hook {name} is missing from {hooks_dir}",
                                     metadata={"hook": name})
        return None
    if not os.access(path, os.X_OK):
        raise BusinessError.make(Reason.HOOK_NOT_EXECUTABLE, f"hook {name} is not executable",
                                 metadata={"hook": name})
    return path


def _time_out(child: subprocess.Popen, name: str, timeout: float | None) -> TechnicalError:
    """Kill the hook's whole group and say the run stops as a blip."""
    os.killpg(child.pid, signal.SIGKILL)
    child.communicate()
    return TechnicalError.make(Reason.HOOK_TIMED_OUT, f"hook {name} ran past {timeout} seconds",
                               metadata={"hook": name}, blip=True)


def run_hook(path: Path, hook_env: HookEnv, cwd: Path | str | None = None,
             timeout: float | None = None) -> HookResult:
    """Run one hook to its end. Its standard error is ours; its standard output is
    kept. On `timeout` its whole group is killed and the run stops as a blip. A
    Ctrl+C lets the hook run on, to the same limit, then goes on to the front end."""
    deadline = None if timeout is None else time.monotonic() + timeout
    child = subprocess.Popen([str(path)], env=hook_env.environ(), cwd=cwd, stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, text=True, start_new_session=True)
    try:
        output, _ = child.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise _time_out(child, path.name, timeout) from exc
    except KeyboardInterrupt:
        # A hook already running runs to its end (§6 *Interruption*, item 1), within
        # its limit; a further Ctrl+C changes nothing.
        while True:
            try:
                child.communicate(timeout=None if deadline is None else max(0.0, deadline - time.monotonic()))
                break
            except KeyboardInterrupt:
                continue
            except subprocess.TimeoutExpired as exc:
                raise _time_out(child, path.name, timeout) from exc
        raise
    return HookResult(path.name, child.returncode, output)
