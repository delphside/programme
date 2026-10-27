# The process on one page

This page owns the rules. The numbered documents own the procedures and the
reasons, and issues own the arguments. If this page and a document disagree,
one of them has a defect: fix it, don't work around it.

**A Claude Code session on the web** (claude.ai/code) works without the local
session's memory and outside its git hooks. It answers questions and comments
on issues freely, makes changes only on a branch with a pull request, never by
pushing to `main`. Programme records and change documents go through a pull
request it merges itself once the required checks pass; everything else waits
for the owner's review (docs/1.2 §2.2). Before it finishes it leaves a note for
the local session: a comment on the issue the work concerns, or on the
application's own notes issue, named in its CLAUDE.md, if there is none. The local session reads new comments at its next start.
docs/1.6 records the app it works through.

## The work

- **The rules serve the project; the project does not serve the rules.** The
  owner may set any rule aside when there is a reason. Claude says which rule
  is being set aside, does what he decided, and records it where the work is
  recorded: the issue, the delivery-log row or the commit message. A rule that
  is continually set aside suggests a defect in the rule: consider changing it.
- A change that seems possible takes one or more of four vehicles: a
  pre-approved change where it is already agreed and needs no branch, a
  Requirement issue where what to do about it, if anything, is open or how it
  is grouped or split into projects is not yet decided, a project where it
  certainly needs doing and that is decided, and a note in the next weekly
  digest where it is a lesson for continual improvement (docs/1.2 *Where a
  possible change goes*). Raise it quickly. Discussion happens in the comments;
  the conclusions go in the body, which is edited to stay current.
- **Raise quickly, but into an existing requirement where one covers the area**
  (owner, 2026-09-17). Look first; a new row in a table beats a new number. A
  new issue is right when the subject is genuinely separate, or when the
  existing one has been scoped and widening it would reopen that.
- **A decision belongs on what it decides.** Its own issue only where it spans
  several, or where the argument is long enough to bury the requirement. Either
  way it is a `Decision` issue, and the board indexes them by type.
- **A decision is only worth an issue while there is a choice to discuss**
  (owner, 2026-09-21). An answer that is already settled goes straight to its
  owning document and to this page, with the argument in the commit message —
  no issue, no `D` number, nothing to close later. The test is whether anybody
  still has to be convinced.
- **Whether to do something is a Requirement; how to do it is a Decision.**
  Owner, 2026-09-27. A requirement can be rejected or folded into a project,
  so an idea not yet agreed is raised as one, not as a Decision.
- **A settled decision is never maintained; the document carrying it is** —
  the general rule under *Documentation*, applied to decisions.
- **Options live in the body, numbered, each saying what it constrains**, so one
  issue can be read and settled rather than assembled from a thread (owner).
- Make a tooling change when something first needs it, not when it occurs to
  you. The requirement is still raised; the doing waits for the need.
- **A change the weekly review proposes is a fix or an improvement** — owner,
  2026-10-27. A fix cites what went wrong and what it cost him, and goes ahead
  as BAU or a project as its type decides; an improvement makes something that
  works better, and waits for him to pick it at the monthly
  `improvement-review` (docs/1.4). A mistake is left to review the first time;
  once it recurs it is a candidate for an automatic check.
- Claude sweeps, the owner reacts. Claude looks across every open item and
  identifies what can be progressed; the owner should not have to scan the
  board to find work waiting on him. So anything genuinely needing him is
  brought to him, and everything else is Claude's to find and move.
- Triage is done jointly with the owner, never alone, and Claude leads it:
  bring the reading and the proposal, then agree it. **Except in Process
  Definition, Programme Tooling and each application's Delivery Tooling, and for type `tooling` or `documentation` in
  any workstream, where Claude triages alone** — D54, 2026-09-17. Anything
  reaching production, the product and its rules, and anything irreversible
  outside git still come to the owner whatever their workstream. Minimum: clear short
  description, workstream, priority, type of change. Then scope (options,
  dependencies, effort), then project planning. Outcomes: solo project,
  grouped project, straight to main, on hold, cancelled.
