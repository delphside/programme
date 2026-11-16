"""The domain model, `Result` and the errors (design §2 *Domain model*, §6).

Every type checks its own form where the value is made (R48): a value that
fails raises a `FormError`, which an argument's or the version file's reader turns
into a business error (`read_input`) and anything else leaves as an unexpected one.
`Result` is docs/1.10's result object; a failure is raised as a
`ProgrammeError` carrying one, and `exit_status` is the one place a result
becomes an exit status.
"""

from __future__ import annotations

import enum
import re
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Callable, Mapping, TypeVar

T = TypeVar("T")

# --------------------------------------------------------------- exit statuses
# docs/1.10 *What a script's exit status means*; design §6 for Turpin's own.

EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_FUNDAMENTAL = 2
EXIT_ERRORS = 3
EXIT_USAGE = 64
EXIT_UNEXPECTED = 70
EXIT_BLIP = 75
EXIT_INTERRUPTED = 130


# --------------------------------------------------------------------- results

class Outcome(enum.Enum):
    """A result's severity (docs/1.10 *The severity of an error*)."""
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"
    FATAL = "fatal"


class ErrorType(enum.Enum):
    """Whose problem an error is (docs/1.10 *The type of an error*)."""
    BUSINESS = "business"
    TECHNICAL = "technical"
    UNEXPECTED = "unexpected"


DOMAIN = "turpin"


