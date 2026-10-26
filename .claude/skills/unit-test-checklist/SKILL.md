---
name: unit-test-checklist
description: A nudge to run through RIGHT-BICEP/CORRECT before calling a change's unit tests done. Use whenever writing or reviewing unit tests for new or changed logic. Technical (Rehearsal) and Functional user (Preview) tests are a different question, answered in the application's testing document (Tile Lite Elite's docs/4.3.3).
---

# Unit test checklist

**The checklist lives in one place**: the application's testing document (Tile
Lite Elite's `docs/4.3.3-testing-ci-and-release.md` §2.2.4, *What a unit test is
expected to cover*). Read it there.

## When this fires

Before treating a change's unit tests as sufficient: while writing them, or
while reviewing someone else's.

## How to use it

Read the checklist, then go through each letter against the actual code
being tested:

- Does it apply here at all? Most letters do not, for most changes: a data
  model has no performance characteristic worth a test, and most functions
  have no inverse. Skipping a letter that does not apply is the checklist
  working.
- Where it does apply, is there a test for it? If not, that is a missing test.
