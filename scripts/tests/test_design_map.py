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


MERMAID = """graph TB
  linkStyle default fill:#ffffff

  subgraph diagram ["Component View"]
    13["<div>Games</div>"]
    14["<div>Roster</div>"]
    21["<div>Session</div>"]

    14-. "<div>sends seat messages</div><div style='font-size: 70%'></div>" .->13
    14-. "<div>changes the seats of<br />the GameSession</div><div style='font-size: 70%'></div>" .->21
    13-. "<div>applies the move</div><div style='font-size: 70%'></div>" .->21
  end
"""

WORKSPACE = {"model": {"softwareSystems": [{"containers": [{"components": [
    {"id": "14", "relationships": [
        {"id": "40", "sourceId": "14", "destinationId": "21",
         "description": "changes the seats of the GameSession",
         "tags": "Relationship,removed,wp:268"},
        {"id": "41", "sourceId": "14", "destinationId": "13",
         "description": "sends seat messages", "tags": "Relationship,new,wp:268"}]},
    {"id": "13", "relationships": [
        {"id": "42", "sourceId": "13", "destinationId": "21",
         "description": "applies the move", "tags": "Relationship"}]},
]}]}]}, "views": {"componentViews": [{"relationships": [{"id": "40"}]}]}}


class RelationshipStyles(Cases):
    """Gap 2: a tagged relationship is coloured and its label says its state."""

    def setUp(self):
        self.out = design_map.style_relationships(MERMAID, WORKSPACE)
        self.lines = [x.strip() for x in self.out.splitlines()]

    def test_the_label_starts_with_the_state(self):
        self.assertIn('14-. "<div>new: sends seat messages</div>', self.out)
        self.assertIn('"<div>removed: changes the seats of<br />the GameSession</div>',
                      self.out)

    def test_an_untagged_relationship_is_left_as_it_was(self):
        self.assertIn('13-. "<div>applies the move</div>', self.out)

    def test_each_tagged_edge_gets_a_link_style_at_its_index(self):
        self.assertIn("linkStyle 0 stroke:#1a7f37,stroke-width:2px", self.lines)
        self.assertIn("linkStyle 1 stroke:#cf222e,stroke-width:2px", self.lines)

    def test_an_untagged_edge_gets_no_link_style(self):
        self.assertFalse([x for x in self.lines if x.startswith("linkStyle 2")])

    def test_changed_is_amber(self):
        workspace = {"model": {"people": [{"relationships": [
            {"id": "1", "sourceId": "13", "destinationId": "21",
             "description": "applies the move", "tags": "Relationship,changed"}]}]}}
        out = design_map.style_relationships(MERMAID, workspace)
        self.assertIn("linkStyle 2 stroke:#9a6700,stroke-width:2px", out)
        self.assertIn("<div>changed: applies the move</div>", out)

    def test_a_map_with_no_tags_comes_out_unchanged(self):
        untagged = {"model": {"people": [{"relationships": [
            {"id": "1", "sourceId": "13", "destinationId": "21",
             "description": "applies the move", "tags": "Relationship"}]}]}}
        self.expect("the text", MERMAID, design_map.style_relationships(MERMAID, untagged))


BLOCK = """workspace extends model.dsl {
    model {
        !element tle.server.games {
            tags "changed" "wp:268"
        }
        !element tle.server {
            bot = component "Bot" "An engine seat." {
                tags "new" "wp:268"
            }
            notes = component "Notifications" "Pings." {
                tags "new" "wp:270"
                properties {
                    "artefact" "crates/x"
                }
            }
        }
        push = softwareSystem "Push" "Web Push." {
            tags "External" "new" "wp:270"
        }
        tle.server.bot -> tle.server.games "submits" {
            tags "new" "wp:268"
        }
        !relationships "tle.server.roster -> tle.server.session" {
            tags "removed" "wp:268"
        }
        tle.server.notes -> push "pings"  {
            tags "new" "wp:270"
        }
    }
    views {
        component tle.server "old" "A hand-written view" {
            include *
        }
        !include views.dsl
    }
}
"""


