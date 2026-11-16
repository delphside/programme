"""A `turpin` command on another component's machine (design §5, §6 *Interruption*, §7).

`build`, `promote`, `remove` and `login` run on the component that owns them: the builder,
the release copier. The controller passes the command on by `ssh`, or runs it as a child
process where the component is its own machine ("on the same machine the call is the same
without `ssh`"). The running, the mapping of `ssh`'s 255 and the retries are `hosts.py`'s,
which this module calls for the program `turpin`.

**The calling side** is `call_turpin`. The call carries `TURPIN_CALLED=1`, since `ssh` carries
no environment, so the called side reports each gate it runs and the result it stops with as
lines on standard error (`@gate`, `@result`), which `hosts.py` copies into the controller's
run log and leaves out of what the operator sees.

**The called side** is the rest: the request it reads from standard input (one line of
JSON), the end of that input as the caller's interruption (the caller holds the input open
for the call's life), and the data a login reads, which ends with the closing line.
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
from typing import Any, Mapping, Sequence, TextIO

from . import hosts, settings
from .model import (CredentialKind, Digest, FormError, Outcome, ProgrammeError, Reason, Repository,
                    RepositoryKind, Result, TechnicalError, UnexpectedError, check_commit, read_input)
from .runlog import RunLog

CLOSING_LINE = hosts.CLOSING_LINE


# ---------------------------------------------------------------- the calling side

def call_turpin(machine: str, args: Sequence[str], *, log: RunLog,
                request: Mapping[str, Any] | None = None, data: str | None = None,
                retry: bool = False, timeout: float | None = None, where: str = "",
                extra: Mapping[str, str] | None = None) -> hosts.HostCall:
    """Run `turpin ARGS` on `machine` and return the call if it ended well (0, or 3: done with
    errors), else raise the error it was. `request` is the one line it is given and holds
    open, or none gives an empty line; `data` is read by a login and ends with the closing
    line. `retry` says a blip may be retried: the call is safe to repeat (promote, remove and
    login are; build is not)."""
    return hosts.call_host(machine, args, log=log, request=request, data=data, retry=retry,
                           timeout=timeout, where=where, program=hosts.TURPIN_COMMAND,
                           extra={settings.ENV_CALLED: "1", **(extra or {})})


# ----------------------------------------------------------------- the called side

def called() -> bool:
    """Whether another `turpin` called this one."""
    return os.environ.get(settings.ENV_CALLED) == "1"


def unreadable(what: str, why: str, **metadata: Any) -> UnexpectedError:
    """The one way a called side finds its request wrong: the caller made it from values it
    had checked, so this is unexpected, exit 70 (design §3)."""
    return UnexpectedError.make(Reason.CALLED_REQUEST_UNREADABLE,
                                f"the {what} request is not as it should be ({why}): raise it as an issue",
                                metadata={"request": what, **metadata}, violations=())


def read_request(what: str, stream: TextIO | None = None) -> dict[str, Any]:
    """The request on the first line of standard input. One that is not a JSON object is
    unexpected. The rest of the input is left to `Watcher`."""
    stream = stream or sys.stdin
    line = stream.readline()
    try:
        body = json.loads(line)
    except ValueError:
        body = None
    if not isinstance(body, dict):
        raise unreadable(what, "it is not a JSON object")
    return body


def field(body: Mapping[str, Any], name: str, kind: type, what: str) -> Any:
    """A field of a request, of the type the design gives it: another is unexpected."""
    value = body.get(name)
    if not isinstance(value, kind) or isinstance(value, bool) and kind is not bool:
        raise unreadable(what, f"{name} is missing or of the wrong type", field=name)
    return value


_APP = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def check_app(text: str) -> str:
    if not _APP.fullmatch(text):
        raise FormError("application", text, "letters, digits, '.', '_' and '-'", "NOT_AN_APPLICATION")
    return text


def application(argument: str) -> str:
    """The APP argument: refused, as a business error, where it is not a name."""
    return read_input("the APP argument", check_app, argument)


def login_kind(body: Mapping[str, Any], what: str) -> CredentialKind:
    try:
        return CredentialKind(field(body, "login", str, what))
    except ValueError as exc:
        raise unreadable(what, "login names no credential kind") from exc


def repository(body: Mapping[str, Any], name: str, kind: RepositoryKind, what: str) -> Repository:
    return Repository(kind, field(body, name, str, what))


def digest_of(text: Any, what: str) -> Digest:
    """A digest of a request; one that fails its form is unexpected, naming the field."""
    try:
        return Digest(str(text))
    except FormError as exc:
        raise exc.unexpected(f"the {what} request") from exc


def commit_of(text: Any, what: str) -> str:
    try:
        return check_commit(str(text))
    except FormError as exc:
        raise exc.unexpected(f"the {what} request") from exc


def done_with_errors(reason: Reason, message: str, errors: list[ProgrammeError]) -> Result:
    """The command's end where each action was tried and some failed: severity *error*, of
    the first failure's type, the others carried in `errors`; exit 3 (design §6)."""
    first = errors[0].result
    return Result(Outcome.ERROR, first.type, first.blip, reason.value, message=message,
                  errors=tuple(e.result for e in errors))


class Watcher:
    """The end of standard input, read as the caller's interruption (design §6, item 3):
    a thread reads to the end, and `interrupted` is set there. Where nothing called this
    `turpin` (a person at a terminal, a timer) there is no caller to interrupt it, so it
    never fires and the thread is not started."""

    def __init__(self, stream: TextIO | None = None, *, watching: bool | None = None):
        self.event = threading.Event()
        self._stream = stream or sys.stdin
        if called() if watching is None else watching:
            threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        try:
            while self._stream.readline():
                pass
        except (OSError, ValueError):
            pass
        self.event.set()

    @property
    def interrupted(self) -> bool:
        return self.event.is_set()

    def check(self, message: str) -> None:
        """Start no further step once interrupted: the front end exits 130 saying `message`."""
        if self.interrupted:
            raise KeyboardInterrupt(message)


def read_data(stream: TextIO | None = None) -> list[str]:
    """The lines of data a login reads, up to the closing line, which is removed. Without
    it the connection dropped before the data arrived whole, so nothing changes: a blip,
    exit 75 (design §6)."""
    stream = stream or sys.stdin
    lines: list[str] = []
    for text in stream:
        if text.rstrip("\n") == CLOSING_LINE:
            return lines
        lines.append(text.rstrip("\n"))
    raise TechnicalError.make(Reason.CALLED_INPUT_CUT_OFF,
                              "the input ended before it was complete, so nothing was changed: try again later",
                              blip=True)
