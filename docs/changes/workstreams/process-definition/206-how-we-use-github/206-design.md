# 206 — How we use GitHub

**Project #206**, under the process definition workstream (#188).
`phase:scope-and-design`. Nothing here is decided.

**Method**, owner 2026-08-25: *"I think we need to list the technical options
for individual things, like storing a field. Then put together complete options
to compare."* So Part 2 lists each choice on its own, and Part 3 assembles the
ones that hang together. Several constrain each other, which is why they cannot
be decided one at a time.

## Part 1 — What this project is about

### The requirements it carries

| | | from |
| --- | --- | --- |
| **R1** | approving a change should work wherever the owner can type it | #197 |
| **R2** | approving and merging should be one act | #198 |
| **R3** | Claude's pull requests should not be authored by the owner | #171 |
| **R4** | every issue attribute should be stored once, somewhere a tool can read it | #216 |
| **R5** | a release's notes should have exactly one home | #217 |

### The idea that makes them one project

Owner, 2026-08-25: *"we should distinguish storing data (each item should be
stored once) and reporting data (many reports could include the same information
in different formats for different purposes). So it is not a choice between
GitHub Project report and our own pipeline report, but it is about how data is
stored for each issue."*

**Many reports may read the same data.** A Project board, `pipeline.md`,
`roadmap.sh` and `actions.py` can all render the same facts for different
purposes, and none of that is in tension. **The tension is only where two of
them store an answer.**

Every requirement here is a case of that:

| | the duplication |
| --- | --- |
| R1, R2 | a review verdict kept in a label we maintain, when GitHub knows it natively |
| R4 | a size kept in prose, where nothing can read it — stored *nowhere*, which is the same failure inverted |
| R5 | release notes in `docs/4.9`, and in GitHub too if Releases were adopted |
| R3 | not duplication, but the reason R1 exists at all |

### Why the review machinery exists, which is the root

`gh` runs under the owner's token, so **every pull request Claude opens is
authored by the owner**, and GitHub refuses self-approval:

> Pull request authors can't approve their own pull requests

The parser in `docs.yml` was not chosen over GitHub's native review. **The
native one was unreachable**, for a reason that has nothing to do with review.

### Where each attribute is stored today

| attribute | stored in | queryable |
| --- | --- | --- |
| type | a label | yes |
| **release** | **the milestone** | yes |
| workstream | the sub-issue parent | yes |
| route | nowhere — derived from the artefact list (D26) | no, deliberately |
| **size** | free text in a triage comment | **no** |
| **impacted artefacts** | free text, then a project body | **no** |
| review verdict | the `approved` label, set by a comment parser | yes, and **duplicated** |

## Part 2 — The individual choices

Each is a decision on its own. Part 3 combines them.

### 2.1 Where an issue attribute is stored

| option | | |
| --- | --- | --- |
| **A. a label** | works today; free; queryable by `gh` and the API | one label per value, so a five-value attribute is five labels. No ordering, no numbers, and the list grows without structure |
| **B. a milestone** | already how `release` works | **one per issue**, so exactly one attribute can use it. `deploy.sh` depends on this one |
| **C. the sub-issue parent** | already how `workstream` works; structural, so it cannot disagree with itself | one parent, so again a single attribute |
| **D. a Project single-select field** | made for this; sortable, filterable, groupable; available on a **personal** repo | the value lives in the Project, not the issue — an issue outside the Project has no value at all |
| **E. an issue field** | on the issue itself, where it belongs | **organisation only** |
| **F. free text in a comment** | costs nothing, says anything | not queryable, and drifts: `prod-tooling`, `prod tooling`, `production tooling` |

**Today**: type = A, release = B, workstream = C, size and artefacts = F.

**The constraint that does not move**: `deploy.sh` reads the milestone to decide
what a deploy closes, so `release` stays B whatever else changes.

#### 2.1.1 A fine-grained token cannot read a user-owned Project — measured

**This is the constraint that reshapes the options**, and it is not in any of
the option descriptions above.

`gh api graphql` returns `FORBIDDEN` for `projectsV2`. The obvious fix — add the
permission — **is not available**: the fine-grained token's *Account permissions*
list has no **Projects** entry. Checked on 2026-08-25 by searching the picker
for `project`, which returned nothing. Alphabetically it would sit between
*Profile* and *SSH signing keys*, and there is nothing there.

Fine-grained tokens grant Projects at **organisation** level. A **user-owned**
Project — which is what `github.com/users/SteveStyle/projects/1` is — has no
corresponding permission.

