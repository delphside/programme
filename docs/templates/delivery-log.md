<!-- markdownlint-disable-file MD041 -->
<!--
The instance is the application's delivery log, 3.n.1, a programme record.
The rule is docs/1.2 §2.14, "The delivery log row is part of the delivery",
and the identifiers are 1.2 §1.1 "What a milestone says". Replace the italic
text and each `n` with the application's own, and delete these comments.
-->

# 3.n.1 Delivery log

*One paragraph: where the log starts, and what earlier record covers anything
before it, if there is one.*

## The deliveries

| ID | Released (UTC) | Deployed (UTC) | Kind | Where | What | Outcome |
| --- | --- | --- | --- | --- | --- | --- |
| *the release version, or the date (`YYYY.MM.DD-n`) for any other delivery* | *for a release, when it was made; otherwise when it was applied* | *when it reached its users; `—` until a release is deployed* | *the kind of delivery: image (a release, or a preview or rehearsal deploy), host, drill, service or repository; several joined by ` · `* | *the environment or service it is for* | *each project and its delivery, and what it changed; for a release, a citation of its release record and any deploy gate set aside, with its reason* | *for a release, **released, not deployed** until it is deployed; then **done**, **done, part descoped** (what) or **failed** (what), each with how it was proved* |

## What each delivery found or left outside git

*For a delivery whose change lives outside git: what it found or left, and
where that is recorded (what it left is in the artefact register, 3.n.2).
Leave the section out when there is none.*
