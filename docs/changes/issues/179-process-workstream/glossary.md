# Glossary: our terms, the industry's, and the process changes they carry

**What this document is for.** Owner, 2026-08-19: *"The glossary has become a
home for candidate changes to process and language of process. After review and
discussion it should state the decisions which can then be used to update doc
3.3 (and any other affected documents)."*

So it has three states, and every section is in one of them:

| state | means |
| --- | --- |
| **candidate** | proposed here, not agreed. Argue with it |
| **decided** | agreed, and not yet in the numbered documents. **This is the work list** for updating `docs/3.3` and its neighbours |
| **applied** | in the numbered documents, and the entry here can go |

A term or a rule leaves this document once it is applied — the numbered
documents are the record, and a second copy here would be the one that goes
stale.

**A new term is used from the moment it is agreed; the sweep waits for
approval.** Owner, 2026-08-19: *"it's okay to change the language now, I just
don't want to cause confusion by having you look for changes now when we can
wait."*

So the two halves separate:

- **new writing uses the new word immediately** — an issue, a commit message, a
  paragraph being edited anyway. There is no value in writing *chunk* in the
  morning because the sweep happens in the afternoon
- **the pass over existing documents waits** for this document to be approved,
  and then happens once. Hunting the old word through the repository while the
  list is still moving costs attention twice and risks a half-applied rename,
  which is worse than either end of it

The point was never renaming for its own sake. It is that a reader who knows the
standard term can map what we do onto what they already know and read further,
and that `docs/3.x` is meant to be portable to a second project, where our
private vocabulary would travel badly.

Three possible outcomes per term: **adopt** it, **keep ours** and say why, or
**use both** — the standard term once so it is findable, ours thereafter.

## Where each part stands

