"""`turpin build [REF] [--local]`: build a commit's image set once and store it in
candidates (design §2, §3 *Operations*, §8, §9).

On the controller, where the builder is another machine, the command resolves REF to a
commit and passes itself on by `ssh`; on the builder it runs here (`TURPIN_ON_BUILD_HOST=1`,
a timer's, or a call from the controller). It is not retried over `ssh`: the build gate
refuses a commit whose images are already pushed, and the run log on the builder says
whether they were.

Here, in order:

1. gate `build-commit`: REF is a commit on the remote (`--local`: preview only, any commit);
2. gates `store-query` and `store-immutable`: each image of the set already in candidates
   is kept, never rebuilt or pushed over; a registry that cannot be asked refuses;
3. a clean worktree of the commit, its payload, and the `build` hook (or the default one),
   which writes one OCI image layout per image and names each on standard output;
4. gate `build-labels`: each platform image's configuration, attestation manifests passed
   over, carries the labels `build` set, before any push;
5. the registry port stores the layouts, and the digests are printed, one image a line.

`--local` (preview only) has the hook load the images into local Docker instead; nothing is
pushed, and each image is named by its image id.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from .. import gitrepo, hooks, layout, payload, profile, remote, settings
from ..cli import Args, Context
from ..hooks import HookEnv
from ..model import (CONTROLLER, BusinessError, ComponentKind, ProgrammeError, Reason, Repository,
                     RepositoryKind, Result, Role, TechnicalError)
from ..registry import connect
from ..registry.port import BuildImage
from ..runlog import REFUSED, PASSED, RunLog, expected_gates

USAGE = "usage: turpin build [REF] [--local]\n"
MIN_ARGS, MAX_ARGS = 0, 1
FLAGS = {"--local": "switch"}

OCI_DIR = Path(".turpin") / "oci"      # where the default hook writes each image's layout
PAYLOAD_DIR = ".turpin-payload"


def refused(log: RunLog, gate: str, reason: Reason, message: str, **metadata) -> BusinessError:
    """A gate that refuses: logged by name, and the error names it."""
    log.gate(gate, REFUSED, message)
    return BusinessError.make(reason, f"gate {gate} refused: {message}", metadata={"gate": gate, **metadata})


def gate_failed(log: RunLog, gate: str, exc: ProgrammeError) -> ProgrammeError:
    """An error from below that stops a gate: the same error, naming the gate."""
    log.gate(gate, REFUSED, exc.result.reason)
    return type(exc)(replace(exc.result, message=f"gate {gate}: {exc.result.message}"))


def now_utc() -> str:
    """RFC 3339, UTC, to the second."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------- the gates

def fetch_remote(repo: Path, log: RunLog) -> None:
    """Bring in what the remote holds, so that a commit pushed since the last fetch resolves.
    A failed fetch is logged and not fatal: the stale view decides at the gate."""
    try:
        gitrepo.git(repo, "fetch", "-q", "origin")
    except TechnicalError as exc:
        log.event("fetch-failed", reason=exc.result.reason)


def resolve_commit(repo: Path, ref: str, log: RunLog) -> str:
    """The full SHA of REF, or the gate refuses."""
    try:
        found = gitrepo.git(repo, "rev-parse", "--verify", "-q", f"{ref}^{{commit}}").strip()
    except TechnicalError as exc:
        if exc.result.reason != Reason.GIT_FAILED.value:
            raise
        found = ""
    if not found:
        raise refused(log, "build-commit", Reason.BUILD_NOT_A_COMMIT, f"{ref} is not a commit", ref=ref)
    return found


def check_commit_gate(repo: Path, prof, sha: str, local: bool, log: RunLog) -> None:
    """Gate `build-commit`: a commit on the remote, or under `--local` any commit, for the
    preview role only."""
    if local:
        if not any(env.role is Role.PREVIEW for env in prof.environments.values()):
            raise refused(log, "build-commit", Reason.BUILD_LOCAL_NEEDS_PREVIEW,
                          "--local is for the preview role, and the profile has none")
        log.gate("build-commit", PASSED, "local, unpushed (preview only)")
        return
    if not gitrepo.git(repo, "branch", "-r", "--contains", sha).strip():
        raise refused(log, "build-commit", Reason.BUILD_NOT_ON_REMOTE,
                      f"{sha[:12]} is not a commit on the remote: push it first", commit=sha)
    log.gate("build-commit", PASSED, "on the remote")


# ------------------------------------------------------------------ the hook

def _run_docker(tree: Path, argv: list[str]) -> None:
    """One `docker` call in the worktree, in a process group of its own (a Ctrl+C reaches
    `turpin` alone) and run to its end. Its output is ours, standard error."""
    try:
        child = subprocess.Popen(argv, cwd=tree, stdin=subprocess.DEVNULL, stdout=sys.stderr,
                                 start_new_session=True)
    except FileNotFoundError as exc:
        raise TechnicalError.make(Reason.BUILD_HOOK_FAILED, "docker is not installed: install it, "
                                  "or give the application a build hook") from exc
    while True:
        try:
            code = child.wait()
            break
        except KeyboardInterrupt:      # a tool already running runs to its end (design §6)
            continue
    if code != 0:
        raise BusinessError.make(Reason.BUILD_HOOK_FAILED, "docker buildx bake failed",
                                 metadata={"hook": "default", "exit": code})


