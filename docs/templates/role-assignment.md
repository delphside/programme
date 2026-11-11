<!-- markdownlint-disable-file MD041 -->
<!--
Who holds each role. The roles themselves are docs/1.7.
Fill it in as the programme-wide holders, records/2.2, or as an application's
role holders, `3.n.5`, where `n` is the application's index in records/2.1.
Copy it to `records/2.2-roles.md` or
`applications/<application>/3.n.5-roles.md`, and delete this comment.

A 3.n.5 keeps the rows for design authority, release manager and environments
manager, and security (the controls only: 2.2 holds the policy), and leaves
the other roles to 2.2. Release manager and environments manager are one row
while one holder holds both. The service owner is a row of 2.2, which a 3.n.5
links to for its design authority.
-->

# 2.2 Programme role holders, or 3.n.5 *Application* role holders

*Who holds the roles for the programme, or for one application, where 2.2
does not hold them. The roles are defined in 1.7; the form is this template.*

## Who holds each role here

| Role | Held by |
| --- | --- |
| owner | *a person* |
| design authority | *the owner threads in the second table, each for its workstreams* |
| technical lead | *who, per project or work package* |
| demand manager | *who* |
| release manager, environments manager | *who* |
| test manager | *who: never the thread that built the change* |
| librarian | *who* |
| security | *policy: who; an application's controls: who* |

| Owner thread | Design authority for | Kind | Runs |
| --- | --- | --- | --- |
| *name* | *workstreams from the workstream register, or none* | *permanent, for a project's life or on call* | *cloud or local* |

For each on-call authority:

| Authority | Its documents | Its skill |
| --- | --- | --- |
| *name* | *the document sections that define it* | *the skill of that authority, or none yet* |
