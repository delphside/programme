<!-- markdownlint-disable-file MD041 -->
# Post-deployment review: Sub-agents

Work package: `delphside/tile-lite-elite#441` *Sub-agents* (one delivery, so
the project is its own work package) · delivery: `main` · reviewed: 2026-11-16

## 1. Was the intended scope delivered?

Checked 2026-11-16 in the programme checkout against the project's
post-deployment table.

| In scope | Delivered | Note |
| --- | --- | --- |
| R1 handover template, every launch uses it | Template yes; use partly evidenced | `docs/templates/agent-handover.md` has eight headings: task, done when, subject, read as well, already checked, agreed but not yet written down, questions, out of scope. `.claude/agents-common.md` says the prompt is a handover in that shape, and `docs/1.1` step 2 of a review round requires it. **Check: still open** (section 2) |
| R2 reference reviewer | Yes | `.claude/agents/reference-reviewer.md`. **Check: passed** for its trial (5932a94, on the project) and in the weekly activity: `records/2.3-activity-log.csv` rows 2026-10-19, 10-26, 11-02 and 11-16 each record corrections. The 2026-10-05 first run the project named has no log row |
| R3 design reviewer | Yes | `.claude/agents/design-reviewer.md`. **Check: passed**, trial on delphside/tile-lite-elite#71 *One Game Model* confirmed by spot check, recorded in the project's trials |
| R4 test designer | Yes | `.claude/agents/test-designer.md`. **Check: passed**, trial on account deletion confirmed, fixing 4.2 and 4.3 (e67e4c1) |
| R5 test reviewer, R6 placement finder | Not built | As designed: built when needed. No file for either exists. **Check: closed as not due** |
| R7 which work goes to an agent | Yes | Stated in `docs/1.1`, *Claude's tooling*, and in one bullet of `CLAUDE.md` ("Reading jobs with a defined file set, and a work package's change, go to an agent"), which links to it. **Check: passed** |
| R8 to R15 | Yes | `change-maker`, `change-reviewer`, `document-reviewer-reader` and `document-reviewer-truth` exist; rounds, model per agent and trials are in `docs/1.1`. No row in the table checks them |

**Anything deferred:** R5 and R6, by design, until a first need. Nothing else.

## 2. What happened that was not planned for?

- The project grew from five agents to seven files and a shared
  `.claude/agents-common.md`; the owner's R8 to R15 were added as the trials
  ran.
- The R1 check, "the next three launches use the template", cannot be
  confirmed from records. A handover is a prompt, so it is stored nowhere. The
  searched evidence: pull request bodies and issue comments from 2026-11-01
  record review rounds by `change-reviewer` and the document reviewers (for
  example delphside/programme#196's *Review rounds* section) but never the
  handover. The weekly digests W44 and W46 show it in use: a reviewer fault
  "the agents were told to use a diff the handover did not give them", and a
  process change that the handover gain a *Cases to check* list. That heading is
  not in the template now, and a pickaxe search of this checkout's history did
  not find it added, so whether it landed was not confirmed.
- The project's body still cites `docs/5.0` and `docs/5.1`; the rule is now in
  `docs/1.1`. The documents are the authority, not the issue.

## 3. Why — what was the cause?

R1's check asks for something nothing records: a launch's prompt. The check was
written without asking where its evidence would be kept.

## 4. What happens next?

| Finding | Pre-approved change, requirement or project | Or why no change |
| --- | --- | --- |
| R1's three launches unconfirmed | | The review-round record already names which agents ran; the next three pull requests' *Review rounds* are read for the handover's headings (*Done when*, *Already checked*). Claude answers it at the next weekly review, and R1 stays open until then |
| *Cases to check* in the digest versus the template | Pre-approved change: the owner or Claude confirms whether W44's process change landed, and edits `docs/templates/agent-handover.md` or the digest note | Straight to `main`, Docs and Programme Tooling |
| No post-deployment row for R8 to R15 | | Their trials are recorded in the project and the agents are in daily use: `change-reviewer` ran on delphside/programme#185 *Change 117: Turpin redesign, Python controller and OCIR adapter* to round 18 |
| R5 and R6 not built | | Built when a first need appears, as the project says |
| The body's stale `docs/5.0` and `docs/5.1` references | | The documents live and the issues expire: `docs/1.1` is the home, and nothing cites the body as authority |
| R2's 2026-10-05 first run absent from the log | | Later weekly rows show the agent used; the date was missed, with no cost found |

## 5. Areas to consider

- **Scope** — grew by R8 to R15, recorded in the project body.
- **Testing** — each agent was trialled on a case with a known answer before
  use.
- **Documentation** — the rule lives in `docs/1.1` and `CLAUDE.md` carries one
  line; no second copy found.
- **Tooling** — a newly written agent type loads only at session start, as the
  design notes.
- **Time** — token cost per run is recorded in the trials, not here.
- **The process** — rounds until nothing material remains are in force.

## 6. Lessons learnt

A check on how often a practice is used needs the practice to leave a record.
Where a prompt is the only artefact, the pull request's review record is the
place to name its headings.