def build_values(sha: str, version: str, created: str) -> dict[str, str]:
    """The `TURPIN_*` values a build argument may be taken from (`settings.BUILD_ARG_SOURCES`)."""
    return {"SHA": sha, "SHORT_SHA": sha[:settings.SHORT_SHA_LENGTH], "VERSION": version, "CREATED": created}


def default_hook(tree: Path, app: str, sha: str, version: str, created: str, images: list[str],
                 local: bool, build_args: Mapping[str, str] = {}) -> str:
    """The default `build` hook (design §8): one `docker buildx bake` per image, labelled, its
    layout written under `.turpin/oci/IMAGE`, or loaded into local Docker under `--local`.
    Returns what a hook prints: a line per image, its name and its layout's directory."""
    lines = []
    for image in images:
        argv = ["docker", "buildx", "bake", "--builder", "turpin"]
        for key, value in ((layout.REVISION, sha), (layout.VERSION, version), (layout.CREATED, created)):
            argv += ["--set", f"{image}.labels.{key}={value}"]
        values = build_values(sha, version, created)
        for name, source in build_args.items():       # the profile's `[turpin.build].args`
            argv += ["--set", f"{image}.args.{name}={values[source]}"]
        if local:
            argv += ["--load", "--set", f"{image}.tags={local_tag(app, image, sha)}", image]
            lines.append(image)
        else:
            directory = OCI_DIR / image
            argv += ["--set", f"{image}.output=type=oci,dest={directory},tar=false", image]
            lines.append(f"{image} {directory}")
        _run_docker(tree, argv)
    return "\n".join(lines) + "\n"


def tag_variable(image: str) -> str:
    """The variable a `--local` hook is given the tag of an image in."""
    return "TURPIN_BUILD_TAG_" + re.sub(r"[^A-Z0-9]", "_", image.upper())


def local_tag(app: str, image: str, sha: str) -> str:
    """What a `--local` image is tagged in local Docker, which a preview deploy reads."""
    return f"turpin-local/{app}-{image}:{sha}"


def layouts_named(output: str, wanted: list[str], tree: Path, hook: str) -> dict[str, Path]:
    """The layout of each image to build, from the hook's lines (`NAME DIRECTORY`); a line
    for an image not asked for is passed over, and a missing one refuses."""
    found: dict[str, Path] = {}
    for line in output.splitlines():
        words = line.split(None, 1)
        if len(words) == 2 and words[0] in wanted:
            found[words[0]] = (tree / words[1].strip())
    missing = [name for name in wanted if name not in found]
    if missing:
        raise BusinessError.make(Reason.BUILD_NO_LAYOUT,
                                 f"the {hook} build hook named no layout for image {', '.join(missing)}",
                                 metadata={"images": missing})
    return found


def check_labels(log: RunLog, layouts: dict[str, Path], sha: str, version: str, created: str) -> None:
    """Gate `build-labels`: every platform image of every layout carries the labels the build
    set, read from its configuration before anything is pushed."""
    wanted = {layout.REVISION: sha, layout.VERSION: version, layout.CREATED: created}
    for image, directory in layouts.items():
        for digest, labels in layout.platform_labels(directory, image):
            for key, value in wanted.items():
                if labels.get(key) != value:
                    raise refused(log, "build-labels", Reason.BUILD_LABELS_DIFFER,
                                  f"image {image} does not carry {key}={value} on {digest[:19]}: nothing was pushed",
                                  image=image, label=key)
    log.gate("build-labels", PASSED, "every platform image carries the labels the build set")


# ------------------------------------------------------------------- the build

def build_here(args: Args, ctx: Context, repo: Path, prof, sha: str, local: bool) -> Result:
    log = ctx.log
    watcher = remote.Watcher()
    commit_profile = profile.read_at_commit(repo, sha)
    images = list(commit_profile.images)
    candidates = Repository(RepositoryKind.CANDIDATES, prof.candidates)
    port = None
    have: dict[str, str] = {}
    if not local:
        port = connect.connect(prof.application, connect.component_of(ComponentKind.BUILDER, prof.build_login), log)
        for image in images:       # what is stored is never rebuilt; a registry that cannot be asked refuses
            try:
                found = port.find_image(candidates, BuildImage(sha, image))
            except ProgrammeError as exc:
                raise gate_failed(log, "store-query", exc) from exc
            if found is not None:
                have[image] = str(found.digest)
    log.gate("store-query", PASSED, "answered")
    tobuild = [image for image in images if image not in have]
    log.gate("store-immutable", PASSED, f"{len(have)} present and kept, {len(tobuild)} to build")
    stored: dict[str, str] = {}
    if tobuild:
        watcher.check("interrupted before the build began: nothing was built or pushed; "
                      f"run turpin build {sha[:12]} again")
        stored = _build(ctx, repo, prof, port, candidates, commit_profile, sha, tobuild, local, watcher)
    elif not local:
        log.gate("build-labels", PASSED, "nothing built")
    for image in images:
        print(f"{image} {have.get(image) or stored[image]}")
    return Result.ok()


