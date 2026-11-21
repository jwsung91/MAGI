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
  control CONTROL_DIR MAGI_DIR...
                     Compare a control run (run.py --control: the same request
                     and facts asked once, without the skill) with the
                     majority outcome of the MAGI runs given. A MAGI run counts
                     for a fixture only if it was asked with the fixture's
                     current request and facts. Writes control.md and
                     control.json into CONTROL_DIR.

What is checked, in order of strictness:
  - schema and rules: hard. A result that breaks result.schema.json or the
    resolution rules (for example a normal proposal with 2/3 approvals that is
    not 'passed') fails its fixture, whatever the fixture expects. The rules
    are those of the run's skill version (run.json): before 1.6.0 a critical
    split goes through a debate round and, still split, on hold; from 1.6.0 it
    is rejected.
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

# Quoted text and parenthetical notes in an agenda are not the proposal
# itself: runs add notes that cite the original question ("원 질문은 '넣지
# 말까?'") or spell out what the vote means ("(rejected = yes, hold off)").
# A single quote counts only when it is not inside a word, so "don't" is not
# taken for a quote. Quotes go first, so a ")" inside a quote does not end a note.
QUOTED_RE = re.compile(r"""(?<!\w)'[^']*'(?!\w)|"[^"]*"|‘[^’]*’|“[^”]*”|「[^」]*」|『[^』]*』|`[^`]*`""")
PAREN_RE = re.compile(r"\([^()]*\)|（[^（）]*）")

# Words a result uses in "framing" when the moderator framed the proposal itself.
MODERATOR_FRAMING_RE = re.compile(r"moderator|모더레이터", re.I)


def agenda_text(result: dict) -> str:
    """The agenda without quoted text or parenthetical notes, for the agenda_match checks."""
    return PAREN_RE.sub(" ", QUOTED_RE.sub(" ", str(result.get("agenda", ""))))


FIXTURE_KEYS = {"id", "category", "pair", "lang", "interaction", "smoke", "request", "facts", "expect", "note"}
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
    "grade_raised": lambda v: isinstance(v, bool),
    "follow_ups_min": lambda v: type(v) is int and 0 <= v <= 2,
    "agenda_match": _is_regex,
    "agenda_not_match": _is_regex,
    "preset_match": _is_regex,
    "asks_questions": lambda v: isinstance(v, bool),
    # Final vote per unit; any subset of the three units.
    "units": lambda v: isinstance(v, dict) and bool(v) and set(v) <= set(UNIT_NAMES)
    and all(x in ("approve", "reject") for x in v.values()),
}


# --- prompts ----------------------------------------------------------------

# The words around the request, per fixture language. The request itself goes
# in unchanged; the skill answers in the language of the request.
PROMPT = {
    "en": {
        "ask": "Decide with MAGI: {request}",
        "facts": "Facts (this list is complete; do not look anything up):",
        "go_ahead": "If anything else is missing, treat it as an assumption and go ahead without asking me.",
        "unattended": "This is an unattended run: nobody can answer questions, and the turn cannot be handed back.",
    },
    "ko": {
        "ask": "MAGI로 판단해줘: {request}",
        "facts": "사실 (이 목록이 전부이며, 따로 찾아보지 않는다):",
        "go_ahead": "더 필요한 정보가 있으면 가정으로 두고, 나에게 묻지 말고 진행해줘.",
        "unattended": "이 실행은 무인 실행이다. 질문에 답할 사람이 없고, 턴을 넘길 수도 없다.",
    },
}

# The control: the same request and facts, asked once without the skill, with
# the answer defined the way MAGI's outcome is (approve is always the change),
# so that a negatively worded request cannot flip the comparison.
CONTROL_PROMPT = {
    "en": {
        "ask": "Decide: {request}",
        "answer": ("Answer with one decision. \"change\" means carrying out the action that changes the "
                   "current state; \"no_change\" means leaving things as they are. A question asked in the "
                   "negative (\"should we not add X?\") is the same decision: adding X is still \"change\". "
                   "If anything is missing, treat it as an assumption; do not ask questions.\n"
                   "End your answer with one line, exactly \"DECISION: change\" or \"DECISION: no_change\"."),
    },
    "ko": {
        "ask": "판단해줘: {request}",
        "answer": ("결정을 하나만 답해줘. \"change\"는 현재 상태를 바꾸는 행동을 하는 것이고, \"no_change\"는 "
                   "그대로 두는 것이다. 부정형으로 물은 질문(\"X를 넣지 말까?\")도 같은 결정이다: X를 넣는 것이 "
                   "여전히 \"change\"다. 빠진 정보는 가정으로 두고, 질문하지 마.\n"
                   "답의 마지막 줄은 정확히 \"DECISION: change\" 또는 \"DECISION: no_change\"로 끝내줘."),
    },
}
CONTROL_ANSWER_RE = re.compile(r"DECISION:\s*\**\s*(no_change|change)\b", re.I)


