#!/usr/bin/env python3
"""board-release.py — the board's half of a release: gates, carries, settle.

    board-release.py gate < request            # the release's board gates and what it carries
    board-release.py settle --announcement TEXT --tag TAG < record
    board-release.py next VERSION [--move N...]
    board-release.py checks SHA [--require NAME...]
    board-release.py publish TAG [--notes-start-tag PREV]
                       [--retrospective REASON --version V --commit SHA]

Run by `deliver` (delphside/programme#117) in the application's checkout, which is
where git is read. JSON in on standard input, JSON out on standard output. Exit:

    0   passed, or done
    1   refused (`gate`, `checks`), or the board or git could not be read
    3   some of it is done and some is left (`settle`, `next`, `publish`): named
    70  a profile error or a crash, which no caller reads as an answer

The repository is `DELIVER_GH_REPO` or the origin URL's; the rules are the board
model's (`release.py`, `milestone.py`, `repo.py`) and every GitHub call is
`sources.py`'s, over GraphQL where the token allows it and REST where it is
refused. A read that cannot be made refuses; it is never read as empty.

Design: records/2.5-changes/programme-tooling/117-generic-deliver-tool/design.md
(*The board model's part*).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from board import profile, release, repo  # noqa: E402
from board.sources import Unavailable  # noqa: E402

EXIT_REFUSED = 1
EXIT_PARTIAL = 3


def _out(data: dict) -> None:
    print(json.dumps(data, separators=(",", ":")))


def _environment() -> None:
    """The repository GitHub calls go to, and the programme file `set_field` reads
    the organisation from (this tool's own, where none is named)."""
    slug = os.environ.get("DELIVER_GH_REPO") or repo.origin_slug()
    if not slug:
        raise Unavailable("cannot tell the GitHub repository (set DELIVER_GH_REPO=owner/name)")
    os.environ[profile.ENV_REPOSITORY] = slug
    if not os.environ.get(profile.ENV_CONFIG):
        own = Path(__file__).resolve().parents[2] / "config" / "programme.toml"
        if own.is_file():
            os.environ[profile.ENV_CONFIG] = str(own)


def _flag(args: list[str], name: str) -> str | None:
    if name not in args:
        return None
    i = args.index(name)
    if i + 1 >= len(args):
        raise profile.ProfileError(f"{name} needs a value")
    return args[i + 1]


def _after(args: list[str], name: str) -> list[str]:
    """The words after `name`, up to the next flag."""
    if name not in args:
        return []
    out = []
    for item in args[args.index(name) + 1:]:
        if item.startswith("--"):
            break
        out.append(item)
    return out


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, args = argv[0], argv[1:]
    try:
        _environment()
        if cmd == "gate":
            result = release.gate(release.GateRequest.parse(json.load(sys.stdin)))
            _out(result.as_json())
            return 0 if result.passed else EXIT_REFUSED
        if cmd == "settle":
            announcement, tag = _flag(args, "--announcement"), _flag(args, "--tag")
            if not announcement or not tag:
                raise profile.ProfileError("settle needs --announcement and --tag")
            done = release.settle(json.load(sys.stdin), announcement, tag)
            _out(done)
            return 0 if done["settled"] else EXIT_PARTIAL
        if cmd == "next" and args:
            done = release.open_next(args[0], [int(n) for n in _after(args, "--move")])
            _out(done)
            return EXIT_PARTIAL if done["failed"] else 0
        if cmd == "checks" and args:
            ok, got, bad = release.checks(args[0], _after(args, "--require"))
            _out({"passed": ok, "checks": got, "failures": bad})
            return 0 if ok else EXIT_REFUSED
        if cmd == "publish" and args:
            done = release.publish(args[0], _flag(args, "--notes-start-tag"),
                                   _flag(args, "--retrospective"), _flag(args, "--version"),
                                   _flag(args, "--commit"))
            _out(done)
            return EXIT_PARTIAL if done["failed"] else 0
    except Unavailable as exc:
        # The board, git or GitHub could not be asked: a refusal, never a pass.
        _out({"refused": str(exc)})
        print(f"board-release: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    print(f"board-release: unknown command {' '.join(argv)}\n{__doc__}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(profile.run(main, sys.argv[1:]))
