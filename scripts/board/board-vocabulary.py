#!/usr/bin/env python3
"""board-vocabulary.py — which module reads each GitHub field and option name.

    programme/scripts/board/board-vocabulary.py             # a Markdown table, then a Mermaid flowchart
    programme/scripts/board/board-vocabulary.py --table     # the table only
    programme/scripts/board/board-vocabulary.py --mermaid   # the flowchart only

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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--table", action="store_true", help="the Markdown table only")
    ap.add_argument("--mermaid", action="store_true", help="the Mermaid flowchart only")
    args = ap.parse_args(argv)
    if args.table:
        print(dataflow.markdown())
    elif args.mermaid:
        print(dataflow.mermaid())
    else:
        print(dataflow.render(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
