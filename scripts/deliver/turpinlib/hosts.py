"""Calls to `turpin-host`, here or over `ssh` (design §6 *Interruption*, §11, §13).

Every call runs in a process group of its own, so a Ctrl+C reaches `turpin` alone.
A call that has a request, or none, gets one line on standard input, which is held
open for the call's life: on a Ctrl+C the input is closed, and the host reads its
end as the interruption (`turpin-host` owns that input). A call that reads data
gets the data, then the closing line `# turpin: end`.

What comes back: the exit status, the output, the gates the host ran
(`@gate NAME RESULT` lines on standard error, copied into the run log and left out
of what the operator sees) and, for a stop, the host's result object (an
`@result JSON` line, the last on standard error). `ssh`'s 255 is mapped by its
error text; a blip is retried where the call is safe to repeat, under the same
`request_id` for a request, which the host answers once.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from . import settings
from .model import (CONTROLLER, Build, BusinessError, Deployed, DeployedBuild, Digest, ErrorType,
                    FormError, Outcome, ProgrammeError, Reason, ReleaseRecord, Result, TechnicalError,
                    UnexpectedError, Violation)
from .runlog import RunLog

CLOSING_LINE = "# turpin: end"
GATE_PREFIX = "@gate "
RESULT_PREFIX = "@result "
HOST_COMMAND = "turpin-host"
TURPIN_COMMAND = "turpin"              # the other program a call may run (`remote.py`)
ERROR_PREFIX = f"{HOST_COMMAND}: "     # how the host starts the line of a stop

# `ssh`'s error text to the error it is (design §6): a first match wins.
_SSH_FUNDAMENTAL = (
    ("Permission denied", Reason.SSH_PERMISSION_DENIED,
     "ssh refused the key for {machine}: load the right key into the ssh agent"),
    ("Host key verification failed", Reason.SSH_HOST_KEY_REFUSED,
     "ssh does not trust the host key of {machine}: fix its entry in known_hosts"),
    ("Could not resolve hostname", Reason.SSH_HOST_UNRESOLVED,
     "ssh cannot find the host {machine}: fix the host alias in the ssh configuration"),
)
_SSH_BLIP = ("Connection timed out", "Connection refused", "Connection reset", "Broken pipe",
             "Connection closed")
# A blip these reasons name was in the connection, which a retry may get past.
_RETRIED = (Reason.SSH_CONNECTION_LOST.value, Reason.HOST_CALL_TIMED_OUT.value)

# The sleep between attempts: replaced by a test.
_sleep = time.sleep


def host_command() -> str:
    """`turpin-host` on this machine: the one named, else the one beside `turpin`."""
    named = os.environ.get(settings.ENV_HOST_BIN)
    return named or str(Path(__file__).resolve().parents[1] / HOST_COMMAND)


def turpin_command() -> str:
    """`turpin` on this machine: the one named, else the entry script beside `turpinlib`."""
    named = os.environ.get(settings.ENV_BIN)
    return named or str(Path(__file__).resolve().parents[1] / TURPIN_COMMAND)


def _argv(machine: str, args: Sequence[str], program: str = HOST_COMMAND,
          extra: Mapping[str, str] | None = None) -> tuple[list[str], dict[str, str]]:
    """The command that runs `PROGRAM ARGS` on `machine`, and its environment. On this
    machine the child sets its own registry login, not the controller's auth file, and finds
    its libraries beside `turpin` (`ssh` carries no environment, so a remote host finds its own,
    and `extra` is written before the program, as the design's examples show)."""
    env = {k: v for k, v in os.environ.items() if k != "REGISTRY_AUTH_FILE"}
    env.setdefault("TURPIN_LIB", str(Path(__file__).resolve().parents[1] / "lib"))
    extra = dict(extra or {})
    if machine == CONTROLLER or not machine:
        local = host_command() if program == HOST_COMMAND else turpin_command()
        return [local, *args], {**env, **extra}
    words = shlex.join([program, *args])
    prefix = "".join(f"{key}={shlex.quote(value)} " for key, value in extra.items())
    return (["ssh", "-o", "BatchMode=yes", machine, prefix + words],
            dict(os.environ, **{"TURPIN_LIB": env["TURPIN_LIB"]}))


@dataclass
class HostCall:
    """How one call to `turpin-host` ended."""
    code: int
    stdout: str = ""
    stderr: str = ""                       # what the operator was shown
    gates: list[tuple[str, str]] = field(default_factory=list)
    result: Result | None = None           # the host's own, from its `@result` line
    interrupted: bool = False              # the operator pressed Ctrl+C while it ran
    seconds: float = 0.0
    raw_stderr: str = ""                   # all of it, for the ssh error text
    held: list[str] = field(default_factory=list)   # the host's lines not shown yet: `raise_for` shows them


def result_from_json(data: Mapping[str, Any]) -> Result | None:
    """The host's result object, or None where it is not one."""
    try:
        kind = data.get("type")
        return Result(
            Outcome(data["outcome"]), ErrorType(kind) if kind else None, data.get("blip"),
            str(data.get("reason", "")), str(data.get("domain", "turpin")), str(data.get("message", "")),
            dict(data.get("metadata") or {}),
            tuple(Violation(**v) for v in data.get("violations") or ()))
    except (KeyError, ValueError, TypeError):
        return None


def _close(stream) -> None:
    try:
        stream.close()
    except (BrokenPipeError, OSError, ValueError):
        pass


def _kill_group(child: subprocess.Popen) -> None:
    try:
        os.killpg(child.pid, 9)
    except (ProcessLookupError, PermissionError):
        pass


def _run_once(machine: str, args: Sequence[str], *, line: str | None, data: str | None,
              timeout: float | None, echo_stdout: bool, program: str = HOST_COMMAND,
              extra: Mapping[str, str] | None = None) -> HostCall:
    """One attempt. `line` is a request, or an empty line, held open to the end; `data` is
    written with the closing line and the input closed."""
    argv, env = _argv(machine, args, program, extra)
    error_prefix = f"{program}: "
    start = time.monotonic()
    child = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, env=env, start_new_session=True)
    call = HostCall(code=-1)
    # What `ssh` itself prints (its 255) is the tool's text, kept for the run log and not shown;
    # so over `ssh` the host's own lines are shown once the call has ended with another status.
    over_ssh = machine not in (CONTROLLER, "")
    out: list[str] = []
    shown: list[str] = []
    raw: list[str] = []

    def pump_out() -> None:
        for text in child.stdout:
            out.append(text)
            if echo_stdout:
                sys.stdout.write(text)
                sys.stdout.flush()

    def pump_err() -> None:
        for text in child.stderr:
            raw.append(text)
            stripped = text.rstrip("\n")
            if stripped.startswith(GATE_PREFIX):
                parts = stripped[len(GATE_PREFIX):].split()
                if len(parts) == 2:
                    call.gates.append((parts[0], parts[1]))
                continue
            if stripped.startswith(RESULT_PREFIX):
                try:
                    call.result = result_from_json(json.loads(stripped[len(RESULT_PREFIX):]))
                except ValueError:
                    pass
                continue
            shown.append(text)
            if not over_ssh and not stripped.startswith(error_prefix):
                sys.stderr.write(text)
                sys.stderr.flush()

    threads = [threading.Thread(target=pump_out, daemon=True), threading.Thread(target=pump_err, daemon=True)]
    for thread in threads:
        thread.start()
    try:
        if data is not None:
            child.stdin.write(data if data.endswith("\n") or not data else data + "\n")
            child.stdin.write(CLOSING_LINE + "\n")
            child.stdin.flush()
            _close(child.stdin)
        else:
            child.stdin.write((line or "") + "\n")
            child.stdin.flush()
    except (BrokenPipeError, OSError):
        pass                                  # the call ended before it read; its status says how
    deadline = None if timeout is None else start + timeout
    while True:
        try:
            child.wait(timeout=None if deadline is None else max(0.0, deadline - time.monotonic()))
            break
        except subprocess.TimeoutExpired:
            _kill_group(child)
            child.wait()
            for thread in threads:
                thread.join(1)
            for pipe in (child.stdin, child.stdout, child.stderr):
                _close(pipe)
            raise TechnicalError.make(
                Reason.HOST_CALL_TIMED_OUT,
                f"the call to {machine or 'this machine'} ran past {timeout:g} seconds: try again later",
                blip=True, metadata={"seconds": timeout}) from None
        except KeyboardInterrupt:
            # The host reads the end of its input as the interruption (§6, item 2); a
            # further Ctrl+C changes nothing, and the call is waited for to its end.
            call.interrupted = True
            _close(child.stdin)
    _close(child.stdin)
    for thread in threads:
        thread.join()
    _close(child.stdout)
    _close(child.stderr)
    # The host's error lines (all its lines, over ssh) are held for `raise_for`, which shows them
    # unless the error it raises says the same.
    call.held = [t for t in shown if over_ssh or t.startswith(error_prefix)]
    call.code = child.returncode
    call.stdout, call.stderr, call.raw_stderr = "".join(out), "".join(shown), "".join(raw)
    call.seconds = time.monotonic() - start
    return call


