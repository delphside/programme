"""`turpin build`, `promote`, `remove`, `prune` and `login`, and `remote.py` (delphside/programme#117,
task T5): what each command decides.

Test conditions derive from the design (§2 *Command flow*, §3 *Operations* and *Where each
operation runs*, §6 *Errors, results and the pivot*, *Interruption* and *The commands*, §8 *The
`build` hook*) and the test design (R3, R4, R44, R46, R47, R48, R52, R55, S1 to S5, S68 to S70,
S111), not from the code. The registry is faked at the port (`registry.connect.connect` gives a
fake `RegistryPort`), `git` is a real repository in a temporary folder, `docker` is never run
(the default hook's one call is replaced), and `ssh` is an executable on `PATH` that records
what it was asked.
"""

import io
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import textwrap
import threading
import unittest
from pathlib import Path
from unittest import mock

from .test_turpin_core import Isolated
from .test_turpin_registry import AdapterCase, REGISTRY as REGISTRY_ADDRESS, component

from turpinlib import gitrepo, hosts, layout, model, payload, profile, remote, settings  # noqa: E402
from turpinlib.commands import build, login, prune, promote, remove  # noqa: E402
from turpinlib.model import (Api, BusinessError, Build, ComponentKind, CredentialKind, Deployed,  # noqa: E402
                             DeployedBuild, Digest, ErrorType, Image, Outcome, ProgrammeError, Reason,
                             ReleaseRecord, Repository, RepositoryKind, TechnicalError, UnexpectedError,
                             Version, exit_status)
from turpinlib.registry import connect  # noqa: E402
from turpinlib.registry.port import BuildImage, Removal, ReleaseImage  # noqa: E402
from turpinlib.runlog import RunLog  # noqa: E402

SHA = "3f2a9c1" + "0" * 33
OTHER = "8d04e7b" + "0" * 33
CREATED = "2026-11-15T10:00:00Z"
REVISION_LABEL = layout.REVISION
OCI_MANIFEST = "application/vnd.oci.image.manifest.v1+json"
OCI_INDEX = "application/vnd.oci.image.index.v1+json"


def digest(seed: str) -> Digest:
    import hashlib
    return Digest("sha256:" + hashlib.sha256(seed.encode()).hexdigest())


PROFILE = textwrap.dedent('''\
    application = "acme"

    [versions.app]
    file = "app.toml"
    pattern = '^version = "([^"]+)"'

    [release]
    tag_prefix = "v"
    history_prefixes = ["prod-"]

    [turpin]
    candidates = "acme/candidates"
    releases = "acme/releases"
    images = ["server", "web"]
    payload_image = "server"
    join = ["docker-compose.yml"]

    [turpin.build]
    on = "controller"

    [[turpin.host_files]]
    src = "ops/backup.sh"
    dest = "/opt/acme/backup.sh"
    mode = "0755"

    [environments.preview]
    role = "preview"
    host = "controller"

    [environments.rehearsal]
    role = "rehearsal"
    ssh = "acme-rehearsal"
    ''')

# A `build` hook that writes an OCI image layout per image, as Buildx does (design §8): what it
# writes is set by PLAN, a JSON object in its environment, and what it was given goes to PLAN's `log`.
HOOK = r'''#!/usr/bin/env python3
import hashlib, json, os, pathlib
plan = json.loads(os.environ["PLAN"])
with open(plan["log"], "a") as log:
    log.write(json.dumps({k: v for k, v in os.environ.items() if k.startswith("TURPIN_")}) + "\n")

def put(root, data):
    h = hashlib.sha256(data).hexdigest()
    folder = pathlib.Path(root, "blobs", "sha256"); folder.mkdir(parents=True, exist_ok=True)
    (folder / h).write_bytes(data)
    return h

def manifest(root, labels, name):
    layer = put(root, name.encode())
    config = put(root, json.dumps({"config": {"Labels": labels}, "image": name}).encode())
    return put(root, json.dumps({"schemaVersion": 2, "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "config": {"digest": "sha256:" + config}, "layers": [{"digest": "sha256:" + layer}]}).encode())

for name in os.environ["TURPIN_BUILD_IMAGES"].split():
    root = pathlib.Path("out", name)
    labels = {"org.opencontainers.image.revision": os.environ["TURPIN_SHA"],
              "org.opencontainers.image.version": os.environ["TURPIN_VERSION"],
              "org.opencontainers.image.created": os.environ["TURPIN_CREATED"]}
    labels.update(plan.get("labels", {}).get(name, {}))
    if plan.get("index"):
        entries = []
        for n, arch in enumerate(("amd64", "arm64")):
            own = dict(labels)
            if plan.get("bad_platform") == n:
                own["org.opencontainers.image.revision"] = "not-the-commit"
            entries.append({"digest": "sha256:" + manifest(root, own, name + arch),
                            "platform": {"architecture": arch, "os": "linux"}})
            entries.append({"digest": "sha256:" + manifest(root, {}, name + arch + "attestation"),
                            "platform": {"architecture": "unknown", "os": "unknown"},
                            "annotations": {"vnd.docker.reference.type": "attestation-manifest"}})
        top = put(root, json.dumps({"schemaVersion": 2, "mediaType": "application/vnd.oci.image.index.v1+json",
                                    "manifests": entries}).encode())
    else:
        top = manifest(root, labels, name)
    (root / "index.json").write_text(json.dumps({"schemaVersion": 2, "manifests": [{"digest": "sha256:" + top}]}))
    if name not in plan.get("unnamed", []):
        print(name, root)
'''


class FakePort:
    """A `RegistryPort` in memory: what candidates holds, and every call it was made."""

    def __init__(self):
        self.present: dict[tuple[str, str], Image] = {}    # (commit, image name) -> the image
        self.versions: tuple = ()
        self.released: dict[tuple[str, str], Image] = {}   # (version text, image name) -> the image
        self.unrecorded: list[Image] = []                  # held by releases under a commit tag
        self.find_error: ProgrammeError | None = None
        self.store_error: ProgrammeError | None = None
        self.remove_errors: dict[str, ProgrammeError] = {}
        self.outcomes: dict[str, Removal] = {}
        self.calls: list[tuple] = []

    def find_image(self, repository, what):
        self.calls.append(("find_image", repository.kind.value, what))
        if self.find_error is not None:
            raise self.find_error
        if isinstance(what, Digest):                  # releases hold it under whatever tag
            return next((i for i in [*self.released.values(), *self.unrecorded] if i.digest == what), None)
        if isinstance(what, BuildImage):
            return self.present.get((what.commit, what.name))
        return self.released.get((str(what.version), what.name))

    def list_versions(self, repository):
        self.calls.append(("list_versions", repository.kind.value))
        if repository.kind is RepositoryKind.CANDIDATES:
            return tuple(sorted({commit for commit, _ in self.present}))
        return tuple(sorted({Version.parse(v) for v, _ in self.released}))

    def store_build(self, repository, commit, layouts):
        self.calls.append(("store_build", commit, {k: str(v) for k, v in layouts.items()}))
        if self.store_error is not None:
            raise self.store_error
        return Build(commit, {name: digest(f"{commit}{name}") for name in layouts})

    def promote(self, candidates, releases, build, version, record):
        self.calls.append(("promote", build, version, record))
        tags = [f"{version or build.commit}-{name}" for name in build.images]
        return mock.Mock(written=tuple(tags), skipped=())

    def remove_candidate(self, repository, build, image, keep, removing):
        tag = f"{build.commit}-{image}"
        self.calls.append(("remove_candidate", tag, tuple(str(d) for d in keep), frozenset(removing)))
        if tag in self.remove_errors:
            raise self.remove_errors[tag]
        return self.outcomes.get(tag, Removal.REMOVED)

    def make_login(self, component, user, token):
        self.calls.append(("make_login", component.kind.value, component.login.value, user, token))

    def ensure_credentials(self, component):
        self.calls.append(("ensure_credentials", component.kind.value))

    def named(self, name):
        return [c for c in self.calls if c[0] == name]


