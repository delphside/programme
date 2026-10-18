# #406 R6: the design map's format, proposed

For the owner's agreement (#406 R6). It answers: what is the map's one
source, what is a project's one change file, how a work package's diagrams are
drawn, how a release applies its entries, and how R4's check is run.

Built, in `scripts/docs/design-map/design-map.py`: the map's generation, a
package's drawing from the change file, and the relationship colours. Still
proposals: the checked edit that applies a release's entries, R4's check, and
drawing a package on top of the packages it builds on.

Written 2026-09-30 from a trial run that day. Each finding is marked
**verified** (run and seen) or **inferred** (read or reasoned, not run).

## The standard first: Structurizr

Before designing a format, the standard one was tried. Structurizr is C4's own
tool: a model written once in its DSL, from which every view is generated. It
is the published answer to "one source, many views".

The trial used the current tool, the `structurizr/structurizr` Docker image
(v2026.09.19). The older `structurizr/cli` now prints that it will receive no
further updates and points to this one, so that is what we would adopt.

The trial's files are in [`406-map-trial/`](406-map-trial/): a sketch of the
server's components, not the real as-is, and a made-up change shaped like the
one #71 will make, enough to test the mechanics. Rerun with:

```bash
cd applications/tile-lite-elite/3.1.7-changes/workstreams/application-game-architecture/406-architecture-views/406-map-trial
docker run --rm -u "$(id -u):$(id -g)" -v "$PWD":/w -w /w structurizr/structurizr \
  export -w change71.dsl -f mermaid -o /tmp/out
```

### What worked

- **One model, several views, generated.** A model with people, containers
  and components, and a Container and a Component view declared as
  `include *`, exported to Mermaid in about 3 seconds. Verified.
- **The export passes our own check.**
  `scripts/docs/mermaid/check.mjs` parsed both
  generated diagrams. Verified.
- **A project's change as an extension of the map.** A file starting
  `workspace extends model.dsl` added a new component, marked an existing one
  changed with a new description, marked another removed, and added a
  relationship, without touching the map's files. The map rendered without
  them and the extension with them. Verified.
