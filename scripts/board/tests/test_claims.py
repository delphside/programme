"""`board/claims.py`: the `Claims:` line, and which pull requests share a file. No network."""

import unittest

from board.claims import Pull, against, pairs, parse_claims, shared, touches


class TheClaimsLine(unittest.TestCase):
    def test_bare_paths(self):
        self.assertEqual(("a.md", "b/c.py"), parse_claims("Refs #1\n\nClaims: a.md, b/c.py\n"))

    def test_backticked_paths(self):
        self.assertEqual(("a.md", "b/c.py"), parse_claims("Claims: `a.md`, `b/c.py`"))

    def test_a_trailing_slash_is_a_directory_prefix(self):
        self.assertEqual(("docs/", "x.py"), parse_claims("Claims: `docs/`, x.py"))

    def test_no_line_claims_nothing(self):
        for body in ("", None, "Refs #1\nno claims here", "The Claims: are in the text", "Claims:"):
            self.assertEqual((), parse_claims(body), body)

    def test_the_first_of_several_lines_counts(self):
        self.assertEqual(("a.md",), parse_claims("Claims: a.md\nClaims: b.md\n"))

    def test_a_path_with_a_space_is_not_supported(self):
        self.assertEqual(("my", "file.md"), parse_claims("Claims: my file.md"))

    def test_a_leading_slash_is_the_repository_root(self):
        self.assertEqual(("docs/b.md",), parse_claims("Claims: /docs/b.md"))
        self.assertTrue(touches("/docs/", "docs/b.md"))

    def test_repeats_and_dot_slash_are_dropped(self):
        self.assertEqual(("a.md",), parse_claims("Claims: a.md, ./a.md,"))

    def test_text_in_an_html_comment_claims_nothing(self):
        for body in ("<!-- Claims: a.md -->", "<!--\nClaims: a.md, b.md\n-->\nno claims", "<!--\nClaims: a.md"):
            self.assertEqual((), parse_claims(body), body)

    def test_a_real_line_after_a_comment_is_the_first(self):
        body = "<!-- say it as Claims: path, path -->\nClaims: real.md\n"
        self.assertEqual(("real.md",), parse_claims(body))

    def test_the_line_may_be_indented(self):
        self.assertEqual(("a.md",), parse_claims("text\n  Claims: a.md"))


class TwoPaths(unittest.TestCase):
    def test_equal_paths_touch(self):
        self.assertTrue(touches("a.md", "a.md"))

    def test_a_directory_holds_what_is_below_it(self):
        self.assertTrue(touches("docs/", "docs/1.2.md"))
        self.assertTrue(touches("docs/1.2.md", "docs/"))

    def test_neighbours_do_not_touch(self):
        self.assertFalse(touches("docs/", "docs2/a.md"))
        self.assertFalse(touches("docs/1.2.md", "docs/1.20.md"))
        self.assertFalse(touches("docs", "docs/a.md"))

    def test_the_more_specific_path_is_reported(self):
        self.assertEqual(("docs/1.2.md",), shared(["docs/"], ["docs/1.2.md", "x"]))


def pull(number, changed=(), claimed=(), repo="o/r", title=None):
    return Pull(repo, number, title or f"title {number}", tuple(changed), tuple(claimed))


class TheOverlap(unittest.TestCase):
    def test_a_changed_file_overlaps(self):
        found = against(["a.md"], [pull(1, changed=["a.md"]), pull(2, changed=["b.md"])])
        self.assertEqual([(1, ("a.md",))], [(p.number, c) for p, c in found])

    def test_a_claimed_file_overlaps(self):
        found = against(["a.md", "z"], [pull(1, claimed=["a.md"])])
        self.assertEqual([(1, ("a.md",))], [(p.number, c) for p, c in found])

    def test_a_claimed_directory_overlaps_what_is_inside(self):
        found = against(["scripts/board/x.py"], [pull(1, claimed=["scripts/board/"])])
        self.assertEqual((("scripts/board/x.py",)), found[0][1])

    def test_nothing_in_common_is_nothing(self):
        self.assertEqual([], against(["a.md"], [pull(1, changed=["b.md"])]))

    def test_pairs_share_a_file_in_one_repository(self):
        found = pairs([pull(3, changed=["a"]), pull(1, claimed=["a", "b"]), pull(2, changed=["c"])])
        self.assertEqual([(1, 3, ("a",))], [(a.number, b.number, c) for a, b, c in found])

    def test_pairs_in_different_repositories_do_not_overlap(self):
        self.assertEqual([], pairs([pull(1, changed=["a"], repo="o/r"), pull(2, changed=["a"], repo="o/s")]))

    def test_a_pull_request_does_not_overlap_itself(self):
        self.assertEqual([], pairs([pull(1, changed=["a"], claimed=["a"])]))


if __name__ == "__main__":
    unittest.main()
