"""The bottom layer (design §3 *The registry adapter*): one function per call, for
Oracle's two APIs. The registry API runs through `skopeo`, the Artifacts API through
the `oci` CLI. Only this module knows a tool's syntax, an auth file or configuration,
and a tool's output format.

It meets the technical errors (R50, R51): authorisation, the network, a timeout, a
missing tool. A blip is retried where the call is safe to repeat (reads, copy and push,
delete), each retry logged, and `oci` is always run with `--no-retry` so this rule is
the only one. It logs each call's name and duration, never its arguments, which can
hold an OCID. Every failure is an `ApiError` of domain `oracle`, whose `metadata`
holds the tool, the call, the exit status, the HTTP status where it can tell it, the
attempts and the tool's text, with the registry address, namespace and OCIDs removed.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

from ... import settings
from ...model import ErrorType, Result, Outcome, TechnicalError, UnexpectedError
from ...runlog import RunLog
from .reasons import DOMAIN, OracleReason, snake

SKOPEO = "skopeo"
OCI = "oci"


class ApiError(TechnicalError):
    """A call that failed: a blip or a fundamental technical error, domain `oracle`.
    The middle layer decides what it means (`translate.classify`)."""


@dataclass(frozen=True)
class Gateway:
    """What every call needs: the component it is made for, its credentials, the run
    log, and the retry rule (design §13: three attempts, waiting 2 seconds, then 4; a
    call times out after 300 seconds)."""
    component: str
    registry: str                                   # HOST/NAMESPACE, to scrub from text
    log: RunLog
    authfile: Path | None = None                    # the component's `skopeo` login
    artifacts_auth: str | None = None               # "api-key" or "instance-principal"
    oci_config_file: str | None = None              # an API key's configuration
    attempts: int = settings.RETRY_ATTEMPTS
    backoff: tuple[float, ...] = settings.RETRY_BACKOFF_SECONDS
    timeout: float = settings.REGISTRY_CALL_TIMEOUT
    sleep: Callable[[float], None] = field(default=time.sleep, compare=False)


# ------------------------------------------------------------------- scrubbing

_OCID = re.compile(r"ocid1\.[A-Za-z0-9_.-]+")


def scrub(text: str, registry: str, secret: str | None = None) -> str:
    """`text` with the registry address, its namespace, any OCID and a secret removed."""
    if secret:
        text = text.replace(secret, "<secret>")
    text = _OCID.sub("<ocid>", text)
    if registry:
        text = text.replace(registry, "<registry>")
        host, _, namespace = registry.partition("/")
        for part, name in ((namespace, "<namespace>"), (host, "<registry>")):
            if part:
                text = re.sub(rf"(?<![\w.-]){re.escape(part)}(?![\w-])", name, text)
    return text


# ---------------------------------------------------------------- running tools

def _env(gw: Gateway, tool: str) -> dict[str, str]:
    env = dict(os.environ)
    if tool == SKOPEO and gw.authfile is not None:
        env["REGISTRY_AUTH_FILE"] = str(gw.authfile)    # the only variable the tool sets
    return env


def _status_of(text: str) -> int | None:
    found = re.search(r"(?:status[: =]+|HTTP |StatusCode:? ?)(\d{3})\b", text, re.IGNORECASE)
    return int(found.group(1)) if found else None


_NETWORK = re.compile(
    r"connection refused|connection reset|no such host|i/o timeout|tls handshake timeout|"
    r"network is unreachable|temporary failure in name resolution|dial tcp|\bEOF\b|"
    r"connecttimeout|connectionerror|max retries exceeded|timed out|broken pipe", re.IGNORECASE)
_UNAUTHORIZED = re.compile(r"unauthorized|authentication required|invalid username/password|"
                           r"authentication failed", re.IGNORECASE)
_DENIED = re.compile(r"\bdenied\b|access denied|forbidden", re.IGNORECASE)
_MANIFEST_UNKNOWN = re.compile(r"manifest unknown|manifest_unknown|manifest for .* not found", re.IGNORECASE)
_NAME_UNKNOWN = re.compile(r"name unknown|name_unknown|repository name not known", re.IGNORECASE)
_AUTH_CONFIG = re.compile(r"config file|configfilenotfound|invalidconfig|private key|key_file|"
                          r"could not find config|invalidprivatekey", re.IGNORECASE)


def _envelope(text: str) -> dict[str, Any] | None:
    """The `oci` CLI's error envelope (`code`, `message`, `status`) in its standard error."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except ValueError:
        return None
    return data if isinstance(data, dict) and ("code" in data or "status" in data) else None


