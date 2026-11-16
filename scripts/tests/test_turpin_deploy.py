"""`turpin deploy` and `turpin settle`, with `gates.py`
(delphside/programme#117, task T6).

Test conditions derive from the design (§6 *Errors, results and the pivot*, *Interruption*, the
deploy request's fields, *Flags that set a gate aside*; §9; §11 *The last request*; §12) and the
test design (R6, R15, R26, R27, R29, R30, R31, R32, R58; S17, S29, S30, S48, S49, S58, S59, S90,
S93, S105), not from the code. The host is a stub executable at `hosts.py`'s boundary, the registry
a fake port and the board a fake model.
"""

import contextlib
import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from .test_turpin_core import PROFILE
from .test_turpin_hosts import UUID4, Stubbed

from turpinlib import board, commands, gates, gitrepo, hosts, model, profile, settings  # noqa: E402
from turpinlib.commands import deploy, settle  # noqa: E402
from turpinlib.model import (BusinessError, Digest, ErrorType, Outcome, Reason, ReleaseRecord, Result,  # noqa: E402
                             TechnicalError, Version, exit_status)
from turpinlib.registry.port import BuildImage  # noqa: E402

REAL_RELEASE_MODULE = board.release_module      # the fixtures below replace it
SHA = "a" * 40
OTHER = "b" * 40
SERVER, WEB = "sha256:" + "1" * 64, "sha256:" + "2" * 64
OTHER_SERVER, OTHER_WEB = "sha256:" + "3" * 64, "sha256:" + "4" * 64
HOST_GATES = ["@gate lock passed", "@gate state passed", "@gate digests passed", "@gate hooks-present passed",
              "@gate pre-deploy passed", "@gate smoke passed"]

OK_RESULT = "@result " + json.dumps({"outcome": "ok", "type": None, "blip": None, "reason": None, "domain": "turpin",
                                     "message": "deployed", "metadata": {}, "violations": []})


def text_with(extra: str = "", announcement: bool = True) -> str:
    """The core's profile with a rehearsal environment, a version file, an announcement and `extra`."""
    text = PROFILE.replace('[release]\n', '[release]\nannouncement = "Released in v"\n', 1) if announcement else PROFILE
    text = text.replace('[turpin]\n', '[turpin]\nlogin = "docker-config"\n', 1)
    return text + '''
    [versions.app]
    file = "app.toml"
    pattern = '^version = "([^"]+)"'

    [environments.rehearsal]
    role = "rehearsal"
    ssh = "acme-reh"
    login = "docker-config"
    ''' + extra


def record(version="0.10.2", commit=SHA, images=None, carries=None) -> ReleaseRecord:
    return ReleaseRecord(
        application="acme", version=Version.parse(version), commit=commit, images={
            k: Digest(v) for k, v in (images or {"server": SERVER, "web": WEB}).items()},
        made="2026-11-02T19:04:00Z", carries=carries or {"work_packages": [555], "issues": [560], "releases": []})


class FakeRegistry:
    """The registry port as the controller uses it: what candidates and releases hold."""

    def __init__(self):
        self.builds = {}           # commit -> {image: digest}
        self.releases = set()      # digests
        self.finds = []

    def find_image(self, repository, what):
        self.finds.append((repository.name, what))
        if isinstance(what, BuildImage):
            digest = self.builds.get(what.commit, {}).get(what.name)
            return model.Image(what.name, Digest(digest), what.commit, "") if digest else None
        if isinstance(what, Digest):
            return model.Image("", what, "", "") if str(what) in self.releases else None
        raise AssertionError(f"not asked for: {what}")

    def list_versions(self, repository):
        return tuple(sorted(self.builds))


