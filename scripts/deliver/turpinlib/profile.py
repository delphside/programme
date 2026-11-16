"""`app-profile.toml` at a commit or in the working tree, as a `Profile`, and the
machine's `APP.env` (design §8).

A setting missing or malformed is found where it is read: a fundamental
technical error, exit 2, naming the key, or the line where a file does not
parse. The commit's profile gives the gates their keys; the working tree's, the
rest; both are read by `parse`.
"""

from __future__ import annotations

import os
import re
import tempfile
import tomllib
from pathlib import Path
from typing import Any, Mapping

from . import gitrepo, settings
from .model import (CONTROLLER, BusinessError, CredentialKind, Environment, Ephemeral, HostFile,
                    Profile, ProfileError, Reason, Role, TechnicalError, Version, read_input)

__all__ = ["ProfileError", "parse", "read_working_tree", "read_at_commit",
           "read_app_env", "require", "repo_dir", "profile_path", "version_in_tree", "version_in_commit", "login_component"]

_ASSIGNMENT = re.compile(r"(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)")


def repo_dir() -> Path:
    """The application's checkout: `TURPIN_REPO`, else the working tree we are in."""
    named = os.environ.get(settings.ENV_REPO)
    return gitrepo.toplevel(named or Path.cwd())


def profile_path(repo: Path) -> Path:
    return Path(os.environ.get(settings.ENV_PROFILE) or repo / settings.PROFILE_FILE)


def read_working_tree(repo: Path) -> Profile:
    path = profile_path(repo)
    try:
        text = path.read_text()
    except OSError as exc:
        raise ProfileError.at(Reason.PROFILE_UNREADABLE, f"there is no readable profile at {path}",
                              source=str(path)) from exc
    return parse(text, str(path))


def read_at_commit(repo: Path, sha: str) -> Profile:
    """The profile as the commit holds it, as its hooks are (design §8)."""
    source = f"{settings.PROFILE_FILE} at {sha[:12]}"
    try:
        text = gitrepo.show(repo, sha, settings.PROFILE_FILE)
    except TechnicalError as exc:  # the commit is unknown here, or has no profile
        raise ProfileError.at(Reason.PROFILE_UNREADABLE, f"cannot read {source}: fetch the commit",
                              cause=exc.result, source=source) from exc
    return parse(text, source)


# ------------------------------------------------------------------- APP.env