def _classify(tool: str, text: str) -> tuple[str, bool, int | None]:
    """(reason, blip, HTTP status) of a failed call, from the tool's error text.
    `skopeo` reports no status and does not reliably exit 2 for an image missing
    from a remote registry, so the text is read and the exit status never is (R51)."""
    envelope = _envelope(text) if tool == OCI else None
    status = int(envelope["status"]) if envelope and isinstance(envelope.get("status"), int) else _status_of(text)
    if envelope and isinstance(envelope.get("code"), str) and envelope["code"]:
        reason = snake(envelope["code"])
    elif _MANIFEST_UNKNOWN.search(text):
        reason = OracleReason.MANIFEST_UNKNOWN.value
    elif _NAME_UNKNOWN.search(text):
        reason = OracleReason.NAME_UNKNOWN.value
    elif status == 429 or "too many requests" in text.lower():
        return OracleReason.THROTTLED.value, True, status or 429
    elif status is not None and 500 <= status <= 599:
        return OracleReason.SERVER_ERROR.value, True, status
    elif status == 401 or _UNAUTHORIZED.search(text):
        reason = OracleReason.UNAUTHORIZED.value
    elif status == 403 or _DENIED.search(text):
        reason = OracleReason.DENIED.value
    elif tool == OCI and _AUTH_CONFIG.search(text):
        reason = OracleReason.AUTH_CONFIG_MISSING.value
    elif _NETWORK.search(text):
        return OracleReason.NETWORK_ERROR.value, True, status
    else:
        reason = OracleReason.TOOL_FAILED.value
    blip = status is not None and (status == 429 or 500 <= status <= 599)
    return reason, blip, status


def _fail(gw: Gateway, tool: str, call: str, reason: str, blip: bool, message: str, *,
          exit_status: int | None, http_status: int | None, attempts: int, text: str,
          earlier_blip: bool, secret: str | None = None) -> ApiError:
    metadata: dict[str, Any] = {"tool": tool, "call": call, "exit": exit_status, "attempts": attempts,
                                "tool_text": scrub(text, gw.registry, secret)[:settings.ERROR_TEXT_MAX]}
    if http_status is not None:
        metadata["http_status"] = http_status
    if earlier_blip:
        metadata["earlier_blip"] = True
    return ApiError(Result(Outcome.FATAL, ErrorType.TECHNICAL, blip, reason, DOMAIN, message, metadata))


