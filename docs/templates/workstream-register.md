<!-- markdownlint-disable-file MD041 -->
<!--
The workstream register: this application's workstreams, each an instance of
a generic one. The rule is docs/1.3, *Generic workstreams* and *What makes
something a workstream*. Copy it to
`applications/<application>/3.n.4-workstreams.md`, where `n` is the
application's index in records/2.1, and delete this comment. Keep the title
and the intro.

`<application>` is the application's folder name and `CODE` is its code in
records/2.1. In the table, the Workstream
cell is the issue field's option, prefixed `CODE:` for the application's own
workstreams and unprefixed for a programme-wide one; headings take the name
without the prefix.

A `###` section for each workstream with artefacts or a boundary to record; its
artefacts go in the section's table, and the Owns cell lists them only for a
workstream with no section. A boundary `####` section per neighbour, its
heading saying where the line falls; leave it out where there is none.

The table of generic workstreams with no instance stays, each with its reason;
leave it out only where every generic workstream has one.
-->

# 3.n.4 *Application*'s workstreams

*Application*'s workstream register: each workstream an instance of a generic
one, or a domain workstream. What a workstream is, and the generic workstreams,
are [1.3](../../docs/1.3-workstreams.md); the programme's own are in
[2.6](../../records/2.6-workstreams.md); the form is
[the template](../../docs/templates/workstream-register.md).

## This application's workstreams

| Workstream | Instance of | Owns |
| --- | --- | --- |
| *the field's option: `CODE: name`, or the name alone if programme-wide* | *a generic workstream from 1.3, or those it merges; "the same" for a programme-wide option, or "a domain workstream"* | *what it owns; its main artefacts too, where it has no section below* |

The generic workstreams with no instance here:

| Workstream | Why |
| --- | --- |
| *a generic workstream from 1.3* | *why the application has none* |

### *Workstream name*

*One paragraph: what the workstream is responsible for, and why it is one
workstream: the mechanisms of its own that make it self-contained (for
Application Architecture, what remains once the others are carved out).*

#### The artefacts *workstream name* owns

| Artefact | For |
| --- | --- |
| *a path, or a name from the artefact register* | *what it is for* |

#### *Where the line falls between this workstream and a neighbour*

*Which side owns the shared part.*
