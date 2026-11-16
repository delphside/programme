"""The vocabulary of GitHub names the board tooling matches. delphside/tile-lite-elite#383 R19 to R22.

No network: the source is read from disk, or stubbed.

  one copy      no module but `vocabulary.py` types a field or option name
  the table     `FIELDS` holds the option constants
  the check     a name GitHub no longer has is reported; a live option the
                tooling does not read is not; a new live option does not fail it;
                an unreachable source is not a pass
  the data      each field and option is attributed to the modules that read it"""

import importlib.util
import io
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from .cases import Cases

from board import dataflow, usage, vocabcheck, vocabulary
from board.sources import Refused, Unavailable


def _live() -> tuple[dict, dict]:
    """The live fields as GitHub would answer, holding exactly the vocabulary."""
    issue = {f: tuple(o) for f, o in vocabulary.FIELDS.items()
             if f not in vocabulary.PROJECT_FIELDS and f not in vocabulary.TEXT_FIELDS}
    project = {f: tuple(vocabulary.FIELDS[f]) for f in vocabulary.PROJECT_FIELDS}
    return issue, project


class OneCopy(Cases):

    def test_no_module_types_a_name_the_vocabulary_holds(self):
        """one copy"""
        stray = usage.stray_literals()
        if stray:
            self.fail("a literal equals a vocabulary name; import the constant from "
                      "vocabulary.py: " + "; ".join(f"{f}:{n} {v!r}" for f, n, v in stray))

    def test_the_scan_finds_a_literal_where_one_is_typed(self):
        """the scan itself"""
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "typed.py"
            path.write_text('"""A docstring saying Post-deployment is skipped."""\n'
                            'x = "Post-deployment"\n')
            self.expect("the literal is named by file and line, the docstring is not",
                        [("typed.py", 2, "Post-deployment")], usage.stray_literals([path]))

    def test_every_option_constant_is_in_the_table(self):
        """the table"""
        held = {o for options in vocabulary.FIELDS.values() for o in options}
        for name in ("PROJ_SCOPE", "REQ_TRIAGE", "DEC_ASKED", "PR_APPROVED",
                     "TKT_PENDING", "TURN_HOLD", "RELEASE", "CHANGE_BUG"):
            self.expect(f"{name} is an option of some field", True,
                        getattr(vocabulary, name) in held)
        self.expect("a former Route name is read as its new one, so is not an option",
                    False, vocabulary.FORMER_APPLICATION_TOOLING in held)


class TheCheck(Cases):

    def test_a_renamed_option_is_reported(self):
        """a renamed option: #326's near-miss"""
        issue, project = _live()
        issue[vocabulary.DECISION_STATE] = tuple(
            "Documented Ready for sign-off" if o == vocabulary.DEC_SIGN_OFF else o
            for o in issue[vocabulary.DECISION_STATE])
        got = vocabcheck.check(issue, project)
        self.expect("exactly the renamed option, on its field",
                    [vocabcheck.Missing(vocabulary.DECISION_STATE, vocabulary.DEC_SIGN_OFF,
                                        "issue fields")], got)

    def test_a_missing_field_is_reported_once(self):
        """a missing field"""
        issue, project = _live()
        del issue[vocabulary.TURN]
        del project[vocabulary.PR_STATE]
        got = vocabcheck.check(issue, project)
        self.expect("each field, not each of its options",
                    [vocabcheck.Missing(vocabulary.TURN, None, "issue fields"),
                     vocabcheck.Missing(vocabulary.PR_STATE, None, "the Projects board")], got)

    def test_a_live_option_the_tooling_does_not_read_says_nothing(self):
        """#326 R2 and R3"""
        issue, project = _live()
        issue[vocabulary.PROJECT_STATE] += ("Parked",)
        issue["Sender email"] = ()
        project[vocabulary.PR_STATE] += ("Stale",)
        self.expect("an added option, and an added field, are not findings",
                    [], vocabcheck.check(issue, project))

    def test_the_report_names_the_finding_and_what_it_did_not_look_at(self):
        """the report"""
        found = [vocabcheck.Missing(vocabulary.TURN, vocabulary.TURN_HOLD, "issue fields")]
        text = vocabcheck.render(found, colour=False)
        self.expect("it names the option and its field", True,
                    "option 'Hold' is not on 'Turn'" in text)
        self.expect("it says what it did not check", True, "not checked: Claimed by" in text)
        self.expect("and says ok only when nothing is missing", True,
                    "ok every one exists" in vocabcheck.render([], colour=False))
        self.expect("not beside a finding", False, "ok every one exists" in text)


