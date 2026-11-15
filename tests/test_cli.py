from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout

from swarmlab import __version__
from swarmlab.__main__ import main


class CliTests(unittest.TestCase):
    def test_version_and_demo(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main(["--version"]), 0)
        self.assertIn(__version__, out.getvalue())
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main(["demo"]), 0)
        self.assertIn('"stats"', out.getvalue())

    def test_help(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main([]), 0)
        self.assertIn("usage", out.getvalue())


if __name__ == "__main__":
    unittest.main()
