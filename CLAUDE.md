# The process on one page

This page owns the rules. The numbered documents own the procedures and the
reasons, and issues own the arguments. If this page and a document disagree,
one of them has a defect: read how they came apart (the rule on disagreements
under *Documentation*), then fix it; do not work around it. docs/1.2 §1's key
terms table defines the terms.

**A Claude Code session on the web** (claude.ai/code) works without the local
session's memory, and with git hooks only where its application's cloud setup
switches them on (Tile Lite Elite's does). It:

- answers questions and comments on issues freely;
- changes things only by branch and pull request, never by pushing to `main`;
- where `main` has since changed text its branch also changes, rebases,
  redoes its edit on `main`'s text, has the parts that came out different
  reviewed again and force-pushes, with a lease, only to a branch of its own
  (owner, 2026-11-23; docs/1.2 *When `main` moves under a branch*);
- merges its own pull request once the required checks pass and its review
  rounds find nothing material, except an application change, which waits for
  the owner's review (docs/1.2 §2.2); a new or changed rule is agreed with him
  in the chat first;
- leaves the local session a note before it finishes, on the issue the work
  concerns or else on the notes issue named in its application's CLAUDE.md,
  read by the local session at its next start.

docs/1.6 records the app it works through.

## The work

- **The rules serve the project; the project does not serve the rules.** The
  owner may set any rule aside for a reason; Claude says which, does what he
  decided and records it on the issue, the delivery-log row or the commit. A
  rule that is continually set aside suggests a defect in the rule: consider
  changing it.
- **A change that seems possible is raised quickly, as one or more of four
  vehicles** (docs/1.2 *Where a possible change goes*); discussion goes in
  comments, conclusions in the body, kept current.

  | Where | Vehicle |
  | --- | --- |
  | agreed, and needs no branch | a pre-approved change |
  | whether to act, or how to group or split it into projects, is open | a `Requirement` |
  | it certainly needs doing, and that is decided | a project |
  | a lesson for continual improvement | a note in the next weekly digest |

- **Raise quickly, but into an existing requirement where one covers the area**
  (owner, 2026-09-17). Look first. A new issue is right where the subject is
  genuinely separate, or where widening a scoped one would reopen it.
- **A decision belongs on what it decides**, with its own issue only where it
  spans several or its argument would bury the requirement. Either way it is a
  `Decision` issue, the GitHub issue type, whose `Decision State` and
  `Agreed Decision` heading `board-check.py` reads.
- **A decision is only worth an issue while there is a choice to discuss**,
  while anybody still has to be convinced (owner, 2026-09-21); a settled answer
  goes straight to its owning document and this page, the argument in the
  commit, with no issue or `D` number.
- **Whether to do something is a Requirement; how to do it is a Decision**
  (owner, 2026-09-27), so an idea not yet agreed is raised as a requirement.
- **A settled decision is never maintained; the document carrying it is** (see
  *Documentation*).
- **Options live in the body, numbered, each saying what it constrains**
  (owner).
- **Make a tooling change when something first needs it**; raise its
  requirement at once.
- **A change the weekly review proposes is a fix or an improvement** (owner,
  2026-10-27; docs/1.4). A fix cites what went wrong and what it cost him, and
  goes ahead as BAU or a project as its type decides; an improvement makes
  something that works better, and waits for him to pick it at the monthly
  `improvement-review`. A mistake is left to review the first time, and once
  it recurs is a candidate for an automatic check.
- **Documentation, process and tooling changes go on without the owner**
  (owner, 2026-11-09; docs/1.2 §2.2, docs/1.4): they merge without his
  review, and only these go to him, in the chat, never left in a document,
  pull request or issue:
  - a new or changed rule, for his agreement before it lands;
  - an action or a question that blocks the work.

  A change to the application still takes his review.
- **Claude sweeps, the owner reacts**: Claude looks across every open item,
  brings him what needs him and moves the rest.
- **Triage is joint: the owner comments first, and Claude writes the triage
  comment and sets the fields from his** (owner, 2026-11-04; docs/1.2 §2.17):
  - Claude triages alone in Process Definition, Programme Tooling and each
    application's Delivery Tooling, and for type `tooling` or `documentation`
    anywhere (delphside/tile-lite-elite#382
    *[Decision]: D54 · Claude's triage scope*, 2026-09-17);
  - of a dependency advisory, only whether it can wait goes to him (owner,
    2026-11-03);
  - anything reaching production, the product and its rules, and anything
    irreversible outside git go to him whatever the workstream.

  The minimum is a clear short title, workstream, priority and type of
  change; then scope (options, dependencies, effort), then project planning,
  whose outcomes are solo project, grouped project, straight to main, on hold
  or cancelled.
- **Related change goes in one project, so it is designed once** (owner,
  2026-09-21; docs/1.2 §2.23), with as little design as possible coordinated
  across projects; a different route splits a delivery, not a project. Two
  projects, linked under *Dependencies and related work*, are right where
  deciding one does not constrain the other.
- **The exception is a shared mechanism**, owned by one workstream (docs/1.3)
  and designed to by the others (owner, 2026-09-21): its own delivery project,
  every use case a customer, each workstream building on top. One that would
  exist for only one caller belongs to that caller's project.
- **A mechanism ships in the same release as its first customers** (owner,
  2026-09-21): scoped and designed independently, scheduled jointly on its
  first callers' milestone.
- **A project owns its requirements: whoever raises it folds its sources into
  it and closes them.** Its issue carries the seven headings of docs/1.2 §2,
  each holding the content or a link to the design document that holds it,
  never both.
- **Non-functional design is four questions and *none, because…* answers any
  of them**: capacity, failure, limits and timeouts, secrets and access. A
  limit's answer says where its number came from.
- **A dependency is declared from both ends**, `waits on` and `is needed by`
  in the two bodies, and as a GitHub link, which `board-check.py` checks
  within the issue's own repository.
- **A project moves through the `Project State` field**, in the field's own
  words:

  | Phase | Done when |
  | --- | --- |
  | Scope | What the project does. Technical option chosen where it affects dependencies. |
  | Q3, Q2, Q1 | The queue. Q1 is next off the blocks. |
  | Design and Test Approach | Design option chosen. Design completed. Test Approach defined. |
  | Development | Being built on its project delivery branch |
  | User testing | On Preview for user functional testing. On Rehearsal for technical testing. Where the application has them: its profile (`3.n.6`) says which environments it has. |
  | Deployment | Image: Prev->Reh->Prod. Repo-only: merge. Non-repo: by hand. |
  | Post-deployment | Check it is working and giving the benefit expected. |
  | Project Closedown | Lessons learnt completed. |

  - the test manager approves the test approach before Development (docs/1.9
    *The test policy*);
  - whoever holds a phase moves it on where no tool does: the design authority
    at Scope and Design and Test Approach, the technical lead from Development
    to closing (for a parent, its design authority);
  - at each `board-sweep` (docs/1.4) Claude proposes moving a workstream's Q1
    project to Design and Test Approach where it has none there, and the owner
    agrees it (owner, 2026-11-04; docs/1.2 §2.22);
  - the daily sweep lists a project past its phase's bound, for the phase's
    holder (docs/1.2 §2.24);
  - the post-deployment check has one row per requirement.
- **A problem found in testing is fixed on the branch, and the branch is
  retested** (owner, 2026-09-26; docs/1.2 §2.1); one found after the merge
  reopens the package or goes in a later one. A merge moves a Production
  Release package to Deployment, a tooling-route one to Post-deployment.
- **A work package is at most one delivery, and so one route** (owner,
  2026-09-27); a delivery may carry several. Building and running a tool are
  two packages.

## Changes

- **A Production Release always takes a branch, a pull request, a semver
  milestone and a row in the delivery log** (docs/1.2 §2.2).
- **Proven and unshipped is the normal state** (delphside/tile-lite-elite#388
  *[Decision]: D55 · Whether a release-route change may reach main before its
  release*). A release change merges to `main` once preview, user
  testing and rehearsal (where the application has them) pass at its branch
  tip, and ships then or later. A release branch is for a release that must
  stabilise while `main` moves on, not for one delivery. An emergency is cut
  from the last released tag, never from `main`.
- **Otherwise the route decides the branch** (docs/1.2 §2.2):
  - Application Tooling takes one;
  - Docs and Programme Tooling goes straight to `main`, which is what
    pre-approved means;
  - so does a document change, unless it is large enough to be given
    Application Tooling;
  - a cloud session's branch and pull request are incidental to the route.
- **One branch per project at a time, and everything the project touches goes
  on it**, its technical documentation included; a dependency update project
  keeps a branch per update.
- **Programme documents, generic assets and records belong to no project and
  change on `main`** (docs/1.3): the programme's own list and each technical
  profile's `documents` table, as `scripts/board/documents.py` reads them.
- **Pre-approved does not mean unreviewed**: the discussion was the review,
  enough where a change is cheap to reverse, which an image change is not.
- **The pull request body says which part of the project's scope is being
  requested, and what is deliberately left out** (owner, 2026-09-17): the
  review surface, restating nothing the issue or documents hold. Where his
  review is owed (docs/1.2 §2.2), add the owner as reviewer at creation and ask
  in the chat; he approves, and Claude merges by rebase and fast-forward.
- A review comes back two ways and they return differently. **Approved with
  comments** stays approved: make the changes and merge. **Changes requested**
  does not: make the changes, then re-request the review, which is what puts it
  back to awaiting review rather than leaving it sitting as answered. The board
  reads both from `reviewDecision`, so skipping the re-request leaves it in the
  wrong column and waiting on nobody.
- **Commits and pull requests say `Refs #N`, never `Closes #N`** (owner,
  2026-10-26; docs/1.2 §2.5): no merge closes an issue, and GitHub's
  auto-close is off (docs/1.6). The deploy settles its milestone; the rest is
  closed by hand.
- **Programme business-as-usual (BAU) work needs no issue**: its commits say
  `Activity: <id>` from docs/1.4's register, and `Initiative: <id>` where there
  is one. BAU is its own triage, so a change that would benefit from a
  project's controls (docs/1.4's table decides), or touches an asset BAU does
  not own, becomes a project, never a requirement.
- **Every commit subject starts with the application's stamp**, from its
  CLAUDE.md, and a space.
- **A commit on a project's branch says `Refs` for the work package it
  delivers**, and need not name the requirements folded into it (docs/1.2
  §2.5). The author rewords one written before its work package was raised,
  ahead of the branch's first test deployment, or of its merge if it has none.
- **Push immediately after committing**: until pushed, a change does not exist.
  Run an unpushed script only to test it.

## Deliveries and releases

- **A *delivery* is a change reaching its users, and every change has one**:
  any update to a programme asset, documents included. A *release* is a new
  version of the application, delivered to production with a new semver.
- **A programme change reaches an application when its pin moves** (owner,
  2026-11-09; docs/1.1, docs/1.2). A Docs and Programme Tooling delivery
  changing anything outside `records/` and `applications/` plans each pin
  move in its steps. Whoever runs a programme tool from an application first
  moves the pin where the programme changed, except on a release branch under
  test or in an emergency.
- **The route decides a delivery's shape** (docs/1.2 §1.0, §1.1):

  | Route | Milestone | Branch and pull request | Delivery log |
  | --- | --- | --- | --- |
  | Docs and Programme Tooling, straight to `main` | none | none, except a web session's own pull request | none |
  | Other, by hand | a date | none | a row |
  | Other, host maintenance | the infrastructure application's date | none | a row in its log |
  | Application Tooling | a date | yes | a row |
  | Production Release | a semver | yes | a row |

  A change straight to `main` is not one point in time; its record is the
  commit, citing what it serves.
- **A milestone marks a delivery made at one point in time** and places it in
  the sequence: the semver where it includes a release, otherwise the day it
  lands, `YYYY.MM.DD-n`, set then and never renamed. **Milestones are only
  semvers and dates, two independent sequences** (owner, 2026-10-26 and
  2026-11-03): a release's semver is fixed when it is made, and a date says
  only when. `pre-approved`, `no-release`, `patch`, `minor` and `major` are
  retired (docs/1.2 §2.15).
- **A change to an application's own asset that reaches the image takes a new
  semver**, being a Production Release; its artefact register (`3.n.2`) lists
  them.
- **`Route` belongs to the artefact, and a delivery has one route.** Work
  touching artefacts with different routes is split into a delivery per route.
- **Documentation riding on a release is a pre-approved add-on**: still one
  delivery under the release's semver, with no milestone, pull request or row
  of its own.
- **A Requirement never carries a milestone.** It delivers by folding into a
  project, whose work package carries the milestone, or straight to `main` with
  none. An application's deploy script can warn about a milestone on a
  requirement.
- **A routine update owes what its route owes, and nothing more** (docs/1.2
  §2.2.1, §2.15):
  - a Production Release bump reaches `main` by pull request, CI its regression
    check, rides the next release and never justifies one;
  - each update is tested for what it changes, on preview and rehearsal (where
    the application has them) at the branch tip, where only a deployed stack
    can show it;
  - a new toolchain or major version gets a look at its new features, and
    anything worth considering is raised as a requirement;
  - host maintenance (a host package, the container runtime, a kernel, a
    reboot, hand-set host configuration) is the infrastructure application's
    delivery, numbered by date; what an application installs on its host (its
    scripts, systemd units and the packages it needs) is its release.
- **A dependency update takes the least ceremony its route allows**:
  - an Application Tooling one takes none: its pull request and commit message
    are the record (owner);
  - a Production Release one, whoever raised it, is a row in the release's
    dependency update project, `#N Dependency updates for X.Y.Z`, with no
    project of its own (owner, 2026-11-04);
  - a host change the owner decides on is host maintenance.
- **Every delivery is one or more work packages**, each carried by a
  sub-project or by the parent (docs/1.2 §1.1). Packages sharing a milestone
  are delivered together, a grouping with no issue of its own. A parent lists
  what it delivers, each row naming the packages that share a milestone or
  saying straight to main.
- **A project that is one package is its own work package; otherwise every
  package in a milestoned delivery has a sub-project.** A delivery with no
  milestone may have one for its steps, tests or checks (docs/1.2).
- **A work package is titled `#N WP A Del 1 of 2: what it delivers`, a parent
  `#N MAIN PROJECT: what it is`** (docs/1.2 *Naming*). The counts are kept
  though they go stale; nothing checks them yet.
- **The parent owns the requirements, the design and the documents**; a work
  package links to them and owns its artefacts, test approach and
  post-deployment checks.
- **A parent with sub-projects carries no milestone and no Route**; settling a
  milestone leaves it out, and `board-check.py` reports a Route on one.
- **The parent runs Scope, the queue and Design and Test Approach, then
  stops**, reaching Post-deployment only for a requirement no single delivery
  satisfies, and Project Closedown to close. A work package may delegate
  lessons learnt to the parent, and says so.
- **A release is made once, at the end of regression; deploying it is choosing
  a version.** Making it, once the test manager has checked the regression
  results and the owner judges rehearsal passed, checks the milestone, writes
  its record, tags the version and bumps `main` to the next patch; a deploy
  checks only the record, the schema and a smoke test (docs/1.2 *Making a
  release, then deploying it*).
- **A release milestone is a shipping list**: move out what is not shipping
  before the release is made (docs/1.2 §2.5).
- **A change merged after the build for *rehearse the release* started waits
  for the next release** (owner, 2026-11-18; docs/1.2 *Scheduling a release*):
  - it joins this release only for a good reason the owner accepts, and the
    regression then runs again;
  - a change that cannot wait for the next release is an emergency.
- **After deploying, run the application's verification and trust its exit
  status**, not its output; its CLAUDE.md names it and what a deploy does.
- **A change to production is the owner's to run; either may read it, Claude
  by default** (owner, 2026-09-21 and 2026-11-18). Claude asks him for a
  change, or a read it cannot reach, and works from what comes back:
  - a change (a deploy, a database write, a restart, a configuration change):
    the owner's;
  - a read (the deployed version and commit, an admin listing, a database
    query, a log dump): Claude's where it can reach production, the owner's
    whenever he chooses;
  - copying production's data into a closed-access rehearsal, where technical
    testing or a deployment rehearsal needs it: Claude's; elsewhere: the
    owner's, as it changes who can see it.

## Tests, checks and decisions

- **Reading jobs with a defined file set, and a work package's change, go to an
  agent; triage, decisions and anything touching production stay with Claude.**
  An agent runs on the model its file sets; a review runs in rounds until one
  finds nothing material (owner, 2026-10-14; docs/1.1). A document change is
  reviewed against docs/1.5 by `document-reviewer-reader` and
  `document-reviewer-truth`, a pull request carrying code by `change-reviewer`
  whoever wrote the code, and a bot's pull request owes no rounds.
- **Test conditions derive from stated rules, not from the code**: an
  application's in its documents, the programme tooling's in the numbered ones.
- **A gate refuses and work stops; a check reports and a person decides.** A
  new check is shown to fail before it ships.
- **Every checkbox names whose move it is**, on the box itself:
  `- [ ] **owner** — run the browser tests` or `- [ ] **Claude** — write the
  tests`. `board-check.py` reports an unlabelled box, which waits on nobody.
- **Claude applies a decision in the same commit that marks it answered**, or
  raises an issue and names it in the decision.
- **A project answers its decisions in order**: document structure, then
  functional requirements, then technical decisions, delivery planning last
  (docs/1.2 *Decisions*).
- **A project's decisions are logged by link**: closed once applied, cited in a
  footnote where the design states the conclusion, and listed in a Decisions
  table in the project's body (owner, 2026-09-29; docs/1.2).
- **A decision is not a change vehicle; it routes work** (docs/1.2
  *Decisions*): it raises a requirement, adds one to a project or updates a
  project. It makes a pre-approved change (a document, a small tooling change,
  a closure) only where no suitable requirement or project exists, so it takes
  no semver and no dated milestone; it has no delivery-log row either.

## Documentation

- **Look up the industry's word before inventing one, and look inside the
  standard already adopted** (owner, 2026-09-21 and 2026-09-22): ITIL, where it
  has the practice. Take its term and shape, leave ceremony needing more people
  than this has, and say which practice an answer came from (docs/1.2).
- **Before naming anything, read the standard's own list, including its
  supplementary parts, then one neighbouring standard**: C4's *Dynamic* view was
  once reinvented as *Runtime*. A name only this repository knows costs every
  future reader, and *we named it ourselves* is never the reason to keep one.
- **An issue or pull request is named by its number and its title**, as
  `#N *title*`, wherever Claude names one (owner, 2026-11-16):
  - a commit body uses `#N "title"`; a commit subject or pull request title
    stays as it is;
  - another repository's number, and any in the chat, takes its repository:
    `delphside/programme#N`;
  - a project's or work package's title drops its own leading `#N`;
  - a line the tooling reads keeps its parsed form: a `Refs #N` trailer takes
    no title, and a dependency is one line, `**waits on #N** *title*: why` or
    `**is needed by #N** *title*: why`, its repository first where another's;
  - text written before 2026-11-16 takes the form when next edited; records,
    closed issues and posted comments stay as they are.
- **One fact, one home.** The rule lives in its owning document, the argument
  in the issue, and every other mention is a link.
- **Where two documents disagree, or a document and the code, read the commit
  history for how the disagreement came about before resolving it** (owner,
  2026-11-09 and 2026-11-16; the change-a-document skill).
- **Every setting is listed in its application's (3+n).4.1** (owner,
  2026-10-17): deployment settings (addresses, keys, hosts) are environment
  variables, product settings (defaults, rate limits, retention, time limits)
  one code module per area (docs/1.5, docs/1.10).
