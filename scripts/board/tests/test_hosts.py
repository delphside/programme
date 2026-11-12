"""Host currency: `hosts.py` and `board-hosts.py`.

From the rules the check implements, not the code: a host is current when no
reboot waits, the newest installed kernel runs and nothing is waiting to be
installed; a pair agrees when kernel and Docker match.

Sections:
  - reading a host's line: good and malformed
  - findings: each kind fires, and stays quiet when it should
  - the table and the JSON
  - the command: exit 0, 1, 2 and 70, with `ssh` stubbed by `SSH_COMMAND`
"""

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from board import hosts
from board.tests.cases import Cases
from board.tests.cli import run

CURRENT = "6.8.0-48\t6.8.0-48\t27.3.1\tno\t0\t0\t"


def reading(label="production", line=CURRENT):
    return hosts.parse(label, label, line)


class Parsing(Cases):
    def test_good_lines(self):
        r = hosts.parse("p", "ssh-p", "6.8.0-48\t6.8.0-50\t27.3.1\tyes\t12\t3\tlibc6,linux-image")
        self.expect("kernels", ("6.8.0-48", "6.8.0-50"), (r.running_kernel, r.newest_kernel))
        self.expect("docker", "27.3.1", r.docker)
        self.expect("reboot", True, r.reboot_pending)
        self.expect("counts are ints", (12, 3), (r.waiting, r.security))
        self.expect("packages", "libc6,linux-image", r.reboot_packages)
        self.expect("ssh name kept", "ssh-p", r.ssh)

    def test_empty_optional_fields(self):
        r = reading()
        self.expect("no packages", "", r.reboot_packages)
        r = hosts.parse("p", "p", "6.8.0-48\t\t\tno\t0\t0\t\n")
        self.expect("no newest kernel, no docker", ("", ""), (r.newest_kernel, r.docker))

    def test_malformed_lines(self):
        for name, line in (("too few fields", "6.8\t6.8\tno"),
                           ("too many fields", CURRENT + "\textra"),
                           ("empty", ""),
                           ("no running kernel", "\t\t\tno\t0\t0\t"),
                           ("reboot not yes or no", "6.8\t6.8\t1.1.1\tmaybe\t0\t0\t"),
                           ("count not a number", "6.8\t6.8\t1.1.1\tno\tmany\t0\t")):
            with self.subTest(name), self.assertRaises(ValueError):
                hosts.parse("p", "p", line)


class Findings(Cases):
    def kinds(self, readings, pairs=()):
        return [f.kind for f in hosts.findings(readings, list(pairs))]

    def test_per_host(self):
        self.expect("current host", [], self.kinds([reading()]))
        self.expect("reboot", ["reboot"],
                    self.kinds([reading(line="6.8\t6.8\t1.1.1\tyes\t0\t0\tlibc6")]))
        self.expect("newer kernel installed", ["kernel"],
                    self.kinds([reading(line="6.8.0-48\t6.8.0-50\t1.1.1\tno\t0\t0\t")]))
        self.expect("no kernel found is not a difference", [],
                    self.kinds([reading(line="6.8.0-48\t\t1.1.1\tno\t0\t0\t")]))
        self.expect("packages", ["packages"],
                    self.kinds([reading(line="6.8\t6.8\t1.1.1\tno\t5\t2\t")]))

    def test_messages(self):
        found = hosts.findings([reading(line="6.8\t6.8\t1.1.1\tyes\t5\t2\tlibc6")], [])
        text = " ".join(f.message for f in found)
        self.expect("count and security", True, "5 packages" in text and "2 of them security" in text)
        self.expect("reboot package named", True, "libc6" in text)

    def test_pairs(self):
        a, b = reading("production"), reading("rehearsal")
        pair = [("rehearsal", "production")]
        self.expect("equal facts", [], self.kinds([a, b], pair))
        kernel = reading("rehearsal", "6.9\t6.9\t27.3.1\tno\t0\t0\t")
        self.expect("kernels differ", ["pair-kernel"], self.kinds([a, kernel], pair))
        docker = reading("rehearsal", "6.8.0-48\t6.8.0-48\t28.0.0\tno\t0\t0\t")
        found = hosts.findings([a, docker], pair)
        self.expect("docker differs", ["pair-docker"], [f.kind for f in found])
        self.expect("says the lead may be deliberate", True,
                    "deliberately" in found[0].message and "cannot tell" in found[0].message)
        self.expect("pair label", "rehearsal / production", found[0].host)
        self.expect("a pair with one host unread is skipped", [], self.kinds([docker], pair))


