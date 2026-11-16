"""The generated table in a document: delphside/tile-lite-elite#383 R18.

No network: the files are in a temporary folder.

  the block     found by its two marker lines alone, and only one of each
  the check     a stale block exits 1, a current one 0, no block or two exit 2
  the write     replaces the block, leaves the rest as it was, and twice is once"""

import importlib.util
import io
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from .cases import Cases

from board import dataflow, usage

BOARD = Path(__file__).resolve().parents[1]
BEGIN, END = dataflow.BEGIN, dataflow.END


def _command():
    spec = importlib.util.spec_from_file_location("board_vocabulary",
                                                  BOARD / "board-vocabulary.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _doc(inside="stale\n", before="# Title\n\nText.\n\n", after="\nTail.\n"):
    return f"{before}{BEGIN}\n{inside}{END}\n{after}"


class TheBlock(Cases):

    def test_a_stale_block_is_not_current_and_a_spliced_one_is(self):
        """stale, current"""
        self.expect("stale", False, dataflow.is_current(_doc()))
        self.expect("current", True, dataflow.is_current(dataflow.splice(_doc())))

    def test_text_outside_the_block_is_untouched(self):
        """outside"""
        out = dataflow.splice(_doc())
        self.expect("before", True, out.startswith("# Title\n\nText.\n\n" + BEGIN + "\n"))
        self.expect("after", True, out.endswith(END + "\n\nTail.\n"))
        self.expect("the table is inside", True,
                    dataflow.markdown() + "\n" + END in out)

    def test_no_block_and_a_doubled_block_are_errors(self):
        """usage"""
        for name, text in (("none", "# Title\n"), ("doubled", _doc() + _doc()),
                           ("no end", BEGIN + "\n"), ("backwards", END + "\n" + BEGIN + "\n")):
            with self.subTest(name), self.assertRaises(dataflow.BlockError):
                dataflow.splice(text)

    def test_only_a_line_that_is_exactly_a_marker_counts(self):
        """markers"""
        fenced = f"```\n{BEGIN}\n{END}\n```\n"
        quoted = f"see `{BEGIN}` and {END} here\n"
        self.expect("a block after a fence that shows the markers", True,
                    dataflow.is_current(dataflow.splice(fenced + _doc())))
        long_fence = f"````\n```\n{BEGIN}\n{END}\n````\n"
        info_line = f"```\n```bash\n{BEGIN}\n{END}\n```\n"
        for name, text in (("fenced", fenced), ("in a sentence", quoted),
                           ("a short fence line inside a longer fence", long_fence),
                           ("a fence line with an info string inside a fence", info_line)):
            with self.subTest(name), self.assertRaises(dataflow.BlockError):
                dataflow.splice(text)

    def test_line_endings_are_kept(self):
        """crlf"""
        text = _doc().replace("\n", "\r\n")
        out = dataflow.splice(text)
        self.expect("no bare newline added", 0, out.replace("\r\n", "").count("\n"))
        self.expect("current once spliced", True, dataflow.is_current(out))

    def test_no_trailing_newline_stays_so(self):
        """no final newline"""
        text = _doc(after="Tail.").rstrip("\n")
        self.expect("kept", False, dataflow.splice(text).endswith("\n"))

    def test_writing_twice_changes_nothing(self):
        """idempotent"""
        once = dataflow.splice(_doc())
        self.expect("second write", once, dataflow.splice(once))


class TheCommand(Cases):

    def run_it(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                status = _command().main(list(argv))
            except SystemExit as e:
                status = e.code
        return status, out.getvalue(), err.getvalue()

    def file(self, text):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / "doc.md"
        path.write_text(text, newline="")
        return path

    def test_check_exits_1_on_stale_naming_the_fix_and_0_when_current(self):
        """check"""
        path = self.file(_doc())
        status, _, err = self.run_it("--check", str(path))
        self.expect("stale: exit 1", 1, status)
        self.expect("says what fixes it", True, f"--write {path}" in err)
        self.expect("check does not write", _doc(), path.read_text())
        self.expect("write: exit 0", 0, self.run_it("--write", str(path))[0])
        self.expect("then check: exit 0", 0, self.run_it("--check", str(path))[0])

    def test_a_write_that_fails_exits_2_not_1(self):
        """write fails"""
        path = self.file(_doc())
        real_open = open

        def refusing(file, mode="r", *args, **kwargs):
            if "w" in mode:
                raise PermissionError("refused")
            return real_open(file, mode, *args, **kwargs)

        with mock.patch("builtins.open", refusing):
            status, _, err = self.run_it("--write", str(path))
        self.expect("exit 2", 2, status)
        self.expect("says it could not write", True, "cannot write" in err)
        self.expect("the file is as it was", _doc(), path.read_text())

    def test_write_twice_leaves_the_file_as_the_first_left_it(self):
        """write twice"""
        path = self.file(_doc())
        self.run_it("--write", str(path))
        first = path.read_bytes()
        self.run_it("--write", str(path))
        self.expect("same bytes", first, path.read_bytes())

    def test_no_block_two_blocks_a_missing_file_and_both_options_exit_2(self):
        """usage errors"""
        for name, argv in (
                ("no block", ("--check", str(self.file("# Title\n")))),
                ("two blocks", ("--check", str(self.file(_doc() + _doc())))),
                ("a missing file", ("--check", "/nonexistent/doc.md")),
                ("both options", ("--check", "a", "--write", "b")),
                ("an empty file name", ("--write", "")),
                ("a table and a check", ("--table", "--check", "a"))):
            status, out, _ = self.run_it(*argv)
            self.expect(f"{name}: exit 2", 2, status)
            self.expect(f"{name}: no pass on stdout", "", out)

    def test_an_option_no_module_reads_does_not_fail_the_check(self):
        """none"""
        with mock.patch.object(usage, "readers", lambda: {}):
            table = dataflow.markdown()
            path = self.file(_doc(inside=table + "\n"))
            status = self.run_it("--check", str(path))[0]
        self.expect("the table says none", True, "| none |" in table)
        self.expect("and the check passes", 0, status)
