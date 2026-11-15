"""The middle layer (design §3 *The registry adapter*): one thin function per Oracle
call, giving domain types built through the translators.

It meets Oracle's business errors: a manifest unknown is *absent* on a read and a
business error where the operation needed it; a delete answered
`NotAuthorizedOrNotFound` is a fundamental technical error naming the builder's
policy (C37); a reply that arrives whole but is invalid is unexpected. An error from
below is translated once, into domain `turpin` and raised `from` the API error, whose
result is its `cause` (design §3, steps 1 and 2). Its calls are well formed, since the
top layer has validated them. It calls the bottom layer through the module, so a test
can replace one function.
"""

from __future__ import annotations

import contextlib
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from ... import settings
from ...model import (BusinessError, CredentialKind, Digest, ProgrammeError, Reason, ReleaseRecord,
                      TechnicalError, UnexpectedError)
from ...runlog import RunLog
from . import api, translate
from .api import ApiError, Gateway
from .reasons import DOMAIN
from .translate import ImageRef, Manifest, Ocid, Verdict


@contextlib.contextmanager
def _translated(gw: Gateway, call: str) -> Iterator[None]:
    """Translate an error from the bottom layer; anything else passes."""
    try:
        yield
    except (ApiError, UnexpectedError) as exc:
        if exc.result.domain != DOMAIN:
            raise
        raise translate.to_turpin(exc, gw.component, call) from exc


def _absent(exc: ProgrammeError) -> bool:
    return translate.classify(exc) is Verdict.ABSENT


def _ref(gw: Gateway, repository: str, tag: str | None = None, digest: Digest | None = None) -> ImageRef:
    return ImageRef(gw.registry, repository, tag, digest)


def gateway(component: str, registry: str, log: RunLog, authfile: Path, artifacts_auth: str | None,
            oci_config_file: str | None, **options: Any) -> Gateway:
    """What the calls of one component are made with, its auth file made private."""
    api.secure_authfile(authfile)
    return Gateway(component, registry, log, authfile, artifacts_auth, oci_config_file, **options)


def secure_authfile(authfile: Path) -> None:
    """The auth file 0600 in a 0700 directory, after a login wrote it (R44)."""
    api.secure_authfile(authfile)


# ---------------------------------------------------------------------- log in

def log_in(gw: Gateway, kind: CredentialKind, user: str | None, token_cmd: str | None) -> None:
    """Put the component's registry login in its auth file. `docker-config` only checks
    that the file holds one (`turpin login COMPONENT` makes it); an `oci-*` kind runs the
    token command and logs in with the token, on each call (design §3 *Logins*)."""
    assert gw.authfile is not None
    with _translated(gw, "log in"):
        if kind is CredentialKind.DOCKER_CONFIG:
            if not api.authfile_logged_in(gw.authfile, gw.registry):
                raise TechnicalError.make(
                    Reason.REGISTRY_LOGIN_MISSING,
                    f"the {gw.component} has no registry login: run `turpin login {gw.component}`",
                    metadata={"component": gw.component, "call": "log in"})
            return
        assert user and token_cmd
        api.skopeo_login(gw, user, api.token_command(gw, token_cmd))


def make_login(gw: Gateway, user: str, token: str) -> None:
    """Make the component's login: `skopeo login --authfile`, the token on standard input
    only, the auth file then private (design §3 *Logins*)."""
    assert gw.authfile is not None
    with _translated(gw, "log in"):
        api.skopeo_login(gw, user, token)


def check_removal_credential(gw: Gateway) -> None:
    """The API key's configuration or the instance principal is there."""
    if not api.artifacts_auth_present(gw):
        raise TechnicalError.make(
            Reason.REMOVAL_CREDENTIAL_MISSING,
            f"the {gw.component}'s removal credential is not there: configure the API key "
            f"(~/.oci/config or {settings.ENV_OCI_CONFIG_FILE}), or install the oci tool for the "
            f"instance principal", metadata={"component": gw.component, "call": "log in"})


# ------------------------------------------------------------ the registry API

def inspect_manifest(gw: Gateway, repository: str, *, tag: str | None = None,
                     digest: Digest | None = None) -> Manifest | None:
    """The manifest or index a tag or digest names, or *absent*. A digest asked for
    must be the digest of the reply."""
    ref = _ref(gw, repository, tag, digest)
    with _translated(gw, "inspect manifest"):
        try:
            raw = api.inspect_raw(gw, ref.docker())
        except ApiError as exc:
            if _absent(exc):
                return None
            raise
        return translate.parse_manifest(raw, ref.digest)


def inspect_labels(gw: Gateway, repository: str, manifest: Manifest) -> tuple[str, str]:
    """The `revision` and `created` labels of an image, read from its first platform
    image where `manifest` is an index (an attestation manifest carries none)."""
    labelled = manifest.digest
    if manifest.index:
        if not manifest.platforms:
            raise translate.invalid("the registry's index lists no platform image")
        labelled = manifest.platforms[0]
    with _translated(gw, "inspect image"):
        return translate.parse_labels(api.inspect_config(gw, _ref(gw, repository, digest=labelled).docker()))


