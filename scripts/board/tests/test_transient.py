"""What `turpin` needs of the board model besides its rules (delphside/programme#117, design §4,
test design R62 and R63): `Unavailable` says whether a failure may pass by itself, and every `gh`
and `git` the model starts runs in a process group of its own.

  transient   true for a timeout, a connection error, 429 and a 5xx, whichever call met it;
              false for a tool that is missing or a refusal (401, 403, 404, 422)
  detached    every `gh` and `git` is started with `start_new_session`, so a Ctrl+C reaches
              `turpin` alone and the call already running runs to its end

No network: `subprocess.run` is replaced.
"""

import ast
import os
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from board import repo, sources
from board.sources import Refused, Unavailable

BOARD = Path(__file__).resolve().parents[1]


class Repository(unittest.TestCase):
    """The calls go to a repository of the tests' own."""

    def setUp(self):
        patcher = mock.patch.dict(os.environ, {"BOARD_REPOSITORY": "fakeorg/widget"})
        patcher.start()
        self.addCleanup(patcher.stop)


def failing(stderr="", code=1):
    return lambda args, **kw: subprocess.CompletedProcess(args, code, "", stderr)


def timing_out(args, **kw):
    raise subprocess.TimeoutExpired(args, 1)


def not_installed(args, **kw):
    raise FileNotFoundError("gh")


# one call of each kind the release makes, each of which reads or writes through `gh` or `git`
CALLS = {
    "a GraphQL read": lambda: sources._gh_graphql("query { viewer { login } }"),
    "a REST read": lambda: sources.rest_get("repos/o/r/milestones"),
    "a REST list": lambda: list(sources._Rest().items("repos/o/r/issues")),
    "a REST write": lambda: sources._rest_write("PATCH", "repos/o/r/issues/1", state="closed"),
    "a Release": lambda: sources.create_release("v1.0.0", None),
    "a git read the gates need": lambda: repo._git_must("tag", "--list"),
}


class Transient(Repository):
    """The flag is set where the model meets the failure, so `turpin` maps it (75 or 2)."""

    def raised(self, call, run):
        with mock.patch.object(sources.subprocess, "run", run):
            with self.assertRaises(Unavailable) as caught:
                CALLS[call]()
        return caught.exception

    def test_an_unavailable_is_not_transient_unless_it_says_so(self):
        self.assertFalse(Unavailable("x").transient)
        self.assertTrue(Unavailable("x", transient=True).transient)
        self.assertEqual("x", str(Unavailable("x", transient=True)))

    def test_a_timeout_is_transient_in_every_call(self):
        for call in CALLS:
            with self.subTest(call):
                self.assertTrue(self.raised(call, timing_out).transient)

    def test_a_server_error_rate_limit_or_connection_failure_is_transient_in_every_call(self):
        for text in ("gh: HTTP 503: Service Unavailable", "gh: HTTP 502", "gh: HTTP 429: too many requests",
                     "gh: You have exceeded a secondary rate limit", "dial tcp: lookup api.github.com: no such host",
                     "Post https://api.github.com: connection reset by peer", "net/http: TLS handshake timeout",
                     "fatal: unable to access: Could not resolve host: github.com",
                     "error connecting to api.github.com", "check your internet connection or githubstatus.com"):
            for call in CALLS:
                with self.subTest(call=call, text=text):
                    self.assertTrue(self.raised(call, failing(text)).transient)

    def test_a_refusal_or_a_missing_tool_is_not_transient_in_any_call(self):
        for text in ("gh: HTTP 401: Bad credentials", "gh: HTTP 403: Resource not accessible by integration",
                     "gh: HTTP 422: Validation Failed", "gh: simulated failure", "fatal: not a git repository",
                     "ssh: Could not resolve hostname github.com: Name or service not known"):
            for call in CALLS:
                with self.subTest(call=call, text=text):
                    self.assertFalse(self.raised(call, failing(text)).transient)
        for call in CALLS:
            with self.subTest(call=call, text="not installed"):
                self.assertFalse(self.raised(call, not_installed).transient)

    def test_a_graphql_refusal_that_is_a_server_error_stays_a_refusal_and_is_transient(self):
        error = self.raised("a GraphQL read", failing("gh: HTTP 502: Bad Gateway"))
        self.assertIsInstance(error, Refused)            # a caller with a REST route may still take it
        self.assertTrue(error.transient)

    def test_a_wrapped_unavailable_keeps_the_flag(self):
        with mock.patch.object(sources, "_gh_graphql", side_effect=Unavailable("GitHub did not answer", transient=True)), \
                mock.patch.object(sources.profile, "organisation", return_value="o"):
            with self.assertRaises(Unavailable) as caught:
                sources.organisation_repositories()
        self.assertTrue(caught.exception.transient)


class Detached(Repository):
    """R63: nothing the board model starts is in `turpin`'s process group."""

    def test_every_gh_and_git_call_the_model_makes_starts_its_own_session(self):
        seen = []

        def record(args, **kw):
            seen.append((args[0], kw.get("start_new_session")))
            return subprocess.CompletedProcess(args, 0, "{}", "")
        with mock.patch.object(sources.subprocess, "run", record):
            for call in CALLS.values():
                try:
                    call()
                except Exception:        # the answers are not the point; the way each is started is
                    pass
            repo._git("tag", "--list")
            sources.remote_branches("origin")
        self.assertGreaterEqual(len(seen), 7)
        self.assertEqual({"gh", "git"}, {tool for tool, _ in seen})
        self.assertTrue(all(started is True for _, started in seen), seen)

    def test_no_module_of_the_model_starts_a_process_in_turpins_group(self):
        """Read from the source: in every module `turpin` imports in-process (the model: profile,
        release, repo, sources, model, milestone, refs), each `subprocess` start is the one in
        `run_detached` or carries `start_new_session`; none is a bare `run`, `Popen` or `call`."""
        starts = {"run", "Popen", "call", "check_call", "check_output"}
        for name in ("profile.py", "release.py", "repo.py", "sources.py", "model.py", "milestone.py", "refs.py"):
            tree = ast.parse((BOARD / name).read_text())
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr in starts and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "subprocess"):
                    self.assertIn("start_new_session", [k.arg for k in node.keywords],
                                  f"{name} line {node.lineno} starts a process in turpin's group")

    def test_run_detached_passes_the_session_flag_and_the_callers_arguments(self):
        with mock.patch.object(sources.subprocess, "run") as run:
            sources.run_detached(["git", "status"], capture_output=True, timeout=5)
        run.assert_called_once_with(["git", "status"], start_new_session=True, capture_output=True, timeout=5)


if __name__ == "__main__":
    unittest.main()
