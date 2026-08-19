# Glossary: our terms and the industry's

A draft for review, per #155. **Nothing here is decided.** Each entry gives the
standard term, what it means in the literature, what we call it, and a
recommendation — because sometimes ours is better *for us* and adopting a word
adopts its baggage.

The point is not renaming for its own sake. It is that a reader who knows the
standard term can map what we do onto what they already know and go and read
more; and that `docs/3.x` is meant to be portable to a second project, where our
private vocabulary would travel badly.

Three possible outcomes per term: **adopt** it, **keep ours** and say why, or
**use both** — the standard term once so it is findable, ours thereafter.

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
| a unit of build | **chunk** | work package | one development unit within a project: "the client changes for #71" |
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
