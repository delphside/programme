"""The tooling's tests outside the model's own, run by unittest (docs/1.1):

    python3 -m unittest discover -s scripts -t scripts

They share the model's harness, `board.tests.cases` and `board.tests.cli`, so
the scripts' folder is put on the path here, as each `board-*.py` command does
for itself.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from board.tests.profiles import use_fakes  # noqa: E402

# Every test reads the fake profiles, never a real application's (#485).
use_fakes()