class Repo:
    """A real git repository of the application with its remote, in a folder of its own."""

    def __init__(self, root: Path, hook: str | None = HOOK):
        self.work, self.remote = root / "work", root / "remote.git"
        self.git("init", "-q", "--bare", str(self.remote), cwd=root)
        self.work.mkdir()
        self.git("init", "-q", "-b", "main", cwd=self.work)
        self.git("remote", "add", "origin", str(self.remote), cwd=self.work)
        (self.work / "app-profile.toml").write_text(PROFILE)
        (self.work / "app.toml").write_text('version = "0.10.2"\n')
        (self.work / "docker-compose.yml").write_text("services: {}\n")
        (self.work / "ops").mkdir()
        (self.work / "ops" / "backup.sh").write_text("#!/bin/sh\n")
        if hook is not None:
            (self.work / "turpin" / "hooks").mkdir(parents=True)
            path = self.work / "turpin" / "hooks" / "build"
            path.write_text(hook)
            path.chmod(0o755)
        self.commit("first")

    @staticmethod
    def git(*args, cwd):
        env = dict(os.environ, GIT_AUTHOR_NAME="T", GIT_AUTHOR_EMAIL="t@e.test",
                   GIT_COMMITTER_NAME="T", GIT_COMMITTER_EMAIL="t@e.test")
        return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True, env=env).stdout.strip()

    def commit(self, message, push=True) -> str:
        self.git("add", "-A", cwd=self.work)
        self.git("commit", "-q", "--allow-empty", "-m", message, cwd=self.work)
        if push:
            self.git("push", "-q", "origin", "main", cwd=self.work)
        return self.git("rev-parse", "HEAD", cwd=self.work)