- **Each numbered document covers one scope**, set by its number, and says what
  is true now with at most a line of reason; history, argument and quotations
  go in the issue or commit (docs/1.5).
- **The documents live; the issues expire** (owner, 2026-09-21). When something
  changes, change the document: never edit a closed issue to agree with it or
  cite one as a rule's authority, though a line added to a closed issue as it
  is superseded is a record.
- **At a process step, consult the owning document.** A process question with
  a choice still open is a `Decision` issue (*The work*), applied to the one
  place that part of the process is documented, then closed. The
  process-definition glossary's D1 to D38 are history, not added to.
- **A change document lives in its parent project's folder**, under its
  application's `3.n.7-changes/` or the programme's `records/2.5-changes/`; a
  work package has none.
- **A report the programme produces on a cadence goes in the records, one file
  per period, in a folder named for the report** (owner, 2026-09-22; docs/1.2
  §2.4):
  - `records/2.4-weekly-digest/` or an application's `3.n.3-capacity-plan/`,
    each file `<OWNER>_<CODE>_<period>.md`, the owner being the application's
    code in records/2.1, or `PRG` programme-wide, and the code the report's;
  - it is neither a numbered nor a change document, and the next one does not
    supersede it;
  - it may be regenerated until the owner has reviewed it (owner, 2026-09-27),
    and is afterwards corrected but never reworked (owner, 2026-10-27).
- **Templates live together in `docs/templates/`, and the numbered document that
  owns the rule links to them** (owner, 2026-09-22): a template carries the
  form and no argument. GitHub's issue and pull request forms stay in
  `.github/`, where it reads them.

## Where the detail is

| For | Read |
| --- | --- |
| the lifecycle | docs/1.2 |
| programme, application and workstreams | docs/1.3 |
| roles and who decides | docs/1.7 |
| the service desk | docs/1.8 |
| the test policy | docs/1.9 |
| how code is built | docs/1.10 |
| activities, the digest, improvement registers | docs/1.4; records/2.7 |
| classifying a change, and routes | docs/1.2 §2.15 |
| artefacts outside git | each application's 3.n.2; docs/1.6 for GitHub's |
| issue fields and the strings tooling reads | docs/1.6 |
| every tool, agents and reviews | docs/1.1 |
| daily state | `scripts/board/`'s `board-inbox.py`, `board-status.py`, `board-actions.py` |
| where a fact belongs | the root README's layout; the change-a-document skill |
| how a document is written | docs/1.5 |
| raising or retitling an issue | the triage skill |
| raising a project or work package | the raise-project skill, loaded first |
