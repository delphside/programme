"""Host currency: what each host runs against what is installed and waiting.

The logic of `board-hosts.py`, with no I/O: the command a host is asked, how
its one line of answer is read, what counts as a finding and how both are
shown. Reaching the hosts is the command's.
"""

from __future__ import annotations

from dataclasses import dataclass

# Run on a host over SSH; prints one tab-separated line of eight fields:
# running kernel, newest installed kernel, Docker version, reboot pending,
# packages waiting, of which security, packages that need the reboot, and
# days since automatic updates last succeeded (the older of apt's two
# success stamps), or `never` where a stamp is missing. `STAMP_DIR` replaces
# `/var/lib/apt/periodic` for the test.
# `BOOT_DIR` replaces `/boot` for the test.
# Read-only for a non-root user, which the hosts' SSH users are: as root, a
# simulated `apt-get` may refresh its own cache. No `apt-get update`, so the
# package counts are as fresh as the host's last daily `apt` run.
# `dist-upgrade` is simulated because plain `upgrade` keeps back a new kernel's
# meta-package. A fact that cannot be read prints `FAILED`, which `parse`
# refuses, so a broken `apt` or a missing Docker never reads as current.
REMOTE_COMMAND = r"""running=$(uname -r)
boot=${BOOT_DIR:-/boot}
newest=$(ls "$boot"/vmlinuz-* 2>/dev/null | sed "s|^$boot/vmlinuz-||" | sort -V | tail -1)
docker=$(docker --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
if [ -f /var/run/reboot-required ]; then reboot=yes; else reboot=no; fi
if sim=$(apt-get -s -o Debug::NoLocking=1 dist-upgrade 2>/dev/null); then
  inst=$(printf '%s\n' "$sim" | grep '^Inst ')
  waiting=$(printf '%s\n' "$inst" | grep -c '^Inst ')
  security=$(printf '%s\n' "$inst" | grep '^Inst ' | grep -c -e '-security')
else
  waiting=FAILED; security=FAILED
fi
needing=$(cat /var/run/reboot-required.pkgs 2>/dev/null | tr '\n' ',' | sed 's/,$//')
# Each stamp is touched only by a success: the lists' update, and the upgrade
# run exiting 0. The older of the two is the age that matters.
dir=${STAMP_DIR:-/var/lib/apt/periodic}
updated=0
for f in update-success-stamp upgrade-stamp; do
  t=$(stat -c %Y "$dir/$f" 2>/dev/null) || { updated=never; break; }
  age=$(( ($(date +%s) - t) / 86400 ))
  [ "$age" -gt "$updated" ] && updated=$age
done
printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "${running:-FAILED}" "${newest:-FAILED}" "${docker:-FAILED}" "$reboot" "$waiting" "$security" "$needing" "$updated"
"""

_FIELDS = 8

# Automatic updates run daily; two missed days is a stopped service, not a
# late timer, and its security packages would otherwise pile up unseen.
STALE_UPDATE_DAYS = 2


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
    updated_days: int | None  # None: automatic updates have never run


@dataclass(frozen=True)
class Finding:
    host: str  # a host's label, or `a / b` for a pair
    kind: str  # reboot, kernel, packages, pair-kernel or pair-docker
    message: str


def parse(label: str, ssh: str, line: str) -> Reading:
    """Reads the line `REMOTE_COMMAND` prints. `ValueError` when it is not that."""
    lines = [l for l in line.splitlines() if l.strip()]
    if len(lines) != 1:
        raise ValueError(f"{label}: expected one line of answer, got {len(lines)}")
    fields = lines[0].rstrip("\r").split("\t")
    if len(fields) != _FIELDS:
        raise ValueError(f"{label}: expected {_FIELDS} tab-separated fields, got {len(fields)}")
    running, newest, docker, reboot, waiting, security, needing, updated = fields
    failed = [name for name, value in (("running kernel", running), ("newest kernel", newest),
                                       ("Docker", docker), ("apt", waiting)) if value == "FAILED"]
    if failed:
        raise ValueError(f"{label}: could not read {', '.join(failed)}")
    if not running:
        raise ValueError(f"{label}: no running kernel in the answer")
    if reboot not in ("yes", "no"):
        raise ValueError(f"{label}: reboot pending must be yes or no, got {reboot!r}")
    try:
        count, secure = int(waiting), int(security)
        days = None if updated == "never" else int(updated)
    except ValueError:
        raise ValueError(f"{label}: counts must be numbers, got {waiting!r}, {security!r} "
                         f"and {updated!r}") from None
    return Reading(label, ssh, running, newest, docker, reboot == "yes", count, secure, needing, days)


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
        # Automatic updates install the security packages themselves (1.2:
        # the platform maintaining itself), so only the others are owed a
        # delivery. Both counts are in the table.
        if r.updated_days is None or r.updated_days > STALE_UPDATE_DAYS:
            when = ("have never succeeded" if r.updated_days is None
                    else f"last succeeded {r.updated_days} days ago")
            waiting = (f", so its {r.security} security packages are not being installed"
                       if r.security else "")
            out.append(Finding(r.label, "updates", f"{r.label}'s automatic updates {when}{waiting}"))
        others = r.waiting - r.security
        if others > 0:
            out.append(Finding(r.label, "packages",
                               f"{r.label} has {others} packages waiting that automatic updates "
                               "do not install"))
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
                               "image may not be the same runtime. A rehearsal host may lead deliberately "
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
        lines.append(f"{ok}No host owes a delivery and the pairs agree.{end}")
    return "\n".join(lines)


def to_json(readings: list[Reading], found: list[Finding]) -> dict:
    return {
        "hosts": [{"label": r.label, "ssh": r.ssh, "running_kernel": r.running_kernel,
                   "newest_kernel": r.newest_kernel, "docker": r.docker,
                   "reboot_pending": r.reboot_pending, "waiting": r.waiting,
                   "security": r.security, "reboot_packages": r.reboot_packages,
                   "updated_days": r.updated_days}
                  for r in readings],
        "findings": [{"host": f.host, "kind": f.kind, "message": f.message} for f in found],
    }