def read_app_env(app: str) -> dict[str, str]:
    """The machine's `~/.config/turpin/APP.env`, as `KEY=VALUE` lines (comments,
    blank lines, `export` and one pair of quotes allowed). Absent is empty."""
    folder = Path(os.environ.get(settings.ENV_CONFIG_DIR) or Path.home() / ".config" / "turpin")
    path = folder / f"{app}.env"
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for number, line in enumerate(path.read_text().splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        found = _ASSIGNMENT.fullmatch(stripped)
        if not found:
            raise ProfileError.at(Reason.SETTINGS_LINE_UNPARSABLE,
                                  f"{path} line {number} does not parse: write it as KEY=VALUE",
                                  source=str(path), line=number)
        value = found.group(2).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        values[found.group(1)] = value
    return values


def require(values: Mapping[str, str], key: str, source: str) -> str:
    """A key a setting file must hold."""
    if not values.get(key):
        raise ProfileError.at(Reason.PROFILE_KEY_MISSING, f"{source} has no {key}: set it",
                              key=key, source=source)
    return values[key]


# -------------------------------------------------------------------- parsing

def parse(text: str, source: str) -> Profile:
    """The text of a profile, validated (design §8)."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ProfileError.at(Reason.PROFILE_UNREADABLE, f"{source} does not parse: {exc}",
                              source=source) from exc
    return _Reader(data, source).profile()


class _Reader:
    """Reads keys from a parsed profile; each failure names the key and the file."""

    def __init__(self, data: dict[str, Any], source: str):
        self.data = data
        self.source = source

    def bad(self, key: str, wanted: str) -> ProfileError:
        return ProfileError.at(Reason.PROFILE_KEY_MALFORMED,
                               f"{self.source}: {key} must be {wanted}", key=key, source=self.source)

    def get(self, table: Mapping[str, Any], path: str, kind: type | tuple, wanted: str,
            required: bool = False, default: Any = None) -> Any:
        key = path.rsplit(".", 1)[-1]
        if key not in table:
            if required:
                raise ProfileError.at(Reason.PROFILE_KEY_MISSING, f"{self.source}: {path} is missing: set it",
                                      key=path, source=self.source)
            return default
        value = table[key]
        if isinstance(value, bool) and kind is not bool:
            raise self.bad(path, wanted)
        if not isinstance(value, kind):
            raise self.bad(path, wanted)
        return value

    def strings(self, table: Mapping[str, Any], path: str, required: bool = False) -> tuple[str, ...]:
        value = self.get(table, path, list, "a list of strings", required, [])
        if not all(isinstance(item, str) for item in value):
            raise self.bad(path, "a list of strings")
        return tuple(value)

    def table(self, table: Mapping[str, Any], path: str) -> Mapping[str, Any]:
        return self.get(table, path, dict, "a table", False, {})

    def login(self, table: Mapping[str, Any], path: str) -> CredentialKind:
        text = self.get(table, path, str, "a string", False, CredentialKind.DOCKER_CONFIG.value)
        try:
            return CredentialKind(text)
        except ValueError:
            kinds = ", ".join(kind.value for kind in CredentialKind)
            raise self.bad(path, f"one of {kinds}") from None

    @staticmethod
    def machine(name: str) -> str:
        return CONTROLLER if name in (CONTROLLER, "control-node") else name

    def profile(self) -> Profile:
        d = self.data
        release, turpin = self.table(d, "release"), self.table(d, "turpin")
        build, copy = self.table(turpin, "turpin.build"), self.table(turpin, "turpin.release")
        eph = self.table(turpin, "turpin.ephemeral")
        deployed = self.table(self.table(d, "versions"), "versions.deployed")
        return Profile(
            application=self.get(d, "application", str, "a string", required=True),
            tag_prefix=self.get(release, "release.tag_prefix", str, "a string", required=True),
            history_prefixes=self.strings(release, "release.history_prefixes"),
            announcement=self.get(release, "release.announcement", str, "a string", default=""),
            deploy_marker=self.get(release, "release.deploy_marker", str, "a string", default=""),
            required_checks=self.strings(release, "release.required_checks"),
            required_hooks=self.strings(release, "release.required_hooks"),
            overridable=self.strings(release, "release.overridable"),
            candidates=self.get(turpin, "turpin.candidates", str, "a string", required=True),
            releases=self.get(turpin, "turpin.releases", str, "a string", required=True),
            images=self.strings(turpin, "turpin.images", required=True),
            payload_image=self.get(turpin, "turpin.payload_image", str, "a string"),
            join=self.strings(turpin, "turpin.join"),
            login=self.login(turpin, "turpin.login"),
            fallback=self.get(turpin, "turpin.fallback", str, "a string"),
            build_on=self.machine(self.get(build, "turpin.build.on", str, "a string", default=CONTROLLER)),
            build_login=self.login(build, "turpin.build.login"),
            copy_on=self.machine(self.get(copy, "turpin.release.copy_on", str, "a string", default=CONTROLLER)),
            copy_login=self.login(copy, "turpin.release.copy_login"),
            host_files=self.host_files(turpin),
            ephemeral=self.ephemeral(eph) if eph else None,
            deployed_path=self.get(deployed, "versions.deployed.path", str, "a string"),
            deployed_field=self.get(deployed, "versions.deployed.field", str, "a string"),
            environments={name: self.environment(name, table)
                          for name, table in self.table(d, "environments").items()},
            build_args=self.build_args(build))

    def build_args(self, build: Mapping[str, Any]) -> dict[str, str]:
        """`[turpin.build].args`: each build argument named for one of the `TURPIN_*` values a build
        has (`settings.BUILD_ARG_SOURCES`, without the prefix)."""
        args = self.get(build, "turpin.build.args", dict, "a table of build arguments to sources", default={})
        for name, source in args.items():
            if source not in settings.BUILD_ARG_SOURCES:
                raise self.bad(f"turpin.build.args.{name}", "one of " + ", ".join(settings.BUILD_ARG_SOURCES))
        return dict(args)

    def host_files(self, turpin: Mapping[str, Any]) -> tuple[HostFile, ...]:
        entries = self.get(turpin, "turpin.host_files", list, "a list of tables", default=[])
        found = []
        for i, entry in enumerate(entries):
            where = f"turpin.host_files[{i}]"
            if not isinstance(entry, dict):
                raise self.bad(where, "a table")
            found.append(HostFile(
                src=self.get(entry, f"{where}.src", str, "a string", required=True),
                dest=self.get(entry, f"{where}.dest", str, "a string", required=True),
                mode=self.get(entry, f"{where}.mode", str, "a string", default="0644"),
                enable=self.get(entry, f"{where}.enable", bool, "true or false", default=False)))
        return tuple(found)

    def ephemeral(self, eph: Mapping[str, Any]) -> Ephemeral:
        return Ephemeral(
            user_prefix=self.get(eph, "turpin.ephemeral.user_prefix", str, "a string", required=True),
            home=self.get(eph, "turpin.ephemeral.home", str, "a string", required=True),
            secrets=self.strings(eph, "turpin.ephemeral.secrets"))

    def environment(self, name: str, table: Mapping[str, Any]) -> Environment:
        where = f"environments.{name}"
        if not isinstance(table, dict):
            raise self.bad(where, "a table")
        role_text = self.get(table, f"{where}.role", str, "a string", required=True)
        try:
            role = Role(role_text)
        except ValueError:
            roles = ", ".join(r.value for r in Role)
            raise self.bad(f"{where}.role", f"one of {roles}") from None
        host = self.get(table, f"{where}.host", str, "a string")
        if host is not None and self.machine(host) == CONTROLLER:
            machine = CONTROLLER
        else:
            # the alias has one home where the profile keeps it for `board-hosts.py`: `[hosts.NAME].ssh`
            alias = self.get(self.table(self.table(self.data, "hosts"), f"hosts.{name}"), f"hosts.{name}.ssh",
                             str, "a string")
            machine = self.get(table, f"{where}.ssh", str, "a string", required=alias is None, default=alias)
        return Environment(
            name=name, role=role, machine=machine, login=self.login(table, f"{where}.login"),
            project=self.get(table, f"{where}.project", str, "a string"),
            url=self.get(table, f"{where}.url", str, "a string"),
            lock=self.get(table, f"{where}.lock", str, "a string"),
            pull_timeout=self.get(table, f"{where}.pull_timeout", int, "a number of seconds",
                                  default=settings.PULL_TIMEOUT_DEFAULT),
            host_files=self.get(table, f"{where}.host_files", bool, "true or false",
                                default=role in (Role.REHEARSAL, Role.PRODUCTION)),
            join=self.strings(table, f"{where}.join"))


# ----------------------------------------------------------------- the version file

def _version_source(tree: Path) -> tuple[_Reader, str, str]:
    """The profile's `versions.app` in `tree`: its reader, the version file and the pattern."""
    source = str(tree / settings.PROFILE_FILE)
    data = profile_data(tree)
    section = (data.get("versions") or {}).get("app") or {}
    reader = _Reader(data, source)
    return (reader, reader.get(section, "versions.app.file", str, "a string", required=True),
            reader.get(section, "versions.app.pattern", str, "a string", required=True))


def version_in_commit(repo: Path, sha: str) -> str:
    """The version the version file holds at commit `sha`, or '' where the commit has no profile,
    no version file or no version in it (a build need not have one)."""
    with tempfile.TemporaryDirectory() as scratch:
        tree = Path(scratch)
        try:
            if not gitrepo.export_paths(repo, sha, [settings.PROFILE_FILE], tree):
                return ""
            if not gitrepo.export_paths(repo, sha, [_version_source(tree)[1]], tree):
                return ""
            return str(version_in_tree(tree))
        except (TechnicalError, BusinessError):
            return ""


def version_source(tree: Path) -> tuple[str, re.Pattern]:
    """The version file and the compiled pattern whose one group is the version."""
    reader, file, pattern = _version_source(tree)
    try:
        wanted = re.compile(pattern, re.MULTILINE)
    except re.error as exc:
        raise reader.bad("versions.app.pattern", "a regular expression") from exc
    if wanted.groups < 1:
        raise reader.bad("versions.app.pattern", "a regular expression with one group, the version")
    return file, wanted


def profile_data(tree: Path) -> dict[str, Any]:
    """The profile of a checked-out tree as parsed TOML, for the keys no `Profile` field holds."""
    source = str(tree / settings.PROFILE_FILE)
    try:
        return tomllib.loads((tree / settings.PROFILE_FILE).read_text())
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ProfileError.at(Reason.PROFILE_UNREADABLE, f"cannot read the profile at {source}",
                              source=source) from exc


def version_in_tree(tree: Path) -> Version:
    """The application's version in a checked-out tree: the first line of the profile's
    `versions.app.file` that matches `versions.app.pattern`, whose one group is the version
    (design §8; the version file is the one a person edits). A key missing is a profile
    error; a file with no match, or a value that is not semver, is a business error naming
    the version file (R48)."""
    file, wanted = version_source(tree)
    try:
        text = (tree / file).read_text()
    except OSError as exc:
        raise BusinessError.make(Reason.VERSION_FILE_UNREADABLE, f"cannot read the version file {file}: "
                                 f"fix versions.app.file or the file", metadata={"file": file}) from exc
    found = wanted.search(text)
    if not found:
        raise BusinessError.make(Reason.VERSION_FILE_UNREADABLE,
                                 f"the version file {file} has no line the pattern versions.app.pattern matches",
                                 metadata={"file": file})
    return read_input(f"the version file {file}", Version.parse, found.group(1))


def login_component(prof: Profile, env: Environment) -> str:
    """The component whose docker login `env`'s deployer uses: the builder's where the environment
    is on the builder's machine (they share one login), else its own name (design §3 *Logins*)."""
    return "builder" if env.machine == prof.build_on else env.name
