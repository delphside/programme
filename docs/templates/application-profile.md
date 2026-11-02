<!-- markdownlint-disable-file MD041 -->
<!--
An application's programme profile: what the programme's processes need to
know about it, read by scripts/board/profile.py. The rule is docs/1.3, "The
generic assets, and an application's instances".

1. Copy this to `applications/<app>/3.n.6-profile.md`.
2. Replace every italic text with the application's own, and leave out an
   optional section that has nothing in it.
3. Keep the headings and the order of the columns: the tooling finds a table
   by its heading, reads its columns by position, and finds the target
   architecture by its first link.
4. Delete these comments.

Backticks matter only in the Environments URL column, where they mark a fixed
URL. The technical facts (how a version is read, what ships, the commands) are
in the technical profile, app-profile.toml at the root of the application's
repository.
-->

# 3.n.6 *Application* profile

*One line: what the application is.* The technical profile is `app-profile.toml`
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
| commit stamp | *the commit-subject stamp (Tile Lite Elite's: `app <X.Y.Z> api <M.N>: <subject>`), or none* |

## Environments

*In the order a change reaches them. Each name is an
`[environments.<name>]` table in the technical profile, whose `env` variables
override the URL here. A URL that is not fixed is written without backticks,
saying why; the technical profile gives its default, or the script to source
and the variable it sets.*

| environment | purpose | URL |
| --- | --- | --- |
| *name* | *what it is for* | `https://…`, or *not fixed* and why |

## Routes

The routes its deliveries take, from
[1.2 §2.15](../../docs/1.2-change-lifecycle.md#route).

| route | how a change on it reaches its users |
| --- | --- |
| *a route* | *when it is live* |

## Target architecture

*A link to the application's architecture document or, until it is written, to
the issue that will write it.*

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

*Optional: leave it out when there are none.* Change documents that stay at the
top of `3.n.7-changes/`, outside the issue and release folders, because GitHub
does not follow a rename and issue comments point at them. One row each, the
file name in the first column. Rows are removed, never added.

| document | why |
| --- | --- |
| `a-document.md` | *what points at it* |
