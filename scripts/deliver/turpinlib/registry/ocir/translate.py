"""The translators (design §3 *Translators*): Oracle's data types, each to and
from the domain model, so no layer above the middle sees Oracle's formats.

Pure: nothing here runs a tool or reads a file. They are beside the middle layer,
and only `calls.py` uses them. An invalid reply raises an unexpected error here
(R49, C34); a reason-keyed absence is for `calls.py` to decide.
"""

from __future__ import annotations

import enum
import hashlib
import io
import json
import re
import tarfile
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from ...model import (Digest, FormError, ProgrammeError, Reason, ReleaseRecord, TechnicalError,
                      UnexpectedError)
from .reasons import NOT_AUTHORIZED_OR_NOT_FOUND, OracleReason

_REVISION_LABEL = "org.opencontainers.image.revision"
_CREATED_LABEL = "org.opencontainers.image.created"
_ATTESTATION_ANNOTATION = "vnd.docker.reference.type"
_ATTESTATION = "attestation-manifest"

_MANIFEST_TYPES = frozenset({"application/vnd.oci.image.manifest.v1+json",
                             "application/vnd.docker.distribution.manifest.v2+json"})
_INDEX_TYPES = frozenset({"application/vnd.oci.image.index.v1+json",
                          "application/vnd.docker.distribution.manifest.list.v2+json"})
_OCI_MANIFEST = "application/vnd.oci.image.manifest.v1+json"
_OCI_CONFIG = "application/vnd.oci.image.config.v1+json"
_OCI_LAYER = "application/vnd.oci.image.layer.v1.tar"


def invalid(message: str, **metadata: Any) -> UnexpectedError:
    """An Oracle reply that arrived whole but is not valid: unexpected, to raise as
    an issue (design §3 *Validation and errors*)."""
    return UnexpectedError.make(Reason.REGISTRY_REPLY_INVALID,
                                f"{message}: this was not expected, raise it as an issue",
                                metadata=metadata)


def _json(text: str, what: str) -> Any:
    try:
        return json.loads(text)
    except ValueError as exc:
        raise invalid(f"the registry's {what} is not JSON", what=what) from exc


# ------------------------------------------------------------------------ OCID

@dataclass(frozen=True)
class Ocid:
    """An Oracle resource identifier. It never reaches a log: `str` and `repr` hide
    it, and `value` is for the one call that needs it."""
    value: str = field(repr=False)
    kind: str

    def __str__(self) -> str:
        return "<ocid>"

    def __repr__(self) -> str:
        return "Ocid(<ocid>)"


def parse_ocid(text: object, kind: str = "containerimage") -> Ocid:
    """An OCID of the kind asked for. The region is not checked: a registry host names
    a region by one name and an OCID by another."""
    parts = text.split(".") if isinstance(text, str) else []
    if len(parts) < 5 or parts[0] != "ocid1" or not parts[-1] or not all(re.fullmatch(r"[A-Za-z0-9_-]*", p) for p in parts):
        raise invalid("the registry gave an identifier that is not an OCID")
    if parts[1] != kind:
        raise invalid("the registry gave an identifier of the wrong kind", wanted_kind=kind, kind=parts[1])
    return Ocid(text, parts[1])  # type: ignore[arg-type]


# ------------------------------------------------------------- image references

@dataclass(frozen=True)
class ImageRef:
    """`REGISTRY/NAMESPACE/REPO:TAG@sha256:...`, as its parts. `registry` holds the
    host and the namespace (`TURPIN_REGISTRY`)."""
    registry: str
    repository: str
    tag: str | None = None
    digest: Digest | None = None

    def __post_init__(self) -> None:
        if self.tag is None and self.digest is None:
            raise ValueError("an image reference names a tag or a digest")

    def text(self) -> str:
        tag = f":{self.tag}" if self.tag is not None else ""
        digest = f"@{self.digest}" if self.digest is not None else ""
        return f"{self.registry}/{self.repository}{tag}{digest}"

    def docker(self) -> str:
        """The form `skopeo` takes."""
        return "docker://" + self.text()


