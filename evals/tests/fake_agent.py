#!/usr/bin/env python3
"""A stand-in for a headless agent, for testing run.py and check.py together.

Takes the prompt as its only argument and behaves the way the skill should:
it writes a result JSON and a progress log into $MAGI_RESULTS_DIR, or, for a
prompt that neither says to go ahead nor that the run is unattended, only a
log whose framing left a question (the turn ended on the question).
No model is involved; the verdict is always 3/3 approve, and every execution
reports a cost of $0.25. A control prompt (run.py --control, which asks for a
"DECISION:" line) is answered with "DECISION: no_change" and nothing written.
"""

import json
import os
import sys
from pathlib import Path


def main() -> int:
    prompt = sys.argv[1]
    if "DECISION:" in prompt:
        print(json.dumps({"type": "result", "result": "Leave it.\n\nDECISION: no_change", "total_cost_usd": 0.05}))
        return 0
    out = Path(os.environ["MAGI_RESULTS_DIR"])
    run_id = "20260101-000000-fake"
    proceeds = any(s in prompt for s in ("go ahead", "unattended", "진행해줘", "무인 실행"))

    events = [{"event": "run_started", "data": {"request": prompt}}]
    if not proceeds:
        events.append({"event": "framing_done", "data": {"questions": ["What does 'release' mean here?"]}})
    else:
        unit = {"verdict": "approve", "confidence": "high", "rationale": ["fake"]}
        result = {"version": 2, "mode": "deliberation", "agenda": "fake proposal", "grade": "normal",
                  "verdict": "passed", "approve_count": 3,
                  "units": {"melchior": unit, "balthasar": unit, "casper": unit}}
        (out / f"{run_id}.json").write_text(json.dumps(result), encoding="utf-8")
        events.append({"event": "framing_done", "data": {"questions": []}})
        events.append({"event": "final", "data": {"result": result}})
    with open(out / f"{run_id}.jsonl", "w", encoding="utf-8") as f:
        for seq, event in enumerate(events, 1):
            f.write(json.dumps({"v": 1, "run_id": run_id, "seq": seq, **event}) + "\n")
    # What Claude Code prints with --output-format json, cut down to what is read.
    print(json.dumps({"type": "result", "result": "done", "total_cost_usd": 0.25}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
