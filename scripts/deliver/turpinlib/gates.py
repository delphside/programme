"""The gates of §9 that are not the board model's, as a deploy runs them on the controller:
`ref` (what REF names, and that a build of it is stored), `production-record`,
`rehearsal-level`, and the check that two environments do not remove each other's host
files. The gates the host runs (`lock`, `state`, `digests`, `hooks-present`, `pre-deploy`,
`smoke`) reach the run log from `hosts.py`.

A gate that refuses logs itself as refused and raises a business error whose message
starts `refused at gate NAME:`, so the run log and the operator's screen say the same.
A read that cannot be made raises its own technical error and is never read as refused
or as passed (design §4, R62).
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from . import gitrepo, hosts, profile, settings
from .model import (CONTROLLER, BusinessError, Digest, Environment, Profile, ProfileError, Reason,
                    ReleaseRecord, Repository, RepositoryKind, Role, TechnicalError, Version, read_input)
from .registry.port import BuildImage, RegistryPort, resolve_commit
from .runlog import PASSED, REFUSED, SET_ASIDE, RunLog

_VERSION_REF = re.compile(r"v?[0-9]+\.[0-9]+\.[0-9]+")
_SHA_REF = re.compile(rf"[0-9a-f]{{{settings.SHORT_SHA_MIN},40}}")
LOCAL_IMAGE = "turpin-local/{app}-{image}:{sha}"    # what `build --local` loads into Docker


@dataclass(frozen=True)
class Resolved:
    """What REF names: the commit, its version where it has one, the images by digest (or,
    for a local build, by image id), the release record where there is one, and the
    commit's own profile, which gives the gates their keys (design §8)."""
    commit: str
    version: str
    images: Mapping[str, Digest]
    record: ReleaseRecord | None
    commit_profile: Profile
    local: bool = False


def refuse(log: RunLog, gate: str, reason: Reason, message: str, **metadata) -> BusinessError:
    """The gate refused: logged, and the error to raise."""
    log.gate(gate, REFUSED, message)
    return BusinessError.make(reason, f"refused at gate {gate}: {message}", metadata={"gate": gate, **metadata})


# ---------------------------------------------------------------- the request's own checks

def check_flags_for_role(log: RunLog, env: Environment, unrecorded: bool, off_level: bool) -> None:
    """`--unrecorded` is for the production role, `--off-level` for the rehearsal's."""
    for given, flag, role in ((unrecorded, "--unrecorded", Role.PRODUCTION), (off_level, "--off-level", Role.REHEARSAL)):
        if given and env.role is not role:
            raise BusinessError.make(Reason.OVERRIDE_WRONG_ROLE,
                                     f"{flag} is for the {role.value} role, and {env.name} is {env.role.value}: leave it out",
                                     metadata={"flag": flag, "environment": env.name})


def host_files_conflict(prof: Profile, env: Environment) -> None:
    """Two environments of one application on one machine that both install host files
    would each remove the other's on a deploy (§9, *no mutual removal*)."""
    names = sorted(e.name for e in prof.environments.values() if e.machine == env.machine and e.host_files)
    if len(names) > 1 and env.name in names:
        raise BusinessError.make(
            Reason.HOST_FILES_CONFLICT,
            f"environments {' '.join(names)} share a machine and all install host files, so each would remove "
            f"the other's: set host_files = false on all but one", metadata={"environments": names})


# ---------------------------------------------------------------- ref

def _stored_build(log: RunLog, registry: Callable[[], RegistryPort], prof: Profile, commit_profile: Profile,
                  commit: str) -> dict[str, Digest]:
    """Each image of the commit's profile, by digest, from candidates; one absent refuses."""
    port, candidates = registry(), Repository(RepositoryKind.CANDIDATES, prof.candidates)
    found: dict[str, Digest] = {}
    missing = []
    for name in commit_profile.images:
        image = port.find_image(candidates, BuildImage(commit, name))
        if image is None:
            missing.append(name)
        else:
            found[name] = image.digest
    if missing:
        raise refuse(log, "ref", Reason.REF_NO_BUILD,
                     f"no build in candidates for {commit[:12]} (missing {' '.join(missing)}): run turpin build",
                     commit=commit)
    return found


def commit_profile_of(log: RunLog, repo: Path, commit: str) -> Profile:
    """The profile at `commit`. A commit this repository lacks is a refused ref: fetch it."""
    try:
        return profile.read_at_commit(repo, commit)
    except ProfileError:
        try:
            gitrepo.git(repo, "cat-file", "-e", f"{commit}^{{commit}}")
        except TechnicalError:
            raise refuse(log, "ref", Reason.REF_UNKNOWN,
                         f"{commit} is not in this repository: git fetch, then try again", ref=commit) from None
        raise


