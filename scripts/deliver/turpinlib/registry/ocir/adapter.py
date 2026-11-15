"""The top layer (design §3 *The registry adapter*): the `OCIR` implementation of the
registry port. Each operation is a sequence of Oracle calls (`calls.py`), with the
switches (every platform, digests preserved, on the release copy) and the rules:

- validation before any call: each value's form, the tag forms, the request's shape;
- the keep list: a digest in it is refused, with no call;
- no overwrite: a version tag or `VERSION-record` that releases already holds with other
  contents is never written, since OCIR has no immutable repositories; a copy of the same
  digest is a no-op (G9, R4, R7);
- the tag forms: `SHA-IMAGE` in candidates, `VERSION-IMAGE` and `VERSION-record` in
  releases;
- the remove sequence: the keep list, then that the tag still names the chosen digest,
  then find the image by digest, then delete it.

It wraps whatever comes from below with the operation's context (which image, which
step), keeping its type and reason (design §3 *Validation and errors*, step 3).
"""

from __future__ import annotations

import contextlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Collection, Iterator, Mapping

from ... import profile, settings
from ...model import (Api, BusinessError, Build, Component, ComponentKind, CredentialForm, CredentialKind,
                      Digest, Image, ProfileError, ProgrammeError, Reason, ReleaseRecord, Repository,
                      RepositoryKind, TechnicalError, UnexpectedError, Version, Violation, check_commit,
                      FormError)
from ...runlog import RunLog
from ..port import BuildImage, Promoted, ReleaseImage, Removal
from . import calls
from .calls import Gateway

_IMAGE_NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9._-]*")
_CANDIDATE_TAG = re.compile(r"([0-9a-f]{40})-(.+)")
_RELEASE_TAG = re.compile(r"((?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*))-(.+)")
RECORD = "record"


# ------------------------------------------------------------------- tag forms

def candidate_tag(commit: str, image: str) -> str:
    """`SHA-IMAGE`."""
    return f"{commit}-{image}"


def release_tag(version: Version, image: str) -> str:
    """`VERSION-IMAGE`."""
    return f"{version}-{image}"


def record_tag(version: Version) -> str:
    """`VERSION-record`."""
    return f"{version}-{RECORD}"


# ----------------------------------------------------------------------- setup

@dataclass(frozen=True)
class OcirConfig:
    """What the adapter reads from the machine's `APP.env` (design §3 *The registry
    address*). `registry` is `HOST/NAMESPACE`; the rest is needed only by the credential
    kind or operation that uses it."""
    app: str
    registry: str
    config_dir: Path
    user: str | None = None
    token_cmd: str | None = None
    compartment: str | None = None
    oci_config_file: str | None = None

    @classmethod
    def from_app_env(cls, app: str) -> OcirConfig:
        """Read `APP.env`; a missing `TURPIN_REGISTRY` is a fundamental technical error."""
        values = profile.read_app_env(app)
        source = f"{app}.env"
        folder = Path(os.environ.get(settings.ENV_CONFIG_DIR) or Path.home() / ".config" / "turpin")
        return cls(app, profile.require(values, settings.ENV_REGISTRY, source), folder,
                   values.get(settings.ENV_REGISTRY_USER), values.get(settings.ENV_TOKEN_CMD),
                   values.get(settings.ENV_COMPARTMENT),
                   values.get(settings.ENV_OCI_CONFIG_FILE) or os.environ.get(settings.ENV_OCI_CONFIG_FILE))

    def authfile(self, component: ComponentKind) -> Path:
        """`~/.config/turpin/auth/APP/COMPONENT.json` (design §3 *Logins*)."""
        return self.config_dir / "auth" / self.app / f"{component.value}.json"

    def need(self, value: str | None, key: str) -> str:
        if not value:
            raise ProfileError.at(Reason.PROFILE_KEY_MISSING, f"{self.app}.env has no {key}: set it",
                                  key=key, source=f"{self.app}.env")
        return value


def _violation(field: str, value: str, limit: str, reason: str) -> Violation:
    return Violation(field, value, limit, reason)


def refuse(message: str, *violations: Violation, **metadata: Any) -> BusinessError:
    """A request refused on validation."""
    return BusinessError.make(Reason.REQUEST_INVALID, message, metadata=metadata, violations=violations)


