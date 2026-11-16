"""An application whose technical profile has no `[release]` table (delphside/programme#199).

The table is optional as a whole: an application that has made no release has no
release tags, no deploy announcements and no CI status to read, and each read
that needed one answers as for a repository that has never released. A table
that is there still needs every key it is read for, so a misspelt key in
Tile Lite Elite's still stops the command, naming the key.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from board import profile, repo, sources
from board.tests.cases import Cases
from board.tests.cli import run
from board.tests.profiles import TECHNICAL, inside, using
from board.tests.test_profile_driven import raises_naming, repository


def without_release(directory: Path) -> Path:
    """The fake application's technical profile with its `[release]` table removed."""
    out, skipping = [], False
    for line in TECHNICAL.read_text().splitlines():
        if line.startswith("["):
            skipping = line == "[release]"
        if not skipping:
            out.append(line)
    path = directory / "app-profile.toml"
    path.write_text("\n".join(out) + "\n")
    return path


class WithoutTheReleaseTable(Cases):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.tmp = Path(self._dir.name)
        self.bare = without_release(self.tmp)
        self.top = repository(self.tmp / "app")
        # a tag that the fake profile would call a release
        subprocess.run(["git", "-C", str(self.top), "tag", "rel-0.8.0"], check=True)

    def test_the_helper_says_whether_the_table_is_there(self):
        self.expect("with", True, profile.technical().has_table("release"))
        with using(self.bare):
            self.expect("without", False, profile.technical().has_table("release"))
            self.expect("a table it has", True, profile.technical().has_table("versions"))
        malformed = self.tmp / "malformed.toml"
        malformed.write_text('application = "widget"\nrelease = "rel-"\n')
        with using(malformed):
            raises_naming(self, "release", lambda: profile.technical().has_table("release"))
        nested = self.tmp / "nested.toml"
        nested.write_text('application = "widget"\nversions = "x"\n')
        with using(nested):
            raises_naming(self, "versions", lambda: profile.technical().has_table("versions.app"))

    def test_no_tag_is_a_release_and_nothing_is_shipped_by_tag(self):
        with inside(self.top), using(self.bare):
            self.expect("release tags", [], repo.release_tags())
            self.expect("history tags", [], repo.history_tags())
            self.expect("shipped milestones", frozenset(), repo.Commits().shipped_milestones())
            self.expect("last tag", None, repo.commits().last_tag)
            self.expect("last release time", None, repo.last_release_at())

    def test_ci_is_never_red(self):
        with inside(self.top), using(self.bare):
            self.expect("not red", None, repo.ci_red_on_main())

    def test_no_comment_is_a_deploys(self):
        with using(self.bare):
            self.expect("no history announcements", [], sources.history_announcements())
            jq = sources.comment_jq("issue_url")
        self.expect("the filter has no deploy branch", False, '"deploy"' in jq)
        if not shutil.which("jq"):
            self.skipTest("jq is not installed")
        comment = [{"issue_url": "https://x/issues/7", "updated_at": "2026-09-27T10:00:00Z",
                    "created_at": "2026-09-26T08:00:00Z", "user": {"login": "u", "type": "User"},
                    "body": "Shipped in rel-0.9.0"}]
        out = subprocess.run(["jq", "-r", jq], capture_output=True, text=True, check=True,
                             input=json.dumps(comment)).stdout
        self.expect("an announcement-looking comment is the owner's", "owner", out.split("\t")[2])

    def test_a_table_that_is_there_still_needs_its_keys(self):
        path = self.tmp / "partial.toml"
        path.write_text(self.bare.read_text() + '\n[release]\nannouncement = "x"\n')
        with inside(self.top), using(path):
            raises_naming(self, "release.tag_prefix", repo.release_tags)
            raises_naming(self, "release.ci_status", repo.ci_red_on_main)

    def test_no_app_version_leaves_out_the_milestone_sections(self):
        import importlib.util
        script = Path(__file__).resolve().parents[1] / "board-check.py"
        spec = importlib.util.spec_from_file_location("board_check_under_test", script)
        check = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(check)
        bare = self.tmp / "no-versions.toml"
        bare.write_text('application = "widget"\n')
        with inside(self.top), using(bare):
            self.expect("no versions.app", None, check._app_version())
        (self.top / "Cargo.toml").write_text('version = "1.2.3"\n')
        with inside(self.top):
            self.expect("with versions.app", "1.2.3", check._app_version())

    def test_the_shell_can_ask_whether_the_table_is_there(self):
        env = {**os.environ, "PROGRAMME_PROFILE": str(self.bare)}
        # a yes/no answer is the exit status (docs/1.10): 0 yes, 1 no, and silent
        without = run("board/board-profile.py", "has", "release", env=env)
        self.expect("without", (1, ""), (without.returncode, without.stdout))
        with_ = run("board/board-profile.py", "has", "release")
        self.expect("with", (0, ""), (with_.returncode, with_.stdout))


if __name__ == "__main__":
    unittest.main()