| to read a user-owned Project | |
| --- | --- |
| **fine-grained PAT** | **not possible** |
| **classic PAT** with `read:project` | works — and classic tokens are all-or-nothing across the whole account, where today's token is scoped to one repository |
| an **organisation**-owned Project | fine-grained works, and per-repository scoping is kept |

**So 2.1D is not the cheap middle option it appears to be.** Storing anything in
a user-owned Project means either **widening the token to everything the account
owns**, to solve a reporting problem — or creating an organisation, which is
2.2B.

**And it applies to reporting, not only to storing.** The board that already
exists cannot be read by our tooling at all today, so even "leave the data where
it is and just render it from a Project" is blocked by the same wall.

| | needs |
| --- | --- |
| inspecting the board while designing | a classic token, or an org |
| `pipeline.py` reporting from Project fields | the same, **permanently** |
| trying fields out before deciding | write as well, and a **throwaway project** rather than the real board — the same shape as the read PAR made for a restore drill and deleted after |

**2.1A costs none of this.** A label needs nothing the token does not already
have, which is a point in its favour that was invisible until this was measured.

### 2.2 Who owns the repository

| option | | |
| --- | --- | --- |
| **A. a personal account** | today. Nothing to do | no issue fields; a second user is an unrelated account |
| **B. an organisation** | issue fields become available; a second user is a member with a role; teams and per-repo permissions | a migration, and `gh`/token/CI settings move with it. Free for what we need |

**Two requirements point here independently** — R4 wants issue fields, R3 wants a
second user — which is why they are in one project. Neither *requires* an
organisation: 2.1D and 2.1A work without one, and a second personal account
works without one.

### 2.3 How many GitHub users

| option | | |
| --- | --- | --- |
| **A. one** | today | every PR is authored by the owner, so **native Approve is impossible**, and attribution relies on Claude remembering a footer |
| **B. two** | native review works; attribution becomes structural rather than remembered | a second account, its token and permissions; and the commit trailer means something different once the author really is different |

### 2.4 How a review verdict is recorded

