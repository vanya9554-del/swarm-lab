from __future__ import annotations

import unittest

from swarmlab.api import ROUTES
from swarmlab.openapi import spec


class ContractTests(unittest.TestCase):
    def test_routes_in_openapi(self) -> None:
        paths = spec()["paths"]
        missing = []
        for method, path in ROUTES:
            entry = paths.get(path)
            if not entry or method.lower() not in entry:
                missing.append((method, path))
        self.assertEqual(missing, [])

    def test_openapi_has_core_paths(self) -> None:
        paths = spec()["paths"]
        for path in ("/v1/tasks/claim", "/v1/tasks/{task_id}/complete", "/mcp"):
            self.assertIn(path, paths)


if __name__ == "__main__":
    unittest.main()