- **The change key as tags.** Elements tagged `new`, `changed` and `removed`
  came out in exactly the key's colours from `docs/diagrams/README.md`, and
  untagged ones in `unchanged`'s. Verified. Mermaid draws no relationship
  styles, so the command colours those lines itself
  ([Relationship colours](#relationship-colours)).
- **A relationship is tagged by its source and destination.**
  `!relationships "tle.server.games -> tle.server.proxy" { tags "removed" "wp:268" }`
  adds the tags to the relationship the map already has, which the JSON export
  shows. This is how an entry marks a relationship removed or changed.
  Verified on the pinned image (#71's change file removes six this way).
- **A tag can name the work package**, such as `wp:268`, beside the change
  state. Verified that it parses;
  [A project's change file](#a-projects-change-file) says what it is used for.

### What it does not do, and what fills the gap

1. **Views must come after the change.** A view declared `include *` in the
   map is resolved there, so a component the extension adds does not appear.
   The fix, verified: the model and the views are two files, `model.dsl` and
   `views.dsl`; the published map is a two-line `map.dsl` that extends the
   model and includes the views; a change file extends the model, makes its
   changes, and includes the same views. So the map is one model file, not
   one file in total.
2. **Tags are workspace-wide, with no per-view styles.** Inferred from the
   DSL's documentation. So one export cannot colour work package 269's
   entries while showing 268's as already done. The command adds a step before
   the export: it builds an extension holding only that package's entries,
   found by their one `wp:` tag, and exports that
   ([A package's drawing](#a-packages-drawing)). Still to come, with the first
   package that builds on another: drawing it on top of the packages it builds
   on, whose entries lose their change tag (and removed ones are excluded).
   Those packages come from the GitHub dependency links between #71's
   packages, which the board model already reads.
3. **Nothing folds an extension back into the model.** Inferred. So a release
   cannot apply its entries by running Structurizr. Two ways to meet
   "applied mechanically":
   - **a checked edit**: the release's entries are copied into `model.dsl` by
     hand (or by the change maker), and the tooling proves it right by
     exporting both "the old model plus the entries" and "the new model" and
     requiring the same result;
   - **our own writer**: a Python step that rewrites `model.dsl` from the
     entries. This means parsing the DSL, which is the part most likely to be
     fragile.
   I recommend the checked edit: the tool proves it, and the copying is small.
4. **Only the C4 views.** Structurizr draws Context, Container, Component,
   Dynamic and Deployment, not state machines, activity, use case or the
   entity-relationship diagram. Those stay hand-written Mermaid.
5. **GitHub's rendering of its labels is unchecked.** The export puts small
   HTML fragments in labels (bold name, smaller type line). The parser accepts
   them; whether GitHub shows them as intended has not been seen. The first
   commit would settle it.
6. **The cost of the dependency.** A 281 MB image with Java inside, run
   through Docker, which the development machine and CI both have. The tool
   changed its packaging once already this year.

## The proposal

### The map

```text
docs/design-map/
  model.dsl      the C4 model: people, containers, components, relationships
  views.dsl      the C4 views, each `include *`
  map.dsl        two lines: extends model.dsl, includes views.dsl
  lifecycles.md  the state machines, activity and use case diagrams, Mermaid
```

`docs/4.2.0-design-map.md` is generated: each C4 view exported from `map.dsl`,
and the diagrams from `lifecycles.md`, with the prose that says what each
view is for. The entity-relationship diagram stays in 4.2, which 2.0 links to.
Generated, like 1.5 and 1.6, so it is never edited by hand.

Each component names what implements it, as a property
(`properties { "artefact" "crates/server-game/src/app/games.rs" }`), which is
what R4's check compares with a project's impacted artefacts, and what a Code
view or a rustdoc link (#448) hangs from.

### A project's change file

One Markdown file in the project's design folder, `<N>-map-change.md`, so a
reviewer reads it on GitHub like any other design document:

- a `structurizr` fenced block holding the extension: every entry tagged with
  its change state and its `wp:` number, with a note on each;
- `mermaid` fenced blocks for the to-be lifecycles, each under a heading
  naming its work package.

The tooling reads the blocks out of the file. One file per project, as agreed,
because the fenced blocks carry both kinds.

Every statement in the extension's `model { }` is either an *entry* or a
*wrapper*. An entry carries exactly one `wp:` tag in its own `tags` line; one
with none or several is an error naming its line. A wrapper is an
`!element X { }` with no tags of its own; the command keeps it for a package
if any child entry is, holding only those children. An entry holds no element or relationship
statements of its own: children go in an untagged wrapper, and the command
rejects an entry that holds any, naming the line. The extension holds no
views; the command writes them. A heading in the file that names `#N` titles
package N's drawing.

#### The DSL the filter accepts

The command reads the extension line by line, so it takes a subset of the
DSL:

- one statement to a line;
- a block's `{` at the end of its line and its `}` on a line of its own, so a
  block spans lines;
- tags on their own `tags` line, none of them holding a comma;
- comments written `//`.

Outside the subset the command stops with an error naming the line: a `#` or
`/* */` comment, a one-line block, a stray brace or a comma in a tag.

### Drawing, applying and checking

A small programme command, on the model's pattern:

| it | does |
| --- | --- |
| draws the map | exports `map.dsl`, writes 2.0 |
| draws a work package | `design-map.py --change <N>-map-change.md --write` draws each package in number order into `<N>-map-diagrams.md` beside the change file ([A package's drawing](#a-packages-drawing)) |
| checks a release's application | exports "old model plus these entries" and "new model", and fails unless they match |
| checks R4 | every impacted artefact appears as an entry's artefact, and every entry appears in the table |

#### A package's drawing

For each package the command builds an extension of the map holding only that
package's entries, generates a view of its own, and exports it. It draws each
package alone and leaves out other packages' entries. The view includes every
element the package's entries name and both ends of every relationship entry.
It is a Component view when all the package's components share a container,
and a Container view otherwise. The command includes the map's own views too
(item 1 of [What it does not do](#what-it-does-not-do-and-what-fills-the-gap)),
so the key's styles apply, and writes only the generated views. `--check`
compares a hash of the change file and the map's sources with the one in the
header, and needs no Docker.

`--change --check` has limits. `check-docs.sh` does not run it: its step 8
runs only the map's `--check`. It runs from an application's checkout. Its
hash covers the change file and the map, not the script or the image, so a
change to either shows only when the drawing is written again.

#### Relationship colours

After every Mermaid export, the map's too, the command draws a relationship
tagged `new`, `changed` or `removed` in the stroke of the
[change key](https://github.com/delphside/tile-lite-elite/blob/main/docs/diagrams/README.md)
by a `linkStyle` line, and starts its label with the state, so it reads
without colour. It exports the workspace as JSON beside the Mermaid and
matches each line to its relationship by source, destination and description.
A line between containers is implied by relationships between their
components: the command draws the state the tagged ones agree on, `changed`
where they differ, and nothing where none is tagged. A Mermaid line of a form
the command does not count as a link is an error, since it would shift every
index after it.

## The alternative: our own format

A TOML file (Python reads it with no extra library) holding elements,
relationships and entries, and a Python generator writing Mermaid directly.
It would apply entries mechanically with no parsing problem and need no
Docker. It is also a format only this repository knows, the thing the
owner's "adopt, don't invent" rule exists to prevent, and its diagrams would
be laid out no better, since Mermaid does the layout either way. Recommended
only if Structurizr's gaps turn out worse than they look.

## Questions for the owner

1. Structurizr for the C4 views, with the four gaps filled as above?
   **Answered, owner 2026-10-17: Structurizr.**
2. Applying a release's entries by a checked edit rather than our own writer?
   **Answered, owner 2026-10-17: a checked edit.**
3. The map in `docs/design-map/`, generated into `docs/4.2.0-design-map.md`?
   **Answered, owner 2026-10-17: as proposed.**
4. A work package's generated diagrams: into the project's design folder as
   their own file, or written into the change file itself between markers,
   as the context header is written into a project's body?
   **Answered, owner 2026-10-17: their own file.**
