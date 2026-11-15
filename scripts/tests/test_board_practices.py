"""board-practices.py: which activities are overdue. #407 R3.

Against real files written to a temporary directory, not stubs: the parser
reads an actual markdown table and an actual CSV, so the test does too. Every
case was run for real against the live register and log while the script was
built, and is reproduced as an assertion.
"""

import json
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from board.tests.cases import Cases
from board.tests.cli import run

REGISTER = """\
| id | activity | frequency (days) | owner | produces | ITIL practice |
| --- | --- | --- | --- | --- | --- |
| `capacity-plan` | Produce and review the capacity plan | 30 | Claude produces, owner reviews | a report | Capacity and performance management |
| `benchmark-run` | Run the engine timing benchmark | 30 | Claude | a row | Capacity and performance management |
| `board-flow` | The daily sweep | 1 | Claude | the pinned issue | test only |
| `never-done` | Something with no log row | 7 | Claude | nothing | test only |
"""


class BoardPractices(Cases):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        d = Path(self._dir.name)
        (d / "register.md").write_text(REGISTER)
        old = (date.today() - timedelta(days=90)).isoformat()
        recent = (date.today() - timedelta(days=2)).isoformat()
        (d / "log.csv").write_text(f"date,activity,who,note\n{old},benchmark-run,Claude,old run\n"
                                   f"{recent},capacity-plan,Claude,recent report\n")
        self.register, self.log = d / "register.md", d / "log.csv"

    def practices(self, *args, register=None):
        env = {**os.environ, "REGISTER_OVERRIDE": str(register or self.register), "LOG_OVERRIDE": str(self.log),
               "PINNED_RUN_OVERRIDE": "unreadable"}
        return run("board/board-practices.py", *args, env=env)

    def test_the_overdue_case(self):
        out = self.practices().stdout.splitlines()
        self.expect("a 90-day-old benchmark run against a 30-day frequency is overdue", 1,
                    sum("benchmark-run" in l and "OVERDUE" in l for l in out))
        self.expect("a 2-day-old capacity plan against 30 days is not", 0,
                    sum("capacity-plan" in l and "OVERDUE" in l for l in out))
        self.expect("an activity with no log row reads never logged, not overdue", 1,
                    sum("never-done" in l and "never logged" in l for l in out))

    def flow_line(self, last_run, *args):
        """The practices with the pinned issue's last run standing at `last_run`."""
        env = {**os.environ, "REGISTER_OVERRIDE": str(self.register), "LOG_OVERRIDE": str(self.log),
               "PINNED_RUN_OVERRIDE": last_run}
        return run("board/board-practices.py", *args, env=env)

    def flow_status(self, last_run):
        out = self.flow_line(last_run).stdout.splitlines()
        return [l for l in out if "board-flow" in l]

    def test_the_daily_sweep_is_judged_from_the_pinned_issue_not_the_log(self):
        day = lambda n: (date.today() - timedelta(days=n)).isoformat()
        self.expect("a run two days ago against a daily cadence is overdue", True,
                    "OVERDUE by 1d" in self.flow_status(day(2))[0])
        self.expect("yesterday's run is not", True, "due in 0d" in self.flow_status(day(1))[0])
        self.expect("today's run is not", True, "due in 1d" in self.flow_status(day(0))[0])
        self.expect("and never reads as never logged", 0,
                    sum("never logged" in l for l in self.flow_status(day(0))))

    def test_an_unreadable_pinned_issue_is_said_and_is_not_overdue(self):
        line = self.flow_status("unreadable")
        self.expect("it says it could not read", True, "could not read" in line[0])
        data = json.loads(self.flow_line("unreadable", "--json").stdout)
        self.expect("and records why", True,
                    any(a["id"] == "board-flow" and a["unread"] for a in data))
        self.expect("but is not counted overdue: only benchmark-run and never-done are", True,
                    "2 overdue or never logged" in self.flow_line("unreadable").stdout)

    def test_the_exit_code_counts_the_daily_sweep_only_when_it_is_overdue(self):
        stale = (date.today() - timedelta(days=5)).isoformat()
        fresh = date.today().isoformat()
        self.expect("a stale sweep adds one to the count", True,
                    "3 overdue or never logged" in self.flow_line(stale).stdout)
        self.expect("a fresh one does not", True,
                    "2 overdue or never logged" in self.flow_line(fresh).stdout)

    def test_the_exit_status_follows_the_daily_sweep_alone(self):
        only = Path(self._dir.name) / "only.md"
        only.write_text("\n".join(l for l in REGISTER.splitlines()
                                  if "board-flow" in l or not l.startswith("| `")) + "\n")

        def status(last_run):
            env = {**os.environ, "REGISTER_OVERRIDE": str(only), "LOG_OVERRIDE": str(self.log),
                   "PINNED_RUN_OVERRIDE": last_run}
            return run("board/board-practices.py", "--exit-code", env=env).returncode

        self.expect("a stale sweep alone exits 1", 1,
                    status((date.today() - timedelta(days=5)).isoformat()))
        self.expect("a fresh one exits 0", 0, status(date.today().isoformat()))
        self.expect("an unreadable one exits 0: it is said, not counted", 0, status("unreadable"))

    def test_exit_code(self):
        self.expect("--exit-code is non-zero when something is overdue", 1, self.practices("--exit-code").returncode)
        self.expect("the plain form exits 0 even with an overdue activity: it reports", 0, self.practices().returncode)

    def test_missing_sources(self):
        # D46's 2, and 'cannot tell' rather than 'nothing outstanding'.
        result = self.practices(register=Path(self._dir.name) / "nope.md")
        self.expect("a missing register is 'could not judge' (D46)", 2, result.returncode)
        self.expect("and says cannot tell, not nothing outstanding", True,
                    "cannot read" in result.stdout + result.stderr)

    def test_json(self):
        data = json.loads(self.practices("--json").stdout)
        self.expect("the overdue entry's overdue_by is positive", True,
                    any((a["overdue_by"] or -1) > 0 for a in data))


if __name__ == "__main__":
    unittest.main()