def _facts_block(words: dict, fx: dict) -> list:
    return ["\n".join([words["facts"]] + [f"- {fact}" for fact in fx["facts"]])] if fx["facts"] else []


def build_prompt(fx: dict) -> str:
    """The prompt run.py gives the agent for one MAGI execution of a fixture."""
    words = PROMPT[fx.get("lang", "en")]
    parts = [words["ask"].format(request=fx["request"])] + _facts_block(words, fx)
    interaction = fx.get("interaction", "go_ahead")
    if interaction != "ask":  # 'ask' adds nothing: a real question must end the turn
        parts.append(words[interaction])
    return "\n\n".join(parts)


def build_control_prompt(fx: dict) -> str:
    """The prompt for one control execution: same request and facts, no skill."""
    lang = fx.get("lang", "en")
    words = CONTROL_PROMPT[lang]
    parts = [words["ask"].format(request=fx["request"])] + _facts_block(PROMPT[lang], fx) + [words["answer"]]
    return "\n\n".join(parts)


def control_eligible(fx: dict) -> bool:
    """Fixtures that expect a deliberation: not information mode, not a run
    that should stop to ask."""
    checks = {**fx["expect"].get("must", {}), **fx["expect"].get("should", {})}
    return checks.get("mode") != "information" and "asks_questions" not in checks \
        and fx.get("interaction", "go_ahead") != "ask"


def control_answer(stdout: str):
    """'change' / 'no_change' from a control execution's output, or None."""
    report = _agent_report(stdout)
    text = report.get("result") if report else stdout
    found = CONTROL_ANSWER_RE.findall(str(text or ""))
    return found[-1].lower() if found else None


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
    if not isinstance(fx.get("smoke", False), bool):
        errors.append("smoke must be true or false")

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


# From skill 1.6.0 a critical proposal passes only with three approvals and is
# otherwise rejected: no debate round, no on hold. Earlier versions put a
# critical split through a debate round and, still split, on hold.
NO_DEBATE_FROM = (1, 6, 0)


def debate_rules(skill_version) -> bool:
    """Whether a run of this skill version used the debate round and on hold.
    An unknown or unreadable version is taken as an earlier one."""
    try:
        parts = tuple(int(x) for x in str(skill_version).split(".")[:3])
    except ValueError:
        return True
    return parts < NO_DEBATE_FROM


def expected_verdict(grade: str, votes: list, debate: bool = True):
    """The resolution SKILL.md section 4 gives for these final votes, under the
    rules with the debate round (debate=True) or without it (1.6.0 on)."""
    approvals = votes.count("approve")
    if grade == "normal":
        return "passed" if approvals >= 2 else "rejected"
    if grade == "critical":
        if not debate:
            return "passed" if approvals == 3 else "rejected"
        return {3: "passed", 0: "rejected"}.get(approvals, "on_hold")
    return None


def _check_proposal(label: str, proposal: dict, main: bool, problems: list, warnings: list,
                    debate: bool = True) -> None:
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
    want = expected_verdict(grade, votes, debate)
    if verdict != want:
        problems.append(f"{label}: a {grade} proposal with {approvals}/3 approvals is {want!r}, got {verdict!r}")


def check_rules(result: dict, debate: bool = True):
    """Return (problems, warnings) for things the schema cannot express.
    debate=False checks the 1.6.0 rules (see NO_DEBATE_FROM)."""
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
        _check_proposal("main proposal", result, True, problems, warnings, debate)
    if result.get("grade_raised") is True and result.get("grade") != "critical":
        problems.append("grade_raised is true but the grade is not critical")
    if debate and result.get("verdict") == "on_hold" and not str(result.get("debate", "")).strip():
        # A critical split always opens a debate round before it can end on hold.
        problems.append("main proposal: on hold without a debate round record")
    if not debate and str(result.get("debate", "")).strip():
        warnings.append("a debate round is recorded, but this skill version has none")
    follow_ups = result.get("follow_ups")
    for i, follow_up in enumerate(follow_ups if isinstance(follow_ups, list) else [], 1):
        if isinstance(follow_up, dict):
            _check_proposal(f"follow-up {i}", follow_up, False, problems, warnings, debate)
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


