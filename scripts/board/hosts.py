"""Host currency: what each host runs against what is installed and waiting.

The logic of `board-hosts.py`, with no I/O: the command a host is asked, how
its one line of answer is read, what counts as a finding and how both are
shown. Reaching the hosts is the command's.
"""

from __future__ import annotations

from dataclasses import dataclass

# Run on a host over ssh; prints one tab-separated line of seven fields:
# running kernel, newest installed kernel, Docker version, reboot pending,
# packages waiting, of which security, packages that need the reboot.
# Read-only: no `apt-get update`, so the package counts are as fresh as the
# host's last daily `apt` run. `dist-upgrade` is simulated because plain
# `upgrade` keeps back a new kernel's meta-package.
REMOTE_COMMAND = r"""running=$(uname -r)
newest=$(ls /boot/vmlinuz-* 2>/dev/null | sed 's|^/boot/vmlinuz-||' | sort -V | tail -1)
docker=$(docker --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
if [ -f /var/run/reboot-required ]; then reboot=yes; else reboot=no; fi
inst=$(apt-get -s -o Debug::NoLocking=1 dist-upgrade 2>/dev/null | grep '^Inst ')
waiting=$(printf '%s\n' "$inst" | grep -c '^Inst ')
security=$(printf '%s\n' "$inst" | grep '^Inst ' | grep -c -e '-security')
needing=$(cat /var/run/reboot-required.pkgs 2>/dev/null | tr '\n' ',' | sed 's/,$//')
printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$running" "$newest" "$docker" "$reboot" "$waiting" "$security" "$needing"
"""

_FIELDS = 7


@dataclass(frozen=True)
class Reading:
    label: str
    ssh: str
    running_kernel: str
    newest_kernel: str
    docker: str
    reboot_pending: bool
    waiting: int
    security: int
    reboot_packages: str


@dataclass(frozen=True)
class Finding:
    host: str  # a host's label, or `a / b` for a pair
    kind: str  # reboot, kernel, packages, pair-kernel or pair-docker
    message: str


def parse(label: str, ssh: str, line: str) -> Reading:
    """Reads the line `REMOTE_COMMAND` prints. `ValueError` when it is not that."""
    fields = line.rstrip("\r\n").split("\t")
    if len(fields) != _FIELDS:
        raise ValueError(f"{label}: expected {_FIELDS} tab-separated fields, got {len(fields)}")
    running, newest, docker, reboot, waiting, security, needing = fields
    if not running:
        raise ValueError(f"{label}: no running kernel in the answer")
    if reboot not in ("yes", "no"):
        raise ValueError(f"{label}: reboot pending must be yes or no, got {reboot!r}")
    try:
        count, secure = int(waiting), int(security)
    except ValueError:
        raise ValueError(f"{label}: package counts must be numbers, got {waiting!r} and {security!r}") from None
    return Reading(label, ssh, running, newest, docker, reboot == "yes", count, secure, needing)


def findings(readings: list[Reading], pairs: list[tuple[str, str]]) -> list[Finding]:
    """What is pending on each host, then where each pair differs. A pair whose
    host was not read is skipped."""
    out: list[Finding] = []
    for r in readings:
        if r.reboot_pending:
            why = f" ({r.reboot_packages})" if r.reboot_packages else ""
            out.append(Finding(r.label, "reboot",
                               f"{r.label} has a reboot pending{why}: installed fixes are on disk and not running"))
        if r.newest_kernel and r.newest_kernel != r.running_kernel:
            out.append(Finding(r.label, "kernel",
                               f"{r.label} runs kernel {r.running_kernel} and has {r.newest_kernel} installed"))
        if r.waiting:
            out.append(Finding(r.label, "packages",
                               f"{r.label} has {r.waiting} packages waiting, {r.security} of them security"))
    by_label = {r.label: r for r in readings}
    for label, other in pairs:
        a, b = by_label.get(label), by_label.get(other)
        if a is None or b is None:
            continue
        pair = f"{label} / {other}"
        if a.running_kernel != b.running_kernel:
            out.append(Finding(pair, "pair-kernel",
                               f"{label} and {other} run different kernels "
                               f"({a.running_kernel}, {b.running_kernel}): a release proven on one "
                               "was proven on another kernel"))
        if a.docker != b.docker:
            out.append(Finding(pair, "pair-docker",
                               f"{label} and {other} run different Docker versions "
                               f"({a.docker or 'none'}, {b.docker or 'none'}): the runtime under the "
                               "image is not the same runtime. A rehearsal host may lead deliberately "
                               "while an upgrade is proven there, and this check cannot tell a "
                               "deliberate lead from drift; it reports and the owner decides"))
    return out


def render(readings: list[Reading], found: list[Finding], colour: bool) -> str:
    header = ("host", "running kernel", "newest kernel", "docker", "reboot", "waiting/security")
    rows = [header] + [(r.label, r.running_kernel, r.newest_kernel or "-", r.docker or "-",
                        "yes" if r.reboot_pending else "no", f"{r.waiting}/{r.security}")
                       for r in readings]
    widths = [max(len(row[i]) for row in rows) for i in range(len(header))]
    lines = ["  ".join(cell.ljust(w) for cell, w in zip(row, widths)).rstrip() for row in rows]
    lines.append("")
    if found:
        start, end = ("\033[33m", "\033[0m") if colour else ("", "")
        lines.extend(f"{start}- {f.message}{end}" for f in found)
    else:
        ok, end = ("\033[32m", "\033[0m") if colour else ("", "")
        lines.append(f"{ok}Every host is current and the pairs agree.{end}")
    return "\n".join(lines)


def to_json(readings: list[Reading], found: list[Finding]) -> dict:
    return {
        "hosts": [{"label": r.label, "ssh": r.ssh, "running_kernel": r.running_kernel,
                   "newest_kernel": r.newest_kernel, "docker": r.docker,
                   "reboot_pending": r.reboot_pending, "waiting": r.waiting,
                   "security": r.security, "reboot_packages": r.reboot_packages}
                  for r in readings],
        "findings": [{"host": f.host, "kind": f.kind, "message": f.message} for f in found],
    }
