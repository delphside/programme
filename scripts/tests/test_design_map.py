"""design-map.py: the sources hash that lets check-docs.sh say "regenerate"
without Docker. delphside/tile-lite-elite#406.

The cases are the command's own promise: the hash moves with any change to any
file in docs/design-map/, including a new one or a rename, and does not move
when nothing changed.
"""

import importlib.util
import tempfile
import unittest
from pathlib import Path

from board.tests.cases import Cases

SPEC = importlib.util.spec_from_file_location(
    "design_map",
    Path(__file__).resolve().parents[1] / "docs" / "design-map" / "design-map.py")
design_map = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(design_map)


class SourcesHash(Cases):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.source = Path(self.tmp.name)
        (self.source / "model.dsl").write_text("workspace {}\n")
        (self.source / "views.dsl").write_text("container tle \"c\" \"d\" {}\n")
        self.before = design_map.sources_hash(self.source)

    def tearDown(self):
        self.tmp.cleanup()

    def test_unchanged_sources_keep_their_hash(self):
        self.expect("the same files hash the same", self.before,
                    design_map.sources_hash(self.source))

    def test_any_change_moves_the_hash(self):
        (self.source / "model.dsl").write_text("workspace { }\n")
        self.assertNotEqual(self.before, design_map.sources_hash(self.source))

    def test_a_new_file_moves_the_hash(self):
        (self.source / "lifecycles.md").write_text("# Lifecycles\n")
        self.assertNotEqual(self.before, design_map.sources_hash(self.source))

    def test_a_rename_moves_the_hash(self):
        (self.source / "views.dsl").rename(self.source / "other.dsl")
        self.assertNotEqual(self.before, design_map.sources_hash(self.source))

    def test_the_header_carries_a_hash_the_check_reads(self):
        found = design_map.HASH.search(design_map.header("4.2.0 Design map", self.before))
        self.expect("the hash read back from the header", self.before, found.group(1))


if __name__ == "__main__":
    unittest.main()
