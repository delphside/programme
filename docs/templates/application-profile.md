<!-- markdownlint-disable-file MD041 -->
<!--
An application's programme profile: what the programme's processes need to
know about it, in fixed tables the tooling reads
(scripts/board/profile.py). The rule is docs/1.3, "The generic
assets, and an application's instances". Copy this to
applications/<app>/3.n.6-profile.md, fill in every table, and delete these
comments. Keep the headings, the column names and the order of the rows: the
tooling finds a table by its heading and a value by its first column.

Put a value in backticks where it is read by a script. The technical facts
(how a version is read, what ships, the commands) are not here: they are in
the technical profile, programme.toml at the root of the application's
repository, which this profile names and does not repeat.
-->

# 3.n.6 *Application* profile

*One line: what the application is.* The technical profile is `programme.toml`
at the root of [its repository](https://github.com/*owner*/*repository*).

## Identity

| field | value |
| --- | --- |
| name | *the application's name* |
| code | `CODE` |
| number | `n` |
| repository | `owner/repository` |
| board view | *the name of its view on the programme board* |
| document range | `(3+n)` |

## Versioning

| field | value |
| --- | --- |
| scheme | `semver` or `date` |
| commit stamp | *the subject's stamp, `app <X.Y.Z> api <M.N>: <subject>`, or none* |

## Environments

In the order a change reaches them. Where a URL is not fixed, say so; the
technical profile's `environments` key gives a default, or the script to source and the variable it sets.

| environment | purpose | URL |
| --- | --- | --- |
| *name* | *what it is for* | `https://…`, or *not fixed* and why |

## Routes

The routes its deliveries take, from [1.2](../1.2-change-lifecycle.md) §2.15.

| route | how a change on it reaches its users |
| --- | --- |
| *a route* | *when it is live* |

## Target architecture

*A link to the application's architecture document.*

## Records

| record | path |
| --- | --- |
| 3.n.1 delivery log | `3.n.1-delivery-log.md` |
| 3.n.2 artefact register | `3.n.2-artefacts.md` |
| 3.n.3 capacity plans | `3.n.3-capacity-plan/` |
| 3.n.4 workstreams | `3.n.4-workstreams.md` |
| 3.n.5 role holders | `3.n.5-roles.md` |
| 3.n.6 application profile | `3.n.6-profile.md` |
| 3.n.7 change documents | `3.n.7-changes/` |

## Grandfathered change documents

*Optional: leave it out when there are none.* Change documents that stay in the
top of `3.n.7-changes/` instead of an issue or release folder, because GitHub
does not follow a rename and issue comments point at them. One row each, the
file name in the first column. The list can only shrink.

| document | why |
| --- | --- |
| `a-document.md` | *what points at it* |
