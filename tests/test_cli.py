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

    def test_serve_and_mcp_branches(self) -> None:
        from unittest.mock import patch
        class FakeServer:
            server_address = ("127.0.0.1", 0)
            def serve_forever(self):
                raise KeyboardInterrupt
            def server_close(self):
                pass
        with patch("swarmlab.api.build_server", return_value=FakeServer()):
            self.assertEqual(main(["serve", "--db", ":memory:"]), 0)
        with patch("swarmlab.mcp.main_stdio", return_value=None) as fake:
            self.assertEqual(main(["mcp", "--db", ":memory:"]), 0)
            fake.assert_called_once()

    def test_sigterm_handler(self) -> None:
        from unittest.mock import patch
        class FakeServer:
            server_address = ("127.0.0.1", 0)
            def serve_forever(self):
                raise KeyboardInterrupt
            def server_close(self):
                pass
            def shutdown(self):
                pass
        with patch("swarmlab.api.build_server", return_value=FakeServer()), patch("signal.signal") as sig:
            self.assertEqual(main(["serve", "--db", ":memory:"]), 0)
            handler = sig.call_args[0][1]
            handler(15, None)

    def test_run_module(self) -> None:
        import runpy
        import sys
        old = sys.argv
        sys.argv = ["swarmlab", "--version"]
        try:
            with self.assertRaises(SystemExit) as ctx:
                runpy.run_module("swarmlab", run_name="__main__")
            self.assertEqual(ctx.exception.code, 0)
        finally:
            sys.argv = old

    def test_help(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main([]), 0)
        self.assertIn("usage", out.getvalue())


if __name__ == "__main__":
    unittest.main()
