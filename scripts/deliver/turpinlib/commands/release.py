"""`turpin release [--expect VERSION] [--commit REF] [--emergency REASON] [--skip-rehearsal
REASON] [--set-aside GATE REASON] [--check]`: release the commit rehearsal runs (design §2, §6,
§9, §10).

The gates, in order (§9): the commit rehearsal ran and passed (`rehearsal-passed`), on
`origin/main` (`on-main`) or, with `--emergency`, cut from the release production runs
(`emergency-descent`), CI green (`ci-passed`), the version new and higher (`version-spent-once`),
then the board model's, called in-process: the tests ticked (`tests-passed`) and the milestone a
shipping list (`milestone`), and the application's `release-check` hook. Then the owner types the
version, or `--expect` gives it. `--check` stops there.

The steps (§10), what cannot be undone last:

1. the release copier copies each image by digest to releases as `VERSION-IMAGE`, then pushes
   `VERSION-record` (`turpin promote`; a copy already there is a no-op, another digest refuses);
2. the annotated tag `vVERSION`, whose message is the record. **This is the pivot**: the version is
   spent. Before it an error stops the run, exit by its type, with nothing spent;
3. after it, each step that fails is an error and the others still run, exit 3, rerun by
   `turpin release`, which resumes: the retrospective issue and the GitHub Release, the bump of
   `main` to the next patch, the next milestone (and the issues an emergency left out moved to it).

The record is made once, at the gates, and kept in the controller's state, so a rerun after a failure
before the tag has the same `made`; a `VERSION-record` in releases is the record when it is for this
commit and these digests.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from .. import board, gates, gitrepo, hooks, hosts, payload, profile, remote, runlog
from ..cli import Args, Context
from ..model import (BusinessError, ComponentKind, Digest, Environment, FormError, ProgrammeError, Reason,
                     ReleaseRecord, Repository, RepositoryKind, Result, Role, TechnicalError, Version)
from ..registry import connect
from ..registry.port import BuildImage
from ..runlog import PASSED, REFUSED, REPORTED, SET_ASIDE, RunLog, expected_gates
from .build import gate_failed, now_utc

USAGE = ("usage: turpin release [--expect VERSION] [--commit REF] [--emergency REASON]\n"
         "                      [--skip-rehearsal REASON] [--set-aside GATE REASON] [--check]\n")
MIN_ARGS = MAX_ARGS = 0
FLAGS = {"--expect": "value", "--commit": "value", "--check": "switch"}
GATE_FLAGS = ("--emergency", "--skip-rehearsal", "--set-aside")

RELEASE_CHECK = "release-check"      # the application's hook that is a gate here


def refused(log: RunLog, gate: str, message: str, **metadata: Any) -> BusinessError:
    """A gate of the release that refuses: the one wording is `gates.refuse`'s."""
    return gates.refuse(log, gate, Reason.RELEASE_GATE_REFUSED, message, **metadata)


def first_environment(prof, role: Role) -> Environment:
    found = next((env for env in prof.environments.values() if env.role is role), None)
    if found is None:
        raise BusinessError.make(Reason.ENVIRONMENT_UNKNOWN, f"the profile has no {role.value}-role environment",
                                 metadata={"role": role.value})
    return found


def production_version(prof, log: RunLog, read_health: bool) -> Version | None:
    """The version of the release production runs (design §9, *Which release production runs*):
    its record in the host's state, else, where the host has no `current` at all (a production
    deployed before the tool), what `/health` reports, but only where `read_health` (the emergency
    gate; the carried range does not read it). A `current` with no record, or a health that cannot
    be read, is None."""
    env = first_environment(prof, Role.PRODUCTION)
    status = hosts.host_status(env.machine, prof.application, env.name, log=log)
    current = status.deployed.current
    if current is not None:
        return current.record.version if current.record is not None else None
    if not (read_health and env.url and prof.deployed_path and prof.deployed_field):
        return None
    log.event("health-read", env=env.name)
    done = subprocess.run(["curl", "-fsS", "--max-time", "30", env.url.rstrip("/") + prof.deployed_path],
                          capture_output=True, text=True, stdin=subprocess.DEVNULL)
    try:
        text = str(json.loads(done.stdout)[prof.deployed_field])
        return Version.parse(text.split("+", 1)[0])
    except (ValueError, KeyError, TypeError, FormError):
        return None