def list_tags(gw: Gateway, repository: str) -> list[str]:
    """Every tag of a repository; a repository not yet made has none."""
    with _translated(gw, "list tags"):
        try:
            raw = api.list_tags(gw, f"docker://{gw.registry}/{repository}")
        except ApiError as exc:
            if _absent(exc):
                return []
            raise
        return translate.parse_tags(raw)


def copy_image(gw: Gateway, source_repository: str, digest: Digest, repository: str, tag: str) -> None:
    """Copy every platform of the image `digest` names in one repository to a tag of
    another, digests preserved. A source that is not there is a business error, naming
    its digest."""
    with _translated(gw, "copy image"):
        try:
            api.copy(gw, _ref(gw, source_repository, digest=digest).docker(),
                     _ref(gw, repository, tag).docker())
        except ApiError as exc:
            if _absent(exc):
                raise BusinessError.wrap(exc, Reason.IMAGE_NOT_FOUND,
                                         "an image to copy is not in the source repository: build it first",
                                         metadata={"digest": str(digest)}) from exc
            raise


def layout_digest(layout: Path) -> Digest:
    """The digest of the image an OCI layout holds. A layout that cannot be read is an
    `OSError`; one that is not a layout is an unexpected error."""
    return translate.layout_digest((layout / "index.json").read_text())


def push_layout(gw: Gateway, layout: Path, repository: str, tag: str) -> None:
    """Push the image an OCI layout holds, every platform, digests preserved."""
    with _translated(gw, "push image"):
        api.copy(gw, f"oci:{layout}", _ref(gw, repository, tag).docker())


def record_digest(record: ReleaseRecord) -> Digest:
    """The digest `record` has as an image."""
    return translate.record_image(record).digest


def push_record(gw: Gateway, record: ReleaseRecord, repository: str, tag: str) -> Digest:
    """Push the record as a one-layer image, and give the digest it will have."""
    image = translate.record_image(record)
    with tempfile.TemporaryDirectory(prefix="turpin-record-") as folder:
        for name, data in image.files.items():
            path = Path(folder) / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        with _translated(gw, "push record"):
            api.copy(gw, f"oci:{folder}", _ref(gw, repository, tag).docker(), all_platforms=False)
    return image.digest


def pull_record(gw: Gateway, repository: str, tag: str) -> ReleaseRecord | None:
    """The record a `VERSION-record` image holds, or *absent*."""
    with tempfile.TemporaryDirectory(prefix="turpin-record-") as folder:
        with _translated(gw, "pull record"):
            try:
                api.copy(gw, _ref(gw, repository, tag).docker(), f"oci:{folder}", all_platforms=False)
            except ApiError as exc:
                if _absent(exc):
                    return None
                raise
        return translate.record_from_layout(lambda name: (Path(folder) / name).read_bytes())


# ---------------------------------------------------------- the Artifacts API

@dataclass(frozen=True)
class Target:
    """An image found for removal: every tag it carries, and its identifier, which only
    `delete_found` reads."""
    tags: tuple[str, ...]
    ocid: Ocid = field(repr=False)


def _list_ocids(gw: Gateway, compartment: str, repository_name: str, digest: Digest) -> list[Ocid]:
    with _translated(gw, "find image"):
        return translate.parse_image_items(api.list_images(gw, compartment, repository_name, str(digest)),
                                           repository_name, digest)


def find_image(gw: Gateway, compartment: str, repository_name: str, digest: Digest,
               own_tag: str) -> Target | None:
    """The one image in a repository with this digest, with all its tags, or none. The
    listing gives the OCID; the tags are on the image itself, so it is got too. Several
    images for one digest, or one without `own_tag`, is an invalid reply."""
    found = _list_ocids(gw, compartment, repository_name, digest)
    if not found:
        return None
    if len(found) > 1:
        raise translate.invalid("the registry lists several images for one digest")
    with _translated(gw, "get image"):
        tags = translate.parse_image_tags(api.get_image(gw, found[0].value), repository_name, digest, own_tag)
    return Target(tags, found[0])


def delete_found(gw: Gateway, target: Target, compartment: str, repository_name: str, digest: Digest) -> None:
    """Delete a found image. `NotAuthorizedOrNotFound` is a fundamental technical
    error naming the builder's policy, since the image was there when `prune` chose it
    and only this builder removes candidates; except after an attempt that timed out or
    got a 5xx, when the image is listed again by digest and finding nothing counts as
    removed (C37)."""
    with _translated(gw, "delete image"):
        try:
            api.delete_image(gw, target.ocid.value)
        except ApiError as exc:
            if translate.classify(exc) is not Verdict.NOT_AUTHORIZED_OR_NOT_FOUND:
                raise
            if exc.result.metadata.get("earlier_blip") and not _list_ocids(gw, compartment, repository_name, digest):
                return
            raise TechnicalError.wrap(
                exc, Reason.REMOVAL_NOT_AUTHORIZED,
                f"the registry would not delete the image: check that the {gw.component}'s policy lets it "
                f"manage repos on candidates", metadata={"call": "delete image", "component": gw.component}) from exc
