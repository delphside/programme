"""The front end (design §5, §6): the subcommand, the flags, a `Result`'s exit status.

Exit statuses (design §6, docs/1.10): 0 done; 1 stopped, a gate refused or a
business error; 2 a fundamental technical error; 75 a blip that kept failing;
70 an unexpected error, its text in the run log; 3 done with errors; 64 a usage
error; 130 interrupted.

A subcommand with no module in `commands.COMMANDS` is run by `turpin-legacy`,
with the original arguments.
"""

from __future__ import annotations

import importlib
import json
import os
import signal
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from . import commands, settings
from .model import (EXIT_INTERRUPTED, FormError, EXIT_OK, EXIT_USAGE, Outcome, ProgrammeError, Reason,
                    Result, TechnicalError, UnexpectedError, exit_status)
from .runlog import RunLog

# The usage text is owned here. `turpin-legacy`'s header carries its own copy until
# T8 (delphside/programme#117) deletes it.
USAGE = """\
usage: turpin build [REF] [--local]
       turpin deploy ENV REF [--wait[=MIN]] [--check] [--set-aside GATE REASON]
                             [--unrecorded REASON] [--off-level REASON]
       turpin release [--expect VERSION] [--commit REF] [--emergency REASON]
                      [--skip-rehearsal REASON] [--set-aside GATE REASON] [--check]
       turpin settle VERSION       turpin rollback ENV      turpin status ENV
       turpin list ENV             turpin prune [--dry-run]
       turpin login COMPONENT      (controller, builder, copier, or an ENV)
       turpin env create|destroy NAME      turpin host-install ENV
       turpin promote APP      turpin remove APP
                       (called by release and prune: a request on standard input)

exit: 0 done; 1 refused or failed; 2 fundamental technical error; 3 done with
errors; 64 usage; 70 unexpected; 75 try again later; 130 interrupted
"""

# Every subcommand, so a misspelt one is a usage error and a real one not yet
# ported is passed to `turpin-legacy`.
KNOWN_COMMANDS = ("build", "deploy", "release", "settle", "rollback", "status", "list",
                  "prune", "login", "host-install", "env", "promote", "remove")

# The flags that set a gate aside (design §6): each takes a reason, and
# `--set-aside` a gate and then a reason.
GATE_FLAGS = {"--emergency": 1, "--skip-rehearsal": 1, "--unrecorded": 1,
              "--off-level": 1, "--set-aside": 2}

LEGACY = Path(__file__).resolve().parents[1] / "turpin-legacy"


class UsageError(Exception):
    """A bad flag or a missing argument: exit 64, naming it."""


@dataclass
class Args:
    positional: list[str] = field(default_factory=list)
    switches: set[str] = field(default_factory=set)
    values: dict[str, str] = field(default_factory=dict)      # a flag that takes a value; "" for a bare optional one
    reasons: dict[str, str] = field(default_factory=dict)     # a gate flag to its reason
    set_aside: list[tuple[str, str]] = field(default_factory=list)


def _reason(flag: str, words: list[str]) -> str:
    """The reason after a gate flag: present, and not another flag."""
    if not words or not words[0] or words[0].startswith("--"):
        raise UsageError(f"{flag} needs a reason")
    return words.pop(0)


def parse_args(argv: Sequence[str], module) -> Args:
    """Parse `argv` against what a command module declares: `FLAGS` (a name to
    "switch", "value" or "optional"), `GATE_FLAGS`, `MIN_ARGS`, `MAX_ARGS`."""
    flags = getattr(module, "FLAGS", {})
    gate_flags = getattr(module, "GATE_FLAGS", ())
    args, words = Args(), list(argv)
    while words:
        word = words.pop(0)
        name, equals, inline = word.partition("=")
        if not word.startswith("--"):
            args.positional.append(word)
        elif name in gate_flags and name in GATE_FLAGS:
            if name == "--set-aside":
                gate = _reason(name, words)
                args.set_aside.append((gate, _reason(name, words)))
            else:
                args.reasons[name] = _reason(name, words)
        elif flags.get(name) == "switch" and not equals:
            args.switches.add(name)
        elif flags.get(name) == "optional":
            args.values[name] = inline
        elif flags.get(name) == "value":
            if not equals and not words:
                raise UsageError(f"{name} needs a value")
            args.values[name] = inline if equals else words.pop(0)
        else:
            raise UsageError(f"unknown flag {name}")
    low, high = getattr(module, "MIN_ARGS", 0), getattr(module, "MAX_ARGS", 0)
    if not low <= len(args.positional) <= high:
        raise UsageError("missing argument" if len(args.positional) < low else "too many arguments")
    return args


