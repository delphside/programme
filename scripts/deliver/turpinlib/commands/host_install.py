"""`turpin host-install ENV|COPIER|BUILDER`: put `turpin-host` and its libraries on a machine
(design §6, §11, R38).

The target is an environment of the profile, or the machine of the release copier
(`[turpin.release].copy_on`) or the builder (`[turpin.build].on`) where it hosts no
environment. The machine is given a script to run (by `ssh`, or here where the machine is
this one), which as the owner's user with `sudo`:

- installs `turpin-host` and its libraries under `/usr/local`, as an install or an update;
- installs `jq` if it is missing, and refuses if `flock` or a tool the credential kind needs
  (`oci`) is absent;
- for an environment, writes the root-owned files `root-ops` decides by: the host-file
  allowlist (merged by `turpin-host allowlist`, never replaced), the ephemeral user prefix,
  and the one `sudo` rule. A copier or builder gets none of these.

The script is safe to repeat, so a blip is retried. `TURPIN_HOST_ROOT` prefixes every path,
as it does for `turpin-host`: a test's machine is a folder.
"""

from __future__ import annotations

import base64
import os
import shlex
import tempfile
from dataclasses import replace
from pathlib import Path

from .. import gates, hosts, profile, settings
from ..cli import Args, Context
from ..model import (BusinessError, CredentialKind, Environment, Outcome, Profile, Reason, Result,
                     TechnicalError)

USAGE = "usage: turpin host-install ENV|COPIER|BUILDER\n"
MIN_ARGS = MAX_ARGS = 1
FLAGS: dict[str, str] = {}

DELIVER = Path(__file__).resolve().parents[2]
# What is installed: the source beside `turpin`, the folder on the machine, and the mode.
COMMAND = ("turpin-host", "/usr/local/bin", "0755")
HOST_PATH = "/usr/local/bin/turpin-host"
LIBRARIES = (("lib/common.sh", "0644"), ("lib/toml.sh", "0644"), ("lib/toml.awk", "0644"),
             ("lib/registry.sh", "0644"))
LIB_DIR = "/usr/local/lib/turpin"
SUDOERS = "/etc/sudoers.d/turpin-host"
STATE_DIR = "/var/lib/turpin"

# The commands a credential kind needs on the machine (design §3 *Logins*).
TOOLS = {CredentialKind.DOCKER_CONFIG: (), CredentialKind.OCI_API_KEY: ("oci",),
         CredentialKind.OCI_INSTANCE_PRINCIPAL: ("oci",)}


def target_of(prof: Profile, name: str) -> tuple[str, CredentialKind, Environment | None]:
    """The machine `name` is, its credential kind, and its environment where it is one."""
    env = prof.environments.get(name)
    if env is not None:
        return env.machine, env.login, env
    if name == prof.copy_on:
        return prof.copy_on, prof.copy_login, None
    if name == prof.build_on:
        return prof.build_on, prof.build_login, None
    raise BusinessError.make(
        Reason.ENVIRONMENT_UNKNOWN,
        f"the profile has no environment {name} and {name} is not the release copier (copy_on) or the builder "
        f"(build.on)", metadata={"environment": name})


def install_file(source: str, folder: str, mode: str, sudo: str) -> str:
    """The line that writes one file, carried as base64 so nothing in it needs quoting."""
    text = base64.b64encode((DELIVER / source).read_bytes()).decode()
    return (f"printf '%s' {text} | base64 -d | {sudo} install -D -m {mode} /dev/stdin "
            f"\"$R{folder}/{Path(source).name}\"")


def under_root(path: str) -> str:
    """`path` under the machine's root, quoted: the application's name is in it."""
    return f'"$R"{shlex.quote(path)}'


def state_files(prof: Profile, env: Environment, sudo: str) -> list[str]:
    """The application's state folder, the environment's inside it and its `.env` (design §11), made for
    the deploy user, who cannot make them under `/var/lib/turpin`: each folder 0700 and owned by the user running this
    script, an empty `.env` 0600 where there is none. An existing `.env` is never touched."""
    folder = under_root(f"{STATE_DIR}/{prof.application}/{env.name}")
    owner = '-o "$(id -un)" -g "$(id -gn)"'
    app_folder = under_root(f"{STATE_DIR}/{prof.application}")
    return [f"{sudo} install -d -m 0700 {owner} {app_folder}",     # first: `install -d` makes a parent for root, and a lock shared by the application's environments is made here
            f"{sudo} install -d -m 0700 {owner} {folder}",
            f'[ -e {folder}/.env ] || {sudo} install -m 0600 {owner} /dev/null {folder}/.env']


