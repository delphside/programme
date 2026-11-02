<!-- markdownlint-disable-file MD041 -->
<!--
The artefact register: everything under change control that leaves no trace in
git. The rule is docs/1.2 §2.13 (naming, and what counts as an artefact) and
§2.15 (route). The instance is an application's artefact register, 3.n.2, a
programme record that changes on main. Delete these comments.
-->

# 3.n.2 *Application* artefacts

This file holds two things:

- the application's artefacts by route
- the register of everything under change control that leaves no trace in git

This file is the only record of the second, so each entry carries enough to
recreate it.

## Artefacts by route

The answer to the route table in
[1.2 §2.15](../../docs/1.2-change-lifecycle.md#route): which of this
application's artefacts take each route.

| route | this application's artefacts |
| --- | --- |
| Production Release | *this application's answer to the row in §2.15* |
| Application Tooling | *this application's answer to the row in §2.15* |
| Docs and Programme Tooling | *this application's answer to the row in §2.15* |
| Other | *this application's answer to the row in §2.15, host maintenance included* |

## *Where they live: a host, a cloud provider, a hosted service*

*One section for each place.*

*When and how this list was last verified.*

| artefact | route | what it is | why it is not in the repository |
| --- | --- | --- | --- |
| *canonical name ([1.2 §2.13](../../docs/1.2-change-lifecycle.md#213-the-impacted-artefacts-and-why-they-are-listed-early))* | *Production Release; Other; or Other, host maintenance* | *what it does* | *a secret, a console setting, a copy made by a deploy* |

## Exit statuses in this application's scripts

*Only the codes a script adds to the scheme in
[1.2 §2.13](../../docs/1.2-change-lifecycle.md#what-a-scripts-exit-status-means),
each linking to the script whose header documents it. Leave the section out
when there is none.*

## Not yet recorded

*Artefacts known to exist and not yet described, each with the issue that will
record it. Leave the section out when there is none.*
