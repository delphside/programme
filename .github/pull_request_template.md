<!-- markdownlint-disable-file MD041 -->
<!--
The rules for the body are in *Changes* in
[the programme's `CLAUDE.md`](https://github.com/delphside/programme/blob/main/CLAUDE.md#changes).
Who reviews, and when Claude merges, is
[1.2 §2.2](https://github.com/delphside/programme/blob/main/docs/1.2-change-lifecycle.md#22-when-to-branch-and-what-pre-approved-means).

The `Refs #N` line:

- for an issue, replace `N` with the issue this delivers;
- for business-as-usual (BAU) work, replace the line with `Activity: <id>`,
  and add `Initiative: <id>` on a line of its own where there is one.

Never write `Closes #N`.

The `Claims:` line names the files this pull request expects to change, so
that `board-overlap.py` can warn another thread before it edits one of them
([1.2](https://github.com/delphside/programme/blob/main/docs/1.2-change-lifecycle.md#claiming-the-files-a-change-will-touch)).
Paths are relative to the repository's root, separated by commas, a trailing
`/` for a directory; keep it current.

*Review* says whether the owner's review is owed:

- not owed, the default here: keep the `No review owed:` line, and open the
  pull request with `create-pr.sh --no-review`;
- owed: replace the line with what he is to check, add him as reviewer when
  opening it (`create-pr.sh` does by default), and ask for the review in the
  chat.

*Review rounds* is the review record, in the form
[1.1](https://github.com/delphside/programme/blob/main/docs/1.1-programme-tooling.md#claudes-tooling)
gives. Keep `None owed:` where 1.1's *what owes none* row covers the change;
otherwise replace it with the record.

The board tooling reads these, so keep them as written:

- *What is being requested* and *What is deliberately left out*, read by
  `board-check.py`;
- *Review* and its opening `No review owed`, read by `board-pr-state.py`;
- *Review rounds* and its opening `None owed`, read by the weekly digest,
  and checked on the pull request by `board-review-record.py`.
-->

Refs #N

Claims:

## What is being requested

<!--
Which part of the scope this delivers, named against its issue or activity.
-->

## What is deliberately left out

<!--
Scope this pull request does not carry, and why. Where nothing is left out,
write *Nothing*.
-->

## Review

No review owed: the programme's records, documents, process and tooling (docs/1.2 §2.2).

## Review rounds

None owed:
