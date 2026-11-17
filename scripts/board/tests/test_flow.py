"""The board flow: the flow table, the daily sweep (`board-flow.py`) and the role
lists (`board-actions.py --role`), delphside/programme#176.

Written from the test design (`records/2.5-changes/process-definition/
176-project-board-flow/test-design.md`, parts 5 and 9), not from the code. Each
test builds its own world in `world.py`, a stand-in for GitHub's REST API that
refuses GraphQL, logs every write and has a fixed *now*, so boundaries are exact
to the minute. The scenario each test serves is named in its docstring.

R15's tests (the session-start list and the comment check) are not here, and
the [TT] tests are run by hand against the real repositories."""

import importlib.util
import io
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from board import flow, merge, model, sources
from board.model import FLOW, HOLDERS, ROLES

from .cases import Cases
from .profiles import FIXTURES
from .world import BY_ID, NOW, REPOS, World, ago

PRG, DP, INF, SD, TLE = REPOS
D = timedelta
FLOW_CONFIG = FIXTURES / "programme-flow.toml"
SCRIPTS = Path(__file__).resolve().parents[1]
OWNER_LOGIN = "fake-owner"
THREAD = "https://claude.ai/code/session_abc123"


def load_script(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_").removesuffix(".py"),
                                                  SCRIPTS / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Flow(Cases):
    """A world, the five repositories' fake programme file, and helpers."""

    def setUp(self):
        saved = {k: os.environ.get(k) for k in ("PROGRAMME_CONFIG", "BOARD_REPOSITORY")}

        def restore():
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        self.addCleanup(restore)
        os.environ["PROGRAMME_CONFIG"] = str(FLOW_CONFIG)
        self.w = World()
        patch = mock.patch("subprocess.run", lambda *a, **k: self.w(*a, **k))
        patch.start()
        self.addCleanup(patch.stop)

    # -- running ----------------------------------------------------------
    def go(self, dry_run=False, now=NOW):
        said, complained = [], []
        code = flow.run(now, dry_run=dry_run, say=said.append, complain=complained.append)
        return SimpleNamespace(code=code, out="\n".join(said), err="\n".join(complained))

    def survey(self, now=NOW):
        return flow.survey(now)

    def verdict(self, repo, number, now=NOW):
        sweep = self.survey(now)
        return next(v for v in sweep.verdicts if v.name == f"{repo}#{number}")

    def stalled(self, now=NOW):
        return {v.name for v in self.survey(now).stalled}

    def attention(self, kind):
        return [(v.name, a.role) for v, a in self.survey().attention if a.kind == kind]

    def actions(self, *args):
        actions = load_script("board-actions.py")
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = actions.main(list(args))
        return SimpleNamespace(code=code, out=out.getvalue(), err=err.getvalue())

    # -- what was written -------------------------------------------------
    def fields_written(self):
        out = []
        for _, path, payload in self.w.field_writes():
            parts = path.split("/")
            for entry in payload["issue_field_values"]:
                out.append((f"{parts[1]}/{parts[2]}", int(parts[4]), BY_ID[entry["field_id"]],
                            entry["value"]))
        return out

    def turns_written(self):
        return [(r, n, v) for r, n, name, v in self.fields_written() if name == "Turn"]

    def turns_written_by_go(self):
        self.go()
        return self.turns_written()

    def type_writes(self):
        return [(p.split("/")[2] and f"{p.split('/')[1]}/{p.split('/')[2]}", int(p.split("/")[4]),
                 payload["type"])
                for m, p, payload in self.w.log if m == "PATCH" and "type" in payload]

    # -- building ---------------------------------------------------------
    def req(self, n, state, since, ws="Tooling", repo=TLE, turn=None, **kw):
        fields = {}
        if state:
            fields["Requirement State"] = state
        if ws:
            fields["Workstream"] = ws
        if turn:
            fields["Turn"] = turn
        return self.w.add_issue(repo, n, "Requirement", fields=fields, since=since, **kw)

    def proj(self, n, state, since, ws="Tooling", repo=TLE, turn=None, route="Production Release",
             **kw):
        fields = {"Project State": state}
        if ws:
            fields["Workstream"] = ws
        if turn:
            fields["Turn"] = turn
        if route:
            fields["Route"] = route
        return self.w.add_issue(repo, n, "Project", fields=fields, since=since, **kw)

    def decision(self, n, state, since, ws="Tooling", repo=TLE, turn=None, **kw):
        fields = {"Decision State": state, "Workstream": ws}
        if turn:
            fields["Turn"] = turn
        return self.w.add_issue(repo, n, "Decision", fields=fields, since=since, **kw)

    def age_in_ledger(self, repo, n, **delta):
        """Say in the pinned issue's ledger that the sweep first saw the item in its
        state `delta` before now: the way a test ages an item the sweep has seen."""
        ledger = flow.parse_ledger(self.w.pinned_body())
        seen = ledger[name(repo, n)]
        ledger[name(repo, n)] = flow.Seen(seen.state, NOW - D(**delta), seen.turn)
        self.w.issues[(PRG, 900)]["body"] = flow.render_ledger(ledger)

    def ticket(self, n, state, since, repo=SD, turn=None, **kw):
        fields = {"Ticket State": state}
        if turn:
            fields["Turn"] = turn
        return self.w.add_issue(repo, n, "Ticket", fields=fields, since=since, **kw)


def name(repo, n):
    return f"{repo}#{n}"


# --------------------------------------------------------------------------
# starting states and types (R7)
# --------------------------------------------------------------------------


class StartingStates(Flow):

    def test_untyped_issue_in_each_repository_becomes_a_requirement(self):
        """S1, O1: an untyped issue in each of the five repositories is typed
        Requirement and given its starting state."""
        for i, repo in enumerate(REPOS):
            self.w.add_issue(repo, 50 + i, None)
        self.go()
        self.expect("one type write per repository",
                    sorted(REPOS), sorted(r for r, _, _ in self.type_writes()))
        for i, repo in enumerate(REPOS):
            self.expect(f"{repo} is a Requirement", "Requirement",
                        self.w.issues[(repo, 50 + i)]["type"]["name"])
            self.expect(f"{repo} starts at Triage", "Triage",
                        self.w.field(repo, 50 + i, "Requirement State"))
        self.expect("the pinned issue is not swept", False,
                    "Turn" in self.w.issues[(PRG, 900)]["_fields"])

    def test_pull_request_is_never_given_an_issue_type(self):
        """S2, O1: a world of typed issues and pull requests makes no type write
        and no issue-field write to a pull request; one untyped issue is typed."""
        for i, repo in enumerate(REPOS):
            self.req(10 + i, "Scope, Options and Dependencies", D(hours=1), repo=repo, turn="Claude")
            self.w.add_pull(repo, 70 + i, reviewers=1)
        self.go()
        self.expect("no type written", [], self.type_writes())
        pulls = {(r, 70 + i) for i, r in enumerate(REPOS)}
        self.expect("no field written to a pull request", [],
                    [w for w in self.fields_written() if (w[0], w[1]) in pulls])
        self.w.add_issue(TLE, 99, None)
        self.w.log.clear()
        self.go()
        self.expect("the one untyped issue is typed", [(TLE, 99, "Requirement")], self.type_writes())

    def test_stateless_project_starts_at_scope(self):
        """S1, O2: a Project with no state is written Scope."""
        self.w.add_issue(TLE, 20, "Project", fields={"Workstream": "Tooling"})
        self.go()
        self.expect("Scope", "Scope", self.w.field(TLE, 20, "Project State"))
        self.expect("and its turn", "Claude", self.w.field(TLE, 20, "Turn"))

    def test_stateless_ticket_starts_at_new(self):
        """S1, S10, O2: a Ticket starts at New, a Decision at Asked (S-G6)."""
        self.w.add_issue(SD, 21, "Ticket")
        self.w.add_issue(TLE, 22, "Decision", fields={"Workstream": "Tooling"})
        self.go()
        self.expect("Ticket New", "New", self.w.field(SD, 21, "Ticket State"))
        self.expect("Decision Asked", "Asked", self.w.field(TLE, 22, "Decision State"))
        self.expect("the Ticket is the owner's", "Owner", self.w.field(SD, 21, "Turn"))

    def test_rerun_writes_nothing_once_states_are_valid(self):
        """S1, S31, O5: a rerun writes nothing but the pinned issue's body."""
        self.w.add_issue(DP, 30, None)
        self.w.add_issue(SD, 31, "Ticket")
        self.w.add_issue(TLE, 32, "Project", fields={"Workstream": "Tooling"})
        self.w.add_pull(INF, 33, reviewers=1)
        self.go()
        self.w.log.clear()
        self.go()
        self.expect("no field", [], self.fields_written())
        self.expect("no type", [], self.type_writes())
        self.expect("only the pinned body", [(PRG, 900)],
                    [(p.split("/")[1] + "/" + p.split("/")[2], int(p.split("/")[4]))
                     for _, p, _ in self.w.body_writes()])

    def test_project_without_workstream_is_raised_with_the_owner(self):
        """S4, O3: a Project with no workstream is listed for the owner, and
        quiet once it has one."""
        self.proj(40, "Scope", D(hours=1), ws=None, turn="Claude")
        run = self.go()
        self.expect("listed", True, "no workstream" in run.out)
        self.expect("under the owner", True,
                    any(a.kind == flow.NO_WORKSTREAM and a.role == "owner"
                        for _, a in self.survey().attention))
        self.w.issues[(TLE, 40)]["_fields"]["Workstream"] = "Tooling"
        self.expect("quiet once set", False, "no workstream" in self.go().out)

    def test_requirement_without_workstream_is_left_for_triage(self):
        """S4: a Requirement with no workstream is the owner's at triage and is
        not listed as missing one."""
        self.req(41, "Triage", D(hours=1), ws=None)
        run = self.go()
        self.expect("not listed as missing a workstream", False, "no workstream" in run.out)
        self.expect("its turn is the owner's", "Owner", self.w.field(TLE, 41, "Turn"))
        self.expect("the holder is the owner", "owner", self.verdict(TLE, 41).role)

    def test_unknown_state_value_is_reported_not_defaulted(self):
        """S35, S-G17: a state the table does not hold is reported, never
        rewritten, and with no Turn it is lost to its type's role."""
        self.req(42, "Backlog", D(days=1))
        run = self.go()
        self.expect("reported", True, "unknown state" in run.out)
        self.expect("lost", True, "lost" in run.out)
        self.expect("the state is not rewritten", "Backlog",
                    self.w.field(TLE, 42, "Requirement State"))
        self.expect("to the type's role", "design-authority", self.verdict(TLE, 42).role)


# --------------------------------------------------------------------------
# bounds and stalling
# --------------------------------------------------------------------------


class Bounds(Flow):

    def test_triage_is_stalled_one_minute_past_a_day(self):
        """S3, O6: an unset Requirement and a Triage one are stalled at 24 h 01 min,
        under the workstream's design authority."""
        self.req(1, None, D(hours=24, minutes=1))
        self.req(2, "Triage", D(hours=24, minutes=1))
        sweep = self.survey()
        for n in (1, 2):
            v = next(v for v in sweep.verdicts if v.name == name(TLE, n))
            self.expect(f"#{n} stalled", True, v.stalled)
            self.expect(f"#{n} held by the design authority", "design-authority", v.role)
            self.expect(f"#{n} bound a day", 1, v.bound)

    def test_triage_at_exactly_a_day_is_not_stalled(self):
        """S3, O7: at 24 h and at 23 h 59 min nothing is stalled."""
        self.req(1, None, D(hours=24))
        self.req(2, "Triage", D(hours=24))
        self.req(3, None, D(hours=23, minutes=59))
        self.req(4, "Triage", D(hours=23, minutes=59))
        self.expect("none", set(), self.stalled())

    def test_scope_requirement_is_stalled_past_seven_days_under_its_design_authority(self):
        """S5: Scope at 6 d 23 h 59 min and 7 d is quiet; 7 d 1 min is stalled."""
        scope = "Scope, Options and Dependencies"
        self.req(1, scope, D(days=6, hours=23, minutes=59), turn="Claude")
        self.req(2, scope, D(days=7), turn="Claude")
        self.req(3, scope, D(days=7, minutes=1), turn="Claude")
        self.expect("only the last", {name(TLE, 3)}, self.stalled())
        self.expect("under its design authority", ("design-authority", "Tooling"),
                    flow._place(self.verdict(TLE, 3)))

    def test_queues_and_candidate_slots_two_and_three_never_stall(self):
        """S5, S7: the queues have no bound, however long an item sits."""
        for n, state in enumerate(("Ready for Project", "Candidate Project 2",
                                   "Candidate Project 3"), start=1):
            self.req(n, state, D(days=90), turn="Claude")
        for n, state in enumerate(("Q1", "Q2", "Q3"), start=10):
            self.proj(n, state, D(days=90), turn="Claude")
        self.expect("none", set(), self.stalled())
        self.expect("no bound", None, self.verdict(TLE, 1).bound)

    def test_candidate_project_one_stalls_past_seven_days_under_the_demand_manager(self):
        """S6, S-G8: Candidate Project 1 is a move owed (raise its project)."""
        self.req(1, "Candidate Project 1", D(days=2), turn="Claude")
        self.req(2, "Candidate Project 1", D(days=8), turn="Claude")
        self.expect("only the older", {name(TLE, 2)}, self.stalled())
        self.expect("the demand manager's", "demand-manager", self.verdict(TLE, 2).role)

    def test_project_phases_stall_past_seven_days(self):
        """S7: Scope, Design and Test Approach, User testing and Project Closedown,
        one minute under and one minute past seven days."""
        roles = {"Scope": "design-authority", "Design and Test Approach": "design-authority",
                 "User testing": "technical-lead", "Project Closedown": "technical-lead"}
        for i, state in enumerate(roles):
            self.proj(10 + i, state, D(days=6, hours=23, minutes=59), turn="Claude")
            self.proj(20 + i, state, D(days=7, minutes=1), turn="Claude")
        want = {name(TLE, 20 + i) for i in range(len(roles))}
        self.expect("only those past", want, self.stalled())
        for i, (state, role) in enumerate(roles.items()):
            self.expect(f"{state} holder", role, self.verdict(TLE, 20 + i).role)

    def test_post_deployment_stalls_fourteen_days_after_it_began(self):
        """S7, S-G12: Post-deployment at 13 d 23 h 59 min and 14 d is quiet; 14 d 1 min stalls."""
        self.proj(1, "Post-deployment", D(days=13, hours=23, minutes=59), turn="Claude")
        self.proj(2, "Post-deployment", D(days=14), turn="Claude")
        self.proj(3, "Post-deployment", D(days=14, minutes=1), turn="Claude")
        self.expect("only the last", {name(TLE, 3)}, self.stalled())

    def test_q1_and_deployment_never_stall(self):
        """S7: Q1 and Deployment, at ninety days, are quiet; Deployment is a hold."""
        self.proj(1, "Q1", D(days=90), turn="Claude")
        self.proj(2, "Deployment", D(days=90), turn="Hold", milestone=("1.0.0", "open"))
        self.expect("none", set(), self.stalled())
        self.expect("Deployment is a hold on its release", "Hold", self.verdict(TLE, 2).turn)

    def test_development_age_is_read_from_the_pull_requests_head_commit(self):
        """S8, S-G11: the field moved 30 days ago; the head commit 1 day ago, then
        8 days ago; with no pull request, the field's age."""
        self.proj(1, "Development", D(days=30), turn="Claude")
        self.w.add_pull(TLE, 101, body="Refs #1", commit_age=D(days=1))
        self.proj(2, "Development", D(days=30), turn="Claude")
        self.w.add_pull(TLE, 102, body="Refs #2", commit_age=D(days=8))
        self.proj(3, "Development", D(days=30), turn="Claude")
        self.proj(4, "Development", D(days=1), turn="Claude")
        self.expect("by commit, and the field's age with none", {name(TLE, 2), name(TLE, 3)},
                    self.stalled())
        self.expect("the technical lead's", "technical-lead", self.verdict(TLE, 2).role)

    def test_parent_waiting_on_open_packages_does_not_stall(self):
        """S9, S-G10: a parent at its resting phase rests while a package is open;
        when the last closes, the bound runs."""
        self.proj(1, "Design and Test Approach", D(days=30), turn="Claude", route=None,
                  sub=((11, "Project", "open"),))
        self.expect("resting", set(), self.stalled())
        self.expect("held by the design authority", "design-authority", self.verdict(TLE, 1).role)
        self.w.issues[(TLE, 1)]["_sub"] = [(11, "Project", "closed")]
        self.expect("stalled once the last closes", {name(TLE, 1)}, self.stalled())

    def test_decision_stalls_past_seven_days_on_whoevers_turn_it_is(self):
        """S10, M6: each state at 6 and 8 days, under the owner or the design authority."""
        holders = {"Asked": "owner", "Feedback Provided": "design-authority",
                   "Documented Ready for Sign-Off": "owner", "Decided": "design-authority",
                   "Actioned": "owner"}
        turns = {"owner": "Owner", "design-authority": "Claude"}
        for i, (state, role) in enumerate(holders.items()):
            self.decision(10 + i, state, D(days=6), turn=turns[role])
            self.decision(20 + i, state, D(days=8), turn=turns[role])
        self.expect("those at eight days", {name(TLE, 20 + i) for i in range(5)}, self.stalled())
        for i, role in enumerate(holders.values()):
            self.expect(f"holder {i}", role, self.verdict(TLE, 20 + i).role)

    def test_pull_request_stalls_past_seven_days_in_any_state(self):
        """S11: Drafting, Awaiting review and Changes requested at 6 and 8 days."""
        kinds = {"Drafting": dict(draft=True), "Awaiting review": dict(reviewers=1),
                 "Changes requested": dict(review="CHANGES_REQUESTED")}
        for i, kw in enumerate(kinds.values()):
            self.w.add_pull(TLE, 30 + i, since=D(days=6), **kw)
            self.w.add_pull(TLE, 40 + i, since=D(days=8), **kw)
        self.expect("those at eight days", {name(TLE, 40 + i) for i in range(3)}, self.stalled())
        roles = [self.verdict(TLE, 40 + i).role for i in range(3)]
        self.expect("Awaiting review is the owner's, the rest its author's",
                    ["author", "owner", "author"], roles)

    def test_pending_ticket_stalls_after_its_review_date(self):
        """S13: Pending with its review date tomorrow, then yesterday; New and
        In progress at 6 and 8 days."""
        tomorrow, yesterday = "2026-11-16", "2026-11-14"
        self.ticket(1, "Pending", D(days=30), turn="Owner",
                    comments=(("someone", f"Review date: {tomorrow}", D(days=3)),))
        self.ticket(2, "Pending", D(days=30), turn="Owner",
                    comments=(("someone", f"Review date: {yesterday}", D(days=3)),))
        for i, state in enumerate(("New", "In progress", "Resolved", "Refused")):
            self.ticket(10 + i, state, D(days=6), turn="Owner")
            self.ticket(20 + i, state, D(days=8), turn="Owner")
        want = {name(SD, 2)} | {name(SD, 20 + i) for i in range(4)}
        self.expect("the stalled", want, self.stalled())
        self.expect("under the owner", "owner", self.verdict(SD, 2).role)

    def release_check_world(self, closed_ago, turn="Hold", state="Post-deployment"):
        """A Release Check package whose own release 1.0.0 shipped, and a next
        release 1.1.0 (`closed_ago` before now, or open when None)."""
        self.w = World()
        self.proj(1, state, D(days=90), turn=turn, labels=("Release Check",),
                  milestone=("1.0.0", "closed"))
        self.w.add_milestone(TLE, "1.0.0", "closed", D(days=100))
        if closed_ago is None:
            self.w.add_milestone(TLE, "1.1.0", "open")
        else:
            self.w.add_milestone(TLE, "1.1.0", "closed", closed_ago)

    def test_release_check_package_at_post_deployment_holds_until_the_next_release(self):
        """S7, S-G2: for ninety days, with the next release open, and again with
        none raised: quiet, and `Turn` is Hold."""
        self.release_check_world(None, turn=None)
        v = self.verdict(TLE, 1)
        self.expect("open next release: Hold", ("Hold", False), (v.turn, v.stalled))
        self.expect("and written", [(TLE, 1, "Hold")], self.turns_written_by_go())
        self.release_check_world(None, turn=None)
        self.w.milestones[TLE] = [m for m in self.w.milestones[TLE] if m["title"] == "1.0.0"]
        v = self.verdict(TLE, 1)
        self.expect("no next release raised: still Hold", ("Hold", False), (v.turn, v.stalled))

    def test_release_check_package_stalls_seven_days_after_the_next_release_closes(self):
        """S54, M4: the hold ends when the next release closes, is reported and
        rewritten; the review is then stalled 7 days after the close."""
        self.release_check_world(D(days=7, minutes=-1))
        run = self.go()
        self.expect("the ended hold is reported", True, "invalid hold" in run.out)
        self.expect("and Turn rewritten", [(TLE, 1, "Claude")], self.turns_written())
        for label, closed, stalled in (("1 minute under", D(days=6, hours=23, minutes=59), False),
                                       ("exactly at", D(days=7), False),
                                       ("1 minute past", D(days=7, minutes=1), True)):
            self.release_check_world(closed, turn="Claude")
            v = self.verdict(TLE, 1)
            self.expect(label, stalled, v.stalled)
            self.expect(f"{label}: age counted from the close", closed, v.age)

    def test_release_check_package_with_a_date_milestone_holds_until_the_next_release_closes(self):
        """M4: a package whose own milestone is a date waits for the lowest semver
        milestone that is open or closed after it entered Post-deployment; a
        release that closed before it entered does not end the hold."""
        for label, own in (("a date milestone", ("2026.11.01-1", "closed")), ("none", None)):
            self.w = World()
            self.proj(1, "Post-deployment", D(days=3), turn="Hold", labels=("Release Check",),
                      milestone=own)
            self.w.add_milestone(TLE, "1.0.0", "closed", D(days=100))
            self.w.add_milestone(TLE, "1.1.0", "open")
            self.expect(f"{label}: waits on the open release", ("Hold", set()),
                        (self.verdict(TLE, 1).turn, self.stalled()))
            self.w.milestones[TLE][-1].update(state="closed", closed_at=ago(days=1))
            self.expect(f"{label}: the hold ends when it closes",
                        [(name(TLE, 1), "technical-lead")], self.attention(flow.INVALID_HOLD))
            self.expect(f"{label}: Turn rewritten", [(TLE, 1, "Claude")],
                        self.turns_written_by_go())

    def test_nothing_stalled_publishes_an_empty_list_and_exits_clean(self):
        """S22, O17: everything within its bound: an empty list, the run's time, exit 0."""
        self.quiet_world()
        run = self.go()
        self.expect("exit 0", 0, run.code)
        self.expect("says so", True, "Nothing is stalled." in run.out)
        self.expect("the pinned issue says so and gives the time", True,
                    "Nothing is stalled." in self.w.pinned_body()
                    and "Last complete run: 2026-11-15T12:00:00Z" in self.w.pinned_body())

    def quiet_world(self):
        self.req(1, "Scope, Options and Dependencies", D(days=1), turn="Claude")
        self.proj(2, "Development", D(days=1), turn="Claude")
        self.decision(3, "Asked", D(days=1), turn="Owner")
        self.ticket(4, "In progress", D(days=1), turn="Owner")
        self.w.add_pull(TLE, 105, reviewers=1, since=D(days=1))

    def test_one_item_past_its_bound_breaks_the_quiet_list(self):
        """S22, O20: age one item one minute past its bound: it is listed, exit 1."""
        self.quiet_world()
        self.expect("quiet", 0, self.go().code)
        self.age_in_ledger(TLE, 1, days=7, minutes=1)
        run = self.go()
        self.expect("exit 1", 1, run.code)
        self.expect("listed", True, name(TLE, 1) in self.w.pinned_body())


# --------------------------------------------------------------------------
# turn and holds
# --------------------------------------------------------------------------


class Turns(Flow):

    def test_decision_turn_alternates_owner_and_claude(self):
        """S10, M6: Asked, Documented and Actioned are the owner's; Feedback Provided
        and Decided are Claude's. DECISION_TURNS agrees with the table."""
        states = ["Asked", "Feedback Provided", "Documented Ready for Sign-Off", "Decided",
                  "Actioned"]
        for i, state in enumerate(states):
            self.decision(10 + i, state, D(hours=1))
        self.go()
        got = [self.w.field(TLE, 10 + i, "Turn") for i in range(5)]
        self.expect("alternating", ["Owner", "Claude", "Owner", "Claude", "Owner"], got)
        self.expect("DECISION_TURNS agrees",
                    {s: model.OWNER if t == "Owner" else model.CLAUDE
                     for s, t in zip(states, got)},
                    {s: who for s, (who, _) in model.DECISION_TURNS.items()})

    def test_derivable_turn_is_written_and_a_wrong_one_corrected(self):
        """S14, O4: unset, then wrong, are written once each; right is not."""
        self.proj(1, "Development", D(hours=1))
        self.proj(2, "Development", D(hours=1), turn="Owner")
        self.decision(3, "Asked", D(hours=1), turn="Owner")
        self.go()
        self.expect("unset and wrong written", [(TLE, 1, "Claude"), (TLE, 2, "Claude")],
                    self.turns_written())

    def test_correct_turn_is_not_rewritten(self):
        """S14, O5: a Turn equal to the derived value is left alone."""
        self.proj(1, "Development", D(hours=1), turn="Claude")
        self.decision(3, "Asked", D(hours=1), turn="Owner")
        self.go()
        self.expect("no write", [], self.fields_written())

    def test_item_with_no_derivable_turn_and_none_set_is_reported_lost(self):
        """S16: an item whose holder the table cannot place and with no Turn is
        lost, to the owner where its type is unknown; quiet once a Turn is set."""
        self.w.add_issue(TLE, 5, "Task", fields={"Workstream": "Tooling"})
        run = self.go()
        self.expect("lost", True, "lost" in run.out)
        self.expect("to the owner", True,
                    any(a.kind == flow.LOST and a.role == "owner" for _, a in self.survey().attention))
        self.expect("not given a Turn", None, self.w.field(TLE, 5, "Turn"))
        self.w.issues[(TLE, 5)]["_fields"]["Turn"] = "Claude"
        self.expect("not lost once set", False,
                    any(a.kind == flow.LOST for _, a in self.survey().attention))

    def hold(self, n, **kw):
        kw.setdefault("blocked_by", ())
        return self.req(n, "Scope, Options and Dependencies", D(days=30), turn="Hold", **kw)

    def test_hold_with_an_open_dependency_rests(self):
        """S17, O7: a Hold on an open linked issue is kept and does not stall."""
        self.hold(1, blocked_by=((TLE, 99, "open"),))
        self.expect("kept", [], self.turns_written_by_go())
        self.expect("not stalled", set(), self.stalled())
        self.expect("nothing reported", [], self.attention(flow.INVALID_HOLD))

    def test_hold_whose_dependency_closed_returns_to_its_role(self):
        """S17, O18, S-G14: the dependency closes: reported for its role, and Turn
        rewritten to the derived value."""
        self.hold(1, blocked_by=((TLE, 99, "closed"),))
        self.expect("reported", [(name(TLE, 1), "design-authority")],
                    self.attention(flow.INVALID_HOLD))
        self.expect("rewritten", [(TLE, 1, "Claude")], self.turns_written_by_go())

    def test_hold_without_a_reason_is_reported(self):
        """S17, O18: a Hold with nothing named under its dependencies."""
        self.hold(1)
        self.expect("reported", [(name(TLE, 1), "design-authority")],
                    self.attention(flow.INVALID_HOLD))

    def test_hold_past_its_review_date_is_reported(self):
        """S17: a named event with its review date tomorrow holds; yesterday does not."""
        text = "## Dependencies and related work\n\nWaiting on the vendor. Review date: {}\n"
        self.hold(1, body=text.format("2026-11-16"))
        self.hold(2, body=text.format("2026-11-14"))
        self.expect("only the second", [(name(TLE, 2), "design-authority")],
                    self.attention(flow.INVALID_HOLD))

    def test_hold_on_an_open_release_milestone_rests_until_it_closes(self):
        """S17, O18: Deployment waits on its own open release milestone; once it
        closes the hold ends and the package is moved to Post-deployment."""
        self.proj(1, "Deployment", D(days=30), turn="Hold", milestone=("1.0.0", "open"))
        self.expect("rests", ([], set()), (self.attention(flow.INVALID_HOLD), self.stalled()))
        self.w.issues[(TLE, 1)]["milestone"]["state"] = "closed"
        self.expect("the hold is released and reported",
                    [(name(TLE, 1), "technical-lead")], self.attention(flow.INVALID_HOLD))
        self.go()
        self.expect("and the package moved", "Post-deployment",
                    self.w.field(TLE, 1, "Project State"))
        self.expect("and its Turn rewritten", "Claude", self.w.field(TLE, 1, "Turn"))

    def test_release_check_package_holds_while_no_next_release_milestone_is_open(self):
        """S17, D5.12: no next release raised or open: the hold stays valid."""
        self.proj(1, "Post-deployment", D(days=90), turn="Hold", labels=("Release Check",),
                  milestone=("1.0.0", "closed"))
        self.w.add_milestone(TLE, "1.0.0", "closed", D(days=100))
        self.expect("valid", [], self.attention(flow.INVALID_HOLD))
        self.expect("not stalled", set(), self.stalled())

    def test_ticket_waiting_on_sender_holds_and_stalls_under_the_owner_after_seven_days(self):
        """S13, S17, M11: at 6 days the hold rests; at 8 it stalls under the owner,
        with the hold kept, not rewritten."""
        self.ticket(1, "Waiting on sender", D(days=6), turn="Hold")
        self.ticket(2, "Waiting on sender", D(days=8), turn="Hold")
        self.expect("only the second", {name(SD, 2)}, self.stalled())
        self.expect("under the owner", "owner", self.verdict(SD, 2).role)
        self.expect("hold kept", [], self.turns_written_by_go())
        self.expect("not an invalid hold", [], self.attention(flow.INVALID_HOLD))

    def test_on_hold_requirement_derives_turn_hold(self):
        """S18, O4, O18: On Hold with a linked open issue is Hold; with none named, reported."""
        self.req(1, "On Hold", D(days=30), blocked_by=((TLE, 99, "open"),))
        self.req(2, "On Hold", D(days=30))
        self.go()
        self.expect("Hold for the linked one", "Hold", self.w.field(TLE, 1, "Turn"))
        self.expect("reported for the other", [(name(TLE, 2), "design-authority")],
                    self.attention(flow.INVALID_HOLD))

    def test_on_hold_is_bound_by_its_review_date(self):
        """S18, Requirement table: past the review date it is stalled for its role;
        on or before it, not; with no date, it rests while its reason holds."""
        text = "## Dependencies and related work\n\nWaiting on the vendor. Review date: {}\n"
        self.req(1, "On Hold", D(days=60), body=text.format("2026-11-14"))
        self.req(2, "On Hold", D(days=60), body=text.format("2026-11-15"))
        self.req(3, "On Hold", D(days=60), body=text.format("2026-11-16"))
        self.req(4, "On Hold", D(days=60), blocked_by=((TLE, 99, "open"),))
        self.req(5, "On Hold", D(days=60), body=text.format("2026-11-14"),
                 blocked_by=((TLE, 99, "open"),))
        self.expect("past its date, even with a linked issue open",
                    {name(TLE, 1), name(TLE, 5)}, self.stalled())
        self.expect("for its role", "design-authority", self.verdict(TLE, 1).role)

    def test_requirement_waiting_on_a_decision_rests_while_the_decision_is_listed_for_the_owner(self):
        """S19, M15: Scope with Turn Hold on an open Decision rests, the Decision
        is the owner's; once it is closed the requirement is its role's."""
        self.decision(50, "Asked", D(days=1), turn="Owner")
        self.hold(1, body="## Dependencies and related work\n\nWaits on #50\n")
        sweep = self.survey()
        self.expect("rests", ([], False),
                    (self.attention(flow.INVALID_HOLD), self.verdict(TLE, 1).stalled))
        self.expect("the Decision on the owner's list", True,
                    name(TLE, 50) in [v.name for v, _ in flow.role_list(sweep, "owner")])
        del self.w.issues[(TLE, 50)]
        self.expect("released, for its role", [(name(TLE, 1), "design-authority")],
                    self.attention(flow.INVALID_HOLD))

    def test_pull_request_awaiting_review_is_the_owners_and_carries_no_issue_field(self):
        """S11, M7: the owner's, derived from the review request; no field is written to it."""
        self.w.add_pull(TLE, 60, reviewers=1)
        v = self.verdict(TLE, 60)
        self.expect("the owner's", ("owner", "Awaiting review"), (v.role, v.state))
        self.go()
        self.expect("no field written", [], [w for w in self.fields_written() if w[1] == 60])

    def test_infrastructure_pull_request_mover_is_derived_from_rest(self):
        """S12, I5: an infrastructure pull request, with no PR State on the board:
        the owner's with a review requested, its author's as a draft."""
        self.w.add_pull(INF, 61, reviewers=1)
        self.w.add_pull(INF, 62, draft=True)
        self.expect("review requested: the owner", "owner", self.verdict(INF, 61).role)
        self.expect("a draft: its author", "author", self.verdict(INF, 62).role)
        self.go()
        self.expect("and it needed no GraphQL", 0, self.w.graphql_calls)

    def test_owner_set_turn_with_an_approval_comment_is_kept(self):
        """S15, M10: a thread-set Owner with its approval comment is kept within the
        bound and stalls under the owner past it; once he has commented, it is the
        thread's again."""
        scope = "Scope, Options and Dependencies"
        self.req(1, scope, D(days=2), turn="Owner", comments=(("a-thread", "Please approve X", D(days=1)),))
        self.req(2, scope, D(days=9), turn="Owner", comments=(("a-thread", "Please approve X", D(days=8)),))
        self.req(3, scope, D(days=2), turn="Owner")
        self.req(4, scope, D(days=2), turn="Owner",
                 comments=(("a-thread", "Please approve X", D(days=1)),
                           (OWNER_LOGIN, "Approved", D(hours=1))))
        self.expect("kept, and the rest rewritten",
                    [(TLE, 3, "Claude"), (TLE, 4, "Claude")], self.turns_written_by_go())
        self.expect("past the bound under the owner", {name(TLE, 2)}, self.stalled())
        self.expect("the owner holds it", "owner", self.verdict(TLE, 2).role)


    def test_a_turn_the_sweep_wrote_is_its_to_rewrite_but_a_threads_is_kept(self):
        """S15, M10: joint triage. Triage with no workstream is the owner's and the
        sweep writes Owner; he comments, Claude comments and moves it to Scope with
        a workstream: the Owner is the sweep's own, so it is rewritten. A thread's
        Owner set after the sweep wrote Claude is kept while its approval is asked."""
        scope = "Scope, Options and Dependencies"
        self.req(1, "Triage", D(hours=2), ws=None,
                 comments=(("a-thread", "Joint triage: what is this?", D(hours=1)),))
        self.expect("owner's at triage", [(TLE, 1, "Owner")], self.turns_written_by_go())
        issue = self.w.issues[(TLE, 1)]
        issue["_comments"] += [
            {"user": {"login": OWNER_LOGIN}, "body": "Tooling", "created_at": ago(minutes=30)},
            {"user": {"login": "a-thread"}, "body": "Scoped.", "created_at": ago(minutes=10)}]
        issue["_fields"].update({"Requirement State": scope, "Workstream": "Tooling"})
        self.w.log.clear()
        self.expect("rewritten to the derived value", [(TLE, 1, "Claude")],
                    self.turns_written_by_go())
        # A thread sets Owner over the sweep's Claude, and asks.
        issue["_fields"]["Turn"] = "Owner"
        issue["_comments"].append({"user": {"login": "a-thread"}, "body": "Please approve X",
                                   "created_at": ago(minutes=5)})
        self.w.log.clear()
        self.expect("kept", [], self.turns_written_by_go())

    def test_a_dry_run_reads_the_ledger_and_writes_nothing(self):
        """S39: the ledger ages an item the field events say is new; a dry run uses
        it, and writes neither fields nor the pinned body."""
        self.req(1, "Scope, Options and Dependencies", D(days=1), turn="Claude")
        self.go()
        self.age_in_ledger(TLE, 1, days=9)
        before = self.w.pinned_body()
        self.w.log.clear()
        run = self.go(dry_run=True)
        self.expect("stalled by the ledger's age", {name(TLE, 1)}, self.stalled())
        self.expect("nothing written", ([], before), (self.w.log, self.w.pinned_body()))
        self.expect("said what it would do", True, "would rewrite" in run.out)

    def test_the_sweeps_own_turn_write_does_not_restart_an_items_clock(self):
        """S22, S-G11: a bootstrap run ages the item from its field event, judged
        before it writes; the next days' runs go on from there."""
        self.req(1, "Scope, Options and Dependencies", D(days=6), turn=None)
        self.expect("first sighting: today's rule", D(days=6), self.verdict(TLE, 1).age)
        self.expect("it writes Turn", [(TLE, 1, "Claude")], self.turns_written_by_go())
        later = NOW + D(days=2)
        v = self.verdict(TLE, 1, now=later)
        self.expect("eight days old, not two", (D(days=8), True), (v.age, v.stalled))

    def test_a_state_that_changed_since_the_ledger_is_aged_by_its_field_event(self):
        """S22: the ledger's word holds only for the state it saw."""
        self.req(1, "Scope, Options and Dependencies", D(days=20), turn="Claude")
        self.go()
        issue = self.w.issues[(TLE, 1)]
        issue["_fields"]["Requirement State"] = "Candidate Project 1"
        issue["_events"].append({"event": "issue_field_changed", "created_at": ago(days=1)})
        self.expect("a day old", D(days=1), self.verdict(TLE, 1).age)


# --------------------------------------------------------------------------
# claims and recovery
# --------------------------------------------------------------------------


class Claims(Flow):

    def claimed(self, n, since, claim):
        self.w.add_issue(TLE, n, "Project", since=since,
                         fields={"Project State": "Development", "Workstream": "Tooling",
                                 "Turn": "Claude", "Route": "Production Release",
                                 "Claimed by": claim})

    def test_live_claim_within_bound_is_not_offered(self):
        """S20, O7: a claim within the bound is shown and the item is quiet."""
        self.claimed(1, D(days=2), f"technical-lead {THREAD}")
        v = self.verdict(TLE, 1)
        self.expect("not stalled, not offered", (False, False), (v.stalled, v.offered))
        self.expect("claim shown", THREAD, v.claim.thread)
        self.expect("on the list", True,
                    f"claimed by technical-lead {THREAD}" in flow.render_role(self.survey(), "technical-lead"))

    def test_stale_claim_is_offered_to_the_roles_current_thread(self):
        """S20, O8, S-G9: past the bound the claim is kept, unchanged, and offered."""
        self.claimed(1, D(days=9), f"technical-lead {THREAD}")
        run = self.go()
        self.expect("offered", True, "offered to the role's current thread" in run.out)
        self.expect("kept", f"technical-lead {THREAD}", self.w.field(TLE, 1, "Claimed by"))
        self.expect("never written", [], [w for w in self.fields_written() if w[2] == "Claimed by"])

    def test_role_only_claim_names_the_role_alone(self):
        """S20, O6: a claim naming a role and no thread; and a malformed one is
        reported and read as none (S-G15)."""
        self.claimed(1, D(days=9), "technical-lead")
        self.claimed(2, D(days=9), "somebody-else")
        v = self.verdict(TLE, 1)
        self.expect("role alone", ("technical-lead", None), (v.claim.role, v.claim.thread))
        self.expect("stalled", True, v.stalled)
        self.expect("malformed is no claim", None, self.verdict(TLE, 2).claim)
        self.expect("and is reported", [(name(TLE, 2), "technical-lead")],
                    [(v.name, a.role) for v, a in self.survey().attention
                     if a.kind == flow.MALFORMED_CLAIM])

    def test_black_start_lists_every_past_bound_item_by_role_and_nothing_else(self):
        """S21, R8: every type in every repository, nothing moved for 30 days, and
        three items within bound holding live claims. One run lists the past-bound
        ones by role."""
        old = D(days=30)
        self.req(1, "Scope, Options and Dependencies", old, repo=TLE)
        self.req(2, "Ready for Project", old, repo=DP)
        self.proj(3, "Development", old, repo=INF)
        self.decision(4, "Asked", old, repo=PRG)
        self.ticket(5, "New", old, repo=SD)
        self.w.add_pull(DP, 6, reviewers=1, since=old)
        self.claimed(7, D(days=2), f"technical-lead {THREAD}")
        self.w.add_issue(DP, 8, "Project", since=D(days=1),
                         fields={"Project State": "Scope", "Workstream": "Tooling",
                                 "Claimed by": f"design-authority {THREAD}"})
        self.w.add_issue(SD, 9, "Ticket", since=D(days=1),
                         fields={"Ticket State": "New", "Claimed by": "owner"})
        sweep = self.survey()
        got = {v.name: v.role for v in sweep.stalled}
        self.expect("by role", {name(TLE, 1): "design-authority", name(INF, 3): "technical-lead",
                                name(PRG, 4): "owner", name(SD, 5): "owner", name(DP, 6): "owner"},
                    got)

    def test_role_without_a_permanent_thread_is_listed_by_role(self):
        """S37, D12.3: an unclaimed stalled item is listed under its role (and
        workstream), naming no thread."""
        self.req(1, "Scope, Options and Dependencies", D(days=30), ws="Process Definition")
        self.req(2, "Candidate Project 1", D(days=30), ws="Tooling")
        out = self.go().out
        self.expect("grouped by role and workstream", True,
                    "### design-authority (Process Definition)" in out
                    and "### demand-manager (Tooling)" in out)
        self.expect("naming no thread", False, "claude.ai" in out)


# --------------------------------------------------------------------------
# missed events
# --------------------------------------------------------------------------


class MissedEvents(Flow):

    def state_writes(self):
        return [(r, n, v) for r, n, f, v in self.fields_written() if f == "Project State"]

    def merged_reports(self):
        return [(v.name, a.role, a.detail) for v, a in self.survey().attention
                if a.kind == flow.MERGED]

    def test_merged_refs_to_a_production_release_package_is_reported_not_moved(self):
        """S24, O16: a merged pull request's `Refs #N` naming a Production Release
        package at Development is listed under needs a look, for the package's
        holder; nothing is written to it."""
        self.proj(1, "Development", D(days=2), turn="Claude", route="Production Release")
        self.w.add_merged(TLE, 300, body="Refs #1")
        run = self.go()
        self.expect("not moved", [], self.state_writes())
        self.expect("reported, with the way out",
                    [(name(TLE, 1), "technical-lead",
                      "merged PR #300 names it; move it if that merge delivered it")],
                    self.merged_reports())
        self.expect("and in the list", True, "merged, not moved" in run.out)

    def test_merged_refs_to_a_tooling_package_is_reported_by_the_merge_modules_rule(self):
        """S24: the route-to-phase rule is `merge.next_phase`'s: a tooling-route
        package at User testing is reported too, and one that no merge completes
        (an Other route) is not."""
        self.proj(1, "User testing", D(days=2), turn="Claude", route="Docs and Programme Tooling")
        self.proj(2, "Development", D(days=2), turn="Claude", route="Other")
        self.w.add_merged(TLE, 300, body="Refs #1, Refs #2")
        self.go()
        self.expect("not moved", [], self.state_writes())
        self.expect("only the first", [name(TLE, 1)], [n for n, _, _ in self.merged_reports()])

    def test_several_partial_merges_are_one_finding_naming_them_all(self):
        """S24: a package delivered by several merges, none of which finished it:
        reported once with every pull request, never moved by the first."""
        self.proj(1, "Development", D(days=2), turn="Claude")
        self.w.add_merged(TLE, 300, body="Refs #1", age=D(days=5))
        self.w.add_merged(TLE, 301, body="Refs #1", age=D(days=2))
        self.go()
        self.expect("not moved", [], self.state_writes())
        self.expect("one finding", 1, len(self.merged_reports()))
        detail = self.merged_reports()[0][2]
        self.expect("naming both", True, "#300" in detail and "#301" in detail
                    and "merged PRs" in detail)

    def test_a_merge_counts_by_when_it_merged_not_when_it_was_touched(self):
        """S24: merged 40 days ago and commented on yesterday is outside the 30-day
        lookback; merged 29 days ago is inside."""
        self.proj(1, "Development", D(days=2), turn="Claude")
        self.proj(2, "Development", D(days=2), turn="Claude")
        old = self.w.add_merged(TLE, 300, body="Refs #1", age=D(days=40))
        old["updated_at"] = ago(days=1)
        self.w.add_merged(TLE, 301, body="Refs #2", age=D(days=29))
        self.expect("only the recent merge", [name(TLE, 2)], [n for n, _, _ in self.merged_reports()])

    def test_needs_a_look_alone_exits_one(self):
        """S38, S-G21: nothing stalled, one item to look at: exit 1."""
        self.proj(1, "Development", D(hours=1), turn="Claude")
        self.w.add_merged(TLE, 300, body="Refs #1")
        run = self.go()
        self.expect("nothing stalled", set(), {v.name for v in self.survey().stalled})
        self.expect("exit 1", 1, run.code)
        self.expect("and listed", True, "## Needs a look" in run.out)

    def test_refs_to_a_parent_moves_nothing(self):
        """S24, O5: `Refs` to a parent only; the package stays."""
        self.proj(1, "Design and Test Approach", D(days=2), turn="Claude", route=None,
                  sub=((2, "Project", "open"),))
        self.proj(2, "Development", D(days=2), turn="Claude", parent=1)
        self.w.add_merged(TLE, 300, body="Refs #1")
        self.go()
        self.expect("nothing moved", [], self.state_writes())

    def test_unmerged_pull_request_moves_nothing(self):
        """S24, O5: an open pull request, and a closed one that never merged;
        and a package already moved."""
        self.proj(1, "Development", D(days=2), turn="Claude")
        self.w.add_pull(TLE, 301, body="Refs #1")
        self.proj(2, "Development", D(days=2), turn="Claude")
        closed = self.w.add_merged(TLE, 302, body="Refs #2")
        closed["merged_at"] = None
        self.proj(3, "Post-deployment", D(days=2), turn="Claude")
        self.w.add_merged(TLE, 303, body="Refs #3")
        self.go()
        self.expect("nothing moved", [], self.state_writes())

    def test_a_moved_items_age_starts_at_the_move(self):
        """S41: a package moved because its release closed is aged from the move
        and keeps that start on the next day's sweep."""
        self.proj(1, "Deployment", D(days=3), turn="Hold", milestone=("1.0.0", "closed"))
        self.expect("age zero at the move", D(0), self.verdict(TLE, 1).age)
        self.go()
        self.expect("recorded", NOW, flow.parse_ledger(self.w.pinned_body())[name(TLE, 1)].since)
        self.expect("a day on", D(days=1), self.verdict(TLE, 1, now=NOW + D(days=1)).age)

    def test_closed_release_milestone_moves_its_open_work_packages(self):
        """S41, S-G13: a package at Deployment in a closed release milestone goes
        to Post-deployment; one already there, and one in an open milestone, stay."""
        self.proj(1, "Deployment", D(days=3), turn="Hold", milestone=("1.0.0", "closed"))
        self.proj(2, "Post-deployment", D(days=3), turn="Claude", milestone=("1.0.0", "closed"))
        self.proj(3, "Deployment", D(days=3), turn="Hold", milestone=("1.1.0", "open"))
        self.go()
        self.expect("only the first", [(TLE, 1, "Post-deployment")], self.state_writes())


# --------------------------------------------------------------------------
# failure and reach
# --------------------------------------------------------------------------


class Failure(Flow):

    def test_read_failure_keeps_earlier_writes_and_names_the_item_and_call(self):
        """S25, O10: a listing that fails stops the run, naming the call, before
        any write; a read an item needs that fails leaves every other write
        standing. A rerun with the source healthy completes."""
        self.w.add_issue(DP, 1, None)
        self.w.fail_reads["fakeorg/infrastructure/issues?state=open"] = "HTTP 500"
        run = self.go()
        self.expect("exit 2", 2, run.code)
        self.expect("names the call", True, "fakeorg/infrastructure/issues" in run.err)
        self.expect("no write", [], self.w.log)
        self.w.fail_reads.clear()
        self.proj(7, "Post-deployment", D(days=3), turn="Claude", repo=TLE, labels=("Release Check",),
                  milestone=("1.0.0", "closed"))
        self.w.fail_reads["fakeorg/tile-lite-elite/milestones"] = "HTTP 500"
        run = self.go()
        self.expect("exit 2", 2, run.code)
        self.expect("names the item and the call", True,
                    "fakeorg/tile-lite-elite#7" in run.err and "milestones" in run.err)
        self.expect("the other write stands", "Requirement", self.w.issues[(DP, 1)]["type"]["name"])
        self.w.fail_reads.clear()
        self.w.add_milestone(TLE, "1.0.0", "closed", D(days=100))
        run = self.go()
        self.expect("the rerun completes", True, run.code in (0, 1))
        self.expect("and the pinned issue shows the new time", True,
                    "Last complete run: 2026-11-15T12:00:00Z" in self.w.pinned_body())

    def test_refused_write_exits_non_zero_and_is_not_reported_as_fixed(self):
        """S26, O10: a Turn write refused with 403 in one repository: exit 2, the
        item not reported as written, the others written; then permitted."""
        self.proj(1, "Development", D(hours=1), repo=DP)
        self.proj(2, "Development", D(hours=1), repo=TLE)
        self.w.refuse_writes.add("fakeorg/dark-portal/issues/1")
        run = self.go()
        self.expect("exit 2", 2, run.code)
        self.expect("names the item", True, "fakeorg/dark-portal#1" in run.err)
        self.expect("not reported as written", False, "wrote fakeorg/dark-portal#1" in run.out)
        self.expect("the other is", "Claude", self.w.field(TLE, 2, "Turn"))
        self.w.refuse_writes.clear()
        self.expect("then permitted", 0, self.go().code)
        self.expect("and written", "Claude", self.w.field(DP, 1, "Turn"))

    def test_hung_call_is_cut_and_treated_as_a_failure(self):
        """S27, I10, S-G20: a hanging call is cut at the timeout setting and the
        run fails."""
        self.w.add_issue(DP, 1, None)
        self.w.hang["fakeorg/dark-portal/issues"] = 1000
        with mock.patch.object(sources, "_flow_setting",
                               lambda name: 5 if name == "rest_timeout_seconds" else 8):
            run = self.go()
        self.expect("exit 2", 2, run.code)
        self.expect("said so", True, "did not answer" in run.err)
        self.expect("the call carried the setting", True, 5 in self.w.timeouts)
        self.expect("and no other", True, set(self.w.timeouts) == {5})

    def test_failed_run_leaves_the_last_complete_run_time_unchanged(self):
        """S25, O10: the pinned issue keeps the previous complete run's time."""
        self.quiet_world_one()
        self.go(now=NOW - D(days=1))
        before = self.w.pinned_body()
        self.w.fail_reads["fakeorg/infrastructure/issues?state=open"] = "HTTP 500"
        self.go()
        self.expect("unchanged", before, self.w.pinned_body())
        self.expect("it is the earlier run's", True, "2026-11-14T12:00:00Z" in before)

    def quiet_world_one(self):
        self.req(1, "Scope, Options and Dependencies", D(hours=1), turn="Claude")

    def test_unreadable_field_is_not_visible_and_never_defaulted(self):
        """S28, O11: one issue's fields cannot be read; the rest are judged."""
        self.w.add_issue(TLE, 1, "Project", since=D(days=30), hide_fields=True)
        self.proj(2, "Development", D(hours=1))
        run = self.go()
        self.expect("reported not visible", True, "not visible" in run.out)
        self.expect("nothing written to it", [], [w for w in self.fields_written() if w[1] == 1])
        self.expect("not judged stalled", False, name(TLE, 1) in {v.name for v in self.survey().stalled})
        self.expect("the rest normal", "Claude", self.w.field(TLE, 2, "Turn"))

    def test_whole_run_succeeds_with_graphql_refused(self):
        """S29, O15: GraphQL is refused throughout; the sweep, the owner's list and
        a role list all complete with the answer the world gives."""
        self.req(1, "Scope, Options and Dependencies", D(days=30), turn="Claude")
        self.decision(2, "Asked", D(days=2), turn="Owner")
        run = self.go()
        self.expect("the sweep lists the stalled", True, name(TLE, 1) in self.w.pinned_body())
        self.expect("exit 1", 1, run.code)
        self.expect("the sweep made no GraphQL call", 0, self.w.graphql_calls)
        self.actions("--role", "design-authority")
        self.expect("nor did a role list", 0, self.w.graphql_calls)
        os.environ["BOARD_REPOSITORY"] = TLE
        owner = self.actions("--quick", "--no-colour")
        self.expect("the owner's list asks GraphQL, is refused, and reads REST", True,
                    self.w.graphql_calls > 0 and owner.code == 0)
        self.expect("and holds the Decision", True, "#2 issue 2" in owner.out)
        self.expect("the role list holds the requirement", True,
                    name(TLE, 1) in self.actions("--role", "design-authority").out)

    def test_missed_day_ends_in_the_same_state_as_a_single_run(self):
        """S30, I4: a world run on day 1 and day 3 ends as the same world run on
        day 3 alone: the same fields and the same stalled set."""
        def build():
            self.w = World()
            self.w.add_issue(DP, 1, None)
            self.req(2, "Scope, Options and Dependencies", D(days=30), turn="Claude")
            self.proj(3, "Development", D(days=1), turn="Claude")
            self.w.add_issue(SD, 4, "Ticket", since=D(days=1))

        def end(w):
            return {k: dict(v["_fields"]) for k, v in w.issues.items() if k != (PRG, 900)}

        build()
        self.go(now=NOW - D(days=2))
        self.go()
        two = (end(self.w), {v.name for v in self.survey().stalled})
        build()
        self.go()
        one = (end(self.w), {v.name for v in self.survey().stalled})
        self.expect("the same fields", one[0], two[0])
        self.expect("the same stalled set", one[1], two[1])

    def test_a_complete_run_says_it_rewrote_the_pinned_issue(self):
        """The output names the stalled-list write, as a dry run names the one
        it would make, so a reader of the output need not open the issue."""
        self.proj(2, "Development", D(hours=1))
        run = self.go()
        self.expect("said so", True, "rewrote " in run.out and flow.STALLED_LIST_TITLE in run.out)

    def test_a_run_whose_item_write_fails_does_not_say_it_rewrote_the_list(self):
        """A run that gets past the survey but has a write refused keeps the last
        complete run's list and rewrites only the ledger, so it never says rewrote."""
        self.proj(1, "Development", D(hours=1), repo=DP)
        self.w.refuse_writes.add("fakeorg/dark-portal/issues/1")
        run = self.go()
        self.expect("exit 2", 2, run.code)
        self.expect("the ledger was rewritten", True, len(self.w.body_writes()) == 1)
        self.expect("not said", False, "rewrote " in run.out)

    def test_a_run_whose_pinned_write_fails_does_not_say_it_rewrote_the_list(self):
        """The rewrite of the pinned issue itself is refused: exit 2, never rewrote."""
        self.proj(2, "Development", D(hours=1))
        self.w.refuse_writes.add("fakeorg/programme/issues/900")
        run = self.go()
        self.expect("exit 2", 2, run.code)
        self.expect("said it could not", True, "could not rewrite" in run.err)
        self.expect("not said", False, "rewrote " in run.out)

    def test_immediate_rerun_writes_only_the_pinned_issue(self):
        """S31, I8: a rerun with nothing changed writes one body and nothing else."""
        self.w.add_issue(DP, 1, None)
        self.proj(2, "Development", D(hours=1))
        self.go()
        self.w.log.clear()
        self.go()
        self.expect("one write", 1, len(self.w.log))
        self.expect("the body", True, self.w.body_writes() == self.w.log)


# --------------------------------------------------------------------------
# lists and the single source
# --------------------------------------------------------------------------


REQUIREMENT_OPTIONS = ["Triage", "Scope, Options and Dependencies", "On Hold", "Ready for Project",
                       "Candidate Project 1", "Candidate Project 2", "Candidate Project 3"]
PROJECT_OPTIONS = ["Scope", "Q3", "Q2", "Q1", "Design and Test Approach", "Development",
                   "User testing", "Deployment", "Post-deployment", "Project Closedown"]
DECISION_OPTIONS = ["Asked", "Feedback Provided", "Documented Ready for Sign-Off", "Decided",
                    "Actioned"]
PR_OPTIONS = ["Drafting", "Awaiting review", "Changes requested", "Approved"]
TICKET_OPTIONS = ["New", "In progress", "Waiting on sender", "Pending", "Resolved", "Refused"]


class Lists(Flow):

    def test_role_list_holds_exactly_its_items_oldest_first_with_age_and_bound(self):
        """S32, O12: a design authority's list, oldest first, with age and bound."""
        scope = "Scope, Options and Dependencies"
        self.req(1, scope, D(days=2), turn="Claude")
        self.req(2, scope, D(days=9), turn="Claude")
        self.req(3, scope, D(days=5), turn="Claude")
        self.req(4, "Ready for Project", D(days=30), turn="Claude")
        self.req(5, scope, D(days=8), ws="Process Definition", turn="Claude")
        run = self.actions("--role", "design-authority", "--workstream", "Tooling",
                           "--now", "2026-11-15T12:00:00Z")
        lines = [ln for ln in run.out.splitlines() if "issue " in ln]
        self.expect("oldest first, only its workstream's", [2, 3, 1],
                    [int(ln.split("#")[1].split()[0]) for ln in lines])
        self.expect("age and bound shown", True, "9.0 days against 7 days" in lines[0])

    def test_role_with_nothing_says_so(self):
        """S32, O12: a role with no items says so plainly."""
        run = self.actions("--role", "test-manager")
        self.expect("exit 0", 0, run.code)
        self.expect("says so", True, "Nothing is waiting on the test-manager." in run.out)

    def test_unknown_role_is_refused(self):
        """S32, O19: an unknown role is refused naming it; a known one lists."""
        run = self.actions("--role", "janitor")
        self.expect("refused", 2, run.code)
        self.expect("naming it", True, "janitor" in run.err)
        self.expect("then a known role lists", 0, self.actions("--role", "demand-manager").code)

    def test_every_role_of_the_roles_document_is_accepted_and_author_is_no_role(self):
        """docs/1.7's nine roles are lower-case hyphenated slugs the list accepts,
        even where the flow table gives one nothing; `author` lists, but is no role."""
        self.expect("the nine", ("owner", "design-authority", "technical-lead",
                                 "demand-manager", "release-manager",
                                 "environments-manager", "test-manager", "librarian",
                                 "security"), ROLES)
        for role in ("environments-manager", "librarian", "security"):
            run = self.actions("--role", role)
            self.expect(f"{role} accepted", 0, run.code)
            self.expect(f"{role} has nothing", True, f"Nothing is waiting on the {role}." in run.out)
        self.expect("author is not a role", False, "author" in ROLES)
        self.expect("but lists the pull requests a thread opened", 0,
                    self.actions("--role", "author").code)
        self.expect("coordinator is refused", 2, self.actions("--role", "coordinator").code)

    def test_owners_list_adds_turn_owner_items_and_keeps_its_five_sources(self):
        """S33, O13: the owner's list holds a Turn = Owner requirement, a Decision at
        Asked, a pull request awaiting review and a work package in User testing
        with an unticked owner box."""
        os.environ["BOARD_REPOSITORY"] = TLE
        self.req(1, "Scope, Options and Dependencies", D(days=2), turn="Owner")
        self.decision(2, "Asked", D(days=2), turn="Owner")
        self.w.add_pull(TLE, 3, reviewers=1)
        self.proj(4, "User testing", D(days=2), turn="Claude",
                  body="## Functional user tests — Preview\n\n- [ ] **owner** — try it\n")
        self.req(5, "Scope, Options and Dependencies", D(days=2), turn="Claude")
        out = self.actions("--quick", "--no-colour").out
        for n, what in ((1, "Turn = Owner"), (2, "decision"), (3, "pull request"), (4, "browser test")):
            self.expect(what, True, f"#{n} " in out)
        self.expect("not the thread's own", False, "#5 " in out)

    def test_every_open_item_has_exactly_one_holder_across_all_lists(self):
        """S34, O14: an item in each multi-actor state has one holder, and the other
        actors with a part see it on their own lists."""
        scope = "Triage"
        self.req(1, scope, D(hours=1), ws=None)
        self.proj(2, "Design and Test Approach", D(days=1), turn="Claude",
                  body="## Design\n\n- [ ] **owner** — choose an option\n")
        self.proj(3, "User testing", D(days=1), turn="Claude",
                  body="## Functional user tests — Preview\n\n- [ ] **owner** — try it\n")
        self.proj(4, "Deployment", D(days=1), turn="Hold", milestone=("1.0.0", "open"))
        self.proj(5, "Design and Test Approach", D(days=1), turn="Claude")
        sweep = self.survey()
        for v in sweep.verdicts:
            holders = [r for r in HOLDERS if any(x is v and what == v.owes
                                               for x, what in flow.role_list(sweep, r))]
            self.expect(f"{v.name} has one holder", [v.role], holders)

        def on(role, n):
            return n in [int(x.name.split("#")[1]) for x, _ in flow.role_list(sweep, role)]
        self.expect("joint triage: the owner's", True, on("owner", 1))
        self.expect("design: the test manager and the owner have a part", (True, True),
                    (on("test-manager", 2), on("owner", 2)))
        self.expect("design with no box of his: not on his list", False, on("owner", 5))
        self.expect("user testing: the owner's part, the lead holds", (True, True),
                    (on("owner", 3), on("technical-lead", 3)))
        self.expect("deployment: the release manager's part, the lead holds", (True, True),
                    (on("release-manager", 4), on("technical-lead", 4)))

    def test_stalled_set_matches_past_bound_items_on_the_role_lists(self):
        """S34, O14: the stalled set is the past-bound items on the role lists."""
        scope = "Scope, Options and Dependencies"
        self.req(1, scope, D(days=9), turn="Claude")
        self.req(2, scope, D(days=1), turn="Claude")
        self.proj(3, "Development", D(days=20), turn="Claude")
        self.decision(4, "Asked", D(days=10), turn="Owner")
        sweep = self.survey()
        listed = set()
        for role in HOLDERS:
            text = flow.render_role(sweep, role)
            listed |= {ln.split()[0] for ln in text.splitlines() if "STALLED" in ln}
        self.expect("the same set", {v.name for v in sweep.stalled}, listed)

    def test_flow_table_covers_every_option_of_every_state_field(self):
        """S35, I1: every option of the five state fields has a mover and a bound
        (or none). A table with a row removed fails."""
        options = {"Requirement": REQUIREMENT_OPTIONS, "Project": PROJECT_OPTIONS,
                   "Decision": DECISION_OPTIONS, "PullRequest": PR_OPTIONS,
                   "Ticket": TICKET_OPTIONS}
        for kind, states in options.items():
            for state in states:
                row = FLOW[kind].get(state)
                self.expect(f"{kind} {state} has a row", True, row is not None)
                if row:
                    self.expect(f"{kind} {state} has a mover", True, row.role in HOLDERS)
                    self.expect(f"{kind} {state} says what it owes", True, bool(row.owes))
                    self.expect(f"{kind} {state} has a Turn", True, row.turn in model.TURNS)
        self.expect("a closed Ticket has no holder", None, FLOW["Ticket"]["Closed"].role)

    def test_flow_table_bounds_are_a_day_for_triage_fourteen_for_post_deployment_seven_elsewhere_none_for_queues(self):
        """S36, M12: the bounds, as the owner set them."""
        bound = lambda kind, state: FLOW[kind][state].bound
        self.expect("triage", 1, bound("Requirement", "Triage"))
        self.expect("post-deployment", 14, bound("Project", "Post-deployment"))
        for kind, state in [("Requirement", "Scope, Options and Dependencies"),
                            ("Requirement", "Candidate Project 1"), ("Project", "Scope"),
                            ("Project", "Design and Test Approach"), ("Project", "Development"),
                            ("Project", "User testing"), ("Project", "Project Closedown"),
                            *[("Decision", s) for s in DECISION_OPTIONS],
                            *[("PullRequest", s) for s in PR_OPTIONS],
                            *[("Ticket", s) for s in TICKET_OPTIONS]]:
            self.expect(f"{state} seven", 7, bound(kind, state))
        for kind, state in [("Requirement", "Ready for Project"),
                            ("Requirement", "Candidate Project 2"),
                            ("Requirement", "Candidate Project 3"), ("Requirement", "On Hold"),
                            ("Project", "Q3"), ("Project", "Q2"), ("Project", "Q1"),
                            ("Project", "Deployment")]:
            self.expect(f"{state} none", None, bound(kind, state))

    def test_each_multi_actor_state_has_one_holder_and_the_others_parts_on_their_lists(self):
        """S34, G1: one holder per state in the table; the other actors are parts."""
        design = FLOW["Project"]["Design and Test Approach"]
        self.expect("design", ("design-authority", {"test-manager", "owner"}),
                    (design.role, {r for r, _ in design.parts}))
        testing = FLOW["Project"]["User testing"]
        self.expect("testing", ("technical-lead", {"owner"}),
                    (testing.role, {r for r, _ in testing.parts}))
        deployment = FLOW["Project"]["Deployment"]
        self.expect("deployment", ("technical-lead", {"release-manager"}),
                    (deployment.role, {r for r, _ in deployment.parts}))

    def test_exit_status_is_0_clean_1_stalled_2_failed(self):
        """S38, S-G21: a quiet world exits 0, a stalled one 1, a failed read 2 and
        never 1."""
        self.quiet_world()
        self.expect("clean", 0, self.go().code)
        self.req(9, "Scope, Options and Dependencies", D(days=30), turn="Claude")
        self.expect("stalled", 1, self.go().code)
        self.w.fail_reads["fakeorg/service-desk/issues?state=open"] = "HTTP 500"
        self.expect("failed", 2, self.go().code)
        self.w.fail_reads.clear()
        self.expect("healthy again", 1, self.go().code)

    def quiet_world(self):
        self.req(1, "Scope, Options and Dependencies", D(days=1), turn="Claude")
        self.proj(2, "Development", D(days=1), turn="Claude")

    def test_dry_run_writes_nothing_and_prints_each_planned_write(self):
        """S39, O21, S-G22: a world needing type, state and Turn writes: a dry run
        prints them and writes nothing; the real run writes them."""
        self.w.add_issue(DP, 1, None)
        self.proj(2, "Development", D(hours=1))
        run = self.go(dry_run=True)
        self.expect("nothing written", [], self.w.log)
        for planned in ("would write fakeorg/dark-portal#1 Type = Requirement",
                        "would write fakeorg/dark-portal#1 Requirement State = Triage",
                        "would write fakeorg/dark-portal#1 Turn = Owner",
                        "would write fakeorg/tile-lite-elite#2 Turn = Claude"):
            self.expect(planned, True, planned in run.out)
        self.go()
        self.expect("the real run writes", "Claude", self.w.field(TLE, 2, "Turn"))
        self.expect("and the pinned body", True, "Last complete run" in self.w.pinned_body())

    def test_missing_pinned_issue_is_refused_and_named(self):
        """S40, O22, S-G18: no pinned issue: refused before any write, naming it;
        once it exists the run succeeds."""
        del self.w.issues[(PRG, 900)]
        self.w.add_issue(DP, 1, None)
        run = self.go()
        self.expect("exit 2", 2, run.code)
        self.expect("names it", True, flow.STALLED_LIST_TITLE in run.err)
        self.expect("no write", [], self.w.log)
        self.w.add_issue(PRG, 901, "Requirement", title=flow.STALLED_LIST_TITLE,
                         fields={"Requirement State": "Triage"})
        self.expect("then it runs", True, self.go().code in (0, 1))
        self.expect("and writes the body", True, "Last complete run" in self.w.issues[(PRG, 901)]["body"])

    def test_pull_request_claim_is_read_from_its_attribution_line(self):
        """S42, S-G16: a pull request's claim is the project thread its body links."""
        self.w.add_pull(TLE, 1, body=f"Refs #5\n\n🤖 Generated with Claude Code\n\n{THREAD}\n",
                        reviewers=1)
        self.w.add_pull(TLE, 2, body="Refs #5", reviewers=1)
        self.expect("the claim", f"author {THREAD}", str(self.verdict(TLE, 1).claim))
        self.expect("none without the line", None, self.verdict(TLE, 2).claim)
        self.expect("but listed by its PR State mover", "owner", self.verdict(TLE, 2).role)

    def test_owner_sees_an_item_once_however_many_sources_name_it(self):
        """S43, S-G19: a Decision at Asked that also carries Turn = Owner is listed once."""
        os.environ["BOARD_REPOSITORY"] = TLE
        self.decision(2, "Asked", D(days=2), turn="Owner")
        out = self.actions("--quick", "--no-colour").out
        self.expect("once", 1, out.count("#2 "))


class Survivors(Flow):

    def test_a_closed_tickets_turn_is_cleared_never_written_null(self):
        """A state with no holder takes the Turn off (a delete) only where it carries
        one, and no write carries a null."""
        self.ticket(1, "Closed", D(days=3), turn="Owner")
        self.ticket(2, "Closed", D(days=3))
        self.go()
        clears = [(m, p) for m, p, _ in self.w.log if m == "DELETE"]
        self.expect("one clear, of the first", [("DELETE", "repos/fakeorg/service-desk/issues/1/"
                                                  "issue-field-values/49935304")], clears)
        self.expect("no null written", True,
                    all(entry["value"] is not None
                        for _, _, payload in self.w.field_writes()
                        for entry in payload["issue_field_values"]))
        self.expect("the Turn is gone", None, self.w.field(SD, 1, "Turn"))
        self.w.log.clear()
        self.go()
        self.expect("a rerun clears nothing", [], [e for e in self.w.log if e[0] == "DELETE"])

    def test_a_ready_pull_request_that_owes_no_review_is_not_drafting(self):
        """A non-draft pull request with no reviewer asked and a `No review owed`
        Review heading is its author's to merge; a draft, and a ready one with no
        such heading, are still drafting."""
        owes_none = "## Review\n\nNo review owed: a record only.\n"
        self.w.add_pull(TLE, 201, body=owes_none)
        self.w.add_pull(TLE, 202, body=owes_none, draft=True)
        self.w.add_pull(TLE, 203, body="## Review\n\nPlease review.\n")
        states = {n: self.verdict(TLE, n).state for n in (201, 202, 203)}
        self.expect("states", {201: "No review owed", 202: "Drafting", 203: "Drafting"}, states)
        self.expect("its author's", "author", self.verdict(TLE, 201).role)

    def test_the_ledger_is_one_block_in_the_pinned_body(self):
        """The body ends with the ledger: each item's state, since and written Turn."""
        self.proj(1, "Development", D(days=2), turn=None)
        self.go()
        ledger = flow.parse_ledger(self.w.pinned_body())
        self.expect("the item", flow.Seen("Development", NOW - D(days=2), "Claude"),
                    ledger[name(TLE, 1)])
        self.expect("one block", 1, self.w.pinned_body().count("<!-- board-flow-ledger"))


class FieldWrites(Flow):
    """`sources.py` writes issue fields over REST (the handover)."""

    def test_rest_writes_and_clears_an_issue_field(self):
        """POST issue-field-values with the field id and the option's name; clearing
        is a DELETE of the field's value."""
        self.req(1, "Triage", D(hours=1))
        sources.write_issue_field(TLE, 1, 49935304, "Owner")
        self.expect("posted", [("POST", "repos/fakeorg/tile-lite-elite/issues/1/issue-field-values",
                                {"issue_field_values": [{"field_id": 49935304, "value": "Owner"}]})],
                    self.w.log)
        self.expect("set", "Owner", self.w.field(TLE, 1, "Turn"))
        sources.clear_issue_field(TLE, 1, 49935304)
        self.expect("cleared", None, self.w.field(TLE, 1, "Turn"))
        self.expect("by DELETE", "DELETE", self.w.log[-1][0])


class TheLedger(Flow):
    """The state-since ledger survives a failed run, a lost block and a large
    board (delphside/programme#182)."""

    SCOPE = "Scope, Options and Dependencies"
    LAST = "Last complete run: 2026-11-14T12:00:00Z\n\nNothing is stalled.\n"

    def kept_list(self):
        self.w.issues[(PRG, 900)]["body"] = self.LAST

    def test_a_failed_run_records_the_writes_made_and_the_next_run_rewrites_a_sweeps_turn(self):
        """A refused write mid-run: exit 2, the list stays the last complete run's,
        the ledger records the Turn that was written; then joint triage moves the
        item on and the next run rewrites the sweep's own Owner."""
        self.kept_list()
        self.proj(1, "Development", D(hours=1), repo=DP)
        self.req(1, "Triage", D(hours=2), ws=None,
                 comments=(("a-thread", "Joint triage: what is this?", D(hours=1)),))
        self.w.refuse_writes.add("fakeorg/dark-portal/issues/1")
        run = self.go()
        self.expect("exit 2", 2, run.code)
        body = self.w.pinned_body()
        ledger = flow.parse_ledger(body)
        self.expect("the write that was made", flow.Seen("Triage", NOW - D(hours=2), "Owner"),
                    ledger[name(TLE, 1)])
        self.expect("the write refused: no Turn recorded",
                    flow.Seen("Development", NOW - D(hours=1), None), ledger[name(DP, 1)])
        self.expect("the list is the last complete run's", True, body.startswith(self.LAST.strip()))
        issue = self.w.issues[(TLE, 1)]
        issue["_comments"] += [
            {"user": {"login": OWNER_LOGIN}, "body": "Tooling", "created_at": ago(minutes=30)},
            {"user": {"login": "a-thread"}, "body": "Scoped.", "created_at": ago(minutes=10)}]
        issue["_fields"].update({"Requirement State": self.SCOPE, "Workstream": "Tooling"})
        self.w.refuse_writes.clear()
        self.w.log.clear()
        self.expect("rewritten to the derived value",
                    [(DP, 1, "Claude"), (TLE, 1, "Claude")], self.turns_written_by_go())

    def test_a_refused_state_write_keeps_the_prior_entry(self):
        """The board still holds the old state, so the ledger does too."""
        self.req(1, None, D(days=3), turn="Owner")
        self.w.refuse_writes.add("fakeorg/tile-lite-elite/issues/1")
        self.expect("exit 2", 2, self.go().code)
        self.expect("no entry for what was not written", {}, flow.parse_ledger(self.w.pinned_body()))

    def test_an_item_with_no_ledger_entry_has_its_turn_judged_afresh(self):
        """Nothing says who set a Turn: a Hold is kept only while a Hold reason
        holds, an Owner only while an approval request is pending."""
        asked = (("a-thread", "Please approve X", D(hours=1)),)
        answered = asked + ((OWNER_LOGIN, "Approved", D(minutes=5)),)
        self.req(1, self.SCOPE, D(days=1), turn="Hold")
        self.req(2, self.SCOPE, D(days=1), turn="Hold", blocked_by=((TLE, 90, "open"),))
        self.req(3, self.SCOPE, D(days=1), turn="Owner", comments=answered)
        self.req(4, self.SCOPE, D(days=1), turn="Owner", comments=asked)
        self.req(5, self.SCOPE, D(days=1), turn="Owner")
        self.expect("the Hold with no reason is reported", [name(TLE, 1)],
                    [n for n, _ in self.attention("invalid hold")])
        self.expect("rewritten but the held and the asked",
                    [(TLE, 1, "Claude"), (TLE, 3, "Claude"), (TLE, 5, "Claude")],
                    self.turns_written_by_go())

    def test_a_pinned_body_without_a_readable_ledger_is_listed_but_not_on_the_first_run(self):
        """Only a body that an earlier run wrote can have lost its ledger."""
        self.req(1, self.SCOPE, D(hours=1), turn="Claude")
        self.expect("first run: none", [], self.attention("no readable ledger"))
        self.go()
        self.expect("a readable ledger: none", [], self.attention("no readable ledger"))
        self.kept_list()
        self.expect("previous run, no ledger", [(name(PRG, 900), "owner")],
                    self.attention("no readable ledger"))
        run = self.go()
        self.expect("exit 1", 1, run.code)
        self.expect("in the list", True, "no readable ledger" in self.w.pinned_body())
        self.expect("the run restored it", [], self.attention("no readable ledger"))
        self.w.issues[(PRG, 900)]["body"] = self.LAST + "<!-- board-flow-ledger\n{broken\n-->\n"
        self.expect("an unreadable block", [(name(PRG, 900), "owner")],
                    self.attention("no readable ledger"))

    def test_items_not_judged_this_run_keep_their_entry_while_open(self):
        """Not visible, an unknown state or a failed read: the entry stays; a
        closed item's goes."""
        for n in (1, 2, 3):
            self.req(n, self.SCOPE, D(days=4), turn="Claude")
        self.go()
        self.w.issues[(TLE, 1)]["_hide"] = True
        self.w.issues[(TLE, 2)]["_fields"]["Requirement State"] = "Not a state"
        del self.w.issues[(TLE, 3)]
        self.w.log.clear()
        self.go()
        ledger = flow.parse_ledger(self.w.pinned_body())
        self.expect("kept while open", {name(TLE, 1), name(TLE, 2)},
                    {n for n in ledger if n.startswith(TLE)})
        self.expect("with the age it had", NOW - D(days=4), ledger[name(TLE, 1)].since)

    def test_the_ledger_is_compact(self):
        self.proj(1, "Development", D(days=2), turn=None)
        self.go()
        block = self.w.pinned_body().split("<!-- board-flow-ledger\n")[1].split("\n-->")[0]
        self.expect("short keys, no padding",
                    '{"%s":{"d":"2026-11-13T12:00:00Z","s":"Development","t":"Claude"}}' % name(TLE, 1),
                    block)

    def test_a_body_near_githubs_limit_loses_the_tail_of_its_list_not_its_ledger(self):
        for n in range(1, 601):
            self.req(n, "Triage", D(days=3), ws=None, turn="Owner")
        run = self.go()
        body = self.w.pinned_body()
        self.expect("under the limit", True, len(body) <= flow.BODY_LIMIT)
        self.expect("every item in the ledger", 600, len(flow.parse_ledger(body)))
        self.expect("says what was left out", True, "Items left out" in body)
        self.expect("listed under needs a look", True,
                    "pinned body near GitHub's limit" in body)
        self.expect("exit 1", 1, run.code)

    def test_a_body_within_the_limit_is_not_cut(self):
        self.req(1, "Triage", D(days=3), ws=None)
        self.go()
        self.expect("whole", False, "left out" in self.w.pinned_body())
        self.expect("and unlisted", [], self.attention("pinned body near GitHub's limit"))

    def test_both_merged_readers_agree_on_what_merged_since(self):
        """`merged_since` and the REST fallback share one reading of the listing."""
        self.w.add_merged(TLE, 7, age=D(days=2))
        self.w.add_merged(TLE, 8, age=D(days=40))
        since = ago(days=10)
        self.expect("same pull requests", [7],
                    [p.number for p in sources.merged_since(TLE, since)])
        self.expect("by date too", [7], [p["number"] for p in
                    sources._merged_pulls(sources._Rest(), TLE, since[:10])])


class TheLastCompleteRun(Flow):
    """`board-practices.py` judges the daily sweep by the pinned issue's
    `Last complete run:` line, read once over REST."""

    def test_the_day_is_the_pinned_bodys(self):
        self.w.issues[(PRG, 900)]["body"] = "Last complete run: 2026-11-14T12:00:00Z\n\nNothing is stalled.\n"
        self.expect("the day of the line", "2026-11-14", flow.last_complete_run().isoformat())

    def test_a_missing_issue_is_unavailable(self):
        del self.w.issues[(PRG, 900)]
        with self.assertRaises(sources.Unavailable):
            flow.last_complete_run()

    def test_a_body_with_no_line_is_unavailable(self):
        self.w.issues[(PRG, 900)]["body"] = "Nothing is stalled.\n"
        with self.assertRaises(sources.Unavailable):
            flow.last_complete_run()

    def test_an_unreadable_github_is_unavailable(self):
        self.w.issues[(PRG, 900)]["body"] = "Last complete run: 2026-11-14T12:00:00Z\n"
        self.w.fail_reads["/issues?state=open"] = "HTTP 500"
        with self.assertRaises(sources.Unavailable):
            flow.last_complete_run()


if __name__ == "__main__":
    unittest.main()
