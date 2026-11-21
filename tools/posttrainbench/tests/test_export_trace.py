"""Fixtures mirror Penguin's core/test/fixtures/trace-bytes.jsonl and AMSP types.

No Penguin runtime, credentials, network, or third-party packages are needed.
Run: python3 -m unittest discover -s tools/posttrainbench/tests -p test_export_trace.py
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "export_trace.py"
SPEC = importlib.util.spec_from_file_location("penguin_export_trace", SCRIPT)
exporter = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = exporter
SPEC.loader.exec_module(exporter)


def record(kind, payload, second=0):
    return {"timestamp": f"2026-10-23T10:00:{second:02d}.000Z", "type": kind, "payload": payload}


def meta(session="session-main", agent="coder", second=0):
    return record("session_meta", {
        "session_id": session,
        "provider": "loopback",
        "model_id": "pinned-model",
        "model_context_window": 128000,
        "system_prompt": "You are a fixture.\nPreserve [REDACTED] and <redacted>.",
        "agent_state": f"/data/demo/agents/{agent}/agent_state",
        "workspace": "/work",
        "source": "cli" if session == "session-main" else "subagent",
    }, second)


def text(value, second=1, role="user"):
    return record("model_msg", {"type": "text", "role": role, "text": value}, second)


def event(kind, second=0, **fields):
    return record("event_msg", {"type": kind, **fields}, second)


class ExportTraceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / "traces"
        self.root.mkdir()
        self.output = self.base / "penguin-transcript.txt"

    def shard(self, records, agent="coder", session="session-main", index=1):
        path = self.root / agent / "2026-10-23" / f"{session}_{index:03d}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records), encoding="utf-8")
        return path

    def export(self):
        result = exporter.export_trace(self.root, self.output)
        self.assertEqual(result, self.output)
        return self.output.read_text(encoding="utf-8")

    def test_preserves_prompt_messages_tools_events_and_all_text_content(self):
        arguments = '{"cmd":"printf token=training-token; cat /work/result.txt"}'
        output = "line one\nline two\n  spaces retained  \n密码 [REDACTED]"
        rows = [
            meta(), event("task_begin"), text("Train the model.\nThen evaluate it."),
            event("tool_list_ready", tools=[{"name": "exec_command", "description": "Run.\nWait."}]),
            event("request_begin", thinking_level="medium"),
            record("model_msg", {"type": "thinking", "role": "assistant", "thinking": "Inspect first.\nThen act.", "fidelity": {"signature": "unchanged-signature"}}),
            record("model_msg", {"type": "tool_call", "role": "assistant", "name": "exec_command", "arguments": arguments, "tool_call_id": "call_1"}),
            event("request_end", status="retryable", error_message="busy\ntry again"),
            record("model_msg", {"type": "tool_call_output", "role": "user", "output": output, "tool_call_id": "call_1", "status": "completed", "images": ["data:image/png;base64,aW1hZ2U="]}),
            text("Training is complete.", second=3, role="assistant"),
            event("hook", output={"content": [{"type": "text", "text": "nested content\nnot dropped"}]}),
            event("future_event", content="Unknown event text retained."),
        ]
        self.shard(rows)
        transcript = self.export()
        for expected in (arguments, output, "Train the model.\nThen evaluate it.",
                         "Inspect first.\nThen act.", "unchanged-signature", "call_1",
                         "Training is complete.", "nested content\nnot dropped",
                         "Unknown event text retained.", "busy\ntry again", "Run.\nWait.",
                         "data:image/png;base64,aW1hZ2U=", "[REDACTED]", "<redacted>"):
            self.assertIn(expected, transcript)
        self.assertIn("12 records", transcript)
        self.assertEqual(transcript.count("=== Record "), len(rows))
        self.assertIn("Source: coder/2026-10-23/session-main_001.jsonl:1", transcript)
        self.assertIn("payload.system_prompt", transcript)
        self.assertIn("agent=coder", transcript)
        self.assertIn("2026-10-23T10:00:03.000Z", transcript)

    def test_nested_subagents_and_timestamp_merge_are_deterministic(self):
        self.shard([
            meta(), text("PARENT_START", second=1),
            event("subagent", second=2, session_id="session-child"),
            text("PARENT_END", second=9, role="assistant"),
        ])
        self.shard([
            meta("session-child", "worker", second=2), text("CHILD_START", second=3),
            event("subagent", second=4, session_id="session-grandchild"),
            text("CHILD_END", second=7, role="assistant"),
        ], agent="worker", session="session-child")
        self.shard([
            meta("session-grandchild", "worker", second=4),
            text("GRANDCHILD_ANSWER", second=5, role="assistant"),
        ], agent="worker", session="session-grandchild")
        transcript = self.export()
        self.assertIn("session-main -> session-child -> session-grandchild | agent=worker", transcript)
        positions = [transcript.index(marker) for marker in (
            "PARENT_START", "CHILD_START", "GRANDCHILD_ANSWER", "CHILD_END", "PARENT_END")]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(transcript.count("GRANDCHILD_ANSWER"), 1)
        self.assertEqual(self.export(), transcript)

    def test_shards_and_equal_or_regressing_timestamps_preserve_append_order(self):
        self.shard([meta(), text("first", second=3), text("second", second=3)])
        # The engine can reuse contextMeta when rotating, carrying its original time.
        self.shard([meta(), text("third", second=2)], index=2)
        transcript = self.export()
        positions = [transcript.index(f"\n{word}\n") for word in ("first", "second", "third")]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("session_order=5", transcript)
        self.assertIn("2 trace files; 5 records", transcript)

    def test_nonconversation_json_files_are_ignored_without_reading_them(self):
        (self.root / "model-list.json").write_text('{"models":[{"id":"not a message"}]}')
        (self.root / "config.json").write_text("not even JSON")
        with self.assertRaisesRegex(exporter.TraceExportError, "no Penguin JSONL traces"):
            self.export()
        self.shard([meta(), text("real message")])
        transcript = self.export()
        self.assertNotIn("not a message", transcript)
        self.assertNotIn("not even JSON", transcript)

    def test_invalid_input_fails_without_replacing_existing_output(self):
        cases = {
            "empty": "\n\n",
            "metadata_only": json.dumps(meta()) + "\n",
            "model_list_disguised_as_trace": '{"models":[]}\n',
            "no_meta": json.dumps(text("hello")) + "\n",
            "missing_text": json.dumps(meta()) + "\n" + json.dumps(record("model_msg", {"type": "text", "role": "user"})),
            "invalid_timestamp": json.dumps(meta()).replace("2026-10-23T10:00:00.000Z", "yesterday"),
            "naive_timestamp": json.dumps(meta()).replace("2026-10-23T10:00:00.000Z", "2026-10-23T10:00:00"),
            "streaming_partial": json.dumps(meta()) + "\n" + json.dumps(record("model_msg", {"type": "partial_text", "role": "assistant", "text": "delta"})),
            "duplicate_key": json.dumps(meta()).replace('"session_meta"', '"session_meta", "type": "session_meta"'),
            "nan": json.dumps(meta()).replace("128000", "NaN"),
            "invalid_utf8": b"\xff\n",
        }
        good = json.dumps(meta()) + "\n" + json.dumps(text("hello")) + "\n"
        cases["torn_tail"] = good + '{"timestamp":'
        cases["malformed_middle"] = json.dumps(meta()) + "\n{broken\n" + json.dumps(text("hello"))
        self.output.write_text("previous complete transcript")
        path = self.shard([])
        for name, content in cases.items():
            with self.subTest(name=name):
                path.write_bytes(content if isinstance(content, bytes) else content.encode())
                with self.assertRaises(exporter.TraceExportError):
                    self.export()
                self.assertEqual(self.output.read_text(), "previous complete transcript")
                self.assertEqual(list(self.base.glob(".*.tmp")), [])

    def test_missing_child_duplicate_session_and_missing_shard_are_errors(self):
        self.shard([meta(), text("hello"), event("subagent", session_id="missing")])
        with self.assertRaisesRegex(exporter.TraceExportError, "missing subagent trace"):
            self.export()
        self.shard([meta(), text("hello")])
        self.shard([meta(), text("later")], index=3)
        with self.assertRaisesRegex(exporter.TraceExportError, "missing context shard"):
            self.export()
        self.shard([meta(), text("middle")], index=2)
        self.shard([meta(agent="other"), text("collision")], agent="other")
        with self.assertRaisesRegex(exporter.TraceExportError, "multiple agents"):
            self.export()

    def test_subagent_cycles_are_errors(self):
        self.shard([meta(), text("hello"), event("subagent", session_id="session-main")])
        with self.assertRaisesRegex(exporter.TraceExportError, "cyclic subagent"):
            self.export()

    def test_atomic_replacement_cleans_temporary_file_on_failure(self):
        self.shard([meta(), text("new transcript")])
        self.output.write_text("old transcript")
        with patch.object(exporter.os, "replace", side_effect=OSError("injected failure")):
            with self.assertRaisesRegex(exporter.TraceExportError, "injected failure"):
                self.export()
        self.assertEqual(self.output.read_text(), "old transcript")
        self.assertEqual(list(self.base.glob(".*.tmp")), [])
        self.assertIn("new transcript", self.export())
        self.assertEqual(list(self.base.glob(".*.tmp")), [])

    def test_cli_success_and_failure(self):
        command = [sys.executable, "-I", str(SCRIPT), "--trace-root", str(self.root), "--output", str(self.output)]
        failed = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(failed.returncode, 1)
        self.assertIn("no Penguin JSONL traces", failed.stderr)
        self.assertFalse(self.output.exists())
        self.shard([meta(), text("CLI message")])
        passed = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(passed.returncode, 0, passed.stderr)
        self.assertIn("CLI message", self.output.read_text())

    def test_missing_root_and_trace_symlink_fail(self):
        with self.assertRaisesRegex(exporter.TraceExportError, "not a directory"):
            exporter.export_trace(self.base / "missing", self.output)
        path = self.shard([meta(), text("message")])
        link = path.parent / "other_001.jsonl"
        link.symlink_to(path)
        with self.assertRaisesRegex(exporter.TraceExportError, "symlink trace"):
            self.export()

    def test_direct_agent_trace_root_uses_metadata_identity(self):
        self.shard([meta(), text("message")])
        exporter.export_trace(self.root / "coder", self.output)
        self.assertIn("agent=coder", self.output.read_text())


if __name__ == "__main__":
    unittest.main()