def _agent_report(stdout: str) -> dict:
    """What the agent printed about its own execution, or {}.

    Claude Code with --output-format json prints one JSON object (or, in
    stream form, a list whose last 'result' entry is that object). Other
    agents print nothing this script knows how to read."""
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return {}
    for entry in reversed(data if isinstance(data, list) else [data]):
        if isinstance(entry, dict) and ("total_cost_usd" in entry or entry.get("type") == "result"):
            return entry
    return {}


def agent_cost(stdout: str):
    """The cost in US dollars the agent reported for one execution, or None."""
    cost = _agent_report(stdout).get("total_cost_usd")
    if isinstance(cost, (int, float)) and not isinstance(cost, bool):
        return round(float(cost), 4)
    return None


def agent_error(stdout: str):
    """The error the agent reported instead of doing the work (not logged in,
    out of quota, over budget), or None."""
    report = _agent_report(stdout)
    if report.get("is_error") is True:
        return " ".join(str(report.get("result") or report.get("subtype") or "error").split())[:200]
    return None


def read_run(run_dir: Path, schema: dict, subagents: bool = False, debate: bool = True) -> dict:
    """One execution of one fixture: its result (if any), what is wrong with
    it, and whether the run stopped to ask the user. With subagents=True, a
    result framed by the moderator directly is a warning: SKILL.md allows that
    only when subagents are not available."""
    run = {"name": run_dir.name, "result": None, "problems": [], "warnings": [], "stopped_to_ask": None,
           "direct_framing": False, "seconds": None, "cost_usd": None}
    meta = {}
    if (run_dir / "meta.json").exists():
        try:
            meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    run["seconds"] = meta.get("seconds")
    run["cost_usd"] = meta.get("cost_usd")
    if run["cost_usd"] is None and (run_dir / "stdout.txt").exists():
        # A run made before run.py recorded the cost: read it from the agent's output.
        run["cost_usd"] = agent_cost((run_dir / "stdout.txt").read_text(encoding="utf-8", errors="replace"))
    result_dir = run_dir / "result"
    results = sorted(result_dir.glob("*.json")) if result_dir.is_dir() else []
    logs = sorted(result_dir.glob("*.jsonl")) if result_dir.is_dir() else []

    asked, finished = read_log(logs[-1]) if logs else (None, False)
    if not results:
        # No result file. With a log we can tell a turn that ended on questions
        # from a run that simply died.
        if logs:
            run["stopped_to_ask"] = bool(asked) and not finished
        if meta.get("timed_out"):
            run["warnings"].append("agent timed out")
        elif meta.get("agent_error"):
            run["warnings"].append(f"agent error: {meta['agent_error']}")
        elif meta.get("exit_code") not in (0, None):
            run["warnings"].append(f"agent exited with code {meta['exit_code']}")
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
    problems, warnings = check_rules(result, debate)
    run["problems"].extend(problems)
    run["warnings"].extend(warnings)
    if subagents and MODERATOR_FRAMING_RE.search(str(result.get("framing", ""))):
        run["direct_framing"] = True
        run["warnings"].append("framed by the moderator directly although subagents were available")
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
    if key == "grade_raised":
        return (result.get("grade_raised") is True) == want
    if key == "follow_ups_min":
        follow_ups = result.get("follow_ups")
        return len(follow_ups if isinstance(follow_ups, list) else []) >= want
    if key == "agenda_match":
        return re.search(want, agenda_text(result), re.I) is not None
    if key == "agenda_not_match":
        return re.search(want, agenda_text(result), re.I) is None
    if key == "preset_match":
        return re.search(want, str(result.get("preset", "")), re.I) is not None
    if key == "units":
        # Final votes, after a debate round if there was one.
        units = result.get("units") if isinstance(result.get("units"), dict) else {}
        return all((units.get(name) or {}).get("verdict") == vote for name, vote in want.items())
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
           "majority_outcome": None, "must": {}, "should": {}, "notes": [],
           "votes": {"results": 0, "unanimous": 0},
           "unit_approvals": {name: 0 for name in UNIT_NAMES},
           "direct_framing": 0, "cost_usd": None, "seconds": None}
    if not runs:
        out["status"] = "skipped"
        return out

    # Counted over results that were voted on: how often all three units landed
    # on the same side, how often each unit approved, and how often the
    # moderator framed the proposal itself.
    for r in runs:
        votes = unit_votes(r["result"].get("units")) if r["result"] is not None else []
        if r["result"] is not None and r["result"].get("mode") != "information" \
                and set(votes) <= {"approve", "reject"}:
            out["votes"]["results"] += 1
            out["votes"]["unanimous"] += len(set(votes)) == 1
            for name, vote in zip(UNIT_NAMES, votes):
                out["unit_approvals"][name] += vote == "approve"
    out["direct_framing"] = sum(1 for r in runs if r["direct_framing"])
    costs = [r["cost_usd"] for r in runs if r["cost_usd"] is not None]
    seconds = [r["seconds"] for r in runs if r["seconds"] is not None]
    out["cost_usd"] = round(sum(costs), 4) if costs else None
    out["seconds"] = round(sum(seconds), 1) if seconds else None

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
    meta = {}
    if (run_dir / "run.json").exists():
        try:
            meta = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    # The default command allows the Agent tool, so the skill had subagents.
    # For another agent this is not known, and the framing check is skipped.
    subagents = "Agent" in (meta.get("command") or [])
    # The resolution rules the run's skill version used.
    debate = debate_rules(meta.get("skill_version"))

    evaluated = {}
    for fid, fx in fixtures.items():
        fixture_dir = run_dir / fid
        run_dirs = sorted(p for p in fixture_dir.glob("run-*") if p.is_dir()) if fixture_dir.is_dir() else []
        evaluated[fid] = evaluate_fixture(fx, [read_run(p, schema, subagents, debate) for p in run_dirs])
    pairs = evaluate_pairs(fixtures, evaluated)
    totals = Counter(e["status"] for e in evaluated.values())
    ran = [e for e in evaluated.values() if e["runs"]]
    costs = [e["cost_usd"] for e in ran if e["cost_usd"] is not None]
    seconds = [e["seconds"] for e in ran if e["seconds"] is not None]
    with_result = sum(n for e in ran for label, n in e["results"].items() if label not in ("asked", "no result"))
    return {
        "run": meta.get("name", run_dir.name),
        "skill_version": meta.get("skill_version"),
        "agent": meta.get("agent"),
        "model": meta.get("model"),
        "totals": {s: totals.get(s, 0) for s in ("pass", "warn", "fail", "skipped")},
        "pairs_failed": sum(1 for p in pairs.values() if p["status"] == "fail"),
        "executions": sum(e["runs"] for e in ran),
        "cost_usd": round(sum(costs), 2) if costs else None,
        "seconds": round(sum(seconds)) if seconds else None,
        "votes": {"results": sum(e["votes"]["results"] for e in ran),
                  "unanimous": sum(e["votes"]["unanimous"] for e in ran)},
        # None when the agent's subagents are not known (a --cmd-json command).
        "framing": {"results": with_result, "direct": sum(e["direct_framing"] for e in ran)} if subagents else None,
        "fixtures": evaluated,
        "pairs": pairs,
    }


