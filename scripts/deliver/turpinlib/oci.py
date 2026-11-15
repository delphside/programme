"""What the OCI image format fixes, read the same way wherever a manifest or a layout is
read: the registry adapter's translators (what a registry holds) and `layout.py` (what a
`build` hook wrote). Pure: nothing here runs a tool or reads a file.
"""

from __future__ import annotations

from typing import Any, Mapping

REVISION = "org.opencontainers.image.revision"
VERSION = "org.opencontainers.image.version"
CREATED = "org.opencontainers.image.created"

_ATTESTATION_ANNOTATION = "vnd.docker.reference.type"
_ATTESTATION = "attestation-manifest"


def is_attestation(entry: Mapping[str, Any]) -> bool:
    """Whether an index entry is an attestation manifest, which carries no labels: marked by
    its annotation, or by the platform `unknown` that buildx gives it."""
    notes = entry.get("annotations") if isinstance(entry.get("annotations"), dict) else {}
    platform = entry.get("platform") if isinstance(entry.get("platform"), dict) else {}
    return notes.get(_ATTESTATION_ANNOTATION) == _ATTESTATION or platform.get("architecture") == "unknown"


def first_entry(index: Any) -> dict[str, Any] | None:
    """The image a layout holds: the first entry of its `index.json`, or none if it lists none."""
    entries = index.get("manifests") if isinstance(index, dict) else None
    if not isinstance(entries, list) or not entries or not isinstance(entries[0], dict):
        return None
    return entries[0]