class Deploying(Stubbed):
    """`turpin deploy` through the front end: the profile and the commit's profile are the text
    below, git and the board are read from fakes, the host is the stub."""

    PROFILE_TEXT = None

    def setUp(self):
        super().setUp()
        self.text = self.PROFILE_TEXT or text_with()
        self.registry = FakeRegistry()
        self.registry.builds[SHA] = {"server": SERVER, "web": WEB}
        self.records = {}
        self.tag_list = ["v0.10.2"]
        self.settled = []
        self.settle_result = Result.ok()
        self.copies = []
        self.exported = []
        self.version_file = 'version = "0.10.2"\n'
        for patcher in (
                mock.patch.object(profile, "repo_dir", lambda: self.dir),
                mock.patch.object(profile, "read_working_tree", lambda repo: profile.parse(self.text, "app-profile.toml")),
                mock.patch.object(profile, "read_at_commit", lambda repo, sha: profile.parse(self.text, f"at {sha[:12]}")),
                mock.patch.object(gitrepo, "fetch_tags", lambda repo: None),
                mock.patch.object(gitrepo, "tags", lambda repo, prefix: [t for t in self.tag_list if t.startswith(prefix)]),
                mock.patch.object(gitrepo, "record_of_tag", self.read_record),
                mock.patch.object(gitrepo, "export_paths", self.export_paths),
                mock.patch.object(gitrepo, "newest_release_made", lambda repo, prof: "2026-11-01T00:00:00Z"),
                mock.patch.object(deploy, "open_registry", lambda prof, log: self.registry),
                mock.patch.object(deploy, "copy_unrecorded", lambda prof, log, resolved: self.copies.append(resolved.commit)),
                mock.patch.object(settle, "settle_version", self.settle_version),
                mock.patch.object(deploy, "post_deploy", lambda *a: None)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def export_paths(self, repo, sha, paths, into):
        """The commit's files: the profile, and the version file it names."""
        files = {"app-profile.toml": self.text, "app.toml": self.version_file}
        for path in paths:
            (into / path).parent.mkdir(parents=True, exist_ok=True)
            (into / path).write_text(files[path])
        return True

    def read_record(self, repo, tag):
        found = self.records.get(tag)
        if isinstance(found, Exception):
            raise found
        return found

    def settle_version(self, repo, prof, version, log):
        self.settled.append(version)
        if isinstance(self.settle_result, BaseException):
            raise self.settle_result
        return self.settle_result

    def host_ok(self, *more, exit=0):
        self.plan({"exit": exit, "stdout": "deployed\n",
                   "stderr": HOST_GATES + list(more) + [OK_RESULT]})

    def deploy(self, env, ref, *flags):
        return self.run_main(["deploy", env, ref, *flags])

    def request(self, n=0):
        return self.requests()[n]

    def gate_events(self):
        log = sorted((self.dir / "logs" / "acme").glob("deploy-*.log"))[-1]
        return [e for e in map(json.loads, log.read_text().splitlines()) if e["event"] == "gate"]

    def gate_named(self, name):
        return [e for e in self.gate_events() if e["name"] == name]

    def untouched(self):
        self.assertEqual([], self.sent(), "the host was called")


class DeployRequest(Deploying):
    """The request the host reads (§6's table) and how it is repeated (§11 *The last request*)."""

    def setUp(self):
        super().setUp()
        # the level of a rehearsal's first deploy is R15's, tested in RehearsalLevelGate
        patcher = mock.patch.object(gates, "rehearsal_level",
                                    lambda log, *a, **k: log.gate("rehearsal-level", "passed", "not under test"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_the_request_names_what_the_host_needs_and_the_digests_by_name(self):
        self.host_ok()
        self.assertEqual(0, self.deploy("rehearsal", SHA)[0])
        request = self.request()
        self.assertRegex(request["request_id"], UUID4)
        self.assertEqual(
            {"repeat": False, "app": "acme", "env": "rehearsal", "role": "rehearsal", "sha": SHA, "version": "0.10.2",
             "images": {"server": SERVER, "web": WEB}, "repo": "acme/candidates", "login": "docker-config",
             "login_component": "rehearsal", "payload_image": "server", "pull_timeout": 300, "lock": None,
             "project": None, "wait": None, "lock_wait": None, "check": False, "local": False, "record": None,
             "set_aside": [], "host_files": True, "env_join": []},
            {k: v for k, v in request.items() if k != "request_id"})

    def test_a_dropped_connection_is_retried_under_the_same_request_id_marked_repeat(self):
        self.plan({"exit": 255, "stderr": ["Connection reset by peer"]}, {"exit": 0, "stderr": HOST_GATES + [OK_RESULT]})
        self.assertEqual(0, self.deploy("rehearsal", SHA)[0])
        first, second = self.requests()[-2:]
        self.assertEqual((first["request_id"], False, True), (second["request_id"], first["repeat"], second["repeat"]))
        self.assertEqual((None, settings.WAIT_DEFAULT_MINUTES), (first["lock_wait"], second["lock_wait"]))

    def test_wait_is_the_hooks_limit_and_the_locks_and_a_bare_wait_is_the_default(self):
        self.host_ok()
        self.deploy("rehearsal", SHA, "--wait=7")
        self.deploy("rehearsal", SHA, "--wait")
        seven, default = self.requests()[-2:]
        self.assertEqual((7, 7), (seven["wait"], seven["lock_wait"]))
        self.assertEqual((settings.WAIT_DEFAULT_MINUTES,) * 2, (default["wait"], default["lock_wait"]))

    def test_a_wait_that_is_not_minutes_is_refused_and_nothing_is_called(self):
        code, _, err = self.deploy("rehearsal", SHA, "--wait=soon")
        self.assertEqual(1, code)
        self.assertIn("--wait", err)
        self.untouched()

    def test_each_command_has_its_own_request_id(self):
        self.host_ok()
        self.deploy("rehearsal", SHA)
        self.deploy("rehearsal", SHA)
        first, second = self.requests()[-2:]
        self.assertNotEqual(first["request_id"], second["request_id"])

    def test_set_aside_gates_go_to_the_host_with_their_reasons_and_to_the_run_log(self):
        self.host_ok()
        self.deploy("rehearsal", SHA, "--set-aside", "pre-deploy", "window closed")
        self.assertEqual([{"gate": "pre-deploy", "reason": "window closed"}], self.requests()[-1]["set_aside"])
        log = sorted((self.dir / "logs" / "acme").glob("deploy-*.log"))[-1].read_text()
        self.assertIn("window closed", log)

    def test_the_builders_login_is_used_where_the_environment_is_on_the_builders_machine(self):
        self.text = text_with().replace('on = "control-node"', 'on = "acme-reh"')
        self.host_ok()
        self.deploy("rehearsal", SHA)
        self.assertEqual("builder", self.requests()[-1]["login_component"])

    def test_a_production_request_reads_releases_and_carries_the_record(self):
        self.records["v0.10.2"] = record()
        self.registry.releases = {SERVER, WEB}
        self.host_ok()
        self.assertEqual(0, self.deploy("production", "0.10.2")[0])
        request = self.request()
        self.assertEqual(("acme/releases", "0.10.2", SHA), (request["repo"], request["version"], request["sha"]))
        self.assertEqual(record().to_json(), request["record"])


class RefGate(Deploying):
    """R6: REF is checked against the role and resolved to stored digests (S58)."""

    def test_a_full_sha_is_resolved_to_the_candidates_digests(self):
        self.host_ok()
        self.assertEqual(0, self.deploy("preview", SHA)[0])
        self.assertEqual({"server": SERVER, "web": WEB}, self.request()["images"])
        self.assertEqual(["passed"], [e["result"] for e in self.gate_named("ref")])

    def test_a_short_sha_resolves_when_one_build_starts_with_it(self):
        self.host_ok()
        self.assertEqual(0, self.deploy("preview", SHA[:9])[0])
        self.assertEqual(SHA, self.request()["sha"])

    def test_an_ambiguous_short_sha_refuses_naming_both_builds_and_calls_nothing(self):
        twin = SHA[:7] + "c" * 33
        self.registry.builds[twin] = {"server": SERVER, "web": WEB}
        code, _, err = self.deploy("preview", SHA[:7])
        self.assertEqual(1, code)
        self.assertIn(SHA, err)
        self.assertIn(twin, err)
        self.untouched()
        self.host_ok()
        self.assertEqual(0, self.deploy("preview", SHA[:8])[0])

    def test_a_sha_too_short_to_be_one_is_a_refused_argument(self):
        code, _, err = self.deploy("preview", "abc")
        self.assertEqual(1, code)
        self.assertIn("refused at gate ref", err)
        self.assertIn("neither a SHA nor a version", err)
        self.untouched()

    def test_unrecorded_with_a_version_is_refused_since_it_takes_a_full_sha(self):
        self.records["v0.10.2"] = record()
        self.registry.releases = {SERVER, WEB}
        code, _, err = self.deploy("production", "0.10.2", "--unrecorded", "x")
        self.assertEqual(1, code)
        self.assertIn("refused at gate ref", err)
        self.assertIn("--unrecorded takes a full SHA", err)
        self.untouched()

    def test_a_build_missing_an_image_refuses_naming_it_and_the_gate(self):
        del self.registry.builds[SHA]["web"]
        code, _, err = self.deploy("preview", SHA)
        self.assertEqual(1, code)
        self.assertIn("refused at gate ref", err)
        self.assertIn("web", err)
        self.assertEqual(["refused"], [e["result"] for e in self.gate_named("ref")])
        self.untouched()

    def test_a_ref_that_is_neither_a_sha_nor_a_version_refuses(self):
        code, _, err = self.deploy("preview", "main")
        self.assertEqual(1, code)
        self.assertIn("neither a SHA nor a version", err)

    def test_a_version_with_a_record_takes_its_commit_and_digests_from_it_without_reading_candidates(self):
        self.records["v0.10.2"] = record(commit=OTHER, images={"server": OTHER_SERVER, "web": OTHER_WEB})
        self.host_ok()
        self.assertEqual(0, self.deploy("preview", "0.10.2")[0])
        request = self.request()
        self.assertEqual((OTHER, {"server": OTHER_SERVER, "web": OTHER_WEB}), (request["sha"], request["images"]))
        self.assertEqual([], self.registry.finds)

    def test_a_v_before_the_version_is_allowed(self):
        self.records["v0.10.2"] = record()
        self.host_ok()
        self.assertEqual(0, self.deploy("preview", "v0.10.2")[0])

    def test_a_tag_with_no_record_deploys_its_commit_from_candidates_except_in_production(self):
        self.tag_list = ["v0.10.1"]
        self.records["v0.10.1"] = None
        with mock.patch.object(gitrepo, "git", lambda repo, *a, **k: SHA + "\n"):
            self.host_ok()
            self.assertEqual(0, self.deploy("preview", "0.10.1")[0])
            self.assertEqual((SHA, "0.10.1"), (self.request()["sha"], self.request()["version"]))
            (self.stub / "sent.log").unlink()
            code, _, err = self.deploy("production", "0.10.1")
        self.assertEqual(1, code)
        self.assertIn("refused at gate production-record", err)
        self.untouched()

    def test_a_version_with_no_tag_refuses(self):
        code, _, err = self.deploy("preview", "0.9.9")
        self.assertEqual(1, code)
        self.assertIn("no tag or record for version 0.9.9", err)

    def test_a_record_version_this_tool_does_not_know_refuses(self):
        self.records["v0.10.2"] = BusinessError.make(Reason.RECORD_VERSION_UNKNOWN, "tag v0.10.2 holds record 2")
        code, _, err = self.deploy("preview", "0.10.2")
        self.assertEqual(1, code)
        self.assertIn("record version this tool does not know", err)
        self.untouched()

    def test_the_version_comes_from_the_version_file_at_the_commit(self):
        self.version_file = 'version = "0.10.7"\nother = 1\n'
        self.host_ok()
        self.deploy("preview", SHA)
        self.assertEqual("0.10.7", self.request()["version"])

    def test_a_registry_that_cannot_be_read_is_never_read_as_no_build(self):
        def down(repository, what):
            raise TechnicalError.make(Reason.REGISTRY_UNREACHABLE, "the registry could not be reached", blip=True)
        self.registry.find_image = down
        code, _, err = self.deploy("preview", SHA)
        self.assertEqual(75, code)
        self.assertNotIn("no build", err)
        self.untouched()


class ProductionRecordGate(Deploying):
    """R26: production takes a version with a record, or `--unrecorded` with a full SHA."""

    def setUp(self):
        super().setUp()
        self.registry.releases = {SERVER, WEB}

    def test_a_raw_sha_refuses_naming_the_flag(self):
        code, _, err = self.deploy("production", SHA)
        self.assertEqual(1, code)
        self.assertIn("refused at gate production-record", err)
        self.assertIn("--unrecorded", err)
        self.untouched()

    def test_a_short_sha_is_refused_even_with_the_flag(self):
        code, _, err = self.deploy("production", SHA[:10], "--unrecorded", "tooling down")
        self.assertEqual(1, code)
        self.assertIn("production-record", err)
        self.untouched()

    def test_a_version_without_a_record_refuses(self):
        code, _, err = self.deploy("production", "0.10.2")
        self.assertEqual(1, code)
        self.assertIn("no record for version 0.10.2", err)
        self.untouched()

    def test_a_records_digest_missing_from_releases_refuses(self):
        self.records["v0.10.2"] = record()
        self.registry.releases = {SERVER}
        code, _, err = self.deploy("production", "0.10.2")
        self.assertEqual(1, code)
        self.assertIn("web digest is not in releases", err)
        self.untouched()

    def test_a_record_with_every_digest_in_releases_passes_and_names_its_version(self):
        self.records["v0.10.2"] = record()
        self.host_ok()
        self.assertEqual(0, self.deploy("production", "0.10.2")[0])
        (gate,) = self.gate_named("production-record")
        self.assertEqual(("passed", "record for 0.10.2"), (gate["result"], gate["detail"]))

    def test_unrecorded_copies_by_sha_logs_the_reason_and_sends_no_record_and_settles_nothing(self):
        self.host_ok()
        self.assertEqual(0, self.deploy("production", SHA, "--unrecorded", "the record tooling is down")[0])
        self.assertEqual([SHA], self.copies)
        (gate,) = self.gate_named("production-record")
        self.assertEqual(("set-aside", "unrecorded: the record tooling is down"), (gate["result"], gate["reason"]))
        self.assertIsNone(self.request()["record"])
        self.assertEqual([], self.settled)

    def test_unrecorded_under_check_copies_nothing(self):
        self.host_ok()
        self.assertEqual(0, self.deploy("production", SHA, "--unrecorded", "x", "--check")[0])
        self.assertEqual([], self.copies)

    def test_a_failed_copy_refuses_at_the_gate_and_calls_no_host(self):
        def failing(prof, log, resolved):
            raise BusinessError.make(Reason.COPY_TO_RELEASES_FAILED, "the copy to releases failed: no")
        with mock.patch.object(deploy, "copy_unrecorded", failing):
            code, _, err = self.deploy("production", SHA, "--unrecorded", "x")
        self.assertEqual(1, code)
        self.assertIn("refused at gate production-record", err)
        self.untouched()

    def test_a_flag_for_another_role_is_refused(self):
        for env, flags in (("rehearsal", ("--unrecorded", "x")), ("production", ("--off-level", "x"))):
            with self.subTest(env, flags=flags):
                code, _, err = self.deploy(env, SHA, *flags)
                self.assertEqual(1, code)
                self.assertIn(flags[0], err)
        self.untouched()


class RehearsalLevelGate(Deploying):
    """R15 (S17, S48, S49): a cycle's first deploy is production's current record."""

    def status(self, *, current="record", deployed=None, deploys=None, previous_deployed=None):
        meta = {"state": "finished", "pending": None, "last_request": None, "previous": None, "running": [],
                "host_files": [], "deploys": []}
        if current is None:
            meta["current"] = None
        else:
            meta["current"] = {"n": 1, "sha": SHA, "version": "0.10.2", "images": {"server": SERVER, "web": WEB},
                               "record": record().to_json() if current == "record" else None,
                               "deployed": deployed}
        if previous_deployed is not None:
            meta["previous"] = {"n": 0, "sha": OTHER, "version": "0.10.1", "images": {"server": SERVER, "web": WEB},
                                "record": None, "deployed": previous_deployed}
        return {"exit": 0, "stdout": json.dumps({"outcome": "ok", "metadata": meta})}

    def deploy_after(self, *reads, flags=()):
        for gone in (self.stub / "calls").iterdir():
            gone.unlink()
        (self.stub / "sent.log").unlink(missing_ok=True)
        self.plan(*reads, {"exit": 0, "stdout": "deployed\n", "stderr": HOST_GATES + [OK_RESULT]})
        return self.deploy("rehearsal", SHA, *flags)

    def hosts_called(self):
        return [s["argv"][-1] for s in self.sent()]

    def test_the_first_deploy_of_a_cycle_must_be_productions_record(self):
        self.registry.builds[SHA] = {"server": OTHER_SERVER, "web": OTHER_WEB}
        code, _, err = self.deploy_after(self.status(current=None, deployed=None), self.status(deployed="2026-10-01T00:00:00Z"))
        self.assertEqual(1, code)
        self.assertIn("refused at gate rehearsal-level", err)
        self.assertIn("starts from production's current record (0.10.2)", err)
        self.assertEqual(2, len(self.sent()))      # the two reads; no deploy

    def test_productions_record_passes_and_is_read_from_productions_host(self):
        code, _, _ = self.deploy_after(self.status(current=None), self.status(deployed="2026-10-01T00:00:00Z"))
        self.assertEqual(0, code)
        self.assertEqual(["turpin-host status acme rehearsal --json", "turpin-host status acme production --json",
                          "turpin-host deploy acme rehearsal"], self.hosts_called())
        self.assertEqual(["acme-reh", "acme-prod", "acme-reh"], [s["argv"][-2] for s in self.sent()])
        log = sorted((self.dir / "logs" / "acme").glob("deploy-*.log"))[-1].read_text()
        self.assertEqual(1, len(re.findall(r'"event":"ssh-read","env":"production"', log)))

    def test_a_later_deploy_of_the_cycle_may_be_any_build(self):
        self.registry.builds[SHA] = {"server": OTHER_SERVER, "web": OTHER_WEB}
        code, _, _ = self.deploy_after(self.status(deployed="2026-11-01T00:00:00Z"))
        self.assertEqual(0, code)
        self.assertEqual(2, len(self.sent()))      # rehearsal's state, then the deploy: production not read

    def test_a_later_deploy_that_is_only_the_previous_one_counts_as_this_cycles(self):
        self.registry.builds[SHA] = {"server": OTHER_SERVER, "web": OTHER_WEB}
        code, _, _ = self.deploy_after(self.status(deployed="2026-10-01T00:00:00Z", previous_deployed="2026-11-02T00:00:00Z"))
        self.assertEqual(0, code)
        self.assertEqual(2, len(self.sent()))      # rehearsal's state, then the deploy: production not read

    def test_a_deploy_from_before_the_last_release_does_not_count_as_this_cycles(self):
        self.registry.builds[SHA] = {"server": OTHER_SERVER, "web": OTHER_WEB}
        code, _, _ = self.deploy_after(self.status(deployed="2026-10-31T23:59:59Z"), self.status(deployed="2026-10-01T00:00:00Z"))
        self.assertEqual(1, code)

    def test_a_production_with_no_turpin_state_or_no_record_refuses(self):
        for production, text in ((self.status(current=None), "production has no turpin state"),
                                 (self.status(current="none"), "no record")):
            with self.subTest(text):
                code, _, err = self.deploy_after(self.status(current=None), production)
                self.assertEqual(1, code)
                self.assertIn("refused at gate rehearsal-level", err)
                self.assertIn(text, err)
                self.assertIn("--off-level", err)

    def test_off_level_sets_the_gate_aside_with_its_reason_in_the_run_log(self):
        self.registry.builds[SHA] = {"server": OTHER_SERVER, "web": OTHER_WEB}
        code, _, _ = self.deploy_after(self.status(current=None), flags=("--off-level", "testing a fix first"))
        self.assertEqual(0, code)
        (gate,) = self.gate_named("rehearsal-level")
        self.assertEqual(("set-aside", "off level: testing a fix first"), (gate["result"], gate["reason"]))
        log = sorted((self.dir / "logs" / "acme").glob("deploy-*.log"))[-1].read_text()
        self.assertIn('"flag":"off-level"', log)

    def test_a_status_that_cannot_be_read_is_never_read_as_a_first_deploy(self):
        self.plan({"exit": 255, "stderr": ["Connection timed out"]})
        code, _, _ = self.deploy("rehearsal", SHA)
        self.assertEqual(75, code)

    def test_the_gate_is_for_the_rehearsal_role_only(self):
        self.host_ok()
        self.assertEqual(0, self.deploy("preview", SHA)[0])
        self.assertEqual([], self.gate_named("rehearsal-level"))


class HostFilesConflict(Deploying):
    """§9: two environments of one application on one machine installing host files refuse."""

    def test_two_environments_on_one_machine_that_both_install_host_files_refuse(self):
        self.text = text_with('''
    [environments.checks]
    role = "test"
    ssh = "acme-reh"
    login = "docker-config"
    host_files = true
    ''').replace('ssh = "acme-reh"\n    login = "docker-config"\n    host_files = true', 'ssh = "acme-reh"\n    login = "docker-config"\n    host_files = true')
        code, _, err = self.deploy("checks", SHA)
        self.assertEqual(1, code)
        self.assertIn("checks rehearsal", err)
        self.assertIn("host_files = false", err)
        self.untouched()

    def test_the_environment_deployed_installing_none_is_fine_whatever_its_neighbours_do(self):
        self.text = text_with('''
    [environments.checks]
    role = "test"
    ssh = "acme-reh"
    login = "docker-config"
    host_files = false

    [environments.second]
    role = "rehearsal"
    ssh = "acme-reh"
    login = "docker-config"
    ''')
        self.host_ok()
        self.assertEqual(0, self.deploy("checks", SHA)[0])

    def test_one_of_them_not_installing_them_is_fine(self):
        self.text = text_with('''
    [environments.checks]
    role = "test"
    ssh = "acme-reh"
    login = "docker-config"
    ''')
        self.host_ok()
        self.assertEqual(0, self.deploy("checks", SHA)[0])


class AfterTheHost(Deploying):
    """§6: the pivot, what follows it, and R31's gate list."""

    def setUp(self):
        super().setUp()
        self.records["v0.10.2"] = record()
        self.registry.releases = {SERVER, WEB}

    def test_a_host_refusal_stops_the_run_by_its_type_and_settles_nothing(self):
        told = {"outcome": "fatal", "type": "business", "blip": None, "reason": "HOST_GATE_REFUSED",
                "domain": "turpin", "message": "refused at gate smoke (exit 1)", "metadata": {}, "violations": []}
        self.plan({"exit": 1, "stderr": HOST_GATES[:5] + ["turpin-host: refused at gate smoke (exit 1)", "@result " + json.dumps(told)]})
        code, _, err = self.deploy("production", "0.10.2")
        self.assertEqual(1, code)
        self.assertEqual([], self.settled)
        self.assertEqual(1, err.count("refused at gate smoke"))

    def test_a_production_deploy_goes_on_to_settle_once_with_the_version(self):
        self.host_ok()
        self.assertEqual(0, self.deploy("production", "0.10.2")[0])
        self.assertEqual(["0.10.2"], self.settled)

    def test_settle_runs_for_production_only_and_not_for_a_check(self):
        self.host_ok()
        self.deploy("rehearsal", SHA, "--off-level", "x")
        self.deploy("production", "0.10.2", "--check")
        self.assertEqual([], self.settled)

    def test_a_settle_that_leaves_work_is_exit_3_naming_the_rerun_and_the_deploy_stands(self):
        self.settle_result = Result(Outcome.ERROR, ErrorType.TECHNICAL, False, Reason.SETTLE_INCOMPLETE.value,
                                    message="settle of 0.10.2 failed; left to do: #560 close; rerun turpin settle 0.10.2")
        self.host_ok()
        code, _, err = self.deploy("production", "0.10.2")
        self.assertEqual(3, code)
        self.assertIn("left to do: #560 close", err)
        self.assertIn("turpin settle 0.10.2", err)

    def test_a_board_that_cannot_be_read_after_the_pivot_is_exit_3_not_75(self):
        self.settle_result = TechnicalError.make(Reason.GIT_FAILED, "the board could not be read for the settle: try again later",
                                                 blip=True)
        self.host_ok()
        code, _, err = self.deploy("production", "0.10.2")
        self.assertEqual(3, code)
        self.assertIn("rerun turpin settle 0.10.2", err)

    def test_a_host_that_ended_with_errors_is_exit_3_and_production_still_settles(self):
        told = {"outcome": "error", "type": "technical", "blip": False, "reason": "HOST_PRUNE_FAILED", "domain": "turpin",
                "message": "pruning the host's images failed; the next deploy prunes again", "metadata": {}, "violations": []}
        self.plan({"exit": 3, "stderr": HOST_GATES + ["turpin-host: " + told["message"], "@result " + json.dumps(told)]})
        code, _, err = self.deploy("production", "0.10.2")
        self.assertEqual(3, code)
        self.assertEqual(["0.10.2"], self.settled)
        self.assertIn("the next deploy repeats it", err)

    def test_a_repeat_answered_with_exit_3_goes_on_to_settle_as_the_first_answer_would_have(self):
        told = {"outcome": "error", "type": "technical", "blip": False, "reason": "HOST_PRUNE_FAILED", "domain": "turpin",
                "message": "pruning failed", "metadata": {}, "violations": []}
        self.plan({"exit": 255, "stderr": ["Connection reset by peer"]},
                  {"exit": 3, "stderr": HOST_GATES + ["@result " + json.dumps(told)]})
        code, _, _ = self.deploy("production", "0.10.2")
        self.assertEqual(3, code)
        self.assertEqual(["0.10.2"], self.settled)
        self.assertTrue(self.requests()[-1]["repeat"])

    def test_a_post_deploy_check_that_fails_is_a_warning_and_leaves_the_exit_code(self):
        self.host_ok()
        warning = Result(Outcome.WARNING, reason=Reason.POST_DEPLOY_REPORTED.value,
                         message="check post-deploy reported exit 1 (the deploy stands)")
        with mock.patch.object(deploy, "post_deploy", lambda *a: warning):
            code, _, err = self.deploy("production", "0.10.2")
        self.assertEqual(0, code)
        self.assertIn("check post-deploy reported exit 1", err)

    def test_a_post_deploy_failure_after_a_deploy_that_is_otherwise_exit_3_leaves_3(self):
        self.settle_result = Result(Outcome.ERROR, ErrorType.TECHNICAL, False, Reason.SETTLE_INCOMPLETE.value,
                                    message="settle of 0.10.2 failed; left to do: #1")
        warning = Result(Outcome.WARNING, reason=Reason.POST_DEPLOY_REPORTED.value,
                         message="check post-deploy reported exit 1 (the deploy stands)")
        self.host_ok()
        with mock.patch.object(deploy, "post_deploy", lambda *a: warning):
            code, _, err = self.deploy("production", "0.10.2")
        self.assertEqual(3, code)
        self.assertIn("settle of 0.10.2 failed", err)
        self.assertIn("check post-deploy reported exit 1", err)

    def test_check_runs_the_gates_and_stops_before_anything_changes(self):
        self.host_ok()
        with mock.patch.object(deploy, "post_deploy", side_effect=AssertionError("ran under --check")):
            code, out, _ = self.deploy("production", "0.10.2", "--check")
        self.assertEqual(0, code)
        self.assertIn("nothing changed", out)
        self.assertTrue(self.request()["check"])

    def test_a_deploy_whose_host_ran_no_smoke_gate_ends_refused_for_the_unrun_gate(self):
        self.plan({"exit": 0, "stderr": HOST_GATES[:5]})
        code, _, err = self.deploy("production", "0.10.2")
        self.assertEqual(1, code)
        self.assertIn("gates unrun: smoke", err)

    def test_under_check_smoke_is_not_expected(self):
        self.plan({"exit": 0, "stderr": HOST_GATES[:5]})
        self.assertEqual(0, self.deploy("production", "0.10.2", "--check")[0])

    def test_the_run_log_names_the_controllers_gates_and_the_hosts(self):
        self.host_ok()
        self.deploy("production", "0.10.2")
        self.assertEqual(["ref", "production-record", "lock", "state", "digests", "hooks-present", "pre-deploy", "smoke"],
                         [e["name"] for e in self.gate_events()])


class Interruption(Deploying):
    """§6 *Interruption* and S90: the message says whether the change is live, and says
    nothing changed only where the host confirms it."""

    HOST_INTERRUPTED = {"outcome": "fatal", "type": "technical", "blip": True, "reason": "HOST_INTERRUPTED",
                        "domain": "turpin", "message": "interrupted before smoke: the deploy is undone",
                        "metadata": {}, "violations": []}

    def test_an_interruption_during_the_gates_changes_nothing_and_names_the_rerun(self):
        with mock.patch.object(gates, "resolve", side_effect=KeyboardInterrupt):
            code, _, err = self.deploy("rehearsal", SHA)
        self.assertEqual(130, code)
        self.assertIn("nothing that runs changed", err)
        self.assertNotIn("copy", err)
        self.assertIn("not live", err)
        self.assertIn(f"turpin deploy rehearsal {SHA}", err)
        self.untouched()

    def test_an_interruption_after_the_copy_to_releases_began_names_the_copy(self):
        def interrupted(prof, log, resolved):
            raise KeyboardInterrupt
        with mock.patch.object(deploy, "copy_unrecorded", interrupted):
            code, _, err = self.deploy("production", SHA, "--unrecorded", "x")
        self.assertEqual(130, code)
        self.assertIn("nothing that runs changed", err)
        self.assertIn("copy of the images to releases was started", err)
        self.assertIn(f"turpin deploy production {SHA}", err)
        self.untouched()

    def test_a_host_that_undid_the_deploy_says_it_is_not_live_and_names_the_rerun(self):
        self.plan({"exit": 130, "stderr": HOST_GATES[:4] + ["@result " + json.dumps(self.HOST_INTERRUPTED)]})
        code, _, err = self.deploy("production", SHA, "--unrecorded", "x")
        self.assertEqual(130, code)
        self.assertIn("the change is not live", err)
        self.assertIn(f"turpin deploy production {SHA}", err)
        self.assertEqual([], self.settled)

    def test_an_interruption_the_host_did_not_confirm_names_status_and_does_not_say_nothing_changed(self):
        self.plan({"exit": 130, "stderr": HOST_GATES[:4]})
        code, _, err = self.deploy("preview", SHA)
        self.assertEqual(130, code)
        self.assertIn("turpin status preview", err)
        self.assertNotIn("nothing changed", err)
        self.assertNotIn("not live", err)

    def test_an_interruption_after_the_host_went_live_starts_no_settle_and_names_it(self):
        self.records["v0.10.2"] = record()
        self.registry.releases = {SERVER, WEB}
        call = hosts.HostCall(code=0, gates=[(g.split()[1], "passed") for g in HOST_GATES], interrupted=True)
        with mock.patch.object(hosts, "call_host", lambda *a, **k: call):
            code, _, err = self.deploy("production", "0.10.2")
        self.assertEqual(130, code)
        self.assertIn("went live", err)
        self.assertIn("turpin settle 0.10.2", err)
        self.assertEqual([], self.settled)

    def test_an_interruption_while_settling_says_the_deploy_is_live_and_names_the_rerun(self):
        self.records["v0.10.2"] = record()
        self.registry.releases = {SERVER, WEB}
        self.settle_result = KeyboardInterrupt()
        self.host_ok()
        code, _, err = self.deploy("production", "0.10.2")
        self.assertEqual(130, code)
        self.assertIn("deploy is live", err)
        self.assertIn("turpin settle 0.10.2", err)


class PostDeployCheck(Stubbed):
    """The check runs the commit's hook on the controller (R29, S59), never the tree's."""

    def setUp(self):
        super().setUp()
        self.repo = self.dir / "work"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        (self.repo / "turpin" / "hooks").mkdir(parents=True)
        self.hook = self.repo / "turpin" / "hooks" / "post-deploy"
        self.write_hook('echo "$TURPIN_ENV $TURPIN_ROLE $TURPIN_SHA $TURPIN_VERSION" > "$OUT"; exit "${EXIT:-0}"')
        self.git("add", "-A")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "app 0.1.0 api 1.0: x")
        self.sha = self.git("rev-parse", "HEAD").strip()
        self.write_hook("touch \"$OUT.tree\"")      # the working tree changes after the commit
        self.env = profile.parse(text_with(), "p").environments["rehearsal"]
        self.prof = profile.parse(text_with(), "p")
        self.resolved = gates.Resolved(self.sha, "0.1.0", {"server": Digest(SERVER)}, None, self.prof)
        self.out = self.dir / "out"
        patcher = mock.patch.dict(os.environ, {"OUT": str(self.out), "XDG_STATE_HOME": str(self.dir / "state")})
        patcher.start()
        self.addCleanup(patcher.stop)

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True, text=True).stdout

    def write_hook(self, body):
        self.hook.write_text(f"#!/usr/bin/env bash\n{body}\n")
        self.hook.chmod(0o755)

    def check(self):
        return deploy.post_deploy(self.repo, self.env, self.resolved, self.prof, self.log)

    def test_it_runs_the_commits_hook_with_the_environment_and_not_the_working_trees(self):
        self.assertIsNone(self.check())
        self.assertEqual(f"rehearsal rehearsal {self.sha} 0.1.0\n", self.out.read_text())
        self.assertFalse((self.dir / "out.tree").exists())

    def test_a_hook_that_could_not_run_is_a_warning_with_the_exit_unchanged_and_the_rollback_hint(self):
        failure = BusinessError.make(Reason.GIT_FAILED, "the hook is not executable")
        with mock.patch.object(deploy.hooks, "run_hook", side_effect=failure):
            result = self.check()
        self.assertEqual((Outcome.WARNING, 0), (result.outcome, exit_status(result)))
        self.assertIn("could not run: the hook is not executable", result.message)
        self.assertIn("turpin rollback rehearsal undoes it", result.message)

    def test_a_hook_that_exits_non_zero_is_a_warning_naming_the_exit_and_the_deploy_standing(self):
        with mock.patch.dict(os.environ, {"EXIT": "1"}):
            result = self.check()
        self.assertEqual((Outcome.WARNING, 0), (result.outcome, exit_status(result)))
        self.assertIn("check post-deploy reported exit 1", result.message)
        self.assertIn("turpin rollback rehearsal undoes it", result.message)

    def test_a_commit_without_the_hook_or_not_in_the_repository_is_quiet(self):
        self.git("rm", "-q", "--cached", "turpin/hooks/post-deploy")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "app 0.1.1 api 1.0: y")
        self.resolved = gates.Resolved(self.git("rev-parse", "HEAD").strip(), "0.1.1", {}, None, self.prof)
        self.assertIsNone(self.check())
        self.resolved = gates.Resolved("c" * 40, "", {}, None, self.prof)
        self.assertIsNone(self.check())


