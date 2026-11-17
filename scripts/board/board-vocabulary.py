#!/usr/bin/env python3
"""board-vocabulary.py — which module reads each GitHub field and option name.

    programme/scripts/board/board-vocabulary.py             # a Markdown table, then a Mermaid flowchart
    programme/scripts/board/board-vocabulary.py --table     # the table only
    programme/scripts/board/board-vocabulary.py --mermaid   # the flowchart only
    programme/scripts/board/board-vocabulary.py --write FILE   # replace the table in FILE's generated block
    programme/scripts/board/board-vocabulary.py --check FILE   # exit 1 when that block is stale

The block in FILE lies between the line `dataflow.BEGIN` and the line
`dataflow.END`. The four options are exclusive. --check exits 0 when the block
is current and 1 when it is stale. Exit 2 is a run that could not complete: a
usage error, a file that cannot be read or written, or a file with no block or
more than one. --write exits 0 when the block is as it should be.

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
            try:
                with open(path, "w", newline="") as f:
                    f.write(new)
            except OSError as e:
                print(f"board-vocabulary: {path}: cannot write: {e}", file=sys.stderr)
                return 2
        return 0
    if new == text:
        return 0
    print(f"board-vocabulary: {path}: the generated table is stale; run "
          f"scripts/board/board-vocabulary.py --write {path}", file=sys.stderr)
    return 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    one = ap.add_mutually_exclusive_group()
    one.add_argument("--table", action="store_true", help="the Markdown table only")
    one.add_argument("--mermaid", action="store_true", help="the Mermaid flowchart only")
    one.add_argument("--write", metavar="FILE", help="replace the generated block in FILE")
    one.add_argument("--check", metavar="FILE", help="exit 1 when FILE's generated block is stale")
    args = ap.parse_args(argv)
    if args.write is not None or args.check is not None:
        write = args.write is not None
        return _file(Path(args.write if write else args.check), write=write)
    if args.table:
        print(dataflow.markdown())
    elif args.mermaid:
        print(dataflow.mermaid())
    else:
        print(dataflow.render(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
