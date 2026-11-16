#!/usr/bin/env python3
"""board-vocabulary.py — which module reads each GitHub field and option name.

    programme/scripts/board/board-vocabulary.py             # a Markdown table, then a Mermaid flowchart
    programme/scripts/board/board-vocabulary.py --table     # the table only
    programme/scripts/board/board-vocabulary.py --mermaid   # the flowchart only
    programme/scripts/board/board-vocabulary.py --write FILE   # replace the table in FILE's generated block
    programme/scripts/board/board-vocabulary.py --check FILE   # exit 1 when that block is stale

The block in FILE lies between the line `dataflow.BEGIN` and the line
`dataflow.END`. --check exits 0 when it is current, 1 when stale, and 2 when it
could not judge: a usage error, an unreadable file, or no block or more than one.

Reads the board's own source with `ast` and `vocabulary.py`, and nothing from
GitHub: it is the data the data flow design (delphside/tile-lite-elite#383 R18)
is generated from. Whether each name still exists in GitHub is
`board-check.py --vocabulary`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from board import dataflow  # noqa: E402


def _file(path: Path, write: bool) -> int:
    try:
        with open(path, newline="") as f:
            text = f.read()
        new = dataflow.splice(text)
    except (OSError, dataflow.BlockError) as e:
        print(f"board-vocabulary: {path}: {e}", file=sys.stderr)
        return 2
    if write:
        if new != text:
            with open(path, "w", newline="") as f:
                f.write(new)
        return 0
    if new == text:
        return 0
    print(f"board-vocabulary: {path}: the generated table is stale; run "
          f"scripts/board/board-vocabulary.py --write {path}", file=sys.stderr)
    return 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--table", action="store_true", help="the Markdown table only")
    ap.add_argument("--mermaid", action="store_true", help="the Mermaid flowchart only")
    ap.add_argument("--write", metavar="FILE", help="replace the generated block in FILE")
    ap.add_argument("--check", metavar="FILE", help="exit 1 when FILE's generated block is stale")
    args = ap.parse_args(argv)
    if args.write and args.check:
        print("board-vocabulary: --write and --check are exclusive", file=sys.stderr)
        return 2
    if args.write or args.check:
        return _file(Path(args.write or args.check), write=bool(args.write))
    if args.table:
        print(dataflow.markdown())
    elif args.mermaid:
        print(dataflow.mermaid())
    else:
        print(dataflow.render(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
