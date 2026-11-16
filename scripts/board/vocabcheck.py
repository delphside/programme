"""Does each name in `vocabulary.py` still exist in GitHub? #383 R20 to R22.

A check, never a gate: it reports and a person decides. It answers one
question, *is a name the tooling matches gone*, and so:

- a field or option the vocabulary holds and GitHub does not is a finding;
- an option GitHub has and the tooling does not read says nothing (#326 R2);
- a new option does not fail it (#326 R3).

The live data comes from `sources.py` and is passed in, so this does no I/O. A
source that cannot answer is the caller's `Unavailable`, which is *not checked*
and never a pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from . import vocabulary


@dataclass(frozen=True)
class Missing:
    """A vocabulary name GitHub does not have: a field, or one of its options."""

    field: str
    option: str | None
    where: str      # `issue fields` or `the Projects board`

    def __str__(self) -> str:
        if self.option is None:
            return f"field {self.field!r} is not among the {self.where}"
        return f"option {self.option!r} is not on {self.field!r} ({self.where})"


def check(issue_fields: Mapping[str, Sequence[str]],
          project_fields: Mapping[str, Sequence[str]]) -> list[Missing]:
    """The vocabulary names absent from the live fields, in vocabulary order.

    `issue_fields` and `project_fields` are {field name: option names} of the
    single-select fields. A field in `vocabulary.TEXT_FIELDS` is not looked for."""
    found = []
    for field, options in vocabulary.FIELDS.items():
        if field in vocabulary.TEXT_FIELDS:
            continue
        on_board = field in vocabulary.PROJECT_FIELDS
        live = project_fields if on_board else issue_fields
        where = "the Projects board" if on_board else "issue fields"
        if field not in live:
            found.append(Missing(field, None, where))
            continue
        have = set(live[field])
        found.extend(Missing(field, option, where) for option in options
                     if option not in have)
    return found


def render(found: Sequence[Missing], colour: bool = True, verbose: bool = False) -> str:
    """One line per name missing. **Nothing at all when none is**, unless
    `verbose`: the quiet case says nothing (#326's test approach). `verbose` also
    says what the check did not look at."""
    paint = (lambda code, t: f"\033[{code}m{t}\033[0m") if colour else (lambda code, t: t)
    n_options = sum(len(o) for o in vocabulary.FIELDS.values())
    out = []
    if found or verbose:
        out.append(f"{paint('1', 'VOCABULARY')}  "
                   + paint('2', f"{len(vocabulary.FIELDS)} fields and {n_options} options the "
                                "tooling matches, against GitHub's"))
    if verbose and not found:
        out.append(f"  {paint('32', 'ok')} " + paint('2', "every one exists"))
    for m in found:
        out.append(f"  {paint('33', '!')} {m}")
    if verbose:
        out.append(paint('2', "  not checked: " + ", ".join(vocabulary.TEXT_FIELDS)
                         + " (not a single-select, so the query shows no options); "
                           "labels and issue types"))
    return "\n".join(out)
