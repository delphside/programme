"""The pin-behind warning at the start of a session (docs/1.1, `pin.py`).

From the rule, not the code: a pin is behind when the programme's `origin/main`
holds a commit it lacks that touches a path outside `records/` and
`applications/`; the warning never moves the pin, and says nothing on a release
branch, at a release tag, in the programme itself, or when it cannot tell.

Each case builds real repositories: a programme, and an application that carries
it as a submodule pinned at its first commit.
"""

import os
import subprocess
import tempfile
import time
from unittest import mock
from pathlib import Path

from board import pin
from board.tests.cases import Cases
from board.tests.cli import run


def git(cwd, *args, check=True):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                           "-c", "protocol.file.allow=always", "-C", str(cwd), *args],
                          check=check, capture_output=True, text=True)


def commit(repo: Path, path: str, text: str = "x") -> None:
    (repo / path).parent.mkdir(parents=True, exist_ok=True)
    (repo / path).write_text(text)
    git(repo, "add", path)
    git(repo, "commit", "-q", "-m", f"change {path}")


class ThePinWarning(Cases):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        top = Path(self._dir.name).resolve()
        self.upstream, self.app = top / "programme-upstream", top / "app"
        self.upstream.mkdir()
        git(self.upstream, "init", "-q", "-b", "main")
        commit(self.upstream, "docs/1.1.md")
        self.app.mkdir()
        git(self.app, "init", "-q", "-b", "main")
        git(self.app, "submodule", "add", "-q", str(self.upstream), "programme")
        git(self.app, "commit", "-q", "-m", "pin")
        self.pinned = self.app / "programme"
        self.pin_sha = git(self.app, "rev-parse", "HEAD:programme").stdout.strip()

    def warning(self):
        return pin.warning(self.app)

    def test_a_commit_outside_records_and_applications_makes_it_behind(self):
        commit(self.upstream, "scripts/board/x.py")
        said = self.warning()
        self.expect("a warning that names the count and the commit", True,
                    said is not None and "1 commit(s) behind" in said and "change scripts/board/x.py" in said)

    def test_it_fetches_the_one_branch_itself(self):
        commit(self.upstream, "docs/1.2.md")
        self.warning()
        self.expect("the submodule now has it", True,
                    git(self.pinned, "rev-parse", "--verify", "-q", "refs/remotes/origin/main").returncode == 0)

    def test_records_and_applications_alone_do_not(self):
        commit(self.upstream, "records/2.3-activity-log.csv")
        commit(self.upstream, "applications/widget/3.1.md")
        self.expect("quiet", None, self.warning())

    def test_a_commit_touching_both_does(self):
        (self.upstream / "records").mkdir()
        (self.upstream / "records" / "r.md").write_text("r")
        (self.upstream / "docs" / "1.1.md").write_text("changed")
        git(self.upstream, "add", ".")
        git(self.upstream, "commit", "-q", "-m", "both")
        self.expect("warned", True, self.warning() is not None)

    def test_a_pin_at_origin_main_says_nothing(self):
        self.expect("quiet", None, self.warning())

    def test_it_never_moves_the_pin(self):
        commit(self.upstream, "docs/1.2.md")
        self.warning()
        self.expect("the gitlink is where it was", self.pin_sha,
                    git(self.pinned, "rev-parse", "HEAD").stdout.strip())

    def test_a_release_or_emergency_branch_keeps_its_pin_quietly(self):
        commit(self.upstream, "docs/1.2.md")
        for name in ("release/1.2.0", "emergency-login"):
            git(self.app, "checkout", "-q", "-b", name)
            self.expect(name, None, self.warning())

    def test_a_detached_head_at_a_tag_is_quiet_and_at_a_commit_is_not(self):
        commit(self.upstream, "docs/1.2.md")
        git(self.app, "checkout", "-q", "--detach")
        self.expect("a bare detached HEAD still warns", True, self.warning() is not None)
        git(self.app, "tag", "v1.0.0")
        self.expect("at a tag it does not", None, self.warning())

    def test_the_programme_itself_has_no_pin(self):
        commit(self.upstream, "docs/1.2.md")
        self.expect("quiet", None, pin.warning(self.upstream))

    def test_an_unreachable_origin_says_nothing_and_does_not_wait(self):
        git(self.pinned, "remote", "set-url", "origin", str(self.upstream) + "-gone")
        self.expect("quiet", None, self.warning())

    def test_a_failed_fetch_says_nothing_even_with_an_older_ref_to_compare(self):
        git(self.pinned, "fetch", "-q", "origin", "main")       # a ref from an earlier session
        commit(self.upstream, "docs/1.2.md")
        git(self.pinned, "remote", "set-url", "origin", str(self.upstream) + "-gone")
        # The ref alone would still show nothing behind; so make it show something.
        git(self.pinned, "fetch", "-q", str(self.upstream), "main:refs/remotes/origin/main")
        self.expect("the stale ref is behind", True,
                    git(self.pinned, "rev-list", "--count", f"{self.pin_sha}..refs/remotes/origin/main").stdout.strip() == "1")
        self.expect("but the fetch failed, so quiet", None, self.warning())

    def test_a_fetch_that_hangs_is_cut_off_at_FETCH_SECONDS(self):
        # A remote that sleeps four seconds; the limit is half a second. Without
        # the limit the call waits the four.
        git(self.pinned, "config", "protocol.ext.allow", "always")
        git(self.pinned, "remote", "set-url", "origin", "ext::sleep 4")
        with mock.patch.object(pin, "FETCH_SECONDS", 0.5):
            start = time.monotonic()
            said = self.warning()
        self.expect("quiet", None, said)
        self.expect("and quickly", True, time.monotonic() - start < 3)

    def test_an_uninitialised_submodule_says_nothing(self):
        for child in list(self.pinned.iterdir()):
            if child.is_file():
                child.unlink()
            else:
                import shutil
                shutil.rmtree(child)
        self.expect("quiet", None, self.warning())

    def test_the_command_prints_one_line_and_exits_0(self):
        commit(self.upstream, "docs/1.2.md")
        out = run("board/board-records.py", "pin", cwd=self.app, env=dict(os.environ))
        self.expect("exit 0", 0, out.returncode)
        self.expect("one line", 1, len(out.stdout.strip().splitlines()))
        quiet = run("board/board-records.py", "pin", cwd=self.upstream, env=dict(os.environ))
        self.expect("quiet in the programme itself", ("", 0), (quiet.stdout, quiet.returncode))
