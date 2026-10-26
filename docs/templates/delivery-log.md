<!-- markdownlint-disable-file MD041 -->
<!--
The delivery log: one row per project delivery, appended, oldest first. The
rule is docs/1.2 §2.14, "The delivery log row is part of the delivery", and
the identifiers are 1.2 §1.1 "What a milestone says". The
instance is a programme record. Delete these comments.
-->

# Delivery log

*One paragraph: where the log starts, and what earlier record covers anything
before it.*

## The deliveries

| id | released (UTC) | deployed (UTC) | kind | where | what | outcome |
| --- | --- | --- | --- | --- | --- | --- |
| *the release version, production's version plus a letter, or the date (`YYYY.MM.DD-n`) in the infrastructure application's log* | *for a release, when it was made; otherwise when it was applied* | *when it reached its users; blank while a release is not yet deployed* | *release, image, host, drill, service or repository* | *the environment or service it is for* | *the project and delivery, and what it changed* | *for a release, **released, not deployed** until production; then **done**, or what was descoped, and how it was proved* |

## What each delivery left behind that git does not show

*For a delivery whose change lives outside git: what it found or left, and
where that is recorded.*