def parse_ref(text: str, registry: str) -> ImageRef:
    """The parts of a reference in `registry`, with or without `docker://`."""
    text = text.removeprefix("docker://")
    if not text.startswith(registry + "/"):
        raise invalid("a reference is not in the registry", reference_in="another registry")
    rest = text[len(registry) + 1:]
    digest = None
    if "@" in rest:
        rest, _, found = rest.partition("@")
        try:
            digest = Digest(found)
        except FormError as exc:
            raise exc.unexpected("an image reference") from exc
    tag = None
    head, _, last = rest.rpartition("/")
    if ":" in last:
        last, _, tag = last.partition(":")
    repository = f"{head}/{last}" if head else last
    if not repository or (tag is None and digest is None):
        raise invalid("a reference names no repository, tag or digest")
    return ImageRef(registry, repository, tag, digest)


# ------------------------------------------------------- manifests and indexes

@dataclass(frozen=True)
class Manifest:
    """A manifest or an index, by the digest that is the image digest. For an index,
    `platforms` are the platform manifests it lists, its attestation manifests left
    out (they carry no labels); for a manifest it is empty."""
    digest: Digest
    index: bool
    platforms: tuple[Digest, ...] = ()
    attestations: int = 0


def _digest_of_reply(raw: bytes, asked: Digest | None) -> Digest:
    """The sha256 of the reply exactly as `skopeo inspect --raw` wrote it, which is the
    image digest; a digest asked for must be it."""
    found = Digest("sha256:" + hashlib.sha256(raw).hexdigest())
    if asked is not None and asked != found:
        raise invalid("the registry gave a manifest whose digest is not the one asked for",
                      asked=str(asked))
    return found


def parse_manifest(raw: bytes | str, asked: Digest | None = None) -> Manifest:
    """A manifest or an index from `skopeo inspect --raw`. The media type must be one
    of the four known; a missing field, or a digest other than `asked`, is invalid."""
    raw = raw.encode() if isinstance(raw, str) else raw
    digest = _digest_of_reply(raw, asked)
    data = _json(raw.decode(errors="replace"), "manifest")
    if not isinstance(data, dict):
        raise invalid("the registry's manifest is not an object")
    media = data.get("mediaType")
    if media is None:
        media = ("application/vnd.oci.image.index.v1+json" if "manifests" in data
                 else _OCI_MANIFEST if "layers" in data else None)
    if media in _MANIFEST_TYPES:
        config, layers = data.get("config"), data.get("layers")
        if not isinstance(config, dict) or not isinstance(config.get("digest"), str) or not isinstance(layers, list):
            raise invalid("the registry's manifest lacks its config or layers")
        return Manifest(digest, False)
    if media in _INDEX_TYPES:
        listed = data.get("manifests")
        if not isinstance(listed, list):
            raise invalid("the registry's index lists no manifests")
        platforms: list[Digest] = []
        attestations = 0
        for entry in listed:
            if not isinstance(entry, dict) or not isinstance(entry.get("digest"), str):
                raise invalid("the registry's index has an entry with no digest")
            try:
                found = Digest(entry["digest"])
            except FormError as exc:
                raise exc.unexpected("an index entry") from exc
            platform = entry.get("platform") if isinstance(entry.get("platform"), dict) else {}
            notes = entry.get("annotations") if isinstance(entry.get("annotations"), dict) else {}
            if notes.get(_ATTESTATION_ANNOTATION) == _ATTESTATION or platform.get("architecture") == "unknown":
                attestations += 1
            else:
                platforms.append(found)
        return Manifest(digest, True, tuple(platforms), attestations)
    raise invalid("the registry's manifest has an unknown media type", media_type=str(media))


def parse_labels(raw: str) -> tuple[str, str]:
    """The `revision` and `created` labels of an image's configuration (`skopeo inspect
    --config`); an image without one has it as ''."""
    data = _json(raw, "image configuration")
    if not isinstance(data, dict):
        raise invalid("the registry's image configuration is not an object")
    section = data.get("config") or {}
    labels = section.get("Labels") if isinstance(section, dict) else None
    if labels is None:
        labels = {}
    if not isinstance(labels, dict) or not all(isinstance(v, str) for v in labels.values()):
        raise invalid("the registry's image labels are not strings")
    return labels.get(_REVISION_LABEL, ""), labels.get(_CREATED_LABEL, "")


def parse_tags(raw: str) -> list[str]:
    """The tags of `skopeo list-tags`."""
    data = _json(raw, "tag list")
    tags = data.get("Tags") if isinstance(data, dict) else None
    if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
        raise invalid("the registry's tag list has no tags")
    return tags


