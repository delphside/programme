# Test design specification: *change*

<!--
The guide is docs/1.9, *How a test design specification is built*.

1. Copy it to where docs/1.9 says, with its change, as
   `test-design.md`, for example `<issue>-<name>/test-design.md`.
2. Fill in the header: replace `Project` with `Issue` where there is no
   project.
3. Keep all ten headings, in order; docs/1.9 says what an empty one says.
4. Delete these comments.

Placeholders: `N` is the project's or issue's number; `<issue>` is the parent
project's number and `<name>` its short name; `X.Y.Z` is the release's
semver. The values of type of change and route are in docs/1.2 §2.15.

Worked example in the ten-part form:
records/2.5-changes/programme-tooling/117-generic-deliver-tool/test-design.md

This holds no test plan (scope, schedule, resources and risks): Claude writes
none (docs/1.9).
-->

Project: `#N` · type of change: *`functional`, or the change's own* · route: *`Production Release`, or the change's own* · release: *`X.Y.Z`, or `not applicable`*

## 1. Rules

<!-- Intent, before anything derives from it. Write each rule from what the
system is supposed to do — the application's rules document (Tile Lite Elite's
docs/4.1.0-rules.md), the issue's body or the design note — and not from the
code.
Claude checks the rules before section 2. Number them; everything below
refers back. -->

| ID | Rule |
| --- | --- |
| R1 | |
| R2 | |

## 2. Conditions, grouped into dimensions

<!-- Each dimension is one axis the behaviour varies along. Mark a dimension
**complete** where its values exhaust the possibilities. Give each value an ID;
the scenarios cite them. -->

**D1 — *name*** *complete · not complete*

- **D1.1** *value*
- **D1.2** *value*

## 3. Outcomes

<!-- Kept apart from the conditions, and each phrased as something observable:
Tile Lite Elite's "the request is refused with 400 and the body names the seat"
and not "it works". -->

| ID | Outcome |
| --- | --- |
| O1 | |

## 4. Matrix

<!-- Where two dimensions cross (D1 and a second, D2, defined in section 2), a
table with a symbol for combinations that cannot occur, so impossible is
distinguishable from untested. -->

| | *D2.1* | *D2.2* |
| --- | --- | --- |
| *D1.1* | | |

## 5. Scenarios

<!-- Lifecycle walks, each covering several conditions. Number them for
navigation while writing. -->

| ID | Scenario | Conditions | Outcomes |
| --- | --- | --- | --- |
| S1 | | | |

## 6. Refusals and successes

<!-- Follow every refusal with a success. Cite scenario IDs. -->

| Refused | Then succeeds |
| --- | --- |
| | |

## 7. Coverage, both ways

<!-- Every rule to a scenario, and every scenario to a rule. -->

| Rule | Scenarios |
| --- | --- |
| R1 | |

| Scenario | Rules |
| --- | --- |
| S1 | |

## 8. Approach

<!-- Answer four questions:
- What runs, and where: component, integration, system or a script on a
  deployed environment?
- What is real, and what is stubbed?
- How is time manipulated?
- What state does each test start from? -->

## 9. Test names

<!-- Name each test for the behaviour and never for a scenario number: Tile
Lite Elite's `delete_refused_while_a_game_is_waiting`, not `s1`. -->

## 10. Gaps

| Gap | What would make the missing test fail | What it would take to close it | Why it is acceptable for now |
| --- | --- | --- | --- |
| | | | |