@dataclass
class Plan:
    """What the gates found, for the record and the steps."""
    sha: str = ""
    version: Version | None = None
    images: dict[str, Digest] = field(default_factory=dict)
    rehearsal_env: str = ""
    rehearsal: dict[str, Any] = field(default_factory=dict)
    prev: str | None = None            # the tag the GitHub notes start from
    carry_from: str | None = None
    range: str = ""
    main_range: str = ""
    carries: dict[str, Any] = field(default_factory=lambda: {"work_packages": [], "issues": [], "releases": []})
    left_out: list[int] = field(default_factory=list)
    set_aside: list[dict[str, str]] = field(default_factory=list)
    resuming: ReleaseRecord | None = None    # the record of the tag that exists
    old_record: ReleaseRecord | None = None  # a `VERSION-record` a failed run left in releases
    record: ReleaseRecord | None = None


class Release:
    def __init__(self, args: Args, ctx: Context, repo: Path, prof):
        self.args, self.ctx, self.log, self.repo, self.prof = args, ctx, ctx.log, repo, prof
        self.prefixes = (prof.tag_prefix, *prof.history_prefixes)
        self.emergency = args.reasons.get("--emergency")
        self.skip = args.reasons.get("--skip-rehearsal")
        self.plan = Plan()
        self.port = connect.connect(prof.application, connect.component_of(ComponentKind.CONTROLLER, prof.login),
                                    self.log)
        self.candidates = Repository(RepositoryKind.CANDIDATES, prof.candidates)
        self.releases = Repository(RepositoryKind.RELEASES, prof.releases)
        self.cprof = None     # the commit's profile: its keys give the gates theirs

    def commit_version(self, sha: str) -> Version:
        """The version the commit's version file holds."""
        text = profile.version_in_commit(self.repo, sha)
        if not text:
            raise BusinessError.make(Reason.VERSION_FILE_UNREADABLE,
                                     f"cannot read the version file at {sha[:12]}: fix versions.app or the commit")
        return Version.parse(text)

    # --------------------------------------------------------------- the gates

    def fetch(self) -> None:
        try:
            gitrepo.fetch_tags(self.repo)
        except TechnicalError as exc:
            self.log.event("fetch-failed", reason=exc.result.reason)    # a stale view decides at the gates

    def commit(self) -> None:
        """The commit: what rehearsal runs, unless `--commit` names one."""
        prof, plan = self.prof, self.plan
        env = first_environment(prof, Role.REHEARSAL)
        plan.rehearsal_env = env.name
        self.status = hosts.host_status(env.machine, prof.application, env.name, log=self.log)
        named = self.args.values.get("--commit")
        if named:
            try:
                plan.sha = gitrepo.git(self.repo, "rev-parse", "--verify", "-q", f"{named}^{{commit}}").strip()
            except TechnicalError:
                plan.sha = ""
            if not plan.sha:
                raise BusinessError.make(Reason.RELEASE_COMMIT_UNKNOWN, f"--commit {named} is not a commit",
                                         metadata={"ref": named})
        elif self.status.deployed.current is not None:
            plan.sha = self.status.deployed.current.build.commit
        else:
            raise refused(self.log, "rehearsal-passed",
                          f"{env.name} has never deployed: nothing to release (name a commit with --commit and "
                          f"--skip-rehearsal REASON)")
        try:
            gitrepo.git(self.repo, "cat-file", "-e", f"{plan.sha}^{{commit}}")
        except TechnicalError as exc:
            raise BusinessError.wrap(exc, Reason.RELEASE_COMMIT_UNKNOWN,
                                     f"commit {plan.sha[:12]} is not in this repository: fetch it") from exc
        self.cprof = profile.read_at_commit(self.repo, plan.sha)
        plan.version = self.commit_version(plan.sha)
        self.tag = f"{prof.tag_prefix}{plan.version}"

    def candidate_digests(self) -> None:
        plan = self.plan
        for name in self.cprof.images:
            try:
                found = self.port.find_image(self.candidates, BuildImage(plan.sha, name))
            except ProgrammeError as exc:
                raise gate_failed(self.log, "store-query", exc) from exc
            if found is None:
                raise refused(self.log, "build-exists", f"no build in candidates for {plan.sha[:12]} "
                              f"(missing {name}): run turpin build", image=name)
            plan.images[name] = found.digest

    def rehearsal_passed(self) -> None:
        plan, deployed = self.plan, self.status.deployed
        current = deployed.current
        if self.skip:
            self.log.gate("rehearsal-passed", PASSED, f"skipped: {self.skip}")
        elif self.tag_carries_this_release():
            # a rerun that resumes: the tag's record is the proof, as the board gates take it too
            self.log.gate("rehearsal-passed", PASSED, f"resuming {self.tag}: its record says rehearsal ran")
        else:
            ok = (deployed.state == "finished" and current is not None and current.build.commit == plan.sha
                  and dict(current.build.images) == plan.images and bool(current.deployed))
            if not ok:
                runs = current.build.commit[:12] if current is not None else "nothing"
                raise refused(self.log, "rehearsal-passed",
                              f"{plan.rehearsal_env} does not show this commit deployed, finished, with its smoke "
                              f"test passed (state {deployed.state or 'none'}, runs {runs})")
            self.log.gate("rehearsal-passed", PASSED, f"{plan.rehearsal_env} ran {plan.sha[:12]}")
        same = current is not None and current.build.commit == plan.sha
        plan.rehearsal = {"environment": plan.rehearsal_env,
                          "deployed": current.deployed if same else None,
                          "smoke": "passed" if same and current.deployed else None}

    def tag_carries_this_release(self) -> bool:
        """Whether the release tag exists here with a record of this commit and these digests: a
        rerun resumes it (`version_spent_once` reads the same record and decides)."""
        plan = self.plan
        if not gitrepo.git(self.repo, "tag", "--list", self.tag).strip():
            return False
        try:
            existing = gitrepo.record_of_tag(self.repo, self.tag)
        except BusinessError:
            return False
        return existing is not None and existing.commit == plan.sha and dict(existing.images) == plan.images

    def history(self) -> None:
        """On `main`, or an emergency cut from the release production runs; and the range."""
        plan, prof, log = self.plan, self.prof, self.log
        tags = gitrepo.release_tags(self.repo, self.prefixes)
        plan.prev = gitrepo.nearest_release_tag(self.repo, plan.sha, self.prefixes, below=plan.version)
        plan.range = f"{plan.prev}..{plan.sha}" if plan.prev else plan.sha
        plan.main_range = f"{plan.prev}..origin/main" if plan.prev else "origin/main"
        if not self.emergency:
            if not gitrepo.is_ancestor(self.repo, plan.sha, "origin/main"):
                raise refused(log, "on-main", f"{plan.sha[:12]} is not on origin/main (a commit off main needs "
                              f"--emergency REASON)")
            log.gate("on-main", PASSED, "on origin/main")
            log.gate("emergency-descent", PASSED, "not an emergency")
            # the carried range starts at the release production runs, so a record lists everything
            # production gains with it; the GitHub notes keep `prev`
            if self.tag not in tags and tags:
                running = production_version(prof, log, read_health=False)
                if running is None:
                    raise refused(log, "milestone", "cannot tell which release production runs: the carried range "
                                  "starts there")
                start = gitrepo.tag_for_version(self.repo, prof, str(running))
                if start is None:
                    raise refused(log, "milestone", f"no tag for production's release {running}: the carried "
                                  f"range starts there")
                plan.carry_from, plan.range, plan.main_range = start, f"{start}..{plan.sha}", f"{start}..origin/main"
            return
        running = production_version(prof, log, read_health=True)
        if running is None:
            raise refused(log, "emergency-descent", "cannot tell which release production runs")
        start = gitrepo.tag_for_version(self.repo, prof, str(running))
        if start is None:
            raise refused(log, "emergency-descent", f"no tag for production's release {running}")
        if not gitrepo.is_ancestor(self.repo, f"{start}^{{commit}}", plan.sha):
            raise refused(log, "emergency-descent", f"{plan.sha[:12]} does not descend from {start}, the release "
                          f"production runs")
        both = (gitrepo.commits_between(self.repo, start, plan.sha)
                & gitrepo.commits_between(self.repo, start, "origin/main"))
        if both:
            raise refused(log, "emergency-descent", f"{len(both)} commit(s) after {start} are on main: an emergency "
                          f"ships nothing unreleased")
        log.gate("on-main", PASSED, "emergency: not required")
        log.gate("emergency-descent", PASSED, f"cut from {start}")
        plan.carry_from = plan.prev = start
        plan.range, plan.main_range = f"{start}..{plan.sha}", f"{start}..origin/main"

    def ci_passed(self) -> None:
        required = list(self.cprof.required_checks)
        with board.working(self.repo, "the CI checks", self.log,
                           "interrupted before the release began: nothing was changed") as model:
            ok, _, bad = model.checks(self.plan.sha, required)
        if not ok:
            raise refused(self.log, "ci-passed", "; ".join(bad))
        self.log.gate("ci-passed", PASSED, " ".join(required) or "no checks required")

    def version_spent_once(self) -> None:
        plan, log = self.plan, self.log
        if not gitrepo.git(self.repo, "tag", "--list", self.tag).strip():
            try:
                old = self.port.read_record(self.releases, plan.version)
            except ProgrammeError as exc:
                raise gate_failed(log, "version-spent-once", exc) from exc
            if old is not None:
                # a record a failed run left is reused when it is this release's
                if old.commit != plan.sha or dict(old.images) != plan.images:
                    raise refused(log, "version-spent-once", f"releases holds a {plan.version}-record for another "
                                  f"commit or other digests")
                plan.old_record = old
            newest = gitrepo.newest_release_tag_version(self.repo, self.prefixes)
            if newest is not None and not plan.version > newest:
                raise refused(log, "version-spent-once", f"version {plan.version} is not higher than the newest "
                              f"release tag {newest}")
            log.gate("version-spent-once", PASSED,
                     f"{plan.version} is new and higher" + (f" than {newest}" if newest else ""))
            return
        try:
            existing = gitrepo.record_of_tag(self.repo, self.tag)
        except BusinessError as exc:       # a record version this tool does not know
            log.gate("version-spent-once", REFUSED, exc.result.message)
            raise
        if existing is None:
            raise refused(log, "version-spent-once", f"tag {self.tag} exists without a record this tool can read")
        if existing.commit != plan.sha or dict(existing.images) != plan.images:
            raise refused(log, "version-spent-once", f"tag {self.tag} holds a different record (commit "
                          f"{existing.commit[:12]}): refusing to resume")
        plan.resuming = existing
        log.gate("version-spent-once", PASSED, f"resuming {self.tag}")

    def overridable(self, gate: str) -> str | None:
        """The reason `--set-aside` gave for `gate`, where the commit's profile allows it; the
        gate is then logged as set aside and recorded. None where it was not asked for or is
        not allowed."""
        for name, reason in self.args.set_aside:
            if name == gate:
                if gate not in self.cprof.overridable:
                    return None
                self.log.gate(gate, SET_ASIDE, reason)
                self.plan.set_aside.append({"gate": gate, "reason": reason})
                return reason
        return None

    def asked_to_set_aside(self, gate: str) -> bool:
        return any(name == gate for name, _ in self.args.set_aside)

    def shipping(self) -> None:
        """The tests and the milestone: the board model's gates, called in-process."""
        plan, log = self.plan, self.log
        if plan.resuming is not None:
            plan.carries = dict(plan.resuming.carries)
            for gate, detail in (("tests-passed", "resuming"), ("milestone", "resuming: carried as recorded"),
                                 ("release-check", "resuming")):
                log.gate(gate, PASSED, detail)
            return
        aside = False
        if self.asked_to_set_aside("milestone"):
            if self.overridable("milestone") is None:
                raise refused(log, "milestone", "the profile does not list milestone in [release].overridable")
            aside = True
        with board.working(self.repo, "the release's milestone gate", log,
                           "interrupted before the release began: nothing was changed") as model:
            request = model.GateRequest(
                version=str(plan.version), sha=plan.sha, range=plan.range, main_range=plan.main_range,
                carry_from=plan.carry_from, prefixes=tuple(p for p in self.prefixes if p),
                emergency=bool(self.emergency), milestone_set_aside=aside)
            result = model.gate(request)
        for verdict in result.gates:
            if not verdict.passed:
                raise refused(log, verdict.name, verdict.message)
            if verdict.name == "milestone" and aside:
                continue          # recorded when it was set aside
            if verdict.reported:
                log.gate(verdict.name, REPORTED, verdict.message)
                print(f"check {verdict.name}: {verdict.message}")
            else:
                log.gate(verdict.name, PASSED, verdict.message)
        for note in result.notes:
            print(f"note: {note}")
        plan.carries, plan.left_out = result.carries, list(result.left_out)

    def release_check(self) -> None:
        """The application's `release-check` hook, from the commit, on the controller: a gate that
        `--set-aside` passes on where the profile lists it."""
        plan, log = self.plan, self.log
        if plan.resuming is not None:
            return
        with tempfile.TemporaryDirectory(prefix="turpin-hooks-") as scratch:
            gitrepo.export_paths(self.repo, plan.sha, ["turpin/hooks"], Path(scratch))
            folder = Path(scratch) / "turpin" / "hooks"
            try:
                path = hooks.find_hook(folder, RELEASE_CHECK, required=RELEASE_CHECK in self.cprof.required_hooks)
            except BusinessError as exc:
                raise refused(log, RELEASE_CHECK, exc.result.message) from exc
            if path is None:
                log.gate(RELEASE_CHECK, PASSED, "no hook")
                return
            state = runlog.state_folder(self.prof.application)
            env = hooks.HookEnv(app=self.prof.application, env="release", role="controller", sha=plan.sha,
                                version=str(plan.version), state=str(state),
                                images={k: str(v) for k, v in plan.images.items()})
            done = hooks.run_hook(path, env, cwd=self.repo)
        if done.passed:
            log.gate(RELEASE_CHECK, PASSED, "")
            return
        if done.code < 0 or done.code > 128:
            done.require()      # killed by a signal: unexpected
        if self.overridable(RELEASE_CHECK) is not None:
            return
        if self.asked_to_set_aside(RELEASE_CHECK):
            raise refused(log, RELEASE_CHECK, f"hook {RELEASE_CHECK} refused (exit {done.code}) and the profile does not list "
                          f"it in overridable")
        raise refused(log, RELEASE_CHECK, f"hook {RELEASE_CHECK} refused (exit {done.code})")

    # ------------------------------------------------------------ the record

    def make_record(self) -> ReleaseRecord:
        plan, app = self.plan, self.prof.application
        if plan.resuming is not None:
            return plan.resuming
        if plan.old_record is not None:         # a record already pushed is the record
            return plan.old_record
        made = now_utc()
        saved = runlog.state_folder(app) / f"release-{plan.version}.json"
        try:
            kept = json.loads(saved.read_text())
            if kept.get("commit") == plan.sha:
                made = kept["made"]
        except (OSError, ValueError, KeyError, AttributeError):
            pass
        programme = payload.pinned_programme(self.repo, plan.sha)
        if programme is None:
            try:
                programme = gitrepo.git(payload.TOOL, "rev-parse", "HEAD").strip()
            except TechnicalError:
                programme = ""
        return ReleaseRecord(
            application=app, version=plan.version, commit=plan.sha, images=plan.images, made=made,
            rehearsal=plan.rehearsal, emergency=self.emergency, rehearsal_skipped=self.skip,
            set_aside=tuple(plan.set_aside), tool={"programme": programme}, carries=plan.carries)

    def show(self, record: ReleaseRecord) -> None:
        print(f"release {record.version} of {record.application}")
        print(f"  commit:   {record.commit}")
        for name, digest in record.images.items():
            print(f"  image:    {name} {digest}")
        rehearsal = record.rehearsal or {}
        print(f"  rehearsal: {rehearsal.get('environment')} deployed {rehearsal.get('deployed') or 'never'}, "
              f"smoke {rehearsal.get('smoke') or 'none'}")
        if self.emergency:
            print(f"  EMERGENCY: {self.emergency}")
        if self.skip:
            print(f"  REHEARSAL SKIPPED: {self.skip}")

    def confirm(self, version: Version) -> None:
        expected = self.args.values.get("--expect")
        if expected is not None:
            if expected != str(version):
                raise BusinessError.make(Reason.RELEASE_NOT_CONFIRMED,
                                         f"--expect {expected} but the release is {version}: nothing was changed")
        else:
            print("type the version to release it: ", end="", file=sys.stderr, flush=True)
            typed = sys.stdin.readline().rstrip("\n")
            if typed != str(version):
                raise BusinessError.make(Reason.RELEASE_NOT_CONFIRMED,
                                         f'confirmation "{typed}" is not {version}: nothing was changed')
        self.log.event("confirmed", version=str(version))

    # ----------------------------------------------------------- the steps

    def step_copy_and_tag(self, record: ReleaseRecord) -> None:
        """Before the pivot: the copier copies the images and pushes `VERSION-record`; then the
        tag, whose push spends the version."""
        prof = self.prof
        text = json.dumps(record.to_json(), separators=(",", ":"))
        state = runlog.state_folder(prof.application)
        try:
            state.mkdir(parents=True, exist_ok=True)
            (state / f"release-{record.version}.json").write_text(text + "\n")
        except OSError:
            pass            # the stable `made` is a convenience
        request = {"login": prof.copy_login.value, "candidates": prof.candidates, "releases": prof.releases,
                   "commit": record.commit, "images": {k: str(v) for k, v in record.images.items()},
                   "version": str(record.version), "record": record.to_json()}
        try:
            remote.call_turpin(prof.copy_on, ["promote", prof.application], log=self.log, request=request,
                               retry=True, where=f"nothing is spent: run {self.rerun()} again")
        except ProgrammeError as exc:       # the same error, saying what a rerun does
            raise type(exc)(replace(exc.result, message=f"{exc.result.message.rstrip('.')}; the release is not "
                                    f"made and nothing is spent: run {self.rerun()} again, which reuses what "
                                    f"was copied")) from exc
        self.log.event("step", name="copy", result="done")
        try:
            gitrepo.push_tag(self.repo, self.tag, record.commit, text)
        except TechnicalError as exc:
            raise TechnicalError.wrap(exc, Reason.RELEASE_TAG_FAILED,
                                      f"cannot push tag {self.tag}: nothing is spent, run {self.rerun()} again",
                                      blip=bool(exc.result.blip)) from exc
        self.log.event("step", name="tag", result="done")

    def after_the_tag(self, record: ReleaseRecord, tagged_now: bool) -> Result:
        """Past the pivot: each step that fails is an error and the others still run (design §6)."""
        failed: list[str] = []
        errors: list[ProgrammeError] = []
        changed = [tagged_now]       # whether this run did anything at all
        interrupted = (f"interrupted after {self.tag} was pushed: the release is made, and {self.rerun()} "
                       f"finishes the steps left")

        def step(name: str, action) -> None:
            try:
                done = action()
            except ProgrammeError as exc:
                failed.append(name)
                errors.append(exc)
                self.log.event("step", name=name, result="failed")
                return
            self.log.event("step", name=name, result="done")
            for left in (done or {}).get("failed") or ():       # the board model names what it could not do
                failed.append(left)
                errors.append(TechnicalError.make(Reason.RELEASE_STEP_FAILED, f"{left} failed", blip=False))
            changed.append(bool(done) and (done.get("created") is True or done.get("release") == "created"
                                           or done.get("retrospective") == "raised"))

        try:
            step("GitHub Release", lambda: self.publish(record))             # 5
            step("bump main", lambda: self.bump(record))                     # 6
            step("next milestone", lambda: self.next_milestone(record))      # 7
        except KeyboardInterrupt as exc:
            raise KeyboardInterrupt(interrupted) from exc
        if failed:
            by_hand = ""
            to_move = [n for n in (f.removeprefix("move ") for f in failed if f.startswith("move #"))]
            if "next milestone" in failed and self.emergency:
                to_move = [f"#{n}" for n in self.plan.left_out]
            if to_move:
                by_hand = (f"; move {' '.join(to_move)} into the next milestone by hand, which "
                           f"{self.rerun()} does not do")
            return remote.done_with_errors(
                Reason.RELEASE_STEPS_FAILED,
                f"{self.tag} is made and pushed, but these steps failed: {', '.join(failed)}; run {self.rerun()} "
                f"again to resume{by_hand}", errors)
        print(f"released {record.version}" if any(changed) else f"every step of {record.version} is already done")
        return Result.ok()

    def publish(self, record: ReleaseRecord) -> dict[str, Any]:
        """Step 5: the retrospective issue where rehearsal was skipped, then the GitHub Release,
        each skipped where it exists."""
        skip = self.skip
        with board.working(self.repo, "the GitHub Release", self.log, "interrupted") as model:
            return model.publish(self.tag, self.plan.prev, skip, str(record.version) if skip else None,
                                 record.commit if skip else None)

    def bump(self, record: ReleaseRecord) -> dict[str, Any]:
        """Step 6: `main` takes the next patch."""
        bumped = gitrepo.bump_main(self.repo, record.version, self.prof.application,
                                   str(runlog.state_folder(self.prof.application)))
        return {"created": bumped}

    def next_milestone(self, record: ReleaseRecord) -> dict[str, Any]:
        """Step 7: the next milestone, and the open issues an emergency left out moved into it."""
        move = list(self.plan.left_out) if self.emergency else []
        with board.working(self.repo, "the next milestone", self.log, "interrupted") as model:
            return model.open_next(str(record.version), move)

    # ------------------------------------------------------------------ run

    def run(self) -> Result:
        self.fetch()
        self.commit()
        self.candidate_digests()
        self.rehearsal_passed()
        self.history()
        self.ci_passed()
        self.version_spent_once()
        self.shipping()
        self.release_check()
        self.log.finish_gates()
        record = self.make_record()
        self.show(record)
        if "--check" in self.args.switches:
            print("check: every release gate passed; nothing changed")
            return Result.ok()
        self.confirm(record.version)
        tagged_now = self.plan.resuming is None
        if tagged_now:
            try:
                self.step_copy_and_tag(record)
            except KeyboardInterrupt as exc:
                raise KeyboardInterrupt(self.interrupted_at_the_tag()) from exc
        else:
            self.ensure_tag_pushed()
        return self.after_the_tag(record, tagged_now)

    def interrupted_at_the_tag(self) -> str:
        """What a Ctrl+C before the steps after the tag says: the version is spent if and only if
        `origin` holds the tag, which is asked of it (the push itself ran to its end)."""
        try:
            spent = gitrepo.origin_has_tag(self.repo, self.tag)
        except (TechnicalError, KeyboardInterrupt):
            return (f"interrupted at the tag: whether {self.tag} reached origin is not known; "
                    f"run {self.rerun()} again, which settles it")
        if spent:
            return (f"interrupted after {self.tag} was pushed: the release is made, and {self.rerun()} "
                    f"finishes the steps left")
        return (f"interrupted before the tag was pushed: the version is not spent, and what was copied "
                f"stays in releases; run {self.rerun()} again")

    def ensure_tag_pushed(self) -> None:
        """A resume: the tag exists here, but a run killed between making it and pushing it leaves
        it only here, and the version is not spent until origin has it. A failure says whether
        origin holds it."""
        try:
            gitrepo.push_existing_tag(self.repo, self.tag)
        except TechnicalError as exc:
            raise TechnicalError.wrap(exc, Reason.RELEASE_TAG_FAILED,
                                      f"cannot push tag {self.tag} ({self.origin_holds_tag()}): "
                                      f"run {self.rerun()} again", blip=bool(exc.result.blip)) from exc
        except KeyboardInterrupt as exc:
            raise KeyboardInterrupt(self.interrupted_at_the_tag()) from exc

    def origin_holds_tag(self) -> str:
        """Whether origin holds the tag, in words, as asked of it."""
        try:
            return ("origin holds it: the release is made" if gitrepo.origin_has_tag(self.repo, self.tag)
                    else "origin does not hold it: nothing is spent")
        except (TechnicalError, KeyboardInterrupt):
            return "whether origin holds it is not known"

    def rerun(self) -> str:
        """The command that resumes this release: the same flags the run was given, so the gates
        pass again (an emergency, a skipped rehearsal, a commit, a set-aside gate)."""
        parts = ["turpin release", f"--expect {self.plan.version}", f"--commit {self.plan.sha}"]
        for flag, reason in self.args.reasons.items():
            parts.append(f"{flag} {shlex.quote(reason)}")
        for gate, reason in self.args.set_aside:
            parts.append(f"--set-aside {gate} {shlex.quote(reason)}")
        return " ".join(parts)


def run(args: Args, ctx: Context) -> Result:
    repo = profile.repo_dir()
    prof = profile.read_working_tree(repo)
    ctx.start_log(prof.application, expected_gates("release"))
    return Release(args, ctx, repo, prof).run()
