"""Every GitHub field and option name the board tooling matches, once.

**One copy.** A name the tooling matches literally is a fact about GitHub's
configuration, and a script that types it again can drift from the field
silently: delphside/tile-lite-elite#326's near-miss was an option created as
`For Agreement` while the tooling read `For agreement`. So callers import the
constant, `test_vocabulary.py` fails on a literal that equals one outside this
file, and `board-check.py --vocabulary` reports a name here that GitHub no
longer has. It is a check and never a gate, and a live option the tooling does
not read is none of its business (#326 R2, R3).

`FIELDS` maps each field to the option names the tooling relies on, `()` for a
field whose options it does not match. `board-vocabulary.py` generates the data
flow from it. No I/O happens here.

Design: delphside/tile-lite-elite#383 (R19 to R22, from #326).
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# the issue fields
# --------------------------------------------------------------------------
# Owner, 2026-09-30: the lifecycle fields share one word, `State`.

REQUIREMENT_STATE = "Requirement State"
PROJECT_STATE = "Project State"
PR_STATE = "PR State"          # on the Projects board, not an issue field
TICKET_STATE = "Ticket State"
DECISION_STATE = "Decision State"
TURN = "Turn"
CLAIMED_BY = "Claimed by"
WORKSTREAM = "Workstream"
ROUTE = "Route"
TYPE_OF_CHANGE = "Type of change"
PRIORITY = "Priority"
EFFORT = "Effort"

# --------------------------------------------------------------------------
# Requirement State
# --------------------------------------------------------------------------

REQ_TRIAGE = "Triage"
REQ_SCOPE = "Scope, Options and Dependencies"
REQ_ON_HOLD = "On Hold"
REQ_READY = "Ready for Project"
REQ_CANDIDATE_1 = "Candidate Project 1"
REQ_CANDIDATE_2 = "Candidate Project 2"
REQ_CANDIDATE_3 = "Candidate Project 3"

# --------------------------------------------------------------------------
# Project State
# --------------------------------------------------------------------------

PROJ_SCOPE = "Scope"
PROJ_Q3 = "Q3"
PROJ_Q2 = "Q2"
PROJ_Q1 = "Q1"
PROJ_DESIGN = "Design and Test Approach"
PROJ_DEVELOPMENT = "Development"
PROJ_USER_TESTING = "User testing"
PROJ_DEPLOYMENT = "Deployment"
PROJ_POST_DEPLOYMENT = "Post-deployment"
PROJ_CLOSEDOWN = "Project Closedown"

# --------------------------------------------------------------------------
# Decision State
# --------------------------------------------------------------------------

DEC_ASKED = "Asked"
DEC_FEEDBACK = "Feedback Provided"
DEC_SIGN_OFF = "Documented Ready for Sign-Off"
DEC_DECIDED = "Decided"
DEC_ACTIONED = "Actioned"

# --------------------------------------------------------------------------
# PR State (derived from GitHub's own state by `board-pr-state.py`)
# --------------------------------------------------------------------------

PR_DRAFTING = "Drafting"
PR_AWAITING_REVIEW = "Awaiting review"
PR_CHANGES_REQUESTED = "Changes requested"
PR_APPROVED = "Approved"
PR_MERGED = "Merged"
PR_CLOSED = "Closed"

# --------------------------------------------------------------------------
# Ticket State
# --------------------------------------------------------------------------

TKT_NEW = "New"
TKT_IN_PROGRESS = "In progress"
TKT_WAITING_ON_SENDER = "Waiting on sender"
TKT_PENDING = "Pending"
TKT_RESOLVED = "Resolved"
TKT_REFUSED = "Refused"
TKT_CLOSED = "Closed"

# --------------------------------------------------------------------------
# Turn
# --------------------------------------------------------------------------

TURN_OWNER, TURN_CLAUDE, TURN_HOLD = "Owner", "Claude", "Hold"

# --------------------------------------------------------------------------
# Route
# --------------------------------------------------------------------------

RELEASE = "Production Release"
APPLICATION_TOOLING = "Application Tooling"
PROGRAMME_TOOLING = "Docs and Programme Tooling"
OTHER = "Other"

# The two tooling options were renamed on 2026-10-26 (owner): every document
# changed on its own is now the second's. Issues may carry the old names until
# the field's options are renamed in GitHub, so both are read.
FORMER_APPLICATION_TOOLING = "Application Tooling and Docs"
FORMER_PROGRAMME_TOOLING = "Programme Tooling and Docs"

# The Repository Change route split in two on 2026-09-29 (#421 R4). The old
# option stays on the field, marked deprecated, because closed issues carry
# it; it is matched by its prefix so renaming it to say so changes nothing.
# A prefix, not an option name: `FIELDS` does not hold it.
DEPRECATED_REPOSITORY = "Repository Change"

# --------------------------------------------------------------------------
# Type of change
# --------------------------------------------------------------------------

CHANGE_FUNCTIONAL = "functional"
CHANGE_COSMETIC = "cosmetic"
CHANGE_NON_FUNCTIONAL = "non-functional"
CHANGE_BUG = "bug"
CHANGE_TOOLING = "tooling"
CHANGE_DOCUMENTATION = "documentation"

# --------------------------------------------------------------------------
# issue types, and labels
# --------------------------------------------------------------------------

TYPE_REQUIREMENT = "Requirement"
TYPE_PROJECT = "Project"
TYPE_DECISION = "Decision"
TYPE_TICKET = "Ticket"
TYPE_PULL_REQUEST = "PullRequest"   # the model's own type for a pull request

# A delivery carrying this waits for the next release and owes nobody an
# action: the difference between "you have not done this" and "this cannot be
# done yet". Without it a Release Check project nags for a review for ever,
# which is #310.
RELEASE_CHECK = "Release Check"

ISSUE_TYPES = (TYPE_REQUIREMENT, TYPE_PROJECT, TYPE_DECISION, TYPE_TICKET)
LABELS = (RELEASE_CHECK,)

# --------------------------------------------------------------------------
# the table
# --------------------------------------------------------------------------

REQUIREMENT_STATES = (REQ_TRIAGE, REQ_SCOPE, REQ_ON_HOLD, REQ_READY,
                      REQ_CANDIDATE_1, REQ_CANDIDATE_2, REQ_CANDIDATE_3)
PROJECT_STATES = (PROJ_SCOPE, PROJ_Q3, PROJ_Q2, PROJ_Q1, PROJ_DESIGN,
                  PROJ_DEVELOPMENT, PROJ_USER_TESTING, PROJ_DEPLOYMENT,
                  PROJ_POST_DEPLOYMENT, PROJ_CLOSEDOWN)
DECISION_STATES = (DEC_ASKED, DEC_FEEDBACK, DEC_SIGN_OFF, DEC_DECIDED,
                   DEC_ACTIONED)
PR_STATES = (PR_DRAFTING, PR_AWAITING_REVIEW, PR_CHANGES_REQUESTED, PR_APPROVED,
             PR_MERGED, PR_CLOSED)
TICKET_STATES = (TKT_NEW, TKT_IN_PROGRESS, TKT_WAITING_ON_SENDER, TKT_PENDING,
                 TKT_RESOLVED, TKT_REFUSED, TKT_CLOSED)
TURNS = (TURN_OWNER, TURN_CLAUDE, TURN_HOLD)
ROUTES = (RELEASE, APPLICATION_TOOLING, PROGRAMME_TOOLING, OTHER)
# Read as their new names (`model.route_of`), so a live option may be either.
FORMER_ROUTES = (FORMER_APPLICATION_TOOLING, FORMER_PROGRAMME_TOOLING)
TYPES_OF_CHANGE = (CHANGE_FUNCTIONAL, CHANGE_COSMETIC, CHANGE_NON_FUNCTIONAL, CHANGE_BUG,
                   CHANGE_TOOLING, CHANGE_DOCUMENTATION)

# Field name -> the option names the tooling relies on. `()` where only the
# field is read. A former Route name is not here: it is read as its new one and
# its absence from GitHub is the intended end state.
FIELDS: dict[str, tuple[str, ...]] = {
    REQUIREMENT_STATE: REQUIREMENT_STATES,
    PROJECT_STATE: PROJECT_STATES,
    DECISION_STATE: DECISION_STATES,
    TICKET_STATE: TICKET_STATES,
    TURN: TURNS,
    ROUTE: ROUTES,
    TYPE_OF_CHANGE: TYPES_OF_CHANGE,
    WORKSTREAM: (),
    CLAIMED_BY: (),
    PRIORITY: (),
    EFFORT: (),
    # On the Projects board, not an organisation issue field: `PROJECT_FIELDS`.
    PR_STATE: PR_STATES,
}

# Fields the `issueFields` query cannot show, because only single-selects carry
# options and it reads those: the check says it did not look at them.
TEXT_FIELDS = (CLAIMED_BY,)

# The fields read from the Projects board (`sources.project_field_options`)
# rather than from the organisation's issue fields.
PROJECT_FIELDS = (PR_STATE,)

# Every name the ast test forbids outside this file: fields, options, issue
# types and labels, and the Route names a former one maps from.
def all_names() -> frozenset[str]:
    names = set(FIELDS) | set(FORMER_ROUTES) | {DEPRECATED_REPOSITORY}
    for options in FIELDS.values():
        names.update(options)
    names.update(ISSUE_TYPES, LABELS, (TYPE_PULL_REQUEST,))
    return frozenset(names)
