# What every agent does

Every agent in `.claude/agents/` reads this file first, then its own. Its own
file adds to these rules and never relaxes them.

## Where things are

- A programme path (`docs/`, `.claude/`, `scripts/`, `.githooks/`) is under
  `programme/` in an application's checkout, including this file.
- Records (`records/`, `applications/`) are read in the programme's live
  checkout, as the application's `CLAUDE.md` says.
- The agent files, and this one, name Tile Lite Elite's documents, scripts and
  commands as the example. Another application's are the equivalent ones,
  though its scripts may not be under `scripts/` (Dark Portal's are in
  `sizing/`). A document carries the same suffix in its own (3+n) range, and a
  record in its own 3.n.x range
  ([1.5](../docs/1.5-writing-documents.md#each-range-covers-one-scope)).
- A script you write goes in a scratch directory outside the repository.

## Your handover

Your prompt is a handover in the shape of `docs/templates/agent-handover.md`.
Its *Agreed but not yet written down* heading carries decisions the documents
do not show yet: treat those as true.

## Your report

Claude reads only your final message, so it is the report. Keep it short, and
do not restate what you were given.

A reviewer (`change-reviewer`, `design-reviewer`, the two document reviewers
and `reference-reviewer`) reports as follows; its own file names its
headings:

- **Every check is answered**: each check in your own file, and each *Done
  when* item and question in the handover, as **holds**, **finding** (with its
  number) or **could not check** (and why). Claude reads silence as
  unchecked.
- **Each finding** gives the file and line, what is wrong, what would be right
  and whether you **verified** it in place or **inferred** it. Where your own
  file grades findings, it says how.
- **Before reporting**, prove each finding in place where you can, then go
  through the checks once more. Clean work is a legitimate result.
- **When Claude resumes you after fixing your findings**, read the fix's diff,
  the text around it and any related text elsewhere it could make false;
  confirm each of your findings is answered and report what the fix broke.
- **Questions for the owner** end every reviewer's report, whatever headings
  its own file names, and are only what the documents cannot settle.

## Never

- Commit or push, or change a file outside what your own file allows.
- Comment on or edit an issue or pull request, or set a board field.
- Check out a commit or switch branches in a checkout you were not given as
  your own: another session's work is in it. Read other commits with
  `git show`, `git diff` or `git archive` into a scratch directory.
- Run an application's deploy or rollback script (Tile Lite Elite's
  `scripts/deliver/deploy*.sh` and `rollback*.sh`), or anything that reaches a
  server.
- Read production: production reads are the owner's.
