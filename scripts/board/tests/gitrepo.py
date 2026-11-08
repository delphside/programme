"""A real git history built in a temporary directory, for the tests whose answer
is git's (a release's range, its reverts, its tags)."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


class History:
    """`History().commit("subject\\n\\nRefs #1")` returns the sha. Use as a context
    manager and run the code under test with `profiles.inside(history.path)`."""

    def __init__(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.path = Path(self._dir.name)
        self.git("init", "-q", "-b", "main", ".")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "test")

    def git(self, *args: str) -> str:
        return subprocess.run(["git", *args], cwd=self.path, check=True,
                              capture_output=True, text=True).stdout.strip()

    def commit(self, message: str) -> str:
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")

    def revert(self, sha: str, trailer: str = "") -> str:
        """A commit that says what `git revert` says, with its own trailer."""
        return self.commit(f"Revert {sha[:7]}\n\n{trailer}\nThis reverts commit {sha}.")

    def tag(self, name: str, message: str | None = None, at: str = "HEAD") -> None:
        self.git("tag", "-a", "-m", message if message is not None else name, name, at)

    def close(self) -> None:
        self._dir.cleanup()

    def __enter__(self) -> "History":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
