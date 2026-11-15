#!/usr/bin/env python3
"""Append one MAGI progress event to a JSON Lines file.

Usage (the event JSON comes on stdin, so no shell escaping is needed):

    python3 log_event.py "$MAGI_RESULTS_DIR/<run_id>.jsonl" <<'EOF'
    {"run_id": "<run_id>", "event": "framing_done", "data": {...}}
    EOF

The script adds "v", "seq" and "ts", writes the event as a single line, and
appends it to the file. Logging is best-effort: on any problem it prints a
warning to stderr and still exits 0, so the deliberation never stops for it.
Standard library only.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

EVENTS = {
    "run_started", "facts_gathered", "framing_done", "questions_answered",
    "units_started", "units_done", "final", "error",
}


def warn(msg: str) -> None:
    print(f"[magi log_event] skipped: {msg}", file=sys.stderr)


def main() -> int:
    if len(sys.argv) != 2:
        warn("usage: log_event.py <file.jsonl>  (event JSON on stdin)")
        return 0
    path = Path(sys.argv[1]).expanduser()
    try:
        event = json.loads(sys.stdin.read())
    except json.JSONDecodeError as e:
        warn(f"event is not valid JSON ({e})")
        return 0
    if not isinstance(event, dict) or event.get("event") not in EVENTS or not event.get("run_id"):
        warn(f"event needs run_id and an event in {sorted(EVENTS)}")
        return 0
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        seq = 1
        if path.exists():
            with open(path, encoding="utf-8") as f:
                seq = sum(1 for line in f if line.strip()) + 1
        record = {"v": 1, "run_id": event["run_id"], "seq": seq,
                  "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
                  "event": event["event"], "data": event.get("data", {})}
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as e:
        warn(str(e))
    return 0


if __name__ == "__main__":
    sys.exit(main())