def parse_image_items(items: list[Any], repository: str, digest: Digest) -> list[Ocid]:
    """The OCIDs of the images an Artifacts listing gave for `repository` and `digest`.
    The listing's items are summaries (`id`, `digest`, `repository-name`, `version` the
    most recent tag only); an item for another digest or repository, or with no OCID,
    is invalid."""
    found: list[Ocid] = []
    for item in items:
        if not isinstance(item, dict):
            raise invalid("the registry listed an image that is not an object")
        if item.get("digest") != str(digest) or item.get("repository-name") != repository:
            raise invalid("the registry listed an image other than the one asked for")
        found.append(parse_ocid(item.get("id"), "containerimage"))
    return found


def parse_image_tags(data: Any, repository: str, digest: Digest, own_tag: str) -> tuple[str, ...]:
    """Every tag of the image `get` gave (its `versions`). The image must be the one asked
    for and carry `own_tag`; with no list of versions, or without the image's own tag, the
    reply is invalid, so nothing is deleted on it."""
    if not isinstance(data, dict) or data.get("digest") != str(digest) or data.get("repository-name") != repository:
        raise invalid("the registry gave an image other than the one asked for")
    versions = data.get("versions")
    if not isinstance(versions, list) or not all(
            isinstance(v, dict) and isinstance(v.get("version"), str) for v in versions):
        raise invalid("the registry gave an image with no list of tags")
    tags = tuple(v["version"] for v in versions)
    if own_tag not in tags:
        raise invalid("the registry's image does not carry the tag it was found by")
    return tags


# ---------------------------------------------------------- OCI image layouts

def layout_digest(index_json: str) -> Digest:
    """The digest of the image a layout holds: its `index.json`'s first entry, the
    index or the manifest the hook wrote (design §3 *Operations*, store a build)."""
    data = _json(index_json, "layout index")
    entries = data.get("manifests") if isinstance(data, dict) else None
    if not isinstance(entries, list) or not entries or not isinstance(entries[0], dict):
        raise invalid("a layout's index.json lists no image")
    try:
        return Digest(str(entries[0].get("digest")))
    except FormError as exc:
        raise exc.unexpected("a layout's index.json") from exc


@dataclass(frozen=True)
class RecordImage:
    """The record as a one-layer image: the files of its OCI layout, and the digest the
    registry will hold. Made reproducibly, so the same record is the same digest."""
    files: Mapping[str, bytes]
    digest: Digest


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def record_image(record: ReleaseRecord) -> RecordImage:
    """`VERSION-record`: a scratch image with one layer holding `record.json`."""
    body = json.dumps(record.to_json(), sort_keys=True, separators=(",", ":")).encode()
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        info = tarfile.TarInfo("record.json")
        info.size, info.mtime, info.mode = len(body), 0, 0o644
        tar.addfile(info, io.BytesIO(body))
    layer = buffer.getvalue()
    config = json.dumps({"architecture": "amd64", "os": "linux", "config": {},
                         "rootfs": {"type": "layers", "diff_ids": ["sha256:" + _sha(layer)]}},
                        sort_keys=True, separators=(",", ":")).encode()
    manifest = json.dumps({
        "schemaVersion": 2, "mediaType": _OCI_MANIFEST,
        "config": {"mediaType": _OCI_CONFIG, "digest": "sha256:" + _sha(config), "size": len(config)},
        "layers": [{"mediaType": _OCI_LAYER, "digest": "sha256:" + _sha(layer), "size": len(layer)}]},
        sort_keys=True, separators=(",", ":")).encode()
    index = json.dumps({"schemaVersion": 2, "manifests": [{
        "mediaType": _OCI_MANIFEST, "digest": "sha256:" + _sha(manifest), "size": len(manifest)}]},
        sort_keys=True).encode()
    files = {"oci-layout": b'{"imageLayoutVersion":"1.0.0"}', "index.json": index,
             f"blobs/sha256/{_sha(config)}": config, f"blobs/sha256/{_sha(layer)}": layer,
             f"blobs/sha256/{_sha(manifest)}": manifest}
    return RecordImage(files, Digest("sha256:" + _sha(manifest)))


def record_from_layout(read: Callable[[str], bytes]) -> ReleaseRecord:
    """The record in a layout `skopeo` pulled, `read` giving a file's bytes by its path
    in the layout. Anything but a one-layer image holding a valid `record.json` is
    invalid: this tool wrote it."""
    try:
        index = json.loads(read("index.json"))
        manifest_hex = index["manifests"][0]["digest"].removeprefix("sha256:")
        manifest = json.loads(read(f"blobs/sha256/{manifest_hex}"))
        layer_hex = manifest["layers"][0]["digest"].removeprefix("sha256:")
        with tarfile.open(fileobj=io.BytesIO(read(f"blobs/sha256/{layer_hex}"))) as tar:
            member = tar.extractfile("record.json")
            if member is None:
                raise KeyError("record.json")
            data = json.loads(member.read())
        return ReleaseRecord.from_json(data)
    except FormError as exc:
        raise exc.unexpected("a release record") from exc
    except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError, tarfile.TarError) as exc:
        raise invalid("the record image is not a one-layer image holding record.json") from exc


