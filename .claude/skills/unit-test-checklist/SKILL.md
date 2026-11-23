---
name: unit-test-checklist
description: A nudge to run through RIGHT-BICEP and CORRECT before calling a change's unit tests done. Use whenever writing or reviewing unit tests for new or changed logic. Technical tests and functional user tests are a different question, answered by each project's test approach at the levels docs/1.9 sets.
---

# Unit test checklist

The checklist lives in
[1.9 *What a unit test covers*](../../../docs/1.9-testing-standards.md#what-a-unit-test-covers).

## How to use it

Before treating a change's unit tests as sufficient, while writing them or
reviewing someone else's, go through each item of the checklist and each
CORRECT letter under *Boundary*:

1. Take the item against the change's stated rules
   ([1.9](../../../docs/1.9-testing-standards.md)). Read the code only to see
   whether the item applies.
2. Decide whether it applies here. A data model has no performance
   characteristic worth a test, and most functions have no inverse, so few
   items apply to any one change. Skipping an item that does not apply is the
   checklist working.
3. Where it applies, look for its test. Write the missing test, or report
   the gap, saying what would make the missing test fail.
