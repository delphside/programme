# Change documents

Tile Lite Elite's change documents: the working documents for one change each,
such as its design, impact assessment, test approach and testing record. They
describe a *transition*: what is wrong now, what replaces it and what
migration does. Where each kind of document goes, and when it changes, is
[1.2 §2.4](../../../docs/1.2-change-lifecycle.md#24-where-a-document-lives-about-the-work-or-a-product-of-it).

What is still true once a change ships goes into the application's documents:
the end state to its overview and design documents (4.1 and 4.2), the as-built
facts to its reference (4.4), and any decision worth citing later to
[4.1.0 Rules](https://github.com/delphside/tile-lite-elite/blob/main/docs/4.1.0-rules.md),
with an id.

## Where they are

- `workstreams/<folder>/`: one folder per workstream, and in it a folder per
  parent project, named `<issue>-<name>/` ([workstreams](workstreams/README.md)).
- `<version>-user-testing.md`: a release's testing record.
- The grandfathered documents at the top level, listed in
  [3.1.6](../3.1.6-profile.md#grandfathered-change-documents).

## Conventions

**The application's documents change on the same branch.** A change document
holds no second copy of the truth. Where a change alters a diagram or a
schema, the numbered document is edited in the same commits as the code, so
every commit is internally consistent.

The exception is while a change is still a proposal: a diagram of the *agreed*
design may live in the change document before any code exists to make it true,
and moves into its permanent home as the code lands.

**Say what is being decided.** A change document is written to be argued with,
so it may record what was rejected and why.