@enum.unique
class Reason(enum.Enum):
    """Every reason of domain `turpin`: unique, never reused (docs/1.10). Another
    component adds its members here. A vendor's own domain (design §3) gets an
    enumeration of its own, in the adapter that names the vendor."""
    # a value's form (R48)
    BAD_VALUE = "BAD_VALUE"
    # the profile and the settings files (§8)
    PROFILE_KEY_MISSING = "PROFILE_KEY_MISSING"
    PROFILE_KEY_MALFORMED = "PROFILE_KEY_MALFORMED"
    PROFILE_UNREADABLE = "PROFILE_UNREADABLE"
    SETTINGS_LINE_UNPARSABLE = "SETTINGS_LINE_UNPARSABLE"
    NOT_IN_REPOSITORY = "NOT_IN_REPOSITORY"
    # git
    GIT_FAILED = "GIT_FAILED"
    GIT_UNREACHABLE = "GIT_UNREACHABLE"
    GIT_REFUSED = "GIT_REFUSED"
    TAG_NOT_FOUND = "TAG_NOT_FOUND"
    RECORD_VERSION_UNKNOWN = "RECORD_VERSION_UNKNOWN"
    RECORD_MALFORMED = "RECORD_MALFORMED"
    # hooks (§8)
    HOOK_MISSING = "HOOK_MISSING"
    HOOK_NOT_EXECUTABLE = "HOOK_NOT_EXECUTABLE"
    HOOK_REFUSED = "HOOK_REFUSED"
    HOOK_NOT_YET = "HOOK_NOT_YET"
    HOOK_TIMED_OUT = "HOOK_TIMED_OUT"
    HOOK_KILLED = "HOOK_KILLED"
    # the run (§6)
    GATES_UNRUN = "GATES_UNRUN"
    UNEXPECTED_EXCEPTION = "UNEXPECTED_EXCEPTION"
    # the registry (§3): its port and every adapter
    REQUEST_INVALID = "REQUEST_INVALID"
    SHORT_SHA_NO_BUILD = "SHORT_SHA_NO_BUILD"
    SHORT_SHA_AMBIGUOUS = "SHORT_SHA_AMBIGUOUS"
    KEEP_LIST = "KEEP_LIST"
    NO_OVERWRITE = "NO_OVERWRITE"
    IMAGE_NOT_FOUND = "IMAGE_NOT_FOUND"
    REGISTRY_LOGIN_MISSING = "REGISTRY_LOGIN_MISSING"
    REGISTRY_REFUSED = "REGISTRY_REFUSED"
    REGISTRY_UNREACHABLE = "REGISTRY_UNREACHABLE"
    REGISTRY_TOOL_MISSING = "REGISTRY_TOOL_MISSING"
    REMOVAL_CREDENTIAL_MISSING = "REMOVAL_CREDENTIAL_MISSING"
    REMOVAL_NOT_AUTHORIZED = "REMOVAL_NOT_AUTHORIZED"
    REGISTRY_REPLY_INVALID = "REGISTRY_REPLY_INVALID"
    REGISTRY_OUTPUT_INVALID = "REGISTRY_OUTPUT_INVALID"
    REGISTRY_CALL_UNEXPECTED = "REGISTRY_CALL_UNEXPECTED"
    REGISTRY_DIGEST_CHANGED = "REGISTRY_DIGEST_CHANGED"
    REGISTRY_NOT_BOUND = "REGISTRY_NOT_BOUND"
    # a call to a host (§6 *Interruption*): `ssh`'s 255 mapped by its error text
    SSH_PERMISSION_DENIED = "SSH_PERMISSION_DENIED"
    SSH_HOST_KEY_REFUSED = "SSH_HOST_KEY_REFUSED"
    SSH_HOST_UNRESOLVED = "SSH_HOST_UNRESOLVED"
    SSH_CONNECTION_LOST = "SSH_CONNECTION_LOST"
    SSH_UNEXPECTED = "SSH_UNEXPECTED"
    HOST_CALL_TIMED_OUT = "HOST_CALL_TIMED_OUT"
    HOST_COMMAND_MISSING = "HOST_COMMAND_MISSING"
    HOST_STATUS_UNREADABLE = "HOST_STATUS_UNREADABLE"
    ENVIRONMENT_UNKNOWN = "ENVIRONMENT_UNKNOWN"
    INTERRUPTED_AFTER_ROLLBACK_BEGAN = "INTERRUPTED_AFTER_ROLLBACK_BEGAN"
    # what `turpin-host` stops for (§11), named in its result objects; the Bash files
    # `turpin-host`, `lib/common.sh` and `payload/` use exactly these (a test holds them to it)
    HOST_STATUS = "HOST_STATUS"
    HOST_REFUSED = "HOST_REFUSED"
    HOST_GATE_REFUSED = "HOST_GATE_REFUSED"
    HOST_FUNDAMENTAL = "HOST_FUNDAMENTAL"
    HOST_BLIP = "HOST_BLIP"
    HOST_UNEXPECTED = "HOST_UNEXPECTED"
    HOST_LOCK_HELD = "HOST_LOCK_HELD"
    HOST_LOCK_WAIT_LIMIT = "HOST_LOCK_WAIT_LIMIT"
    HOST_STATE_REFUSED = "HOST_STATE_REFUSED"
    HOST_DIGEST_REFUSED = "HOST_DIGEST_REFUSED"
    HOST_PULL_TIMED_OUT = "HOST_PULL_TIMED_OUT"
    HOST_PAYLOAD_UNREADABLE = "HOST_PAYLOAD_UNREADABLE"
    HOST_STEP_FAILED = "HOST_STEP_FAILED"
    HOST_RESTORE_FAILED = "HOST_RESTORE_FAILED"
    HOST_PRUNE_FAILED = "HOST_PRUNE_FAILED"
    HOST_INTERRUPTED = "HOST_INTERRUPTED"
    HOST_REQUEST_UNREADABLE = "HOST_REQUEST_UNREADABLE"
    HOST_REQUEST_ID_INVALID = "HOST_REQUEST_ID_INVALID"
    HOST_REQUEST_RUNNING = "HOST_REQUEST_RUNNING"
    HOST_INPUT_CUT_OFF = "HOST_INPUT_CUT_OFF"
    HOST_LOGIN_INCOMPLETE = "HOST_LOGIN_INCOMPLETE"
    HOST_DEPLOY_GONE = "HOST_DEPLOY_GONE"
    ROLLBACK_NO_PREVIOUS = "ROLLBACK_NO_PREVIOUS"
    ROLLBACK_NOTHING_DEPLOYED = "ROLLBACK_NOTHING_DEPLOYED"
    ROLLBACK_FIRST_DEPLOY_FAILED = "ROLLBACK_FIRST_DEPLOY_FAILED"
    STATE_LAYOUT_BASH = "STATE_LAYOUT_BASH"
    # build, promote, remove, prune and login (T5)
    BUILD_NOT_A_COMMIT = "BUILD_NOT_A_COMMIT"
    BUILD_NOT_ON_REMOTE = "BUILD_NOT_ON_REMOTE"
    BUILD_LOCAL_NEEDS_PREVIEW = "BUILD_LOCAL_NEEDS_PREVIEW"
    BUILD_HOOK_FAILED = "BUILD_HOOK_FAILED"
    BUILD_NO_LAYOUT = "BUILD_NO_LAYOUT"
    BUILD_LABELS_DIFFER = "BUILD_LABELS_DIFFER"
    BUILD_NO_LOCAL_IMAGE = "BUILD_NO_LOCAL_IMAGE"
    BUILD_WORKTREE_FAILED = "BUILD_WORKTREE_FAILED"
    BUILD_GATE_REFUSED = "BUILD_GATE_REFUSED"
    VERSION_FILE_UNREADABLE = "VERSION_FILE_UNREADABLE"
    CALLED_REQUEST_UNREADABLE = "CALLED_REQUEST_UNREADABLE"
    CALLED_INPUT_CUT_OFF = "CALLED_INPUT_CUT_OFF"
    PRUNE_NO_RELEASE = "PRUNE_NO_RELEASE"
    PRUNE_REMOVE_FAILED = "PRUNE_REMOVE_FAILED"
    REMOVE_REFUSED = "REMOVE_REFUSED"
    LOGIN_UNKNOWN_COMPONENT = "LOGIN_UNKNOWN_COMPONENT"
    LOGIN_SHARED_WITH_BUILDER = "LOGIN_SHARED_WITH_BUILDER"
    LOGIN_INCOMPLETE = "LOGIN_INCOMPLETE"
    LOGIN_DOCKER_FAILED = "LOGIN_DOCKER_FAILED"
    LOGIN_TOOL_MISSING = "LOGIN_TOOL_MISSING"
    # deploy and settle (§6, §9, §12): what the controller stops for, before the host is called or after it
    REF_UNKNOWN = "REF_UNKNOWN"
    REF_NO_BUILD = "REF_NO_BUILD"
    REF_RECORD_UNREADABLE = "REF_RECORD_UNREADABLE"
    PRODUCTION_RECORD_MISSING = "PRODUCTION_RECORD_MISSING"
    PRODUCTION_RECORD_NOT_IN_RELEASES = "PRODUCTION_RECORD_NOT_IN_RELEASES"
    REHEARSAL_OFF_LEVEL = "REHEARSAL_OFF_LEVEL"
    OVERRIDE_WRONG_ROLE = "OVERRIDE_WRONG_ROLE"
    HOST_FILES_CONFLICT = "HOST_FILES_CONFLICT"
    COPY_TO_RELEASES_FAILED = "COPY_TO_RELEASES_FAILED"
    DEPLOY_LIVE_WITH_ERRORS = "DEPLOY_LIVE_WITH_ERRORS"
    POST_DEPLOY_REPORTED = "POST_DEPLOY_REPORTED"
    SETTLE_NO_RECORD = "SETTLE_NO_RECORD"
    SETTLE_NO_ANNOUNCEMENT = "SETTLE_NO_ANNOUNCEMENT"
    SETTLE_INCOMPLETE = "SETTLE_INCOMPLETE"
    BOARD_UNAVAILABLE = "BOARD_UNAVAILABLE"
    BOARD_REPOSITORY_UNKNOWN = "BOARD_REPOSITORY_UNKNOWN"
    # the board model, called in-process (§4), and release (T7)
    BOARD_PROFILE_ERROR = "BOARD_PROFILE_ERROR"
    RELEASE_GATE_REFUSED = "RELEASE_GATE_REFUSED"
    RELEASE_COMMIT_UNKNOWN = "RELEASE_COMMIT_UNKNOWN"
    RELEASE_NOT_CONFIRMED = "RELEASE_NOT_CONFIRMED"
    RELEASE_TAG_FAILED = "RELEASE_TAG_FAILED"
    RELEASE_STEPS_FAILED = "RELEASE_STEPS_FAILED"
    RELEASE_STEP_FAILED = "RELEASE_STEP_FAILED"
    BUMP_FAILED = "BUMP_FAILED"