def _run_once(argv: Sequence[str], env: dict[str, str], stdin: str | None,
              timeout: float) -> tuple[int, bytes, bytes]:
    """One run in a process group of its own, so a Ctrl+C reaches `turpin` alone; a
    run past `timeout` has its group killed (`subprocess.TimeoutExpired`)."""
    # Bytes, not text: a manifest is hashed exactly as the registry stores it.
    child = subprocess.Popen(list(argv), env=env, stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    deadline = time.monotonic() + timeout
    pending = stdin.encode() if stdin is not None else None
    while True:
        try:
            out, err = child.communicate(pending, timeout=max(0.0, deadline - time.monotonic()))
            return child.returncode, out, err
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.communicate()
            raise
        except KeyboardInterrupt:
            # A call in flight runs to its end within its limit, as a hook does (design §6
            # *Interruption*, item 1); a further Ctrl+C changes nothing. `turpin` goes on to
            # its front end after.
            while True:
                try:
                    child.communicate(timeout=max(0.0, deadline - time.monotonic()))
                    break
                except KeyboardInterrupt:
                    continue
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.communicate()
                    break
            raise


def _call(gw: Gateway, tool: str, call: str, argv: Sequence[str], *, retry: bool = True,
          stdin: str | None = None, secret: str | None = None, raw: bool = False,
          quiet_output: bool = False) -> Any:
    """Run `argv`, retrying a blip if `retry`; the standard output of the run that passed,
    as bytes if `raw`. `quiet_output` keeps a failed run's standard output out of the error
    text, for a call whose output is a secret."""
    attempts = gw.attempts if retry else 1
    earlier_blip = False
    for attempt in range(1, attempts + 1):
        started = time.monotonic()
        try:
            code, out_bytes, err_bytes = _run_once(argv, _env(gw, tool), stdin, gw.timeout)
            out, err = out_bytes.decode(errors="replace"), err_bytes.decode(errors="replace")
            failure = None if code == 0 else _classify(tool, err if quiet_output else err or out)
            blip = failure is not None and failure[1]
            status = failure[2] if failure else None
            reason = failure[0] if failure else None
        except FileNotFoundError as exc:
            raise _fail(gw, tool, call, OracleReason.TOOL_MISSING.value, False,
                        f"{tool} is not installed: install it", exit_status=None, http_status=None,
                        attempts=attempt, text=str(exc), earlier_blip=earlier_blip) from exc
        except subprocess.TimeoutExpired:
            code, out_bytes, out, err, blip, status, reason = None, b"", "", \
                f"{tool} ran past {gw.timeout} seconds", True, None, OracleReason.TIMEOUT.value
            failure = (reason, True, None)
        except KeyboardInterrupt:
            gw.log.event("registry-call", call=call, tool=tool, attempt=attempt,
                         seconds=round(time.monotonic() - started, 3), result="interrupted")
            raise
        gw.log.event("registry-call", call=call, tool=tool, attempt=attempt,
                     seconds=round(time.monotonic() - started, 3),
                     result="ok" if failure is None else reason)
        if failure is None:
            return out_bytes if raw else out
        if blip and attempt < attempts:
            wait = gw.backoff[min(attempt, len(gw.backoff)) - 1] if gw.backoff else 0
            gw.log.event("registry-retry", call=call, attempt=attempt, reason=reason, wait=wait)
            # Only a timeout or a 5xx may have done the work before it failed (design §3).
            earlier_blip = earlier_blip or reason == OracleReason.TIMEOUT.value or (
                status is not None and 500 <= status <= 599)
            gw.sleep(wait)
            continue
        message = (f"{tool} {call} kept failing: try again later" if blip
                   else f"{tool} {call} failed")
        raise _fail(gw, tool, call, reason, blip, message, exit_status=code, http_status=status,
                    attempts=attempt, text=err if quiet_output else err or out, earlier_blip=earlier_blip, secret=secret)
    raise AssertionError("unreachable")   # pragma: no cover


def _bad_output(gw: Gateway, tool: str, call: str, what: str, text: str) -> UnexpectedError:
    """Output not in the tool's format at all: unexpected."""
    error = UnexpectedError.make(OracleReason.BAD_OUTPUT.value, f"{tool} {call} gave {what}",
                                 domain=DOMAIN, metadata={"tool": tool, "call": call,
                                 "tool_text": scrub(text, gw.registry)[:settings.ERROR_TEXT_MAX]})
    return error  # type: ignore[return-value]


# -------------------------------------------------------------- the registry API

def secure_authfile(path: Path) -> None:
    """The auth file's directory 0700 and the file 0600, set on every use (R44)."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    if path.exists():
        os.chmod(path, 0o600)


def authfile_logged_in(path: Path, registry: str) -> bool:
    """Whether a `skopeo` auth file holds a login for the registry's host."""
    try:
        auths = json.loads(path.read_text()).get("auths", {})
    except (OSError, ValueError, AttributeError):
        return False
    host = registry.partition("/")[0]
    return isinstance(auths, dict) and any(
        isinstance(v, dict) and (k == registry or k == host or k.startswith(host + "/") or registry.startswith(k))
        for k, v in auths.items())


def skopeo_login(gw: Gateway, user: str, token: str) -> None:
    """`skopeo login --authfile`, the token on standard input only."""
    assert gw.authfile is not None
    _call(gw, SKOPEO, "login", [SKOPEO, "login", "--authfile", str(gw.authfile), "-u", user,
                                "--password-stdin", gw.registry.partition("/")[0]],
          retry=False, stdin=token, secret=token)
    secure_authfile(gw.authfile)


def token_command(gw: Gateway, command: str) -> str:
    """The short-lived token `TURPIN_OCI_TOKEN_CMD` prints."""
    try:
        argv = shlex.split(command)
    except ValueError as exc:
        raise _bad_output(gw, OCI, "token", "a token command that cannot be split", command) from exc
    if not argv:
        raise _bad_output(gw, OCI, "token", "an empty token command", command)
    if Path(argv[0]).name == OCI and "--no-retry" not in argv:
        argv = [*argv, "--no-retry"]       # the CLI would otherwise retry on its own
    out = _call(gw, OCI, "token", argv, retry=False, quiet_output=True).strip()
    if not out:
        raise _bad_output(gw, OCI, "token", "no token", "")
    return out


def inspect_raw(gw: Gateway, ref: str) -> bytes:
    """`skopeo inspect --raw`: the manifest or index, as the registry holds it, byte for
    byte (it writes the stored bytes unchanged)."""
    return _call(gw, SKOPEO, "inspect manifest", [SKOPEO, "inspect", "--raw", ref], raw=True)


def inspect_config(gw: Gateway, ref: str) -> str:
    """`skopeo inspect --config`: the image's configuration, for its labels."""
    return _call(gw, SKOPEO, "inspect config", [SKOPEO, "inspect", "--config", ref])


def list_tags(gw: Gateway, ref: str) -> str:
    """`skopeo list-tags`."""
    return _call(gw, SKOPEO, "list tags", [SKOPEO, "list-tags", ref])


def copy(gw: Gateway, source: str, destination: str, *, all_platforms: bool = True) -> None:
    """`skopeo copy`, every platform with digests preserved, between registries, from
    an OCI layout (`oci:DIR`) or to one."""
    flags = ["--all", "--preserve-digests"] if all_platforms else ["--preserve-digests"]
    _call(gw, SKOPEO, "copy image", [SKOPEO, "copy", *flags, source, destination])


# --------------------------------------------------------------- the Artifacts API

def artifacts_auth_present(gw: Gateway) -> bool:
    """Whether the API key's configuration, or the instance principal's tool, is there."""
    if shutil.which(OCI) is None:
        return False
    if gw.artifacts_auth == "instance-principal":
        return True
    config = gw.oci_config_file or os.environ.get(settings.ENV_OCI_CONFIG_FILE) or "~/.oci/config"
    return Path(config).expanduser().is_file()


def _oci_argv(gw: Gateway, *words: str) -> list[str]:
    auth = ["--auth", "instance_principal"] if gw.artifacts_auth == "instance-principal" else (
        ["--config-file", gw.oci_config_file] if gw.oci_config_file else [])
    return [OCI, *words, "--no-retry", *auth]


def _envelope_of(gw: Gateway, call: str, out: str) -> dict[str, Any]:
    try:
        data = json.loads(out)
    except ValueError as exc:
        raise _bad_output(gw, OCI, call, "output that is not JSON", out) from exc
    if not isinstance(data, dict) or "data" not in data:
        raise _bad_output(gw, OCI, call, "no data in its envelope", out)
    return data


def list_images(gw: Gateway, compartment: str, repository_name: str, digest: str) -> list[Any]:
    """`oci artifacts container image list` for a repository and digest: every page of
    the JSON envelope's `data.items`, following `opc-next-page`."""
    items: list[Any] = []
    page: str | None = None
    while True:
        argv = _oci_argv(gw, "artifacts", "container", "image", "list", "--compartment-id", compartment,
                         "--repository-name", repository_name, "--image-digest", digest,
                         "--lifecycle-state", "AVAILABLE")
        if page:
            argv += ["--page", page]
        out = _call(gw, OCI, "list images", argv)
        envelope = _envelope_of(gw, "list images", out)
        data = envelope["data"]
        found = data.get("items") if isinstance(data, dict) else data
        if not isinstance(found, list):
            raise _bad_output(gw, OCI, "list images", "no list of images in its data", out)
        items += found
        page = envelope.get("opc-next-page")
        if not page:
            return items


def get_image(gw: Gateway, image_id: str) -> Any:
    """`oci artifacts container image get`: one image with its `versions` (tags), which a
    listing's summaries do not carry. The envelope's `data`; paging does not apply."""
    out = _call(gw, OCI, "get image", _oci_argv(gw, "artifacts", "container", "image", "get",
                                                "--image-id", image_id))
    return _envelope_of(gw, "get image", out)["data"]


def delete_image(gw: Gateway, image_id: str) -> None:
    """`oci artifacts container image delete`, by OCID."""
    _call(gw, OCI, "delete image", _oci_argv(gw, "artifacts", "container", "image", "delete",
                                             "--image-id", image_id, "--force"))
