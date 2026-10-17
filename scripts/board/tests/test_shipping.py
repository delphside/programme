"""What reaches the image, decided once (#421).

The cases are the programme's docs/1.2's rule, not the pattern's: built into the image is a
Production Release, and everything else is not. `shipping-paths.bats` keeps
testing the functions the bash callers source, against real commits.
"""

import os
import tempfile
import unittest
from pathlib import Path

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


class TheCommand(unittest.TestCase):
    def test_paths_prints_only_the_shipping_ones(self):
        self.assertEqual("Dockerfile", run("board/board-shipping.py", "paths", stdin="docs/a.md\nDockerfile\n").stdout.strip())

    def test_an_unknown_commit_changed_nothing(self):
        self.assertEqual(1, run("board/board-shipping.py", "commit", "no-such-commit").returncode)

    def test_an_unknown_command_is_refused(self):
        self.assertEqual(2, run("board/board-shipping.py", "frobnicate").returncode)


if __name__ == "__main__":
    unittest.main()