class Entries(Cases):
    """Gap 3: an entry belongs to exactly one work package."""

    def test_packages_come_in_number_order(self):
        self.expect("the packages", [268, 270], design_map.entry_packages(BLOCK))

    def test_a_package_keeps_only_its_own_entries(self):
        text, _ = design_map.package_entries(BLOCK, 268)
        self.assertIn("tle.server.games", text)
        self.assertIn("bot = component", text)
        self.assertIn("tle.server.roster -> tle.server.session", text)
        self.assertNotIn("notes", text)
        self.assertNotIn("push", text)
        self.assertNotIn("wp:270", text)

    def test_the_wrapper_holds_only_the_kept_children(self):
        text, _ = design_map.package_entries(BLOCK, 270)
        self.assertIn("!element tle.server {", text)
        self.assertIn("notes = component", text)
        self.assertIn('"artefact" "crates/x"', text)
        self.assertNotIn("bot = component", text)

    def test_a_wrapper_with_no_kept_child_is_dropped(self):
        text, _ = design_map.package_entries(BLOCK.replace('"wp:270"', '"wp:268"', 1), 270)
        self.assertNotIn("!element tle.server {", text)

    def test_the_views_are_not_part_of_an_entry(self):
        text, _ = design_map.package_entries(BLOCK, 268)
        self.assertNotIn("old", text)
        self.assertNotIn("include", text)

    def test_the_names_are_the_elements_and_both_ends_of_each_relationship(self):
        _, names = design_map.package_entries(BLOCK, 268)
        self.expect("names", ["tle.server.games", "tle.server.bot",
                              "tle.server.roster", "tle.server.session"], names)

    def test_an_entry_with_two_package_tags_is_rejected(self):
        bad = BLOCK.replace('tags "changed" "wp:268"', 'tags "changed" "wp:268" "wp:270"')
        with self.assertRaisesRegex(design_map.ChangeError, "line 4"):
            design_map.entry_packages(bad)

    def test_an_entry_with_no_package_tag_is_rejected(self):
        bad = BLOCK.replace('tags "changed" "wp:268"', 'tags "changed"')
        with self.assertRaisesRegex(design_map.ChangeError, "line 4"):
            design_map.entry_packages(bad)

    def test_an_entry_with_no_tags_is_rejected(self):
        bad = BLOCK.replace('            tags "changed" "wp:268"\n', "")
        with self.assertRaisesRegex(design_map.ChangeError, "line 3"):
            design_map.entry_packages(bad)

    def test_a_wrapped_child_with_no_package_tag_is_rejected(self):
        bad = BLOCK.replace('tags "new" "wp:268"\n            }\n            notes',
                            'tags "new"\n            }\n            notes')
        with self.assertRaisesRegex(design_map.ChangeError, "line 8"):
            design_map.entry_packages(bad)


class Views(Cases):
    """Gap 3: a Component view of the container, else a Container view."""

    def test_components_of_one_container_make_a_component_view_of_it(self):
        self.expect("kind", ("component", "tle.server"),
                    design_map.view_kind(["tle.server.games", "tle.server.bot"]))

    def test_other_elements_do_not_change_the_container(self):
        self.expect("kind", ("component", "tle.server"),
                    design_map.view_kind(["tle.server.notes", "push", "tle.db"]))

    def test_components_of_two_containers_make_a_container_view(self):
        self.expect("kind", ("container", "tle"),
                    design_map.view_kind(["tle.server.games", "tle.web.page"]))

    def test_the_view_includes_every_name(self):
        dsl = design_map.package_view(268, "WP A, changing a game",
                                      ["tle.server.games", "tle.server.bot", "push"])
        self.assertIn('component tle.server "wp-268" "WP A, changing a game"', dsl)
        for name in ("tle.server.games", "tle.server.bot", "push"):
            self.assertIn(name, dsl)

    def test_a_container_view_includes_the_containers_not_the_components(self):
        dsl = design_map.package_view(5, "T", ["tle.server.games", "tle.web.page", "resend"])
        self.assertIn('container tle "wp-5" "T"', dsl)
        self.assertIn("tle.server", dsl)
        self.assertIn("tle.web", dsl)
        self.assertNotIn("tle.server.games", dsl)
        self.assertIn("resend", dsl)

    def test_a_heading_naming_the_package_titles_it(self):
        text = "# P\n\n## WP A, #268 Core Game\n\ntext\n\n```text\n# not a heading #270\n```\n"
        self.expect("titles", {268: "WP A, #268 Core Game"}, design_map.package_titles(text))


class ChangeCheck(Cases):
    """Gap 3: --check compares the hash, with no Docker."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.source = root / "design-map"
        self.source.mkdir()
        (self.source / "model.dsl").write_text("workspace {}\n")
        self.change = root / "9-map-change.md"
        self.change.write_text("# P: the map change\n")
        self.target = root / "9-map-diagrams.md"
        self.target.write_text(design_map.change_header(
            "P: the map change, drawn", self.change.name,
            design_map.change_hash(self.change, self.source)))

    def tearDown(self):
        self.tmp.cleanup()

    def current(self):
        return design_map.change_is_current(self.change, self.source, self.target)

    def test_unchanged_sources_are_current(self):
        self.assertTrue(self.current())

    def test_a_changed_change_file_is_stale(self):
        self.change.write_text("# P: the map change\n\nmore\n")
        self.assertFalse(self.current())

    def test_a_changed_map_is_stale(self):
        (self.source / "model.dsl").write_text("workspace { }\n")
        self.assertFalse(self.current())

    def test_a_missing_diagrams_file_is_stale(self):
        self.target.unlink()
        self.assertFalse(self.current())


if __name__ == "__main__":
    unittest.main()