class Showing(Cases):
    def test_render(self):
        r = reading()
        plain = hosts.render([r], [], False)
        self.expect("table has the host and its docker", True, "production" in plain and "27.3.1" in plain)
        self.expect("all current line", True, "current" in plain and "agree" in plain)
        found = hosts.findings([reading(line="6.8\t6.8\t1.1.1\tno\t4\t1\t")], [])
        self.expect("finding listed", True, "4 packages" in hosts.render([r], found, False))
        self.expect("no colour when off", False, "\033[" in hosts.render([r], found, False))
        self.expect("colour when on", True, "\033[" in hosts.render([r], found, True))

    def test_json(self):
        found = hosts.findings([reading(line="6.8\t6.8\t1.1.1\tyes\t4\t1\tlibc6")], [])
        data = hosts.to_json([reading()], found)
        self.expect("host keys", "production", data["hosts"][0]["label"])
        self.expect("kinds", ["reboot", "packages"], [f["kind"] for f in data["findings"]])
        json.dumps(data)


PROFILE = """application = "widget"

[hosts.production]
ssh = "prod-default"
env = ["BOARD_HOSTS_TEST_PROD"]

[hosts.rehearsal]
ssh = "reh-default"
compare_with = "production"
"""

STUB = """#!/bin/sh
# argv: -n -o BatchMode=yes -o ConnectTimeout=10 <name> <command>
name="$6"
case "$name" in
  down*) echo "no route" >&2; exit 255 ;;
  *) cat "$STUB_DIR/$name" ;;
esac
"""


class Command(Cases):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        stub = self.dir / "ssh-stub"
        stub.write_text(STUB)
        stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
        self.stub = stub

    def answer(self, name, line):
        (self.dir / name).write_text(line + "\n")

    def command(self, *args, profile=PROFILE, **env):
        path = self.dir / "app-profile.toml"
        path.write_text(profile)
        full = dict(os.environ, PROGRAMME_PROFILE=str(path), SSH_COMMAND=str(self.stub),
                    STUB_DIR=str(self.dir))
        full.pop("BOARD_HOSTS_TEST_PROD", None)
        full.update(env)
        return run("board/board-hosts.py", *args, env=full)

    def test_exit_statuses(self):
        self.answer("prod-default", CURRENT)
        self.answer("reh-default", CURRENT)
        done = self.command()
        self.expect("current and agreeing: 0", 0, done.returncode)
        self.expect("says so", True, "current" in done.stdout)

        self.answer("reh-default", "6.8.0-48\t6.8.0-48\t28.0.0\tno\t0\t0\t")
        done = self.command()
        self.expect("a finding: 1", 1, done.returncode)
        self.expect("pair finding shown", True, "Docker" in done.stdout)

        done = self.command(BOARD_HOSTS_TEST_PROD="down-host")
        self.expect("unreadable host: 2", 2, done.returncode)
        self.expect("names it", True, "could not read production (down-host)" in done.stderr)
        self.expect("says closed and dead look alike", True, "look alike" in done.stderr)

    def test_env_override_and_single_host(self):
        self.answer("prod-default", "6.8\t6.8\t1.1.1\tyes\t0\t0\t")
        self.answer("other-name", CURRENT)
        self.answer("reh-default", CURRENT)
        done = self.command("--host", "production", BOARD_HOSTS_TEST_PROD="other-name")
        self.expect("env name replaced ssh; reboot pending on the default was not read", 0, done.returncode)
        done = self.command("--host", "rehearsal")
        self.expect("one host, no pair judged", 0, done.returncode)
        self.expect("unknown host: 2", 2, self.command("--host", "nowhere").returncode)

    def test_json_output(self):
        self.answer("prod-default", CURRENT)
        self.answer("reh-default", CURRENT)
        data = json.loads(self.command("--json").stdout)
        self.expect("both hosts", ["production", "rehearsal"], [h["label"] for h in data["hosts"]])

    def test_malformed_answer_is_unreadable(self):
        self.answer("prod-default", "garbage")
        self.answer("reh-default", CURRENT)
        self.expect("2", 2, self.command().returncode)

    def test_profile_errors(self):
        done = self.command(profile='application = "widget"\n')
        self.expect("no hosts table: 70", 70, done.returncode)
        done = self.command(profile=PROFILE.replace('compare_with = "production"',
                                                    'compare_with = "nowhere"'))
        self.expect("compare_with names no host: 70", 70, done.returncode)


if __name__ == "__main__":
    unittest.main()
