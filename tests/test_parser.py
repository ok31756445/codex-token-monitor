import json
import tempfile
import unittest
from pathlib import Path

from codex_token_monitor.parser import SessionLogError, find_latest_session, parse_session


class ParserTests(unittest.TestCase):
    def write_jsonl(self, directory: Path, records: list[object]) -> Path:
        path = directory / "rollout.jsonl"
        lines = [json.dumps(record) if not isinstance(record, str) else record for record in records]
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def test_current_format_uses_thread_total_without_double_counting(self):
        with tempfile.TemporaryDirectory() as temp:
            path = self.write_jsonl(
                Path(temp),
                [
                    {
                        "type": "session_meta",
                        "payload": {"session_id": "s1", "cli_version": "0.167.0", "context_window": 1000},
                    },
                    {
                        "type": "token_usage_record",
                        "payload": {
                            "usage": {"input_tokens": 10, "output_tokens": 2, "cached_input_tokens": 3},
                            "thread_token_usage": {
                                "input_tokens": 100,
                                "output_tokens": 20,
                                "cached_input_tokens": 30,
                                "total_tokens": 120,
                            },
                        },
                    },
                    {
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "info": {
                                "total_token_usage": {
                                    "input_tokens": 100,
                                    "output_tokens": 20,
                                    "cached_input_tokens": 30,
                                    "total_tokens": 120,
                                },
                                "model_context_window": 1000,
                            },
                        },
                    },
                ],
            )
            stats = parse_session(path)
            self.assertEqual(stats.usage.total, 120)
            self.assertEqual(stats.usage.cached_input, 30)
            self.assertEqual(stats.session_id, "s1")
            self.assertEqual(stats.context_window, 1000)

    def test_legacy_token_count_and_malformed_line(self):
        with tempfile.TemporaryDirectory() as temp:
            path = self.write_jsonl(
                Path(temp),
                [
                    "not-json",
                    {
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "info": {
                                "total_token_usage": {
                                    "input_tokens": 9,
                                    "output_tokens": 4,
                                    "cached_input_tokens": 2,
                                }
                            },
                        },
                    },
                ],
            )
            stats = parse_session(path)
            self.assertEqual(stats.usage.total, 13)
            self.assertEqual(stats.invalid_lines, 1)

    def test_api_style_cached_tokens(self):
        with tempfile.TemporaryDirectory() as temp:
            path = self.write_jsonl(
                Path(temp),
                [
                    {
                        "usage": {
                            "input_tokens": 8,
                            "input_tokens_details": {"cached_tokens": 5},
                            "output_tokens": 3,
                            "total_tokens": 11,
                        }
                    },
                    {
                        "usage": {
                            "input_tokens": 2,
                            "input_tokens_details": {"cached_tokens": 1},
                            "output_tokens": 1,
                            "total_tokens": 3,
                        }
                    },
                ],
            )
            stats = parse_session(path)
            self.assertEqual(stats.usage.cached_input, 6)
            self.assertEqual(stats.usage.total, 14)
            self.assertEqual(stats.source, "summed_incremental_usage")

    def test_last_usage_alone_is_not_mislabeled_as_session_total(self):
        with tempfile.TemporaryDirectory() as temp:
            path = self.write_jsonl(
                Path(temp),
                [
                    {
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "info": {"last_token_usage": {"input_tokens": 9, "output_tokens": 1}},
                        },
                    }
                ],
            )
            with self.assertRaises(SessionLogError):
                parse_session(path)

    def test_unknown_format_has_clear_error(self):
        with tempfile.TemporaryDirectory() as temp:
            path = self.write_jsonl(Path(temp), [{"type": "future_format", "payload": {}}])
            with self.assertRaises(SessionLogError):
                parse_session(path)

    def test_find_latest_session_recurses(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            older = root / "2025" / "old.jsonl"
            newer = root / "2026" / "new.jsonl"
            older.parent.mkdir()
            newer.parent.mkdir()
            older.write_text("{}", encoding="utf-8")
            newer.write_text("{}", encoding="utf-8")
            older.touch()
            newer.touch()
            older_time = older.stat().st_mtime - 10
            import os

            os.utime(older, (older_time, older_time))
            self.assertEqual(find_latest_session(root), newer)


if __name__ == "__main__":
    unittest.main()

