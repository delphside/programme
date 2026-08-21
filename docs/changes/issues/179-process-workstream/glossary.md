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

Its sibling in this folder is
[`process-review.md`](process-review.md) — this project measured against
published release-engineering practice, written 2026-08-13 for #133. It is
history rather than a live document: what survived it is in `docs/3.3`.

The point was never renaming for its own sake. It is that a reader who knows the
standard term can map what we do onto what they already know and read further,
and that `docs/3.x` is meant to be portable to a second project, where our
private vocabulary would travel badly.

Three possible outcomes per term: **adopt** it, **keep ours** and say why, or
**use both** — the standard term once so it is findable, ours thereafter.

**Older sections here use the older words.** Owner, 2026-08-20: *"we have been
updating our use of the words 'issue', 'project', 'release', 'delivery'. Some of
the text predates this. However the important document is not this one, but the
main documents we will update."*

So this document is not swept. It is a record of how the words were arrived at,
and a section written before *delivery* was settled is evidence of that, not a
defect. **The sweep applies to `docs/3.x` and its neighbours**, where a reader is
looking for the rule rather than for the argument that produced it — and where a
stale word would be read as current.

## Decisions

Owner, 2026-08-20: *"A lot of the actions can become decisions in the glossary,
with options and recommendations."* So they are here, as questions rather than
as *"(Steve) decide whether…"* scattered across issues — each with what the
options actually are and what I would do.

**Each decision lives in the section it belongs to**, with the argument that
produced it. This is the index: the question, whether it is settled, and where
to read it.