@dataclass(frozen=True)
class Violation:
    """One refused value (AIP-193's `BadRequest`)."""
    field: str
    value: str
    limit: str
    reason: str


@dataclass(frozen=True)
class Result:
    """How an operation or a command ended. Frozen; `cause` is the result from
    below, so the object is recursive."""
    outcome: Outcome
    type: ErrorType | None = None
    blip: bool | None = None
    reason: str = ""
    domain: str = DOMAIN
    message: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    violations: tuple[Violation, ...] = ()
    cause: Result | None = None
    errors: tuple[Result, ...] = ()

    def __post_init__(self) -> None:
        failed = self.outcome in (Outcome.ERROR, Outcome.FATAL)
        if failed != (self.type is not None):
            raise ValueError("only an error or fatal result has a type")
        if (self.type is ErrorType.TECHNICAL) != (self.blip is not None):
            raise ValueError("a technical result says blip or not, and no other does")

    def to_json(self) -> dict[str, Any]:
        """The whole object, recursive over `cause` and `errors`: what the run log
        and `turpin-host status --json` carry (R56)."""
        data: dict[str, Any] = {
            "outcome": self.outcome.value, "type": self.type.value if self.type else None,
            "blip": self.blip, "reason": self.reason, "domain": self.domain,
            "message": self.message, "metadata": dict(self.metadata),
            "violations": [asdict(v) for v in self.violations]}
        if self.cause is not None:
            data["cause"] = self.cause.to_json()
        if self.errors:
            data["errors"] = [e.to_json() for e in self.errors]
        return data

    @classmethod
    def ok(cls, message: str = "", metadata: Mapping[str, Any] | None = None) -> Result:
        return cls(Outcome.OK, message=message, metadata=metadata or {})


