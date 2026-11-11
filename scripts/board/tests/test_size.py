"""The size limit on documents and issue bodies. The programme's docs/1.5.

No network and no files: paths and sizes only.

  limit       over the limit is reported, at the limit is not, largest first
  measure     bytes of UTF-8, as a file's size is
  exempt      logs, reports, fixtures and the design map are left out;
              change documents are measured (owner, 2026-11-11)"""

from .cases import Cases

from board.size import LIMIT_BYTES, Oversized, exempt, oversized, render, size_of


class TheSizeLimit(Cases):

    def test_over_the_limit_is_reported_largest_first(self):
        """over the limit"""
        got = oversized([("a.md", LIMIT_BYTES), ("b.md", LIMIT_BYTES + 1),
                         ("c.md", 3 * LIMIT_BYTES), ("d.md", 10)])
        self.expect("only those over the limit, largest first",
                    [Oversized("c.md", 3 * LIMIT_BYTES), Oversized("b.md", LIMIT_BYTES + 1)],
                    got)
        self.expect("the limit is about 25 KB", 25 * 1024, LIMIT_BYTES)

    def test_size_is_bytes_of_utf8(self):
        """measured in bytes"""
        self.expect("a non-ASCII character counts as its bytes", 2, size_of("é"))

    def test_the_report_names_each_item_and_says_ok_when_none(self):
        """the report"""
        text = render([Oversized("docs/1.2-change-lifecycle.md", 113180)], "documents",
                      colour=False)
        self.expect("names the document in full, with its size", True,
                    "111 KB  docs/1.2-change-lifecycle.md" in text)
        self.expect("says so when nothing is over", True,
                    "ok no issue bodies over the limit" in render([], "issue bodies", colour=False))

    def test_what_the_limit_leaves_out(self):
        """exemptions"""
        for path in ("records/2.4-weekly-digest/PRG_WD_2026_W44.md",
                     "applications/tile-lite-elite/3.1.3-capacity-plan/TLE_CP_2026_10.md",
                     "applications/tile-lite-elite/3.1.1-delivery-log.md",
                     "sizing/results/2026-10-27-report.md",
                     "scripts/board/tests/fixtures/body.md",
                     "docs/4.2.0-design-map.md"):
            self.expect(f"left out: {path}", True, exempt(path))
        for path in ("docs/1.2-change-lifecycle.md", "CLAUDE.md",
                     ".claude/skills/triage/SKILL.md",
                     "records/2.5-changes/README.md",
                     "applications/tile-lite-elite/3.1.7-changes/ops/benchmark-runbook.md",
                     "docs/4.4.3-api-schema.md",
                     "records/2.5-changes/programme-tooling/117-generic-deliver-tool/design.md",
                     "applications/tile-lite-elite/3.1.7-changes/workstreams/x/71-design.md"):
            self.expect(f"measured: {path}", False, exempt(path))
