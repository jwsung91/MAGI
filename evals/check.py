#!/usr/bin/env python3
"""Check MAGI eval runs against the fixtures in evals/fixtures.

A fixture is one request, the facts handed to the moderator, and what the
result must or should look like. run.py runs each fixture several times in a
headless agent with MAGI_RESULTS_DIR set; this script reads the result JSON
files (and progress logs) those runs left behind.

Subcommands:
  fixtures [DIR]     Validate the fixture files. Used by CI.
  results RUN_DIR    Check one run: every result against the result schema and
                     the resolution rules, every fixture against its
                     expectations, and paired fixtures against each other.
                     Writes report.md and summary.json into RUN_DIR.
                     Exit 1 if anything failed.
  compare A B        Compare two checked runs fixture by fixture (A is the
                     baseline). Exit 1 if a fixture that did not fail in A
                     fails in B.

What is checked, in order of strictness:
  - schema and rules: hard. A result that breaks result.schema.json or the
    resolution rules (for example a normal proposal with 2/3 approvals that is
    not 'passed') fails its fixture, whatever the fixture expects.
  - expect.must: every run has to meet it, or the fixture fails.
  - expect.should: reported as a rate; a miss is a warning, not a failure.
  - pairs: two fixtures that ask the same decision in opposite directions must
    reach the same outcome in the majority of their runs.

Standard library only.
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIXTURES_DIR = HERE / "fixtures"
RESULT_SCHEMA = ROOT / "skills" / "magi" / "result.schema.json"

UNIT_NAMES = ("melchior", "balthasar", "casper")
VERDICTS = ("passed", "rejected", "on_hold", "error")
# Approve is always the change (SKILL.md, framing), so the verdict alone says
# what happens: 'passed' carries the change out; 'rejected' and 'on_hold' do not.
OUTCOME = {"passed": "change", "rejected": "no_change", "on_hold": "no_change"}


# --- fixtures ---------------------------------------------------------------

ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
FIXTURE_KEYS = {"id", "category", "pair", "lang", "interaction", "request", "facts", "expect", "note"}
LANGS = ("en", "ko")
# go_ahead: the prompt tells the skill to proceed on assumptions (the default).
# ask: nothing is added, so a real question must end the turn.
# unattended: the prompt says nobody can answer.
INTERACTIONS = ("go_ahead", "ask", "unattended")


def _is_regex(value) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        re.compile(value)
    except re.error:
        return False
    return True


EXPECT_KEYS = {
    "mode": lambda v: v in ("deliberation", "information"),
    "grade": lambda v: v in ("normal", "critical"),
    "outcome": lambda v: v in ("change", "no_change"),
    "verdict": lambda v: isinstance(v, list) and bool(v) and all(x in VERDICTS for x in v),
    "split": lambda v: isinstance(v, bool),
    "follow_ups_min": lambda v: type(v) is int and 0 <= v <= 2,
    "agenda_match": _is_regex,
    "agenda_not_match": _is_regex,
    "preset_match": _is_regex,
    "asks_questions": lambda v: isinstance(v, bool),
}


def validate_fixture(path: Path, fx) -> list:
    errors = []
    if not isinstance(fx, dict):
        return ["fixture must be a JSON object"]
    for key in sorted(set(fx) - FIXTURE_KEYS):
        errors.append(f"unknown key {key!r}")
    if not isinstance(fx.get("id"), str) or not ID_RE.match(fx["id"]):
        errors.append("id must be lowercase words joined by hyphens")
    elif fx["id"] != path.stem:
        errors.append(f"id {fx['id']!r} does not match the file name")
    for key in ("category", "request"):
        if not isinstance(fx.get(key), str) or not fx[key].strip():
            errors.append(f"{key} must be a non-empty string")
    facts = fx.get("facts")
    if not isinstance(facts, list) or not all(isinstance(f, str) and f.strip() for f in facts):
        errors.append("facts must be a list of non-empty strings")
    if fx.get("lang", "en") not in LANGS:
        errors.append(f"lang must be one of {LANGS}")
    if fx.get("interaction", "go_ahead") not in INTERACTIONS:
        errors.append(f"interaction must be one of {INTERACTIONS}")
    if "pair" in fx and (not isinstance(fx["pair"], str) or not ID_RE.match(fx["pair"])):
        errors.append("pair must be lowercase words joined by hyphens")

    expect = fx.get("expect")
    if not isinstance(expect, dict) or set(expect) - {"must", "should"}:
        return errors + ["expect must be an object with 'must' and/or 'should'"]
    must, should = expect.get("must", {}), expect.get("should", {})
    if not isinstance(must, dict) or not isinstance(should, dict) or not (must or should):
        return errors + ["expect.must and expect.should must be objects, and one must be non-empty"]
    for level, checks in (("must", must), ("should", should)):
        for key, value in checks.items():
            if key not in EXPECT_KEYS:
                errors.append(f"expect.{level}: unknown check {key!r}")
            elif not EXPECT_KEYS[key](value):
                errors.append(f"expect.{level}.{key}: bad value {value!r}")
    for key in sorted(set(must) & set(should)):
        errors.append(f"{key!r} is in both expect.must and expect.should")
    if must.get("asks_questions") is True or should.get("asks_questions") is True:
        # A run that stops to ask writes no result, so nothing else can be checked.
        if len(must) + len(should) > 1:
            errors.append("asks_questions: true cannot be combined with other checks")
        if fx.get("interaction") != "ask":
            errors.append("asks_questions: true needs interaction 'ask'")
    return errors


def load_fixtures(directory: Path):
    """Return ({id: fixture}, [error strings])."""
    fixtures, errors = {}, []
    paths = sorted(directory.glob("*.json"))
    if not paths:
        errors.append(f"no fixtures in {directory}")
    for path in paths:
        try:
            fx = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"{path.name}: not valid JSON ({e})")
            continue
        found = validate_fixture(path, fx)
        errors.extend(f"{path.name}: {e}" for e in found)
        if not found:
            fixtures[fx["id"]] = fx
    pairs = Counter(fx["pair"] for fx in fixtures.values() if "pair" in fx)
    for pair, count in sorted(pairs.items()):
        if count != 2:
            errors.append(f"pair {pair!r} has {count} fixture(s); a pair needs exactly 2")
    return fixtures, errors


# --- result schema ----------------------------------------------------------

class SchemaError(Exception):
    """The schema uses something this validator does not implement."""


_ANNOTATIONS = {"$schema", "$id", "title", "description", "$defs"}
_KEYWORDS = {"type", "enum", "const", "required", "properties", "additionalProperties",
             "items", "maxItems", "minLength", "minimum", "maximum", "$ref"}
_TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "integer": lambda v: type(v) is int,
}


def validate_schema(value, schema: dict, root: dict, path: str = "$") -> list:
    """Validate against the subset of JSON Schema that result.schema.json uses.

    An unknown keyword raises SchemaError instead of being skipped, so a schema
    change can never make this check pass by accident.
    """
    unknown = set(schema) - _KEYWORDS - _ANNOTATIONS
    if unknown:
        raise SchemaError(f"unsupported schema keyword(s) at {path}: {sorted(unknown)}")
    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/$defs/") or ref[8:] not in root.get("$defs", {}):
            raise SchemaError(f"unsupported $ref {ref!r}")
        return validate_schema(value, root["$defs"][ref[8:]], root, path)

    if "const" in schema and (type(value) is not type(schema["const"]) or value != schema["const"]):
        return [f"{path}: must be {schema['const']!r}, got {value!r}"]
    if "enum" in schema and (isinstance(value, (dict, list)) or value not in schema["enum"]):
        return [f"{path}: must be one of {schema['enum']}, got {value!r}"]
    if "type" in schema:
        if schema["type"] not in _TYPES:
            raise SchemaError(f"unsupported type {schema['type']!r} at {path}")
        if not _TYPES[schema["type"]](value):
            return [f"{path}: must be {schema['type']}, got {type(value).__name__}"]

    errors = []
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}: missing {key!r}")
        props = schema.get("properties", {})
        for key, item in value.items():
            if key in props:
                errors.extend(validate_schema(item, props[key], root, f"{path}.{key}"))
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}: unexpected key {key!r}")
        if schema.get("additionalProperties") not in (None, False, True):
            raise SchemaError(f"unsupported additionalProperties at {path}")
    elif isinstance(value, list):
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{path}: at most {schema['maxItems']} items, got {len(value)}")
        if "items" in schema:
            for i, item in enumerate(value):
                errors.extend(validate_schema(item, schema["items"], root, f"{path}[{i}]"))
    elif isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{path}: must not be empty")
    elif type(value) is int:
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: below {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: above {schema['maximum']}")
    return errors


# --- resolution rules -------------------------------------------------------

def unit_votes(units) -> list:
    units = units if isinstance(units, dict) else {}
    return [(units.get(name) or {}).get("verdict") for name in UNIT_NAMES]


def expected_verdict(grade: str, votes: list):
    """The resolution SKILL.md section 4 gives for these final votes."""
    approvals = votes.count("approve")
    if grade == "normal":
        return "passed" if approvals >= 2 else "rejected"
    if grade == "critical":
        return {3: "passed", 0: "rejected"}.get(approvals, "on_hold")
    return None


def _check_proposal(label: str, proposal: dict, main: bool, problems: list, warnings: list) -> None:
    grade, verdict = proposal.get("grade"), proposal.get("verdict")
    if "units" not in proposal:
        warnings.append(f"{label}: no per-unit verdicts")
        return
    votes = unit_votes(proposal["units"])
    if None in votes:
        problems.append(f"{label}: a unit has no verdict")
        return
    if "error" in votes:
        # A failed unit is exposed, never outvoted by the other two.
        if verdict != "error":
            problems.append(f"{label}: a unit reports an error, so the resolution must be 'error', got {verdict!r}")
        return
    if verdict == "error":
        warnings.append(f"{label}: resolution is 'error' but no unit reports one")
        return
    approvals = votes.count("approve")
    if "approve_count" in proposal and proposal["approve_count"] != approvals:
        problems.append(f"{label}: approve_count is {proposal['approve_count']} but {approvals} unit(s) approve")
    if grade is None:
        (problems if main else warnings).append(f"{label}: no grade")
        return
    want = expected_verdict(grade, votes)
    if verdict != want:
        problems.append(f"{label}: a {grade} proposal with {approvals}/3 approvals is {want!r}, got {verdict!r}")


def check_rules(result: dict):
    """Return (problems, warnings) for things the schema cannot express."""
    problems, warnings = [], []
    units = result.get("units") if isinstance(result.get("units"), dict) else {}
    if result.get("mode") == "information":
        for name in UNIT_NAMES:
            if not str((units.get(name) or {}).get("answer", "")).strip():
                problems.append(f"information mode: {name} has no answer")
        for key in ("verdict", "grade", "approve_count"):
            if key in result:
                warnings.append(f"information mode: {key!r} should not be set (there is no vote)")
        return problems, warnings

    for key in ("grade", "verdict"):
        if key not in result:
            problems.append(f"main proposal: {key!r} is required in deliberation mode")
    if "verdict" in result:
        _check_proposal("main proposal", result, True, problems, warnings)
    if result.get("grade_raised") is True and result.get("grade") != "critical":
        problems.append("grade_raised is true but the grade is not critical")
    if result.get("verdict") == "on_hold" and not str(result.get("debate", "")).strip():
        # A critical split always opens a debate round before it can end on hold.
        problems.append("main proposal: on hold without a debate round record")
    follow_ups = result.get("follow_ups")
    for i, follow_up in enumerate(follow_ups if isinstance(follow_ups, list) else [], 1):
        if isinstance(follow_up, dict):
            _check_proposal(f"follow-up {i}", follow_up, False, problems, warnings)
    return problems, warnings


# --- reading a run ----------------------------------------------------------

def _has_questions(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() not in ("", "none", "없음")
    return bool(value)


def read_log(path: Path):
    """Return (asked, finished) from a progress log: whether the last framing
    left questions for the user, and whether the run reached its final event."""
    framing, finished = None, False
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("event") == "framing_done":
            framing = event.get("data") if isinstance(event.get("data"), dict) else {}
        elif event.get("event") == "final":
            finished = True
    asked = None if framing is None else _has_questions(framing.get("questions"))
    return asked, finished


def read_run(run_dir: Path, schema: dict) -> dict:
    """One execution of one fixture: its result (if any), what is wrong with
    it, and whether the run stopped to ask the user."""
    run = {"name": run_dir.name, "result": None, "problems": [], "warnings": [], "stopped_to_ask": None}
    result_dir = run_dir / "result"
    results = sorted(result_dir.glob("*.json")) if result_dir.is_dir() else []
    logs = sorted(result_dir.glob("*.jsonl")) if result_dir.is_dir() else []

    asked, finished = read_log(logs[-1]) if logs else (None, False)
    if not results:
        # No result file. With a log we can tell a turn that ended on questions
        # from a run that simply died.
        if logs:
            run["stopped_to_ask"] = bool(asked) and not finished
        meta_path = run_dir / "meta.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                if meta.get("timed_out"):
                    run["warnings"].append("agent timed out")
                elif meta.get("exit_code") not in (0, None):
                    run["warnings"].append(f"agent exited with code {meta['exit_code']}")
            except json.JSONDecodeError:
                pass
        return run

    run["stopped_to_ask"] = False
    if len(results) > 1:
        run["problems"].append(f"{len(results)} result files; expected one")
    try:
        result = json.loads(results[-1].read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        run["problems"].append(f"result is not valid JSON ({e})")
        return run
    if not isinstance(result, dict):
        run["problems"].append("result is not a JSON object")
        return run
    run["result"] = result
    run["problems"].extend(f"schema: {e}" for e in validate_schema(result, schema, schema))
    problems, warnings = check_rules(result)
    run["problems"].extend(problems)
    run["warnings"].extend(warnings)
    return run


# --- expectations -----------------------------------------------------------

def meets(key: str, want, run: dict):
    """True / False, or None when the run left nothing to verify it with."""
    result = run["result"]
    if key == "asks_questions":
        stopped = run["stopped_to_ask"]
        return None if stopped is None else stopped == want
    if result is None:
        return False
    if key in ("mode", "grade"):
        return result.get(key) == want
    if key == "outcome":
        return OUTCOME.get(result.get("verdict")) == want
    if key == "verdict":
        return result.get("verdict") in want
    if key == "split":
        votes = set(unit_votes(result.get("units")))
        return ({"approve", "reject"} <= votes) == want
    if key == "follow_ups_min":
        follow_ups = result.get("follow_ups")
        return len(follow_ups if isinstance(follow_ups, list) else []) >= want
    if key == "agenda_match":
        return re.search(want, str(result.get("agenda", "")), re.I) is not None
    if key == "agenda_not_match":
        return re.search(want, str(result.get("agenda", "")), re.I) is None
    if key == "preset_match":
        return re.search(want, str(result.get("preset", "")), re.I) is not None
    raise ValueError(key)


def run_label(run: dict) -> str:
    """What one run ended as, for the report."""
    if run["result"] is None:
        return "asked" if run["stopped_to_ask"] else "no result"
    if run["result"].get("mode") == "information":
        return "information"
    return str(run["result"].get("verdict"))


def evaluate_fixture(fx: dict, runs: list) -> dict:
    out = {"status": "pass", "runs": len(runs), "results": {}, "approvals_mean": None,
           "majority_outcome": None, "must": {}, "should": {}, "notes": []}
    if not runs:
        out["status"] = "skipped"
        return out

    out["results"] = dict(Counter(run_label(r) for r in runs))
    approvals = [unit_votes(r["result"].get("units")).count("approve") for r in runs
                 if r["result"] is not None and r["result"].get("mode") != "information"]
    if approvals:
        out["approvals_mean"] = round(sum(approvals) / len(approvals), 2)
    outcomes = Counter(OUTCOME.get(r["result"].get("verdict")) for r in runs if r["result"] is not None)
    outcomes.pop(None, None)
    if outcomes:
        top = outcomes.most_common(2)
        out["majority_outcome"] = "tie" if len(top) == 2 and top[0][1] == top[1][1] else top[0][0]

    failed = warned = False
    for run in runs:
        for problem in run["problems"]:
            failed = True
            out["notes"].append(f"{run['name']}: {problem}")
        for warning in run["warnings"]:
            warned = True
            out["notes"].append(f"{run['name']}: {warning}")

    expect = fx["expect"]
    for level in ("must", "should"):
        for key, want in expect.get(level, {}).items():
            answers = [meets(key, want, run) for run in runs]
            met, unverified = answers.count(True), answers.count(None)
            out[level][key] = {"want": want, "met": met, "unverified": unverified, "total": len(runs)}
            missed = len(runs) - met - unverified
            if missed:
                if level == "must":
                    failed = True
                else:
                    warned = True
                out["notes"].append(f"{level} {key}={want!r}: met in {met}/{len(runs)} runs")
            if unverified:
                warned = True
                out["notes"].append(f"{level} {key}: could not be verified in {unverified} run(s) (no progress log)")
    out["status"] = "fail" if failed else "warn" if warned else "pass"
    return out


def evaluate_pairs(fixtures: dict, evaluated: dict) -> dict:
    members = {}
    for fid, fx in fixtures.items():
        if "pair" in fx:
            members.setdefault(fx["pair"], []).append(fid)
    pairs = {}
    for pair, ids in sorted(members.items()):
        sides = {fid: {"majority_outcome": evaluated[fid]["majority_outcome"],
                       "approvals_mean": evaluated[fid]["approvals_mean"]} for fid in ids}
        outcomes = [s["majority_outcome"] for s in sides.values()]
        if None in outcomes:
            status = "skipped"
        elif len(set(outcomes)) == 1 and outcomes[0] != "tie":
            status = "pass"
        else:
            status = "fail"
        pairs[pair] = {"status": status, "members": sides}
    return pairs


# --- report -----------------------------------------------------------------

def check_results(run_dir: Path, fixtures: dict) -> dict:
    schema = json.loads(RESULT_SCHEMA.read_text(encoding="utf-8"))
    evaluated = {}
    for fid, fx in fixtures.items():
        fixture_dir = run_dir / fid
        run_dirs = sorted(p for p in fixture_dir.glob("run-*") if p.is_dir()) if fixture_dir.is_dir() else []
        evaluated[fid] = evaluate_fixture(fx, [read_run(p, schema) for p in run_dirs])
    pairs = evaluate_pairs(fixtures, evaluated)

    meta = {}
    if (run_dir / "run.json").exists():
        try:
            meta = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    totals = Counter(e["status"] for e in evaluated.values())
    return {
        "run": meta.get("name", run_dir.name),
        "skill_version": meta.get("skill_version"),
        "agent": meta.get("agent"),
        "totals": {s: totals.get(s, 0) for s in ("pass", "warn", "fail", "skipped")},
        "pairs_failed": sum(1 for p in pairs.values() if p["status"] == "fail"),
        "fixtures": evaluated,
        "pairs": pairs,
    }


def _cell(text) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def render_report(summary: dict) -> str:
    t = summary["totals"]
    lines = [
        "# MAGI Eval Report",
        "",
        f"Run: `{summary['run']}` · skill {summary['skill_version'] or 'unknown'} · agent {summary['agent'] or 'unknown'}",
        "",
        f"Fixtures: pass {t['pass']}, warn {t['warn']}, fail {t['fail']}, skipped {t['skipped']} · "
        f"pairs failed: {summary['pairs_failed']}",
        "",
        "| Fixture | Status | Results | Approvals (mean) | Notes |",
        "|---|---|---|---|---|",
    ]
    for fid, e in summary["fixtures"].items():
        results = ", ".join(f"{label} {n}" for label, n in sorted(e["results"].items())) or "—"
        approvals = "—" if e["approvals_mean"] is None else f"{e['approvals_mean']}/3"
        notes = "; ".join(e["notes"][:4]) + (f"; … (+{len(e['notes']) - 4})" if len(e["notes"]) > 4 else "")
        lines.append(f"| {fid} | {e['status']} | {results} | {approvals} | {_cell(notes) or '—'} |")
    if summary["pairs"]:
        lines += ["", "## Pairs", "",
                  "Two fixtures that ask the same decision in opposite directions. "
                  "Both must reach the same outcome in the majority of their runs.",
                  "", "| Pair | Status | Fixture | Majority outcome | Approvals (mean) |", "|---|---|---|---|---|"]
        for pair, p in summary["pairs"].items():
            for fid, side in p["members"].items():
                approvals = "—" if side["approvals_mean"] is None else f"{side['approvals_mean']}/3"
                lines.append(f"| {pair} | {p['status']} | {fid} | {side['majority_outcome'] or '—'} | {approvals} |")
    return "\n".join(lines) + "\n"


def load_summary(path: Path) -> dict:
    if path.is_dir():
        path = path / "summary.json"
    return json.loads(path.read_text(encoding="utf-8"))


def render_compare(a: dict, b: dict):
    """Return (markdown, regressions)."""
    lines = [f"# MAGI Eval Comparison: `{a['run']}` → `{b['run']}`", "",
             "| Fixture | A | B | Approvals A | Approvals B | |", "|---|---|---|---|---|---|"]
    regressions = []
    for fid in sorted(set(a["fixtures"]) | set(b["fixtures"])):
        ea, eb = a["fixtures"].get(fid), b["fixtures"].get(fid)
        sa = ea["status"] if ea else "absent"
        sb = eb["status"] if eb else "absent"
        mark = ""
        if sb == "fail" and sa in ("pass", "warn"):
            mark = "regression"
            regressions.append(fid)
        elif sa == "fail" and sb in ("pass", "warn"):
            mark = "fixed"
        elif sa != sb:
            mark = "changed"
        fmt = lambda e: "—" if not e or e["approvals_mean"] is None else f"{e['approvals_mean']}/3"
        lines.append(f"| {fid} | {sa} | {sb} | {fmt(ea)} | {fmt(eb)} | {mark} |")
    for pair in sorted(set(a.get("pairs", {})) & set(b.get("pairs", {}))):
        pa, pb = a["pairs"][pair]["status"], b["pairs"][pair]["status"]
        if pb == "fail" and pa == "pass":
            regressions.append(f"pair {pair}")
    lines += ["", f"Regressions: {', '.join(regressions) if regressions else 'none'}"]
    return "\n".join(lines) + "\n", regressions


# --- command line -----------------------------------------------------------

def cmd_fixtures(args) -> int:
    fixtures, errors = load_fixtures(Path(args.dir))
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    if errors:
        return 1
    pairs = len({fx["pair"] for fx in fixtures.values() if "pair" in fx})
    print(f"{len(fixtures)} fixtures OK ({pairs} pairs)")
    return 0


def cmd_results(args) -> int:
    run_dir = Path(args.run_dir)
    if not run_dir.is_dir():
        print(f"error: {run_dir} is not a directory", file=sys.stderr)
        return 2
    fixtures, errors = load_fixtures(Path(args.fixtures))
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 2
    summary = check_results(run_dir, fixtures)
    report = render_report(summary)
    (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (run_dir / "report.md").write_text(report, encoding="utf-8")
    print(report)
    return 1 if summary["totals"]["fail"] or summary["pairs_failed"] else 0


def cmd_compare(args) -> int:
    report, regressions = render_compare(load_summary(Path(args.a)), load_summary(Path(args.b)))
    print(report)
    return 1 if regressions else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("fixtures", help="validate the fixture files")
    p.add_argument("dir", nargs="?", default=str(FIXTURES_DIR))
    p.set_defaults(func=cmd_fixtures)
    p = sub.add_parser("results", help="check one run and write report.md and summary.json")
    p.add_argument("run_dir")
    p.add_argument("--fixtures", default=str(FIXTURES_DIR))
    p.set_defaults(func=cmd_results)
    p = sub.add_parser("compare", help="compare two checked runs (A is the baseline)")
    p.add_argument("a")
    p.add_argument("b")
    p.set_defaults(func=cmd_compare)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