- **Related change goes in one project, so it is designed once** (owner,
  2026-09-21), and as little design as possible is coordinated across projects.
  A different route is not a reason to split a project — it is a reason to split
  a delivery, which is what a work package already is. Two projects are right
  where deciding one does not constrain the other, and then a link under
  *Dependencies and related work* is enough.
- **The exception is a shared mechanism**, which is owned by one workstream and
  designed to by the others — owner, 2026-09-21. It gets a delivery project of
  its own, treating every use case as a customer feeding requirements for the
  generic thing; each workstream then builds its own functionality on top. The
  test is whether it would exist for only one caller. If it would, it belongs
  to that caller's project. docs/1.3 says how a mechanism's owning
  workstream is chosen.
- **A mechanism ships in the same release as its first customers**, so it is
  tested against a real requirement rather than only against its own tests —
  owner, 2026-09-21. Scoped and designed independently, scheduled jointly: its
  milestone is the one its first callers carry.
- A project owns its requirements: sources are folded and closed. Its issue
  carries seven headings: requirements, design, **non-functional design**, test
  approach, dependencies and related work, deliveries (each delivery's
  artefacts by route, then its steps), post-deployment checks against
  requirements. Under each heading is the content or a link to the design
  document that holds it, never both.
- **Non-functional design is four questions and *none, because…* answers any of
  them**: capacity, failure, limits and timeouts, secrets and access. Asked
  per change they are cheap; a project is the expensive way to answer them
  later. A limit's answer says **where its number came from**.
- **A dependency is declared from both ends.** `waits on` has an inverse,
  `is needed by`, so a relation lives in both bodies rather than in whichever was
  written second. The edge is also a GitHub dependency link, which the
  generated context header shows and `board-check.py` checks.
- A project moves through the Project State field. The wording is the field's own
  stage descriptions:

  | phase | done when |
  | --- | --- |
  | Scope | What the project does. Technical option chosen where it affects dependencies. |
  | Q3, Q2, Q1 | The queue. Q1 is next off the blocks. |
  | Design and Test Approach | Design option chosen. Design completed. Test Approach defined. |
  | Development | Being built on its project delivery branch |
  | User testing | On Preview for user functional testing. On Rehearsal for technical testing. Where the application has them: its profile (`3.n.6`) says which environments it has. |
  | Deployment | Image: Prev->Reh->Prod. Repo-only: merge. Non-repo: by hand. |
  | Post-deployment | Check it is working and giving the benefit expected. |
  | Project Closedown | Lessons learnt completed. |

  The post-deployment check has one row per requirement.
- **A problem found in testing is fixed on the branch, and the branch is
  retested.** One found after the merge either reopens the package (a new
  branch, back to Development, tested again) or goes in a later package. A
  merge moves a Production Release package to Deployment and a tooling-route
  one to Post-deployment; docs/1.2 §2.1 has why. Owner, 2026-09-26.
