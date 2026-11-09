<!-- markdownlint-disable-file MD041 -->
<!--
Who holds each role. The roles themselves are docs/1.7.
Fill it in as the programme-wide holders, records 2.2, or as an application's
role holders, 3.n.5, where `n` is the application's index. A 3.n.5 keeps the
rows for design authority, release manager and environments manager, and
security (the controls half only); 2.2 holds the other roles for every
application. Delete these comments.
-->

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
| *name* | *the document sections that define it* | *the skill saying what it signs off and what it defers to, or none yet* |