def _cell(text) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _duration(seconds) -> str:
    minutes = round(seconds / 60)
    return f"{minutes // 60}h {minutes % 60:02d}m" if minutes >= 60 else f"{minutes}m"


def _stats(summary: dict) -> dict:
    """The run-wide numbers as text, keyed by label. Summaries written before
    these numbers existed simply have none."""
    stats = {}
    n = summary.get("executions")
    if n:
        parts = [str(n)]
        if summary.get("cost_usd") is not None:
            parts.append(f"${summary['cost_usd']:.2f} (${summary['cost_usd'] / n:.2f} each)")
        if summary.get("seconds") is not None:
            parts.append(f"{_duration(summary['seconds'])} of agent time")
        stats["Executions"] = " · ".join(parts)
    votes = summary.get("votes")
    if votes and votes["results"]:
        stats["Unanimous votes"] = f"{votes['unanimous']} of {votes['results']} voted results"
    framing = summary.get("framing")
    if framing and framing["results"]:
        stats["Framed by the moderator directly"] = f"{framing['direct']} of {framing['results']} results"
    return stats


def _unit_cell(e: dict) -> str:
    """'2/3 · 0/3 · 3/3': approvals per unit over the voted results. Summaries
    written before this count existed have none."""
    voted, approvals = e.get("votes", {}).get("results"), e.get("unit_approvals")
    if not voted or not approvals:
        return "—"
    return " · ".join(f"{approvals[name]}/{voted}" for name in UNIT_NAMES)