def local_build(repo: Path, prof: Profile, ref: str) -> Resolved | None:
    """A preview on the controller may run an image `build --local` loaded into Docker:
    named by the commit REF gives, identified by Docker's image id. None where there is none."""
    try:
        commit = gitrepo.git(repo, "rev-parse", "--verify", "-q", f"{ref}^{{commit}}").strip()
    except TechnicalError:
        return None
    if not commit:
        return None
    commit_profile = profile.read_at_commit(repo, commit)
    ids: dict[str, Digest] = {}
    for name in commit_profile.images:
        try:
            done = subprocess.run(
                ["docker", "image", "inspect", LOCAL_IMAGE.format(app=prof.application, image=name, sha=commit),
                 "--format", "{{.Id}}"], capture_output=True, text=True,
                timeout=settings.DOCKER_INSPECT_TIMEOUT, stdin=subprocess.DEVNULL)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None
        if done.returncode != 0 or not done.stdout.strip():
            return None
        ids[name] = Digest(done.stdout.strip())
    if not ids:
        return None
    return Resolved(commit, profile.version_in_commit(repo, commit), ids, None, commit_profile, local=True)


def resolve(log: RunLog, repo: Path, prof: Profile, env: Environment, ref: str, *,
            registry: Callable[[], RegistryPort], unrecorded: bool) -> Resolved:
    """The `ref` gate: REF checked against the environment's role (R6) and resolved to
    the digests of a build stored in candidates, or, for production, of a record."""
    role = env.role
    if role is Role.PREVIEW and env.machine == CONTROLLER and not _VERSION_REF.fullmatch(ref):
        local = local_build(repo, prof, ref)
        if local is not None:
            log.gate("ref", PASSED, f"resolved {local.commit[:12]} (a local build)")
            return local
    try:
        gitrepo.fetch_tags(repo)
    except TechnicalError as exc:
        log.event("fetch-tags-failed", reason=exc.result.reason)   # a stale view of the tags is all it costs
    resolved = _resolve_ref(log, repo, prof, env, ref, registry, unrecorded)
    log.gate("ref", PASSED, f"resolved {resolved.commit[:12]}" + (f" (version {resolved.version})" if resolved.version else ""))
    return resolved


def _resolve_ref(log: RunLog, repo: Path, prof: Profile, env: Environment, ref: str,
                 registry: Callable[[], RegistryPort], unrecorded: bool) -> Resolved:
    production = env.role is Role.PRODUCTION
    if _VERSION_REF.fullmatch(ref):
        if unrecorded:
            raise refuse(log, "ref", Reason.REF_UNKNOWN,
                         f"--unrecorded takes a full SHA, not the version {ref}: leave the flag out", ref=ref)
        version = str(read_input("REF", Version.parse, ref.removeprefix("v")))
        tag = gitrepo.tag_for_version(repo, prof, version)
        record = None
        if tag is not None:
            try:
                record = gitrepo.record_of_tag(repo, tag)
            except BusinessError as exc:
                if exc.result.reason != Reason.RECORD_VERSION_UNKNOWN.value:
                    raise
                raise refuse(log, "ref", Reason.REF_RECORD_UNREADABLE,
                             f"tag {tag} carries a record version this tool does not know", tag=tag) from exc
        if record is not None:
            return Resolved(record.commit, str(record.version), record.images, record,
                            profile.read_at_commit(repo, record.commit))
        if production:
            raise refuse(log, "production-record", Reason.PRODUCTION_RECORD_MISSING,
                         f"no record for version {version}: production deploys only rehearsed releases "
                         f"(turpin release makes the record); --unrecorded takes a full SHA", version=version)
        if tag is None:
            raise refuse(log, "ref", Reason.REF_UNKNOWN, f"no tag or record for version {version}", version=version)
        commit = gitrepo.git(repo, "rev-parse", f"{tag}^{{commit}}").strip()     # a release made before the tool
        commit_profile = commit_profile_of(log, repo, commit)
        return Resolved(commit, version, _stored_build(log, registry, prof, commit_profile, commit), None, commit_profile)
    if not _SHA_REF.fullmatch(ref):
        raise refuse(log, "ref", Reason.REF_UNKNOWN, f"{ref} is neither a SHA nor a version", ref=ref)
    if production and (len(ref) != 40 or not unrecorded):
        raise refuse(log, "production-record", Reason.PRODUCTION_RECORD_MISSING,
                     "production takes a version with a record; a raw SHA needs --unrecorded REASON and a full SHA",
                     ref=ref)
    commit = ref
    if len(ref) != 40:
        port = registry()
        try:
            commit = resolve_commit(port.list_versions(Repository(RepositoryKind.CANDIDATES, prof.candidates)),
                                    ref, "REF")
        except BusinessError as exc:
            if exc.result.reason not in (Reason.SHORT_SHA_NO_BUILD.value, Reason.SHORT_SHA_AMBIGUOUS.value):
                raise
            matches = exc.result.metadata.get("matches") or []
            raise refuse(log, "ref", Reason(exc.result.reason),
                         f"{exc.result.message}" + (f" ({' '.join(matches)})" if matches else ""), ref=ref) from exc
    commit_profile = commit_profile_of(log, repo, commit)
    images = _stored_build(log, registry, prof, commit_profile, commit)
    return Resolved(commit, profile.version_in_commit(repo, commit), images, None, commit_profile)