def exit_status(result: Result) -> int:
    """The one place a result becomes an exit status (design §6)."""
    if result.outcome in (Outcome.OK, Outcome.WARNING):
        return EXIT_OK
    if result.outcome is Outcome.ERROR:
        return EXIT_ERRORS
    if result.type is ErrorType.BUSINESS:
        return EXIT_REFUSED
    if result.type is ErrorType.TECHNICAL:
        return EXIT_BLIP if result.blip else EXIT_FUNDAMENTAL
    return EXIT_UNEXPECTED


class ProgrammeError(Exception):
    """An error carrying its `Result`. One raised in answer to another is raised
    `from` it, and its result's `cause` is the other's result."""

    kind: ErrorType

    def __init__(self, result: Result):
        super().__init__(result.message)
        self.result = result

    @classmethod
    def make(cls, reason: Reason | str, message: str, *,
             domain: str = DOMAIN, outcome: Outcome = Outcome.FATAL,
             metadata: Mapping[str, Any] | None = None,
             violations: tuple[Violation, ...] = (),
             cause: Result | None = None, blip: bool = False) -> ProgrammeError:
        """The error of this class: `blip` is read by a `TechnicalError` only."""
        text = reason.value if isinstance(reason, enum.Enum) else reason
        kind = cls.kind
        return cls(Result(outcome, kind, blip if kind is ErrorType.TECHNICAL else None,
                          text, domain, message, metadata or {}, violations, cause))


    @classmethod
    def wrap(cls, inner: ProgrammeError, reason: Reason | str, message: str, **kwargs: Any) -> ProgrammeError:
        """An error of this class raised in answer to `inner`: its result is the
        new one's `cause`. Raise it `from inner`."""
        return cls.make(reason, message, cause=inner.result, **kwargs)

    def with_context(self, **metadata: Any) -> ProgrammeError:
        """The same error with more context in its metadata (which image, which
        step); type, reason and cause are kept. Returns a new error to raise."""
        return type(self)(replace(self.result, metadata={**self.result.metadata, **metadata}))


class BusinessError(ProgrammeError):
    """The request is wrong, a rule refuses it, or the thing is not there: exit 1."""
    kind = ErrorType.BUSINESS


class TechnicalError(ProgrammeError):
    """A service failed for now (a blip, exit 75) or a credential, tool or setting
    is wrong (fundamental, exit 2)."""
    kind = ErrorType.TECHNICAL


class UnexpectedError(ProgrammeError):
    """Any error the code did not expect: exit 70."""
    kind = ErrorType.UNEXPECTED