def _stat_lines(summary: dict) -> list:
    return [f"{label}: {text}  " for label, text in _stats(summary).items()] + ([""] if _stats(summary) else [])


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
        *_stat_lines(summary),
        "Units M · B · C: how many of the voted results each unit approved "
        "(MELCHIOR-1, BALTHASAR-2, CASPER-3).",
        "",
        "| Fixture | Status | Results | Approvals (mean) | Units M · B · C | Notes |",
        "|---|---|---|---|---|---|",
    ]
    for fid, e in summary["fixtures"].items():
        results = ", ".join(f"{label} {n}" for label, n in sorted(e["results"].items())) or "—"
        approvals = "—" if e["approvals_mean"] is None else f"{e['approvals_mean']}/3"
        notes = "; ".join(e["notes"][:4]) + (f"; … (+{len(e['notes']) - 4})" if len(e["notes"]) > 4 else "")
        lines.append(f"| {fid} | {e['status']} | {results} | {approvals} | {_unit_cell(e)} | {_cell(notes) or '—'} |")
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
        elif sa != sb and not {sa, sb} & {"skipped", "absent"}:
            mark = "changed"  # a fixture only one run covers is not a change
        fmt = lambda e: "—" if not e or e["approvals_mean"] is None else f"{e['approvals_mean']}/3"
        lines.append(f"| {fid} | {sa} | {sb} | {fmt(ea)} | {fmt(eb)} | {mark} |")
    for pair in sorted(set(a.get("pairs", {})) & set(b.get("pairs", {}))):
        pa, pb = a["pairs"][pair]["status"], b["pairs"][pair]["status"]
        if pb == "fail" and pa == "pass":
            regressions.append(f"pair {pair}")
    sa, sb = _stats(a), _stats(b)
    if sa or sb:
        lines += ["", "| | A | B |", "|---|---|---|"]
        lines += [f"| {label} | {sa.get(label, '—')} | {sb.get(label, '—')} |"
                  for label in dict.fromkeys(list(sa) + list(sb))]
    lines += ["", f"Regressions: {', '.join(regressions) if regressions else 'none'}"]
    return "\n".join(lines) + "\n", regressions


# --- control ----------------------------------------------------------------

def _majority(outcomes: list):
    counts = Counter(o for o in outcomes if o in ("change", "no_change"))
    if not counts:
        return None
    top = counts.most_common(2)
    return "tie" if len(top) == 2 and top[0][1] == top[1][1] else top[0][0]


def _run_dirs(base: Path, fid: str) -> list:
    fixture_dir = base / fid
    return sorted(p for p in fixture_dir.glob("run-*") if p.is_dir()) if fixture_dir.is_dir() else []


def _asked_with(run_dir: Path, prompt: str) -> bool:
    """Whether this execution was given exactly this prompt, so that runs made
    with an earlier version of a fixture's facts are not counted."""
    path = run_dir / "prompt.txt"
    return path.exists() and path.read_text(encoding="utf-8").strip() == prompt.strip()


