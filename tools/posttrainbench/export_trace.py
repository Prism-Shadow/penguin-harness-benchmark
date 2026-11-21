#!/usr/bin/env python3
"""Export already-redacted Penguin AMSP traces for PostTrainBench judges.

Run after agents/penguin_agent/run.sh has collected and redacted its traces.
This exporter does not read config, follow recovery paths, or redact evidence.
The schema comes from Penguin's packages/amsp/src/records/types.ts and
packages/core/src/trace/writer.ts: every context shard starts with session_meta;
child sessions have their own shards, linked by event_msg/subagent records.

export_trace(trace_root, output) returns the output Path. Invalid or incomplete
input raises TraceExportError; an existing output is left untouched on failure.
Only the Python 3.10+ standard library is required.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import heapq
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
from typing import Any, TextIO


DEFAULT_TRACE_ROOT = Path("/logs/agent/penguin/traces")
DEFAULT_OUTPUT = Path("/logs/agent/penguin-transcript.txt")
_SHARD_NAME = re.compile(r"(.+)_(\d{3,})\.jsonl\Z")
_MODEL_FIELDS = {
    "text": ("text",),
    "thinking": ("thinking",),
    "inline_thinking": ("data", "mime_type"),
    "inline_data": ("data", "mime_type"),
    "image_url": ("image_url",),
    "tool_call": ("name", "arguments", "tool_call_id"),
    "tool_call_output": ("output", "tool_call_id"),
}


class TraceExportError(ValueError):
    """The input cannot produce a complete, trustworthy transcript."""


@dataclass
class _Record:
    data: dict[str, Any]
    time: datetime
    source: str
    line: int


@dataclass
class _Session:
    agent: str
    records: list[_Record]


def _string(obj: dict[str, Any], key: str, where: str, *, nonempty: bool = False) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or (nonempty and not value):
        raise TraceExportError(f"{where}: {key} must be {'a nonempty' if nonempty else 'a'} string")
    return value


def _reject_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant {value}")


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _read_records(path: Path, root: Path) -> list[_Record]:
    source = path.relative_to(root).as_posix()
    records = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue  # The writer may add blank lines while healing a torn tail.
            where = f"{source}:{line_number}"
            try:
                data = json.loads(line, parse_constant=_reject_constant, object_pairs_hook=_unique_keys)
            except ValueError as exc:
                # Do not echo source payloads to stderr, including a truncated final line.
                raise TraceExportError(f"{where}: invalid JSON record") from exc
            if not isinstance(data, dict) or not isinstance(data.get("payload"), dict):
                raise TraceExportError(f"{where}: expected an AMSP record with an object payload")
            timestamp = _string(data, "timestamp", where, nonempty=True)
            try:
                time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                if time.tzinfo is None:
                    raise ValueError("timezone required")
                time = time.astimezone(timezone.utc)
            except ValueError as exc:
                raise TraceExportError(f"{where}: invalid timestamp (timezone required)") from exc
            payload = data["payload"]
            kind = data.get("type")
            if kind == "session_meta":
                for key in ("session_id", "agent_state"):
                    _string(payload, key, where, nonempty=True)
                _string(payload, "system_prompt", where)
            elif kind == "model_msg":
                subtype = _string(payload, "type", where, nonempty=True)
                if subtype not in _MODEL_FIELDS:
                    raise TraceExportError(f"{where}: unsupported complete model message type")
                if payload.get("role") not in ("user", "assistant"):
                    raise TraceExportError(f"{where}: invalid model message role")
                for key in _MODEL_FIELDS[subtype]:
                    _string(payload, key, where)
            elif kind == "event_msg":
                subtype = _string(payload, "type", where, nonempty=True)
                if subtype == "subagent":
                    _string(payload, "session_id", where, nonempty=True)
            else:
                raise TraceExportError(f"{where}: unrecognized AMSP record type")
            if "origin" in data and data["origin"] != []:
                raise TraceExportError(f"{where}: nested stream records are not on-disk Penguin traces")
            records.append(_Record(data, time, source, line_number))
    if not records or records[0].data["type"] != "session_meta":
        raise TraceExportError(f"{source}: empty trace or missing initial session_meta")
    return records


def _load_sessions(root: Path) -> tuple[dict[str, _Session], dict[str, str], int]:
    if not root.is_dir():
        raise TraceExportError(f"trace root is not a directory: {root}")
    shards: dict[str, dict[int, list[_Record]]] = {}
    agents: dict[str, str] = {}
    files = 0

    def walk_error(error: OSError) -> None:
        raise error

    for directory, dirs, names in os.walk(root, onerror=walk_error):
        dirs.sort()
        for name in dirs:
            if (Path(directory) / name).is_symlink():
                raise TraceExportError("trace root contains a symlink directory")
        for name in sorted(names):
            if not name.endswith(".jsonl"):
                continue  # Model catalogs, cost reports and config JSON are not traces.
            path = Path(directory) / name
            if path.is_symlink():
                raise TraceExportError(f"symlink trace is not supported: {path.relative_to(root)}")
            match = _SHARD_NAME.fullmatch(name)
            if match is None or int(match[2]) < 1:
                raise TraceExportError(f"invalid Penguin trace shard filename: {path.relative_to(root)}")
            records = _read_records(path, root)
            meta = records[0].data["payload"]
            session_id = meta["session_id"]
            if session_id != match[1] or any(
                record.data["type"] == "session_meta"
                and record.data["payload"]["session_id"] != session_id
                for record in records
            ):
                raise TraceExportError(f"{path.relative_to(root)}: inconsistent session_id")
            # Collected layout: <agent>/<date>/<session>_<index>.jsonl. Metadata
            # also identifies the agent when pointed directly at its traces directory.
            parts = path.relative_to(root).parts
            agent = parts[-3] if len(parts) >= 3 else PurePosixPath(meta["agent_state"]).parent.name
            if not agent:
                raise TraceExportError(f"{path.relative_to(root)}: cannot identify agent")
            if session_id in agents and agents[session_id] != agent:
                raise TraceExportError(f"session_id belongs to multiple agents: {session_id}")
            agents[session_id] = agent
            index = int(match[2])
            segments = shards.setdefault(session_id, {})
            if index in segments:
                raise TraceExportError(f"duplicate shard {index} for session {session_id}")
            segments[index] = records
            files += 1
    if not files:
        raise TraceExportError(f"no Penguin JSONL traces found under {root}")

    sessions = {}
    parents: dict[str, str] = {}
    for session_id, segments in sorted(shards.items()):
        indices = sorted(segments)
        if indices != list(range(1, len(indices) + 1)):
            raise TraceExportError(f"missing context shard(s) for session {session_id}")
        records = [record for index in indices for record in segments[index]]
        if not any(record.data["type"] == "model_msg" for record in records):
            raise TraceExportError(f"session has no conversation messages: {session_id}")
        sessions[session_id] = _Session(agents[session_id], records)
        for record in records:
            payload = record.data["payload"]
            if record.data["type"] == "event_msg" and payload["type"] == "subagent":
                child = payload["session_id"]
                if child not in shards:
                    raise TraceExportError(f"{record.source}:{record.line}: missing subagent trace {child}")
                if child in parents and parents[child] != session_id:
                    raise TraceExportError(f"subagent has multiple parents: {child}")
                parents[child] = session_id
    for session_id in sessions:
        seen = {session_id}
        ancestor = session_id
        while ancestor in parents:
            ancestor = parents[ancestor]
            if ancestor in seen:
                raise TraceExportError(f"cyclic subagent references at {session_id}")
            seen.add(ancestor)
    return sessions, parents, files


def _write_value(stream: TextIO, label: str, value: Any) -> None:
    """Render every field; text stays literal, including newlines and redactions."""
    if isinstance(value, dict) and value:
        for key, item in value.items():
            _write_value(stream, f"{label}.{key}" if label else key, item)
    elif isinstance(value, list) and value:
        for index, item in enumerate(value):
            _write_value(stream, f"{label}[{index}]", item)
    elif isinstance(value, str):
        stream.write(f"{label} ({len(value)} characters):\n{value}\n")
    else:
        stream.write(f"{label}: {json.dumps(value, ensure_ascii=False, allow_nan=False)}\n")


def _write_transcript(stream: TextIO, sessions: dict[str, _Session], parents: dict[str, str], files: int) -> None:
    count = sum(len(session.records) for session in sessions.values())
    stream.write(f"Penguin transcript\n{len(sessions)} sessions; {files} trace files; {count} records\n")
    stream.write("Source: already-redacted AMSP traces; all recorded fields retained.\n")
    stream.write("Order: timestamp merge across sessions; shard/line append order within each session wins.\n")
    stream.write("Ties: session ID, then append order. Timestamps are original, including clock regressions.\n\n")
    stream.write("Session hierarchy (root -> descendants):\n")
    for session_id, session in sessions.items():
        chain = [session_id]
        while chain[-1] in parents:
            chain.append(parents[chain[-1]])
        stream.write(f"  {' -> '.join(reversed(chain))} | agent={session.agent}\n")
    stream.write("\n")

    # A heap merge, rather than sorting all records by timestamp, keeps old meta
    # timestamps in rotated shards and any clock regressions in their real order.
    pending = [(session.records[0].time, session_id, 0) for session_id, session in sessions.items()]
    heapq.heapify(pending)
    ordinal = 0
    while pending:
        _, session_id, index = heapq.heappop(pending)
        session = sessions[session_id]
        record = session.records[index]
        data = record.data
        payload = data["payload"]
        ordinal += 1
        kind = data["type"] + ("/" + payload["type"] if "type" in payload else "")
        stream.write(
            f"=== Record {ordinal} | {data['timestamp']} | agent={session.agent} | "
            f"session={session_id} | session_order={index + 1} | {kind} ===\n"
        )
        stream.write(f"Source: {record.source}:{record.line}\n")
        for key, value in data.items():
            if key not in ("timestamp", "type"):
                _write_value(stream, key, value)
        stream.write("\n")
        if index + 1 < len(session.records):
            heapq.heappush(pending, (session.records[index + 1].time, session_id, index + 1))


def export_trace(trace_root: str | Path, output: str | Path) -> Path:
    """Validate all trace shards, then atomically replace output with the transcript.

    Missing child traces, missing context segments, empty conversations, malformed
    records (even a torn final line), and ambiguous session identities are errors.
    No messages are filtered based on request success, role, event type or content.
    """
    root = Path(trace_root).resolve()
    target = Path(output).absolute()
    temporary: Path | None = None
    try:
        if target.suffix == ".jsonl":
            raise TraceExportError("output must not be a JSONL trace file")
        sessions, parents, files = _load_sessions(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=target.parent,
            prefix=f".{target.name}.", suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            _write_transcript(stream, sessions, parents, files)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        temporary = None
    except (OSError, UnicodeError) as exc:
        raise TraceExportError(f"cannot export Penguin traces: {exc}") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace-root", type=Path, default=DEFAULT_TRACE_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    try:
        target = export_trace(args.trace_root, args.output)
    except TraceExportError as exc:
        print(f"export_trace: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote Penguin transcript to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