class ProfileError(TechnicalError):
    """A setting missing or malformed, in a profile, an `APP.env` or a host's
    `.env`: fundamental, exit 2, naming the key or the line (design §8)."""

    @classmethod
    def at(cls, reason: Reason, message: str, cause: Result | None = None,
           **metadata: Any) -> ProfileError:
        return cls.make(reason, message, metadata=metadata, cause=cause)  # type: ignore[return-value]



class FormError(Exception):
    """A value that fails its form, found where the value is made. It is not a
    `ProgrammeError`, so one nobody translated reaches the front end as an
    unexpected error, exit 70. Design §3: it is business only from an argument or
    the version file, which `read_input` says; else unexpected, naming the field."""

    def __init__(self, field_name: str, value: object, limit: str, reason: str):
        super().__init__(f"{field_name} {value!r} is not {limit}")
        self.violation = Violation(field_name, str(value), limit, reason)

    def business(self, where: str) -> BusinessError:
        """Refused: `where` names the argument or the file the value came from."""
        return BusinessError.make(Reason.BAD_VALUE, f"{where}: {self}",  # type: ignore[return-value]
                                  metadata={"source": where}, violations=(self.violation,))

    def unexpected(self, where: str) -> UnexpectedError:
        """Not expected: `turpin` wrote the value, so it is a defect to raise as an issue."""
        return UnexpectedError.make(Reason.BAD_VALUE, f"{where}: {self}: raise it as an issue",  # type: ignore[return-value]
                                    metadata={"source": where}, violations=(self.violation,))


def read_input(where: str, make: Callable[..., T], *args: Any) -> T:
    """Make a value from an argument or the version file, `where` naming which: a
    bad form is a business error (R48)."""
    try:
        return make(*args)
    except FormError as exc:
        raise exc.business(where) from exc


# ----------------------------------------------------------------- value types

_SEMVER = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_COMMIT = re.compile(r"[0-9a-f]{40}")


@dataclass(frozen=True, order=True)
class Version:
    """A release's version, ordered as semver."""
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, text: str) -> Version:
        found = _SEMVER.fullmatch(text)
        if not found:
            raise FormError("version", text, "a semver version (X.Y.Z)", "NOT_SEMVER")
        return cls(*(int(part) for part in found.groups()))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


@dataclass(frozen=True)
class Digest:
    """An image digest: `sha256:` and 64 hexadecimal characters."""
    text: str

    def __post_init__(self) -> None:
        if not _DIGEST.fullmatch(self.text):
            raise FormError("digest", self.text, "sha256: and 64 hexadecimal characters", "NOT_A_DIGEST")

    def __str__(self) -> str:
        return self.text


def check_commit(text: str) -> str:
    """A full 40-character SHA, or a business error."""
    if not _COMMIT.fullmatch(text):
        raise FormError("commit", text, "a full 40-character hexadecimal SHA", "NOT_A_COMMIT")
    return text


@dataclass(frozen=True)
class Image:
    """One image as the registry holds it."""
    name: str
    digest: Digest
    revision: str
    created: str


@dataclass(frozen=True)
class Build:
    """One commit's image set, built once and stored in candidates."""
    commit: str
    images: Mapping[str, Digest]

    def __post_init__(self) -> None:
        check_commit(self.commit)


@dataclass(frozen=True)
class ReleaseRecord:
    """A release's record, read and written whole (design §10), version 1."""
    application: str
    version: Version
    commit: str
    images: Mapping[str, Digest]
    made: str
    rehearsal: Mapping[str, Any] | None = None
    emergency: str | None = None
    rehearsal_skipped: str | None = None
    set_aside: tuple[Mapping[str, str], ...] = ()
    tool: Mapping[str, str] = field(default_factory=dict)
    carries: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        check_commit(self.commit)

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> ReleaseRecord:
        return cls(
            application=data["application"], version=Version.parse(data["version"]),
            commit=data["commit"], images={k: Digest(v) for k, v in data["images"].items()},
            made=data["made"], rehearsal=data.get("rehearsal"), emergency=data.get("emergency"),
            rehearsal_skipped=data.get("rehearsal_skipped"),
            set_aside=tuple(data.get("set_aside") or ()), tool=data.get("tool") or {},
            carries=data.get("carries") or {})

    def to_json(self) -> dict[str, Any]:
        return {
            "record": 1, "application": self.application, "version": str(self.version),
            "commit": self.commit, "images": {k: str(v) for k, v in self.images.items()},
            "made": self.made, "rehearsal": self.rehearsal, "emergency": self.emergency,
            "rehearsal_skipped": self.rehearsal_skipped, "set_aside": list(self.set_aside),
            "tool": dict(self.tool), "carries": dict(self.carries)}