# ---------------------------------------------------------------- Oracle errors

class Verdict(enum.Enum):
    """What an API error means to Turpin (design §3 *Validation and errors*, step 2)."""
    ABSENT = "absent"
    REFUSED = "refused"
    NOT_AUTHORIZED_OR_NOT_FOUND = "not-authorized-or-not-found"
    BLIP = "blip"
    TOOL_MISSING = "tool-missing"
    CREDENTIAL_MISSING = "credential-missing"
    UNEXPECTED = "unexpected"


_ABSENT_REASONS = {OracleReason.MANIFEST_UNKNOWN.value, OracleReason.NAME_UNKNOWN.value}
_REFUSED_REASONS = {OracleReason.UNAUTHORIZED.value, OracleReason.DENIED.value}


def classify(err: ProgrammeError) -> Verdict:
    """The verdict on an error the bottom layer raised, from its result alone."""
    result = err.result
    if isinstance(err, UnexpectedError):
        return Verdict.UNEXPECTED
    if result.blip:
        return Verdict.BLIP
    status = result.metadata.get("http_status")
    if result.reason in _ABSENT_REASONS:
        return Verdict.ABSENT
    if result.reason == NOT_AUTHORIZED_OR_NOT_FOUND:
        return Verdict.NOT_AUTHORIZED_OR_NOT_FOUND
    if result.reason in _REFUSED_REASONS or status in (401, 403):
        return Verdict.REFUSED
    if result.reason == OracleReason.TOOL_MISSING.value:
        return Verdict.TOOL_MISSING
    if result.reason == OracleReason.AUTH_CONFIG_MISSING.value:
        return Verdict.CREDENTIAL_MISSING
    return Verdict.UNEXPECTED


def to_turpin(err: ProgrammeError, component: str, call: str) -> ProgrammeError:
    """The error of domain `turpin` that answers an API error: its type and next step,
    no tool text, address or OCID in its message, and the API error as its `cause`.
    Raise it `from err`. An absence is for the caller to decide first."""
    verdict = classify(err)
    tool = str(err.result.metadata.get("tool", "the registry tool"))
    meta = {"call": call, "component": component}
    if verdict is Verdict.UNEXPECTED and isinstance(err, UnexpectedError):
        return UnexpectedError.wrap(err, Reason.REGISTRY_OUTPUT_INVALID,
                                    f"{tool} gave output not in its format: this was not expected, "
                                    f"raise it as an issue", metadata=meta)
    if verdict is Verdict.BLIP:
        return TechnicalError.wrap(err, Reason.REGISTRY_UNREACHABLE,
                                   "the registry did not answer in time or is busy: try again later",
                                   metadata=meta, blip=True)
    if verdict is Verdict.REFUSED:
        return TechnicalError.wrap(err, Reason.REGISTRY_REFUSED,
                                   f"the registry refused the {component}'s login: run `turpin login {component}`, "
                                   f"or check its policy", metadata=meta)
    if verdict is Verdict.NOT_AUTHORIZED_OR_NOT_FOUND:
        return TechnicalError.wrap(err, Reason.REGISTRY_REFUSED,
                                   f"the registry says the {component} is not authorised or the thing is not "
                                   f"there: check the {component}'s policy and the compartment setting", metadata=meta)
    if verdict is Verdict.TOOL_MISSING:
        return TechnicalError.wrap(err, Reason.REGISTRY_TOOL_MISSING,
                                   f"{tool} is not installed on this machine: install it", metadata=meta)
    if verdict is Verdict.CREDENTIAL_MISSING:
        return TechnicalError.wrap(err, Reason.REMOVAL_CREDENTIAL_MISSING,
                                   f"the {component} has no API key configuration or instance principal for "
                                   f"{tool}: configure one", metadata=meta)
    return UnexpectedError.wrap(err, Reason.REGISTRY_CALL_UNEXPECTED,
                                f"the registry call {call} failed in a way that was not expected: "
                                f"raise it as an issue", metadata=meta)
