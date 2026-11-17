#!/usr/bin/env python3
"""Run the MAGI eval fixtures in a headless agent.

For each fixture, starts the agent RUNS times with the fixture's request and
facts as the prompt and MAGI_RESULTS_DIR pointing at a folder of its own, so
the skill leaves its result JSON and progress log there. Nothing is judged
here; check.py reads the folders afterwards:

    python3 evals/run.py --name baseline-1.5.0
    python3 evals/check.py results evals/out/baseline-1.5.0

Layout of a run:

    evals/out/<name>/run.json                          what was run, and how
    evals/out/<name>/<fixture>/run-<k>/result/         MAGI_RESULTS_DIR
    evals/out/<name>/<fixture>/run-<k>/work/           the agent's empty working folder
    evals/out/<name>/<fixture>/run-<k>/stdout.txt, stderr.txt, meta.json

The agent itself runs in a temporary folder outside this repository, and
result/ and work/ are copied here when it ends. Claude Code treats any file
under the --plugin-dir tree as sensitive and denies Write there, even with
--add-dir, so a results folder under evals/out/ cannot be written directly.

The default command is Claude Code with this repository loaded as a plugin.
For another agent, pass the whole command with --cmd-json; "{prompt}",
"{plugin_dir}" and "{results_dir}" are filled in. A run that already has a
meta.json is skipped, so an interrupted run can be continued with the same
--name.

Every execution is a full deliberation (framing plus three units), so the
full set at 3 runs each uses a real amount of quota: the 1.5.0 baseline was
60 executions for about $49. --smoke runs one fixture per kind of behaviour
once, as a quick check that nothing broke; --only narrows a run by fixture,
category or pair. What the agent reports as its cost is kept in meta.json
and totalled by check.py.

Standard library only.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check  # noqa: E402  (fixture loading and validation live there)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT_DIR = HERE / "out"
PLUGIN_JSON = ROOT / ".claude-plugin" / "plugin.json"

# Web tools are denied so that a run depends only on the facts in the fixture.
# Bash is needed for the progress log helper; the agent works in an empty folder.
# The results folder sits outside that folder, so it is added with --add-dir.
DEFAULT_COMMAND = [
    "claude", "-p", "{prompt}",
    "--plugin-dir", "{plugin_dir}",
    "--add-dir", "{results_dir}",
    "--allowedTools", "Bash", "Read", "Write", "Agent", "Skill",
    "--disallowedTools", "WebSearch", "WebFetch",
    "--output-format", "json",
    "--no-session-persistence",
]

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


def build_prompt(fx: dict) -> str:
    words = PROMPT[fx.get("lang", "en")]
    parts = [words["ask"].format(request=fx["request"])]
    if fx["facts"]:
        parts.append("\n".join([words["facts"]] + [f"- {fact}" for fact in fx["facts"]]))
    interaction = fx.get("interaction", "go_ahead")
    if interaction != "ask":  # 'ask' adds nothing: a real question must end the turn
        parts.append(words[interaction])
    return "\n\n".join(parts)


def select(fixtures: dict, only: str) -> dict:
    if not only:
        return fixtures
    wanted = {w.strip() for w in only.split(",") if w.strip()}
    chosen = {fid: fx for fid, fx in fixtures.items()
              if fid in wanted or fx["category"] in wanted or fx.get("pair") in wanted}
    unknown = wanted - set(chosen) - {fx["category"] for fx in chosen.values()} \
        - {fx.get("pair") for fx in chosen.values()}
    if unknown:
        raise SystemExit(f"error: --only matched nothing for: {', '.join(sorted(unknown))}")
    return chosen


def run_once(fx: dict, k: int, run_root: Path, command: list, timeout: int, force: bool) -> str:
    run_dir = run_root / fx["id"] / f"run-{k}"
    if (run_dir / "meta.json").exists() and not force:
        return "skipped (already run)"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="magi-eval-") as tmp:
        status = _run_in(Path(tmp), fx, k, run_dir, command, timeout)
    return status


def _run_in(tmp: Path, fx: dict, k: int, run_dir: Path, command: list, timeout: int) -> str:
    result_dir, work_dir = tmp / "result", tmp / "work"
    result_dir.mkdir()
    work_dir.mkdir()

    prompt = build_prompt(fx)
    (run_dir / "prompt.txt").write_text(prompt + "\n", encoding="utf-8")
    argv = [part.replace("{prompt}", prompt).replace("{plugin_dir}", str(ROOT))
            .replace("{results_dir}", str(result_dir)) for part in command]
    env = dict(os.environ, MAGI_RESULTS_DIR=str(result_dir))

    started = time.monotonic()
    timed_out, exit_code = False, None
    with open(run_dir / "stdout.txt", "w", encoding="utf-8") as out, \
            open(run_dir / "stderr.txt", "w", encoding="utf-8") as err:
        try:
            exit_code = subprocess.run(argv, cwd=work_dir, env=env, stdin=subprocess.DEVNULL,
                                       stdout=out, stderr=err, timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            timed_out = True
    for sub in (result_dir, work_dir):
        shutil.copytree(sub, run_dir / sub.name, symlinks=True)
    results = sorted(p.name for p in (run_dir / "result").glob("*.json"))
    stdout = (run_dir / "stdout.txt").read_text(encoding="utf-8", errors="replace")
    meta = {"fixture": fx["id"], "run": k, "exit_code": exit_code, "timed_out": timed_out,
            "seconds": round(time.monotonic() - started, 1), "cost_usd": check.agent_cost(stdout),
            "agent_error": check.agent_error(stdout), "result_files": results}
    # Written last: its presence marks the run as finished.
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    if timed_out:
        return f"timed out after {timeout}s"
    if meta["agent_error"] and not results:
        return f"agent error: {meta['agent_error']}"
    return f"{'result' if results else 'no result'} (exit {exit_code}, {meta['seconds']}s)"


def git_commit() -> str:
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
                              check=True, capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--name", help="run name (default: <skill version>-<timestamp>)")
    parser.add_argument("--runs", type=int, help="executions per fixture (default 3; 1 with --smoke)")
    parser.add_argument("--smoke", action="store_true",
                        help="only the fixtures marked \"smoke\": true, one run each unless --runs is given")
    parser.add_argument("--only", default="", help="comma-separated fixture ids, categories or pair names")
    parser.add_argument("--jobs", type=int, default=1, help="executions in parallel (default 1)")
    parser.add_argument("--timeout", type=int, default=1800, help="seconds per execution (default 1800)")
    parser.add_argument("--model", help="passed to the default command as --model")
    parser.add_argument("--cmd-json", help='the agent command as a JSON list, e.g. \'["codex", "exec", "{prompt}"]\'')
    parser.add_argument("--fixtures", default=str(check.FIXTURES_DIR))
    parser.add_argument("--out", default=str(OUT_DIR))
    parser.add_argument("--force", action="store_true", help="run again even if a run already finished")
    parser.add_argument("--dry-run", action="store_true", help="print the prompts and the command, run nothing")
    args = parser.parse_args(argv)

    fixtures, errors = check.load_fixtures(Path(args.fixtures))
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 2
    if args.smoke:
        fixtures = {fid: fx for fid, fx in fixtures.items() if fx.get("smoke")}
    fixtures = select(fixtures, args.only)
    if not fixtures:
        print("error: no fixtures selected", file=sys.stderr)
        return 2
    runs = args.runs if args.runs is not None else (1 if args.smoke else 3)
    if runs < 1:
        print("error: --runs must be at least 1", file=sys.stderr)
        return 2

    if args.cmd_json:
        command = json.loads(args.cmd_json)
        if not isinstance(command, list) or not all(isinstance(p, str) for p in command) or not command:
            print("error: --cmd-json must be a non-empty JSON list of strings", file=sys.stderr)
            return 2
    else:
        command = DEFAULT_COMMAND + (["--model", args.model] if args.model else [])

    if args.dry_run:
        print("command:", json.dumps(command, ensure_ascii=False))
        for fid, fx in fixtures.items():
            print(f"\n=== {fid} ===\n{build_prompt(fx)}")
        return 0

    if shutil.which(command[0]) is None:
        print(f"error: {command[0]!r} is not on PATH", file=sys.stderr)
        return 2

    version = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))["version"]
    name = args.name or f"{version}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    run_root = Path(args.out) / name
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / "run.json").write_text(json.dumps({
        "name": name, "skill_version": version, "commit": git_commit(), "agent": command[0],
        "command": command, "model": args.model, "runs": runs, "smoke": args.smoke,
        "started": datetime.now().astimezone().isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    jobs = [(fx, k) for fx in fixtures.values() for k in range(1, runs + 1)]
    print(f"{len(fixtures)} fixtures x {runs} runs = {len(jobs)} executions -> {run_root}")

    def work(job):
        fx, k = job
        status = run_once(fx, k, run_root, command, args.timeout, args.force)
        print(f"  {fx['id']} run-{k}: {status}", flush=True)

    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        list(pool.map(work, jobs))
    print(f"\nNext: python3 evals/check.py results {run_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
