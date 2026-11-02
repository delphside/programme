<!-- markdownlint-disable-file MD041 -->
<!--
The handover Claude gives a subagent at launch, as its prompt; the rule is
docs/1.1, "Claude's tooling". The agent's definition in .claude/agents/, with
.claude/agents-common.md, holds what does not change between runs; this holds
what is particular to one job.

Fill every heading, writing "None" where one does not apply, so the agent
reads every heading as answered. Delete these comments.
-->

## Task

One sentence: the single thing to do. For a change, its kind: design, code,
documentation or tests.

## Done when

What finishes it, as checks the agent can run or read: the requirements it
meets, the tests that pass, the documents that say so. Each names the check
and how it is proved: "same exit statuses" needs "and tested", or it is
proved once by hand and nothing holds it. For a review, the questions
answered.

## Subject

The issue, document or branch, the commit or stamp it runs from, and whether
the review covers the whole of it or a diff range.

## Read as well

Anything beyond the *Before anything* list in the agent's definition.

## Already checked

For a review in rounds, the points earlier rounds settled, copied from their
reports, each marked *recheck* where a fix has touched it since (1.1, "Claude's
tooling").

## Agreed but not yet written down

Decisions from Claude's conversation with the owner that the documents do not
show yet. The agent cannot see the conversation, so anything missing here is
invisible to it.

## Questions

What specifically to answer, numbered.

## Out of scope

What to leave alone, so no effort goes there.
