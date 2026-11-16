"""What counts as an answer under a heading (delphside/programme#103)."""

import unittest

from board.model import RawIssue, classify
from board.obligations import headings_answered, is_answer, section_has_text

TABLE = "| Check | Result |\n| --- | --- |"


class WhatIsAnAnswer(unittest.TestCase):
    def test_header_and_separator_only_is_not_an_answer(self):
        self.assertFalse(is_answer(TABLE))

    def test_aligned_separator_only_is_not_an_answer(self):
        self.assertFalse(is_answer("| A | B |\n|:---|---:|"))

    def test_a_data_row_makes_it_an_answer(self):
        self.assertTrue(is_answer(TABLE + "\n| lint | passes |"))

    def test_prose_is_an_answer(self):
        self.assertTrue(is_answer("See the design document."))

    def test_placeholders_and_empty_are_not(self):
        for body in ("", "  \n", "none", "None", "n/a", "TBD", "tbc", "- none"):
            with self.subTest(body=body):
                self.assertFalse(is_answer(body))

    def test_prose_before_a_table_still_counts(self):
        self.assertTrue(is_answer("Below.\n\n" + TABLE))

    def test_a_dashed_data_row_is_data(self):
        self.assertTrue(is_answer(TABLE + "\n| lint | passes |\n| - | - |"))


def _project(body):
    return classify(RawIssue(1, "t", "OPEN", body, "Project", {}, (), None, None,
                             frozenset()))


class TheObligationsUseIt(unittest.TestCase):
    def test_a_skeleton_table_does_not_answer_a_heading(self):
        check = headings_answered("Deliveries")
        self.assertFalse(check(_project("## Deliveries\n\n" + TABLE)))
        self.assertTrue(check(_project("## Deliveries\n\n" + TABLE + "\n| 1 | it |")))

    def test_a_skeleton_table_is_no_text(self):
        check = section_has_text("Dependencies and related work")
        self.assertFalse(check(_project("## Dependencies and related work\n\n" + TABLE)))


if __name__ == "__main__":
    unittest.main()
