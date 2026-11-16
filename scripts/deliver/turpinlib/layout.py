"""Reading an OCI image layout the `build` hook wrote (design §8): the labels of each
platform image, so `build` checks them before any push.

A layout is a directory: `index.json` names the image (a manifest, or an index of one
manifest per platform and, where the build adds them, an attestation manifest per
platform), and `blobs/sha256/` holds the manifests, configurations and layers. An
attestation manifest carries no labels and is passed over.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import oci
from .model import BusinessError, Reason

REVISION, VERSION, CREATED = oci.REVISION, oci.VERSION, oci.CREATED


def _unusable(image: str, why: str) -> BusinessError:
    return BusinessError.make(Reason.BUILD_NO_LAYOUT,
                              f"the build wrote no usable layout for image {image}: {why}",
                              metadata={"image": image})


def _json(path: Path, image: str) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise _unusable(image, f"{path.name} cannot be read") from exc


def _blob(layout: Path, digest: Any, image: str) -> Any:
    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        raise _unusable(image, "a descriptor has no digest")
    return _json(layout / "blobs" / "sha256" / digest.removeprefix("sha256:"), image)


def platform_labels(layout: Path, image: str) -> list[tuple[str, dict[str, str]]]:
    """Each platform image's manifest digest and the labels in its configuration: one
    entry for an image with no index, one per platform for an index, its attestation
    manifests left out. An image with none is not usable."""
    index = _json(layout / "index.json", image)
    top = oci.first_entry(index)
    if top is None:
        raise _unusable(image, "index.json lists no image")
    document = _blob(layout, top.get("digest"), image)
    if isinstance(document, dict) and isinstance(document.get("manifests"), list):
        platforms = [e for e in document["manifests"] if isinstance(e, dict) and not oci.is_attestation(e)]
    else:
        platforms = [top]
    if not platforms:
        raise _unusable(image, "the index lists no platform image")
    found = []
    for entry in platforms:
        manifest = _blob(layout, entry.get("digest"), image)
        config_digest = (manifest.get("config") or {}).get("digest") if isinstance(manifest, dict) else None
        config = _blob(layout, config_digest, image)
        section = config.get("config") if isinstance(config, dict) else None
        labels = section.get("Labels") if isinstance(section, dict) else None
        if not isinstance(labels, dict):
            labels = {}
        found.append((str(entry.get("digest")), {k: str(v) for k, v in labels.items()}))
    return found
