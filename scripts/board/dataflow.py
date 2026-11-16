"""Which module reads each field and option: the data R18's data flow design is generated from.

Built from `vocabulary.py` (what exists) and `usage.py` (what each module
reads, by `ast`), so it cannot drift from either. No I/O beyond reading the
board's source. A Markdown table and a Mermaid flowchart: fields, then options,
then the modules that read them.
"""

from __future__ import annotations

from . import usage, vocabulary

# What a module reads when it uses one of these, besides the field names.
KINDS = (
    (usage.ISSUE_TYPE, vocabulary.ISSUE_TYPES + (vocabulary.TYPE_PULL_REQUEST,)),
    (usage.LABEL, vocabulary.LABELS),
)


def groups() -> list[tuple[str, tuple[str, ...]]]:
    """Each field, then the issue types and labels, with the names under it."""
    out = [(field, options) for field, options in vocabulary.FIELDS.items()]
    out.extend(KINDS)
    return out


def table() -> list[tuple[str, str, tuple[str, ...]]]:
    """(field, option or "", readers) per row: a field's own row, then its options."""
    read = usage.readers()
    rows = []
    for field, options in groups():
        if field not in (usage.ISSUE_TYPE, usage.LABEL):
            rows.append((field, "", tuple(sorted(read.get((field, ""), ())))))
        for option in options:
            rows.append((field, option, tuple(sorted(read.get((field, option), ())))))
    return rows


def markdown() -> str:
    """The table: one row per field and per option, naming its readers."""
    out = ["| Field | Option | Read by |", "| --- | --- | --- |"]
    for field, option, modules in table():
        who = ", ".join(f"`{m}`" for m in modules) or "none"
        out.append(f"| `{field}` | {f'`{option}`' if option else 'the field'} | {who} |")
    return "\n".join(out)


def mermaid() -> str:
    """The flowchart, left to right: field, option, module."""
    out = ["flowchart LR"]
    modules: set[str] = set()
    option_ids: dict[tuple[str, str], str] = {}
    field_ids: dict[str, str] = {}
    for field, option, readers in table():
        if field not in field_ids and option:
            field_ids[field] = f"F{len(field_ids)}"
            out.append(f'    {field_ids[field]}["{field}"]')
        if not option:
            field_ids[field] = f"F{len(field_ids)}"
            out.append(f'    {field_ids[field]}["{field}"]')
            for m in readers:
                modules.add(m)
                out.append(f"    {field_ids[field]} --> {_module(m)}")
            continue
        oid = option_ids.setdefault((field, option), f"O{len(option_ids)}")
        out.append(f'    {oid}("{option}")')
        out.append(f"    {field_ids[field]} --- {oid}")
        for m in readers:
            modules.add(m)
            out.append(f"    {oid} --> {_module(m)}")
    for m in sorted(modules):
        out.append(f'    {_module(m)}[["{m}"]]')
    return "\n".join(out)


def _module(name: str) -> str:
    return "M_" + name.removesuffix(".py").replace("-", "_")


def render() -> str:
    return ("## Which module reads each field and option\n\n" + markdown()
            + "\n\n```mermaid\n" + mermaid() + "\n```\n")
