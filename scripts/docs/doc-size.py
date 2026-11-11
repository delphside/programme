#!/usr/bin/env python3
"""Report the markdown documents over the size limit. The programme's docs/1.5.

    doc-size.py               an application's documents, from its repository
    doc-size.py --programme   the programme repository's own

Every markdown file git tracks, less what `board/size.py`'s `exempt` leaves
out (logs, reports, fixtures and the design map), the `programme/`
submodule's (checked in the programme repository, as its own) and the
generated documents an application names in its technical profile
(`documents.generated`). The limit and the report are `board/size.py`'s, which
`board-check.py` uses for issue bodies too.

A measure, not a gate: always exits 0, and the weekly `document-review`
proposes a restructure for each document listed (docs/1.4).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from board import profile  # noqa: E402
from board.size import exempt, oversized, render  # noqa: E402


def documents(root: Path, generated: set[str]) -> list[str]:
    """Tracked markdown under `root`, by path relative to it."""
    out = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--", "*.md"],
                         capture_output=True, text=True, check=True).stdout
    return sorted(p for p in out.split("\0")
                  if p and p not in generated and not exempt(p))


def main(argv: list[str]) -> int:
    if "--programme" in argv:
        root = Path(__file__).resolve().parents[2]
        generated: set[str] = set()
    else:
        root = profile.app_root()
        # An application with no `documents` table names no generated documents.
        spec = profile.technical(root)
        generated = (set(spec.strings("documents.generated"))
                     if "generated" in spec.data.get("documents", {}) else set())
    paths = documents(root, generated)
    found = oversized((p, (root / p).stat().st_size) for p in paths
                      if (root / p).is_file())
    print(render(found, f"documents (of {len(paths)})"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
