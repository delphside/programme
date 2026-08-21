# Templates

Documents you copy and fill in, rather than write from a blank page.

A template says **what must be included**; the worked examples beside it show
**how to complete it**. Both matter — a template alone leaves you guessing at
depth, and an example alone leaves you guessing at what was optional.

| template | copy it to | worked examples |
| --- | --- | --- |
| [test-design-specification.md](test-design-specification.md) | the project's folder — `docs/changes/projects/<name>/` — else the issue's | [user deletion](../changes/41-user-deletion-test-design.md) (#41, functional) · [rate limiting](../changes/25-rate-limiting-test-design.md) (#25, non-functional) |
| [post-deployment-review.md](post-deployment-review.md) | the project's folder, once its last release has been live and used | none yet — the first project to finish writes it |

## Notes

**Why a template rather than the prose that describes it.** `docs/3.3`'s "How a
test design specification is built" explains the ten parts and why each earns its place. That is
the right document to read once; it is the wrong thing to work from every time,
because turning a description into a document is work repeated at every use, and
the part you forget is invisible.

**Keep the reasoning out of the template.** The template carries what to write
and nothing else, with pointers to where the reasoning lives. A template that
argues with you while you fill it in is one people stop opening.

**Two examples, deliberately unalike.** The user-deletion specification is functional and
user-testable; rate limiting has nothing for a person to look at, so its
judgement moved into a script on the rehearsal host. A single example teaches its
own shape as though it were the rule.