class CommandCase(Isolated):
    """The environment a command runs in: the repository, the fake port, the plan the hook follows."""

    def setUp(self):
        super().setUp()
        self.repo = Repo(self.dir)
        self.port = FakePort()
        self.plan = {"log": str(self.dir / "hook.log")}
        patchers = [
            mock.patch.dict(os.environ, {"TURPIN_REPO": str(self.repo.work), "PLAN": "{}"}),
            mock.patch.object(connect, "connect", side_effect=self.connect),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        for name in (settings.ENV_CALLED, settings.ENV_ON_BUILD_HOST):
            os.environ.pop(name, None)
        self.connections = []

    def connect(self, app, component, log, bind=True):
        self.connections.append((app, component, bind))
        return self.port

    def set_plan(self, **plan):
        self.plan.update(plan)
        os.environ["PLAN"] = json.dumps(self.plan)

    def hook_calls(self):
        path = Path(self.plan["log"])
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def gates(self):
        """The gates the run logged, name to verdict, of the newest run log."""
        logs = sorted((self.dir / "logs" / "acme").glob("*.log"), key=lambda p: p.stat().st_mtime)
        events = [json.loads(line) for line in logs[-1].read_text().splitlines()]
        return {e["name"]: e["result"] for e in events if e["event"] == "gate"}


# ----------------------------------------------------------------------- build

class Building(CommandCase):
    def build(self, *argv):
        self.set_plan()
        return self.run_main(["build", *argv])

    def test_build_refuses_a_commit_not_on_the_remote(self):
        sha = self.repo.commit("unpushed", push=False)
        code, out, err = self.build(sha)
        self.assertEqual(1, code)
        self.assertIn("build-commit", err)
        self.assertIn("is not a commit on the remote", err)
        self.assertEqual([], self.port.named("store_build"))
        self.assertEqual([], self.hook_calls())
        self.assertEqual("refused", self.gates()["build-commit"])
        self.repo.git("push", "-q", "origin", "main", cwd=self.repo.work)
        self.assertEqual(0, self.build(sha)[0])

    def test_build_refuses_a_ref_that_is_not_a_commit(self):
        code, _, err = self.build("no-such-ref")
        self.assertEqual(1, code)
        self.assertIn("no-such-ref is not a commit", err)

    def test_build_pushes_each_image_as_it_names_it_and_prints_a_digest_a_line(self):
        sha = self.repo.git("rev-parse", "HEAD", cwd=self.repo.work)
        code, out, _ = self.build()
        self.assertEqual(0, code)
        stored = self.port.named("store_build")
        self.assertEqual(1, len(stored))
        self.assertEqual(sha, stored[0][1])
        self.assertEqual(["server", "web"], sorted(stored[0][2]))
        self.assertEqual([f"server {digest(sha + 'server')}", f"web {digest(sha + 'web')}"], out.splitlines())
        self.assertEqual({"build-commit", "store-query", "store-immutable", "build-labels"}, set(self.gates()))

    def test_build_never_rebuilds_an_image_already_stored(self):
        sha = self.repo.git("rev-parse", "HEAD", cwd=self.repo.work)
        have = Image("server", digest("kept"), sha, CREATED)
        self.port.present[(sha, "server")] = have
        code, out, _ = self.build()
        self.assertEqual(0, code)
        (call,) = self.hook_calls()
        self.assertEqual("web", call["TURPIN_BUILD_IMAGES"])                  # the hook is asked for the one missing
        (stored,) = self.port.named("store_build")
        self.assertEqual(["web"], sorted(stored[2]))                          # and only it is pushed
        self.assertEqual(f"server {digest('kept')}", out.splitlines()[0])      # the one held is named as it is
        self.port.present[(sha, "web")] = Image("web", digest("kept web"), sha, CREATED)
        self.hook_calls_before = len(self.hook_calls())
        self.assertEqual(0, self.build()[0])
        self.assertEqual(self.hook_calls_before, len(self.hook_calls()))      # all present: nothing built
        self.assertEqual(1, len(self.port.named("store_build")))

    def test_build_stops_when_the_registry_cannot_be_queried_by_exit_type_and_builds_nothing(self):
        for blip, expected in ((True, 75), (False, 2)):         # docs/1.10: a blip is 75, a fundamental error 2
            with self.subTest(blip=blip):
                self.port.find_error = TechnicalError.make(Reason.REGISTRY_UNREACHABLE, "the registry did not "
                                                           "answer", blip=blip)
                code, _, err = self.build()
                self.assertEqual(expected, code)
                self.assertIn("store-query", err)
                self.assertEqual([], self.hook_calls())
                self.assertEqual([], self.port.named("store_build"))
                self.assertEqual("refused", self.gates()["store-query"])

    def test_a_commit_pushed_since_the_builders_last_fetch_is_built(self):
        other = self.dir / "other"
        Repo.git("clone", "-q", "-b", "main", str(self.repo.remote), str(other), cwd=self.dir)
        (other / "src.txt").write_text("from elsewhere")
        Repo.git("add", "-A", cwd=other)
        Repo.git("-c", "user.name=T", "-c", "user.email=t@e.test", "commit", "-q", "-m", "elsewhere", cwd=other)
        Repo.git("push", "-q", "origin", "HEAD:main", cwd=other)
        sha = Repo.git("rev-parse", "HEAD", cwd=other)
        # the builder's clone has never seen it
        self.assertEqual(1, subprocess.run(["git", "cat-file", "-e", sha], cwd=self.repo.work).returncode)
        code, _, err = self.build(sha)
        self.assertEqual(0, code, err)
        self.assertEqual(sha, self.port.named("store_build")[0][1])

    def test_the_images_to_build_are_the_commits_profiles_not_the_working_trees(self):
        sha = self.repo.git("rev-parse", "HEAD", cwd=self.repo.work)
        (self.repo.work / "app-profile.toml").write_text(PROFILE.replace('images = ["server", "web"]', 'images = ["server"]'))
        code, _, err = self.build(sha)
        self.assertEqual(0, code, err)
        self.assertEqual("server web", self.hook_calls()[0]["TURPIN_BUILD_IMAGES"])

    def test_an_interruption_after_the_build_and_before_the_push_stores_nothing(self):
        class AfterTheBuild(remote.Watcher):
            checks = 0

            def __init__(self, *a, **k):
                self.event = threading.Event()

            def check(self, message):
                AfterTheBuild.checks += 1
                if AfterTheBuild.checks == 2:                  # the second look is the one before the push
                    raise KeyboardInterrupt(message)
        with mock.patch.object(remote, "Watcher", AfterTheBuild):
            code, _, err = self.build()
        self.assertEqual(130, code)
        self.assertIn("nothing was stored", err)
        self.assertEqual(1, len(self.hook_calls()))             # the hook did run
        self.assertEqual([], self.port.named("store_build"))

    def test_build_refuses_an_image_whose_labels_differ_and_pushes_nothing(self):
        for label in ("revision", "version", "created"):
            with self.subTest(label=label):
                self.set_plan(labels={"web": {f"org.opencontainers.image.{label}": "other"}})
                code, _, err = self.run_main(["build"])
                self.assertEqual(1, code)
                self.assertIn("build-labels", err)
                self.assertEqual([], self.port.named("store_build"))

    def test_build_gives_every_image_the_same_created_label_in_rfc_3339_utc(self):
        self.build()
        (call,) = self.hook_calls()
        self.assertRegex(call["TURPIN_CREATED"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        # what `build` set once is what it reads back from each image's configuration
        self.assertEqual(0, self.run_main(["build"])[0])
        self.assertEqual("0.10.2", call["TURPIN_VERSION"])                    # from the version file at the commit
        self.assertEqual(self.repo.git("rev-parse", "HEAD", cwd=self.repo.work), call["TURPIN_SHA"])

    def test_build_passes_over_an_attestation_manifest_and_checks_each_platform_image(self):
        self.set_plan(index=True)
        self.assertEqual(0, self.run_main(["build"])[0])                      # attestations carry no labels: passed over
        self.assertEqual(1, len(self.port.named("store_build")))
        self.port.calls.clear()
        self.set_plan(index=True, bad_platform=1)                              # the second platform has another revision
        code, _, err = self.run_main(["build"])
        self.assertEqual(1, code)
        self.assertIn("build-labels", err)
        self.assertEqual([], self.port.named("store_build"))

    def test_build_builds_in_a_clean_worktree_of_the_commit_and_leaves_none_behind(self):
        (self.repo.work / "app.toml").write_text('version = "9.9.9"\n')       # the operator's tree: dirty
        self.assertEqual(0, self.build()[0])
        (call,) = self.hook_calls()
        self.assertEqual("0.10.2", call["TURPIN_VERSION"])
        self.assertNotIn("turpin-build", self.repo.git("worktree", "list", cwd=self.repo.work))
        self.assertFalse(Path(call["TURPIN_PAYLOAD_DIR"]).exists())

    def test_the_hook_is_given_the_environment_the_design_names(self):
        self.build()
        (call,) = self.hook_calls()
        for name in ("TURPIN_APP", "TURPIN_SHA", "TURPIN_VERSION", "TURPIN_CREATED", "TURPIN_PAYLOAD_DIR",
                     "TURPIN_BUILD_IMAGES"):
            self.assertIn(name, call)
        self.assertEqual("acme", call["TURPIN_APP"])
        self.assertNotIn("TURPIN_LOCAL", call)

    def test_a_hook_that_names_no_layout_for_an_image_refuses(self):
        self.set_plan()
        hook = self.repo.work / "turpin" / "hooks" / "build"
        hook.write_text(HOOK.replace('print(name, root)', 'pass'))
        self.repo.commit("a hook that names nothing")
        code, _, err = self.run_main(["build"])
        self.assertEqual(1, code)
        self.assertIn("named no layout for image", err)
        self.assertEqual([], self.port.named("store_build"))

    def test_a_hook_that_refuses_stops_the_build_naming_it(self):
        hook = self.repo.work / "turpin" / "hooks" / "build"
        hook.write_text("#!/bin/sh\nexit 3\n")
        self.repo.commit("a hook that fails")
        code, _, err = self.build()
        self.assertEqual(1, code)
        self.assertIn("hook build refused", err)
        self.assertEqual([], self.port.named("store_build"))

    def test_the_store_failing_stops_the_run_by_its_type(self):
        self.port.store_error = UnexpectedError.make(Reason.REGISTRY_DIGEST_CHANGED, "the registry stores another digest")
        self.assertEqual(70, self.build()[0])

    def test_a_missing_registry_login_is_the_next_step_and_exit_2(self):
        def refuse(app, component, log, bind=True):
            raise TechnicalError.make(Reason.REGISTRY_LOGIN_MISSING,
                                      "the builder has no registry login: run `turpin login builder`")
        with mock.patch.object(connect, "connect", side_effect=refuse):
            code, _, err = self.build()
        self.assertEqual(2, code)
        self.assertIn("turpin login builder", err)

    def test_the_build_connects_as_the_builder_with_the_profiles_login(self):
        self.build()
        ((app, comp, bind),) = self.connections
        self.assertEqual(("acme", ComponentKind.BUILDER, CredentialKind.DOCKER_CONFIG), (app, comp.kind, comp.login))
        self.assertTrue(bind)


_real_run = subprocess.run


def only_docker(argv, **kw):
    """`docker image inspect` answers an image id; git and the rest run for real."""
    if argv[0] == "docker":
        return mock.Mock(returncode=0, stdout="sha256:" + "ab" * 32 + "\n")
    return _real_run(argv, **kw)


class BuildingLocally(CommandCase):
    def test_local_loads_into_docker_pushes_nothing_and_names_each_image_by_its_id(self):
        sha = self.repo.commit("unpushed", push=False)
        self.set_plan()
        seen = []
        with mock.patch.object(build, "_run_docker", side_effect=lambda tree, argv: seen.append(argv)), \
                mock.patch.object(subprocess, "run", side_effect=only_docker):
            code, out, err = self.run_main(["build", sha, "--local"])
        self.assertEqual(0, code, err)
        self.assertEqual([], self.port.named("store_build"))
        self.assertEqual([], self.connections)                                  # no registry login is needed
        self.assertEqual("server", out.splitlines()[0].split()[0])
        self.assertEqual(["server", "web"], [line.split()[0] for line in out.splitlines()])
        (call,) = self.hook_calls()
        self.assertEqual("1", call["TURPIN_LOCAL"])
        self.assertEqual(f"turpin-local/acme-server:{sha}", call["TURPIN_BUILD_TAG_SERVER"])   # where to tag it
        self.assertEqual(f"turpin-local/acme-web:{sha}", call["TURPIN_BUILD_TAG_WEB"])

    def test_local_reads_the_names_the_hook_prints_and_an_image_it_does_not_name_is_refused(self):
        sha = self.repo.commit("unpushed", push=False)
        self.set_plan(unnamed=["web"])
        with mock.patch.object(subprocess, "run", side_effect=only_docker):
            code, _, err = self.run_main(["build", sha, "--local"])
        self.assertEqual(1, code)
        self.assertIn("did not name image web", err)

    def test_local_is_for_the_preview_role_and_the_profile_must_have_one(self):
        text = PROFILE.replace('role = "preview"', 'role = "test"')
        (self.repo.work / "app-profile.toml").write_text(text)
        sha = self.repo.commit("no preview", push=False)
        code, _, err = self.run_main(["build", sha, "--local"])
        self.assertEqual(1, code)
        self.assertIn("--local is for the preview role", err)


class TheDefaultHook(CommandCase):
    def run_default(self, local):
        (self.repo.work / "turpin" / "hooks" / "build").unlink(missing_ok=True)
        self.sha_built = self.repo.commit("no hook")
        seen = []
        with mock.patch.object(build, "_run_docker", side_effect=lambda tree, argv: seen.append(argv)):
            if local:
                with mock.patch.object(subprocess, "run", side_effect=only_docker):
                    code, out, err = self.run_main(["build", "--local"])
            else:
                # no layouts are written by the stub: only the labels and the bake line are looked at
                code, out, err = self.run_main(["build"])
        return seen, code, err

    def test_the_default_hook_sets_the_labels_by_bake_and_under_load(self):
        seen, _, _ = self.run_default(local=False)
        self.assertEqual(2, len(seen))                                          # one bake per image
        argv = seen[0]
        self.assertEqual(["docker", "buildx", "bake", "--builder", "turpin"], argv[:5])
        sets = [argv[i + 1] for i, word in enumerate(argv) if word == "--set"]
        self.assertIn(f"server.labels.org.opencontainers.image.revision={self.sha_built}", sets)
        self.assertIn("server.labels.org.opencontainers.image.version=0.10.2", sets)
        self.assertTrue(any(s.startswith("server.labels.org.opencontainers.image.created=20") for s in sets))
        self.assertIn("server.output=type=oci,dest=.turpin/oci/server,tar=false", sets)
        self.assertEqual("server", argv[-1])
        self.assertNotIn("--load", argv)
        # under --local the same labels, loaded and tagged where a preview deploy looks
        seen, code, err = self.run_default(local=True)
        self.assertEqual(0, code, err)
        argv = seen[0]
        self.assertIn("--load", argv)
        sets = [argv[i + 1] for i, word in enumerate(argv) if word == "--set"]
        self.assertTrue(any(s.startswith("server.labels.org.opencontainers.image.revision=") for s in sets))
        self.assertTrue(any(s.startswith("server.tags=turpin-local/acme-server:") for s in sets))
        self.assertFalse(any(".output=" in s for s in sets))

    def test_the_default_hook_passes_the_profiles_build_arguments_taken_from_turpin_values(self):     # T5
        text = PROFILE.replace('[turpin.build]\non = "controller"',
                               '[turpin.build]\non = "controller"\nargs = {ACME_BUILD_ID = "SHORT_SHA", ACME_COMMIT = "SHA", ACME_V = "VERSION"}')
        (self.repo.work / "app-profile.toml").write_text(text)
        seen, code, err = self.run_default(local=False)
        sets = [seen[0][i + 1] for i, word in enumerate(seen[0]) if word == "--set"]
        self.assertIn(f"server.args.ACME_BUILD_ID={self.sha_built[:7]}", sets)
        self.assertIn(f"server.args.ACME_COMMIT={self.sha_built}", sets)
        self.assertIn("server.args.ACME_V=0.10.2", sets)
        self.assertTrue(any(s.startswith("web.args.ACME_BUILD_ID=") for s in [seen[1][i + 1] for i, w in enumerate(seen[1]) if w == "--set"]))
        seen, _, _ = self.run_default(local=True)                                     # and under --local
        self.assertIn(f"server.args.ACME_BUILD_ID={self.sha_built[:7]}", [seen[0][i + 1] for i, w in enumerate(seen[0]) if w == "--set"])

    def test_a_profile_without_build_arguments_passes_none(self):                                   # T5
        seen, _, _ = self.run_default(local=False)
        self.assertFalse(any(".args." in word for word in seen[0]))

    def test_the_default_hook_reads_nothing_of_the_operators_tree(self):
        seen, _, _ = self.run_default(local=False)
        self.assertTrue(seen)          # run in the worktree, which `_run_docker` is given as its first argument


class Layouts(unittest.TestCase):
    def write(self, root, entries):
        import hashlib

        def put(data):
            h = hashlib.sha256(data).hexdigest()
            (root / "blobs" / "sha256").mkdir(parents=True, exist_ok=True)
            (root / "blobs" / "sha256" / h).write_bytes(data)
            return "sha256:" + h

        def image(labels):
            config = put(json.dumps({"config": {"Labels": labels}}).encode())
            return put(json.dumps({"config": {"digest": config}, "layers": []}).encode())

        top = put(json.dumps({"manifests": [dict(e, digest=image(e.pop("labels"))) for e in entries]}).encode()) \
            if entries and len(entries) > 1 else image(entries[0]["labels"])
        (root / "index.json").write_text(json.dumps({"manifests": [{"digest": top}]}))

    def test_a_layout_with_no_index_has_one_platform_image(self):
        with tempfile.TemporaryDirectory() as folder:
            self.write(Path(folder), [{"labels": {"a": "b"}}])
            self.assertEqual([{"a": "b"}], [labels for _, labels in layout.platform_labels(Path(folder), "x")])

    def test_an_index_lists_each_platform_and_leaves_its_attestations_out(self):
        with tempfile.TemporaryDirectory() as folder:
            self.write(Path(folder), [
                {"labels": {"p": "1"}, "platform": {"architecture": "amd64"}},
                {"labels": {}, "platform": {"architecture": "unknown"}, "annotations": {"vnd.docker.reference.type": "attestation-manifest"}},
                {"labels": {"p": "2"}, "platform": {"architecture": "arm64"}}])
            self.assertEqual([{"p": "1"}, {"p": "2"}], [labels for _, labels in layout.platform_labels(Path(folder), "x")])

    def test_an_attestation_marked_only_by_its_annotation_is_left_out(self):
        with tempfile.TemporaryDirectory() as folder:
            self.write(Path(folder), [
                {"labels": {"p": "1"}, "platform": {"architecture": "amd64", "os": "linux"}},
                {"labels": {}, "platform": {"architecture": "amd64", "os": "linux"},
                 "annotations": {"vnd.docker.reference.type": "attestation-manifest"}}])
            self.assertEqual([{"p": "1"}], [labels for _, labels in layout.platform_labels(Path(folder), "x")])

    def test_an_attestation_marked_only_by_the_unknown_architecture_is_left_out(self):
        with tempfile.TemporaryDirectory() as folder:
            self.write(Path(folder), [
                {"labels": {"p": "1"}, "platform": {"architecture": "amd64", "os": "linux"}},
                {"labels": {}, "platform": {"architecture": "unknown", "os": "unknown"}}])
            self.assertEqual([{"p": "1"}], [labels for _, labels in layout.platform_labels(Path(folder), "x")])

    def test_a_folder_that_is_no_layout_is_a_business_error_naming_the_image(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(BusinessError) as caught:
                layout.platform_labels(Path(folder), "web")
        self.assertEqual(Reason.BUILD_NO_LAYOUT.value, caught.exception.result.reason)
        self.assertIn("web", caught.exception.result.message)


class VersionFile(unittest.TestCase):
    def tree(self, profile_text, files):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        root = Path(folder.name)
        (root / "app-profile.toml").write_text(profile_text)
        for name, text in files.items():
            (root / name).write_text(text)
        return root

    def test_the_version_is_the_first_line_the_pattern_matches(self):
        root = self.tree(PROFILE, {"app.toml": 'name = "x"\nversion = "1.2.3"\nversion = "9.9.9"\n'})
        self.assertEqual(Version(1, 2, 3), profile.version_in_tree(root))

    def test_a_version_that_is_not_semver_is_a_business_error_naming_the_file(self):
        root = self.tree(PROFILE, {"app.toml": 'version = "one"\n'})
        with self.assertRaises(BusinessError) as caught:
            profile.version_in_tree(root)
        self.assertIn("app.toml", caught.exception.result.message)
        self.assertEqual("version", caught.exception.result.violations[0].field)

    def test_a_file_with_no_matching_line_and_a_missing_file_are_business_errors(self):
        for files in ({"app.toml": "nothing\n"}, {}):
            root = self.tree(PROFILE, files)
            with self.assertRaises(BusinessError) as caught:
                profile.version_in_tree(root)
            self.assertEqual(Reason.VERSION_FILE_UNREADABLE.value, caught.exception.result.reason)

    def test_a_profile_with_no_version_pattern_is_a_fundamental_profile_error(self):
        root = self.tree(PROFILE.replace('pattern = \'^version = "([^"]+)"\'', ""), {"app.toml": 'version = "1.0.0"\n'})
        with self.assertRaises(model.ProfileError) as caught:
            profile.version_in_tree(root)
        self.assertEqual("versions.app.pattern", caught.exception.result.metadata["key"])


class Payloads(unittest.TestCase):
    def test_the_payload_holds_the_steps_hooks_joined_files_and_host_files_of_the_commit_not_a_working_tree(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = Repo(Path(folder))
            sha = repo.git("rev-parse", "HEAD", cwd=repo.work)
            tree = Path(folder) / "tree"
            repo.git("worktree", "add", "-q", "--detach", str(tree), sha, cwd=repo.work)
            (repo.work / "docker-compose.yml").write_text("services: {dirty: {}}\n")      # the operator's tree
            dest = Path(folder) / "payload"
            payload.assemble(repo.work, tree, sha, dest)
            self.assertEqual("services: {}\n", (dest / "join" / "docker-compose.yml").read_text())
            self.assertTrue((dest / "host_files" / "ops" / "backup.sh").exists())
            self.assertTrue((dest / "hooks" / "build").exists())
            for name in ("deploy", "rollback", "steps.sh", "lib/common.sh", "lib/toml.sh", "lib/toml.awk", "profile.json"):
                self.assertTrue((dest / name).exists(), name)
            self.assertEqual("acme", json.loads((dest / "profile.json").read_text())["application"])
            self.assertEqual(sorted(os.listdir(dest)), sorted(set(os.listdir(dest))))
            for path in dest.rglob("*"):
                if path.is_file():
                    self.assertNotIn("token", path.name.lower())

    def test_the_payload_carries_only_the_profile_keys_a_host_reads(self):                          # T6
        from turpinlib import board
        with tempfile.TemporaryDirectory() as folder:
            repo = Repo(Path(folder))
            sha = repo.git("rev-parse", "HEAD", cwd=repo.work)
            tree = Path(folder) / "tree"
            repo.git("worktree", "add", "-q", "--detach", str(tree), sha, cwd=repo.work)
            dest = Path(folder) / "payload"
            payload.assemble(repo.work, tree, sha, dest)
            carried = json.loads((dest / "profile.json").read_text())
            self.assertEqual({"application", "turpin"}, set(carried))      # not versions, release, environments
            self.assertEqual({"host_files", "join"}, set(carried["turpin"]))
            for key in ("candidates", "releases", "images", "payload_image", "build"):
                self.assertNotIn(key, carried["turpin"])
            everything = {"application": "a", "versions": {"x": 1}, "environments": {"p": {}},
                          "release": {"tag_prefix": "v", "required_hooks": ["h"], "overridable": ["o"]},
                          "turpin": {"candidates": "c", "fallback": "f", "host_files": [], "join": [], "ephemeral": {}}}
            self.assertEqual({"application": "a", "release": {"required_hooks": ["h"], "overridable": ["o"]},
                              "turpin": {"fallback": "f", "host_files": [], "join": [], "ephemeral": {}}},
                             board.shipping_module().host_profile(everything))
            self.assertEqual("ops/backup.sh", carried["turpin"]["host_files"][0]["src"])

    def test_the_payload_carries_the_libraries_the_board_model_names_and_no_others(self):          # T6
        from turpinlib import board
        with tempfile.TemporaryDirectory() as folder:
            repo = Repo(Path(folder))
            sha = repo.git("rev-parse", "HEAD", cwd=repo.work)
            tree = Path(folder) / "tree"
            repo.git("worktree", "add", "-q", "--detach", str(tree), sha, cwd=repo.work)
            dest = Path(folder) / "payload"
            payload.assemble(repo.work, tree, sha, dest)
            self.assertEqual(sorted(board.shipping_module().LIB_FILES), sorted(os.listdir(dest / "lib")))
            smaller = Path(folder) / "smaller"
            with mock.patch.object(board.shipping_module(), "LIB_FILES", ("common.sh",)):
                payload.assemble(repo.work, tree, sha, smaller)
            self.assertEqual(["common.sh"], os.listdir(smaller / "lib"))

    def test_a_joined_file_the_commit_does_not_have_is_a_business_error(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = Repo(Path(folder))
            (repo.work / "docker-compose.yml").unlink()
            sha = repo.commit("lose the joined file")
            tree = Path(folder) / "tree"
            repo.git("worktree", "add", "-q", "--detach", str(tree), sha, cwd=repo.work)
            with self.assertRaises(BusinessError) as caught:
                payload.assemble(repo.work, tree, sha, Path(folder) / "payload")
            self.assertIn("docker-compose.yml", caught.exception.result.message)


# --------------------------------------------------------------- promote, remove

class CalledCase(CommandCase):
    def call(self, command, request, app="acme", called=True, closed_input=False):
        text = request if isinstance(request, str) else json.dumps(request)
        env = {settings.ENV_CALLED: "1"} if called else {}
        # the caller holds the input open for the call's life, so the pipe's write end stays open
        r, w = os.pipe()
        os.write(w, (text + "\n").encode())
        if closed_input:
            os.close(w)
        reader = os.fdopen(r)
        try:
            with mock.patch.dict(os.environ, env), mock.patch.object(sys, "stdin", reader):
                return self.run_main([command, app])
        finally:
            if not closed_input:
                os.close(w)  # the watcher thread ends at the end of input, which frees the reader
            reader.close()


BUILD_IMAGES = {"server": str(digest("s")), "web": str(digest("w"))}
RECORD = {"record": 1, "application": "acme", "version": "0.10.2", "commit": SHA, "images": BUILD_IMAGES,
          "made": "2026-11-15T00:00:00Z"}


def promote_request(**changes):
    request = {"login": "docker-config", "candidates": "acme/candidates", "releases": "acme/releases",
               "commit": SHA, "images": BUILD_IMAGES, "version": "0.10.2", "record": RECORD}
    request.update(changes)
    return request


class Promoting(CalledCase):
    def test_promote_copies_the_build_with_its_version_and_record_as_the_copier(self):
        code, out, err = self.call("promote", promote_request())
        self.assertEqual(0, code, err)
        (_, build_, version, record) = self.port.named("promote")[0]
        self.assertEqual((SHA, {k: Digest(v) for k, v in BUILD_IMAGES.items()}), (build_.commit, dict(build_.images)))
        self.assertEqual(Version(0, 10, 2), version)
        self.assertEqual(SHA, record.commit)
        self.assertEqual(["copied 0.10.2-server", "copied 0.10.2-web"], out.splitlines())
        ((app, comp, _),) = self.connections
        self.assertEqual((ComponentKind.COPIER, CredentialKind.DOCKER_CONFIG), (comp.kind, comp.login))

    def test_an_unrecorded_promotion_has_neither_a_version_nor_a_record(self):
        code, out, _ = self.call("promote", promote_request(version=None, record=None))
        self.assertEqual(0, code)
        (_, _, version, record) = self.port.named("promote")[0]
        self.assertEqual((None, None), (version, record))
        self.assertIn(f"copied {SHA}-server", out)

    def test_a_field_that_fails_its_form_is_unexpected_naming_the_field(self):
        for change, field in ((dict(commit="abc"), "commit"), (dict(images={"server": "sha256:short"}), "digest"),
                              (dict(version="one"), "version")):
            with self.subTest(field=field):
                code, _, err = self.call("promote", promote_request(**change))
                self.assertEqual(70, code)
                self.assertIn(field, err)
        self.assertEqual([], self.port.named("promote"))

    def test_a_request_that_is_not_json_or_lacks_a_field_is_unexpected(self):
        self.assertEqual(70, self.call("promote", "{not json")[0])
        request = promote_request()
        del request["releases"]
        self.assertEqual(70, self.call("promote", request)[0])
        self.assertEqual(70, self.call("promote", promote_request(login="made-up"))[0])

    def test_a_refusal_from_the_registry_stops_by_its_type(self):
        self.port.promote = mock.Mock(side_effect=BusinessError.make(Reason.NO_OVERWRITE, "releases already holds it"))
        self.assertEqual(1, self.call("promote", promote_request())[0])

    def test_an_application_that_is_not_a_name_is_a_business_error(self):
        self.assertEqual(1, self.call("promote", promote_request(), app="../x")[0])

    def test_a_called_promote_reports_its_result_as_the_last_line_for_the_caller(self):
        self.port.promote = mock.Mock(side_effect=BusinessError.make(Reason.NO_OVERWRITE, "releases already holds it"))
        _, _, err = self.call("promote", promote_request())
        last = err.strip().splitlines()[-1]
        self.assertTrue(last.startswith("@result "))
        self.assertEqual("NO_OVERWRITE", json.loads(last[len("@result "):])["reason"])

    def test_the_gate_lines_and_result_are_for_a_called_turpin_only(self):
        self.port.promote = mock.Mock(side_effect=BusinessError.make(Reason.NO_OVERWRITE, "releases already holds it"))
        _, _, err = self.call("promote", promote_request(), called=False)
        self.assertNotIn("@result", err)

    def test_an_interruption_before_the_copy_starts_changes_nothing_and_exits_130(self):
        class Gone(remote.Watcher):
            def __init__(self, *a, **k):
                self.event = threading.Event()
                self.event.set()
        with mock.patch.object(remote, "Watcher", Gone):
            code, _, err = self.call("promote", promote_request())
        self.assertEqual(130, code)
        self.assertIn("nothing was changed", err)
        self.assertEqual([], self.port.named("promote"))


def remove_request(removes, keep=(), **changes):
    request = {"login": "docker-config", "candidates": "acme/candidates",
               "removes": [{"commit": c, "image": i, "digest": str(digest(c + i))} for c, i in removes],
               "keep": [str(k) for k in keep]}
    request.update(changes)
    return request


class Removing(CalledCase):
    def test_remove_removes_each_candidate_as_the_builder_with_its_removal_credential(self):
        code, out, err = self.call("remove", remove_request([(SHA, "server"), (OTHER, "web")]))
        self.assertEqual(0, code, err)
        self.assertEqual([f"removed {SHA}-server", f"removed {OTHER}-web"], out.splitlines())
        ((_, comp, _),) = self.connections
        self.assertEqual(ComponentKind.BUILDER, comp.kind)
        self.assertEqual({Api.REGISTRY, Api.ARTIFACTS}, {c.api for c in comp.credentials})

    def test_every_removal_is_given_the_full_set_of_tags_this_prune_removes_and_the_keep_list(self):
        keep = [digest("released")]
        self.call("remove", remove_request([(SHA, "server"), (OTHER, "web")], keep))
        calls = self.port.named("remove_candidate")
        self.assertEqual(2, len(calls))
        for call in calls:
            self.assertEqual(frozenset({f"{SHA}-server", f"{OTHER}-web"}), call[3])
            self.assertEqual((str(keep[0]),), call[2])

    def test_a_tag_that_moved_is_gone_or_shared_is_left_and_no_error(self):
        self.port.outcomes = {f"{SHA}-server": Removal.TAG_MOVED, f"{SHA}-web": Removal.ALREADY_GONE,
                              f"{OTHER}-server": Removal.SHARED}
        code, out, _ = self.call("remove", remove_request([(SHA, "server"), (SHA, "web"), (OTHER, "server")]))
        self.assertEqual(0, code)
        self.assertEqual([f"tag-moved {SHA}-server", f"already-gone {SHA}-web", f"shared {OTHER}-server"],
                         out.splitlines())

    def test_a_candidate_that_fails_is_an_error_the_others_are_removed_and_the_exit_is_3(self):
        self.port.remove_errors[f"{SHA}-server"] = TechnicalError.make(
            Reason.REMOVAL_NOT_AUTHORIZED, "the registry would not delete the image: check the policy")
        code, out, err = self.call("remove", remove_request([(SHA, "server"), (OTHER, "web")]))
        self.assertEqual(3, code)
        self.assertEqual([f"removed {OTHER}-web"], out.splitlines())
        self.assertIn("1 of 2 candidates could not be removed", err)
        self.assertIn("turpin prune", err)
        self.assertEqual(2, len(self.port.named("remove_candidate")))         # the failure did not stop the rest
        self.assertTrue(err.strip().splitlines()[-1].startswith("@result "))

    def test_a_digest_in_the_keep_list_is_refused_and_is_an_error(self):
        self.port.remove_errors[f"{SHA}-server"] = BusinessError.make(Reason.KEEP_LIST, "it is in the keep list")
        code, _, err = self.call("remove", remove_request([(SHA, "server")]))
        self.assertEqual(3, code)

    def test_a_request_whose_digest_or_commit_fails_its_form_is_unexpected(self):
        request = remove_request([(SHA, "server")])
        request["removes"][0]["digest"] = "nope"
        self.assertEqual(70, self.call("remove", request)[0])
        request = remove_request([(SHA, "server")])
        request["removes"][0]["commit"] = "abc"
        self.assertEqual(70, self.call("remove", request)[0])
        self.assertEqual(70, self.call("remove", remove_request([(SHA, "server")], keep=["x"]))[0])
        self.assertEqual([], self.port.named("remove_candidate"))

    def test_an_interruption_starts_no_further_removal_and_names_the_rerun(self):
        class After(remote.Watcher):
            checks = 0

            def __init__(self, *a, **k):
                self.event = threading.Event()

            def check(self, message):
                After.checks += 1
                if After.checks > 1:
                    raise KeyboardInterrupt(message)
        with mock.patch.object(remote, "Watcher", After):
            code, _, err = self.call("remove", remove_request([(SHA, "server"), (OTHER, "web")]))
        self.assertEqual(130, code)
        self.assertIn("run turpin prune again", err)
        self.assertEqual(1, len(self.port.named("remove_candidate")))


# ----------------------------------------------------------------------- prune

def status_of(current=None, previous=None):
    def deploy(images):
        return None if images is None else DeployedBuild(Build(SHA, images), None, None)
    return hosts.HostStatus(Deployed("finished", None, None, None, deploy(current), deploy(previous)), (), (), ())


class Pruning(CommandCase):
    """`created` before the newest release's `made` removes; nothing in `keep` is removed."""

    NEWEST = "2026-06-01T00:00:00Z"

    def setUp(self):
        super().setUp()
        self.sent = []
        self.records = {"v0.9.0": ReleaseRecord("acme", Version(0, 9, 0), SHA, {"server": digest("rel-s")}, self.NEWEST)}
        self.call_result = mock.Mock(code=0, result=None)
        self.status = {}
        patchers = [
            mock.patch.object(gitrepo, "fetch_tags"),
            mock.patch.object(gitrepo, "tags", side_effect=lambda repo, prefix: [t for t in self.records if t.startswith(prefix)]),
            mock.patch.object(gitrepo, "record_of_tag", side_effect=lambda repo, tag: self.records[tag]),
            mock.patch.object(hosts, "host_status", side_effect=lambda machine, app, env, log: self.status.get(env, status_of())),
            mock.patch.object(remote, "call_turpin", side_effect=self.send),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def send(self, machine, args, **kw):
        self.sent.append((machine, list(args), kw))
        return self.call_result

    def candidate(self, commit, name, created="2026-05-01T00:00:00Z"):
        self.port.present[(commit, name)] = Image(name, digest(commit + name), commit, created)

    def test_a_candidate_built_before_the_newest_release_and_unreferenced_is_removed(self):
        self.candidate(SHA, "server")
        self.candidate(OTHER, "web", created="2026-07-01T00:00:00Z")           # built after the release: kept
        code, out, err = self.run_main(["prune", "--dry-run"])
        self.assertEqual(0, code, err)
        self.assertEqual([f"would remove {SHA}-server"], out.splitlines())

    def test_prune_keeps_what_a_release_a_record_or_an_environment_runs(self):
        for name in ("a", "b", "c", "d", "e"):
            self.candidate(name * 40, "server")
        self.records["v0.9.0"] = ReleaseRecord("acme", Version(0, 9, 0), SHA, {"server": digest("a" * 40 + "server")}, self.NEWEST)
        self.port.released[("0.8.0", "server")] = Image("server", digest("b" * 40 + "server"), "x", "x")
        self.status["preview"] = status_of(current={"server": digest("c" * 40 + "server")})
        self.status["rehearsal"] = status_of(previous={"server": digest("d" * 40 + "server")})
        code, out, _ = self.run_main(["prune", "--dry-run"])
        self.assertEqual(0, code)
        self.assertEqual([f"would remove {'e' * 40}-server"], out.splitlines())

    def test_a_candidate_an_unrecorded_release_copied_is_kept_though_it_has_no_version(self):
        self.candidate(SHA, "server")
        self.port.unrecorded.append(Image("server", digest(SHA + "server"), SHA, "x"))   # releases' tag SHA-server
        code, out, err = self.run_main(["prune", "--dry-run"])
        self.assertEqual(0, code, err)
        self.assertEqual("", out)

    def test_a_candidate_with_no_created_label_or_an_unreadable_one_is_never_removed(self):
        self.candidate(SHA, "server", created="")
        self.candidate(OTHER, "server", created="yesterday")
        _, out, _ = self.run_main(["prune", "--dry-run"])
        self.assertEqual("", out)

    def test_dry_run_sends_nothing(self):
        self.candidate(SHA, "server")
        self.run_main(["prune", "--dry-run"])
        self.assertEqual([], self.sent)

    def test_the_candidates_are_sent_to_the_builder_with_the_keep_list_and_its_login(self):
        self.candidate(SHA, "server")
        self.candidate(OTHER, "web")
        self.candidate("c" * 40, "server")
        self.port.released[("0.8.0", "server")] = Image("server", digest("c" * 40 + "server"), "x", "x")
        code, out, err = self.run_main(["prune"])
        self.assertEqual(0, code, err)
        ((machine, args, kw),) = self.sent
        self.assertEqual((model.CONTROLLER, ["remove", "acme"]), (machine, args))
        request = kw["request"]
        self.assertEqual("docker-config", request["login"])
        self.assertEqual("acme/candidates", request["candidates"])
        self.assertEqual([{"commit": SHA, "image": "server", "digest": str(digest(SHA + "server"))},
                          {"commit": OTHER, "image": "web", "digest": str(digest(OTHER + "web"))}],
                         sorted(request["removes"], key=lambda r: r["commit"]))
        self.assertIn(str(digest("c" * 40 + "server")), request["keep"])
        self.assertTrue(kw["retry"])                                           # a remove repeats safely

    def test_a_builder_on_another_machine_is_called_there(self):
        (self.repo.work / "app-profile.toml").write_text(PROFILE.replace('on = "controller"', 'on = "the-builder"'))
        self.candidate(SHA, "server")
        self.run_main(["prune"])
        self.assertEqual("the-builder", self.sent[0][0])

    def test_the_controller_never_removes(self):
        self.candidate(SHA, "server")
        self.run_main(["prune"])
        self.assertEqual([], self.port.named("remove_candidate"))
        ((_, comp, _),) = self.connections
        self.assertEqual(ComponentKind.CONTROLLER, comp.kind)
        self.assertNotIn(Api.ARTIFACTS, [c.api for c in comp.credentials])

    def test_a_candidate_the_builder_failed_to_remove_is_an_error_exit_3_naming_prune(self):
        self.candidate(SHA, "server")
        self.call_result = mock.Mock(code=3, result=model.Result(Outcome.ERROR, ErrorType.TECHNICAL, False, "X"))
        code, _, err = self.run_main(["prune"])
        self.assertEqual(3, code)
        self.assertIn("run turpin prune again", err)

    def test_the_builders_result_is_kept_as_the_cause_so_the_log_names_the_failed_tags(self):
        self.candidate(SHA, "server")
        told = model.Result(Outcome.ERROR, ErrorType.TECHNICAL, False, "PRUNE_REMOVE_FAILED",
                            message="1 of 1", errors=(model.Result(Outcome.FATAL, ErrorType.TECHNICAL, False, "X",
                                                                   message=f"not removed {SHA}-server"),))
        self.call_result = mock.Mock(code=3, result=told)
        self.run_main(["prune"])
        log = "".join(p.read_text() for p in (self.dir / "logs" / "acme").glob("*.log"))
        self.assertIn(f"not removed {SHA}-server", log)

    def test_nothing_to_remove_calls_nobody(self):
        code, out, _ = self.run_main(["prune"])
        self.assertEqual(0, code)
        self.assertEqual([], self.sent)

    def test_with_no_release_nothing_is_old_enough_and_the_run_refuses(self):
        self.records.clear()
        code, _, err = self.run_main(["prune"])
        self.assertEqual(1, code)
        self.assertIn("no release has been made", err)

    def test_a_tag_with_no_record_counts_its_date_and_releases_none_of_its_candidates(self):
        self.records.clear()
        self.records["v0.5.0"] = None
        self.candidate(SHA, "server", created="2026-01-01T00:00:00Z")
        with mock.patch.object(prune, "tag_date", return_value=prune._when("2026-06-01T00:00:00Z")):
            _, out, _ = self.run_main(["prune", "--dry-run"])
        self.assertEqual([f"would remove {SHA}-server"], out.splitlines())

    def test_a_host_that_cannot_be_read_stops_the_run_with_nothing_sent(self):
        self.candidate(SHA, "server")
        with mock.patch.object(hosts, "host_status", side_effect=TechnicalError.make(
                Reason.SSH_CONNECTION_LOST, "the connection to x was lost", blip=True)):
            code, _, _ = self.run_main(["prune"])
        self.assertEqual(75, code)
        self.assertEqual([], self.sent)


# ----------------------------------------------------------------------- login

class LoginCase(CommandCase):
    def run_login(self, *argv, stdin="tle-user\nthe-token\n"):
        with mock.patch.object(sys, "stdin", io.StringIO(stdin)):
            return self.run_main(["login", *argv])


class Login(LoginCase):
    def setUp(self):
        super().setUp()
        self.docker = []
        patcher = mock.patch.object(login, "docker_login", side_effect=lambda app, user, token: self.docker.append((user, token)))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.sent = []
        patcher = mock.patch.object(remote, "call_turpin", side_effect=lambda *a, **k: self.sent.append((a, k)))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_the_controller_and_the_copier_make_their_own_skopeo_login_only(self):
        for who, kind in (("controller", "controller"), ("copier", "copier")):
            self.port.calls.clear()
            code, out, err = self.run_login(who)
            self.assertEqual(0, code, err)
            self.assertIn(f"logged in: {who}", out)
            self.assertEqual([("make_login", kind, "docker-config", "tle-user", "the-token")], self.port.named("make_login"))
        self.assertEqual([], self.docker)

    def test_the_builder_also_makes_the_docker_login_where_an_environment_on_its_machine_pulls_with_it(self):
        code, out, _ = self.run_login("builder")
        self.assertEqual(0, code)
        self.assertEqual([("tle-user", "the-token")], self.docker)            # preview is on the builder's machine
        self.assertEqual(1, len(self.port.named("make_login")))
        self.assertIn("logged in: builder", out)
        # with no environment on the builder's machine there is no docker login to make
        self.docker.clear()
        (self.repo.work / "app-profile.toml").write_text(PROFILE.replace('host = "controller"', 'ssh = "elsewhere"'))
        self.assertEqual(0, self.run_login("builder")[0])
        self.assertEqual([], self.docker)

    def test_an_environment_on_the_builders_machine_is_refused_naming_turpin_login_builder(self):
        code, _, err = self.run_login("preview")
        self.assertEqual(1, code)
        self.assertIn("preview shares the builder's docker login on this machine: run turpin login builder", err)
        self.assertEqual([], self.port.named("make_login"))

    def test_an_unknown_component_is_refused(self):
        code, _, err = self.run_login("nonsense")
        self.assertEqual(1, code)
        self.assertIn("nonsense is not controller, builder, copier or an environment", err)

    def test_an_empty_token_or_user_is_refused_before_anything_is_made(self):
        for stdin in ("tle-user\n\n", "\ntoken\n", ""):
            with self.subTest(stdin=stdin):
                code, _, err = self.run_login("copier", stdin=stdin)
                self.assertEqual(1, code)
                self.assertIn("login needs a user and a token", err)
        self.assertEqual([], self.port.named("make_login"))

    def test_an_environment_runs_turpin_host_login_with_the_user_and_token_as_data(self):
        with mock.patch.object(hosts, "call_host") as call:
            code, _, _ = self.run_login("rehearsal")
        self.assertEqual(0, code)
        args, kwargs = call.call_args
        self.assertEqual(("acme-rehearsal", ["login", "acme", "deployer", "rehearsal"]), args)
        self.assertEqual("tle-user\nthe-token\n", kwargs["data"])
        self.assertTrue(kwargs["retry"])                                      # a login overwrites: safe to repeat

    def test_a_builder_or_copier_on_another_machine_is_reached_by_turpin_login_passed_on(self):
        (self.repo.work / "app-profile.toml").write_text(PROFILE.replace('on = "controller"', 'on = "the-builder"'))
        code, _, _ = self.run_login("builder")
        self.assertEqual(0, code)
        ((args, kwargs),) = self.sent
        self.assertEqual(("the-builder", ["login", "builder"]), args)
        self.assertEqual("tle-user\nthe-token\n", kwargs["data"])
        self.assertTrue(kwargs["retry"])
        self.assertEqual([], self.port.named("make_login"))                    # nothing was made on this machine

    def test_the_token_is_never_in_the_output_the_run_log_or_an_argument(self):
        code, out, err = self.run_login("builder", stdin="tle-user\ncanary-token-value\n")
        self.assertEqual(0, code)
        self.assertNotIn("canary-token-value", out + err)
        for log in (self.dir / "logs").rglob("*.log"):
            self.assertNotIn("canary-token-value", log.read_text())
        (self.repo.work / "app-profile.toml").write_text(PROFILE.replace('on = "controller"', 'on = "the-builder"'))
        self.run_login("builder", stdin="tle-user\ncanary-token-value\n")
        for (args, kwargs) in self.sent:
            self.assertNotIn("canary-token-value", json.dumps(args))

    def test_a_fundamental_failure_says_a_new_auth_token_can_take_a_few_minutes(self):
        self.port.make_login = mock.Mock(side_effect=TechnicalError.make(
            Reason.REGISTRY_REFUSED, "the registry refused the controller's login: run turpin login controller"))
        code, _, err = self.run_login("controller")
        self.assertEqual(2, code)
        self.assertIn("a new auth token can take a few minutes to start working", err)

    def test_a_called_login_reads_its_data_up_to_the_closing_line_and_runs_here(self):
        (self.repo.work / "app-profile.toml").write_text(PROFILE.replace('on = "controller"', 'on = "the-builder"'))
        with mock.patch.dict(os.environ, {settings.ENV_CALLED: "1"}):
            code, out, err = self.run_login("builder", stdin="tle-user\nthe-token\n# turpin: end\n")
        self.assertEqual(0, code, err)
        self.assertEqual(1, len(self.port.named("make_login")))
        self.assertEqual([], self.sent)

    def test_a_called_login_without_the_closing_line_changes_nothing_and_exits_75(self):
        with mock.patch.dict(os.environ, {settings.ENV_CALLED: "1"}):
            code, _, err = self.run_login("builder", stdin="tle-user\nthe-token\n")
        self.assertEqual(75, code)
        self.assertEqual([], self.port.named("make_login"))
        self.assertEqual([], self.docker)


class MakingALogin(AdapterCase):
    def test_make_login_runs_skopeo_login_with_the_token_and_binds_no_credentials(self):
        self.adapter.make_login(component(ComponentKind.COPIER), "tle-releaser", "tok")
        self.assertEqual([("skopeo_login", ("tle-releaser", "tok"))], self.registry.log)
        with self.assertRaises(UnexpectedError):                              # not bound: no other operation ran
            self.adapter.find_image(Repository(RepositoryKind.CANDIDATES, "acme/candidates"),
                                    BuildImage("a" * 40, "server"))


class Components(unittest.TestCase):
    def test_the_builder_holds_an_api_key_for_removal_or_its_instance_principal(self):
        key = connect.component_of(ComponentKind.BUILDER, CredentialKind.DOCKER_CONFIG, removal=True)
        self.assertEqual([("auth-token", Api.REGISTRY), ("api-key", Api.ARTIFACTS)],
                         [(c.form.value, c.api) for c in key.credentials])
        principal = connect.component_of(ComponentKind.BUILDER, CredentialKind.OCI_INSTANCE_PRINCIPAL, removal=True)
        self.assertEqual([("instance-principal", Api.REGISTRY), ("instance-principal", Api.ARTIFACTS)],
                         [(c.form.value, c.api) for c in principal.credentials])
        self.assertEqual(1, len(connect.component_of(ComponentKind.BUILDER, CredentialKind.OCI_API_KEY).credentials))


# ---------------------------------------------------------------------- remote

SSH = '''#!/usr/bin/env python3
import json, os, sys
base = os.environ["STUB_DIR"]
line = sys.stdin.readline()
with open(base + "/sent.log", "a") as log:
    log.write(json.dumps({"argv": sys.argv[1:], "line": line, "called": os.environ.get("TURPIN_CALLED")}) + "\\n")
step = json.load(open(base + "/plan.json"))
for text in step.get("stderr", []):
    print(text, file=sys.stderr)
print(step.get("stdout", ""), end="")
sys.exit(step.get("exit", 0))
'''


class Remote(Isolated):
    def setUp(self):
        super().setUp()
        self.stub = self.dir / "stub"
        self.stub.mkdir()
        bindir = self.dir / "bin"
        bindir.mkdir()
        (bindir / "ssh").write_text(SSH)
        (bindir / "ssh").chmod(0o755)
        (bindir / "turpin").write_text(SSH)
        (bindir / "turpin").chmod(0o755)
        patcher = mock.patch.dict(os.environ, {"PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}",
                                               "STUB_DIR": str(self.stub), settings.ENV_BIN: str(bindir / "turpin")})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.log = RunLog()

    def plan(self, **step):
        (self.stub / "plan.json").write_text(json.dumps(step))

    def sent(self):
        return [json.loads(line) for line in (self.stub / "sent.log").read_text().splitlines()]

    def test_a_command_on_another_machine_is_one_ssh_call_that_says_it_is_called(self):
        self.plan()
        remote.call_turpin("the-builder", ["build", SHA], log=self.log, extra={settings.ENV_ON_BUILD_HOST: "1"})
        (sent,) = self.sent()
        self.assertEqual(["-o", "BatchMode=yes", "the-builder",
                          f"TURPIN_CALLED=1 TURPIN_ON_BUILD_HOST=1 turpin build {SHA}"], sent["argv"])

    def test_the_request_is_one_line_on_standard_input(self):
        self.plan()
        remote.call_turpin("the-copier", ["promote", "acme"], log=self.log, request={"a": 1})
        self.assertEqual('{"a":1}\n', self.sent()[0]["line"])

    def test_on_this_machine_the_call_runs_turpin_itself_without_ssh(self):
        self.plan()
        remote.call_turpin(model.CONTROLLER, ["remove", "acme"], log=self.log, request={})
        (sent,) = self.sent()
        self.assertEqual(["remove", "acme"], sent["argv"])
        self.assertEqual("1", sent["called"])                   # the child still knows it is called

    def test_ssh_255_is_mapped_by_its_error_text_as_for_turpin_host(self):
        self.plan(exit=255, stderr=["x@y: Permission denied (publickey)."])
        with self.assertRaises(TechnicalError) as caught:
            remote.call_turpin("the-builder", ["build", SHA], log=self.log)
        self.assertFalse(caught.exception.result.blip)
        self.assertIn("refused the key", caught.exception.result.message)
        self.plan(exit=255, stderr=["Connection reset by peer"])
        with self.assertRaises(TechnicalError) as caught:
            remote.call_turpin("the-builder", ["build", SHA], log=self.log, where="read the run log")
        self.assertTrue(caught.exception.result.blip)
        self.assertIn("read the run log", caught.exception.result.message)

    def test_a_build_is_not_retried_and_a_remove_is(self):
        self.plan(exit=255, stderr=["Connection reset by peer"])
        with mock.patch.object(hosts, "_sleep"):
            with self.assertRaises(TechnicalError):
                remote.call_turpin("b", ["build", SHA], log=self.log, retry=False)
            self.assertEqual(1, len(self.sent()))
            with self.assertRaises(TechnicalError):
                remote.call_turpin("b", ["remove", "acme"], log=self.log, request={}, retry=True)
        self.assertEqual(1 + settings.RETRY_ATTEMPTS, len(self.sent()))

    def test_the_called_sides_result_and_gates_come_back_as_its_reason_and_log_lines(self):
        result = {"outcome": "fatal", "type": "business", "blip": None, "reason": "NO_OVERWRITE",
                  "domain": "turpin", "message": "releases already holds it", "metadata": {}, "violations": []}
        self.plan(exit=1, stderr=["@gate store-query passed", "turpin: releases already holds it",
                                  "@result " + json.dumps(result)])
        log = RunLog.start("acme", "test", [])
        with self.assertRaises(BusinessError) as caught:
            remote.call_turpin("b", ["promote", "acme"], log=log, request={})
        self.assertEqual("NO_OVERWRITE", caught.exception.result.reason)
        self.assertIn("store-query", log.ran)

    def test_exit_3_is_done_with_errors_and_returns_the_call(self):
        self.plan(exit=3, stdout="removed x\n")
        call = remote.call_turpin("b", ["remove", "acme"], log=self.log, request={})
        self.assertEqual(3, call.code)

    def test_a_turpin_missing_on_the_machine_names_how_to_install_it(self):
        self.plan(exit=127)
        with self.assertRaises(TechnicalError) as caught:
            remote.call_turpin("b", ["build", SHA], log=self.log)
        self.assertIn("turpin is not on b", caught.exception.result.message)


class CalledSide(unittest.TestCase):
    def test_the_end_of_input_is_the_callers_interruption(self):
        watcher = remote.Watcher(io.StringIO("\n"), watching=True)
        self.assertTrue(watcher.event.wait(2))
        self.assertTrue(watcher.interrupted)
        with self.assertRaises(KeyboardInterrupt):
            watcher.check("stop")

    def test_it_does_not_watch_where_nothing_called_it(self):
        watcher = remote.Watcher(io.StringIO(""), watching=False)
        self.assertFalse(watcher.interrupted)
        watcher.check("never")

    def test_a_request_is_the_first_line_and_must_be_an_object(self):
        stream = io.StringIO('{"a": 1}\nmore\n')
        self.assertEqual({"a": 1}, remote.read_request("x", stream))
        for text in ("", "[1]\n", "nope\n"):
            with self.assertRaises(UnexpectedError):
                remote.read_request("x", io.StringIO(text))

    def test_data_ends_at_the_closing_line_which_is_removed_and_without_it_nothing_is_changed(self):
        self.assertEqual(["u", "t"], remote.read_data(io.StringIO("u\nt\n# turpin: end\n")))
        with self.assertRaises(TechnicalError) as caught:
            remote.read_data(io.StringIO("u\nt\n"))
        self.assertTrue(caught.exception.result.blip)


class WireForm(Isolated):
    def test_a_called_turpin_prints_each_gate_it_runs_as_a_line_on_standard_error(self):
        err = io.StringIO()
        with mock.patch.dict(os.environ, {settings.ENV_CALLED: "1"}), mock.patch.object(sys, "stderr", err):
            RunLog().gate("build-commit", "passed", "on the remote")
        self.assertEqual("@gate build-commit passed\n", err.getvalue())
        err = io.StringIO()
        with mock.patch.object(sys, "stderr", err):
            RunLog().gate("build-commit", "passed", "on the remote")
        self.assertEqual("", err.getvalue())


if __name__ == "__main__":
    unittest.main()