def check_control(control_dir: Path, magi_dirs: list, fixtures: dict) -> dict:
    """The control answers per fixture next to MAGI's majority outcome."""
    rows = {}
    for fid, fx in fixtures.items():
        if not control_eligible(fx):
            continue
        answers = []
        for run_dir in _run_dirs(control_dir, fid):
            if not (run_dir / "meta.json").exists() or not _asked_with(run_dir, build_control_prompt(fx)):
                continue
            meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
            answers.append(meta.get("answer"))
        magi, sources = [], []
        prompt = build_prompt(fx)
        for base in magi_dirs:
            counted = 0
            for run_dir in _run_dirs(base, fid):
                if not _asked_with(run_dir, prompt):
                    continue
                results = sorted((run_dir / "result").glob("*.json")) if (run_dir / "result").is_dir() else []
                if not results:
                    continue
                try:
                    result = json.loads(results[-1].read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    continue
                magi.append(OUTCOME.get(result.get("verdict")) if isinstance(result, dict) else None)
                counted += 1
            if counted:
                sources.append(f"{base.name} ({counted})")
        if not answers and not magi:
            continue
        control, majority = _majority(answers), _majority(magi)
        if control in (None, "tie") or majority in (None, "tie"):
            agree = None
        else:
            agree = control == majority
        rows[fid] = {"control": answers, "control_majority": control,
                     "magi": dict(Counter(o or "none" for o in magi)), "magi_majority": majority,
                     "magi_sources": sources, "agree": agree}
    compared = [r for r in rows.values() if r["agree"] is not None]
    return {"control": control_dir.name, "magi": [p.name for p in magi_dirs], "fixtures": rows,
            "compared": len(compared), "agreed": sum(1 for r in compared if r["agree"])}


def render_control(summary: dict) -> str:
    fmt = lambda counts: ", ".join(f"{k} {n}" for k, n in sorted(counts.items())) or "—"
    lines = [f"# MAGI Control Comparison: `{summary['control']}` vs MAGI ({', '.join(summary['magi'])})", "",
             "The control asks the same request and facts once, without the skill, and answers "
             "change or no_change. MAGI's outcome: passed is change; rejected and on hold are no_change.", "",
             "| Fixture | Control answers | Control majority | MAGI outcomes | MAGI majority | Agree | MAGI runs from |",
             "|---|---|---|---|---|---|---|"]
    for fid, r in summary["fixtures"].items():
        answers = fmt(Counter(a or "no answer" for a in r["control"]))
        agree = {True: "yes", False: "**no**", None: "—"}[r["agree"]]
        lines.append(f"| {fid} | {answers} | {r['control_majority'] or '—'} | {fmt(r['magi'])} | "
                     f"{r['magi_majority'] or '—'} | {agree} | {', '.join(r['magi_sources']) or '—'} |")
    lines += ["", f"Control agreed with MAGI on {summary['agreed']} of {summary['compared']} fixtures "
                  "(fixtures with a clear majority on both sides)."]
    return "\n".join(lines) + "\n"


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
    if _is_control(run_dir):
        print(f"error: {run_dir} is a control run; use: check.py control {run_dir} MAGI_DIR...", file=sys.stderr)
        return 2
    summary = check_results(run_dir, fixtures)
    if not summary["executions"]:
        # Nothing to check, and writing a report would replace one that is
        # kept there on purpose (evals/baseline/<version>/ holds only reports).
        print(f"error: no runs of any fixture in {run_dir}", file=sys.stderr)
        return 2
    report = render_report(summary)
    (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (run_dir / "report.md").write_text(report, encoding="utf-8")
    print(report)
    return 1 if summary["totals"]["fail"] or summary["pairs_failed"] else 0


def cmd_compare(args) -> int:
    report, regressions = render_compare(load_summary(Path(args.a)), load_summary(Path(args.b)))
    print(report)
    return 1 if regressions else 0


def _is_control(run_dir: Path) -> bool:
    try:
        return json.loads((run_dir / "run.json").read_text(encoding="utf-8")).get("control") is True
    except (OSError, json.JSONDecodeError):
        return False


def cmd_control(args) -> int:
    control_dir, magi_dirs = Path(args.control_dir), [Path(p) for p in args.magi_dirs]
    for path in [control_dir] + magi_dirs:
        if not path.is_dir():
            print(f"error: {path} is not a directory", file=sys.stderr)
            return 2
    if not _is_control(control_dir):
        print(f"error: {control_dir} is not a control run (run.py --control)", file=sys.stderr)
        return 2
    fixtures, errors = load_fixtures(Path(args.fixtures))
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 2
    summary = check_control(control_dir, magi_dirs, fixtures)
    report = render_control(summary)
    (control_dir / "control.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                                              encoding="utf-8")
    (control_dir / "control.md").write_text(report, encoding="utf-8")
    print(report)
    return 0


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
    p = sub.add_parser("control", help="compare a control run with MAGI runs")
    p.add_argument("control_dir")
    p.add_argument("magi_dirs", nargs="+")
    p.add_argument("--fixtures", default=str(FIXTURES_DIR))
    p.set_defaults(func=cmd_control)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