class SettleCommand(Stubbed):
    """§12 and R27: the board to what the record says, from the tag's record."""

    def setUp(self):
        super().setUp()
        self.text = text_with()
        self.record = record(carries={"work_packages": [555], "issues": [560], "releases": []})
        self.tags = ["v0.10.2"]
        self.board = mock.Mock()
        self.board.settle.return_value = {"settled": True, "done": ["#555 state"], "left": []}
        for patcher in (
                mock.patch.object(profile, "repo_dir", lambda: self.dir),
                mock.patch.object(profile, "read_working_tree", lambda repo: profile.parse(self.text, "app-profile.toml")),
                mock.patch.object(gitrepo, "fetch_tags", lambda repo: None),
                mock.patch.object(gitrepo, "tags", lambda repo, prefix: [t for t in self.tags if t.startswith(prefix)]),
                mock.patch.object(gitrepo, "record_of_tag", lambda repo, tag: self.record),
                mock.patch.object(board, "release_module", lambda: self.board),
                mock.patch.object(board, "in_repo", lambda path: contextlib.nullcontext())):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_it_is_registered(self):
        self.assertEqual({"deploy", "settle"}, set(commands.COMMANDS) & {"deploy", "settle"})

    def test_it_settles_what_the_tags_record_carries_with_the_announcement_and_the_tag(self):
        code, out, _ = self.run_main(["settle", "0.10.2"])
        self.assertEqual((0, "settled 0.10.2\n"), (code, out))
        self.board.settle.assert_called_once_with(self.record.to_json(), "Released in v", "v0.10.2")

    def test_a_v_before_the_version_is_allowed_and_a_bad_version_is_refused(self):
        self.assertEqual(0, self.run_main(["settle", "v0.10.2"])[0])
        code, _, err = self.run_main(["settle", "0.10"])
        self.assertEqual(1, code)
        self.assertIn("VERSION", err)

    def test_work_left_is_exit_3_naming_the_items_and_the_rerun(self):
        self.board.settle.return_value = {"settled": False, "done": [], "left": ["#560 close", "milestone 0.10.2"],
                                          "why": "the issues could not be read"}
        code, _, err = self.run_main(["settle", "0.10.2"])
        self.assertEqual(3, code)
        self.assertIn("settle of 0.10.2 failed; left to do: #560 close milestone 0.10.2", err)
        self.assertIn("rerun turpin settle 0.10.2", err)
        self.assertIn("because: the issues could not be read", err)

    def test_a_tag_with_no_record_or_one_this_tool_does_not_read_is_refused_exit_1_and_settles_nothing(self):
        for found in (None, BusinessError.make(Reason.RECORD_VERSION_UNKNOWN, "record 2")):
            with self.subTest(found), mock.patch.object(
                    gitrepo, "record_of_tag", lambda repo, tag: (_ for _ in ()).throw(found) if found else None):
                code, _, err = self.run_main(["settle", "0.10.2"])
            self.assertEqual(1, code)
            self.assertIn("no record this tool reads", err)
        self.board.settle.assert_not_called()

    def test_a_version_with_no_tag_is_refused(self):
        self.tags = []
        code, _, err = self.run_main(["settle", "0.10.2"])
        self.assertEqual(1, code)
        self.assertIn("no tag for 0.10.2", err)

    def test_a_profile_without_an_announcement_is_a_profile_error_exit_2_and_settles_nothing(self):
        self.text = text_with(announcement=False)
        code, _, err = self.run_main(["settle", "0.10.2"])
        self.assertEqual(2, code)
        self.assertIn("release.announcement", err)
        self.board.settle.assert_not_called()

    def test_a_board_that_cannot_be_asked_exits_75_if_transient_else_2_and_a_bad_profile_exits_2(self):
        self.board.settle.side_effect = board.unavailable()("the board did not answer", transient=True)
        self.assertEqual(75, self.run_main(["settle", "0.10.2"])[0])
        self.board.settle.side_effect = board.unavailable()("gh: HTTP 401")      # a refusal is not a blip
        self.assertEqual(2, self.run_main(["settle", "0.10.2"])[0])
        self.board.settle.side_effect = board.profile_error()("programme file missing")
        self.assertEqual(2, self.run_main(["settle", "0.10.2"])[0])

    def test_a_repository_the_model_cannot_name_is_configuration_exit_2(self):
        env = {k: v for k, v in os.environ.items() if k != "TURPIN_GH_REPO"}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(board, "release_module", REAL_RELEASE_MODULE), \
                mock.patch.object(board.repo_module(), "origin_slug", lambda: ""):
            code, _, err = self.run_main(["settle", "0.10.2"])
            with self.assertRaises(TechnicalError) as caught:
                REAL_RELEASE_MODULE()
        self.assertEqual(2, code)
        self.assertIn("TURPIN_GH_REPO", err)
        self.assertEqual(Reason.BOARD_REPOSITORY_UNKNOWN.value, caught.exception.result.reason)

    def test_an_unexpected_exception_exits_70(self):
        self.board.settle.side_effect = KeyError("carries")
        self.assertEqual(70, self.run_main(["settle", "0.10.2"])[0])

    def test_an_interruption_says_the_release_is_live_and_names_the_rerun(self):
        self.board.settle.side_effect = KeyboardInterrupt
        code, _, err = self.run_main(["settle", "0.10.2"])
        self.assertEqual(130, code)
        self.assertIn("turpin settle 0.10.2", err)
        self.assertIn("live", err)

    def test_it_runs_no_gate_and_needs_no_argument_but_the_version(self):
        self.assertEqual(64, self.run_main(["settle"])[0])
        self.assertEqual(64, self.run_main(["settle", "0.10.2", "extra"])[0])


