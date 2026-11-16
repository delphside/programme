"""What reaches the image, decided once (#421).

The cases are the programme's docs/1.2's rule, not the pattern's: built into the image is a
Production Release, and everything else is not. `shipping-paths.bats` keeps
testing the functions the bash callers source, against real commits.
"""

import os
import subprocess
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from board import shipping
from board.shipping import application_tooling, image_paths, reaches_image, ships, touches_image, version_bump_only

from .cli import run

BUMP = ['-version = "0.9.0"', '+version = "0.9.1"']


class ReachesTheImage(unittest.TestCase):
    def test_built_in(self):
        for path in ("crates/server-game/src/app.rs", "crates/rules-shared/src/wordlists/greylist.txt",
                     "Cargo.toml", "Cargo.lock", "Dockerfile", "Caddyfile", "docker-compose.yml",
                     ".cargo/config.toml", "old-crates/first-try/src/main.rs"):
            with self.subTest(path):
                self.assertTrue(reaches_image(path))

    def test_not_built_in(self):
        for path in ("docs/4.3.3-testing-ci-and-release.md", "scripts/deploy.sh", "e2e/tests/smoke.spec.ts",
                     ".github/workflows/ci.yml", ".githooks/pre-commit", ".claude/settings.json",
                     ".cargo/audit.toml", "crates/server-game/examples/engine_timing_results.csv",
                     "crates/server-game/tests/api.rs", "crates/engine-core/benches/b.rs",
                     "crates/ui/README.md", "LICENSE", ".gitignore", ".markdownlint.json",
                     ".gitmodules", "programme", "programme/docs/1.2-change-lifecycle.md"):
            with self.subTest(path):
                self.assertFalse(reaches_image(path))


class AChange(unittest.TestCase):
    def test_one_shipping_path_among_many(self):
        self.assertEqual(["Cargo.lock"], image_paths(["docs/a.md", "Cargo.lock", "scripts/x.sh"]))

    def test_a_change_that_touched_nothing_reaches_nothing(self):
        self.assertFalse(touches_image([]))


class AVersionBump(unittest.TestCase):
    def test_cargo_toml_alone_version_lines_only(self):
        self.assertTrue(version_bump_only(["Cargo.toml"], BUMP))

    def test_with_cargo_lock_version_lines_only(self):
        self.assertTrue(version_bump_only(["Cargo.lock", "Cargo.toml"], BUMP * 8))

    def test_a_dependency_line_is_not_a_bump(self):
        self.assertFalse(version_bump_only(["Cargo.toml"], BUMP + ['+anyhow = "1"']))

    def test_another_file_alongside_is_not_a_bump(self):
        self.assertFalse(version_bump_only(["Cargo.toml", "crates/api/src/lib.rs"], BUMP))

    def test_no_changed_lines_is_not_a_bump(self):
        self.assertFalse(version_bump_only(["Cargo.toml"], []))

    def test_a_two_part_version_is_not_ours(self):
        self.assertFalse(version_bump_only(["Cargo.toml"], ['+version = "1.0"']))


class Ships(unittest.TestCase):
    def test_the_post_release_bump_ships_nothing(self):
        self.assertFalse(ships(["Cargo.lock", "Cargo.toml"], BUMP))

    def test_a_dockerfile_change_ships(self):
        self.assertTrue(ships(["Dockerfile"], []))

    def test_a_document_ships_nothing(self):
        self.assertFalse(ships(["docs/a.md"], []))

    def test_a_crate_change_ships(self):
        self.assertTrue(ships(["crates/ui/src/app.rs"], []))


class ApplicationTooling(unittest.TestCase):
    """The folders are the profile's `scripts.groups` (the fake's are `make/` and
    `ship/`), so Tile Lite Elite's `develop/` is not one here: R10 reads the
    profile and holds no list."""

    def test_the_paths_in_the_profiles_folders(self):
        self.assertEqual(["scripts/make/a.sh", "scripts/ship/deep/b.sh"],
                         application_tooling(["docs/a.md", "scripts/make/a.sh", "scripts/ship/deep/b.sh"]))

    def test_other_script_paths_are_not_application_tooling(self):
        for path in ("scripts/a.sh", "scripts/develop/a.sh", "scripts/tests/t.bats", "scripts/makefile.sh",
                     "programme/scripts/board/board-check.py", ".githooks/pre-commit"):
            with self.subTest(path):
                self.assertEqual([], application_tooling([path]))

    def test_the_command_prints_them(self):
        out = run("board/board-shipping.py", "application-tooling", stdin="docs/a.md\nscripts/ship/x.sh\n")
        self.assertEqual((0, "scripts/ship/x.sh\n"), (out.returncode, out.stdout))

    def test_a_profile_without_the_key_is_not_an_answer(self):
        # exit 70, so the pre-commit hook refuses rather than reading "none"
        bare = Path(tempfile.mkdtemp()) / "bare.toml"
        bare.write_text('application = "widget"\n')
        self.addCleanup(bare.unlink)
        out = run("board/board-shipping.py", "application-tooling", stdin="scripts/ship/x.sh\n",
                  env={**os.environ, "PROGRAMME_PROFILE": str(bare)})
        self.assertEqual(70, out.returncode)
        self.assertIn("scripts.groups", out.stderr)