| option | | |
| --- | --- | --- |
| **A. our label, set by the comment parser** | today; works from anywhere a comment can be typed | a second store for what GitHub knows; **fails silently** in four of five places a verdict can be typed (#197) |
| **B. GitHub's native review state** | one store; every client; no parser | needs 2.3B, and has no equivalent of `/prov` |
| **C. both** | — | **rejected on sight**: two stores for one fact is the thing this project exists to stop |

**`/prov` is the only outcome with no native equivalent**, and the owner closed
that gap on 2026-08-23: *"in the absence of provisional approval, I can use
[request] changes and approve when you say they are done."* Arguably better than
`/prov`, which merges work he has not seen.

### 2.5 Where release notes live

| option | | |
| --- | --- | --- |
| **A. `docs/4.9` only** | today; versioned, reviewed, read from `origin/main` | no notes on the tag itself; nothing on GitHub's Releases page |
| **B. GitHub Releases only** | notes on the tag; generated from merged PRs; a free-text field | a second surface to keep current, and it is not in git — so it needs a row in `docs/4.8` |
| **C. `docs/4.9` is the store, a Release is generated from it** | one store, two renderings — exactly the storing/reporting split | something has to generate it, most likely `deploy.sh` |

### 2.6 What applies an answer once it is decided

**The gap nothing currently owns**, seen three times:

| | |
| --- | --- |
| **D32** | the requirement form's dropdown answers do not become labels — *parked* |
| **#215** | applying a triage takes four manual actions; two were missed |
| 2026-08-25 | folding takes three; the third was missed on five issues |

| option | | |
| --- | --- | --- |
| **A. by hand** | today; nothing to build | it is forgotten, demonstrably, and the report is the only thing that notices |
| **B. a workflow reads the form and applies labels** | D32's original proposal | only covers raising, not triage or folding |
| **C. a workflow reads the triage comment's table** | covers the case that actually failed | parsing a comment is fragile — though the standard reply now lists valid values, which is what makes it possible at all |
| **D. fewer places to apply it** | if an attribute lives in one place, there is less to keep in step | not an option on its own; a consequence of 2.1 |

## Part 3 — Complete options

Assembled from Part 2, in increasing order of change. Each is internally
consistent; the point of writing them out is that **choices constrain each
other** and a menu cannot show that.

### Option 1 — Stay as we are, and fix the parser

`2.1` unchanged · `2.2A` · `2.3A` · `2.4A` · `2.5A` · `2.6B or C`

Fix #197 so the command works from a review as well as a comment. Everything
else stays.

| | |
| --- | --- |
| **for** | smallest possible change; no migration; nothing to learn |
| **against** | R4 unmet — size and artefacts stay unqueryable. R2 unmet. Keeps a parser that duplicates what GitHub knows, and the #197 defect is the second silent failure in that job this month |

### Option 2 — Add Project fields, stay personal

`2.1D for size` · `2.2A` · `2.3A` · `2.4A` · `2.5A or C` · `2.6C`

A Project becomes the store for attributes labels handle badly. Type, release
and workstream stay where they are.

| | |
| --- | --- |
| **for** | R4 met without a migration; the table view is the spreadsheet asked for; the sub-issues progress column is a live workstream rollup we do not have |
| **against** | a value in a Project is not on the issue — an issue outside the board has none, and something must keep the board complete. R1, R2, R3 all unmet |
| **and the one that may kill it** | **our tooling cannot read a user-owned Project at all** (2.1.1). This option therefore requires a **classic token**, widening access from one repository to everything the account owns — to solve a reporting problem. That is a worse trade than it looked before it was measured |

### Option 3 — Move to an organisation

`2.1E for size and any new attribute` · `2.2B` · `2.3B` · `2.4B` · `2.5C` · `2.6B`

The repository moves to an organisation; Claude gets an account in it; native
review replaces the parser; issue fields hold what labels handle badly.

| | |
| --- | --- |
| **for** | every requirement met. The parser, the `approved` label and a whole class of silent failure are **deleted** rather than fixed. Attribution becomes structural. And it is the **only** way to store an attribute outside a label without widening the token (2.1.1) |
| **against** | the largest change, and the only one with a migration. Two accounts to manage. `/prov` is lost and replaced by an extra lap. Nothing here is urgent, and this is not a small step |

### Option 4 — Organisation, but keep our own review

`2.2B` · `2.3A` · `2.4A` · rest as Option 2

An organisation purely for issue fields, with the review machinery untouched.

| | |
| --- | --- |
| **for** | R4 met on the issue itself rather than in a Project |
| **against** | pays for the migration and collects only one of its benefits. Hard to argue against Option 3 once the org exists |

## Part 4 — What the design must answer

1. **Which option**, or which parts of which.
2. **What happens to `pipeline.py`** — it derives, so it cannot drift; a Project maintains, so it can. Both may live, but only if it is written down which is the store.
3. **Whether `/prov` survives** in some form, or the extra lap is accepted.
4. **What 2.6 does**, because every option leaves *something* applied by hand,
   and that is the failure that keeps recurring.
5. **Whether an organisation is worth it on its own merits**, separately from
   the two requirements that happen to want one.
6. **Whether implementation needs a branch**, which the chosen option decides
   rather than the project. Owner, 2026-08-25: *"no need for a branch yet. I am
   not sure if we will want one for development."* §2.2's test says a branch is
   needed only when the old version is required in the interim — so changing
   `docs.yml`'s `commands` job while still relying on it to approve things would
   need one, and adding a Project field would not. **This design note does not**,
   which is why it is on `main`.

## Part 5 — Impacted artefacts

*Provisional until the design is agreed.*

| artefact | new or modified | route |
| --- | --- | --- |
| `.github/workflows/docs.yml` — the `commands` job | modified, or **deleted** | repository |
| `scripts/actions.py` — reads the `approved` label | modified | repository |
| `scripts/pipeline.py` | modified, or deleted | repository |
| `docs/3.6` §2.18 and §3.8 | modified | repository |
| `docs/4.8-artefacts.md` | modified — a configured Project, an organisation and a second account are all artefacts under change control | repository |
| `docs/4.9-delivery-log.md` | modified, if 2.5C | repository |
| the GitHub Project, its fields and workflows | new or modified | **service** |
| an organisation, if 2.2B | **new** | **service** |
| a second GitHub account and its token, if 2.3B | **new** | **service** |
| `.githooks/commit-msg` — the `Co-Authored-By` trailer | modified, if 2.3B | repository |

## Part 6 — Test approach

*To be agreed with the design.* What must be shown whichever option is chosen:

- the owner can approve from **every** client he uses, or is told plainly that a
  route does not work. **No command fails silently** — that is the defect, not
  which box works
- every attribute has **one** home, and it is written down which
- a report can show size, which today it cannot
- release notes exist in exactly one place
- a triage applied incompletely is **noticed** — by a check, or by the report
  disagreeing, but not by chance
- nothing stores change history. Owner, 2026-08-25: *"change history must be
  derived from git"*
