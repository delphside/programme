# Templates

Documents you copy and fill in.

**The numbered document owns the rule and links to the template; the template
names that document and carries no reasoning.** The templates are filed
together because a template is looked for as a template, and the link from the
owning document is what keeps each one findable from the rule.

A template says **what must be included**; the worked examples beside it show
**how to complete it**.

| template | the numbered document that links it, and its rule |
| --- | --- |
| [test-design-specification.md](test-design-specification.md) | [1.9](../1.9-testing-standards.md#how-a-test-design-specification-is-built), *How a test design specification is built* |
| [post-deployment-review.md](post-deployment-review.md) | [1.2](../1.2-change-lifecycle.md#the-parents-lifecycle-is-shorter), *The parent's lifecycle is shorter*: lessons learnt |
| [capacity-plan.md](capacity-plan.md) | [1.2](../1.2-change-lifecycle.md#which-document-goes-where), *Which document goes where*: reports |
| [agent-handover.md](agent-handover.md) | [1.1](../1.1-programme-tooling.md#claudes-tooling), *Claude's tooling* |
| [triage-comment.md](triage-comment.md) | [1.2](../1.2-change-lifecycle.md#what-triage-asks), *What triage asks* |
| [workstream-register.md](workstream-register.md) | [1.3](../1.3-workstreams.md#the-generic-assets-and-an-applications-instances), *The generic assets, and an application's instances*; the rule is [*Generic workstreams*](../1.3-workstreams.md#generic-workstreams) and [*What makes something a workstream*](../1.3-workstreams.md#what-makes-something-a-workstream) |
| [artefact-register.md](artefact-register.md) | [1.3](../1.3-workstreams.md#the-generic-assets-and-an-applications-instances), *The generic assets, and an application's instances*; the rule is [1.2 §2.13](../1.2-change-lifecycle.md#213-the-impacted-artefacts-and-why-they-are-listed-early) and [§2.15](../1.2-change-lifecycle.md#route) |
| [role-assignment.md](role-assignment.md) | [1.7](../1.7-roles-and-responsibilities.md#who-holds-each-role), *Who holds each role*; the rule is [*The roles*](../1.7-roles-and-responsibilities.md#the-roles) |
| [delivery-log.md](delivery-log.md) | [1.2 §2.14](../1.2-change-lifecycle.md#214-the-delivery-runbook), *The delivery log row is part of the delivery* |
| [application-profile.md](application-profile.md) | [1.3](../1.3-workstreams.md#the-generic-assets-and-an-applications-instances), *The generic assets, and an application's instances* |

**A new template is added to this table, and its numbered document links to
it.**

| template | copy it to | worked examples |
| --- | --- | --- |
| [test-design-specification.md](test-design-specification.md) | with its change, as [1.9](../1.9-testing-standards.md#how-a-test-design-specification-is-built) says | Tile Lite Elite's [user deletion](../../applications/tile-lite-elite/3.1.7-changes/41-user-deletion-test-design.md) (functional) · [rate limiting](../../applications/tile-lite-elite/3.1.7-changes/25-rate-limiting-test-design.md) (non-functional, judged by a script on rehearsal) |
| [post-deployment-review.md](post-deployment-review.md) | the issue's body or the project's folder, as [1.2](../1.2-change-lifecycle.md#the-parents-lifecycle-is-shorter) says | [documentation by type](../../records/2.5-changes/process-definition/427-documentation-by-type/post-deployment-review.md) · [the programme repository](../../records/2.5-changes/programme-tooling/485-programme-repository/post-deployment-review.md) · Tile Lite Elite's [Claude sessions from the workspace root](../../applications/tile-lite-elite/3.1.7-changes/workstreams/delivery-tooling/452-claude-sessions-from-workspace-root/post-deployment-review.md) |
| [capacity-plan.md](capacity-plan.md) | the application's capacity plans (`3.n.3-capacity-plan/`), monthly, named as [1.2](../1.2-change-lifecycle.md#which-document-goes-where) says | [TLE_CP_2026_09](../../applications/tile-lite-elite/3.1.3-capacity-plan/TLE_CP_2026_09.md), the first |
| [workstream-register.md](workstream-register.md) · [artefact-register.md](artefact-register.md) · [role-assignment.md](role-assignment.md) · [delivery-log.md](delivery-log.md) · [application-profile.md](application-profile.md) | a new application's programme records, once each, when the programme takes it on | Tile Lite Elite's: [3.1.4](../../applications/tile-lite-elite/3.1.4-workstreams.md) · [3.1.2](../../applications/tile-lite-elite/3.1.2-artefacts.md) · [3.1.5](../../applications/tile-lite-elite/3.1.5-roles.md) · [3.1.1](../../applications/tile-lite-elite/3.1.1-delivery-log.md) · [3.1.6](../../applications/tile-lite-elite/3.1.6-profile.md) |

## The forms GitHub offers

**The forms GitHub offers when an issue or pull request is opened live in each
repository's `.github/`**, which is where GitHub reads them. Tile Lite Elite's
are the programme's working set:

| template | offered when |
| --- | --- |
| [`Requirement`](https://github.com/delphside/tile-lite-elite/blob/main/.github/ISSUE_TEMPLATE/requirement.yml) · [`Project`](https://github.com/delphside/tile-lite-elite/blob/main/.github/ISSUE_TEMPLATE/project.yml) · [`Decision`](https://github.com/delphside/tile-lite-elite/blob/main/.github/ISSUE_TEMPLATE/decision.yml) | raising an issue of that type |
| [`PULL_REQUEST_TEMPLATE.md`](https://github.com/delphside/tile-lite-elite/blob/main/.github/PULL_REQUEST_TEMPLATE.md) | opening a pull request |

GitHub fills those in front of you. The templates in this folder are copied:
into the repository, or, for the triage comment and the handover, into an
issue comment or an agent's prompt.

## Reports

**A report's template keeps a series comparable.** A test design specification
is written once for a project, and its template guards against forgetting a
part. A capacity plan is written every month, and its template keeps the rows
comparable between months.
