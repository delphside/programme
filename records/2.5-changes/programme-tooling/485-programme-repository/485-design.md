# Programme repository shared by every application

The design for **project #485**, in the Programme Tooling workstream. It
applies D73 (#484): one programme manages several applications, the generic
assets and every programme record live in `delphside/programme`, and each
application's repository holds only the application.

*Nothing here is built.* The decisions are answered in the order docs/5.1
sets: the structure of the documents first, then what the split must do,
then how, then the deliveries. All of them are answered; the table at the
end lists them.

## The state today

Everything is in `delphside/tile-lite-elite`. The leak pass
(`/mnt/project-files/notes/programme-leak-pass.md`, repeated at bfc7cb4)
found the generic documents mostly clean of this application, with its
answers in labelled sections, and the scripts still hard-coding it (#476).

| what | where today | class (docs/5.2) |
| --- | --- | --- |
| the rules on one page | `CLAUDE.md` | generic, with this application's lines in it |
| process documents | `docs/5.0` to `docs/5.7`, `docs/1.7` | generic, with labelled sections for this application |
| templates | `docs/templates/` | generic |
| skills, agents, hooks | `.claude/` | generic, except `reference-reviewer`'s file list |
| programme scripts and git hooks | `scripts/programme/`, `.githooks/` | generic code with this application's identity and shape built in |
| workstream list | `docs/5.2` *This application's workstreams* | record |
| role holders | `docs/5.7` *Who holds each role here* | record |
| artefact register | `docs/4.8`, and docs/5.1 §2.15's lists | record |
| delivery log | `docs/5.6`'s rows | record |
| capacity plans, weekly digests | `docs/reports/` | record |
| programme activity log | `docs/programme-activity-log.csv` | record |
| change documents | `docs/changes/` | record |
| the application profile | constants in `sources.py`, `shipping.py`, `.githooks/commit-msg` | record, once #476 exists |

## Structure of the programme repository

Decided by the owner on 2026-10-16: one folder per application, the same files in each.

```text
delphside/programme/
  CLAUDE.md                  the generic rules; each application's CLAUDE.md imports it
  README.md                  the layout, and the lookup until 1.8 exists
  docs/1.0 … 1.7             the programme's definition and processes (were 1.7, 5.0 to 5.7)
  docs/templates/            the templates
  .claude/skills/, agents/   reached by each application through the submodule (T2)
  scripts/, githooks/        the programme tooling (later in this delivery)
  records/                   programme-wide records
    2.1-applications.md      the applications, their index, code and repository
    2.2-roles.md             programme-wide role holders
    2.3-activity-log.csv     the programme activity log
    2.4-weekly-digest/       the weekly digests
    2.5-changes/             change documents for programme-wide work
    2.6-workstreams.md       the programme's own workstreams
  applications/
    tile-lite-elite/         application 1
      README.md              how it fits the programme
      3.1.1-delivery-log.md  and 3.1.2 artefacts, 3.1.3 capacity plans, 3.1.4 workstreams,
                             3.1.5 role holders, 3.1.6 profile (to come), 3.1.7 changes
    dark-portal/             application 2, the same shape
    infrastructure/          application 3, the same shape (#489)
```

**One programme board for every repository.** Decided by the owner on
2026-10-16 (R2 reworded). Issues stay in their application's repository; the
board, an organisation project, shows them all, with a saved view per
application. Issue types and fields are the organisation's, so every
repository has them already; project fields such as PR State are defined
once, on the one board.

**Each application folder has the same shape**, one numbered file per
generic asset, the suffix the same in every application. A record is found by asking "which
application, which asset", and a new application starts from a copy of the
templates.

**One numbering across the programme** (owner, 2026-10-16). A number names
one document anywhere in the four repositories, and equivalent documents
carry equivalent numbers. Each application has an index *n* (1 Tile Lite
Elite, 2 Dark Portal, 3 Infrastructure); its records are `3.n.x` in the
programme repository and its own documents are the range `(3+n).x` in its
repository, so the two numbers point at each other.

| range | holds | where |
| --- | --- | --- |
| 1.x | the programme's definition and processes: 1.0 overview (today 1.7), 1.1 tooling (5.0), 1.2 change lifecycle (5.1), 1.3 workstreams (5.2), 1.4 programme activities (5.3), 1.5 writing documents (5.4), 1.6 the board (5.5), 1.7 roles (5.7), 1.8 document map (comes with the scripts) | programme |
| 2.x | programme-wide records: 2.1 applications, 2.2 programme role holders, 2.3 activity log, 2.4 weekly digests, 2.5 programme-wide change documents, 2.6 the programme's own workstreams | programme |
| 3.n.x | application *n*'s records, the same suffix for every application: 3.n.1 delivery log, 3.n.2 artefact register, 3.n.3 capacity plans, 3.n.4 workstreams, 3.n.5 role holders, 3.n.6 application profile, 3.n.7 change documents | programme, `applications/<app>/` |
| 4.x | Tile Lite Elite's documents: 4.1 overview, 4.2 design, 4.3 development and operation, 4.4 reference, each with today's documents beneath (1.1 architecture becomes 4.1.1) | tile-lite-elite |
| 5.x | Dark Portal's documents, the same four groups (5.1.1 architecture) | dark-portal |
| 6.x | Infrastructure's documents, the same four groups | infrastructure |

Applied in the delivery that moves the files, as a commit of its own after the move (owner, 2026-10-16). A fourth application takes 3.4 and 7.x. The document tooling (`document-map.py`,
`check-docs.sh`) reads two-level numbers today and learns three.

**What leaves each generic document is its labelled section** for this
application: 5.2's workstream tables, 5.7's role holders, 5.6's rows, 5.1
§2.15's artefact lists. The rule stays; the instance moves to the
application's folder and the rule links to the template.

## What the split must do

The functional half, answered after the structure. Each question is put to
the owner with its options; the recommendation is marked.

### F1. What a session in an application repository has without set-up (R4)

**Decided by the owner on 2026-10-16: option 1, both repositories, read and write.**

Today a session in `tile-lite-elite` reads every rule, skill and record from
the one checkout, and writes records with a commit. After the split, three
things it uses live elsewhere: the generic rules, the skills, agents and
hooks, and this application's records. A session writes records often
(change documents, delivery-log rows, the activity log), so reading them is
not enough.

1. **Both repositories, read and write.** Every session, local or cloud,
   starts with the programme repository beside the application's, and can
   commit to it. Constrains: a cloud environment must list both repositories,
   and a local checkout must have both. Recommended: it is today's behaviour
   with a second checkout, and nothing a session does today becomes harder.
2. **Rules and plugin only; records fetched when needed.** The session loads
   the generic rules and the plugin, and reads or writes records through the
   GitHub API. Constrains: every script that reads a record must learn a
   second way to reach it, and an offline local session cannot see them.
3. **Rules, plugin and records read-only; writes go through the programme's
   own sessions.** Keeps one writer per record. Constrains: every delivery-log
   row and change document becomes a hand-off between sessions, which is the
   cost #474 set out to avoid.

Whichever is chosen, a session that finds the programme repository missing
or behind says so at start rather than working from an old copy (the failure
answer in the non-functional design).

### F2. How a project's change document and branch are tied together (R7)

**Decided by the owner on 2026-10-16: option 1, the issue number.**

A project's issue stays on its application's board (R2); its change
document moves to `applications/<app>/3.n.7-changes/`; its branch stays in the
application's repository. Three things in two repositories must still be
found from each other.

1. **The issue number ties them, as today.** The branch is named for the
   work package's issue (`485-…`), the change-document folder for the
   parent's, and both point at the issue. Tooling joins them by number within
   one application. Constrains: an issue number is unique only within one
   repository, so the folder sits under its application and a link across
   repositories is written `delphside/tile-lite-elite#485`. Recommended: no
   new field, and the convention already exists.
2. **The issue body names both.** The project's *Impacted artefacts* and
   *Deliveries* carry the change document's path and the branch. Constrains:
   a second statement of what the numbering already says, and one that goes
   stale when a branch is renamed for a work package.

### F3. How a record reaches the programme repository's main

R7 says a record update is a commit with no branch. That holds for a local
session. A cloud session cannot push to main, so it does what it does today
for records: a short-lived branch and a pull request it merges itself once
the required checks pass (docs/5.1 §2.2). Nothing new to decide; noted so
that the programme repository gets the same required checks and branch
protection as this one, in stage 1.

## How

### T1. How an application reaches the generic documents, scripts and hooks (R3)

**Decided by the owner on 2026-10-16: option 1, a pinned submodule.**

F1 already gives every session the programme repository checked out beside
the application's, at the head of its main, for writing records. The
question is whether the tooling an application runs (its CLAUDE.md import,
the docs gate, the git hooks, the board scripts) uses that live checkout or
a pinned copy.

1. **A submodule, pinned.** The application carries `programme/` as a git
   submodule at a chosen commit and moves the pin by a commit of its own.
   A change to the generic tooling reaches an application, its CI included,
   only when that application takes it, which is how any other dependency is
   taken. Constrains: two copies of the programme in a session, so the
   submodule is read-only by rule (a hook refuses a commit inside it) and
   every write goes to the live checkout; a pin bump per programme change an
   application wants. Recommended: this is what R3 says, and a change to a
   gate cannot turn every application's CI red at once.
2. **The live checkout only.** No submodule; the tooling runs from the
   programme repository at the head of main, and CI checks it out beside the
   application. Constrains: one copy and no bumps, but a programme change
   reaches every application immediately, untested against any of them, and
   R3 is reworded.

### T2. How the skills, agents and hooks arrive (R3, R4)

**Decided by the owner on 2026-10-16: option 1, through the submodule. R3 is reworded to drop the plugin.**

R3 says a Claude Code plugin. **The documentation rules that out for cloud
sessions**: a cloud session "doesn't load the plugins you installed on your
own machine or the ones your repository's `.claude/settings.json` turns on"
(code.claude.com/docs/en/plugins/install). Locally, a plugin enabled in
project settings still has to be installed by hand by each contributor
(plugins/org). Both fail R4. What a cloud session does load is what is
committed under `.claude/` in the cloned repository, and SessionStart hooks
run there (claude-code-on-the-web).

1. **Through the submodule.** The application's `.claude/skills/`,
   `.claude/agents/` and its hook commands point into `programme/` (symlinks,
   and hook paths in `settings.json`), so they come from the pinned commit
   T1 chose. Constrains: the submodule must be initialised before skills are
   read at session start, which the cloud clone may not do; to be shown by a
   trial at the start of stage 1, with the existing SessionStart hook as
   the fallback. R3 is reworded to drop the plugin. Recommended: one
   mechanism, one pin, and no install step anywhere.
2. **A plugin installed by a SessionStart hook.** The hook adds the
   programme's marketplace and installs the plugin each session. Constrains:
   a second version to keep in step with the submodule pin, an install on
   every cloud start, and git credentials inside the hook if the programme
   repository is private.

### T3. How CLAUDE.md is split

Follows T1: the application's CLAUDE.md imports the generic rules from the
programme (`@programme/CLAUDE.md` with a submodule) and keeps only its own
lines: the commit stamp, the deploy and rehearsal lines, its environments.

### T4. How the tooling reads records in the other repository (R7)

Follows from F1 and T1, so not put to the owner. A session or CI job has two
copies of the programme: the pinned submodule, which supplies the tooling,
and the live checkout beside the application, which holds the records. The
tooling reads and writes records only in the live checkout, at a path the
application profile (R8) gives, `../programme` by default and overridable by
an environment variable. CI checks the programme repository out beside the
application in the same way.

Today the scripts find records by path inside this repository: `programme.py`
globs `docs/changes/`, `repo.py` excludes it as not a delivery, and
`documents.py` lists the paths that change on main. After the move those
paths are in another repository, so the three ask the records path instead,
and `documents.py`'s list shrinks to "anything in the programme repository".
Because the records move in stage 1 and the scripts only in stage 2,
**this records-path change is in stage 1**, made in the scripts where they
still are.

## Delivery

### Stage 1, in order

#485 has two deliveries: the first created the repository by hand, and the
second, all of this design, is made in two stages, below.

Tile Lite Elite keeps working throughout: steps 1 to 4 only add to the new
repository, and step 5 switches over in one pull request.

1. **owner**: with `delphside/programme` created and the Claude app and
   `BOARD_TOKEN` given access (delivery 1), add the same required checks and branch
   protection as this repository (F3). Today's organisation board becomes
   the programme board, with a view per application.
2. **Claude**: trial T2 on a scratch branch: a submodule and `.claude/`
   links, then a fresh cloud session, listing which skills and agents it
   loaded. If they do not load, the SessionStart hook initialises the
   submodule and the trial is repeated.
3. **Claude**: bring the generic documents, templates, skills, agents and
   the generic half of CLAUDE.md into the programme repository, then
   renumber them in a commit of their own.
4. **Claude**: bring this application's records into
   `applications/tile-lite-elite/`, numbered 3.1.x, and the programme-wide
   records into 2.x.
5. **Claude**, reviewed by the owner: in this repository, one pull request
   adds the submodule, makes CLAUDE.md import the generic rules, points
   `.claude/` into the submodule, gives the scripts the records path (T4),
   deletes what moved, renumbers this application's documents to 4.x and
   rewrites every link.
6. **Claude**: run the post-deployment checks R1, R2, R4 and R6.

### Stage 2

Stage 2 takes every fact about Tile Lite Elite out of the programme's tooling
into two profiles, then moves the tooling into this repository. It also
regroups Tile Lite Elite's own scripts, which were #447's work under #421 and
were folded in by the owner on 2026-10-16 so that the boundary is designed
once. The facts the tooling holds today are listed, with file and line, in
the stage 2 inventory (`/mnt/project-files/notes/485/stage2-inventory.md`,
2026-10-16).

#### As-is

The tooling is in Tile Lite Elite: `scripts/programme/` (`board/`, `docs/`,
`reports/`), `.githooks/` and the Claude hooks in `.claude/`. It holds Tile
Lite Elite in three ways:

- constants: the repository, the board and the application name
  (`sources.py`, `records.py`);
- shape: what ships (`shipping.py`), where the versions are read
  (`commit-msg`, `board-check.py`), the environment URLs (`programme.py`),
  the `prod-` tags and the CI-status script (`repo.py`);
- location: every script finds the repository from its own path, which
  stops working once it runs from the `programme/` submodule.

Tile Lite Elite's own scripts sit flat in `scripts/`, 35 of them.

#### Layout

The repositories already say whose a script is, so no folder level does
(owner, 2026-10-16):

| repository | holds |
| --- | --- |
| `delphside/programme` | `scripts/board/`, `scripts/docs/`, `scripts/reports/`, `.githooks/`, `.claude/hooks/`, with their tests and CI |
| `delphside/tile-lite-elite` | `scripts/develop/`, `scripts/deliver/`, `scripts/operate/`, `scripts/measure/` (#447's grouping, kept by the owner), its tests, `.claude/settings.json`, `cloud-setup.sh` and its technical profile |

Tile Lite Elite runs the programme's tooling from the pinned submodule: the
git hooks through `core.hooksPath programme/.githooks`, the Claude hooks
through `settings.json` entries into `programme/.claude/hooks/`, and the
board scripts as `programme/scripts/board/...`.

What checks Tile Lite Elite's own code stays there rather than becoming a
setting: `check-api-errors.py` and `check-run-log-events.py` (to
`develop/`), `comment-inventory.py` (to `measure/`), the `cargo fmt` hook
step, `cloud-setup.sh`, and check-docs's two application steps. The
reference reviewer's file table moves into a Tile Lite Elite document the
agent reads through the technical profile.

#### Two profiles

Owner, 2026-10-16: one profile holds what the programme's processes need, in
a form every application shares; the other holds the technical facts.

The **programme profile** is a record, `applications/<app>/3.n.6-profile.md`,
made from a template: identity (name, code, number, repository, board view,
document range), versioning scheme (semver and a commit stamp for Tile Lite
Elite, dates for Infrastructure), environments in order with their purpose
and URL, the routes its deliveries take, its target architecture, and where
its records are. It is markdown like every record, in fixed tables the
scripts parse.

The **technical profile** is `programme.toml` at the application
repository's root, changed on a project branch with the code it describes
(owner: in the application's repository; TOML):

| key | holds |
| --- | --- |
| `versions` | how each version is read, the stamp's pattern, and the files and line pattern of a version-only bump |
| `ships` | the regular expressions for paths that do not reach a release; everything else does |
| `environments` | for each environment the programme profile names, the variables that override its URL and, where it is not fixed, a default (`url`) or a script to source and the variable it sets (`url_from`, `url_variable`) |
| `release` | the tag prefix, the deploy announcement marker, the CI-status command |
| `documents` | generated documents, the document map's path, the tools register |
| `source` | where the source is, for the test designer and the reviewers |
| `hooks` | the application's own pre-commit and check-docs steps |

Where the two overlap, the programme profile names a thing and the technical
profile says how to reach it. What every application shares (the
organisation and the board, issue types and field options, the accounts, the
branch and title conventions, the live checkout's default) goes in one
programme file in this repository.

A script finds its application from the repository it runs in:
`git rev-parse --show-superproject-working-tree` from inside the submodule,
else `--show-toplevel`. Neither needs a git remote, so test fixtures keep
working; `PROGRAMME_PROFILE` overrides, as `PROGRAMME_DIR` does. The tests
replace their Tile Lite Elite literals (about 170 lines in 20 files) with
fake profiles.

Issue numbers across repositories (`owner/repo#N`) are kept out: the owner
moved them to #383 as R13 on 2026-10-16, to be delivered before Dark
Portal's first issue.

#### Also in stage 2

Left by stage 1's review:

- the change-document placement check becomes a gate in this repository's
  CI; until then Tile Lite Elite's `check-docs.sh` only reports it (T1);
- a hook refusing a commit inside the `programme/` submodule;
- whether the activity, problem and improvement registers are records, read
  from the live checkout, or generic documents read from the pin;
- `repo.py`'s `NOTES` prefix matches only history;
- `board-records.py` gets its row in 1.1.

Found by the inventory: `board-digest.py` names the weekly digest `TLE_WD_`,
where 2.1 says `PRG_WD_`.

#### Delivery

One branch in each repository. This repository's carries the scripts,
hooks, programme file and profile template, with their tests and CI, and
merges first. Tile Lite Elite's carries the deletions, the regrouping, its
technical profile, every caller's new path (scripts, workflows, `e2e/`, the
shell aliases, documents) and the submodule pin; the owner reviews it, and
it is tried from the branch on preview and rehearsal before it merges,
because `deploy.sh` moves.

**Found in stage 1's trials**: a cloud thread starts in a workspace folder
with every project repository beside it and loads each one's `CLAUDE.md`,
skills and agents natively, so in the cloud the programme's arrive from the
checkout beside, and the submodule's symlinks serve local sessions. No
repository's `settings.json` hooks run there; the project's cloud
environment runs each repository's `cloud-setup.sh` instead
([`.claude/cloud-environment-setup.sh`](../../../../.claude/cloud-environment-setup.sh)).

### Delivery decisions

- **D1. Whether the programme repository is public.** *Decided by the owner on 2026-10-16: public.* Today every programme
  document and record is public, in this repository. Public keeps that, and
  lets the submodule and the plugin-free `.claude/` links load with no
  credentials in CI or a cloud session. Private hides the records (delivery
  log, capacity plans, host details) and needs a token wherever the
  submodule is fetched. Recommended: public, with the existing rule that
  security specifics stay off GitHub.
- **D2. Whether history moves with the files.** *Decided by the owner on 2026-10-16: keep the history.* Bringing the files across
  with `git filter-repo` keeps each document's history and blame in the new
  repository; a plain copy starts them fresh, with the source commit named
  in the first commit message. Recommended: keep the history; it costs one
  extra command and the documents' reasons live in their commits.

## Decisions

Every question was put to the owner as a decision card on 2026-10-16 and
answered the same day, in the order docs/5.1 sets. None was open long enough
to need a `Decision` issue.

| | question | answer |
| --- | --- | --- |
| structure | layout of the programme repository | a folder per application, the same files in each |
| structure | document numbering | one programme-wide scheme, applied in stage 1 |
| F1 | what a session has without set-up | both repositories, read and write |
| F2 | what ties a change document to its branch | the issue number |
| R2 | boards | one programme board, a view per application |
| T1 | how an application reaches the generic tooling | a pinned submodule |
| T2 | how skills, agents and hooks arrive | through the submodule, not a plugin |
| D1 | programme repository visibility | public |
| D2 | history of moved files | kept, with `git filter-repo` |
| stage 2 | where the application profile lives | split in two: a programme profile in the records folder, a technical profile in the application's repository |
| stage 2 | script layout | no programme or application level; #447's grouping kept |
| stage 2 | #447 | folded into stage 2 |
| stage 2 | technical profile format | TOML |
| stage 2 | issue numbers across repositories | later, #383 R13 |
