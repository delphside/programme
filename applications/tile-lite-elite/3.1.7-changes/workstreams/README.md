# Change documents by workstream

One folder per workstream, a short kebab-case name for its capability. A folder
appears when the workstream's first change document does
([1.2 §2.4](../../../../docs/1.2-change-lifecycle.md#24-where-a-document-lives-about-the-work-or-a-product-of-it)),
so a workstream with none has no folder yet. The workstreams are
[3.1.4](../../3.1.4-workstreams.md).

| folder | workstream |
| --- | --- |
| `application-game-architecture/` | TLE: Application Architecture |
| `capacity-planning/` | Capacity & Performance |
| `delivery-tooling/` | TLE: Delivery Tooling |
| `operations/` | Operations & Infrastructure |

The programme's own change documents are in
[`records/2.5-changes/`](../../../../records/2.5-changes/README.md).

Inside each folder:

- documents the workstream owns, at the top level;
- a folder per parent project that has documents of its own, named
  `<issue>-<name>`.

**The folder makes the writer choose the workstream when a document is
created**, while the answer is still cheap.