def _ssh_error(machine: str, call: HostCall) -> ProgrammeError:
    """`ssh`'s 255, mapped by the error text it printed (design §6)."""
    text = call.raw_stderr.strip()
    for phrase, reason, message in _SSH_FUNDAMENTAL:
        if phrase in text:
            return TechnicalError.make(reason, message.format(machine=machine), metadata={"tool_text": text})
    if any(phrase in text for phrase in _SSH_BLIP):
        return TechnicalError.make(Reason.SSH_CONNECTION_LOST,
                                   f"the connection to {machine} was lost: try again later",
                                   blip=True, metadata={"tool_text": text})
    return UnexpectedError.make(Reason.SSH_UNEXPECTED,
                                f"ssh to {machine} failed in a way not expected: raise it as an issue, with the run log",
                                metadata={"tool_text": text})


_BY_CODE = {1: (BusinessError, Reason.HOST_REFUSED), 2: (TechnicalError, Reason.HOST_FUNDAMENTAL),
            70: (UnexpectedError, Reason.HOST_UNEXPECTED), 75: (TechnicalError, Reason.HOST_BLIP)}


class HostInterrupted(KeyboardInterrupt):
    """The host read the end of its input while it waited for the lock, and stopped having changed nothing."""


def _show(call: HostCall, restated: str | None = None, program: str = HOST_COMMAND) -> None:
    """The host's held lines, except the one that only restates the message of the error being raised."""
    skip = f"{program}: {restated}\n" if restated is not None else None
    later = [t for t in call.held if t != skip]
    call.held = []
    if later:
        sys.stderr.write("".join(later))
        sys.stderr.flush()