# ---------------------------------------------------------------- production-record

def production_record(log: RunLog, prof: Profile, resolved: Resolved, registry: Callable[[], RegistryPort], *,
                      unrecorded_reason: str | None, copy: Callable[[Resolved], None] | None) -> None:
    """A production deploy needs a record for VERSION whose digests releases holds; or
    `--unrecorded`, where the release copier puts `SHA-IMAGE` into releases (no version
    is spent). `copy` is None under `--check`, which changes nothing."""
    if resolved.record is not None:
        port, releases = registry(), Repository(RepositoryKind.RELEASES, prof.releases)
        for name in resolved.commit_profile.images:
            digest = resolved.images.get(name)
            if digest is None:
                raise refuse(log, "production-record", Reason.PRODUCTION_RECORD_NOT_IN_RELEASES,
                             f"the record names no image {name}", image=name)
            if port.find_image(releases, digest) is None:
                raise refuse(log, "production-record", Reason.PRODUCTION_RECORD_NOT_IN_RELEASES,
                             f"the record's {name} digest is not in releases", image=name)
        log.gate("production-record", PASSED, f"record for {resolved.version}")
        return
    if copy is not None:
        try:
            copy(resolved)
        except BusinessError as exc:
            raise refuse(log, "production-record", Reason.COPY_TO_RELEASES_FAILED,
                         f"the copy to releases failed: {exc.result.message}") from exc
    log.gate("production-record", SET_ASIDE, f"unrecorded: {unrecorded_reason}")


# ---------------------------------------------------------------- rehearsal-level

def rehearsal_level(log: RunLog, repo: Path, prof: Profile, env: Environment, resolved: Resolved, *,
                    off_level_reason: str | None) -> None:
    """A cycle's first deploy to a rehearsal-role environment is production's current
    record, the same digests (§9). Production is read from its host state over `ssh`."""
    log.event("ssh-read", env=env.name, what="host state")
    status = hosts.host_status(env.machine, prof.application, env.name, log=log)
    made = gitrepo.newest_release_made(repo, prof)
    deployed = status.deployed
    later = [d.deployed for d in (deployed.current, deployed.previous) if d is not None and d.deployed]
    if any(when >= made for when in later):
        log.gate("rehearsal-level", PASSED, "a later deploy of the cycle")
        return
    if off_level_reason is not None:
        log.gate("rehearsal-level", SET_ASIDE, f"off level: {off_level_reason}")
        return
    production = next((e for e in prof.environments.values() if e.role.value == "production"), None)
    if production is None:
        raise refuse(log, "rehearsal-level", Reason.REHEARSAL_OFF_LEVEL,
                     "the profile has no production environment to start from")
    log.event("ssh-read", env=production.name, what="host state")
    current = hosts.host_status(production.machine, prof.application, production.name, log=log).deployed.current
    if current is None:
        raise refuse(log, "rehearsal-level", Reason.REHEARSAL_OFF_LEVEL,
                     "production has no turpin state; a first cycle needs --off-level REASON")
    if current.record is None:
        raise refuse(log, "rehearsal-level", Reason.REHEARSAL_OFF_LEVEL,
                     "production runs a build with no record (deployed before the tool); needs --off-level REASON")
    if {k: str(v) for k, v in current.record.images.items()} == {k: str(v) for k, v in resolved.images.items()}:
        log.gate("rehearsal-level", PASSED, f"starts from production's record {current.record.version}")
        return
    raise refuse(log, "rehearsal-level", Reason.REHEARSAL_OFF_LEVEL,
                 f"a cycle starts from production's current record ({current.record.version}); this deploy is not it. "
                 f"Use --off-level REASON")
