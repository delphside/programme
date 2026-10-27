# What every agent does

Every agent in `.claude/agents/` reads this file first, then its own. Its own
file adds to these rules and never relaxes them.

## Where things are

A programme document's path (`docs/`, `.claude/`) is under `programme/` in an
application's checkout, this file's included. Records (`records/`,
`applications/`) are read in the programme's live checkout, as the
application's `CLAUDE.md` says. Tile Lite Elite's documents are named as the
example; another application's are the ones in the same place in its own
range.

## Your handover

Your prompt is a handover in the shape of `docs/templates/agent-handover.md`.
Its *Agreed but not yet written down* heading carries decisions the documents
do not show yet: treat those as true.

## Your report

Your final message is the report, and nothing else is read. Keep it short, and
do not restate what you were given. Any script you write goes in a scratch
directory outside the repository.

A reviewer (`change-reviewer`, `design-reviewer`, the two document reviewers
and `reference-reviewer`) reports as follows; its own file names its
headings:

- **Every check is answered**: each check in your own file, and each *Done
  when* item and question in the handover, as **holds**, **finding** (with its
  number) or **could not check** (and why). None is left out, so silence is
  never read as checked.
- **Each finding** gives the file and line, what is wrong, what would be right
  and whether you **verified** it in place or **inferred** it. Where your own
  file grades findings, it says how.
- **Before reporting**, prove each finding in place where you can, then go
  through the checks once more. Clean work is a legitimate result.
- **Resumed on a fix**, read its diff, the text around it and any related
  text elsewhere it could make false; confirm each of your findings is
  answered and report what the fix broke.
- **Questions for the owner** are only what the documents cannot settle.

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
