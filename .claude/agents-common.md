# What every agent does

Every agent in `.claude/agents/` reads this file first, then its own. Its own
file adds to these rules and never relaxes them. This file owns the rules an
agent follows when it runs;
[1.1](../docs/1.1-programme-tooling.md#claudes-tooling)
says what each agent is for and how Claude runs a review.

## Where things are

- A programme path (`docs/`, `.claude/`, `scripts/`, `.githooks/`) is under
  `programme/` in an application's checkout, and so is this file.
- Records (`records/`, `applications/`) are read in the programme's live
  checkout, as the application's `CLAUDE.md` says.
- The agent files, and this one, name Tile Lite Elite's documents, scripts and
  commands as the example. Another application's are the equivalent ones,
  and its scripts are where its repository keeps them (Dark Portal's:
  `sizing/`). A document carries the same suffix in its own (3+n) range, and a
  record in its own 3.n.x range
  ([1.5](../docs/1.5-writing-documents.md#each-range-covers-one-scope)).
- A script you write goes in a scratch directory outside the repository.
- An issue's body, and its comments, are read with `gh`:

  ```bash
  gh issue view <N> -R delphside/<repo> --json body,comments
  ```

  `gh issue view` uses GraphQL, which a cloud session is refused, so a cloud
  session uses the REST form, paginated so that no comment is missed:

  ```bash
  gh api repos/delphside/<repo>/issues/<N> -q .body
  gh api --paginate repos/delphside/<repo>/issues/<N>/comments
  ```

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
- **A finding that two documents disagree, or a document and the code**,
  says how they came apart where `git log` shows it: the commit that wrote
  each side, and which changed last. Where
  `git rev-parse --is-shallow-repository` prints `true` in the repository
  searched, the history is **could not check**
  ([the change-a-document skill](skills/change-a-document/SKILL.md#when-documents-or-code-disagree)
  says why).
- **Each finding** gives the file and line, what is wrong, what would be right
  and whether you **verified** it in place or **inferred** it. A document
  reviewer grades it as *The two document reviewers* says; another reviewer's
  own file says how, where it grades.
- **Before reporting**, prove each finding in place where you can, then go
  through the checks once more. Clean work is a legitimate result.
- **When Claude resumes you after fixing your findings**, read the fix's diff,
  the text around it and any related text elsewhere it could make false;
  confirm each of your findings is answered and report what the fix broke.
- **Questions for the owner** end every reviewer's report, after
  *Completeness*, whatever headings its own file names, and are only what the
  documents cannot settle.

## The two document reviewers

`document-reviewer-reader` and `document-reviewer-truth` share these rules:

- **A handover missing a heading of the template** still binds you to every
  check in your own *What to check*; answer the questions it does carry.
- **Scope**: every changed section is in scope.
  - Where the handover asks for a document whole, every section is.
  - Where it also names no diff, every finding is *pre-existing*: say so once
    in the report.
- **Grading**: *material* is a finding where a reader would act wrongly or be
  misled, as by an untrue claim; *minor* is any other breach of a 1.5
  principle or deviation, such as a copy that is still true. *Pre-existing*
  marks a finding in text the diff leaves unchanged.
- **Rechecking**: review the whole change in every round. Do not raise a point
  the handover's *Already checked* lists as settled, unless Claude has marked
  it *recheck*; answer it **already checked**.
- **Completeness**: give your estimate of the share of faults you found and
  what you checked least well. Claude takes it as one input, never as the
  reason to stop the rounds.

## Never

- Commit or push, or change a file outside what your own file allows.
- Comment on or edit an issue or pull request, or set a board field.
- Check out a commit or switch branches in a checkout you were not given as
  your own: another session's work is in it. Read other commits with
  `git show`, `git diff` or `git archive` into a scratch directory.
- Run an application's deploy or rollback script (Tile Lite Elite's
  `scripts/deliver/deploy*.sh` and `rollback*.sh`), or anything that reaches a
  server.
- Read production: a read of production is the main session's to make.