class Context:
    """What a command is given besides its arguments: the run log, started once it
    knows the application."""

    def __init__(self, command: str, argv: Sequence[str], args: Args):
        self.command, self.argv, self.args = command, list(argv), args
        self.log = RunLog()

    def start_log(self, app: str, expected: Sequence[str] = ()) -> RunLog:
        self.log = RunLog.start(app, self.command, self.argv, expected)
        for flag, reason in self.args.reasons.items():
            self.log.event("override", flag=flag.removeprefix("--"), reason=reason)
        for gate, reason in self.args.set_aside:
            self.log.event("override", flag=f"set-aside:{gate}", reason=reason)
        return self.log


def report(result: Result, ctx: Context | None = None) -> int:
    """A result's message to the person, its line to the run log, and its exit status."""
    code = exit_status(result)
    if result.outcome is not Outcome.OK and result.message:
        print(f"turpin: {result.message}", file=sys.stderr)
    if os.environ.get(settings.ENV_CALLED) == "1" and result.outcome is not Outcome.OK:
        # called by another `turpin`: its result object, the last line on standard error
        print("@result " + json.dumps(result.to_json(), separators=(",", ":")), file=sys.stderr)
    if ctx is not None:
        ctx.log.event("result", exit=code, result=result.to_json())
    return code


def _unexpected(exc: BaseException, ctx: Context | None) -> int:
    """An error the code did not expect: exit 70, its text in the run log."""
    text = "".join(traceback.format_exception(exc))
    error = UnexpectedError.make(
        Reason.UNEXPECTED_EXCEPTION,
        "an unexpected error stopped the run: raise it as an issue, with the run log",
        metadata={"exception": f"{type(exc).__name__}: {exc}"})
    if ctx is None or ctx.log.path is None:
        print(text, file=sys.stderr)    # no run log to hold it
    else:
        ctx.log.event("unexpected", text=text)
    return report(error.result, ctx)


def _restore_for_exec() -> None:
    """Hand `turpin-legacy` the process state the caller gave us. Python ignores
    SIGPIPE and SIGXFSZ at start, and an ignored signal survives `exec`, so a Bash
    pipeline would not see a closed pipe as it does elsewhere; and PEP 538 sets
    `LC_CTYPE` where the locale was C, so the original is put back from the
    environment `exec` gave us (Linux; elsewhere it is left)."""
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    signal.signal(signal.SIGXFSZ, signal.SIG_DFL)
    try:
        initial = Path("/proc/self/environ").read_bytes().split(b"\0")
    except OSError:
        return
    for entry in initial:
        name, _, value = entry.partition(b"=")
        if name == b"LC_CTYPE":
            os.environ["LC_CTYPE"] = os.fsdecode(value)
            return
    os.environ.pop("LC_CTYPE", None)


def delegate(argv: Sequence[str]) -> int:
    """Run the Bash `turpin-legacy` in this process's place, with the arguments
    unchanged."""
    try:
        _restore_for_exec()
        os.execv(LEGACY, [str(LEGACY), *argv])
    except OSError as exc:
        return report(TechnicalError.make(
            Reason.NOT_PORTED, f"cannot run {LEGACY.name}: it is missing or not executable",
            metadata={"exception": str(exc)}).result)
    return EXIT_OK   # execv does not return; reached only where a test replaces it


def main(argv: Sequence[str]) -> int:
    if not argv:
        print(USAGE, file=sys.stderr, end="")
        return EXIT_USAGE
    command = argv[0]
    if command in ("-h", "--help", "help"):
        print(USAGE, end="")
        return EXIT_OK
    module_name = commands.COMMANDS.get(command)
    if module_name is None:
        if command in KNOWN_COMMANDS:
            return delegate(argv)
        print(f"turpin: unknown command {command}\n{USAGE}", file=sys.stderr, end="")
        return EXIT_USAGE
    ctx: Context | None = None
    try:
        module = importlib.import_module(f"{commands.__name__}.{module_name}")
        try:
            args = parse_args(argv[1:], module)
        except UsageError as exc:
            print(f"turpin: {exc}\n{getattr(module, 'USAGE', USAGE)}", file=sys.stderr, end="")
            return EXIT_USAGE
        ctx = Context(command, argv[1:], args)
        result = module.run(args, ctx) or Result.ok()
        if result.outcome in (Outcome.OK, Outcome.WARNING):
            ctx.log.finish_gates()
        return report(result, ctx)
    except ProgrammeError as exc:
        return report(exc.result, ctx)
    except KeyboardInterrupt as exc:
        print(f"turpin: {exc.args[0] if exc.args else 'interrupted'}", file=sys.stderr)
        return EXIT_INTERRUPTED
    except FormError as exc:    # a value nobody translated: unexpected, its field kept
        return report(exc.unexpected("a value made in this run").result, ctx)
    except Exception as exc:
        return _unexpected(exc, ctx)