class OcirAdapter:
    """The registry port over OCIR. Call `ensure_credentials` first: it binds the adapter
    to a component, whose credentials every other operation then uses."""

    def __init__(self, config: OcirConfig, log: RunLog | None = None, **gateway_options: Any):
        self.config = config
        self.log = log or RunLog()
        self._options = gateway_options
        self._gw: Gateway | None = None

    # ------------------------------------------------------------ plumbing

    @contextlib.contextmanager
    def _operation(self, name: str, **context: Any) -> Iterator[dict[str, Any]]:
        """Add the operation's context to an error from below, keeping its type."""
        ctx: dict[str, Any] = {"operation": name, **context}
        try:
            yield ctx
        except ProgrammeError as exc:
            raise exc.with_context(**{k: v for k, v in ctx.items() if k not in exc.result.metadata}) from exc

    def _bound(self) -> Gateway:
        if self._gw is None:
            raise UnexpectedError.make(Reason.REGISTRY_NOT_BOUND,
                                       "a registry operation ran before ensure_credentials: raise it as an issue")
        return self._gw

    @staticmethod
    def _unexpected(message: str, **metadata: Any) -> UnexpectedError:
        return UnexpectedError.make(Reason.REGISTRY_REPLY_INVALID,
                                    f"{message}: this was not expected, raise it as an issue", metadata=metadata)

    @staticmethod
    def _check_image(name: str) -> str:
        if not _IMAGE_NAME.fullmatch(name) or len(name) > settings.TAG_MAX_LENGTH - settings.TAG_PREFIX_LENGTH:
            raise refuse(f"image name {name!r} cannot be part of a tag",
                         _violation("image", name, "letters, digits, '_', '.' and '-', and short enough for a tag",
                                    "NOT_AN_IMAGE_NAME"))
        return name

    @staticmethod
    def _check_kind(repository: Repository, kind: RepositoryKind) -> None:
        if repository.kind is not kind:
            raise refuse(f"this operation needs the {kind.value} repository",
                         _violation("repository", repository.kind.value, kind.value, "WRONG_REPOSITORY"))

    @staticmethod
    def _check_commit(commit: str) -> str:
        try:
            return check_commit(commit)
        except FormError as exc:
            raise refuse(str(exc), exc.violation) from exc

    # ------------------------------------------------------- the operations

    def ensure_credentials(self, component: Component) -> None:
        """Bind to `component` and put its credentials in place: its registry login, and
        for a component holding an Artifacts API credential, that the key or principal is
        there. An `oci-*` login runs on each call."""
        with self._operation("ensure credentials", component=component.kind.value):
            if component.kind is ComponentKind.DEPLOYER:
                raise UnexpectedError.make(Reason.REQUEST_INVALID,
                                           "a deployer pulls with docker, outside the registry port: "
                                           "raise it as an issue")
            artifacts = None
            for credential in component.credentials:
                if credential.api is Api.ARTIFACTS:
                    artifacts = ("instance-principal" if credential.form is CredentialForm.INSTANCE_PRINCIPAL
                                 else "api-key")
            authfile = self.config.authfile(component.kind)
            gw = calls.gateway(component.kind.value, self.config.registry, self.log, authfile, artifacts,
                               self.config.oci_config_file, **self._options)
            user = token_cmd = None
            if component.login is not CredentialKind.DOCKER_CONFIG:
                user = self.config.need(self.config.user, settings.ENV_REGISTRY_USER)
                token_cmd = self.config.need(self.config.token_cmd, settings.ENV_TOKEN_CMD)
            calls.log_in(gw, component.login, user, token_cmd)
            calls.secure_authfile(authfile)
            if artifacts is not None:
                calls.check_removal_credential(gw)
            self._gw = gw

    def find_image(self, repository: Repository, what: BuildImage | ReleaseImage | Digest) -> Image | None:
        with self._operation("find image") as ctx:
            name, tag, digest = "", None, None
            if isinstance(what, Digest):
                digest = what
            elif isinstance(what, BuildImage):
                name = self._check_image(what.name)
                tag = candidate_tag(self._check_commit(what.commit), name)
            elif isinstance(what, ReleaseImage):
                self._check_kind(repository, RepositoryKind.RELEASES)
                name = self._check_image(what.name)
                tag = release_tag(what.version, name)
            else:
                raise refuse("find an image by a digest, a build's image or a release's image")
            ctx["image"] = name
            gw = self._bound()
            manifest = calls.inspect_manifest(gw, repository.name, tag=tag, digest=digest)
            if manifest is None:
                return None
            revision, created = calls.inspect_labels(gw, repository.name, manifest)
            return Image(name, manifest.digest, revision, created)

    def list_versions(self, repository: Repository) -> tuple[str, ...] | tuple[Version, ...]:
        with self._operation("list versions"):
            tags = calls.list_tags(self._bound(), repository.name)
            if repository.kind is RepositoryKind.CANDIDATES:
                return tuple(sorted({m.group(1) for t in tags if (m := _CANDIDATE_TAG.fullmatch(t))}))
            return tuple(sorted({Version.parse(m.group(1)) for t in tags if (m := _RELEASE_TAG.fullmatch(t))}))

    def store_build(self, repository: Repository, commit: str, layouts: Mapping[str, Path]) -> Build:
        with self._operation("store build", commit=commit) as ctx:
            self._check_kind(repository, RepositoryKind.CANDIDATES)
            self._check_commit(commit)
            if not layouts:
                raise refuse("a build has no images", _violation("images", "", "at least one", "NO_IMAGES"))
            expected: dict[str, Digest] = {}
            for name, layout in layouts.items():
                self._check_image(name)
                try:
                    expected[name] = calls.layout_digest(Path(layout))
                except OSError as exc:
                    raise refuse(f"the build wrote no layout for image {name}",
                                 _violation("layout", str(layout), "an OCI image layout", "NO_LAYOUT"),
                                 image=name) from exc
            gw = self._bound()
            stored: dict[str, Digest] = {}
            for name, layout in layouts.items():
                ctx["image"], ctx["step"] = name, "push"
                tag = candidate_tag(commit, name)
                calls.push_layout(gw, Path(layout), repository.name, tag)
                ctx["step"] = "inspect"
                manifest = calls.inspect_manifest(gw, repository.name, tag=tag)
                if manifest is None:
                    raise self._unexpected("an image just pushed is not in the registry", image=name)
                if manifest.digest != expected[name]:
                    raise UnexpectedError.make(
                        Reason.REGISTRY_DIGEST_CHANGED,
                        "the registry stores an image under a digest other than its layout's: "
                        "this was not expected, raise it as an issue", metadata={"image": name})
                stored[name] = manifest.digest
            return Build(commit, stored)

    def read_record(self, repository: Repository, version: Version) -> ReleaseRecord | None:
        with self._operation("read record", version=str(version)):
            self._check_kind(repository, RepositoryKind.RELEASES)
            record = calls.pull_record(self._bound(), repository.name, record_tag(version))
            if record is not None and record.version != version:
                raise self._unexpected("the record image holds another version's record")
            return record

    def promote(self, candidates: Repository, releases: Repository, build: Build,
                version: Version | None, record: ReleaseRecord | None) -> Promoted:
        with self._operation("promote", commit=build.commit) as ctx:
            self._check_kind(candidates, RepositoryKind.CANDIDATES)
            self._check_kind(releases, RepositoryKind.RELEASES)
            if (version is None) != (record is None):
                raise refuse("a promotion has a version and a record, or neither (--unrecorded)",
                             _violation("record", "" if record is None else "given", "given with the version, or neither",
                                        "VERSION_AND_RECORD_TOGETHER"))
            if not build.images:
                raise refuse("a build has no images", _violation("images", "", "at least one", "NO_IMAGES"))
            for name in build.images:
                self._check_image(name)
                if version is not None and name == RECORD:
                    raise refuse("an image cannot be named record: that tag is the release's record",
                                 _violation("image", name, "not 'record'", "RESERVED_NAME"))
            if record is not None and (record.version != version or record.commit != build.commit
                                       or dict(record.images) != dict(build.images)):
                raise refuse("the record is not the build's and version's",
                             _violation("record", str(record.version), "the version, commit and digests promoted",
                                        "RECORD_DISAGREES"))
            gw = self._bound()
            tags = {name: release_tag(version, name) if version is not None else candidate_tag(build.commit, name)
                    for name in build.images}
            wanted = {tags[name]: digest for name, digest in build.images.items()}
            if record is not None and version is not None:
                wanted[record_tag(version)] = calls.record_digest(record)

            # Before any write: the sources are there, and no target holds other contents.
            held: set[str] = set()
            for name, digest in build.images.items():
                ctx["image"], ctx["step"] = name, "check source"
                if calls.inspect_manifest(gw, candidates.name, digest=digest) is None:
                    raise BusinessError.make(Reason.IMAGE_NOT_FOUND,
                                             f"image {name} is not in candidates at the digest named: build it first",
                                             metadata={"digest": str(digest)})
            for tag, digest in wanted.items():
                ctx["image"], ctx["step"] = tag, "check target"
                if self._holds_same(gw, releases, tag, digest):
                    held.add(tag)

            # Every image is written first and the record last, so a failure part way leaves
            # no record, and a rerun writes only what is missing.
            written: list[str] = []
            for name, digest in build.images.items():
                if tags[name] in held:
                    continue
                ctx["image"], ctx["step"] = name, "copy"
                self._holds_same(gw, releases, tags[name], digest)      # the target, as it is written
                calls.copy_image(gw, candidates.name, digest, releases.name, tags[name])
                written.append(tags[name])
            if record is not None and version is not None and record_tag(version) not in held:
                ctx["image"], ctx["step"] = RECORD, "push"
                self._holds_same(gw, releases, record_tag(version), wanted[record_tag(version)])
                calls.push_record(gw, record, releases.name, record_tag(version))
                written.append(record_tag(version))
            return Promoted(dict(build.images), record, tuple(written),
                            tuple(tag for tag in wanted if tag in held))

    @staticmethod
    def _holds_same(gw: Gateway, repository: Repository, tag: str, digest: Digest) -> bool:
        """Whether releases already holds `digest` under this tag (a no-op to write); another
        digest under it is refused, since a release is never overwritten."""
        found = calls.inspect_manifest(gw, repository.name, tag=tag)
        if found is None:
            return False
        if found.digest == digest:
            return True
        raise BusinessError.make(
            Reason.NO_OVERWRITE,
            f"releases already holds {tag} with other contents, and a release is never overwritten: "
            f"use another version",
            metadata={"tag": tag, "held": str(found.digest), "wanted": str(digest)},
            violations=(_violation("tag", tag, "a tag releases does not hold, or holds with the same digest",
                                   "WOULD_OVERWRITE"),))

    def remove_candidate(self, repository: Repository, build: Build, image: str,
                         keep: Collection[Digest], removing: Collection[str]) -> Removal:
        with self._operation("remove candidate", image=image) as ctx:
            self._check_kind(repository, RepositoryKind.CANDIDATES)
            self._check_image(image)
            if image not in build.images:
                raise refuse(f"the build has no image {image}",
                             _violation("image", image, "an image of the build", "NOT_IN_BUILD"))
            digest = build.images[image]
            if digest in set(keep):
                raise BusinessError.make(
                    Reason.KEEP_LIST, f"image {image} is in the keep list: it is not removed",
                    metadata={"digest": str(digest)},
                    violations=(_violation("image", image, "not in the keep list", "KEEP_LIST"),))
            gw = self._bound()
            compartment = self.config.need(self.config.compartment, settings.ENV_COMPARTMENT)
            if gw.artifacts_auth is None:
                raise TechnicalError.make(
                    Reason.REMOVAL_CREDENTIAL_MISSING,
                    f"the {gw.component} holds no removal credential: configure its API key or instance principal")
            ctx["step"] = "check tag"
            held = calls.inspect_manifest(gw, repository.name, tag=candidate_tag(build.commit, image))
            if held is None:
                return Removal.ALREADY_GONE
            if held.digest != digest:
                return Removal.TAG_MOVED
            ctx["step"] = "find"
            tag = candidate_tag(build.commit, image)
            target = calls.find_image(gw, compartment, repository.name, digest, tag)
            if target is None:
                raise ProfileError.at(
                    Reason.PROFILE_KEY_MALFORMED,
                    f"image {image} was not found in the compartment {settings.ENV_COMPARTMENT} names: "
                    f"check that setting", key=settings.ENV_COMPARTMENT, source=f"{self.config.app}.env")
            others = sorted(set(target.tags) - set(removing))
            if others:      # a digest shared with a tag this prune keeps: deleting it would delete that tag
                self.log.event("remove-shared", image=image, other_tags=others)
                return Removal.SHARED
            ctx["step"] = "delete"
            calls.delete_found(gw, target, compartment, repository.name, digest)
            return Removal.REMOVED
