# Programme

How the work on several applications is organised and recorded: the processes
and tools they share, and the records the programme produces. Each application
keeps its own code and technical documents in a repository of its own.

## Layout

| Path | Holds |
| --- | --- |
| `CLAUDE.md` | the generic rules on one page; each application's `CLAUDE.md` imports it |
| `docs/` | the programme's processes, `1.x`, starting at [1.0](docs/1.0-programme.md) |
| `docs/templates/` | the forms for the records, the agents' handover, the triage comment and the test design specification |
| `config/programme.toml` | what every application shares: the organisation, the board, the accounts, the programme repository and the paths of its registers |
| `scripts/` | the board model and its commands (`board/`), the documents' checks and generators (`docs/`), the reports (`reports/`) and the tests of all of them (`board/tests/`, `tests/`) |
| `.githooks/` | the git hooks an application runs through the script in its own `.githooks/`, and `in-submodule/`, which refuses a commit inside the submodule |
| `.claude/` | the skills and agents every application uses, `hooks/`, the three Claude Code hooks its `settings.json` runs, and `cloud-environment-setup.sh`, the cloud environment's setup script |
| `.github/workflows/` | `ci.yml`, this repository's CI: the model's tests, the scripts' tests and the documents gate; and `board-add.yml`, which puts every repository's open items on the board |
| `records/` | records about the whole programme, `2.x`: [2.1 applications](records/2.1-applications.md), [2.2 role holders](records/2.2-roles.md), [2.3 activity log](records/2.3-activity-log.csv), [2.4 weekly digests](records/2.4-weekly-digest/), [2.5 change documents](records/2.5-changes/), [2.6 programme workstreams](records/2.6-workstreams.md) |
| `applications/<app>/` | one folder per application, with each record under the same suffix, `3.n.x` ([2.1](records/2.1-applications.md#what-each-applications-folder-holds)) |

## Numbering

The numbering scheme is [1.5](docs/1.5-writing-documents.md)'s. The
applications and their indexes are in [2.1](records/2.1-applications.md).

## How an application consumes it

- The application's repository carries this one as a pinned git submodule at
  `programme/`, and its `CLAUDE.md` imports `programme/CLAUDE.md`. The pin moves
  by a commit of the application's own. How its hooks reach the programme's is
  in
  [1.1 *Two kinds of tooling*](docs/1.1-programme-tooling.md#two-kinds-of-tooling).
- Every session has this repository checked out beside the application's, and
  writes records here: a commit to `main` locally, a short-lived branch and
  pull request from a cloud session.
- One programme board shows every repository's issues
  ([1.6](docs/1.6-github-project-board.md)).

The design is in
[the programme repository's design](records/2.5-changes/programme-tooling/485-programme-repository/485-design.md).