def raise_for(machine: str, call: HostCall, program: str = HOST_COMMAND) -> HostCall:
    """Return a call that ended well (0, or 3: done with errors) and raise the error any
    other ending is. The host's own result gives the reason and the message where its type
    is the status's; anything else is unexpected."""
    code = call.code
    ssh = machine not in (CONTROLLER, "")
    if code == 255 and ssh:
        raise _ssh_error(machine, call)                 # ssh's own text is not shown
    if code in (0, 3):
        _show(call, program=program)
        return call
    if code == 130:
        _show(call, program=program)
        if call.result is not None and call.result.reason == Reason.HOST_INTERRUPTED.value:
            raise HostInterrupted
        raise KeyboardInterrupt
    if code == 127 and ssh:
        _show(call, program=program)
        fix = ("run turpin host-install for its environment" if program == HOST_COMMAND
               else "install it, and set TURPIN_REPO where a non-interactive ssh session reads it")
        raise TechnicalError.make(Reason.HOST_COMMAND_MISSING,
                                  f"{program} is not on {machine}: {fix}",
                                  metadata={"tool_text": call.raw_stderr.strip()})
    if code in _BY_CODE:
        klass, generic = _BY_CODE[code]
        told = call.result
        if told is not None and told.type is klass.kind and told.outcome is Outcome.FATAL \
                and (told.blip or False) == (code == 75):
            _show(call, told.message, program)
            raise klass.make(told.reason or generic, told.message or call.stderr.strip(),
                             metadata=dict(told.metadata), violations=told.violations,
                             blip=bool(told.blip))
        last = call.stderr.strip().splitlines()[-1] if call.stderr.strip() else ""
        _show(call, last.removeprefix(f"{program}: ") if last else None, program)
        raise klass.make(generic, last or f"{program} stopped with exit {code}", blip=code == 75)
    _show(call, program=program)
    raise UnexpectedError.make(Reason.HOST_UNEXPECTED,
                               f"{program} on {machine or 'this machine'} stopped in a way not expected "
                               f"(exit {code}): raise it as an issue, with the run log",
                               metadata={"exit": code, "tool_text": call.raw_stderr.strip()})


