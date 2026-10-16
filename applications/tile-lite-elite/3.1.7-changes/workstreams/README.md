# Documents owned by a workstream

One folder per workstream, named for the **capability** rather than an issue
number — D7, re-answered 2026-08-24 against the three areas that replaced the
two it was originally decided for.

| folder | workstream |
| --- | --- |
| `application-game-architecture/` | the application's central function and its architecture |
| `capacity-planning/` | whether the service will outgrow its infrastructure |
| `delivery-tooling/` | the machinery that carries a change to a running environment |
| `operations/` | the service once it is live |

Process Definition's and Programme Tooling's documents belong to the programme,
not to this application, and are in
[`records/2.5-changes/`](../../../../records/2.5-changes/README.md).

Inside each: documents the **workstream** owns at the top level, and a folder per
issue or project that has documents of its own, named `<number>-<name>`.

**The structure forces the classification rather than merely recording it.**
Owner, 2026-08-20: *"yes, B. And it makes us think about which workstream an
issue is in."* The question gets asked when a document is created and the answer
is still cheap — the same principle as the issue form asking for type and route
at the moment an issue is raised.
