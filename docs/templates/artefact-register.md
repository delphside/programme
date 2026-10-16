<!-- markdownlint-disable-file MD041 -->
<!--
The artefact register: everything under change control that leaves no trace in
git. The rule is docs/1.2 §2.13 (naming, and what counts as an artefact) and
§2.15 (route). The instance is an application's artefact register, 3.n.2, a
programme record that changes on main. Delete these comments.
-->

# *Application* artefacts

The application's artefacts by route, and the register of everything under
change control that leaves no trace in git. For the second part this file is
the only record, so each entry carries enough to recreate it.

## Artefacts by route

The answer to the route table in docs/1.2 §2.15: which of this application's
artefacts take each route.

| route | this application's artefacts |
| --- | --- |
| Production Release | *what ships, and what is deployed to the production host* |
| Application Tooling and Docs | *the scripts that build, test, deploy, operate or measure it, and their documents* |
| Programme Tooling and Docs | *anything else in the repository* |
| Other | *cloud resources, GitHub objects, preview and rehearsal deploys* |

## *Where they live: a host, a cloud provider, a hosted service*

*When and how this list was last verified.*

| artefact | route | what it is | why it is not in the repository |
| --- | --- | --- | --- |
| *canonical name (1.2 §2.13)* | *Production Release, or Other* | *what it does* | *a secret, a console setting, a copy made by a deploy* |

## Exit statuses in this application's scripts

The scheme is docs/1.2 §2.13; list here only what a script adds to it.

| script | 0 | non-zero |
| --- | --- | --- |
| *script* | *what success means* | *what each failure means* |

## Not yet recorded

*Artefacts known to exist and not yet described, each with the issue that will
record it.*
