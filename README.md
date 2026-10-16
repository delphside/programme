# Programme

How the work on several applications is organised and recorded: the processes
and tools they share, and the records the programme produces. Each application
keeps its own code and technical documents in a repository of its own.

## Layout

| path | holds |
| --- | --- |
| `CLAUDE.md` | the generic rules on one page; each application's `CLAUDE.md` imports it |
| `docs/` | the programme's processes, `1.x`, starting at [1.0](docs/1.0-programme.md) |
| `docs/templates/` | the forms for the records below |
| `.claude/` | the skills and agents every application uses |
| `records/` | records about the whole programme, `2.x`: [2.1 applications](records/2.1-applications.md), [2.2 role holders](records/2.2-roles.md), [2.3 activity log](records/2.3-activity-log.csv), [2.4 weekly digests](records/2.4-weekly-digest/), [2.5 change documents](records/2.5-changes/), [2.6 programme workstreams](records/2.6-workstreams.md) |
| `applications/<app>/` | one folder per application, with the same records in each, `3.n.x` |

The scripts and git hooks are still in the Tile Lite Elite repository
(`scripts/programme/`, `.githooks/`) and move here in a later step of delphside/tile-lite-elite#485.

## Numbering

One number names one document anywhere in the programme's repositories; the
scheme is owned by [1.5](docs/1.5-writing-documents.md). The applications and
their indexes are in [2.1](records/2.1-applications.md).

## How an application consumes it

- The application's repository carries this one as a pinned git submodule at
  `programme/`. Its `CLAUDE.md` imports `programme/CLAUDE.md` and adds its own
  lines; its `.claude/` skills and agents point into `programme/.claude/`. The
  pin moves by a commit of the application's own.
- Every session has this repository checked out beside the application's, and
  writes records here: a commit to `main` locally, a short-lived branch and
  pull request from a cloud session.
- The one programme board will show every repository's issues, with a view per
  application. It is set up in delivery 1 of delphside/tile-lite-elite#485; until then the board is
  Tile Lite Elite's.

The design is in [485](records/2.5-changes/programme-tooling/485-programme-repository/485-design.md).
