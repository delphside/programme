# Rate Limiting — Test Plan

For issue #25. The design is in
[25-rate-limiting.md](25-rate-limiting.md); this says what is checked, what is
not, and why. It follows the method used for the user-deletion plan in #41:
conditions grouped into complete partitions, a matrix that names the
impossible combinations, and scenarios that walk several conditions each.

**There is no user testing for this change.** There is nothing for a person to
look at, and the numbers only mean anything on a machine the size of the one
they protect. The judgement moves to a script run on the rehearsal host, which
is what that environment is for.

## The rules being tested

Proposed for [1.0 Rules](../1.0-rules.md), added on this branch:

| Id | Rule |
| --- | --- |
| LIMIT-1 | The service limits how often a caller may ask, separately from how much work it will do at once |
| LIMIT-2 | A caller over its allowance is refused, not queued |
| LIMIT-3 | An allowance belongs to its caller — being refused never depends on somebody else's traffic, except at the global floor |
| LIMIT-4 | `/health` is never limited |
| LIMIT-5 | Exceeding an allowance slows a caller; it does not lock them out for a fixed window |
| LIMIT-6 | Rate limits protect the service from load. They are not how bad behaviour is dealt with |
| LIMIT-7 | Every limit is tunable per host without a rebuild |

LIMIT-6 is not testable and is here because it decides how the others are
read: a test that asserted an attacker was stopped would be asserting
something we have deliberately not built.

## Conditions

Four dimensions. Each is a **complete** partition — the values are mutually
exclusive and cover every case.

**W — who is asking** (complete)

- **W1** unauthenticated, address known — `X-Forwarded-For` present
- **W2** unauthenticated, address unknown — no header and no peer address
- **W3** authenticated — a session token

**R — what they are asking for** (complete over the routed surface)

- **R1** registration
- **R2** heavy auth — login, forgot-password, reset-password
- **R3** any other player route, including the events upgrade
- **R4** `/health`
- **R5** admin

**H — how much this caller has asked** (complete)

- **H1** within the burst
- **H2** over the allowance
- **H3** over, then waited at least one period

**E — what everybody else is doing** (complete)

- **E1** nobody else near a limit
- **E2** another caller is over its allowance
- **E3** the service as a whole is over the global floor

## Outcomes

- **Served** — the limiter passes the request to the handler. What the handler
  then answers is not this change's business; a rejected password is a 401 and
  still counts as served.
- **Refused** — `429`, without reaching the handler.

## Matrix: route against the caller's own traffic

∅ marks a combination that cannot arise.

| | H1 within | H2 over | H3 waited |
| --- | --- | --- | --- |
| **R1** registration | Served | Refused | Served |
| **R2** heavy auth | Served | Refused | Served |
| **R3** other player routes | Served | Refused | Served |
| **R4** health | Served | ∅ — no allowance to exceed | ∅ |
| **R5** admin | Served | ∅ — outside every layer | ∅ |

## Matrix: who is asking against which bucket they land in

| | R1 registration | R2 heavy auth | R3 other | R4 health | R5 admin |
| --- | --- | --- | --- | --- | --- |
| **W1** address known | address | address | address | ∅ — unlimited | ∅ — loopback only |
| **W2** address unknown | one shared bucket | one shared bucket | one shared bucket | ∅ | Served |
| **W3** session | address | address | session | ∅ | ∅ — loopback only |

Two cells are worth reading twice. **W3 × R1** keys by address, not session:
registration is limited by where the request came from whether or not the
caller is already signed in, because a signed-in caller manufacturing accounts
is the case being stopped. And **W2** exists only in-process — every request
from outside carries one or the other — which is why it collapses to a single
bucket rather than being an evasion.

## Matrix: the caller against everybody else

| | E1 quiet | E2 another caller over | E3 service over the floor |
| --- | --- | --- | --- |
| keyed routes, caller within allowance | Served | Served | Refused |
| `/health` | Served | Served | Served |

The middle column is LIMIT-3 and the right-hand one is its stated exception:
the global floor is the one place a caller can be refused for somebody else's
traffic, which is the price of having a floor at all.

## Scenarios

Each walks several conditions. **T** are automated and run in CI; **S** are
steps of the rehearsal script.