def root_files(prof: Profile, sudo: str) -> list[str]:
    """What `root-ops` decides by (design §11): the host-file destinations and the ephemeral user
    prefix, from the profile as it is now, so a changed `host_files` list owes a rerun of this
    command; and the one `sudo` rule."""
    app = shlex.quote(prof.application)
    # one line per host file: destination, source within the payload, mode, enable (tab-separated)
    lines = "\n".join("\t".join((f.dest, f.src, f.mode, "true" if f.enable else "false"))
                      for f in prof.host_files)
    prefix = prof.ephemeral.user_prefix + "\n" if prof.ephemeral and prof.ephemeral.user_prefix else ""
    allow_dir = f"/etc/turpin/{prof.application}"
    return [
        f"{sudo} install -d -m 0755 \"$R/etc/turpin\" {under_root(allow_dir)}",
        # merged with what is still in use, never replaced (`turpin-host allowlist`); the closing
        # line says the lines arrived whole
        f"{{ printf '%s' {shlex.quote(lines)}; printf '\\n{hosts.CLOSING_LINE}\\n'; }} | {sudo} env "
        f"TURPIN_LIB=\"$R{LIB_DIR}\" \"$R{HOST_PATH}\" allowlist {app}",
        # a bad line in a sudoers file locks `sudo` out, so it is checked before it is installed;
        # both files are written to temporary files first, never installed from a pipe: an empty
        # prefix piped to `install /dev/stdin` over an existing file failed on CI's runner
        'T="$(mktemp)"; P="$(mktemp)"',
        "trap 'rm -f \"$T\" \"$P\"' EXIT",                      # on every way out, a refusal included
        f"printf '%s' {shlex.quote(prefix)} > \"$P\"",
        f"{sudo} install -m 0644 \"$P\" {under_root(allow_dir + '/ephemeral.prefix')}",
        f'printf "%s ALL=(root) NOPASSWD: {HOST_PATH} root-ops *\\n" "$(id -un)" > "$T"',
        'PATH="$PATH:/usr/sbin:/sbin" visudo -qcf "$T" >&2',
        f'{sudo} install -D -m 0440 "$T" "$R{SUDOERS}"',
    ]


def script_for(prof: Profile, login: CredentialKind, env: Environment | None, local: bool = False) -> str:
    """The script the machine runs. `env` is None for a copier or a builder, which gets the command
    and its libraries and none of the root-owned files nor a state folder.

    It is one function called at the end, so `bash -s` has read all of it before it runs any.
    A tool or a right that is missing is fundamental (docs/1.10): every failure, a `sudo` that
    wants a password included (`-n` never asks; a person at the terminal is asked), exits 2 with the tool's own text above a line
    naming the step, so no status of a tool's reaches `turpin` as another meaning; a Ctrl+C (130)
    stays 130."""
    sudo = "sudo" if local else "sudo -n"
    body = [install_file(*COMMAND, sudo)]
    body += [install_file(name, LIB_DIR, mode, sudo) for name, mode in LIBRARIES]
    body.append(f"command -v jq >/dev/null 2>&1 || {sudo} apt-get install -y jq >/dev/null </dev/null")
    body.append('command -v flock >/dev/null 2>&1 || { echo "flock (util-linux) is missing" >&2; exit 2; }')
    for tool in TOOLS[login]:
        body.append(f'command -v {tool} >/dev/null 2>&1 || {{ echo "{tool} is missing '
                    f'(needed by the {login.value} login)" >&2; exit 2; }}')
    if env is not None:
        body += root_files(prof, sudo)
        body += state_files(prof, env, sudo)
    body.append('echo "turpin-host installed"')
    lines = ["main() {", "  set -euo pipefail", '  R="${TURPIN_HOST_ROOT:-}"',
             "  trap 'c=$?; echo \"turpin host-install: stopped at: $BASH_COMMAND\" >&2; "
             "[ $c -eq 130 ] && exit 130; exit 2' ERR"]
    lines += [f"  {line}" for line in body]
    lines += ["}", "set -E", "main"]
    return "\n".join(lines) + "\n"


def run_here(script: str, name: str) -> None:
    """Run the script on this machine from a file of its own: a script is too long for one
    argument. It is attached to the person's terminal, so `sudo` can ask for a password; a
    Ctrl+C there is 130. The file is removed however this ends."""
    fd, path = tempfile.mkstemp(prefix="turpin-host-install-")     # mode 0600
    try:
        with os.fdopen(fd, "w") as out:
            out.write(script)
        hosts.call_attached([path], f"turpin host-install {name}", program="bash")
    except TechnicalError as exc:
        if exc.result.outcome is not Outcome.FATAL:
            raise
        raise TechnicalError(replace(exc.result, message=(
            f"host-install on this machine stopped (the lines above say why): "
            f"fix it, then run turpin host-install {name} again"))) from exc
    finally:
        os.unlink(path)


def run(args: Args, ctx: Context) -> Result:
    repo = profile.repo_dir()
    prof = profile.read_working_tree(repo)
    ctx.start_log(prof.application)
    machine, login, env = target_of(prof, args.positional[0])
    if env is not None:
        gates.host_files_conflict(prof, env)
    name = args.positional[0]
    if machine in (hosts.CONTROLLER, ""):
        # attached to the person's terminal, so `sudo` can ask for a password; Ctrl+C there is 130
        run_here(script_for(prof, login, env, local=True), name)
        return Result.ok()
    hosts.call_host(machine, ["-s"], log=ctx.log, data=script_for(prof, login, env),
                    program="bash", retry=True, timeout=settings.HOST_INSTALL_TIMEOUT,
                    where=f"run turpin host-install {name} again")
    return Result.ok()
