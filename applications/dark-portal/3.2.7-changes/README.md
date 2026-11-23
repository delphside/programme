# Change documents

Dark Portal's change documents: the working documents for one change each,
such as its test design specification. Where each kind of document goes, and
when it changes, is
[1.2 §2.4](../../../docs/1.2-change-lifecycle.md#24-where-a-document-lives-about-the-work-or-a-product-of-it).

What stays true once a change ships goes into Dark Portal's own `5.x`
documents, in
[its repository](https://github.com/delphside/dark-portal).

## Where they are

A parent project with change documents has a folder here, named
`<issue>-<name>/`. A work package has no folder of its own.

| Folder | Project |
| --- | --- |
| [`5-dark-portal-v1/`](5-dark-portal-v1/) | delphside/dark-portal#5 *MAIN PROJECT: Dark Portal v1* |

## Conventions

**The application's documents change on the same branch.** A change document
holds no second copy of the truth. Where a change alters a design the `5.x`
documents state, whoever makes the change edits them in the same commits as the
code, so every commit is internally consistent.

The exception is while a change is still a proposal: the *agreed* design may
live in the change document before any code exists to make it true, and the
change moves it into the `5.x` documents as the code lands. Dark Portal has no
`5.x` documents yet, and its agreed design is in the folder
[`5-dark-portal-v1/`](5-dark-portal-v1/) and the body of
delphside/dark-portal#5.

**Say what is being decided.** A change document is written to be argued with,
so it may record what was rejected and why.