| | Scenario | Conditions | Rules |
| --- | --- | --- | --- |
| T1 | The key is the forwarded client, not the proxy that relayed it | W1 | LIMIT-3 |
| T2 | The leftmost entry of a two-proxy chain wins | W1 | LIMIT-3 |
| T3 | Two sessions from one address are two callers, and an anonymous caller is a third | W1, W3, R3 | LIMIT-3 |
| T4 | Four requests against a burst of two: the fourth is refused, not delayed | H1 → H2 | LIMIT-1, LIMIT-2 |
| T5 | A second address still gets its own allowance while the first is refused | H2, E2 | LIMIT-3 |
| S1 | Registering repeatedly from one address is refused within eight attempts | W1, R1, H1 → H2 | LIMIT-1, LIMIT-2 |
| S2 | `/health` still answers while that caller is being refused | R4, E2 | LIMIT-4 |
| S3 | A different address registers successfully at the same moment | W1, R1, E2 | LIMIT-3 |
| S4 | Logging in repeatedly from one address is refused within twenty attempts | W1, R2, H2 | LIMIT-1, LIMIT-2 |

S1 to S4 are one run of `./scripts/check-rate-limits.sh` against rehearsal,
which uses a fresh random address pair per run so a re-run is not refused by
the buckets the last one filled.

## Coverage, both ways

### Every rule to a scenario

| Rule | Covered by | |
| --- | --- | --- |
| LIMIT-1 | T4, S1, S4 | ✓ |
| LIMIT-2 | T4, S1, S4 | ✓ |
| LIMIT-3 | T1, T2, T3, T5, S3 | ✓ |
| LIMIT-4 | S2 | ✓ |
| LIMIT-5 | — | **gap** |
| LIMIT-6 | not testable by design | n/a |
| LIMIT-7 | — | **gap** |

### Every condition to a scenario

| Condition | Covered by | |
| --- | --- | --- |
| W1 address known | T1, T2, T4, T5, S1–S4 | ✓ |
| W2 address unknown | — | **gap**, in-process only |
| W3 session | T3 | ✓ |
| R1 registration | S1, S3 | ✓ |
| R2 heavy auth | S4 | ✓ |
| R3 other player routes | T3 | partial — keying only, never a refusal |
| R4 health | S2 | ✓ |
| R5 admin | — | **gap** |
| H1 within | T4, T5, S1 | ✓ |
| H2 over | T4, S1, S4 | ✓ |
| H3 waited | — | **gap** |
| E1 quiet | all | ✓ |
| E2 another caller over | T5, S2, S3 | ✓ |
| E3 over the global floor | — | **gap** |

## The gaps, and what I would do about them

Five, in the order I would close them.

**Replenishment (LIMIT-5, H3).** "Slowed rather than locked out" is claimed in
the design note and in the code and asserted nowhere. A config that locked a
caller out for a full window would pass every test here. Cheap to close: a unit
test with a short period that exhausts the burst, waits, and asserts the next
request is served.

**The environment parsing (LIMIT-7).** `limit_from_env` and `burst_from_env`
have no test, and the case they exist for is the one that has already taken a
deploy down — Compose passes `${VAR:-}` as an empty string, so an *empty*
value must fall back to the default exactly as an unset one does. Cheap, and
the failure it guards against is silent: the limits would quietly become
whatever the default is, or fail to build the config at all.

**The wiring (R5, and the tiers generally).** The limits are off under
`cfg(test)`, so no test exercises `build_router` — only the layer it applies.
A tier attached to the wrong routes, or admin accidentally inside the global
layer, would pass CI and only show up in rehearsal. Closing this properly means
a test that builds the router with limits *on*, which is a bigger change than
the others and may not be worth it; the rehearsal script covers the cases that
matter most.

**The global floor (E3).** The one tier a caller cannot detect from their own
traffic, and the one that refuses people who have done nothing wrong. Hard to
test from outside without generating 1200 requests a minute, which is #28's
job rather than this script's. A unit test against a router with a small global
limit would at least prove the tier does what it says.

**W2, the shared bucket.** Reachable only in-process, and the code path exists
to stop a request with no address from panicking rather than to be relied on.
Low value.

## Not in scope

**Whether the numbers are right.** 2 registrations a minute, 240 requests a
minute for a signed-in caller: these are a first guess for a 954 MB box and
nothing here measures them. That needs sustained load against the rehearsal
host, which is #28 — the third of the three changes the design note sets out,
after #11's concurrency bounds and this one.

**The `429` versus `503` distinction**, which #28 expects and this change does
not yet make. Recorded in the design note as a decision to settle before
release rather than a gap in this plan.

**A WebSocket's message rate.** The upgrade is limited; what flows over the
socket afterwards is not. Recorded as a known gap in the design note.