| | question | | where |
| --- | --- | --- | --- |
| **D1** | Does the lane become three attributes? | **answered** | [Classifying a change](#classifying-a-change-type-route-release) |
| **D2** | Do we adopt capability workstreams, and when? | **answered** | [Workstreams](#workstreams-the-capabilities-we-maintain) |
| **D3** | Do project phases stay, and where do they apply? | **answered** | [Projects](#projects-phases-and-gates) |
| **D4** | Is the post-implementation review built, and how? | **answered** | [Projects](#projects-phases-and-gates) |
| **D5** | Does `main` get a ruleset? | **answered** | [Process and authorisation](#process-and-authorisation-what-a-change-must-pass-through) |
| **D6** | What is a release, and what gets logged as one? | **answered** | [Delivery](#delivery-releases-applications-and-merges) |
| **D7** | Should `docs/changes/issues/` be renamed, and to what? | **answered** | [How the process is managed](#how-the-process-is-managed-github-folders-scripts) |
| **D8** | How much to cite | **answered** | [Terminology](#terminology-our-words-and-the-industrys) |
| **D9** | Do *gate* and *check* mean different things? | **answered** | [Terminology](#terminology-our-words-and-the-industrys) |
| **D10** | The terminology recommendations — accept them? | **answered** | [Terminology](#terminology-our-words-and-the-industrys) |
| **D11** | Do phases apply to a work package, or only to a project? | **answered** | [Projects](#projects-phases-and-gates) |
| **D12** | Can a release carry work from more than one project? | **answered** | [Delivery](#delivery-releases-applications-and-merges) |
| **D13** | Is *release* the word for any delivery? | **answered** | [Delivery](#delivery-releases-applications-and-merges) |
| **D14** | Do we classify the process a delivery must go through? | **answered** | [Process and authorisation](#process-and-authorisation-what-a-change-must-pass-through) |
| **D15** | Technical testing and user testing — a variant, or a property of each change? | **answered** | [Classifying a change](#classifying-a-change-type-route-release) |
| **D16** | What is a *test approach*, and what satisfies the gate? | **answered** | [Process and authorisation](#process-and-authorisation-what-a-change-must-pass-through) |
| **D17** | Do we adopt the standard testing terminology? | **answered** | [Terminology](#terminology-our-words-and-the-industrys) |
| **D18** | What does a project own, and what happens to the issues it absorbs? | **open** | [Projects](#projects-phases-and-gates) |
| **D19** | Do we need a release object? | **answered** | [Delivery](#delivery-releases-applications-and-merges) |

## The levels: programme, workstream, project, work package, release

Definitions only — where these live in GitHub is a separate question, settled
on issue #179. Checked against MSP and PRINCE2, and against a second opinion
asked the same question.

| level | ours | the industry's | definition |
| --- | --- | --- | --- |
| the whole thing | **programme** | evergreen programme · continuous value stream | the application **and everything we maintain to keep it going**: the production service, the dev, preview and rehearsal environments, the documentation, and the process itself. Unbounded scope, no end date |
| an area of it | **workstream** | functional or capability workstream | one capability, worked on indefinitely — the game model, the process, production operations |
| a bounded piece | **project** | project | *a temporary endeavour undertaken to create a unique product or result* — fixed scope, ends when the scope is complete |
| a unit of build | **work package** | work package (PRINCE2, WBS) | one development unit within a project: "the client changes for #71". We said *chunk* until 2026-08-19 |
| what ships | **release** | release | one or more changes built, tested and deployed together |

**Everything in the programme is under change control, not only the production
service.** Owner, 2026-08-20: *"The whole application includes not only the
production service, but also the dev and test environments, the design
documentation, the processes and so on. A change to any of these should be
recorded and controlled."* That is why `documentation` and `non-prod-tooling`
are types rather than exemptions, why the merge lane is a lane rather than a way
of avoiding one, and why this document exists at all. What differs between them
is the **evidence** each owes and the **route** it takes — never whether it is
tracked.

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

*Both were listed as open questions at the foot of this document until
2026-08-20; they were answered here and the duplicate has gone.*

---

## Workstreams: the capabilities we maintain

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
| **infrastructure and persistence** | what every feature rests on: schema, migrations, concurrency, process lifetime, memory | #29, and #71's work package A |
| **capacity planning** | *will it fit* — growth, throttling, limits, measurement | #89, #29, #165 |
| **production operations** | *is it healthy now* — logs, alerts, backups, disk, access | #174, #175, #176, #40 |
| **dictionaries and word lists** | the lexicons and what may be played | #116 |
| **desktop and distribution** | shipping something that is not the web client | #38, #15 |

### Every open issue, on all three axes and a workstream

**The whole tracker, in one table.** Owner, 2026-08-20: *"As you have mapped
every open issue to the axes and workstream can we see that in one table."* This
is the test the list and the axes both have to pass, and the work list if D1 and
D2 are adopted.

Routes are abbreviated: **artifact** · **deploy** · **host** · **service** ·
**repo**. *Release* is `not decided` wherever the work is not scheduled, which
is most of the backlog and is the honest answer.

| # | title | type | route | release | workstream |
| --- | --- | --- | --- | --- | --- |
| **10** | Bot client harness: run an engine as an extern… | non-prod-tooling | repo | none | process and tooling |
| **15** | Desktop has no client-update signal since 2.9 | major-function | artifact | not decided | desktop and distribution |
| **29** | Memory and startup grow with every game ever p… | major-function | artifact | not decided | infrastructure and persistence |
| **38** | A download site for desktop builds — or a deci… | major-function | service · a download site is a service we would run | not decided | desktop and distribution |
| **40** | Rehearsal holds production user data on a publ… | non-prod-tooling | **?** · Caddyfile or a firewall rule — shape not chosen | none | production operations |
| **57** | A player closing their own account | major-function | artifact | not decided | accounts and identity |
| **58** | Shutting out a problematic player | major-function | artifact | not decided | accounts and identity |
| **66** | A rating graph point can link to a swept game | bug | artifact | patch | game model and rules |
| **68** | Retention for games that never started: the 30… | major-function | artifact | not decided | game model and rules |
| **71** | One game model: version, seats, DTOs and the e… | major-function | artifact | major | game model and rules |
| **73** | Undo, from a history keyed on the game's versi… | major-function | artifact | major | game model and rules |
| **80** | Changing your display name does not reach othe… | bug | artifact | patch | accounts and identity |
| **84** | Games list appearance | appearance | artifact | not decided | interaction design |
| **87** | Tell a player a message has arrived when they … | major-function | artifact | not decided | notification and liveness |
| **88** | out-of-turn staging and rearranging tiles | minor-function | artifact | not decided | game model and rules |
| **89** | Notice unusual growth in the database, startin… | major-function | artifact · the daily record is in the image | not decided | capacity planning |
| **91** | Stress testing: find where the service breaks,… | non-prod-tooling | repo | none | process and tooling |
| **103** | Browser tab icon | appearance | artifact | patch | interaction design |
| **105** | withdrawing should immediately hide the game | minor-function | artifact | patch | game model and rules |
| **106** | inviting yourself should automatically accept | minor-function | artifact | patch | game model and rules |
| **116** | Curate the denylist | minor-function | artifact · the list is compiled in | patch | dictionaries and word lists |
| **128** | e2e-clean cleans dev's database whatever envir… | non-prod-tooling | repo | none | process and tooling |
| **130** | Show the server's version in dev, where the to… | — | artifact · dev-only, but it ships in the binary | minor | **unassigned** |
| **134** | Ship the build we tested, rather than rebuildi… | prod-tooling | repo · deploy.sh runs from a laptop | none | process and tooling |
| **135** | Make a release branch rebuildable, so a change… | non-prod-tooling | repo | none | process and tooling |
| **140** | Admin CLI: sign an account out, so the delete … | — | artifact · the admin CLI is in the image | not decided | accounts and identity |
| **142** | A reconnected WebSocket never re-fetches state… | minor-function | artifact | not decided | notification and liveness |
| **144** | Check CI before merging into a release branch,… | prod-tooling | repo | none | process and tooling |
| **146** | Rework the play controls: Pass/Exchange/Play, … | — | artifact | not decided | interaction design |
| **148** | check-rate-limits.sh leaves its test accounts … | prod-tooling | repo | none | process and tooling |
| **150** | deploy.sh closed the milestone on an emergency… | prod-tooling | repo | none | process and tooling |
| **151** | Check for a new bundle on visibilitychange, no… | — | artifact | patch | notification and liveness |
| **152** | removing a game should clear the board and rac… | appearance | artifact | patch | interaction design |
| **155** | Process decisions: agree them here, apply them… | documentation | repo | none | process and tooling |
| **156** | A log with one entry per release | documentation | repo | none | process and tooling |
| **157** | Remove leaves a staged tile on the board after… | bug | artifact | patch | interaction design |
| **160** | Use more of GitHub where it replaces something… | non-prod-tooling | service · GitHub's own configuration | none | process and tooling |
| **165** | Retry-After is rebuilt from an already-rounded… | minor-function | artifact | patch | infrastructure and persistence |
| **166** | Nothing happens when a move time limit expires… | minor-function | artifact | not decided | game model and rules |
| **171** | A separate GitHub account for Claude, if the f… | non-prod-tooling | service · a second GitHub account | none | process and tooling |
| **174** | Container logs are discarded on every deploy, … | minor-function | artifact · **+ host** — the journald drop-in | not decided | production operations |
| **175** | No backup leaves the VM: losing the instance l… | prod-tooling | **?** · host or deploy — shape not chosen | none | production operations |
| **176** | Nothing alerts on the production disk filling,… | prod-tooling | service · an OCI alarm | none | production operations |
| **179** | Process workstream | documentation | repo · the parent issue itself | none | process and tooling |
| **183** | A document review workflow in Actions: lint, l… | non-prod-tooling | repo · a workflow file is a repo file | none | process and tooling |

#### What the table shows

**Four issues carry no type label** — 130, 140, 146, 151 — which the form would
have made impossible: type is a required field. That is the first concrete
argument for the form over labels applied afterwards.

**Two cannot answer *route*.** #40 and #175 do not know their own shape yet: a
firewall rule or a `Caddyfile` change; a script on the host or one in the image.
Route needs a *not decided yet*, exactly as release has one.

**One carries two routes.** #174 is JSON logging in the artifact **and** a
journald drop-in on the host. The tie-break picks artifact; nothing yet records
the half that stays manual.

**One fits no workstream.** #130 is dev-only tooling that ships in the client
binary — process by purpose, interaction design by location. Left unassigned as
evidence rather than forced.

**Two workstreams hold one issue each, and that is fine.** Owner: *"It may be a
fairly focussed workstream. It may be that the issue was well scoped with a
complete thought out set of changes."* A capability is not less real for having
one open question about it today. What would be evidence against it is a
workstream nothing ever lands in.

**The release column is mostly *not decided*, and should be.** Twenty-three of
forty-five. Deciding what ships together is scheduling, and scheduling before
there is a project to schedule is guessing.

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

#### D2 · Do we adopt capability workstreams, and when? — **answered: yes, one pass**

| option | |
| --- | --- |
| **adopt in one pass** | assign all 47 open issues, then keep it true |
| **adopt as issues arise** | new issues get one, old ones do not |
| **do not adopt** | keep grouping by whatever arrived together |

**Recommended: one pass.** A partial taxonomy still has to be searched, so the
half-done version costs what the whole one costs and delivers nothing. It is an
hour of filing, once.

**Answered 2026-08-20: yes — adopt them, and every issue is assigned to a
workstream.** Owner: *"yes, adopt capability workstreams, every issue is assigned
to a workstream."* So it is a rule and not a habit: an issue without a workstream
is an issue that is not yet filed, which makes the pass over the 47 open ones the
first application of the rule rather than a migration preceding it.

## Classifying a change: type, route, release

### D1 · Does the lane become three attributes? — **answered: yes, as an issue form**

**Decided 2026-08-20**, with the criteria still to settle. Owner: *"we should be
using the issues form. I would like to see how this categorises some example
real issues. The merge lane one's are the hardest. We still need to settle the
criteria."*

The form asks three questions — **type**, **route**, **release** — and the
answers land in the issue body where `actions.py` and `roadmap.sh` can read
them. Draft in `.github/ISSUE_TEMPLATE/change.yml`.

#### The form itself, as proposed

**Not created yet**, deliberately: an issue form is live the moment it lands, and
two of its options are still wrong (below). It lives here as text until D1 is
settled, and then it is created once — because an issue with changes on `main`
and changes on a branch invites exactly the mistake it sounds like. Owner,
2026-08-20: *"No issue should have changes in main and changes in a branch."*

```yaml
name: Change
description: Anything that changes the application, the process, or how either is run
body:
  - type: markdown
    attributes:
      value: |
        Three questions before the description. They decide what this change
        owes and how it reaches users — and answering them here is cheaper than
        arguing about them later.

  - type: textarea
    id: what
    attributes:
      label: What is wrong, and what should be true instead
      description: The scope. What is excluded is worth saying too.
    validations:
      required: true

  - type: dropdown
    id: type
    attributes:
      label: Type — what this change is
      description: One only. If two apply, it is two changes.
      options:
        - "bug — the app does the wrong thing"
        - "minor-function — behaviour a user could notice"
        - "major-function — changes the design, architecture or principles"
        - "appearance — visual only"
        - "documentation — the whole change is documentation"
        - "non-prod-tooling — dev, test and preview tooling"
        - "prod-tooling — acts on production without changing the app"
    validations:
      required: true

  - type: dropdown
    id: route
    attributes:
      label: Route — how it reaches production
      description: >-
        Where several apply, pick the one that decides the risk: the artifact
        beats the deploy, the deploy beats the host.
      options:
        - "in the artifact — built into an image we ship"
        - "carried by the deploy — sent to the VM, but not built"
        - "applied on the host — by hand on the production machine, no artifact"
        - "applied to a service we use — GitHub, OCI, DNS, the mail provider"
        - "never leaves the repository — live the moment it merges"
    validations:
      required: true

  - type: dropdown
    id: release
    attributes:
      label: Release — what carries it to users
      description: Leave as "not decided" if it is not scheduled yet.
      options:
        - "nothing — live at merge"
        - "a patch, on its own"
        - "grouped into a minor release"
        - "grouped into a major release"
        - "not decided yet"
    validations:
      required: true

  - type: textarea
    id: evidence
    attributes:
      label: What would show it works
      description: >-
        Evidence follows what the change does, not its type — a migration owes a
        restore, a rate limit owes a script, a document owes a reader.
```

**Two things to fix before it is created**, both found by running real issues
through it:

- **route needs a *not decided yet***, as release has. #40 and #175 do not know
  their own shape — a firewall rule or a `Caddyfile` change; a script on the host
  or one in the image — and the form currently forces a guess
- **a change can have two routes.** #174 is JSON logging in the artifact **and** a
  journald drop-in on the host. The tie-break picks the artifact, and nothing
  records the half that stays manual. Either route becomes multi-select, or two
  routes means two issues — the same shape as *one change, one type*

##### The four axes, defined

Owner, 2026-08-20: *"each of these three axes needs a table with definitions.
Workstream as well."* Four tables, one per axis, each value defined rather than
listed.

###### type — what the change is

The seven, and **`docs/3.3` §2.9.6 is the definition** — how each ships, what
version it moves, and what evidence it owes. Summarised here only so the axes
can be read together; when this is applied, 3.3's table gains the other three
rather than repeating this one.

| value | what it is |
| --- | --- |
| `bug` | the app does the wrong thing. A bug in a script is tooling, not this |
| `minor-function` | behaviour a user could notice, client or server |
| `major-function` | changes the design, architecture or principles — owes a design note first |
| `appearance` | visual only, no change in behaviour |
| `documentation` | the **whole** change is documentation. Every other type updates its own docs as part of being done |
| `non-prod-tooling` | dev, preview and test tooling: it does not act on production |
| `prod-tooling` | acts on production without changing the app |

###### route — how it reaches its consumer

Named for production because that is where the risk is, but the honest question
is **how does this reach whoever uses it**. Owner, 2026-08-20: *"the production
service is not everything we are maintaining."* A document's consumer is
whoever reads it, a script's is the person who runs it, and for both of those
the answer is *at merge* — which is why the merge lane exists and why "live"
means a consumer has it rather than that production does.

| value | what it means | examples | consequence |
| --- | --- | --- | --- |
| **in the artifact** | built into an image we ship | client and server code, migrations, the `Caddyfile`, the admin CLI | the full release path |
| **carried by the deploy** | sent to the VM by `deploy.sh`, but built by nothing | `docker-compose.yml`, the `sa` alias | the full release path — it reaches production and can break it |
| **applied on the host** | changed by hand on the production machine; no artifact exists | `.env`, a journald drop-in, a cron entry | no release. Document it, and close the issue by hand |
| **applied to a service we use** | changed in somebody else's console | OCI alarms, DNS, GitHub's own settings, the mail provider | no release, same obligations as the host |
| **never leaves the repository** | nothing is sent anywhere | `docs/`, `scripts/` we run locally, CI config, tests | the merge lane — but **on save** for whoever is in the worktree, **on merge** for everyone else |

**When each route goes live is not the same moment.** Owner, 2026-08-20: *"code,
docker files etc. are checked out as part of the build process. Documents and
scripts are read in the dev environment worktree. This means that the dev branch
must be main before they are accessed… It also means that changes in main take
effect even before they are committed and merged."*

That is a real asymmetry, and it is the sharpest thing said about the repo route:

| | how it is read | live from |
| --- | --- | --- |
| **code, `Dockerfile`, migrations** | checked out into a throwaway worktree **at a commit**, then built | the commit is deployed — and never before, by construction |
| **documents and scripts** | read from **the working tree you are standing in** | **the moment the file is saved** |

So *"live at merge"* is the repo route's answer for **everyone else** — for CI,
for a fresh checkout, for the next session. For the person at the keyboard it is
already live, on whatever branch they happen to be on, saved or not committed.

Three consequences, and the first two are already defended:

- **`deploy.sh` checks the tooling it is running from**, not only the commit it
  ships: uncommitted changes under `scripts/` are reported before a release,
  because the script running the deploy is *not* the one from the worktree it
  builds
- **the fresh-checkout rule exists to make the first row true.** Code is
  protected from this by construction; scripts and documents are not, and cannot
  be — they have to be usable before they are finished
- **so documents are read in GitHub, and edited in the worktree.** Owner,
  2026-08-20: *"you choose the branch and it defaults to main. In the dev
  environment worktree the branch might switch as part of development."* GitHub
  makes provenance explicit — the branch is named on the page and `main` is the
  default — where the working tree answers *"which version is this?"* with
  whatever the last checkout left behind. The exception is a document **under
  review**: it is on a branch by definition, so choose that branch deliberately,
  which is the one case where the default is the wrong answer.

  The evidence is from today: three commits went to a branch while I believed I
  was on `main`, and `git push origin main` reported success because it pushed
  `main` — unchanged — from a working tree standing somewhere else.
- **a separate checkout for released scripts was considered and rejected.**
  Owner, 2026-08-20: *"Previously we decided not to have a separate clone of the
  repository for scripts, and have the check for main instead. It was seen as
  lower risk."* `deploy.sh`'s own comment records the same judgement — *"the fix
  is a separate released-scripts checkout, judged not worth its own upkeep"*. The
  trade is a **detect** control against a **prevent** one: a second clone would
  make it impossible to deploy from unmerged tooling, and would introduce two
  checkouts that can drift, a second thing to update, and the new failure of
  running the wrong one. The warning is cheaper than the failure it would prevent
- **the branch you are on decides which process you are following.** Switching
  branches switches your runbook, your scripts and your conventions, silently.
  That is the same shape as the dev client/server drift, one level up: the
  environment is telling you something different from what you think you are
  looking at

**And what a defect in each one reaches.** Owner, 2026-08-20: *"things have a
different IMPACT if there is a defect. The production service will impact users.
Capacity might also impact users. Design documents impact developers."*

| route | a defect reaches | when |
| --- | --- | --- |
| in the artifact · carried by the deploy | **users** | as soon as it is live |
| applied on the host or a service, for **production** | **users** — and with no smoke test or rollback to catch it | as soon as it is applied |
| applied on the host or a service, for **rehearsal or preview** | **developers** | next time somebody uses that environment |
| never leaves the repository | **developers** | next time somebody follows it |

**Impact is not a fourth axis**, because for most changes it follows from route
and environment — and a dropdown that can be derived is a dropdown nobody should
be asked to fill in. It is stated here because it is the reason the routes take
different paths: *care scales with who a defect reaches, and how soon.*

**Two kinds of change have deferred impact**, and they are the ones this rule
would otherwise flatter:

- **capacity** — a defect reaches users only when load arrives, which may be
  months after the change, and by then nobody is looking at it
- **design documents** — a wrong design reaches developers immediately and users
  eventually, through whatever gets built from it. That is the argument for
  reviewing a design note as carefully as the code it produces

**Two moments, not one, on the last row.** Owner, 2026-08-20: *"we should
distinguish between 'release on save' and 'release on merge'."*

| | delivered when | to whom |
| --- | --- | --- |
| **on save** | the file is written | the person standing in that worktree, on whatever branch they are on |
| **on merge** | it lands on `main` | everyone else — CI, a fresh checkout, the next session, and a reader on GitHub |

**And reading on GitHub costs a push.** Owner, 2026-08-20: *"if you are reading
docs on GitHub then you need changes to be merged and pushed to see them."* True,
and it is the price of the provenance: GitHub can only show what it has. Read the
worktree when you need the unpushed state — and know which branch you are on,
which is the reason the rule exists.

**A commit on `main` is a decision to deliver.** Owner: *"Any change in main could
be pushed by any other change, so you must decide that is okay."* An unpushed
commit on `main` rides out with the next push, whatever that push was for —
so committing to `main` is publishing, delayed only by accident. Two things
follow: never leave half-finished work committed on `main`, and the
[standard-change criteria](#standard-changes-what-may-go-straight-to-main) are
exactly the test of whether you are happy for it to go now, because *now* is when
it may go.

This is unique to the repository route, because it is the only one whose consumer
is holding the file. An artifact is delivered when it is deployed and a host
change when it is applied — both single moments, both for everybody at once.

It is also why `deploy.sh` reports the branch and cleanliness of the tooling it
is running from: on-save delivery means the script running a release can be a
version nobody else has.

> **Where several apply: the artifact beats the deploy, the deploy beats the
> host.** Pick the one that decides the risk. A file in the repository is repo
> route whatever executes it — otherwise every CI change becomes a service
> change.

###### release — what carries it to users

| value | what it means | which milestone closes it |
| --- | --- | --- |
| **nothing — live at merge** | the merge lane: it reaches its consumer when it lands on `main` | none. The commit says `Closes #N`, because nothing else will |
| **a patch, on its own** | shipped alone, usually a fix — the fasttrack | the patch version's milestone |
| **grouped into a minor** | rides with other changes in a `0.x.0` | that release's milestone |
| **grouped into a major** | rides in a `x.0.0` — structural, or a breaking wire change | that release's milestone |
| **not decided yet** | nobody has scheduled it. **The honest answer for most of the backlog** | none, until it is scheduled |

###### When the release is *nothing* — what to do, and how you know it is done

Owner, 2026-08-20: *"Where the release is 'nothing' how do we know what to do?
How do we know when we have done it?"* A release is the completion event for
everything that has one: the milestone closes, `deploy.sh` announces it, and the
issue closes itself. Without one, both questions need answering separately —
and the answer comes from **route**, which is the other reason the axis earns
its place.

| route | what to do | done when | what proves it |
| --- | --- | --- | --- |
| **never leaves the repository** | 1.1 record · 1.2 push · merge. Steps 1.3 – 1.7 do not apply — there is nothing to deploy | it merges | the commit, which says `Closes #N` because nothing else will ever close it |
| **applied on the host** | make the change · **write it down** · merge the documentation · close the issue by hand | the documentation merges | the documentation commit, which is the only durable record that the change was made |
| **applied to a service we use** | the same, and say **where** — which console, which account, which setting | the documentation merges | the same |

**The rule underneath: a change with no artifact is done when its documentation
is.** That is not bureaucracy — for `.env`, an OCI alarm or a DNS record, the
documentation *is* the only thing in the repository that knows the change
happened, and the only thing that survives a rebuilt host or a forgotten
console. `50-cap.conf` is the counter-example that proves it: a journald cap
applied by hand on 2026-07-30, recorded nowhere, and rediscovered three weeks
later only because it silently defeated a requirement.

**Two consequences worth stating:**

- **Nothing closes these issues automatically.** `deploy.sh` closes a
  milestone's issues on release, and there is no release — so a host or service
  change stays open until somebody closes it. That is a known gap, not an
  oversight: #136 and #147 were both closed by hand for this reason.
- **"Live at merge" is not "finished".** `check-docs.sh` was live the moment it
  merged, and its convention was not adopted anywhere yet. Where the two differ,
  the issue closes on **live**, and whatever remains is a new issue rather than
  an open one nobody can act on.

###### workstream — which capability it belongs to

The ten are defined in [Capability
workstreams](#workstreams-the-capabilities-we-maintain) below, with what each covers and the two
rules that keep the list clean. A workstream is a **capability**, worked on
indefinitely — not a bag of issues that arrived in the same week — and every
open issue has one, which is the test that list had to pass.

##### The routes, and the tie-break

| route | means |
| --- | --- |
| **in the artifact** | built into an image we ship |
| **carried by the deploy** | sent to the VM, but not built — `docker-compose.yml`, the `sa` alias |
| **applied on the host** | by hand on the production machine — `.env`, a journald drop-in |
| **applied to a service we use** | GitHub, OCI, DNS, the mail provider |
| **never leaves the repository** | live the moment it merges |

> **Where several apply, the artifact beats the deploy, and the deploy beats the
> host.** Pick the one that decides the risk.

The fourth route is new, and it appeared the moment real issues were tried
against the proposal: #136's alarms and #147's DNS are neither an artifact nor
the production host, and filing them under *the host* was the first thing that
broke.

##### Twenty real issues, run through the three questions

Chosen to exercise every route, every type, and each case #154 called hard —
not to demonstrate that it works.

| issue | type | route | release | what it tests |
| --- | --- | --- | --- | --- |
| #71 one game model | major-function | artifact | major | the ordinary case |
| #166 move timeouts | minor-function | artifact | not decided | a rule that needs a background task is still the app |
| #157 staged tile after removal | bug | artifact | patch | bug → patch, no argument |
| #103 browser tab icon | appearance | artifact | patch | appearance is still the artifact |
| #116 curate the denylist | minor-function | artifact | patch | data compiled into the image is the artifact |
| **#130 server version in dev** | minor-function | **artifact** | minor | **the surprise**: dev-only client code still ships in the binary |
| **#134 ship the build we tested** | prod-tooling | **never leaves the repo** | none | **the case that started #154** — `deploy.sh` runs from a laptop |
| #144 check CI before merging | prod-tooling | never leaves the repo | none | same shape, no argument |
| #128 e2e-clean | non-prod-tooling | never leaves the repo | none | test tooling is repo-side |
| #91 stress testing | non-prod-tooling | never leaves the repo | none | so is a load test |
| #156 the release log | documentation | never leaves the repo | none | documents are repo-side, even about releases |
| **#183 the docs workflow** | non-prod-tooling | **never leaves the repo** | none | **runs on GitHub, but it is a file in the repo** — the file decides, not the executor |
| **#176 disk alarm** | prod-tooling | **a service we use** | none | the new route, and it needs no artifact |
| #136 OCI alarms (closed) | prod-tooling | a service we use | none | confirms it against a change already made |
| #147 rehearsal DNS (closed) | prod-tooling | a service we use | none | DNS is a service, not a host |
| `.env` on the VM | prod-tooling | applied on the host | none | the config-only case, closed by hand |
| the `sa` alias `deploy.sh` writes | prod-tooling | carried by the deploy | with a release | not built, but it reaches production |
| `docker-compose.yml` | prod-tooling | carried by the deploy | with a release | same, and the case that made "built into" too narrow |
| **#174 container logs** | minor-function | **artifact** (JSON logging) **+ host** (journald) | with a release | **two routes** — the tie-break sends it to the artifact |
| **#175 the backup** | prod-tooling | **host, or deploy** — undecided | none | **the shape is not known until the fix is chosen** |
| **#40 rehearsal access** | non-prod-tooling | **artifact or service** — undecided | none | same, and #154 named it |

##### What the test found

**Three answers changed nothing**, which is the point: #134, #144 and #128 come
out merge-lane without an argument, where the old criterion produced one.

**Two issues cannot answer *route* yet.** #175 and #40 do not know their own
shape — a backup script could ship in the image or live on the host; access
control could be a `Caddyfile` change or a firewall rule. The form has *"not
decided yet"* for release and **nothing equivalent for route**, so today it
forces a guess. That is a gap, and the fix is one option.

**One issue has two routes.** #174 is JSON logging in the image *and* a journald
drop-in on the host. The tie-break answers it — artifact wins, so it takes the
release path — but the host half still has to happen by hand afterwards, and
nothing in the form records that. Either it is two issues, or *route* needs to
be multi-select.

**One boundary needed stating.** #183's workflow *runs* on GitHub but is a file
in the repository. The rule that settles it: **the file decides, not the
executor** — otherwise every CI change becomes a service change.

**The options as they stood, kept as the record:**

| option | |
| --- | --- |
| **keep the lane** | one label, and the arguments recur — five framings in a day, and #134 decided against the written test |
| **three attributes as labels** | `type` (have it) · `route` · `release`. Explicit, and four new label families to maintain |
| **three attributes via an issue form** | the same three as dropdowns when an issue is raised, landing in the body where the tooling can read them |

**Recommended: the issue form.** It puts the question at the moment the answer is
cheapest — when the issue is written — and it needs no new labels. It also gives
issue #160 something concrete: this is GitHub replacing something we would otherwise
hand-maintain.

#### D15 · Technical testing and user testing — a variant, or a property of each change? — **answered: a property of each change**

Owner, 2026-08-20: *"One variant on application release is technical application
release, which replaces user testing with technical testing in rehearsal… Or
perhaps we just say that technical aspects of the change are tested in rehearsal
by a technical test rather than in preview by a user test. Then if a release is
all technical or all functional it would just do one, but if it is a mix it would
do both."*

**The second framing is the better one**, and it is already 3.3's rule arriving
from a new direction: *evidence follows what the change does, not the label it
carries.* A category called *technical application release* would make the
release the unit; the change is the unit, and a release inherits the union of its
changes' obligations.

| what the change is | where it is judged | by what |
| --- | --- | --- |
| a person can see whether it does what was wanted | **preview** | **user testing** — the judgement no script makes |
| nobody can see it by using it — limits, timing, memory, headers | **rehearsal** | **a technical test**: a script that asserts the shape, on hardware that matches production |
| both | both | both, and neither substitutes for the other |

**This is not derivable from type.** #165 (`Retry-After` rebuilt from a rounded
number) is `minor-function` and entirely technical: nobody can see it by playing.
Issue #29 (memory growth) is `major-function` and tested by load, not by use. And #25's
rate limiting is the case that produced `check-rate-limits.sh` precisely because
preview *cannot* judge it — a development machine says nothing about a 2 vCPU
box.

**The machinery already exists**, and only the reasoning is missing:
`DEPLOY_SKIP_PREVIEW=1` means *"there was nothing for a person to look at"*,
which is exactly the all-technical release. Today that is a judgement typed at
deploy time; it should be the sum of what the milestone's issues said.

| option | |
| --- | --- |
| **every issue names where it is tested** — preview, rehearsal, or both | one more thing to answer, and the release's obligation becomes the union rather than a judgement at the end |
| a fifth axis, *test surface* | the same information, dressed as a category |
| leave it a judgement | which is where `DEPLOY_SKIP_PREVIEW` is now, and it has never been wrong yet — because one person holds all the context |

**Recommended: the first**, as part of the *what would show it works* field rather
than as a new dropdown. It costs a phrase per issue and it makes the skip
derivable — and the one-person-holds-the-context argument for leaving it is
exactly the argument that stops being true first.

**Answered 2026-08-20: the recommended option**, and the owner reduced it to two
questions asked of every delivery:

- **does this delivery involve functional changes which require user testing?**
- **does this delivery involve technical changes that require technical testing?**

They are asked separately and answered independently, which is the whole point:
*yes/no* sends it to preview alone, *no/yes* to rehearsal alone, *yes/yes* to
both, and *no/no* is a change nobody can show works — which is the answer worth
catching. A delivery's obligation is the union of its changes' answers, so
`DEPLOY_SKIP_PREVIEW=1` stops being a judgement typed at deploy time and becomes
the sum of what the milestone's issues already said.

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
| **config-only** (never named, and no longer needed) | it changes production with no artifact — which the axes now say as *route = applied on the host, release = none*. A combination, not a category: naming it would invite it to grow rules of its own | deployment |
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
| **route** | *in the artifact* · *carried by the deploy* · *applied on the host* · *applied to a service we use* · *never leaves the repository* | how it reaches its consumer, and which environment it changes |
| **release** | patch (alone) · minor · major · none | what carries it to users, and which milestone closes it |

Authorisation then falls out without a label of its own, landing on ITIL's three
change types exactly: *never leaves the repo* is a **standard change** — live on
merge, pre-authorised by a documented procedure; anything in the artifact or
carried by the deploy is a **normal change**; and the emergency deploy is an
**emergency change**, orthogonal to both other attributes.

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
| **journald retention drop-in** (#174) | prod-tooling | applied on the **production** host | none — document it, close by hand |
| **OCI alarms** (#136) | prod-tooling | applied to a service, for **production** | none — same |
| **rehearsal DNS** (#147) | prod-tooling | applied to a service, for **rehearsal** | none — same, and it changed no production service at all |
| `.env` on the VM | prod-tooling | applied on the **production** host | none — same |
| **the backup job** (#175) | prod-tooling | applied on the host, from a script in the repo | none, unless it ships in the image |

The two rows that used to have no answer at all — config-only and
tooling-installed-by-the-deploy — now have one by construction rather than by
adjudication.

## Projects: phases and gates

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

### What the phases still owe

The two questions this section used to carry are now **D4** (the
post-implementation review, answered) and **D11** (phases on a work package).
What remains is not a decision but a piece of work:

**Inserting the project layer.** #71's work packages and #179's children hang
directly off a workstream, with no project between. The vocabulary is decided and
the restructuring is not done — and #71 is where it will first be tested, being
the one workstream that genuinely has projects.

---

#### D3 · Do project phases stay, and where do they apply? — **answered: delivering workstreams only**

**Decided 2026-08-20.** Phases belong to projects, and projects belong to
delivering workstreams; a standing workstream has issues and pull requests and
nothing between. With three consequences the owner drew out, and the third
reverses an earlier decision:

**A project is an issue.** It has to be raised as one, because that is what
records its structure — its scope, its work packages, its phase, and its
documents.

**A project is named, not versioned.** *"The version won't be known until it is
scheduled, so we also need a name for the project consisting of workstream
number and an increasing letter or number"* — so `71A`, `71B`, `179A`. A project
still has a **main release version** once it is scheduled; the name is what it is
called before that, and after.

**Releases are attributes of projects** — the mechanism by which a project puts
its changes live — rather than the thing the project is filed under. Owner:
*"This changes a previous comment from me about naming projects after releases.
I now think releases are too volatile and imprecise."* That reverses the folder
rule agreed yesterday: a project's documents live under its **name**, not under
a version that may move or split.

**The options as they stood, kept as the record:**

| option | |
| --- | --- |
| **projects in delivering workstreams only** — *chosen* | a standing workstream has issues and pull requests and nothing between |
| every issue | more state to maintain, and most of it derivable |
| drop them | fall back to the derived three: not started, in progress, completed |

The first real test will be #71, the one workstream that genuinely has projects.

#### D11 · Do phases apply to a work package, or only to a project? — **answered: the project only**

Left over from the phases section, and untested because there is no project
layer in GitHub yet.

| option | |
| --- | --- |
| **projects only** | a work package inherits its project's phase and carries no label |
| every work package | more state, and most of it derivable from whether a branch exists |

**Recommended: projects only**, on the same argument as D3: a phase changes a
handful of times per project, which is when hand-set state stays honest. A work
package that needs its own phase is probably a project.

**Answered 2026-08-20: the project only.** Owner: *"phases apply to the whole
project, work packages deliver into the project and manage themselves."*

The second half is the part worth keeping, because it says what a work package
*is*: not a smaller project with a smaller lifecycle, but a unit of work that
owes the project **a delivery** and is otherwise left alone. Nobody tracks where
it has got to — the branch and its pull request say that already — and nothing is
reported at its level. The phase belongs to the project because the phase is what
the project owes *outward*: scope agreed, built, user-tested, deployed, reviewed.
A work package is inside that and inherits it.

#### D4 · Is the post-implementation review built, and how? — **answered: yes, as a lessons-learned review**

**Decided 2026-08-20.** Owner: *"Post-deployment should have a lesson's learnt
review, conducted by Claude and reviewed by Steve. It should have a template and
include 'was the intended scope delivered'… the template should list areas to be
considered, including areas where we have had problems. This review might lead
to new issues — to improve the process or to extend the scope."*

**Written by Claude, reviewed by Steve.** The person who did the work is worst
placed to notice what it cost and best placed to remember what happened, which
is the argument for both halves of that.

**The template is `docs/templates/post-deployment-review.md`**, and its shape
comes from two sources rather than from invention:

| source | what it contributes |
| --- | --- |
| [After Action Review](https://asana.com/resources/after-action-review-template) | the four questions: what did we set out to do, what happened, why the difference, what next. The oldest and clearest form of this |
| [PRINCE2 Lessons Report](https://prince2.wiki/management-products/reports/lessons-report/) | that a lesson is only worth capturing if somebody can act on it — so every finding ends as an issue, or is explicitly dropped |

Plus a list of **areas to consider**, each there because it has cost us
something: the milestone closing unshipped work (#67), a deferred test shipping
anyway, a rule landing in two documents, gates skipped, a tool failing silently.

**When:** once the project's last release has been live and used, not on the day
it ships — a week is usually enough for the interesting failures to surface.

**The options as they stood, kept as the record:**

Nothing asked whether a *normal* release did what it was for. #67 is the worked
example: closed by a milestone, listed as deferred in the testing report, and
genuinely broken.

| option | |
| --- | --- |
| **an action on the project at close** — *chosen* | one checkbox, no machinery, and it can be skipped silently |
| an issue raised by `deploy.sh` | as it already does for an emergency. Impossible to skip, and it will sometimes be noise |
| nothing | the status quo |

Start where it costs nothing; if a release goes wrong and nobody notices, that is
the evidence for making it automatic — which is how the emergency retrospective
came about.

#### D18 · What does a project own, and what happens to the issues it absorbs?

Owner, 2026-08-21: *"Within a workstream issues can be grouped into a project,
which then has a design, test approach and deliveries. At this point we should
freeze the source issues as the project now owns the requirements, design, test
approach and delivery… A single issue can be run as a project in its own right…
These can be text within the issue if they do not justify separate documents. A
single issue project can also accumulate other smaller issues and become the
project issue for them also."*

##### A project owns four things

| artefact | the question it answers | ours today |
| --- | --- | --- |
| **requirements** | what must be true when this is done | the issue's body, or a document — the glossary is playing this role for the process work |
| **design** | how it will be done | the design note, already required for `major-function` |
| **test approach** | environment, tools, and what is measured against what criteria | [D16](#d16--what-is-a-test-approach-and-what-satisfies-the-gate--answered-in-the-issue-or-in-8), and §8 of the test design specification |
| **deliveries** | what was shipped, when, and what happened | [D6](#d6--what-is-a-release-and-what-gets-logged-as-one--answered-the-log-records-deliveries)'s delivery log, recorded against the project |

**All four always exist. Only their location varies**, and it varies with size —
which is the whole answer to *documentation for large and small pieces*:

| | small | large |
| --- | --- | --- |
| **where the four live** | text in the project issue, under headings | four documents in the project's folder |
| **what decides** | whether they justify a separate document | the same question, answered the other way |
| **what does not change** | that each one is written down, and that the project owns it | — |

So there is no lightweight *process* and heavyweight *process* — one process, and
a document threshold inside it. A change too small for a design note still says
how it will be done; it says it in three lines in the issue.

##### Freezing the source issues

**The freeze is the part that does real work**, and it is worth being precise
about what it means. Once a project owns the requirements, a source issue that is
still live is a second place where requirements can change — and two sources
drift silently, which is the failure this whole workstream exists to prevent.

Frozen means: **the issue keeps its number and its history, and stops being where
anything is decided.** New thoughts about it go to the project. It is no longer
work in its own right, because the project is the work.

How to record that, three ways:

| option | |
| --- | --- |
| **close it, with a `folded` label and a comment naming the project** | the work list stays honest — a frozen issue is not work. Precedent: #154 and #181, both folded into the glossary and closed this way on 2026-08-20, and nothing was lost. The label is what keeps *closed* queryable into **delivered** and **folded**, which otherwise become indistinguishable |
| leave it open with a `frozen` label, closed by the delivery | *closed means delivered* stays true. But a project runs for weeks, and every list — `actions.py`, `status.sh`, the 45-issue backlog — carries issues nobody may act on |
| make it a sub-issue and leave it open | the parent link is real and GitHub renders it, but it says *belongs to* and not *do not touch*, which is the bit that matters |

**Recommended: the first**, and the comment is not optional — it is the only
thing that leads a reader of the frozen issue to where its content went. Two
rules follow, both of which exist because the freeze can otherwise trap things:

- **fold before you freeze.** The content moves into the project's requirements
  *first*; closing an issue whose requirement was never copied loses it silently
- **a frozen issue can be thawed.** If it turns out not to belong, it is reopened
  and the project's requirements say so. A freeze that cannot be undone is a
  reason not to freeze

##### Capture cheaply, consolidate deliberately

Owner: *"I don't want to limit our willingness to raise issues quickly when
something comes up, but we should expect to go through a process of merging them
into a coherent change."*

This is a rule about **when** consolidation happens, and there is already a phase
for it: **scope-and-design**. Raising an issue stays a five-second act with no
ceremony attached, precisely because nothing downstream assumes an issue is
well-formed. What makes it coherent happens later, once, and visibly.

Worth naming, because the two halves are easy to confuse: *raise freely* is not
*decide freely*. An issue raised in five seconds records that something was
noticed. It does not settle anything, and the project is where it gets settled.

##### A project is a state an issue enters, not a thing created up front

The three shapes are one shape at different times:

| | |
| --- | --- |
| **several issues grouped** | a new issue becomes the project, and absorbs them |
| **one issue run as a project** | it owns its own four artefacts, as text |
| **one issue that accretes** | the same issue becomes the project for later ones |

Two consequences. **A project's identity is an issue number** — which retires the
`<workstream><letter>` naming (`71A`) proposed earlier: `#71` already names it,
and a second identifier would need keeping in step. And **any issue may become a
project**, so nothing has to be decided at the moment of raising, which is what
makes *capture cheaply* safe.

##### Tested against the work in front of us

The process work is this model, arrived at by doing it rather than by planning
it — which is the strongest evidence available, and it also shows where the model
does not yet fit:

| | |
| --- | --- |
| **#179 absorbed six issues** | #137, #154, #181 folded and closed; #155, #156, #183 still open |
| **the glossary is its requirements** | exactly the owner's *"the glossary acting as the requirements"* |
| **but #155, #156 and #183 are not frozen** | #155 is the discussion venue for the requirements, which is a different thing from a source issue — it is the project's own thread. #156 and #183 are genuine source issues and should be frozen under this rule |
| **and #179 is called a workstream** | it has a fixed scope and an end, which by our own definition makes it a **project** — inside a *process* workstream that does not end. The name predates the levels |

That last row is a real finding rather than a tidy-up: the thing we have been
calling the process **workstream** is a project, and the workstream above it is
the one that will still exist after the glossary is applied.

##### The questions this leaves

- **is `folded` the right disposal**, or should frozen issues stay open?
- **should #156 and #183 be folded into #179 now**, on the same rule?
- **does #179 get renamed** to a project, with a process workstream above it?

## Delivery: releases, applications and merges

### D13 · Is *release* the word for any delivery? — **answered: no, *delivery* is**

Owner, 2026-08-20: *"are we happy that we use the word 'release' for any delivery
of change to its users, including a document edit? Otherwise we need a word for
this."*

Today *release* means a **versioned deploy** — `prod-X.Y.Z`, a tag, a milestone,
a smoke test — and the merge lane deliberately has none of those. So the word
either widens or gains a sibling.

| option | |
| --- | --- |
| **release means any delivery** | a document edit is a release. Then we need a new word for the versioned kind, and every existing sentence about releases has to be reread |
| **release stays narrow; *delivery* is the umbrella** | a **delivery** is a change reaching its consumer, and it comes in three kinds: a **release** (versioned, deployed), an **application** (done by hand on a host or a service), a **merge** (live where it lands) |
| no umbrella term | we keep saying *"live at merge"* and *"applied"*, which works in a sentence and not in a table heading |

**Decided 2026-08-20.** Owner: *"I am happy to have delivery as the general term
and release for a change in the application build id and version."*

So **a release is a change to the application's build id and version** — which is
exactly what `deploy.sh` produces, since the build id is derived from the commit
it builds. That definition settles an edge that would otherwise have needed
arguing: a `docker-compose.yml` change ships through `deploy.sh`, which rebuilds
from the commit, so the build id moves and it *is* a release — even though
nothing in the image changed on purpose.

And **delivery** is the general term, in three kinds: **release**,
**application** (by hand, on a host or in a service), **merge**.

**Evidence for the ambiguity, from the same conversation:** the owner asked to
distinguish *"release on save"* from *"release on merge"* — reaching for
*release* in the broad sense one message after asking whether it should carry
that sense. The word is already doing both jobs, which is the argument for giving
the broad one its own name rather than legislating the narrow one.

**Recommended: the second.** It keeps *release* meaning what it means everywhere
else — ITIL's *"one or more changes built, tested and deployed together"* — and
gives the thing we lacked a name: the row in a log, the event in a lifecycle, the
answer to *"when did this reach anybody?"*

**And it renames one thing already proposed.** #156's *release log* becomes the
**delivery log**, because D6 already decided it records host and service changes
alongside deploys — entries with no version. The name was describing one of its
three kinds.

Owner, 2026-08-20: *"I guess we start with route. Does route [determine] the
release mechanism? Do we group issues by route to construct releases?"*

**Yes to the first. No to the second**, and the difference is the whole of
planning.

### Route decides the mechanism; it does not decide the grouping

| route | mechanism | who acts |
| --- | --- | --- |
| in the artifact · carried by the deploy | **a release** — build, ship, migrate, smoke-test, tag, close the milestone | `deploy.sh` |
| applied on the host · to a service | **an action**, done by hand and written down | a person |
| never leaves the repository | **a merge** | whoever merges |

So route **filters** what a release can even contain: only artifact and deploy
issues are eligible. Grouping them is a different question, and grouping *by
route* would produce a release of unrelated changes that happen to share a
delivery mechanism — which is the milestone-as-lane mistake in a new costume.

### What actually groups issues: the project

**A project groups by outcome** — the set of changes that makes something true —
and its issues will usually span routes. #174 is the worked example already in
front of us: JSON logging is *artifact*, the journald retention drop-in is
*host*, and neither delivers the outcome alone.

So the shape of delivery is:

```text
workstream          a capability, never finished
  project           a fixed scope, and it ends
    issues          each with a route
      artifact/deploy  →  one or more releases
      host/service     →  actions, ordered around the releases
      repo             →  merges, live when they land
```

### Four things decide a release, in this order

1. **Eligibility** — route. Only artifact and deploy issues can ship in one.
2. **Coherence** — project. A release exists to deliver something; the project
   says what.
3. **Readiness** — is it built, reviewed, merged? An unready issue leaves the
   milestone rather than delaying it (#151 was caught this way, with an hour to
   spare).
4. **Version** — type. The highest type in the release decides the bump: a
   `minor-function` anywhere makes it a minor, and everything else rides along.

**A release may itself span routes, and that is not a defect.** Owner,
2026-08-20: *"we shouldn't split a project's release by route, because the
changes may be related and have to be done together in a particular order. So a
release may involve different routes."* A release is therefore a **coordinated
set of steps**, not a single act: host actions ordered around the deploy, and —
rarely — *"different builds of the application applied at the beginning and the
end"*, which is worth knowing is possible so that nobody treats one deploy per
release as a rule.

**Sequencing across routes is planning too**, and it is the part a milestone
cannot express: #174's journald drop-in should be applied *before* the JSON
logging ships, or the first structured logs land in a 50M journal that discards
them in five days. A project plan has to say that; a release cannot.

#### D12 · Can a release carry work from more than one project? — **answered: one owner, plus small passengers**

**Decided 2026-08-20.** Owner: *"It should be possible to combine different
projects in the same release… one owning project and smaller passengers makes
sense. Larger projects are complicated enough in themselves that you wouldn't
want to combine them. However small code changes can be tacked on to another
release without increasing the risk or complexity, as long as they don't touch
the same code."*

**The criterion for a passenger, in his words:** small, and **it does not touch
the same code**. That is what keeps the risk additive rather than multiplicative
— two changes in one file interact, two changes in different files do not, and
the second case is most of a backlog's small fixes.

**Two large projects are never combined.** Each is complicated enough on its own,
and a release that fails then has two candidate causes and two rollback stories.

*Previously discussed and consistent with this: a milestone is a shipping list,
and anything not shipping leaves it before the deploy.*

| option | |
| --- | --- |
| **one release, one project** | clean, and it matches *"releases are attributes of projects"*. It also forces more releases, and leaves a one-line fix waiting for a project it has nothing to do with |
| **a release has one owning project, and may carry passengers** | the project is why the release exists; unrelated ready work rides along and the milestone records it. Matches what 0.6.0 actually was — twelve issues, several unrelated |
| anything ready ships together | which is where we are now, and it is what made the milestone mean four different things |

**Recommended: the second.** The owning project explains the release; passengers
are how a two-line fix reaches users without waiting for a project of its own.
The cost is that *"what was this release for?"* has an answer and a footnote —
which the release log's *what it carried* column already accommodates.

#### D19 · Do we need a release object? — **answered: no, the release is derived**

Owner, 2026-08-21: *"Another grouping is projects from different workstreams
being delivered together. All we need do is state it in each project, include all
projects when we do the release build, and update the phase of all projects as we
take the release through the environments to production. We don't need to track a
release object separately."*

**This extends [D12](#d12--can-a-release-carry-work-from-more-than-one-project--answered-one-owner-plus-small-passengers)
from *owner plus passengers* to *peers*.** D12's case was one project explaining
the release with small unrelated fixes riding along. This is two projects from
different workstreams, each substantial, deliberately shipped on one build — and
D12's criterion still governs which combinations are allowed: *not the same
code*, so the risk stays additive.

##### The release is a set of projects that name it

Three mechanisms, no fourth:

| | |
| --- | --- |
| **each project states the release it is going in** | membership lives with the project, so there is one place to change and no list to keep in step |
| **the build includes all of them** | which it does anyway — the build is a commit of `main`, and everything merged is in it |
| **their phases move together** | from the moment the release forms, every project in it is in the same phase: deployment, then post-deployment |

**And the release itself is not a thing we maintain.** Its membership, its
contents, its version and its date are all derivable from the projects and the
tag. This is the fourth time the same answer has come out — route decides the
mechanism, the process category is derived, the milestone is derived, and now the
release. **We store what someone decided; we derive what follows from it.**

**In GitHub, the milestone already is this.** *Stating the release in each
project* means putting the project issue in the milestone, which `deploy.sh`
already reads as the shipping list. So the mechanism exists and needs a name
rather than a build.

##### Not in conflict with the delivery log

[D6](#d6--what-is-a-release-and-what-gets-logged-as-one--answered-the-log-records-deliveries)
records one row per delivery, which sounds like the object this decision refuses.
It is not: the log is written **after the fact** and answers *what changed in
production, and when* — a record, not a thing managed in flight. Nothing consults
it to decide what ships. The distinction is worth keeping sharp, because a log
that starts being read as a plan becomes a second source of truth.

##### What co-delivery costs, and the rule it needs

Two projects on one build are coupled in two directions, and only one of them is
obvious:

- **forwards** — if one fails user testing, the release waits or the project is
  pulled. With D12's owner-and-passenger there was an answer: pull the passenger.
  Between peers there is no owner, so it needs stating
- **backwards** — **a rollback takes back the whole release**, including the
  project that was fine. That is the sharper cost, and it argues that a change
  which must not be reverted, a security fix, should not ride with a risky one

**Proposed rule:** a project may leave a release at any point **up to the release
branch being cut**; after that, removing it means cutting a new branch, which is
a decision to slip the release rather than a tidy-up. This matches what our
release branches already are — the point at which the contents stop moving.

##### Phases diverge, then converge

A consequence worth writing down because it makes the `phase:` labels honest:
projects in different workstreams run their own phases independently — one may be
in development while another is in user testing — and from the moment they name
the same release they are **in the same phase for the rest of it**. Deployment
and post-deployment are properties of the release, and the projects in it share
them.

Which also means the phase update is scriptable rather than clerical: set the
phase on every project in the milestone, one command per environment.

#### D6 · What is a release, and what gets logged as one? — **answered: the log records deliveries**

Owner, 2026-08-20: *"These are attributes of the issue. We also need to
categorise a release. Are we going to log any change as a release, or only code
changes…"*

**Releases have attributes of their own**, and they are not the issue's. An issue
says what a change is; a release says what happened to production on one
occasion.

| attribute | values |
| --- | --- |
| **version** | `X.Y.Z` — patch, minor or major, per the rules already in 3.3 |
| **kind** | **normal** · **fasttrack** (a patch shipped alone) · **emergency** (gates skipped, retrospective owed) · **rollback** (production moved backwards) |
| **carried** | the milestone's issues — derivable, and `deploy.sh` already closes them |
| **outcome** | went live · rolled back · **went live and was wrong**, which #67 was |
| **facts** | tag, commit, date — all derivable from `git tag --list 'prod-*'` |

##### What gets logged

Three options, and the question is really *what is the log for*:

| option | | |
| --- | --- | --- |
| **A. deploys only** | one entry per `prod-*` tag | clean and fully derivable, and it misses every production change that arrives without a deploy — the journald cap, an OCI alarm, a DNS record |
| **B. anything that changes an environment we maintain** | deploys, **plus** host and service changes, **and which environment** each touched | matches the route axis exactly: artifact and deploy get a version, host and service get a dated entry with no version. And it holds for rehearsal and preview, which are also things we maintain — #147 changed rehearsal's DNS and nothing in production |
| **C. every change** | including merge-lane work | the commit log already does this, better, and nobody would read a log that grows by a dozen entries a week |

**Recommended: B**, and the reason is the one the route axis already found. A
change applied on the host or in somebody's console leaves **nothing in the
repository** unless we put it there — that is why those routes are *done when
their documentation is*. The release log is where that documentation naturally
lives, because the question it answers is *"what changed in production, and
when?"*, and a firewall rule answers to that question exactly as a deploy does.

So the log has two kinds of entry:

```text
version  date        kind       where       what                              outcome
0.6.2    2026-08-17  normal     production  bytes RUSTSEC fix, throttle test  went live
—        2026-08-19  host       production  journald retention raised to 7d   —
0.6.1    2026-08-14  fasttrack  production  #67's real fix                    went live
—        2026-08-14  service    rehearsal   DNS: rehearsal.tileliteelite.com  —
0.6.0    2026-08-14  normal     production  twelve issues                     #67 was wrong
```

**The version column is empty for a host or service change**, which is the point:
it says at a glance that this one had no release, and therefore no smoke test, no
rollback path and no milestone.

**And the environment column is there because production is not everything we
maintain.** A rehearsal DNS record and a preview volume are changes to things we
own, and the log's question — *what changed, where, and when* — is the same for
them. Filtering to production is then a column, where excluding them would have
been a decision nobody could reverse later.

##### Answered 2026-08-20

Owner: *"we have just discussed the general term is 'delivery', a release is a
version of the application with a build id and app version."*

So the two halves of the question separate, and the word does the separating:

- **the log records deliveries** — option B, everything that changes an
  environment we maintain, because a firewall rule answers *"what changed in
  production, and when?"* exactly as a deploy does
- **only some of those rows are releases** — the ones with a **build id and an
  application version**. That is what the empty version column above was already
  saying without having the word for it

Which means the table is a **delivery log**, not a release log, and the version
column is the test of which kind each row is. A row with a version is a release
and owes a smoke test, a rollback path and a milestone; a row without one owes
its documentation and nothing else.

##### The part that is not derivable

Version, date, commit and contents all come from tags and milestones. **Outcome
does not**, and it is the column worth having: *"went live and was wrong"* is
what makes 0.6.0's entry useful, and no tag knows it. That is #156's
generated-skeleton-plus-a-written-line, arrived at from the other end.

## Process and authorisation: what a change must pass through

### D14 · Do we classify the process a delivery must go through? — **answered: yes, derived**

Owner, 2026-08-20, proposing four categories: *pre-approved edit directly in
main · document merge · non-prod tooling and configuration · production tooling
and configuration*, the last two *"design and test approach approved"*.

**The categories are right and the list is incomplete** — it covers everything
except changes to the application itself, which is where most of the evidence
rules already live. The full set:

| process category | when | what it owes |
| --- | --- | --- |
| **pre-approved** | meets the [standard-change criteria](#standard-changes-what-may-go-straight-to-main), or the owner says *"go ahead and change the script"* | nothing beyond the commit. Straight to `main` |
| **document, reviewed** | a document that states a rule, or a major revision | a branch, a pull request, a review checklist, and the owner's tick |
| **non-production tooling and configuration** | `non-prod-tooling`, any route | **the design and test approach agreed before it is built**, then a branch and a review |
| **production tooling and configuration** | `prod-tooling`, any route | the same, plus rehearsal where the change can be rehearsed |
| **application change** | `bug` · `appearance` · `minor-function` · `major-function` | the full release path: CI, preview, **user testing**, rehearsal, the deploy gates. `major-function` owes a design note first |
| **emergency** | production is broken now | the rollback first; two gates skipped and a retrospective owed |

#### Is it a fifth axis, or derived?

**Derived**, and it should stay that way. Every row above is decided by *type*
plus *route* plus the standard-change criteria — the three things an issue
already carries — so asking for it in the form would be asking a question whose
answer is already in the answers. That is the same conclusion as *impact*: state
it, do not collect it.

**But one thing in it is genuinely new**, and it is the part worth adopting: the
tooling rows say **the design and test approach is agreed before the work
starts**. Today that gate exists only for `major-function` (a design note first)
and for projects (scope and design agreed). A tooling change of any size goes
straight from *"good idea"* to a branch — which is how `check-docs.sh` acquired a
second copy of CI's markdown lint, and how `actions.py` was rewritten three times
in a morning against a moving target.

| option | |
| --- | --- |
| **derive the category, and add the design-and-test gate for tooling** | one new obligation, on the two rows that lack it |
| derive it, change nothing | the table is documentation, and the gap stays |
| make it a fifth field on the form | a question whose answer is already implied by two others |

**Recommended: the first.** The categories go into `docs/3.3` as a table — *what
do I have to do with this?* is the question a contributor actually asks — and the
tooling rows gain the gate that would have caught two of this week's rewrites.

**Answered 2026-08-20: the recommended option, and the category is derived** —
from type, route and the standard-change criteria, never asked for on the form.

**The new gate is on the *test approach*, not on a test plan.** Owner: *"note
that the gate is on test approach, not a detailed test plan, although a test plan
would satisfy the gate, and we haven't defined test approach."* Two things follow.
The obligation is deliberately light — a paragraph saying how we will know this
works clears it, and the #41-style test plan is the heavy end of the same
spectrum, not a separate requirement. And **the term is undefined**, which is
[D16](#d16--what-is-a-test-approach-and-what-satisfies-the-gate--answered-in-the-issue-or-in-8) below.

#### D16 · What is a *test approach*, and what satisfies the gate? — **answered: in the issue, or in §8**

New, 2026-08-20, arising from D14: the gate names a document we have never
defined. A test plan we have — [`docs/templates/test-plan.md`](../../../templates/test-plan.md),
ten parts, written for #41 and deliberately thorough. A *test approach* is meant
to be the smaller thing that usually suffices, and right now nothing says what it
contains or where it lives.

##### What the industry means by the two words

Researched 2026-08-20, at the owner's instruction. Owner's own definition first:
*"test approach says things like — use this environment, use these tools, measure
these things against these criteria. Whereas a test plan is the detailed tests
with conditions and scripts."*

**The first half of that is the standard definition almost word for word.** ISTQB
glossary: a test approach is *"the implementation of the test strategy for a
specific project… the test design techniques to be applied, exit criteria and
test types to be performed."* Environment and tools, techniques, and what is
measured against what criteria — the same list.

**The second half is where our word has drifted**, and it is worth knowing
because `docs/3.x` is meant to travel. Three terms, not two:

| term | what the standards mean by it | ours |
| --- | --- | --- |
| **test strategy** | organisation- or programme-level: the test levels performed, and the testing within them. Generic, outlives any one project | we have never written one. `docs/3.3`'s testing sections *are* it, unnamed |
| **test approach** | the strategy applied to one project: environment, tools, techniques, test types, exit criteria | the thing D14 gates on |
| **test plan** | a **management** document — scope, approach, schedule, resources, risks, metrics, deliverables | not what we mean at all |

The detailed tests are none of those. In IEEE 829 they are the **test design
specification** (techniques, conditions, pass/fail criteria), the **test case
specification** (preconditions, inputs, expected results) and the **test
procedure** (the script). ISO/IEC/IEEE 29119-3 superseded 829 in 2013 and keeps
the split, folding the approach into the plan as a *test strategy* clause.

**So the approach is a section of the plan, not a lighter substitute for one** —
IEEE 829's test plan has *Approach* as its section 6. Which is exactly the shape
our own template already has, without anyone having planned it:
[`docs/templates/test-plan.md`](../../../templates/test-plan.md) §8 is called
**Approach**, and it asks *what runs and where · what is real and what is stubbed
· how time is manipulated · what state each test starts from*. The criteria half
of the owner's definition lives in §3 (outcomes) and §6 (refusals and successes).

That makes the "a test plan would satisfy the gate" clause exact rather than
generous: a test plan satisfies it **by containing it**.

##### The options, in that light

| option | |
| --- | --- |
| **the plan's §8, extractable** — environment · tools · what is measured against what criteria, written in the issue when there is no plan | one form, one vocabulary. A change that later grows a test plan pastes what it already wrote into §8 |
| a named short form of our own — what could go wrong · how we would see it · where it is judged | readable, and it invents a third structure alongside §8 and the standards' |
| a cut-down template beside the test plan | a second document to maintain, and a folder to file it in, for what is usually a paragraph |
| leave it to judgement | which is what we have now, and D14 just added a gate that cannot be checked against nothing |

**Recommended: the first**, written in the issue under the existing *what would
show it works* field rather than in a document of its own. The gate is then
answerable by looking at the issue: either the environment, the tools and the
criteria are stated or they are not.

Distinct from D15, which asks *where* a change is judged: this asks *what runs
there, and what would count as passing*.

**Answered 2026-08-21, by D17 and D18 between them.** D17 settled *what it is* —
the test design specification's §8, plus the criteria in §3 and §6: environment,
tools, and what is measured against what criteria. D18 settled *where it lives* —
with the project, as a document when the project justifies one and as text in the
issue when it does not. Owner: *"these can be text within the issue if they do
not justify separate documents."*

So the gate is answerable by looking at one place: the project owns a test
approach, and either it is written down or it is not. Nothing about the gate
changes with the size of the change; only the length of the answer does.

**One thing this exposes**, for the apply pass rather than for now: our test-plan
template is, by the standards' names, a test **design** specification with a
plan's title. Renaming it is probably not worth the churn, but `docs/3.3` should
say so in a line, so that a reader who knows the standard terms is not misled.

Sources: [ISTQB glossary: test approach](https://istqb-glossary.page/test-approach/) ·
[ISTQB glossary: test strategy](https://glossary.istqb.org/en_US/term/test-strategy) ·
[IEEE 829 test documentation](https://zetcode.com/terms-testing/ieee-829/) ·
[ISO/IEC/IEEE 29119-3](https://www.iso.org/standard/56737.html)

#### D5 · Does `main` get a ruleset? — **answered: yes**

**Decided 2026-08-20**, reviewing PR #184. Requiring CI's `check` job on `main`,
and nothing more. Still to do: create the ruleset, which may need a token
permission we do not have.

**The options as they stood, kept as the record:**

| option | |
| --- | --- |
| none | anything can be pushed, and nothing had gone wrong yet |
| **require the CI check** — *chosen* | a red push cannot land on `main` |
| require CI and the review checklist | and a pull request for every change, which the merge lane deliberately does not ask for |

**Agreed: require CI's `check` job, nothing else, and only after #184 merges.** It is the one gate whose answer is objective and whose
failure is expensive. Requiring a review checklist with one author is ceremony,
and requiring pull requests would undo the merge lane.

## Terminology: our words and the industry's

### D10 · The terminology recommendations — accept them? — **answered: accept, with three corrections**

Owner, 2026-08-20, on what else is open: *"for example the recommendations around
terminology."* Right — every entry below carries a recommendation and none has
been agreed, so the whole set is one unanswered question wearing nine hats.

Answering them one at a time is the wrong shape. **Accept the set, or name the
exceptions:**

| term | ours | recommendation |
| --- | --- | --- |
| release branch | version branch | **adopt** — universal, and ours adds nothing |
| release *train* | — | **decline** — it names a schedule we do not run |
| hermetic build | "builds a commit, never the working tree" | **use both** — the term once, our phrase thereafter |
| expand/contract · parallel change | — | **adopt** — we do it and have no word for it |
| build metadata | `+<sha>` | **adopt**, for the version discussion |
| parent issue · sub-issue | master issue, lead issue | **adopt** — *applied 2026-08-19* |
| blast radius | — | **adopt** — already in use |
| staging | rehearsal | **keep ours**, mention *staging* once — staging carries expectations we deliberately do not meet |
| living document · standing issue | ours, coined here | **keep ours** — defined in 3.3 and doing real work |
| preview | preview | **keep ours** — the same word and much the same thing: ours is per-branch too, but rebuilt on demand rather than standing |
| work package | chunk | **adopt** — *decided 2026-08-20* |
| programme · project · delivery | ours | **adopt** — the levels are already the standard terms. A delivery is recorded against its project, not as an issue of its own |

**Recommended: accept the set.** Two are already applied, the rest cost a
find-and-replace in the sweep, and the only one that changes behaviour rather
than vocabulary is *release train*, which is being declined.

**Answered 2026-08-20: accepted**, with three corrections the owner made in the
same breath, all of them now in the table above.

**One: the staging row named the wrong term.** The first column is the
*industry's* word and it read *rehearsal* — our word in both columns, which made
the row say nothing. The industry's word is **staging**.

**Two: what staging expects that rehearsal does not meet.** The row asserted the
mismatch without ever listing it, so the question was fair. Four expectations
come with the word:

| what *staging* is expected to be | what rehearsal actually is |
| --- | --- |
| **permanently up**, addressable at a known URL | brought up for a release and taken down after. Between releases there is nothing running |
| **a mirror of production's data**, or a scrubbed copy of it | production's *shape*, with its own data. We never copy players' games sideways |
| **where features are demonstrated and signed off** | where the **mechanism** is proved — migration, deploy, rollback, and anything needing production-like hardware. Features are judged in preview |
| **the last environment before production**, and therefore the place bugs are found | the last *gate* before production, and deliberately not the place we expect to find functional bugs — if one surfaces there, preview failed |

The standing criticism of staging — that mirroring production is a fool's errand,
because the mirror is never quite the thing and the difference is where you get
hurt — lands on the first two rows. It does not land on ours, because ours never
claims to be a mirror. That is precisely why the word is worth avoiding: adopting
*staging* would import an argument we are not having.

**Three: preview is per-branch after all.** Owner: *"ours is per branch initially
until we are ready to test the whole release, we can tear it down and rebuild it
to test whatever branch or build we want, although it is more efficient to test
branches in dev first to save build and CI time."* So the difference from the
industry's review app is not *what it points at* but *how many exist*: one stack,
rebuilt on demand at whatever ref is being looked at, rather than one per open
pull request standing simultaneously. The recommendation is unchanged — keep the
word — but the note attached to it was wrong and is corrected below.

**And the levels row now says *delivery*.** A delivery is recorded **against its
project**, not as an issue in its own right: the project is the thing with a
number, and what it delivered is a line in its record. This is the same shape as
D6's answer — the delivery log is a log, not a set of issues.

#### D8 · How much to cite — **answered: cite once, in the notes**

The trailing *open questions* section carried this, and it is still open. A named
practice a reader can look up is worth more than a paragraph of our own
reasoning — but `docs/3.3` is long, and #137 was about making it shorter to
consult.

| option | |
| --- | --- |
| **cite once, in the notes** | the term appears in the *what*; the source appears once in part 3, and nowhere else |
| cite at every use | findable anywhere, and it turns the runbook into a bibliography |
| cite nowhere | our vocabulary becomes private, which is the thing this document exists to prevent |

**Recommended: the first.** Part 3 is where a reader goes when they want to know
*why*, which is the same moment they want the source.

**Answered 2026-08-20: the recommended option.** The term appears where it is
used; the source appears once, in part 3.

#### D9 · Do *gate* and *check* mean different things? — **answered: yes — a gate refuses, a check reports**

We use *gate* for both **a check that refuses** and **a check that warns and
asks** — and #137's audit found `docs/3.3` describing the second as the first,
which is the evidence that the words are doing two jobs.

| option | |
| --- | --- |
| **gate refuses, check reports** | used strictly. `deploy.sh`'s nine gates refuse; `verify.sh` reports; the review checklist refuses; the tooling-on-`main` warning asks |
| one word, qualified in place | *"a gate that warns"* — accurate, and it puts the burden on every sentence |
| leave it | the audit already found one place where the ambiguity misled a reader |

**Recommended: the first**, and it costs a pass over `docs/3.3` in the same
change that applies the rest.

**Answered 2026-08-20: the recommended option.** Used strictly from now on: a
**gate** refuses and the work stops; a **check** reports and a person decides.
Every existing use of *gate* in `docs/3.3` is re-read against that in the sweep,
because #137's audit already found one that was a check wearing the other word.

#### D17 · Do we adopt the standard testing terminology? — **answered: yes**

Owner, 2026-08-20: *"we should adopt the standard terminology for testing. Test
Plan is a term that is often abused, and you are right in what it is supposed to
mean."*

Arising from D16's research. Our *test plan* is not what the standards call a
test plan, and the word is the most abused in testing precisely because everyone
uses it for whatever document they happen to have. Three renames and one term we
gain:

| what we have | what it is, in the standards' names | what happens |
| --- | --- | --- |
| `docs/templates/test-plan.md` — rules, conditions, outcomes, the matrix, scenarios, coverage both ways | a **test design specification**: techniques, conditions and pass/fail criteria | renamed, and its two worked examples with it — `41-user-deletion-*` and `25-rate-limiting-*` |
| §8 of that template, plus the criteria in §3 and §6 | a **test approach** | named as such, and it is what [D14](#d14--do-we-classify-the-process-a-delivery-must-go-through--answered-yes-derived)'s gate asks for |
| `docs/3.3`'s testing sections | a **test strategy** — the levels we test at and the testing within them, holding across every change | named as such. **This is the term we gain**, and it is the one that pays |
| *(nothing)* | a **test plan** — scope, schedule, resources, risks for one project's testing | we do not write one and should not start. One developer, no schedule to coordinate |

**The gain is the test strategy.** Once `docs/3.3` can say *this is the test
strategy* — what a unit test is for here, what belongs in an e2e test, what only
rehearsal can judge — every per-change document stops restating it and says only
what is different about this change. That is #137's complaint (3.3 is long)
answered from the vocabulary end rather than by cutting text.

**And the fourth row is a real decision, not an omission.** A test plan
coordinates people and dates. There is one developer and no schedule, so writing
one would be ceremony — but *saying* we do not write one is different from not
having heard of it, and the difference is exactly what this row records.

**Cost**: three file renames, the references in
[`docs/templates/README.md`](../../../templates/README.md) and `docs/3.3`
(§2.4.2 *How a test plan is built*, and the document-ownership row in §2.9.4.1),
and a heading pass over 3.3's testing sections. All inside the apply pass.

#### release branch · release train

**Standard**: a branch cut for a release, with scope frozen at the cut; changes
merge into it, and it ships. A *train* is the scheduling variant — it departs on
time and unready features get off.

**Ours**: "version branch", "version-named branch".

**Recommend: adopt.** "Release branch" is universal and ours adds nothing. The
train metaphor is worth adopting too, because it names the de-scoping rule we do
not yet have (#135): the train leaves, the feature waits for the next one.

#### hermetic build

**Standard**: a build that depends only on declared inputs, so it can be
reproduced from source control alone.

**Ours**: "fresh-checkout principle" — deploys build a throwaway `git worktree`
at the target commit, never the working tree.

**Recommend: use both.** "Hermetic" is the findable term; our phrase says what we
actually do, which is narrower and clearer. Lead with hermetic, keep the
worktree sentence.

#### expand/contract  (also: parallel change)

**Standard**: schema changes made in two deployable steps so the old and new
code both work against the intermediate state.

**Ours**: unnamed — we describe migrations running as their own step before the
container swap.

**Recommend: adopt.** We have the practice and no word for it, which makes it
hard to reason about. Worth noting we currently do the *sequencing* half but not
the two-phase half — naming it makes that gap visible.

#### build metadata

**Standard**: semver §10 — the `+<anything>` suffix, ignored in precedence.

**Ours**: "the `+sha`", "build id".

**Recommend: adopt** for the version-number discussion, where the precedence
rule matters. "Build id" is fine everywhere else.

#### parent issue  ·  sub-issue

**Standard**: GitHub's own vocabulary for the feature — a *parent issue* with
*sub-issues*, with progress rolled up automatically.

**Ours**: `docs/3.3` said **master issue** until PR #185; conversation on
2026-08-19 used **lead issue**. Both are gone.

**Recommend: adopt**, decided 2026-08-19. Using the tool's own word means the
document, the API and the UI all say the same thing, and it retires "master".
Owes one edit to 3.3's *Where a document lives*.

#### blast radius

**Standard**: how much breaks, and how visibly, if a change is wrong.

**Ours**: unnamed until 2026-08-15, when it went into `docs/3.4` as "grade by
blast radius, not by category".

**Recommend: adopt.** Already done.

---

#### rehearsal  (vs staging)

**Standard**: *staging* — an environment resembling production, used before
release.

**Ours**: *rehearsal* — a production clone whose purpose is to prove the release
**mechanism** and to run anything needing production-like hardware.

**Recommend: keep ours, mention staging once.** "Staging" carries four
expectations we deliberately do not meet — permanently up, mirroring production's
data, where features are signed off, and where bugs are expected to surface —
each set against what rehearsal actually is in D10 above.
The standing criticism of staging (Charity Majors: mirroring production is a
fool's errand) lands on that version and not on ours. Our word says what it is *for*,
which is the distinction that makes the preview/rehearsal split work. Say
"rehearsal (a staging environment, but see below)" once, then use ours.

#### ~~lane~~ → three attributes

**Superseded** by [Categorising changes and
releases](#classifying-a-change-type-route-release)
below. The short version: `merge`, `fasttrack`, `minor`, `major` and
`emergency` are one word answering three different questions, which is why
mapping a real change onto the list takes an argument every time.

#### living document · standing issue

**Standard**: none in common use.

**Recommend: keep ours.** Coined here, defined in 3.3, and doing real work.

#### preview

**Standard**: "preview environment" / "review app" — the same thing, and ours is
per-branch too.

**Recommend: keep ours.** The difference worth noting is **how many exist at
once**: the industry's version usually stands one per open pull request,
automatically, for as long as the branch lives. Ours is a single local stack torn
down and rebuilt at whatever ref is being looked at — a branch early on, the
release branch once there is a whole release to judge. Cheaper to run and
cheaper to reason about, at the cost of only one thing being previewable at a
time; branches are usually tried in dev first, where nothing has to be built or
run through CI.

---

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
| **change enablement** | ITIL — normal / standard / emergency changes, with post-implementation review | we have the decision points exactly, under our own words — see [Categorising changes and releases](#classifying-a-change-type-route-release) |
| **quality gate** | an automated check that blocks progress | our "gate" — same word, already aligned |

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

### How an action is recorded

**Decided 2026-08-19**, from #181. An **action** is an unchecked `- [ ]` in an
**issue** body, under an `Open actions` heading, prefixed `(Steve)` or
`(Claude)`.

The issue body is the only surface that carries state: an issue holds one bit,
open or closed; a comment is append-only, so it can never be marked done; a pull
request body freezes at merge. A checkbox can be ticked, GitHub counts it, and an
item promotes to a full issue in one click when it turns out to be real work.

**The same syntax in a pull request body is not an action** — it is the review
checklist, which is the review itself.

**The boundary with a sub-issue:** if it needs a branch, it is an issue. If it is
a decision, a lookup or a small edit, it is a checkbox. A checkbox that grows a
design discussion has told you it should have been an issue.

`./scripts/actions.py` gathers them across every open issue, grouped by
workstream, so the record can stay where the argument is without becoming
impossible to find.

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

**Where a document lives is `docs/3.3` §2.9.4.1**, applied and enforced by
`check-docs.sh`. It is not repeated here: the table below covers only what that
section does not, because a second copy of a rule is the copy that goes stale.

| path | holds |
| --- | --- |
| `docs/diagrams/` | `.mmd` sources and their rendered `.svg` — edit the source, re-render, commit both |
| `scripts/` | the tools, listed in `docs/3.0` |
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

#### D7 · Should `docs/changes/issues/` be renamed, and to what? — **answered: B, nested**

Owner, 2026-08-20: *"We should rename the issues folder as workstream, but
presumably that will be done as part of applying the glossary."* Yes to the
second half — it is an apply-the-glossary task, and it moves files, so it wants
doing once.

**But the folder does not hold only workstreams today.** It holds
`179-process-workstream/` — a workstream's parent — and
`174-logs-and-backups/` — a plain issue's design note, for an issue that belongs
to *production operations* and is not a workstream at all. Renaming to
`workstreams/` would file that second one under a claim that is not true.

| option | | |
| --- | --- | --- |
| **A. keep `issues/`** | folders named for the issue that owns them, whatever level that issue is | accurate today, and says nothing about the levels |
| **B. rename to `workstreams/`, and nest** | `workstreams/179-process/`, with projects and issue notes inside | mirrors the model exactly, and every document has one path that reflects what owns it |
| **C. three folders** | `workstreams/` · `projects/` · `issues/` | most precise, and three places to look instead of one |

**Decided 2026-08-20: B.** Owner: *"yes, B. And it makes us think about which
workstream an issue is in."* Which is the argument I had missed — the structure
does not merely *record* the classification, it **forces** it, at the moment a
document is created and while the answer is still cheap. Same principle as the
issue form asking for type and route at the moment an issue is raised.

The shape:

```text
docs/changes/
  workstreams/
    process-and-tooling/          the capability, not the issue number
      glossary.md                 documents the workstream owns
      process-review.md
      179-…/                      an issue's own documents, where it has any
      projects/
        179A-…/                   a project's documents, testing included
    production-operations/
      174-logs-and-backups/
        design.md
```

**Named for the capability, not for a parent issue**, because a capability may
have no parent issue yet — nine of the ten do not. A folder needs no issue to
exist, and naming it for one would block filing behind creating ten issues
nobody has asked for.

The costs stand and are worth restating: deeper paths, a move when an issue's
workstream changes — rare — and one more round of broken links, which is the
argument for doing **every** folder move in a single change.

## Background: how ITIL handles tooling, monitoring and instrumentation

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

### An issue's changes live in one place

**Decided 2026-08-20.** Owner: *"No issue should have changes in main and changes
in a branch, it invites mistakes."*

Right, and today produced the mistake to prove it: #155 had the glossary on
`main` and the issue form on a branch, so *"where is #155's work?"* had two
answers, and a document that should never have been behind a review spent an
afternoon there.

**So an issue is either standard — everything on `main` — or normal —
everything on a branch until it merges.** The [standard-change
criteria](#standard-changes-what-may-go-straight-to-main) decide which, and they
decide it for the **issue**, not for each commit.

**When an issue turns out to be both**, it is two issues. That is the same rule
as *one change, one type*, arriving from a different direction: #155's decisions
are standard and belong on `main`; creating the issue form is normal and belongs
on a branch of its own, raised when the decision is made. Until then the form
is text in this document, which is a proposal rather than a change.

### Standard changes: what may go straight to `main`

**Decided 2026-08-20.** Owner: *"sometimes we say documents should be in a branch
(because they are a major new version, and people should not consult them until
approved) and sometimes we make the changes in main (because they are living
documents, it is a quick update, or otherwise we want the changes to be
immediately visible). That ties into the authorised point in the ITIL change
type. Subject to certain criteria changes can be made directly in main with
limited process — they are pre-approved."*

That is ITIL's **standard change** exactly: pre-approved by the *procedure*, so
no authorisation is sought for the instance. It answers a question 3.3 has been
answering by feel — *when is a branch called for?* — with a criterion instead.

#### Straight to `main` — pre-approved

A change is standard when **every** one of these holds:

| | |
| --- | --- |
| **it records a decision, rather than making one** | the glossary noting what was agreed; a release log entry |
| **or it corrects an error** | a typo, a broken link, a stale reference, a lint failure |
| **or it is additive reference** | a row for a tool that already exists |
| **a defect reaches developers only** | route is *never leaves the repository*, and nobody is mid-way through following it |
| **and it is reversible in one commit** | no migration, no third party, nothing already read and acted on |

#### A branch and a review — normal

Any **one** of these makes it a normal change:

| | |
| --- | --- |
| **it states or changes a rule** | somebody may follow it while it is still provisional |
| **it is a major revision** | the half-updated state misleads — `docs/3.3`'s restructure was 2,300 lines of it |
| **a defect reaches users** | route is *in the artifact*, *carried by the deploy*, or applied to production |
| **it is live at merge with a blast radius** | a workflow, a shared script, a template everybody copies |
| **the owner asked to see it first** | which needs no other justification |

#### Tested against today

| change | went | correct? |
| --- | --- | --- |
| the glossary recording D3, D4, D6 | `main` | yes — records decisions, developer-only, reversible |
| five tool rows in `docs/3.0` | `main` | yes — additive reference |
| the blank-line and lint fixes | `main` | yes — corrections |
| `docs/3.3` restructured into three parts | branch, PR #178 | yes — a major revision |
| `check-docs.sh` and the docs workflow | branch, PR #184 | yes — live at merge, and CI runs it on every push |
| the issue form | branch, PR #187 | yes — live at merge, changes how every issue is raised |
| **the glossary, this afternoon** | **branch, PR #187** | **no** — it was a living document behind a review, which is the drift this rule prevents |

**This entry is itself a standard change**: it records a decision the owner just
made, a defect in it reaches nobody but us, and reverting it is one commit. So it
went straight to `main`, which is the rule demonstrating itself.

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

## Where each part stands

| section | state | lands in |
| --- | --- | --- |
| [The levels](#the-levels-programme-workstream-project-work-package-release) | **decided** | `docs/3.3`, the change lifecycle |
| [Workstreams](#workstreams-the-capabilities-we-maintain) | **decided** — the list is agreed; the assignment is not applied | `docs/3.3`, and a parent issue or label per workstream |
| [Classifying a change](#classifying-a-change-type-route-release) | **decided**, except the form's two gaps | `docs/3.3`'s lane table, and `.github/ISSUE_TEMPLATE/change.yml` |
| [Workstream assignment](#every-open-issue-on-all-three-axes-and-a-workstream) | **decided**, not applied — 47 issues to file | GitHub: a label or parent issue per workstream |
| [Projects: phases and gates](#projects-phases-and-gates) | **decided**; the `phase:` labels exist | `docs/3.3` |
| [Delivery](#delivery-releases-applications-and-merges) | **decided** | `docs/3.3`, and #156's delivery log |
| [Process and authorisation](#process-and-authorisation-what-a-change-must-pass-through) | **decided**, except D16 — what a *test approach* is | `docs/3.3` |
| [Terminology](#terminology-our-words-and-the-industrys) | **decided** — the set is accepted, with three corrections | wherever each term is used |
| [How the process is managed](#how-the-process-is-managed-github-folders-scripts) | **decided**; the `docs/3.0` rows are **applied** | a new section in `docs/3.3` |
| [Background: ITIL](#background-how-itil-handles-tooling-monitoring-and-instrumentation) | reasoning only; changes nothing on its own | the notes behind the lane rule |
| *parent issue* | **applied** 2026-08-19 | `docs/3.3` — PR #185 |
