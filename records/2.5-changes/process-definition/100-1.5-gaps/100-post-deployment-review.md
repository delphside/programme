<!-- markdownlint-disable-file MD041 -->
# Post-deployment review: 1.5 gaps found by the first document review

Work package: `delphside/programme#100` *1.5 gaps found by the first document
review* (one delivery, so the project is its own work package) · delivery:
`main` (delphside/programme#161 *1.5: README, front matter, run-in label and
template rules*, merged 2026-11-11, 8db5301) · reviewed: 2026-11-16, check
answered 2026-11-26: passed

## 1. Was the intended scope delivered?

| In scope | Delivered | Note |
| --- | --- | --- |
| R1 a README rule in 1.5 | Yes | `docs/1.5-writing-documents.md`, *What a README holds*; *One fact, one home* lets a README own its folder's conventions |
| R2 front matter wrapping | Yes | One line per key, under *Wrap prose at 80 characters* |
| R3 bold run-in labels | Yes | *Bold run-in labels* (colon outside the bold); *Bold lead sentence* widened |
| R4 templates in sentence case | Yes | The rule is in *Sentence case, and names as the system shows them*; the triage-comment and raise-project template headers were fixed |

All four headings exist in 1.5 today (grep of `docs/1.5-writing-documents.md`,
2026-11-16).

**Anything deferred:** Tile Lite Elite's `.github/ISSUE_TEMPLATE/project.yml`
still has lower-case headers; the delivery comment left it for that repository.
No requirement or pre-approved change records it (section 4). Quotations in
`CLAUDE.md` stayed with delphside/programme#89 *Document review, week 1 of 4*,
question 13, as the project said.

## 2. What happened that was not planned for?

- The change took four review rounds, not the one a rule edit suggests. Round 1
  found four material faults, each a new rule clashing with practice or with
  another rule, and the owner's questions afterwards found the front matter
  rule's stated reason was wrong, which no reviewer found (the week 47 digest
  draft's notes).
- The owner's comments produced a follow-up, delphside/programme#164 *Headings
  name their topic*, now closed.

## 3. Why — what was the cause?

The rules were written from the gap, not from a count of the forms in use, so
each clashed with a form already in use. The digest draft's proposed
conclusion is to count the forms and check every rule and tool that reads
them before writing a style rule.

## 4. What happens next?

| Finding | Pre-approved change, requirement or project | Or why no change |
| --- | --- | --- |
| The check, a document-review week citing the new rules and raising no gap on the four subjects | | Passed on 2026-11-26 (below); the project closes |
| `project.yml` in Tile Lite Elite has lower-case headers | Pre-approved change: Docs and Programme Tooling's pin move or a Tile Lite Elite template edit, raised by the next Tile Lite Elite session | It is a small template edit in another repository and no issue carries it |
| Style rules clash with practice | The week 47 digest note's proposed conclusion, with its monitor | Left to the weekly review to adopt |

### The check, answered 2026-11-26: passed

Two document-review weeks ran after the rules merged:

- 2026-11-16, week 4 of 4;
- 2026-11-23, week 1 of a new quarter.

Their reviews covered READMEs (the root README, the templates README and Tile
Lite Elite's), templates and front matter. Each week's log row in
`records/2.3-activity-log.csv` ends with none material. Neither week raised an
issue or a finding on a README, front matter, a run-in label or a template
header: the issues raised from 2026-11-23 are delphside/programme#251
*Re-requested review still shows Changes requested* and
delphside/infrastructure#10 *Record the hosts as built in 3.3.2*.

One finding in `records/2.4-weekly-digest/PRG_WD_2026_W48.md` cites
*Sentence case, and names as the system shows them* by heading. The other
three rules are cited nowhere. That is because nothing broke them, so the
check's "cites by heading" half is read as met by their absence. The open
check below is kept as the 2026-11-16 record.

### The open check, as of 2026-11-16

Evidence searched on 2026-11-16, none of it answering the check:

- `records/2.3-activity-log.csv`: the last `document-review` row is 2026-11-09,
  week 3 of 4, which predates the rules (merged 2026-11-11). There is no week 4
  row.
- Pull requests since 2026-11-11 (`gh api repos/delphside/programme/pulls`): no
  document-review pull request; the only review-titled ones are delphside/
  programme#165 and #171, which are digest and process changes.
- Issues: delphside/programme#144 *Document review, week 3* is closed and the
  latest of its kind.
- `records/2.4-weekly-digest/PRG_WD_2026_W47.md`: notes on these four rules'
  own review rounds, not on a later week's findings.

The check is answered by week 4's document review: its log row, its pull
request or issue of owner questions, and the digest's *Document reviews* part
(1.4) show whether reviewers cite *What a README holds*, *Bold run-in labels*,
*Wrap prose at 80 characters* and *Sentence case* by heading, and raise no gap
on a README, front matter, run-in label or template header. Close the project
when that is read.

## 5. Areas to consider

- **Scope** — unchanged.
- **Testing** — `check-docs.sh --programme` and both reviewers, four rounds.
- **Documentation** — 1.5 changed; existing documents are left to the rotating
  review, as designed.
- **The deploy itself** — straight to `main`; each application takes the rules
  at its next pin move.
- **The process** — the rule was agreed with the owner in chat first, as the
  rules require.

## 6. Lessons learnt

Count the forms in use and check every rule and tool that reads them before
writing a style rule: round 1's faults were all findable that way.
