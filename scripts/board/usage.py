"""Where the board tooling uses each vocabulary name, read from its own source.

Two readings of `scripts/board/*.py` by `ast`, and no I/O beyond reading those
files:

- `stray_literals`: a string constant equal to a name in `vocabulary.py`, outside
  it. `tests/test_vocabulary.py` fails on one, which is what keeps
  `vocabulary.py` the one copy (#326 R4).
- `readers`: which module reads each field and option, by a reference to its
  constant or a literal. `board-vocabulary.py` prints it, and it is the data the
  data flow design (#383 R18) is generated from.

Docstrings are not matches: a string that is the first statement of a module,
class or function is skipped.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterator

from . import vocabulary

BOARD = Path(__file__).resolve().parent

# A literal that equals a vocabulary name and is not a match for one. Each entry
# is (file, value) with the reason; a file that gains a second such literal is
# covered by the entry, so keep it to what the reason says.
ALLOWED: dict[tuple[str, str], str] = {
    ("model.py", "Claude"): "the checkbox label `**Claude**` (`CLAUDE`), a role label, not the `Turn` option",
}


# The modules that are about the vocabulary, not users of it.
META = ("vocabulary.py", "usage.py", "dataflow.py", "vocabcheck.py", "__init__.py")


def sources() -> list[Path]:
    """The board's modules and entry scripts, not its tests, `vocabulary.py` or the modules in `META`."""
    return sorted(p for p in BOARD.glob("*.py")
                  if p.name not in META)


def _docstrings(tree: ast.AST) -> set[int]:
    skip: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(
                    body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                skip.add(id(body[0].value))
    return skip


def stray_literals(paths: list[Path] | None = None) -> list[tuple[str, int, str]]:
    """(file, line, value) of each string constant that is a vocabulary name."""
    names = vocabulary.all_names()
    found = []
    for path in paths if paths is not None else sources():
        tree = ast.parse(path.read_text(), filename=str(path))
        skip = _docstrings(tree)
        for node in ast.walk(tree):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and id(node) not in skip and node.value in names
                    and (path.name, node.value) not in ALLOWED):
                found.append((path.name, node.lineno, node.value))
    return sorted(found)


# Where a value is an option of two fields (`Closed` is a Ticket State and a PR
# State), the constant's own prefix says which.
_PREFIX_FIELD = {"PR_": vocabulary.PR_STATE, "TKT_": vocabulary.TICKET_STATE}

# `(field, option)`: the option "" is the field itself, and the issue types and
# labels are held under these two names.
ISSUE_TYPE, LABEL = "issue type", "label"
Name = tuple[str, str]


def _homes() -> dict[str, list[Name]]:
    """Each vocabulary value -> the (field, option) pairs it names."""
    out: dict[str, list[Name]] = {}
    for field, options in vocabulary.FIELDS.items():
        out.setdefault(field, []).append((field, ""))
        for option in options:
            out.setdefault(option, []).append((field, option))
    for kind, values in ((ISSUE_TYPE, vocabulary.ISSUE_TYPES + (vocabulary.TYPE_PULL_REQUEST,)),
                         (LABEL, vocabulary.LABELS)):
        for value in values:
            out.setdefault(value, []).append((kind, value))
    for value in vocabulary.FORMER_ROUTES + (vocabulary.DEPRECATED_REPOSITORY,):
        out.setdefault(value, []).append((vocabulary.ROUTE, value))
    return out


def _constant_names() -> dict[str, list[Name]]:
    """Each vocabulary constant's name -> the (field, option) pairs it stands
    for: one, or a field's whole option list for a tuple such as `TURNS`."""
    homes = _homes()
    groups = {options: field for field, options in vocabulary.FIELDS.items() if options}
    out: dict[str, list[Name]] = {}
    for name, value in vars(vocabulary).items():
        if name.startswith("_") or not name.isupper():
            continue
        if isinstance(value, str) and value in homes:
            pairs = homes[value]
            if len(pairs) > 1:
                prefixed = [p for pre, f in _PREFIX_FIELD.items() if name.startswith(pre)
                            for p in pairs if p[0] == f]
                pairs = prefixed or pairs
            out[name] = pairs
        elif isinstance(value, tuple) and value in groups:
            out[name] = [(groups[value], option) for option in value]
        elif value == vocabulary.ISSUE_TYPES:
            out[name] = [(ISSUE_TYPE, v) for v in value]
        elif value == vocabulary.LABELS:
            out[name] = [(LABEL, v) for v in value]
    return out


def references(path: Path) -> Iterator[tuple[int, Name]]:
    """(line, (field, option)) for each use in a module, by constant or literal."""
    constants = _constant_names()
    homes = _homes()
    tree = ast.parse(path.read_text(), filename=str(path))
    skip = _docstrings(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in constants:
            for pair in constants[node.id]:
                yield node.lineno, pair
        elif isinstance(node, ast.Attribute) and node.attr in constants:
            for pair in constants[node.attr]:
                yield node.lineno, pair
        elif (isinstance(node, ast.Constant) and isinstance(node.value, str)
              and id(node) not in skip and node.value in homes
              and (path.name, node.value) not in ALLOWED):
            for pair in homes[node.value]:
                yield node.lineno, pair


def readers() -> dict[Name, set[str]]:
    """(field, option) -> the modules that read it; option "" is the field."""
    out: dict[Name, set[str]] = {}
    for path in sources():
        for _, pair in references(path):
            out.setdefault(pair, set()).add(path.name)
    return out
