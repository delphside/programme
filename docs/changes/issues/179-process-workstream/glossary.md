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

## Decisions awaiting your agreement

Owner, 2026-08-20: *"A lot of the actions can become decisions in the glossary,
with options and recommendations."* So they are here, as questions rather than
as *"(Steve) decide whether…"* scattered across issues — each with what the
options actually are and what I would do.

A decision made here is **decided** in the section it belongs to, and then
applied to the numbered documents in one pass.

### D1 · Does the lane become three attributes?

**The question.** Today one milestone answers three questions: how a change is
authorised, how it reaches production, and what carries it to users.

| option | |
| --- | --- |
| **keep the lane** | one label, and the arguments recur — five framings in a day, and #134 decided against the written test |
| **three attributes as labels** | `type` (have it) · `route` · `release`. Explicit, and four new label families to maintain |
| **three attributes via an issue form** | the same three as dropdowns when an issue is raised, landing in the body where the tooling can read them |

**Recommended: the issue form.** It puts the question at the moment the answer is
cheapest — when the issue is written — and it needs no new labels. It also gives
issue #160 something concrete: this is GitHub replacing something we would otherwise
hand-maintain.

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

#### The four axes, defined

Owner, 2026-08-20: *"each of these three axes needs a table with definitions.
Workstream as well."* Four tables, one per axis, each value defined rather than
listed.

##### type — what the change is

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

##### route — how it reaches its consumer

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
| **never leaves the repository** | nothing is sent anywhere; it is live when it merges | `docs/`, `scripts/` we run locally, CI config, tests | the merge lane |

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

> **Where several apply: the artifact beats the deploy, the deploy beats the
> host.** Pick the one that decides the risk. A file in the repository is repo
> route whatever executes it — otherwise every CI change becomes a service
> change.

##### release — what carries it to users

| value | what it means | which milestone closes it |
| --- | --- | --- |
| **nothing — live at merge** | the merge lane: it reaches its consumer when it lands on `main` | none. The commit says `Closes #N`, because nothing else will |
| **a patch, on its own** | shipped alone, usually a fix — the fasttrack | the patch version's milestone |
| **grouped into a minor** | rides with other changes in a `0.x.0` | that release's milestone |
| **grouped into a major** | rides in a `x.0.0` — structural, or a breaking wire change | that release's milestone |
| **not decided yet** | nobody has scheduled it. **The honest answer for most of the backlog** | none, until it is scheduled |

##### When the release is *nothing* — what to do, and how you know it is done

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

##### workstream — which capability it belongs to

