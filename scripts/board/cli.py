"""What the board's commands share as commands: the exit statuses they return
for a usage error, a business error and a blip (docs/1.10), the form of a
pull request's reference, and an argument parser that exits with the usage one.
"""

from __future__ import annotations

import argparse
import re
import sys

EX_USAGE = 64
EX_DATAERR = 65
EX_TEMPFAIL = 75

REPO = r"[\w.-]+/[\w.-]+"
# `OWNER/REPO#N`: groups owner, name, number.
PR_REF = re.compile(r"([\w.-]+)/([\w.-]+)#(\d+)")


class Parser(argparse.ArgumentParser):
    """An `ArgumentParser` whose usage error exits `EX_USAGE`, not argparse's 2,
    which a command's own answers use."""

    def error(self, message: str):
        self.print_usage(sys.stderr)
        print(f"{self.prog}: {message}", file=sys.stderr)
        raise SystemExit(EX_USAGE)
