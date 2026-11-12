#!/usr/bin/env python3
"""board-hosts.py — are the hosts current: kernels, reboots, packages, Docker.

    board-hosts.py                # every host in the profile, as a table and its findings
    board-hosts.py --json         # the same, machine-readable
    board-hosts.py --host <label> # one host
    board-hosts.py --no-colour    # plain output
    board-hosts.py -C <dir> ...   # against the application at <dir>

Reads the hosts from the application's technical profile (`app-profile.toml`,
`PROGRAMME_PROFILE` replaces it), a table per host:

    [hosts.rehearsal]
    ssh = "app-rehearsal"          # the default ssh name
    env = ["REHEARSAL_SSH_HOST"]   # optional: the first of these variables set replaces `ssh`
    compare_with = "production"    # optional: another host, whose kernel and Docker should match

A missing `hosts` table is a profile error, never a built-in default. Each host
is asked `hosts.REMOTE_COMMAND` over ssh, read-only, and every host is read
before any is judged. `SSH_COMMAND` replaces `ssh` (a path), so a test can stub it.

Exit status (docs/1.10 *What a script's exit status means*): 0 no host owes a delivery
and the pairs agree; 1 there is a finding (a check reporting, not a gate); 2 a
host could not be read, so the check cannot judge (a closed door and a dead host
look alike); 70 the profile is missing or broken (`profile.EXIT_PROFILE_ERROR`).

Host currency is the Infrastructure application's; the `host-currency` activity
(docs/1.4) runs this. Requirement: delphside/tile-lite-elite#360. The logic is
`hosts.py`.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from board import hosts, profile  # noqa: E402

TIMEOUT_SECONDS = 40  # ssh's own ConnectTimeout is 10; this bounds a host that connects and hangs


def ssh_name(spec: profile.Section, label: str) -> str:
    """The first set variable of `env`, else `ssh`."""
    if "env" in spec.get(f"hosts.{label}"):
        for name in spec.strings(f"hosts.{label}.env"):
            if os.environ.get(name):
                return os.environ[name]
    return spec.string(f"hosts.{label}.ssh")


def configured(spec: profile.Section) -> dict[str, dict]:
    table = spec.get("hosts")
    if not isinstance(table, dict) or not table or not all(isinstance(t, dict) for t in table.values()):
        raise profile.ProfileError(f"{spec.source}: `hosts` must be a table of `[hosts.<label>]` tables")
    for label, entry in table.items():
        other = entry.get("compare_with")
        if other is not None and other not in table:
            raise profile.ProfileError(f"hosts.{label}: `compare_with` names `{other}`, which is not a host")
    return table


def read_host(label: str, ssh: str) -> hosts.Reading:
    """`ValueError` carries why the host could not be read."""
    command = os.environ.get("SSH_COMMAND") or "ssh"
    try:
        done = subprocess.run(
            [command, "-n", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", ssh, hosts.REMOTE_COMMAND],
            capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise ValueError(str(exc)) from None
    if done.returncode != 0:
        raise ValueError(done.stderr.strip() or f"ssh exited {done.returncode}")
    return hosts.parse(label, ssh, done.stdout)


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[0] == "-C":
        os.chdir(argv[1])
        argv = argv[2:]
    ap = argparse.ArgumentParser(prog="board-hosts.py", description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--host", metavar="LABEL", help="read one host")
    ap.add_argument("--no-colour", action="store_true")
    args = ap.parse_args(argv)

    spec = profile.technical()
    table = configured(spec)
    if args.host and args.host not in table:
        print(f"board-hosts: no host `{args.host}` in the profile (it has {', '.join(table)})",
              file=sys.stderr)
        return 2
    labels = [args.host] if args.host else list(table)

    readings, unreadable = [], []
    for label in labels:
        ssh = ssh_name(spec, label)
        try:
            readings.append(read_host(label, ssh))
        except ValueError as exc:
            unreadable.append(label)
            print(f"board-hosts: could not read {label} ({ssh}): {exc}", file=sys.stderr)
    if unreadable:
        print("board-hosts: a closed door and a dead host look alike here; nothing was judged.",
              file=sys.stderr)
        return 2

    pairs = [(label, table[label]["compare_with"]) for label in labels if "compare_with" in table[label]]
    found = hosts.findings(readings, pairs)
    if args.json:
        print(json.dumps(hosts.to_json(readings, found), indent=2))
    else:
        colour = sys.stdout.isatty() and not args.no_colour and "NO_COLOR" not in os.environ
        print(hosts.render(readings, found, colour))
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(profile.run(main, sys.argv[1:]))