The ten are defined in [Capability
workstreams](#capability-workstreams) below, with what each covers and the two
rules that keep the list clean. A workstream is a **capability**, worked on
indefinitely — not a bag of issues that arrived in the same week — and every
open issue has one, which is the test that list had to pass.

#### The routes, and the tie-break

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

#### Twenty real issues, run through the three questions

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

#### What the test found

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

### D2 · Do we adopt capability workstreams, and when?

| option | |
| --- | --- |
| **adopt in one pass** | assign all 47 open issues, then keep it true |
| **adopt as issues arise** | new issues get one, old ones do not |
| **do not adopt** | keep grouping by whatever arrived together |

**Recommended: one pass.** A partial taxonomy still has to be searched, so the
half-done version costs what the whole one costs and delivers nothing. It is an
hour of filing, once.

### D3 · Do project phases stay, and where do they apply? — **answered: delivering workstreams only**

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

### D4 · Is the post-implementation review built, and how? — **answered: yes, as a lessons-learned review**

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

### Route is the join between an issue and a release

**Owner, 2026-08-20: *"I guess route ties issues and releases together."*** That
is the framing, and it is worth stating before D6 rather than discovering it
inside it.

An issue's other two axes describe the issue: *type* says what it is and what it
owes, *workstream* says which capability it belongs to. Neither says anything
about production. **Route does** — and in saying how a change reaches
production, it decides whether a release exists at all, what kind, and what
counts as done:

| route | is there a release? | what the record is |
| --- | --- | --- |
| in the artifact · carried by the deploy | **yes** — versioned, tagged, smoke-tested, closing a milestone | a release entry |
| applied on the host · applied to a service | **no**, but production changed | a dated entry with **no version** |
| never leaves the repository | no, and production did not change | the commit |

So the release log's shape is not a separate design: it falls out of the route
values, one entry-kind per class. If a new route ever appears, the log gains a
kind — which is a good test of whether the route is real.

### D7 · Should `docs/changes/issues/` be renamed, and to what?

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

**Recommended: B**, with the caveat that it is the most work. It is the only one
that makes the folder tree say what the levels say — and since **every issue now
has a workstream** (D2), every document can be placed under one without a
judgement. It also removes the question *"is this folder's issue a workstream?"*,
which is the ambiguity A quietly carries.

The cost is real: deeper paths, a move whenever an issue's workstream changes —
which should be rare — and one more round of broken links, which is the argument
for doing every folder move in the same change.

### D6 · What is a release, and what gets logged as one?

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

#### What gets logged

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

#### The part that is not derivable

Version, date, commit and contents all come from tags and milestones. **Outcome
does not**, and it is the column worth having: *"went live and was wrong"* is
what makes 0.6.0's entry useful, and no tag knows it. That is #156's
generated-skeleton-plus-a-written-line, arrived at from the other end.

### D5 · Does `main` get a ruleset? — **answered: yes**

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

### A review has three outcomes

**Decided 2026-08-20.** Owner: *"I need to say 'approved', 'approved with
changes', 'change and re-review'. I guess we don't need 'reject'."*

| outcome | label | what happens next |
| --- | --- | --- |
| **approved** | `approved` | Claude merges |
| **approved with changes** | `provisionally-approved` | Claude makes the noted changes **and merges** — no second review |
| **change and re-review** | neither | Claude changes it and hands it back |

The middle one is most reviews, and without it each of them costs a lap whose
only purpose is to confirm what was already agreed. There is no *reject*: a
change that should not happen is a closed pull request and a comment saying why.

## Where each part stands

| section | state | lands in |
| --- | --- | --- |
| [The four levels](#the-four-levels-and-what-each-is-called) | **decided** | `docs/3.3`, the change lifecycle |
| [Project phases](#project-phases) | **decided**, except the last | `docs/3.3`, and the `phase:` labels already exist |
| [Capability workstreams](#capability-workstreams) | **candidate** — the list is agreed, the adoption is not started | `docs/3.3`, and a parent issue or label per workstream |
| [Decisions awaiting your agreement](#decisions-awaiting-your-agreement) | **D1–D4 open, D5 answered** | each into the section it belongs to, then `docs/3.3` |
| [Categorising changes and releases](#categorising-changes-and-releases-three-attributes-not-one-lane) | **candidate** — the decision is D1; #154 is closed and folded here | `docs/3.3`'s lane table, and new labels or an issue form |
| [How ITIL handles tooling](#how-itil-handles-tooling-monitoring-and-instrumentation) | **decided** as reasoning; changes nothing on its own | the notes behind the lane rule |
| [How the process is managed](#how-the-process-is-managed-github-folders-scripts) | **decided**; the `docs/3.0` script rows are **applied** in PR #184 | a new section in `docs/3.3` |
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

**Ours**: `docs/3.3` said **master issue** until PR #185; conversation on
2026-08-19 used **lead issue**. Both are gone.

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
| **route** | *in the artifact* · *carried by the deploy* · *applied on the host* · *applied to a service we use* · *never leaves the repository* | how it reaches its consumer, and which environment it changes |
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
| **journald retention drop-in** (#174) | prod-tooling | applied on the **production** host | none — document it, close by hand |
| **OCI alarms** (#136) | prod-tooling | applied to a service, for **production** | none — same |
| **rehearsal DNS** (#147) | prod-tooling | applied to a service, for **rehearsal** | none — same, and it changed no production service at all |
| `.env` on the VM | prod-tooling | applied on the **production** host | none — same |
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