class AProgrammePinMove(unittest.TestCase):
    """T6: a move of the `programme` pin ships only where it changes the deploy steps the payload
    carries (`scripts/deliver/payload/`, `scripts/deliver/lib/`) between the old pin and the new."""

    GIT = ["git", "-c", "user.name=T", "-c", "user.email=t@e.test", "-c", "commit.gpgsign=false"]

    def git(self, where, *args):
        return subprocess.run([*self.GIT, "-C", str(where), *args], check=True, capture_output=True,
                              text=True).stdout.strip()

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.app = Path(tmp.name) / "app"
        self.prog = self.app / "programme"
        self.app.mkdir()
        self.git(self.app, "init", "-q", "-b", "main")
        self.git(self.app, "init", "-q", "-b", "main", "programme")
        self.programme_commit({"docs/a.md": "one"})
        (self.app / "Dockerfile").write_text("FROM scratch\n")
        self.git(self.app, "add", "-A")
        self.git(self.app, "commit", "-q", "-m", "base")
        self.base = self.git(self.app, "rev-parse", "HEAD")

    def programme_commit(self, files):
        for name, text in files.items():
            (self.prog / name).parent.mkdir(parents=True, exist_ok=True)
            (self.prog / name).write_text(text)
        self.git(self.prog, "add", "-A")
        self.git(self.prog, "commit", "-q", "-m", "change")

    def moved(self, files):
        """Move the pin over a programme commit changing `files`; the app's commit moving it."""
        self.programme_commit(files)
        self.git(self.app, "add", "programme")
        self.git(self.app, "commit", "-q", "-m", "move the pin")
        return self.git(self.app, "rev-parse", "HEAD")

    def env(self, opted):
        """The technical profile the commands read: the fixture's, with `ships.carries_payload` or without."""
        base = Path(os.environ["PROGRAMME_PROFILE"])
        if not opted:
            return None
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "app-profile.toml"
        path.write_text(base.read_text().replace("[ships]\n", "[ships]\ncarries_payload = true\n", 1))
        return {**os.environ, "PROGRAMME_PROFILE": str(path)}

    def answers(self, head, opted=True):
        """Exit statuses of `range`, `commit` and `ships` for the move."""
        env = self.env(opted)
        return [run("board/board-shipping.py", "-C", str(self.app), cmd, *args, env=env).returncode
                for cmd, args in (("range", (self.base, head)), ("commit", (head,)), ("ships", (head,)))]

    def staged_paths(self, files, opted=True):
        """What `paths` prints for a staged pin move over a programme commit changing `files`."""
        self.programme_commit(files)
        self.git(self.app, "add", "programme")
        return run("board/board-shipping.py", "-C", str(self.app), "paths", stdin="programme\n",
                   env=self.env(opted)).stdout.strip()

    def test_a_pin_move_changing_only_documents_ships_nothing(self):
        self.assertEqual([1, 1, 1], self.answers(self.moved({"docs/b.md": "two", "scripts/board/x.py": "x"})))

    def test_a_pin_move_changing_the_payload_ships(self):
        self.assertEqual([0, 0, 0], self.answers(self.moved({"scripts/deliver/payload/deploy": "new"})))

    def test_a_pin_move_changing_a_library_the_payload_carries_ships(self):
        for name in ("common.sh", "toml.sh", "toml.awk"):
            with self.subTest(name):
                self.assertEqual([0, 0, 0], self.answers(self.moved({f"scripts/deliver/lib/{name}": name + "x"})))

    def test_a_pin_move_changing_a_library_the_payload_does_not_carry_ships_nothing(self):
        self.assertEqual([1, 1, 1], self.answers(self.moved({"scripts/deliver/lib/registry.sh": "new"})))

    def test_without_the_key_the_profile_decides_the_pin_and_a_payload_move_ships_nothing(self):
        head = self.moved({"scripts/deliver/payload/deploy": "new"})
        self.assertEqual([1, 1, 1], self.answers(head, opted=False))

    def test_the_pre_commit_paths_judge_the_staged_move_where_the_key_is_set(self):
        self.assertEqual("programme", self.staged_paths({"scripts/deliver/payload/deploy": "new"}))

    def test_the_pre_commit_paths_pass_a_staged_documents_move(self):
        self.assertEqual("", self.staged_paths({"docs/b.md": "two"}))

    def test_the_pre_commit_paths_without_the_key_pass_a_payload_move(self):
        self.assertEqual("", self.staged_paths({"scripts/deliver/payload/deploy": "new"}, opted=False))

    def test_the_pin_move_alongside_a_shipping_path_still_ships_for_the_path(self):
        self.programme_commit({"docs/b.md": "two"})
        (self.app / "Dockerfile").write_text("FROM other\n")
        self.git(self.app, "add", "-A")
        self.git(self.app, "commit", "-q", "-m", "both")
        self.assertEqual([0, 0, 0], self.answers(self.git(self.app, "rev-parse", "HEAD")))

    def test_a_pin_that_cannot_be_compared_ships(self):
        self.moved({"docs/b.md": "two"})
        with mock.patch.object(shipping.repo, "programme_paths_between", return_value=None):
            self.assertTrue(shipping.pin_ships("a" * 40, "b" * 40))


class TheCommand(unittest.TestCase):
    def test_paths_prints_only_the_shipping_ones(self):
        self.assertEqual("Dockerfile", run("board/board-shipping.py", "paths", stdin="docs/a.md\nDockerfile\n").stdout.strip())

    def test_an_unknown_commit_changed_nothing(self):
        self.assertEqual(1, run("board/board-shipping.py", "commit", "no-such-commit").returncode)

    def test_an_unknown_command_is_refused(self):
        self.assertEqual(2, run("board/board-shipping.py", "frobnicate").returncode)


if __name__ == "__main__":
    unittest.main()