def _build(ctx: Context, repo: Path, prof, port, candidates, commit_profile, sha: str, tobuild: list[str],
           local: bool, watcher: remote.Watcher) -> dict[str, str]:
    log = ctx.log
    tree = Path(tempfile.mkdtemp(prefix="turpin-build-"))
    try:
        try:
            gitrepo.git(repo, "worktree", "add", "-q", "--detach", str(tree), sha)
        except TechnicalError as exc:
            raise BusinessError.wrap(exc, Reason.BUILD_WORKTREE_FAILED,
                                     f"cannot make a clean worktree of {sha[:12]}: fix the repository") from exc
        version = str(profile.version_in_tree(tree))
        created = now_utc()
        payload_dir = tree / PAYLOAD_DIR
        payload.assemble(repo, tree, sha, payload_dir)
        extra = {"TURPIN_PAYLOAD_DIR": str(payload_dir), "TURPIN_BUILD_IMAGES": " ".join(tobuild),
                 "TURPIN_SHORT_SHA": sha[:settings.SHORT_SHA_LENGTH]}
        if local:       # where a local build must tag each image, for a preview deploy to find it
            extra.update({tag_variable(image): local_tag(prof.application, image, sha) for image in tobuild})
        hook_env = HookEnv(app=prof.application, env="", role="builder", sha=sha, version=version,
                           state=str(tree), created=created, local=local, extra=extra)
        log.event("build-start", sha=sha, images=" ".join(tobuild), version=version)
        hook = hooks.find_hook(tree / "turpin" / "hooks", "build")
        if hook is not None:
            result = hooks.run_hook(hook, hook_env, cwd=tree)
            result.require()
            output = result.output
        else:
            output = default_hook(tree, prof.application, sha, version, created, tobuild, local,
                                  commit_profile.build_args)
        if local:
            return _local_ids(prof.application, sha, tobuild, output, log)
        layouts = layouts_named(output, tobuild, tree, "build")
        check_labels(log, layouts, sha, version, created)
        watcher.check("interrupted before anything was pushed: nothing was stored; "
                      f"run turpin build {sha[:12]} again")
        stored = port.store_build(candidates, sha, layouts)
        return {name: str(digest) for name, digest in stored.images.items()}
    finally:
        try:
            gitrepo.git(repo, "worktree", "remove", "--force", str(tree))
        except ProgrammeError:
            pass
        shutil.rmtree(tree, ignore_errors=True)


def _local_ids(app: str, sha: str, images: list[str], output: str, log: RunLog) -> dict[str, str]:
    """Each local image, by its image id: `RepoDigests` is empty where nothing was pushed.
    The hook names each image it built (the first word of a line); one it did not name has
    no local image."""
    named = {words[0] for words in (line.split() for line in output.splitlines()) if words}
    ids = {}
    for image in images:
        if image not in named:
            raise BusinessError.make(Reason.BUILD_NO_LOCAL_IMAGE,
                                     f"the build hook did not name image {image}: it must print the name of "
                                     f"each image it loaded", metadata={"image": image})
        done = subprocess.run(["docker", "image", "inspect", local_tag(app, image, sha), "--format", "{{.Id}}"],
                              capture_output=True, text=True, stdin=subprocess.DEVNULL)
        if done.returncode != 0 or not done.stdout.strip():
            raise BusinessError.make(Reason.BUILD_NO_LOCAL_IMAGE,
                                     f"the build left no local image {image}: the hook must tag it "
                                     f"{local_tag(app, image, sha)}", metadata={"image": image})
        ids[image] = done.stdout.strip()
    log.gate("build-labels", PASSED, "local build, labels not read")
    return ids


def pass_on(machine: str, sha: str, local: bool, ctx: Context) -> Result:
    """Run the same command on the builder; its output and exit status come back."""
    argv = ["build", sha] + (["--local"] if local else [])
    where = (f"the run log on {machine} says whether the images were pushed: "
             f"read it before running turpin build {sha[:12]} again")
    remote.call_turpin(machine, argv, log=ctx.log, retry=False, where=where,
                       extra={settings.ENV_ON_BUILD_HOST: "1"})
    return Result.ok()


def run(args: Args, ctx: Context) -> Result:
    repo = profile.repo_dir()
    prof = profile.read_working_tree(repo)
    local = "--local" in args.switches
    on_builder = (remote.called() or bool(os.environ.get(settings.ENV_ON_BUILD_HOST))
                  or prof.build_on == CONTROLLER)
    ctx.start_log(prof.application, expected_gates("build") if on_builder else ())
    if not local:
        fetch_remote(repo, ctx.log)
    sha = resolve_commit(repo, args.positional[0] if args.positional else "HEAD", ctx.log)
    check_commit_gate(repo, prof, sha, local, ctx.log)
    if not on_builder:
        return pass_on(prof.build_on, sha, local, ctx)
    return build_here(args, ctx, repo, prof, sha, local)
