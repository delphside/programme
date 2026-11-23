# Programme

How the work on several applications is organised and recorded: the processes
and tools they share, and the records the programme produces. Each application
keeps its own code and technical documents in a repository of its own, and
carries this one as its `programme/` submodule.

## Layout

[1.1](docs/1.1-programme-tooling.md) describes each tool and says how an
application's own tooling differs from the programme's.

| Path | Holds |
| --- | --- |
| [`CLAUDE.md`](CLAUDE.md) | the generic rules on one page; each application's `CLAUDE.md` imports it |
| [`docs/`](docs/) | the programme's processes, `1.x`, starting at [1.0](docs/1.0-programme.md) |
| [`docs/templates/`](docs/templates/README.md) | documents to copy and fill in; its README lists each |
| [`config/programme.toml`](config/programme.toml) | what every application shares: the organisation, the board, the accounts, the comment and sweep settings, the programme repository, and the paths of its registers, records and programme documents |
| [`scripts/board/`](scripts/board/) | the board model and its commands, and their tests (`board/tests/`) |
| [`scripts/docs/`](scripts/docs/) | the documents' checks and generators |
| [`scripts/reports/`](scripts/reports/) | the reports |
| [`scripts/deliver/`](scripts/deliver/) | Turpin, the build, release and deploy tool: application tooling that lives here ([1.1 *Two kinds of tooling*](docs/1.1-programme-tooling.md#two-kinds-of-tooling)) |
| [`scripts/tests/`](scripts/tests/) | the tests of the other scripts, the git hooks, the Claude hooks and the cloud setup script |
| [`.githooks/`](.githooks/) | the git hooks `commit-msg`, `pre-commit` and `post-merge`, which an application that runs them reaches through `shim.sh` in its own `.githooks/`, and `in-submodule/`, which refuses a commit inside the submodule |
| [`.claude/skills/`](.claude/skills/) and [`.claude/agents/`](.claude/agents/) | the skills and agents every application uses |
| [`.claude/agents-common.md`](.claude/agents-common.md) | what every agent reads first |
| [`.claude/hooks/`](.claude/hooks/) | the Claude Code hooks an application runs ([1.1](docs/1.1-programme-tooling.md) says how), and `application-root.sh`, which they source |
| [`.claude/cloud-environment-setup.sh`](.claude/cloud-environment-setup.sh) | the setup script of the cloud environment |
| [`.github/workflows/ci.yml`](.github/workflows/ci.yml) | this repository's CI: the board model's tests, the scripts' tests and the documents gate |
| [`.github/workflows/board-add.yml`](.github/workflows/board-add.yml) | puts every repository's open items on the board |
| [`.github/workflows/pr-state.yml`](.github/workflows/pr-state.yml) | keeps the board's `PR State` current for this repository's pull requests |
| [`.github/workflows/context.yml`](.github/workflows/context.yml) | keeps the context header on every open programme project current |
| [`.github/pull_request_template.md`](.github/pull_request_template.md) | the form of a pull request to this repository |
| [`records/`](records/) | records about the whole programme, `2.x`: [2.1 applications](records/2.1-applications.md), [2.2 role holders](records/2.2-roles.md), [2.3 activity log](records/2.3-activity-log.csv), [2.4 weekly digests](records/2.4-weekly-digest/), [2.5 change documents](records/2.5-changes/), [2.6 programme workstreams](records/2.6-workstreams.md), [2.7 improvement registers](records/2.7-improvement-registers.md) |
| [`applications/<app>/`](applications/) | one folder per application, with each record under the same suffix, `3.n.x` ([2.1](records/2.1-applications.md#what-each-applications-folder-holds)) |

The numbering scheme, and so what each document number covers, is
[1.5](docs/1.5-writing-documents.md#each-range-covers-one-scope)'s.

## How an application uses the programme

- The submodule is pinned, and the pin moves by a commit of the application's
  own. How its hooks reach the programme's is in
  [1.1 *Two kinds of tooling*](docs/1.1-programme-tooling.md#two-kinds-of-tooling).
- Every session has this repository checked out beside the application's, and
  writes every programme change here:
  - locally, a commit to `main`, or a branch where the change's route takes one
    (the application's tooling, `scripts/deliver/`);
  - from a cloud session, a short-lived branch and pull request
    ([1.2 *A session that cannot push to `main`*](docs/1.2-change-lifecycle.md#a-session-that-cannot-push-to-main)).
- One programme board shows every repository's issues
  ([1.6](docs/1.6-github-project-board.md)).