def call_host(machine: str, args: Sequence[str], *, log: RunLog,
              request: Mapping[str, Any] | Callable[[bool], Mapping[str, Any]] | None = None,
              data: str | None = None, retry: bool = False, timeout: float | None = None,
              echo_stdout: bool = True, where: str = "", program: str = HOST_COMMAND,
              extra: Mapping[str, str] | None = None) -> HostCall:
    """Run `PROGRAM ARGS` (`turpin-host`, or `turpin` for `remote.py`) on `machine` and return
    it if it ended well, else raise. `extra` is environment for the called program.

    `request` is the call's request, or a function of `repeat` that makes it: a retry
    sends `repeat` true under the same `request_id`, which the function keeps. `retry`
    says the call is safe to repeat, so a blip is retried (design §13: three attempts,
    waiting 2 seconds, then 4). `timeout` bounds one attempt.
    """
    attempts = settings.RETRY_ATTEMPTS if retry else 1
    for attempt in range(attempts):
        body = request(attempt > 0) if callable(request) else request
        line = None if body is None and data is None else (json.dumps(body, separators=(",", ":")) if body is not None else "")
        try:
            call = _run_once(machine, args, line=line if data is None else None, data=data,
                             timeout=timeout, echo_stdout=echo_stdout, program=program, extra=extra)
            for name, verdict in call.gates:
                log.gate(name, verdict, "on the host" if program == HOST_COMMAND else f"on {machine or 'this machine'}")
            return raise_for(machine, call, program)
        except TechnicalError as exc:
            if not (exc.result.blip and exc.result.reason in _RETRIED):
                raise
            if attempt + 1 >= attempts:
                # retries ran out, or none was safe: say where the call stopped (exit 75)
                if where:
                    raise TechnicalError(replace(exc.result, message=f"{exc.result.message.rstrip('.')}; {where}")) from exc
                raise
            wait = settings.RETRY_BACKOFF_SECONDS[min(attempt, len(settings.RETRY_BACKOFF_SECONDS) - 1)]
            log.event("retry", machine=machine, call=" ".join(args[:1]), attempt=attempt + 1,
                      reason=exc.result.reason, wait=wait)
            _sleep(wait)
    raise AssertionError("unreachable")   # the loop returns or raises


# ------------------------------------------------------------------- status

@dataclass(frozen=True)
class HostStatus:
    """`turpin-host status --json`'s metadata, read: `Deployed` and the rest of what it holds."""
    deployed: Deployed
    running: tuple[str, ...]
    host_files: tuple[tuple[str, str], ...]     # (destination, equal | differs | missing ...)
    deploys: tuple[tuple[int, str | None], ...]   # (number, when `smoke` passed)
    pending_number: int | None = None           # `pending`'s number where its folder has no `meta.json`


def _build_of(meta: Mapping[str, Any] | None) -> DeployedBuild | None:
    if not meta or "sha" not in meta:
        return None
    try:
        build = Build(meta["sha"], {name: Digest(text) for name, text in (meta.get("images") or {}).items()})
        record = meta.get("record")
        return DeployedBuild(build, ReleaseRecord.from_json(record) if record else None, meta.get("deployed"),
                             meta.get("n"), meta.get("version") or "")
    except FormError as exc:
        raise exc.unexpected("the host's status") from exc
    except (KeyError, TypeError, AttributeError) as exc:
        raise UnexpectedError.make(Reason.HOST_STATUS_UNREADABLE,
                                   "the host's status holds a deploy that is malformed: raise it as an issue",
                                   metadata={"exception": str(exc)}) from exc


def parse_status(text: str) -> HostStatus:
    """The host's status result object, whose `metadata` holds the status."""
    try:
        data = json.loads(text)
        meta = data["metadata"]
        last = meta.get("last_request") or {}
        return HostStatus(
            Deployed(meta.get("state") or "", _build_of(meta.get("pending")), last.get("request_id"),
                     last.get("outcome"), _build_of(meta.get("current")), _build_of(meta.get("previous"))),
            tuple(meta.get("running") or ()),
            tuple((f["dest"], f["status"]) for f in meta.get("host_files") or ()),
            tuple((d["n"], d.get("deployed")) for d in meta.get("deploys") or ()),
            (meta.get("pending") or {}).get("n") if not (meta.get("pending") or {}).get("sha") else None)
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise UnexpectedError.make(Reason.HOST_STATUS_UNREADABLE,
                                   "the host's status is not a result object: raise it as an issue",
                                   metadata={"exception": str(exc)}) from exc


def host_status(machine: str, app: str, env: str, *, log: RunLog) -> HostStatus:
    """What `env` runs, read from its host: safe to repeat, so a blip is retried (§6)."""
    call = call_host(machine, ["status", app, env, "--json"], log=log, retry=True,
                     timeout=settings.HOST_CALL_TIMEOUT, echo_stdout=False,
                     where=f"run turpin status {env} to try again")
    return parse_status(call.stdout)
