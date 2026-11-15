import unittest
from pathlib import Path


class DeployTests(unittest.TestCase):
    def test_k8s_manifest(self) -> None:
        text = (Path(__file__).resolve().parents[1] / "deploy" / "k8s.yaml").read_text(encoding="utf-8")
        for expected in ("/ready", "runAsNonRoot", "PodDisruptionBudget", "NetworkPolicy", "resources"):
            self.assertIn(expected, text)
        pg = (Path(__file__).resolve().parents[1] / "deploy" / "k8s-postgres.yaml").read_text(encoding="utf-8")
        for expected in ("HorizontalPodAutoscaler", "swarmlab-pg", "/ready", "kind: Deployment"):
            self.assertIn(expected, pg)


    def test_validator(self) -> None:
        import importlib.util
        path = Path(__file__).resolve().parents[1] / "scripts" / "validate_manifests.py"
        spec = importlib.util.spec_from_file_location("validate_manifests", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.check(), [])


if __name__ == "__main__":
    unittest.main()
