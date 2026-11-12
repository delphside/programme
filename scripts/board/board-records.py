#!/usr/bin/env python3
"""board-records.py — where the programme's files are, for shell scripts.

    programme/scripts/board/board-records.py live       # the live checkout, for records
    programme/scripts/board/board-records.py generic    # the pinned submodule
    programme/scripts/board/board-records.py change-documents  # this application's change documents, in the live checkout
    programme/scripts/board/board-records.py check      # one line if the live checkout needs attention
    programme/scripts/board/board-records.py pin        # one line if the pin is behind the programme's origin/main

One definition of the default and the override (`records.py`), asked rather
than repeated in each shell script. A missing live checkout prints the path
tried and exits non-zero.

`check` is for the start of a session: it prints one line naming the path when
the live checkout is missing, not a git checkout, behind the local `origin/main`
(whatever branch it is on), or cannot be judged for want of that ref, and nothing when all is well. It never changes the checkout and
always exits 0.

`pin` is for the same moment: one fetch of the pinned submodule's `origin/main`
(five seconds at most) and one line when it lacks a commit that touches anything
outside `records/` and `applications/`, and nothing otherwise, on a `release/*`
branch or at a release tag, and in the programme itself (`pin.py`). It never
moves the pin and always exits 0.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from board import pin, records  # noqa: E402


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args == ["live"]:
        print(records.live())
    elif args == ["check"]:
        line = records.problem()
        if line:
            print(line)
    elif args == ["pin"]:
        line = pin.warning()
        if line:
            print(line)
    elif args == ["generic"]:
        print(records.generic())
    elif args == ["change-documents"]:
        print(records.change_documents())
    else:
        print(__doc__, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