| section | state | lands in |
| --- | --- | --- |
| [The four levels](#the-four-levels-and-what-each-is-called) | **decided** | `docs/3.3`, the change lifecycle |
| [Project phases](#project-phases) | **decided**, except the last | `docs/3.3`, and the `phase:` labels already exist |
| [Capability workstreams](#capability-workstreams) | **candidate** — the list is agreed, the adoption is not started | `docs/3.3`, and a parent issue or label per workstream |
| [Categorising changes and releases](#categorising-changes-and-releases-three-attributes-not-one-lane) | **candidate** — #154 | `docs/3.3`'s lane table, and new labels or an issue form |
| [How ITIL handles tooling](#how-itil-handles-tooling-monitoring-and-instrumentation) | **decided** as reasoning; changes nothing on its own | the notes behind the lane rule |
| [How the process is managed](#how-the-process-is-managed-github-folders-scripts) | **decided** — the inventory of what we use | a new section in `docs/3.3`; script rows in `docs/3.0` |
| Individual terms below | **candidate**, except *parent issue* | wherever the term is used |
| *parent issue* | **applied** 2026-08-19 | `docs/3.3` — PR #185 |

---

## Where the standard term is simply better

### release branch · release train

**Standard**: a branch cut for a release, with scope frozen at the cut; changes
merge into it, and it ships. A *train* is the scheduling variant — it departs on
time and unready features get off.

**Ours**: "version branch", "version-named branch".

**Recommend: adopt.** "Release branch" is universal and ours adds nothing. The
train metaphor is worth adopting too, because it names the de-scoping rule we do
not yet have (#135): the train leaves, the feature waits for the next one.

### hermetic build

**Standard**: a build that depends only on declared inputs, so it can be
reproduced from source control alone.

**Ours**: "fresh-checkout principle" — deploys build a throwaway `git worktree`
at the target commit, never the working tree.

**Recommend: use both.** "Hermetic" is the findable term; our phrase says what we
actually do, which is narrower and clearer. Lead with hermetic, keep the
worktree sentence.

### expand/contract  (also: parallel change)

**Standard**: schema changes made in two deployable steps so the old and new
code both work against the intermediate state.

**Ours**: unnamed — we describe migrations running as their own step before the
container swap.

**Recommend: adopt.** We have the practice and no word for it, which makes it
hard to reason about. Worth noting we currently do the *sequencing* half but not
the two-phase half — naming it makes that gap visible.

### build metadata

**Standard**: semver §10 — the `+<anything>` suffix, ignored in precedence.

**Ours**: "the `+sha`", "build id".

**Recommend: adopt** for the version-number discussion, where the precedence
rule matters. "Build id" is fine everywhere else.

### parent issue  ·  sub-issue

**Standard**: GitHub's own vocabulary for the feature — a *parent issue* with
*sub-issues*, with progress rolled up automatically.

**Ours**: `docs/3.3` says **master issue**; conversation on 2026-08-19 used
**lead issue**.

**Recommend: adopt**, decided 2026-08-19. Using the tool's own word means the
document, the API and the UI all say the same thing, and it retires "master".
Owes one edit to 3.3's *Where a document lives*.

### blast radius

**Standard**: how much breaks, and how visibly, if a change is wrong.

**Ours**: unnamed until 2026-08-15, when it went into `docs/3.4` as "grade by
blast radius, not by category".

**Recommend: adopt.** Already done.

---

## Where ours is better, and should stay

### rehearsal  (vs staging)

**Standard**: *staging* — an environment resembling production, used before
release.

**Ours**: *rehearsal* — a production clone whose purpose is to prove the release
**mechanism** and to run anything needing production-like hardware.

**Recommend: keep ours, mention staging once.** "Staging" carries expectations we
deliberately do not meet: it is usually a permanent production mirror, and the
standing criticism of staging (Charity Majors: mirroring production is a fool's
errand) lands on that version and not on ours. Our word says what it is *for*,
which is the distinction that makes the preview/rehearsal split work. Say
"rehearsal (a staging environment, but see below)" once, then use ours.

### ~~lane~~ → three attributes

**Superseded** by [Categorising changes and
releases](#categorising-changes-and-releases-three-attributes-not-one-lane)
below. The short version: `merge`, `fasttrack`, `minor`, `major` and
`emergency` are one word answering three different questions, which is why
mapping a real change onto the list takes an argument every time.

### living document · standing issue

**Standard**: none in common use.

**Recommend: keep ours.** Coined here, defined in 3.3, and doing real work.

### preview

**Standard**: "preview environment" / "review app" — close enough to be the same
thing, though usually per-branch and ephemeral where ours is one shared local
stack.

**Recommend: keep ours**, and note the difference: ours is not per-branch.

---

## Where the standard term names something we do not do

Worth naming anyway, because a considered rejection needs somewhere to live —
and 3.3's convention of "say what we do, not what we rejected" currently leaves
these looking like oversights.

| term | what it is | our position |
| --- | --- | --- |
| **canary release** | ship to a fraction of traffic first | not done — needs parallel infrastructure we do not have; automatic rollback on smoke-test failure is the substitute |
| **blue/green** | two production environments, switch between | same |
| **feature flag** | merge continuously, ship dark, flip when ready | not done, and the whole "when to merge, what to hold back" section is solving the problem flags solve. Defensible for one developer; the *absence of the word* is not |
| **artifact promotion** | build once, promote the same artifact through environments | **#134** — we currently rebuild, so rehearsal proves *a* build and production ships another |
| **SLSA provenance** | binding an artifact digest to a source revision | the formal version of #134; worth citing there |
| **trunk-based development** | short-lived branches off a trunk that is always releasable | mostly what we do; our release branches are TBD's "branch for release", explicitly *not* GitFlow's permanent `develop` |
| **dev/prod parity** | 12-factor X — keep environments similar | why preview keeps its volume, so migrations meet a non-empty database |
| **change enablement** | ITIL — normal / standard / emergency changes, with post-implementation review | we have the decision points exactly, under our own words — see [Categorising changes and releases](#categorising-changes-and-releases-three-attributes-not-one-lane) |
| **quality gate** | an automated check that blocks progress | our "gate" — same word, already aligned |

---

## The four levels, and what each is called

Definitions only — where these live in GitHub is a separate question, settled
on issue #179. Checked against MSP and PRINCE2, and against a second opinion
asked the same question.

| level | ours | the industry's | definition |
| --- | --- | --- | --- |
| the whole thing | **programme** | evergreen programme · continuous value stream | the application and its support: unbounded scope, no end date |
| an area of it | **workstream** | functional or capability workstream | one capability, worked on indefinitely — the game model, the process, production operations |
| a bounded piece | **project** | project | *a temporary endeavour undertaken to create a unique product or result* — fixed scope, ends when the scope is complete |
| a unit of build | **work package** | work package (PRINCE2, WBS) | one development unit within a project: "the client changes for #71". We said *chunk* until 2026-08-19 |
| what ships | **release** | release | one or more changes built, tested and deployed together |

**A workstream is a capability area, not a bag of related changes.** That is the
sharper definition, and it gives a test: two pieces of work belong in the same
workstream when they touch the same capability, not when they merely arrived in
the same week.

**A release may stand outside a project.** A fasttrack patch is a release with no
project behind it, and a merge-lane change is live with no release at all. A
model that implied otherwise would send documentation and tooling looking for a
project they will never have.

### Two terms offered and declined

**Release train.** The train is specifically the *scheduled* variant: it departs
on time and unready features get off. We release when a scope is ready, so the
word would promise a cadence we do not run. Adopt *release branch*; keep the
train metaphor for the de-scoping rule (#135), which is the narrower claim.

**Epic**, for a project. An epic is not time-bound and has no fixed scope, which
is the one property that makes a project a project.

---

## Project phases

**Decided 2026-08-19**, except where marked. A phase belongs to a **project**, not
to a workstream: a workstream has no end, and a project is the thing that passes
through phases and stops.

Five, and the first covers two activities rather than being split into two
phases — owner: *"scoping and design are done in the same phase for us."*

| phase | the question | its artefact | it ends when |
| --- | --- | --- | --- |
| **scope and design** | what is in, and how will it be done? | the **issue body** fixes the scope; the **design note** carries the design | both are agreed — in practice one review |
| **development** | is it built? | **work packages**: branches, pull requests, merges | the last work package in scope is merged |
| **user testing** | does it do what was wanted? | the **project's** testing documents, in a folder named for its main release | somebody decides it does — **or the scope changes**, which sends it back |
| **deployment** | is it live? | the **release**: milestone, `prod-` tag, smoke test | `deploy.sh` exits 0 |
| **post-deployment** | did it do what it was for? | a **review** — *not built* | the project closes |

**Recorded as a `phase:` label** on the project's issue, hand-set. The
interesting boundaries are judgements — *"user testing is finished"* is not
visible to a script — and a phase changes a handful of times per project, which
is when hand-set state does not drift. A label rather than a body line, because
a label is filterable where the work is done.

### Where the gates are, and why there are only three

The classic five gates map onto the phases, and two of them are already machines:

| gate | attaches to | who answers |
| --- | --- | --- |
| scope agreed · design agreed | the project | a person, and it needs no ceremony beyond the review we already run |
| **build review** | each release | **CI** — fmt, clippy, tests, wasm, the stamp, e2e |
| **go-live readiness** | each release | **the deploy gates** — preview and rehearsal on the exact commit, the schema check, the snapshot, automatic rollback |
| **post-implementation** | the project, at close | a person — **and we do not have it** |

A gate with an objective answer belongs in a script; the ones left for a person
are the ones without. That is the same test the lane discussion arrived at.

### The decision points still open

1. **The post-implementation review.** Nothing asks whether a normal release did
   what it was for — only an emergency gets a retrospective, raised by
   `deploy.sh` itself. #67 is the case: closed by a milestone, listed as
   deferred in the testing report, and genuinely broken. **Candidate**, and it
   needs an issue of its own.
2. **Whether phases apply to a project only**, or also to a work package. Today a work package
   inherits its project's phase and carries no label. Untested, because we have
   no project layer in GitHub yet.
3. **Inserting the project layer.** #71's work packages and #179's children hang
   directly off a workstream, with no project between. The vocabulary is decided;
   the restructuring is not done.

---

## Categorising changes and releases: three attributes, not one lane

Moved here from #154 on the owner's instruction, 2026-08-19, because it is a
question about **words** before it is a question about process.

### What the industry separates

ITIL keeps three things apart that our one lane word runs together:

| | categorises by | values |
| --- | --- | --- |
| **change type** | how it is **authorised** | standard (pre-approved, repeatable, no per-instance authorisation) · normal (assessed and scheduled) · emergency (expedited) |
| **release type** | what the release **contains** | major · minor · emergency |
| **release vs deployment** | *deployment* moves components into an environment; *release* makes function available to users | two separate practices in ITIL 4 |

That third row is the one worth internalising: they are deliberately not the
same event, which is also the entire basis of feature flags in the CD
literature — deploy dark, release later.

**A naming caution.** ITIL already uses *dimensions* for something else — the
[four dimensions of service
management](https://itsm.tools/itil-4-explained/) — so ours should be called
**attributes** or **axes**, never dimensions, or a reader who knows ITIL will
expect organisations-and-people, information-and-technology, partners, and value
streams.

### What our lane word is actually saying

| our lane | the question it answers | ITIL axis |
| --- | --- | --- |
| **merge** | it never travels the deploy path | deployment |
| **config-only** (unnamed today) | it changes production with no artifact | deployment |
| **fasttrack** | it ships alone, as a patch | release |
| **minor** / **major** | it is grouped into a release of that size | release |
| **emergency** | authorisation is expedited | change type |

`emergency` is not the same *kind* of thing as `minor`, and `merge` is not the
same kind of thing as `fasttrack`.

### The proposal

Three attributes on an issue, replacing the single lane:

| attribute | values | answers |
| --- | --- | --- |
| **type** (already have it) | the seven labels | what it is, and what evidence it owes |
| **route** | *in the artifact* · *carried by the deploy* · *applied on the host* · *never leaves the repo* | does it reach production, and how |
| **release** | patch (alone) · minor · major · none | what carries it to users, and which milestone closes it |

Authorisation then falls out without a label of its own, landing on ITIL's three
change types exactly: *never leaves the repo* is a **standard change** — live on
merge, pre-authorised by a documented procedure; anything in the artifact or
carried by the deploy is a **normal change**; and the emergency deploy is an
**emergency change**, orthogonal to both other attributes.

## How the three attributes settle the cases that were hard

The cases are #154's, plus the ones this week produced. Every row was previously
an argument.

| case | type | route | release |
| --- | --- | --- | --- |
| `deploy.sh`, `rollback.sh`, `verify.sh` | prod-tooling | never leaves the repo | none — live at merge |
| `.github/workflows/`, `e2e/`, `scripts/tests/` | non-prod-tooling | never leaves the repo | none |
| `Caddyfile.preview` | non-prod-tooling | never leaves the repo | none |
| documentation, including `docs/3.4` about production | documentation | never leaves the repo | none |
| client/server code, `Caddyfile`, the admin CLI | app | in the artifact | with a release |
| **migrations** | app | in the artifact, and they change production data irreversibly | with a release |
| dev-only client code (#130) | minor-function | in the artifact | with a release |
| **instrumentation** — JSON logs, metrics (#174) | minor-function | in the artifact | with a release |
| `docker-compose.yml` | prod-tooling | carried by the deploy | with a release |
| the `sa` alias `deploy.sh` writes on the VM | prod-tooling | carried by the deploy | with a release |
| **journald retention drop-in** (#174) | prod-tooling | applied on the host | none — document it, close by hand |
| **OCI alarms** (#136), rehearsal DNS (#147) | prod-tooling | applied on the host | none — same |
| `.env` on the VM | prod-tooling | applied on the host | none — same |
| **the backup job** (#175) | prod-tooling | applied on the host, from a script in the repo | none, unless it ships in the image |

The two rows that used to have no answer at all — config-only and
tooling-installed-by-the-deploy — now have one by construction rather than by
adjudication.

## How ITIL handles tooling, monitoring and instrumentation

The owner's question, 2026-08-19. ITIL's answer is not a special case for
tooling; it is that **the categories were never about "app versus tooling" in
the first place.**

**1. Everything under change control is a configuration item.** ITIL's unit is
the CI, and change enablement depends on service configuration management
knowing what the CIs are and how they relate — without it, assessing risk is
guesswork. A monitoring rule, a deploy script and a game server are all CIs. The
question is never "is this tooling?" but **which service's CIs does this change,
and what is the risk to that service?**

**2. Tooling is an internal service, with the delivery team as its consumer.**
ITIL 4 distinguishes internal from external services. The game is the external
service; the deployment pipeline, the preview stack and the test suite are
internal ones whose only consumer is us. The same machinery applies at both
levels — which is exactly what our merge lane is: **releasing an internal
service to its only consumer**, and why "live at merge" is literally true rather
than a shortcut.

**3. Monitoring has its own practice, and monitoring config is its CIs.**
[Monitoring and event
management](https://purplegriffon.com/blog/monitoring-and-event-management-itil)
is a practice in its own right, defining an event as *"any change of state that
has significance for the management of a service or other configuration item"*.
So an OCI alarm is a CI of the **monitoring** service, not of the game.
Changing it changes what we can see, not what users get — which is precisely why
it has no artifact and no release, and why it still needs writing down.

**4. Instrumenting the application is a change to the application.** Adding
structured logging to the server changes the game's own CI and ships in its
image, so it takes the external service's full path — even though its *purpose*
is internal. That is the reason #174's JSON logging is typed `minor-function`
rather than `prod-tooling`, and the reason our "does it reach production through
a deploy?" test gives the right answer there without anyone having to argue about
intent.

**5. Deployment tooling sits under deployment management, not release
management.** The split in ITIL 4 puts the mechanism of moving components
(deployment) in a different practice from making function available (release).
Our `deploy.sh` is deployment-management tooling, and changing it changes the
internal service that performs deployments — so it is a normal change to *that*
service and a standard change from the game's point of view. Both statements are
true at once, and the confusion in #154 came from having one word that forced a
single answer.

### The criteria inform the judgement; the judgement decides

**Decided 2026-08-19.** Owner: *"there are lots of framings which might apply in
different circumstances. Perhaps an important one is that we can make the
decision we think is right, even if the documented criteria don't tell us to do
that."*

Five framings were produced for the lane question in one day — the artifact test,
the deploy test, the configuration-item test, blast radius, and live-means-a-
consumer. That is the evidence for the rule: **they are lenses, not a decision
procedure.**

> The criteria inform the judgement. The judgement decides. The reason is
> recorded.

Two constraints keep that from dissolving the process:

- **Judgement may override a classification; it may never override a gate.** A
  change can be called merge-lane against the written test; nobody can decide
  that CI passed. Gates have objective answers and scripts own them — overrides
  live entirely on the other side of that line.
- **A criterion overridden repeatedly is a defect in the criterion.** One
  override is a judgement, three in the same direction are a bug report. That is
  how #154 came to exist.

And an override costs **a sentence** — what was decided, and why the written test
did not fit. Not a form and not an approval: the sentence is what turns a
departure into evidence, and evidence is what fixes the criterion.

### Live means a consumer has it, not that production has it

**Decided 2026-08-19.** Owner, on merging a half-written script: *"I want to use
the new script, so it is 'live' even if it is potentially still being
developed."*

That is the merge lane's logic stated from the other end. Tooling is an internal
service whose consumer is the delivery team, so **merging is its release** —
there is nobody else to release it to. Three consequences:

- it stops being a scratch file: further work goes on a branch and merges like
  any other change, and leaving it broken is a small outage rather than an
  untidy working tree
- *still being developed* is not the opposite of live — it is the
  living-document rule applied to a script: **finished means working, not
  complete**
- care scales with **blast radius**, not with category: `actions.py` breaks a
  view, `deploy.sh` breaks a release, and both are tooling

**What this gives us that "does it reach production through a deploy?" does
not.** The deploy test is the right *operational* question — fast, checkable,
and it answers most cases. The CI-and-service framing is the *reason*, and it is
what makes config-only and monitoring fall out cleanly instead of feeling like
exceptions. Keep the deploy question as the test; keep this as the explanation
behind it.

Sources: [ITIL change
enablement](https://itsm.tools/change-enablement/) · [release vs deployment
management](https://www.vivantio.com/blog/release-management-vs-deployment-management/)
· [ITIL release
types](https://the-requirements-engineer.com/management-articles/itil-types-of-releases/)
· [monitoring and event
management](https://purplegriffon.com/blog/monitoring-and-event-management-itil)
· [ITIL 4 overview, including the four
dimensions](https://itsm.tools/itil-4-explained/)

---

## How the process is managed: GitHub, folders, scripts

**Decided and in use**, except where marked. Owner, 2026-08-19: *"We also need to
document how we are using GitHub and scripts to manage the process… and the
folders and any other tooling."* This is the inventory; it lands in `docs/3.3`
as a section of its own, and the script rows join the table in `docs/3.0`.

### GitHub objects, and what each one means here

| object | carries | notes |
| --- | --- | --- |
| **issue** | one change, or one project | the body is the conclusion, the comments are the argument |
| **parent issue** · **sub-issue** | a workstream and its parts | real GitHub links, so structure is read rather than inferred |
| **milestone** | a **release**, or a lane | `deploy.sh` closes the milestone and every open issue in it, which is why anything not shipping must leave first |
| **type label** | what a change is, and what it owes | the seven: `bug`, `documentation`, `non-prod-tooling`, `prod-tooling`, `major-function`, `minor-function`, `appearance` |
| **`phase:` label** | where a project is | five, hand-set — scope-and-design, development, user-testing, deployment, post-deployment |
| **`awaiting-review`** | it is Steve's turn | set by hand or by `/ready`; the native draft flag cannot be set by our token |
| **`approved`** | reviewed; the merge is Claude's to run | approving and merging are different decisions, so this never merges anything |
| **task list in an issue body** | an **action** — the only surface that carries state | `(Steve)` / `(Claude)` prefix makes "waiting on whom" derivable |
| **task list in a pull request body** | the **review checklist**, which is the review itself | a workflow fails the check while a box is unticked |
| **pull request** | one change's passage: review, readiness, mechanics | frozen at merge, so conclusions are promoted to the issue body or a document before then |

### What the tooling reads, and what it writes

**Decided 2026-08-20**, after the owner left two tables in an issue body he
wanted to delete: *"I wasn't sure if they were automated and I didn't want to
break the tooling."* A document whose machine-read parts are invisible makes
every edit a risk, and the safe move becomes changing nothing.

Two categories, and they need different marks because they need opposite
behaviour from a reader:

| | mark | who writes it | what a person may do |
| --- | --- | --- | --- |
| **read** by a script | a **named heading**: `## Open actions`, `## Review` | a person | edit freely, but keep the shape — one `- [ ]` per item |
| **written** by a script | a **banner**, unmissable: `***** GENERATED — DO NOT EDIT *****`, with the tool named | the tool | nothing. Change the source, re-run the tool |
| everything else | none | a person | anything at all |

**Nothing is generated today.** The banner is defined ahead of its first use:
the release log in #156 is the first thing that will need it — because the rule is
cheap to state now and expensive to retrofit onto a document somebody has
already hand-edited.

**Never mix the two in one section.** That is #156's own conclusion about the
release log — *never mix generated and hand-written in one file* — applied one
level down: a regeneration that has to preserve somebody's prose is a
regeneration that will eventually eat it, and the failure is silent.

**A read section says so, in itself.** One italic line under the heading naming
the script and the shape it expects. A reader should not have to know the
tooling to know what is safe.

### Folders

| path | holds |
| --- | --- |
| `docs/1.x` – `docs/4.x` | the numbered documents: rules, design, lifecycle, reference. The permanent record |
| `docs/changes/issues/<n>-<name>/` | design notes, impact assessments and drafts for one issue — or for a workstream's parent |
| `docs/changes/releases/<version>/` | testing documents for one release |
| `docs/changes/*.md` | five files that predate the convention and stay put, because issue comments link to them |
| `docs/diagrams/` | `.mmd` sources and their rendered `.svg` — edit the source, re-render, commit both |
| `scripts/` | everything below, plus the deploy path |
| `.github/workflows/` | CI, and the document review workflow |
| `.claude/` | how Claude is driven — gitignored, because it is not the project's |

### Which script answers which question

| question | script |
| --- | --- |
| where is every open change, and what is each environment running? | `status.sh` |
| what is in each release, in release order? | `roadmap.sh` |
| what is waiting on me? | `actions.py` |
| what has been said on GitHub since I last looked? | `inbox.sh` |
| is everything actually in place? (asserts, exits non-zero) | `verify.sh` |
| are the documents lint-clean, their links live, their files in the right folders? | `check-docs.sh` — CI runs it on every push |
| did a named CI run pass for this commit? | `ci-status.sh` |

The first four **derive and store nothing**, so they cannot drift; the last three
**assert**, and exit non-zero when they are unhappy. That split is deliberate:
a display has to be read, and the failure mode of reading is not noticing.

### Other tooling

| | what it does |
| --- | --- |
| **CI** (`.github/workflows/ci.yml`) | fmt, clippy, tests, wasm, the commit stamp, `check-docs.sh`, and Playwright on `main` and pull requests. A deploy gate, not a signal |
| **Docs workflow** (`docs.yml`) | the review checklist as a check, and `/ready` `/changes` `/approve` as label-only commands. **Candidate** until PR #184 merges |
| **OCI monitoring** | external `/health` probes from three regions, plus CPU, memory and instance-stopped alarms, emailing the owner (#136) |
| **`.claude/` hooks** | a session-start GitHub digest, and a per-turn check for new comments and edited pull request bodies |

---

## Capability workstreams

**Candidate**, with the list agreed 2026-08-19 and the adoption not started. A
workstream is a **capability area**, worked on indefinitely — not a bag of
issues that arrived in the same week. The difference is that a capability
workstream is *predictive*: a new issue knows where it belongs before anybody
discusses it.

Ten, and they cover **every one of the 47 open issues** — which is the test a
taxonomy has to pass, because an issue with no home goes back to being grouped
by whoever filed it.

| workstream | what it covers | anchored today by |
| --- | --- | --- |
| **process and tooling** | how we work, and everything that runs the work: the release path, the scripts, CI, testing tooling | #179, #160, #134, #144, #91 |
| **game model and rules** | what the game *is*: seats, turns, versions, history, retention, the rules themselves | #71, #73, #68, #166 |
| **interaction design** | how the game is presented and controlled | #146, #84, #105, #152 |
| **accounts and identity** | who a player is, and what may be done to an account | #57, #58, #140 |
| **notification and liveness** | telling a client that something changed, and noticing when it did not | #87, #142, #15 |
| **infrastructure and persistence** | what every feature rests on: schema, migrations, concurrency, process lifetime, memory | #29, and #71's chunk A |
| **capacity planning** | *will it fit* — growth, throttling, limits, measurement | #89, #29, #165 |
| **production operations** | *is it healthy now* — logs, alerts, backups, disk, access | #174, #175, #176, #40 |
| **dictionaries and word lists** | the lexicons and what may be played | #116 |
| **desktop and distribution** | shipping something that is not the web client | #38, #15 |

### The two rules that keep it clean

**One axis: capability, never layer.** *Client UI* and *server/db* are tiers, and
a taxonomy on two axes stops being predictive — #142 would belong to notification
*and* to server/db, and #71 to game model *and* to both tiers, which is precisely
the issue whose argument is that the two halves are one model. So *client UI*
becomes **interaction design**, and *server/db* becomes **infrastructure and
persistence**, which is a genuine non-feature capability rather than a tier:
everything rests on it.

**If it would disappear when a feature is cut, it belongs to the feature.** That
is the test for infrastructure, and it settles the cases that feel ambiguous:
issue #29 survives every feature, so it is infrastructure; #166 is a rule, and needing
a background task does not move it out of game model; #142's fix is a server's
but its symptom is a user's, so it is liveness.

**And a technique is not a capability.** *e2e design* is how we know the
application works, not something it does — so it is a project inside process and
tooling rather than a workstream of its own.

### The decision point

Adopting this means **every open issue gets a workstream**: a pass over 47, and a
choice between a parent issue each or a `workstream:` label each. Worth doing
once, deliberately — the half-done version is worse than the grouping it
replaces, because a partial taxonomy still has to be searched.

---

## Open questions for the review

1. **How much to cite.** A named practice a reader can look up is worth more
   than a paragraph of our own reasoning — but 3.3 is already long, and #137 is
   about making it shorter to consult. Suggest: name the term in the *what*,
   cite the source once in the *notes*, and nowhere else.

2. **Whether "gate" needs qualifying.** We use it for both "a check that
   refuses" and "a check that warns and asks" — and the audit found 3.3
   describing the second as the first. Perhaps *gate* (refuses) and *check*
   (reports), used strictly.

3. **Whether to adopt "release train" fully.** It implies a schedule, and we
   release when a scope is ready rather than on a cadence. Adopting the word
   without the schedule may mislead.

4. **Whether to adopt the three attributes and retire "lane"** — the substantive
   decision in this document. Adopting them means new labels or a project field
   (worth checking against #160 before adding four more labels), an edit to
   `docs/3.3`'s lane table, and `status.sh` learning to read whichever mechanism
   replaces the milestone-as-lane.

5. **Whether "config-only" needs a name at all**, or is simply *route = applied
   on the host, release = none*. I lean to the second: it is a combination, not
   a category, and naming it invites it to grow rules of its own.
