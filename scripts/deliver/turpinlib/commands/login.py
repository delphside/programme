"""`turpin login COMPONENT`: the owner's one `docker-config` login for a component (design §3
*Logins*, §6).

COMPONENT is `controller`, `builder`, `copier`, or an environment (its deployer). The user is
asked for, and the token read at a hidden prompt, then passed on by standard input only: it
is never printed, logged or an argument.

- `controller` and `copier` run `skopeo login --authfile` for the component's file;
- `builder` does that for its file, and also `docker login` for the machine user where an
  environment on its machine pulls with that login (the one shared login);
- a builder or copier on another machine is reached by `turpin login` passed on by `ssh`,
  where it reads the user and token as data, closed by the closing line, and runs here;
- an environment runs `turpin-host login`, a `docker login` for its machine user, except
  one on the builder's machine, which refuses and names `turpin login builder`.
"""

from __future__ import annotations

import getpass
import os
import subprocess
import sys
from dataclasses import replace

from .. import hosts, profile, remote, settings
from ..cli import Args, Context
from ..model import (CONTROLLER, BusinessError, ComponentKind, CredentialKind, ProgrammeError, Reason,
                     Result, TechnicalError)
from ..registry import connect

USAGE = "usage: turpin login COMPONENT      (controller, builder, copier, or an environment)\n"
MIN_ARGS = MAX_ARGS = 1
FLAGS: dict[str, str] = {}

COMPONENTS = {"controller": ComponentKind.CONTROLLER, "builder": ComponentKind.BUILDER,
              "copier": ComponentKind.COPIER}
NEW_TOKEN = " (a new auth token can take a few minutes to start working)"


def ask(component: str) -> tuple[str, str]:
    """The user and the token: at a terminal the token is hidden, and from a pipe both are
    the first two lines."""
    if sys.stdin.isatty():
        print(f"registry user for the {component}: ", end="", file=sys.stderr, flush=True)
        user = sys.stdin.readline().strip()
        token = getpass.getpass("token (hidden): ")
        return user, token
    print(f"registry user for the {component}: ", end="", file=sys.stderr, flush=True)
    user = sys.stdin.readline().rstrip("\n")
    print("token (hidden): ", file=sys.stderr)
    return user, sys.stdin.readline().rstrip("\n")


def login_kind(prof, kind: ComponentKind) -> CredentialKind:
    return {ComponentKind.CONTROLLER: prof.login, ComponentKind.BUILDER: prof.build_login,
            ComponentKind.COPIER: prof.copy_login}[kind]


def place_of(prof, kind: ComponentKind) -> str:
    """The machine a component runs on."""
    return {ComponentKind.CONTROLLER: CONTROLLER, ComponentKind.BUILDER: prof.build_on,
            ComponentKind.COPIER: prof.copy_on}[kind]


def with_advice(exc: ProgrammeError) -> ProgrammeError:
    """A fundamental error from a login says that a new auth token can take a few minutes to
    start working (design §3, step 4)."""
    if isinstance(exc, TechnicalError) and not exc.result.blip:
        return type(exc)(replace(exc.result, message=exc.result.message.rstrip(".") + NEW_TOKEN))
    return exc


def docker_login(app: str, user: str, token: str) -> None:
    """`docker login` for the machine user, the token on standard input only."""
    registry = profile.require(profile.read_app_env(app), settings.ENV_REGISTRY, f"{app}.env")
    host = registry.partition("/")[0]
    try:
        done = subprocess.run(["docker", "login", "-u", user, "--password-stdin", host], input=token,
                              capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise TechnicalError.make(Reason.LOGIN_TOOL_MISSING, "docker is not installed on this machine: "
                                  "install it") from exc
    if done.returncode != 0:
        text = done.stderr.replace(token, "<token>").replace(registry, "<registry>").replace(host, "<registry>")
        raise with_advice(TechnicalError.make(
            Reason.LOGIN_DOCKER_FAILED, "docker login was refused: check the user and the token",
            metadata={"tool_text": text.strip()[:settings.ERROR_TEXT_MAX]}))


def login_here(app: str, prof, kind: ComponentKind, user: str, token: str, ctx: Context) -> None:
    """The login of a component whose machine is this one."""
    component = connect.component_of(kind, login_kind(prof, kind))
    port = connect.connect(app, component, ctx.log, bind=False)
    try:
        port.make_login(component, user, token)
    except ProgrammeError as exc:
        raise with_advice(exc) from exc
    if kind is ComponentKind.BUILDER and any(env.machine == prof.build_on for env in prof.environments.values()):
        docker_login(app, user, token)      # an environment on this machine pulls with it


def run(args: Args, ctx: Context) -> Result:
    repo = profile.repo_dir()
    prof = profile.read_working_tree(repo)
    app = prof.application
    ctx.start_log(app)
    name = args.positional[0]
    environment = None
    kind = COMPONENTS.get(name)
    if kind is None:
        environment = prof.environments.get(name)
        if environment is None:
            raise BusinessError.make(Reason.LOGIN_UNKNOWN_COMPONENT,
                                     f"{name} is not controller, builder, copier or an environment of the "
                                     f"profile", metadata={"component": name})
        if profile.login_component(prof, environment) == "builder":
            raise BusinessError.make(Reason.LOGIN_SHARED_WITH_BUILDER,
                                     f"{name} shares the builder's docker login on this machine: "
                                     f"run turpin login builder", metadata={"component": name})
    if remote.called():
        user, token = (remote.read_data() + ["", ""])[:2]
    else:
        user, token = ask(name)
    if not user or not token:
        raise BusinessError.make(Reason.LOGIN_INCOMPLETE, "login needs a user and a token")
    ctx.log.event("login", component=name)
    data = f"{user}\n{token}\n"
    if environment is not None:
        hosts.call_host(environment.machine, ["login", app, "deployer", name], log=ctx.log, data=data,
                        retry=True, timeout=settings.LOGIN_CALL_TIMEOUT, echo_stdout=True,
                        where=f"run turpin login {name} again")
        return Result.ok()
    place = place_of(prof, kind)
    here = (remote.called() or place == CONTROLLER
            or (kind is ComponentKind.BUILDER and bool(os.environ.get(settings.ENV_ON_BUILD_HOST))))
    if here:
        login_here(app, prof, kind, user, token, ctx)
        print(f"logged in: {name}")
    else:
        remote.call_turpin(place, ["login", name], log=ctx.log, data=data, retry=True,
                           timeout=settings.LOGIN_CALL_TIMEOUT, where=f"run turpin login {name} again")
    return Result.ok()
