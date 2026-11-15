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


if __name__ == "__main__":
    unittest.main()
