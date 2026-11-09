<!-- markdownlint-disable-file MD041 -->
<!--
**Claude writes it; the owner reviews it.**

**Where:** a section of the issue body when the project has no other
documents, otherwise this file in its folder, pointed to from the body
(docs/1.2). Either way the body carries section 6's lessons under
`## Lessons learnt`. When the review is in the body, section 6 takes that title
without its number, and the review's other headings sit one level below the
body's. A work package that delegates its lessons writes `Delegated to #P`
there, `P` being the parent's number (docs/1.2).

**When:** once the project's last delivery is live and has been used. Wait a
week, so the failures surface.

The findings go to the next weekly digest as a note,
and a finding that needs a change also takes a pre-approved change, a
requirement or a project
([1.2](../1.2-change-lifecycle.md#where-a-possible-change-goes)).

Placeholders: `#N` is the project's number; the date is ISO 8601,
`2026-10-17`.

Replace each prompt with its answer. Delete these comments as you go.
-->

# Post-deployment review: *project*

Project: `#N` · deliveries: *milestone or `main`, each* · reviewed: *date*

## 1. Was the intended scope delivered?

<!-- The scope as the project issue fixed it, compared with what is live, item
by item, with anything dropped or deferred named as such. -->

| In scope | Delivered | Note |
| --- | --- | --- |
| | | |

**Anything deferred:** where did it go — a pre-approved change, a requirement,
a project or nowhere? Record "nowhere" as such.

## 2. What happened that was not planned for?

<!-- Surprises, in both directions. A thing that turned out easier belongs here
as much as a thing that broke. -->

## 3. Why — what was the cause?

<!-- For each surprise: the mechanism, not the blame. Prefer "the check ran
only when someone looked" to "somebody forgot to check". -->

## 4. What happens next?

<!-- Every finding is an action or a deliberate non-action. An observation with
neither is a note nobody will read again. -->

| Finding | Pre-approved change, requirement or project | Or why no change |
| --- | --- | --- |
| | | |

## 5. Areas to consider

<!-- Prompts, not a checklist to tick — most will not apply. Each has cost the
programme something before. -->

- **Scope** — did it change mid-project, and was the change recorded where the
  scope was fixed?
- **The milestone** — did anything settle with the milestone that had not
  shipped (delphside/tile-lite-elite#67)? Tile Lite Elite's deploy advances each
  project in its milestone, except a parent, to `Post-deployment`.
- **Testing** — was anything marked deferred and then released anyway? Did the
  tests derive from the rules, or from the code they were testing?
- **Documentation** — is any numbered document now wrong? Did a rule end up in
  two places?
- **The deploy itself** — were gates skipped, was a rollback needed, did a
  migration want more care than it got?
- **Environments** — did preview and rehearsal hold what production got?
- **Data** — did anything irreversible happen: a deletion, a migration, a
  change to retention?
- **Tooling** — did a script do something surprising, or fail silently? Did a
  tool read its own documentation as live input?
- **Time** — where did it actually go, against where it was expected to go?
- **The process** — which rule helped, which was in the way and which was
  quietly ignored?

## 6. Lessons learnt

<!-- The one or two sentences a future project would want. If there are none,
say so. The weekly digest collates the body's `## Lessons learnt`
([1.4](../1.4-programme-activities.md#what-the-digest-reviews-each-week)). -->
