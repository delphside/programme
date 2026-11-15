"""The board flow's settings: every figure and identifier the daily sweep
(`board-flow.py`) and the role lists hold, in one place (docs/1.10, *Where an
application's settings are held*). The bounds are not here: they are the flow
table's, in `model.py`.

Designed in `programme/records/2.5-changes/process-definition/176-project-board-flow/`.
"""

from __future__ import annotations

# Each REST call is cut at this long (implementation.md, *Non-functional design*,
# limits and timeouts). The figure is `sources.py`'s own for its REST reads
# before the sweep existed; it is a setting so a test can shorten it.
REST_TIMEOUT_SECONDS = 120

# How many of an item's own reads (sub-issues, dependencies, timeline, reviews)
# are made at once. A hundred items took over two minutes one after another
# (measured 2026-11-15); GitHub's limit on concurrent requests is well above this.
READ_WORKERS = 8

# The issue whose body each sweep rewrites, found in the programme repository
# by this exact title (owner, 2026-11-13: a pinned issue). It is an identifier:
# changing it blinds the sweep to the issue that exists (docs/1.10).
STALLED_LIST_TITLE = "Board flow: the stalled list"

# Issue fields, by name, and the organisation's id for each (REST writes take
# an id). Read from the issues' own `issue_field_values` on 2026-11-15, except
# `Turn`, which the owner created and gave the handover. `Claimed by` is a text
# field whose id is not yet known: None until it is set here, and until then the
# sweep takes it from an issue that carries a value, or fails the write naming
# it. A name missing here is learned the same way.
FIELD_IDS: dict[str, int | None] = {
    "Turn": 49935304,
    "Project State": 46162136,
    "Requirement State": 46185224,
    "Decision State": 46531431,
    "Ticket State": 48733274,
    "Workstream": 46217763,
    "Route": 46415058,
    "Claimed by": None,
}

# How far back a merged pull request is read for the `Refs #N` it carries, to
# catch a merge whose work package was not moved. A missed week of sweeps is
# tolerated; the figure has no measurement behind it (chosen 2026-11-15).
MERGED_LOOKBACK_DAYS = 30

# The branch a merge delivers to.
DEFAULT_BRANCH = "main"
