import tempfile
import unittest
from pathlib import Path

from codex_token_monitor.models import TokenUsage
from codex_token_monitor.state import StateStore


class StateTests(unittest.TestCase):
    def test_delta_and_round_trip(self):
        with tempfile.TemporaryDirectory() as temp:
            store = StateStore(Path(temp) / "state.json")
            before = TokenUsage(input=10, output=2, cached_input=3, total=12)
            after = TokenUsage(input=15, output=5, cached_input=4, total=20)
            store.put("session.jsonl", before)
            loaded = store.get("session.jsonl")
            self.assertEqual(loaded, before)
            delta, reset = after.delta(loaded)
            self.assertFalse(reset)
            self.assertEqual(delta, TokenUsage(input=5, output=3, cached_input=1, total=8))

    def test_counter_reset_uses_current_values(self):
        before = TokenUsage(input=100, output=20, cached_input=40, total=120)
        current = TokenUsage(input=5, output=1, cached_input=2, total=6)
        delta, reset = current.delta(before)
        self.assertTrue(reset)
        self.assertEqual(delta, current)


if __name__ == "__main__":
    unittest.main()