class Role(enum.Enum):
    """What an environment is for, which gates key on."""
    PREVIEW = "preview"
    TEST = "test"
    REHEARSAL = "rehearsal"
    PRODUCTION = "production"


class CredentialKind(enum.Enum):
    """How a component's registry login is made (the profile's `login`)."""
    DOCKER_CONFIG = "docker-config"
    OCI_API_KEY = "oci-api-key"
    OCI_INSTANCE_PRINCIPAL = "oci-instance-principal"


class CredentialForm(enum.Enum):
    """What a credential starts from."""
    AUTH_TOKEN = "auth-token"
    API_KEY = "api-key"
    INSTANCE_PRINCIPAL = "instance-principal"


class Api(enum.Enum):
    """Which of the registry host's APIs a credential is used for (design §3)."""
    REGISTRY = "registry"
    ARTIFACTS = "artifacts"


class ComponentKind(enum.Enum):
    CONTROLLER = "controller"
    BUILDER = "builder"
    COPIER = "copier"
    DEPLOYER = "deployer"


class RepositoryKind(enum.Enum):
    CANDIDATES = "candidates"
    RELEASES = "releases"


CONTROLLER = "controller"   # an environment's or component's machine, when it is this one


@dataclass(frozen=True)
class Environment:
    """One application environment in the profile."""
    name: str
    role: Role
    machine: str            # CONTROLLER, or an `ssh` alias
    login: CredentialKind
    project: str | None
    url: str | None
    lock: str | None
    pull_timeout: int
    host_files: bool
    join: tuple[str, ...]


@dataclass(frozen=True)
class Credential:
    """One way a component proves who it is to the registry host."""
    form: CredentialForm
    api: Api


@dataclass(frozen=True)
class Component:
    """Whose credentials an operation uses."""
    kind: ComponentKind
    environment: Environment | None
    login: CredentialKind
    credentials: tuple[Credential, ...] = ()


@dataclass(frozen=True)
class Repository:
    """One of the application's two repositories."""
    kind: RepositoryKind
    name: str


@dataclass(frozen=True)
class DeployedBuild:
    """What a host ran: the build, its record where there is one, and when. `number`
    is the host's deploy number and `version` the version the request named (empty for
    a commit with none)."""
    build: Build
    record: ReleaseRecord | None
    deployed: str | None
    number: int | None = None
    version: str = ""


@dataclass(frozen=True)
class Deployed:
    """What an environment runs, as `turpin-host status` reports it."""
    state: str
    pending: DeployedBuild | None
    request_id: str | None
    outcome: str | None
    current: DeployedBuild | None
    previous: DeployedBuild | None


@dataclass(frozen=True)
class HostFile:
    src: str
    dest: str
    mode: str = "0644"
    enable: bool = False


@dataclass(frozen=True)
class Ephemeral:
    user_prefix: str
    home: str
    secrets: tuple[str, ...]


@dataclass(frozen=True)
class Profile:
    """The application's profile at a commit or in the working tree (design §8)."""
    application: str
    tag_prefix: str
    history_prefixes: tuple[str, ...]
    announcement: str
    deploy_marker: str
    required_checks: tuple[str, ...]
    required_hooks: tuple[str, ...]
    overridable: tuple[str, ...]
    candidates: str
    releases: str
    images: tuple[str, ...]
    payload_image: str | None
    join: tuple[str, ...]
    login: CredentialKind
    fallback: str | None
    build_on: str
    build_login: CredentialKind
    copy_on: str
    copy_login: CredentialKind
    host_files: tuple[HostFile, ...]
    ephemeral: Ephemeral | None
    deployed_path: str | None
    deployed_field: str | None
    environments: Mapping[str, Environment]