class LoginComponent(unittest.TestCase):
    """One rule for which docker login an environment's deployer uses (design §3 *Logins*)."""

    def test_the_builders_where_the_environment_is_on_its_machine_else_its_own(self):
        prof = profile.parse(text_with().replace('on = "control-node"', 'on = "acme-reh"'), "p")
        self.assertEqual("builder", profile.login_component(prof, prof.environments["rehearsal"]))
        prof = profile.parse(text_with(), "p")
        self.assertEqual("rehearsal", profile.login_component(prof, prof.environments["rehearsal"]))


class ExportedPaths(unittest.TestCase):
    """The post-deploy hook is the commit's, never the working tree's (R29, S59): `export_paths`."""

    def test_export_paths_gives_the_commits_files_and_false_for_one_it_lacks(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        tree, into = Path(tmp.name) / "tree", Path(tmp.name) / "export"
        (tree / "turpin/hooks").mkdir(parents=True)
        (tree / "turpin/hooks/smoke").write_text("#!/bin/sh\n")
        env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
               "GIT_COMMITTER_EMAIL": "t@t"}
        for command in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "x"]):
            subprocess.run(["git", "-C", str(tree), *command], check=True, env=env)
        sha = subprocess.run(["git", "-C", str(tree), "rev-parse", "HEAD"], check=True, capture_output=True,
                             text=True).stdout.strip()
        (tree / "turpin/hooks/smoke").write_text("changed after the commit\n")
        self.assertTrue(gitrepo.export_paths(tree, sha, ["turpin/hooks"], into))
        self.assertEqual("#!/bin/sh\n", (into / "turpin/hooks/smoke").read_text())
        self.assertFalse(gitrepo.export_paths(tree, sha, ["nothing/here"], Path(tmp.name) / "other"))
        self.assertFalse(gitrepo.export_paths(tree, "c" * 40, ["turpin/hooks"], Path(tmp.name) / "other"))


if __name__ == "__main__":
    unittest.main()
