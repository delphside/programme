"""The run log, and the gates each command expects to run (design §6, §9).

Every command writes a run log naming each gate it ran, and refuses if a gate in
its list did not run (R31). One JSON line per event, one file per run on this
machine, the last `RUN_LOGS_KEPT` per command kept. Identifiers only: never a
secret. `lib/common.sh` holds the same log for `turpin-host` and the payload.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from . import settings
from .model import BusinessError, Reason, Role

PASSED = "passed"
REFUSED = "refused"
REPORTED = "reported"
SET_ASIDE = "set-aside"


def expected_gates(command: str, role: Role | None = None, check: bool = False) -> tuple[str, ...]:
    """The gates `command` must have run by its end (§9). `role` is the deployed
    environment's, and `check` is `--check`, which stops before `smoke`."""
    if command == "build":
        return ("build-commit", "store-query", "store-immutable", "build-labels")
    if command == "deploy":
        gates = ["ref"]
        if role is Role.PRODUCTION:
            gates.append("production-record")
        if role is Role.REHEARSAL:
            gates.append("rehearsal-level")
        gates += ["lock", "state", "digests", "hooks-present", "pre-deploy"]
        return tuple(gates if check else gates + ["smoke"])
    if command == "rollback":
        return ("lock", "rollback-target")
    if command == "release":
        return ("rehearsal-passed", "on-main", "emergency-descent", "ci-passed",
                "version-spent-once", "tests-passed", "milestone", "release-check")
    return ()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class RunLog:
    """One run's log. With no file (`path` None) every call does nothing."""

    def __init__(self, path: Path | None = None, expected: Sequence[str] = ()):
        self.path = path
        self.expected = tuple(expected)
        self.ran: list[str] = []

    @classmethod
    def start(cls, app: str, command: str, args: Sequence[str],
              expected: Sequence[str] = ()) -> RunLog:
        folder = Path(os.environ.get(settings.ENV_LOG_DIR)
                      or Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state")
                      / "turpin") / app
        try:
            folder.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
            path = folder / f"{command}-{stamp}.{os.getpid()}.log"
            path.touch()
            for old in sorted(folder.glob(f"{command}-*.log"), key=lambda p: (p.stat().st_mtime, p.name),
                              reverse=True)[settings.RUN_LOGS_KEPT:]:
                old.unlink(missing_ok=True)
        except OSError:
            return cls(None, expected)   # a log that cannot be written is not a reason to stop
        log = cls(path, expected)
        log.event("start", args=" ".join(args))
        return log

    def event(self, kind: str, /, **fields: Any) -> None:
        if self.path is None:
            return
        line = json.dumps({"t": _now(), "event": kind, **fields}, separators=(",", ":"))
        try:
            with self.path.open("a") as out:
                out.write(line + "\n")
        except OSError:
            pass

    def gate(self, name: str, verdict: str, detail: str = "") -> None:
        """Record a gate as run: `passed`, `refused`, `reported` or `set-aside`."""
        self.ran.append(name)
        key = "reason" if verdict == SET_ASIDE else "detail"
        self.event("gate", name=name, result=verdict, **{key: detail})

    def finish_gates(self) -> None:
        """A command that ends with a gate of its list unrun refuses."""
        missing = [name for name in self.expected if name not in self.ran]
        if missing:
            self.event("gates-unrun", names=" ".join(missing))
            raise BusinessError.make(Reason.GATES_UNRUN,
                                     f"ended with gates unrun: {' '.join(missing)}",
                                     metadata={"gates": missing})