- **A work package is at most one delivery, and so one route.** A delivery may
  carry several packages; a package never spans two deliveries. Building a tool
  and running it are two deliveries with different routes, so two packages
  (delphside/tile-lite-elite#404 and delphside/tile-lite-elite#422). Owner, 2026-09-27.

## Changes

- A Production Release always takes a branch, a pull request, a semver
  milestone and a row in the delivery log. The pull request is what gives the
  review its mechanics, and a release commit that reaches main *unproven*
  cannot be guaranteed to work and blocks every other release until it does,
  because main is what gets deployed.
- **Proven and unshipped is different, and is the normal state.** A release
  change merges to main once preview, user testing and rehearsal (where the
  application has them) have passed against its branch tip; shipping may follow immediately or later. So main is
  the accumulating next release, and a release branch is for a release that
  must stabilise while main moves on, not for one delivery. D55. The condition
  that makes this safe lives in the emergency path: cut an emergency from the
  last released tag, never from main.
- Otherwise the route decides (docs/1.2 §2.2). Application Tooling takes a
  branch, because main is where it runs; Docs and Programme Tooling commits
  straight to main, which is what pre-approved means. A document change takes
  no branch unless it is large enough to be given Application Tooling: a
  document branch lives too long, main moves, and the review does not happen.
  A cloud session's branch and pull request are incidental to the route. One
  branch per project, and everything the project touches goes on it, its
  technical documentation included. Programme documents, generic assets and
  records alike (docs/1.3; the list is `programme/scripts/board/documents.py`'s),
  belong to no project and change on main.
- A pull request is what gives a review mechanics: a diff, a place to comment,
  a recorded approval, a merge that waits for a tick. Pre-approved does not mean
  unreviewed — it means the discussion was the review, which is enough where a
  change is cheap to reverse and is not, for the image.
- The pull request body is the review surface. **It says which part of the
  project's scope is being requested, and what is deliberately left out** —
  owner, 2026-09-17. It does not duplicate the project body or the documents:
  the argument, the measurements and the design live on the issue, and a body
  that restates them makes the reviewer read the same thing twice to find the
  one paragraph that is new. Add the owner as reviewer at creation. He ticks and
  approves, Claude merges by rebase and fast-forward.
- A review comes back two ways and they return differently. **Approved with
  comments** stays approved: make the changes and merge. **Changes requested**
  does not: make the changes, then re-request the review, which is what puts it
  back to awaiting review rather than leaving it sitting as answered. The board
  reads both from `reviewDecision`, so skipping the re-request leaves it in the
  wrong column and waiting on nobody.
- Commits and pull requests say `Refs #N`, never `Closes #N`: no merge closes
  an issue, because even a change that never leaves the repository enters
  Post-deployment at its merge. Each repository has GitHub's auto-close
  setting off (docs/1.6); the deploy settles its milestone, and anything else
  is closed by hand (owner, 2026-10-26). Programme BAU work needs no issue: its commits say
  `Activity: <id>` from docs/1.4's register, and `Initiative: <id>` where there
  is one. BAU is its own triage, so a change that would benefit from a
  project's controls, which docs/1.4's table decides by type of change, or one
  to an asset BAU does not own, becomes a project, never a requirement. Every
  subject starts with the application's stamp and a space; each application's
  CLAUDE.md says what its stamp is.
- Push immediately after committing. Until pushed, a change does not exist.
  Run an unpushed script to test it, never to use it.

## Deliveries and releases

- A **delivery** is a change reaching its users — any update to a programme
  asset, documents included. **Every change has one**, because it has to reach
  main. A **release** is a new version of the application, delivered to
  production with a new semver.
- **Not every delivery has a milestone.** A change applied straight to main is
  not assumed to be a single point in time, so it has no place in the sequence
  the milestones are: no branch, no pull request, no milestone, no
  delivery-log row. Its record is the commit, which references the requirement
  or project it serves — possibly more than one.
- **A milestone marks a delivery made at one point in time**, and places it in
  the sequence: the release semver where it includes a release, otherwise
  **production's current version** with a letter appended, or for host
  maintenance a date. Production's, not the development version, because the
  development version is intent and can change, and a letter pinned to it can
  name a release that is never made.
- `Route` belongs to the **artefact**, and **a delivery has one route**. Work
  touching artefacts with different routes is split into a delivery per route,
  each taking the shape its own route needs. A project might deliver its script
  changes first, then a configuration change applied in the console, then the
  application — three deliveries, three routes, one project.
- **Each of those deliveries is a work package, so each is tracked**, and the
  route lives where the delivery does: the parent carries no `Route`.
- **Documentation riding on a release is a pre-approved add-on.** A release that
  also touches documents stays one delivery with one semver milestone: the
  documents need no letter milestone, no second pull request and no row of their
  own. They are on the project branch already, reviewed in the same diff, and
  live when the release is. A document carried along does not make a second
  delivery.
- So there are two shapes: straight to main, recorded by its commits; or held
  back on a branch, which then owes a pull request, a milestone and a row in
  the delivery log. The branch is what makes a delivery a point in time; the
  milestone is what places that point in the sequence.
- **A Requirement never carries a milestone.** A requirement is a statement
  that something should be true; it delivers either by folding into a project,
  and then the project's work package carries the milestone, or straight to
  `main` as pre-approved, with none. A milestone on a requirement means a
  delivery happened with no work package to own it. An application's deploy
  script can warn about this.
- **Milestones are only semvers, letters and dates** — owner, 2026-10-26.
  `pre-approved`, `no-release`, `patch`, `minor` and `major` are retired;
  `Route`, `Type of change` and the requirement and project states carry their
  meaning (docs/1.2 §2.15).
- **A routine update owes what its route owes, and nothing more.** A
  `Production Release` bump (a base image, a dependency, the toolchain) reaches
  `main` by pull request, so CI is its regression check, and waits for the next
  release, whose regression testing is the last one; it never justifies a
  release of its own. Every update is tested for what it changes, on preview and
  rehearsal (where the application has them) at the branch tip where only a
  deployed stack can show it. A new toolchain or major version gets a look at
  its new features; anything that might be worth considering is raised as a
  requirement, which judges it. Host maintenance (a host package, the container
  runtime, a kernel, a reboot, hand-set host configuration) has no release to
  ride, so it is the infrastructure application's delivery: a work package and a
  row in its delivery log, numbered by date. What an application installs on its
  host (its scripts, systemd units and the packages it needs) is its release.
  `docs/1.2` §2.2.1 is the table, and §2.15 the rule.
- **Who drove the change decides the ceremony, not how big the diff is.** A
  routine dependency bump raised by tooling takes none: a Dependabot pull
  request has no project, no milestone and no delivery-log row, and its commit
  message is the record (owner). A host or dependency change **we** decide on
  and carry out is the other case — the kernel and package work of 2026-09-19 —
  and it takes the project, a milestone (a date for host maintenance) and a row.
- **A change to one of our own assets that reaches the image takes a new
  semver**, not a letter: each application's artefact register (`3.n.2`) lists
  them, and changing one is a Production Release. The letter form is for a
  delivery that ships **no** application code at all — a console change, a
  drill; host maintenance is numbered by date instead.
- **Every delivery is one or more work packages**, each carried by a sub-project
  or by the parent. Work packages sharing a milestone are delivered together,
  and that grouping has no issue of its own — the milestone is what identifies
  it. A parent lists what it delivers, each row naming the work packages that
  share a milestone or saying straight to main. The four cases are in docs/1.2
  §1.1.
- **A project that is one package is its own work package; otherwise every
  package in a milestoned delivery has a sub-project**, which shows it on the
  board and gives its tests a home of their own. A delivery with no milestone
  may have one to carry its own steps, tests or checks; docs/1.2 has the
  table.
- A work package is titled `#N WP A Del 1 of 2: what it delivers`, a parent
  `#N MAIN PROJECT: what it is`. `pt P of Q` is added only where a delivery
  carries more than one package, and the packages of one change split by route,
  developed and tested together, may share a letter: `WP A1`, `WP A2`. The
  counts go stale and are kept anyway: a title saying `Del 1 of 2` is wrong
  loudly where `Del 1` is silently incomplete. They are derivable from the
  milestones; nothing checks them yet.
- The parent owns the requirements, the design and the documents; a work package
  links to them and carries its own artefacts, test approach and post-deployment
  checks, because a check is answered per delivery. A parent with sub-projects
  (a parent with none is the work package) needs no milestone and no Route: it
  has no delivery role, and both answer how a change reaches its users. A
  milestone may still be set — a target release, say — and is then ignored:
  making the release leaves the parent out of the record, so no deploy settles
  it. A Route may not: `board-check.py` reports one on a parent, because in
  delphside/tile-lite-elite#297 parents were given routes to silence a report
  that had asked for the wrong thing.
- The parent runs Scope, the queue, and Design and Test Approach, then stops —
  oversight is a design role. It may reach Post-deployment for a requirement no
  single delivery satisfies, and Project Closedown to close. A work package may
  delegate lessons learnt to the parent, and says so.
- **A release is made once, at the end of regression; deploying it is
  choosing a version.** Making the release, once the owner judges rehearsal
  passed, checks the milestone, writes the release record, tags the version and
  bumps `main` to the next patch; the deploy checks only the record, the schema
  and a smoke test. docs/1.2 *Making a release, then deploying it* has the
  steps.
- A release milestone is a shipping list: move out what is not shipping before
  the release is made (docs/1.2 §2.5).
- An issue whose change went straight to main has no milestone, and is
  closed by hand; no deploy settles it.
- After deploying, run the application's verification and trust exit status,
  not read output. Each application's CLAUDE.md names its script and says
  what a deploy does.
- **Production access is the owner's to run**, reads included: an admin
  listing, a database query, a log dump. Ask him for it, he runs it, Claude
  works from what comes back (owner, 2026-09-21). The exception is the
  scripted checks an application's tooling already makes, which are bounded
  and reviewed; its CLAUDE.md names them.

## Tests, checks and decisions

- **Reading jobs with a defined file set, and a work package's change, go to an
  agent; triage, decisions and anything touching production stay with Claude.**
  Each agent runs on the model its file sets, and a review runs in rounds until
  one finds no material issue — owner, 2026-10-14. docs/1.1 has which model, how
  a round runs and what makes a good agent task. A document change is reviewed
  by `document-reviewer-reader` and `document-reviewer-truth`, against
  docs/1.5's house style, and a pull request carrying code by `change-reviewer`,
  whoever wrote the code; a pull request a bot opened owes no review rounds.
- Test conditions derive from stated rules, not from the code. Each
  application's rules are stated in its own documents, and the programme
  tooling's in the programme's numbered documents.
- A gate refuses and work stops; a check reports and a person decides. A new
  check is shown to fail before it ships.
- **Every checkbox names whose move it is**: `- [ ] **owner** — run the six
  browser tests`, or `- [ ] **Claude** — write the regression tests`. The label
  is on the box, not inferred from its heading, so a box keeps its owner when
  it moves and a reader sees whose it is without scrolling up. An unlabelled
  box is waiting on nobody, and `board-check.py` reports it.
- A decision is applied in the same commit that marks it answered, or an
  issue is raised and named in the decision.
- **A project answers its decisions in order**: document structure, then
  functional requirements, then technical decisions, delivery planning last.
  docs/1.2 *Decisions* has why.
- **A project's decisions are logged by link**: closed once applied, cited in a
  footnote where the design states the conclusion, and listed in a Decisions
  table in the project's body (owner, 2026-09-29). docs/1.2 has the detail.
- A decision is not a change vehicle. It routes work: raise a requirement, add
  one to a project, update a project or the documents, or close something. It
  may make a pre-approved change only where no suitable requirement or project
  exists. So it takes no semver and no letter milestone, and no delivery-log
  row.

## Documentation

- **Look up the industry's word before inventing one, and look inside the
  standard you have already adopted** (owner, 2026-09-21 and 2026-09-22): ITIL,
  where it has the practice. Take the term and the shape of the practice, leave
  the ceremony that needs more people than this has, and say which practice an
  answer came from. docs/1.2 has the mapping tables.
- **The first rule did not stop it, so here is the test.** On 2026-09-22, in the
  commit adopting C4, I invented a view called *Runtime* that C4 already has as
  *Dynamic*, and labelled a Deployment diagram as a Container one. Before naming
  anything: **read the standard's own list, including its supplementary parts**,
  then look at one neighbouring standard. A name only this repository knows is a
  cost paid by every future reader, and *we named it ourselves* is never the
  reason to keep one.
- One fact, one home. The rule lives in its owning document, the argument in
  the issue, and every other mention is a link.
- **Every setting is listed in the application's (3+n).4.1.** Deployment
  settings (addresses, keys, hosts) are environment variables; product
  settings (defaults, rate limits, retention, time limits) are one code module
  per area. Owner, 2026-10-17; docs/1.5 has the rule.
- **Each numbered document covers one scope**, set by its number (docs/1.5
  owns the scheme). A document says what is true now with at most a
  line of reason. History, argument and quotations go in the issue or the
  commit. docs/1.5 has the detail.
- **The documents live; the issues expire** (owner, 2026-09-21). A `docs/N.N`
  file answers what is true now and is edited whenever that changes. An issue
  answers what was argued and when, and once it closes that is all it answers.
  So when something changes, change the document — do not edit a closed issue to
  agree with it, and do not cite one as the authority for a rule. A line added
  to a closed issue at the moment it is superseded is a record; editing one to
  keep it true is the thing to avoid.
- At a process step, consult the owning document. A process question with a
  choice still open is a **`Decision` issue** — the GitHub issue type, carrying
  `Decision State` and an `Agreed Decision` heading that `board-check.py`
  reads — and is applied to the one place that part of the process is
  documented, then closed. A process answer that is already settled skips the
  issue and goes straight to that document and this page. The
  process-definition glossary holds D1 to D38 and is history: it predates the
  issue type and is not added to.
- A change document lives in its issue's folder under its application's
  `3.n.7-changes/`, or under `records/2.5-changes/` for the programme's own,
  named for the parent project — a work package has no folder of its own.
- **A report the programme produces on a cadence goes in the records, in a folder
  named for the report (`records/2.4-weekly-digest/`, each application's
  `3.n.3-capacity-plan/`), one file per period, named `<OWNER>_<CODE>_<period>.md`, where the owner's code is the application's in
  records/2.1, or `PRG` for a programme-wide report.** Owner, 2026-09-22 —
  the name has to mean something once it has left the folder. It is neither a numbered document
  nor a change document: it records what was true at a moment, may be
  regenerated until the owner has reviewed it (owner, 2026-09-27), and
  afterwards is corrected but never reworked: a broken link or a wrong value is
  fixed, and the content is not kept open (owner, 2026-10-27). It is not
  superseded by the next one — the series is what carries the meaning.
- **Templates live together in `docs/templates/`, and the numbered document that
  owns the rule links to them** (owner, 2026-09-22). The document owns the rule
  and carries the reasoning; the template carries the form and no argument. A
  new template owes that link, or nobody finds it at the moment they need it.
  The forms GitHub offers when an issue or pull request is opened stay in
  `.github/`, because GitHub reads them only there.

## Where the detail is

| for | read |
| --- | --- |
| the lifecycle in full, and why | docs/1.2 |
| programme and application, and the workstreams and what each owns | docs/1.3 |
| roles, who decides, and each role's reading list | docs/1.7 |
| the service desk: how a Ticket arrives, is answered and closed | docs/1.8 |
| the test strategy, and the standards every test is held to | docs/1.9 |
| the recurring activities, what the weekly digest reports and the improvement registers | docs/1.4 |
| every tool, and how it is run | docs/1.1 |
| every field a change is classified by, and each artefact's route | docs/1.2 §2.15 |
| artefacts outside git | each application's artefact register (3.n.2), and docs/1.6 for GitHub's |
| the fields each issue carries, and the strings tooling matches | docs/1.6 |
| agents: which work, which model, how a review runs | docs/1.1 *Claude's tooling* |
| daily state | programme/scripts/board/board-inbox.py, programme/scripts/board/board-status.py, programme/scripts/board/board-actions.py |
| where a fact belongs, before writing it | the layout in the root README, and the change-a-document skill |
| how a document is written, and what it may hold | docs/1.5 |
| raising or retitling any issue | the triage skill |
| raising a project or work package: load it before creating the issue | the raise-project skill |