def _board_check():
    script = Path(__file__).resolve().parents[1] / "board-check.py"
    spec = importlib.util.spec_from_file_location("board_check_vocabulary", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TheCommand(Cases):

    def run_it(self, issue, project, exit_code=False):
        module = _board_check()
        out, err = io.StringIO(), io.StringIO()
        args = SimpleNamespace(no_colour=True, exit_code=exit_code)
        with mock.patch.object(module, "issue_field_names", issue), \
                mock.patch.object(module, "project_field_names", project), \
                redirect_stdout(out), redirect_stderr(err):
            status = module.vocabulary_main(args)
        return status, out.getvalue(), err.getvalue()

    def test_nothing_missing_exits_zero(self):
        """a pass"""
        issue, project = _live()
        status, out, _ = self.run_it(lambda: issue, lambda: project, exit_code=True)
        self.expect("exit 0", 0, status)
        self.expect("says ok", True, "ok every one exists" in out)

    def test_a_finding_exits_non_zero_only_when_asked(self):
        """a finding"""
        issue, project = _live()
        del issue[vocabulary.ROUTE]
        self.expect("exit 1 with --exit-code", 1,
                    self.run_it(lambda: issue, lambda: project, exit_code=True)[0])
        self.expect("exit 0 without: a check reports, a person decides", 0,
                    self.run_it(lambda: issue, lambda: project)[0])

    def test_an_unreachable_source_is_not_a_pass(self):
        """not checked"""
        _, project = _live()

        def refused():
            raise Refused("GitHub refused: GraphQL is not available")

        for name, issue, proj in (("issue fields refused", refused, lambda: project),
                                  ("the board refused", lambda: _live()[0], refused)):
            status, out, err = self.run_it(issue, proj, exit_code=True)
            self.expect(f"{name}: exit 2, as the report's other unreachable sources", 2, status)
            self.expect(f"{name}: says not checked", True, "not checked" in err)
            self.expect(f"{name}: never says ok", False, "ok" in out)


class TheDataFlow(Cases):

    def test_each_option_is_attributed_to_the_modules_that_read_it(self):
        """readers"""
        read = usage.readers()
        self.expect("the model reads Post-deployment through the flow table; "
                    "turn.py through the constant", True,
                    {"model.py", "turn.py"} <= read[(vocabulary.PROJECT_STATE,
                                                     vocabulary.PROJ_POST_DEPLOYMENT)])
        self.expect("Closed is two options: the ticket's is the model's, the pull "
                    "request's is sources.py's",
                    ({"model.py"}, {"sources.py"}),
                    (read[(vocabulary.TICKET_STATE, vocabulary.TKT_CLOSED)],
                     read[(vocabulary.PR_STATE, vocabulary.PR_CLOSED)]))

    def test_the_table_and_the_flowchart_name_a_field_its_options_and_readers(self):
        """output"""
        table, chart = dataflow.markdown(), dataflow.mermaid()
        self.expect("a table row for an option", True,
                    "| `Project State` | `Post-deployment` |" in table)
        self.expect("a flowchart", True, chart.startswith("flowchart LR"))
        self.expect("with an edge from a field to an option", True,
                    '["Project State"]' in chart and "F1 --- O" in chart)
        self.expect("and one to a module", True, "--> M_turn" in chart)
