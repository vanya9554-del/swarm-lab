from __future__ import annotations

import random
import time
import unittest

from swarmlab.store import SwarmError, SwarmStore


class FuzzTests(unittest.TestCase):
    def test_random_task_market_actions(self) -> None:
        rng = random.Random(20261116)
        store = SwarmStore(":memory:")
        try:
            agents = [f"a{i}" for i in range(4)]
            for agent in agents:
                store.register(agent, ["x"])
            ids: list[str] = []
            for _ in range(400):
                action = rng.choice(["submit", "claim", "complete", "renew", "cancel", "requeue", "expire", "noop"])
                try:
                    if action == "submit":
                        ids.append(store.submit(
                            "x", {"n": rng.randint(0, 10)},
                            priority=rng.randint(0, 3),
                            ttl_s=rng.choice([None, 0.01, 60]),
                            max_attempts=rng.choice([1, 3]),
                        )["task_id"])
                    elif action == "claim":
                        store.claim(rng.choice(agents), "x", lease_s=rng.choice([1, 60]))
                    elif action == "complete" and ids:
                        task = store.get(rng.choice(ids))
                        if task and task.get("claimed_by"):
                            store.complete(task["task_id"], task["claimed_by"], {}, fence=task["lease_epoch"])
                    elif action == "renew" and ids:
                        task = store.get(rng.choice(ids))
                        if task and task.get("claimed_by"):
                            store.renew(task["task_id"], task["claimed_by"], fence=task["lease_epoch"])
                    elif action == "cancel" and ids:
                        store.cancel(rng.choice(ids))
                    elif action == "requeue" and ids:
                        store.requeue(rng.choice(ids))
                    elif action == "expire":
                        store.expire()
                except (SwarmError, RuntimeError):
                    pass
                if rng.random() < 0.05:
                    time.sleep(0.01)
            valid = {"pending", "claimed", "completed", "failed", "cancelled", "expired"}
            for task in store.tasks(None, 1000):
                self.assertIn(task["status"], valid)
                self.assertLessEqual(task["attempts"], task["max_attempts"] + 1)
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
