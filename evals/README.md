# MAGI evals

A fixed set of requests, run through the skill in a headless agent, with the results checked by a script. The purpose is to see whether a change to `SKILL.md` changes how MAGI behaves, before the change is released.

Nothing here is part of the skill: `evals/` is not in any release zip, and changing it needs no version bump.

## What is checked

| Check | Strictness | What it catches |
|---|---|---|
| Result schema | fails the fixture | A result JSON that does not match [`result.schema.json`](../skills/magi/result.schema.json) |
| Resolution rules | fails the fixture | A resolution that does not follow from the votes: a critical proposal passed by 2/3, a normal proposal on hold, a unit error outvoted, `approve_count` that disagrees with the units, on hold with no debate record. The rules are those of the run's skill version (`run.json`): from 1.6.0 a critical split is rejected and on hold is wrong |
| `expect.must` | fails the fixture unless every run meets it | Mode, grade or outcome on cases where only one answer is defensible |
| `expect.should` | warning | Things that are likely but arguable; reported as a rate |
| Framing | warning | A result framed by the moderator directly when the agent had subagents (the default command allows the Agent tool). `SKILL.md` allows that only when subagents are not available |
| Pairs | fails the pair | The same decision asked in opposite directions reaching different outcomes |

The verdict of a model is not deterministic, so each fixture is run several times (3 by default) and the report shows how the runs came out, not just pass or fail.

## Fixtures

One JSON file per fixture in [`fixtures/`](fixtures/); the file name is the id.

```json
{
  "id": "direction-lint-not-add",
  "category": "direction",
  "pair": "direction-lint",
  "lang": "ko",
  "interaction": "go_ahead",
  "smoke": true,
  "request": "CI에 린트 검사를 넣지 말까?",
  "facts": ["...", "..."],
  "expect": {
    "must": { "mode": "deliberation", "outcome": "change" },
    "should": { "grade": "normal" }
  },
  "note": "Why this fixture exists and what a failure means."
}
```

- `request` is passed to the skill unchanged. `facts` are given as the complete list of facts; web tools are off during a run, so a fixture has to carry everything the decision needs.
- `interaction` decides what the prompt says about questions:
  - `go_ahead` (default): proceed on assumptions without asking.
  - `ask`: nothing is added, so a real question must end the turn.
  - `unattended`: nobody can answer.
- `pair` names two fixtures that ask one decision in opposite directions (add / do not add, remove / keep), with the same facts.
- `smoke: true` puts the fixture in the short set that `run.py --smoke` runs: one fixture per kind of behaviour, chosen so that a broken skill fails at least one of them.

Checks available under `must` and `should`:

| Check | Value | Met when |
|---|---|---|
| `mode` | `deliberation` / `information` | the result's mode matches |
| `grade` | `normal` / `critical` | the main proposal's grade matches |
| `outcome` | `change` / `no_change` | `change`: the resolution is passed. `no_change`: rejected, or on hold in results before 1.6.0. Approve is always the change, so this is what happens to the current state |
| `verdict` | list of resolutions | the resolution is one of them (use `outcome` unless the difference between rejected and on hold matters; on hold appears only before 1.6.0) |
| `split` | `true` / `false` | the three units did (not) vote on both sides |
| `grade_raised` | `true` / `false` | the grade was (not) raised to critical by a unit's grade objection (`grade_raised` in the result; absent counts as false) |
| `follow_ups_min` | 0–2 | at least that many follow-up proposals |
| `follow_ups_max` | 0–2 | at most that many follow-up proposals. `0` on a request with one action and one reading: an alternative (another means, "fix it first", a variant) belongs under options outside the binary, not in a follow-up |
| `agenda_match`, `agenda_not_match`, `preset_match` | regex, case-insensitive | the text does (not) match. For the agenda, quoted text (`'…'`, `"…"`, `“…”`, `「…」`, backticks) and parenthetical notes (`(…)`) are left out first, so a note that cites the original question or spells out what the vote means does not count as the proposal |
| `units` | object, e.g. `{"melchior": "reject", "balthasar": "approve"}` | each unit listed cast that final vote (after a debate round, in results before 1.6.0). Any subset of the three units; used by the `conflict` fixtures, in `should` |
| `asks_questions` | `true` | the run stopped to ask: no result file, and the progress log shows a framing with questions and no `final` event. Needs `interaction: "ask"` and cannot be combined with other checks |

The current set:

| Category | Fixtures | Question |
|---|---|---|
| `direction` | 4 pairs | Does the wording of the request (add / not add, remove / keep) change the outcome? The lint pair is asked in Korean (`direction-lint`) and in English (`direction-lint-en`) with the same facts, so the language can be compared too |
| `clear` | 2 approve, 2 reject | Does a case with one defensible answer get that answer? |
| `grade` | 2 | Is an irreversible action critical, and a thought experiment normal? |
| `information` | 1 | Does an open question stay a question instead of a vote? |
| `pressure` | 2 | Does "the CTO decided" or "eight months already spent" move the result? |
| `split` | 2 | On a trade-off, do the three perspectives actually disagree? These have no expected outcome; what is tracked is how often the units vote on both sides. One is a personal decision, so it also shows whether that preset is chosen |
| `conflict` | 5 | Designed conflicts: each fact answers one unit's question in a clear direction, so every unit has an expected vote (`units`), and the fixtures differ in pattern (2-1 passed with the dissent on each unit in turn, 1-2 rejected, a critical proposal rejected at 2/3). Where the request states a goal, `agenda_match` checks that the framing kept it in the proposal. One is in Korean |
| `preset` | 6 | Designed conflicts outside the default preset: personal decision (2-1 passed, 1-2 rejected), ethics (a thought experiment, 2-1) and code review (a light objection that stays normal and passes 2-1; a security hole that makes the proposal critical, so two approvals are rejected; the same with the hole described only as behaviour, to leave room for a grade objection). Each fact answers one unit's question in that preset; expected votes are under `units`, and `grade_raised` checks whether a light objection was wrongly turned into a grade objection |
| `bundled` | 1 | A request with two actions that can be decided separately: does it still get a follow-up proposal (`follow_ups_min`) once alternatives are kept out of follow-ups? |
| `questions` | 2 | Does an ambiguous request end the turn on a question, and fall back properly when nobody can answer? |

When adding a fixture, put under `must` only what you would call a bug if it came out otherwise.

## Running

```bash
# Look at the prompts without running anything
python3 evals/run.py --dry-run

# A small trial: one pair, one run each
python3 evals/run.py --name trial --only direction-lint --runs 1

# The smoke set: one fixture per kind of behaviour, one run each
python3 evals/run.py --name smoke --smoke
python3 evals/check.py results evals/out/smoke

# The full set, three runs each
python3 evals/run.py --name baseline-1.5.0
python3 evals/check.py results evals/out/baseline-1.5.0
```

`check.py results` prints a report, writes `report.md` and `summary.json` into the run folder, and exits 1 if a fixture or a pair failed.

Each execution is a full deliberation (framing plus three units; before 1.6.0 also a debate round on a critical split), so a run costs real quota and time: the 1.5.0 baseline was 60 executions for about $49, roughly $0.80 each. Which run to use:

| Run | Executions | For |
|---|---|---|
| `--smoke` | 8 | A quick check that a change did not break anything: mode, grade, direction, pressure, stopping to ask. One run each cannot show a shift in how the units vote |
| `--only <names> --runs N` | as chosen | A change aimed at one behaviour. Something that happens in one run out of ten needs about thirty executions before its absence means anything |
| full set | fixtures x 3 | A baseline for a released version, and the comparison before a change to the rules of resolution or the unit perspectives |

`--only` takes fixture ids, categories or pair names and can be combined with `--smoke`; `--jobs` runs executions in parallel; a run that was interrupted continues where it stopped when started again with the same `--name`.

Besides the table of fixtures, the report gives three numbers for the whole run:

- **Executions**, with the cost the agent reported (Claude Code's `total_cost_usd`) and the time the agents ran.
- **Unanimous votes**: of the results that were voted on, how many had all three units on the same side. Most fixtures are clear-cut on purpose, so this is high; it is the number to watch when the perspectives, or the models behind the units, change.
- **Framed by the moderator directly**: how many results were framed without the framing agent although subagents were available.

The fixture table also has a **Units M · B · C** column: of a fixture's voted results, how many each unit approved (MELCHIOR-1, BALTHASAR-2, CASPER-3). `summary.json` keeps the same counts as `unit_approvals`. Read it next to a `units` expectation: three units that always vote together show as `3/3 · 3/3 · 3/3` or `0/3 · 0/3 · 0/3` whatever the fixture asks.

An execution in which the agent reports an error instead of working (not logged in, out of quota) is shown as `agent error: …` by both scripts.

The default agent is Claude Code (`claude -p`) with this repository loaded as a plugin through `--plugin-dir`, so the skill under test is the one in the working tree, not an installed copy. Bash, Read, Write, Agent and Skill are allowed and web tools are denied; the agent runs in an empty temporary folder outside the repository, with the results folder added through `--add-dir`, and both are copied to `evals/out/` when it ends. (Claude Code denies Write anywhere under the `--plugin-dir` tree as a sensitive file, so the results folder cannot live under `evals/out/` while the agent runs.) To run another agent, give the whole command as a JSON list, with that agent's own flags; `{prompt}`, `{plugin_dir}` and `{results_dir}` are filled in:

```bash
python3 evals/run.py --name codex-trial --cmd-json '["codex", "exec", "{prompt}"]'
```

The agent has to have the skill installed in that case, and has to be able to run shell commands, because results are collected through `MAGI_RESULTS_DIR`.

## Control: one question without the skill

```bash
python3 evals/run.py --name control-1 --control --model claude-opus-5-5
python3 evals/check.py control evals/out/control-1 evals/out/baseline-1.5.0 evals/out/after-1.5.1
```

`--control` asks each deliberation fixture (not information mode, not the ones that should stop to ask) the same request and facts once, with no skill: Claude Code runs with `--safe-mode --tools "" --strict-mcp-config`, so no installed plugin, skill, CLAUDE.md, MCP server or tool takes part. The prompt asks for `DECISION: change` or `DECISION: no_change`, and defines change as the action that changes the current state, so that a question asked in the negative ("should we not add X?") still answers in the same direction as MAGI, whose approve is always the change. The answer goes in each run's `meta.json`.

`check.py control` puts the control answers next to the majority outcome of the MAGI runs given (passed is change; rejected, and on hold before 1.6.0, are no_change) and ends with one line: on how many fixtures the control agreed with MAGI. A MAGI run counts for a fixture only if its `prompt.txt` matches the fixture's current request and facts, so runs made with an earlier version of a fixture are left out on their own. It writes `control.md` and `control.json` into the control folder. Agreement on nearly every fixture means that, on this set, the three units add no decision information over asking once; it says nothing about the reasons and recommendations MAGI also gives.

## Comparing two versions of the skill

```bash
git checkout main            && python3 evals/run.py --name before
git checkout my-skill-change && python3 evals/run.py --name after
python3 evals/check.py results evals/out/before
python3 evals/check.py results evals/out/after
python3 evals/check.py compare evals/out/before evals/out/after
```

`compare` lists every fixture with its status and mean approvals in both runs, then the run-wide numbers side by side, and exits 1 if a fixture that did not fail before fails now. With three runs per fixture, a difference of one run is within noise; look for fixtures that flip. A fixture that only one of the two runs covers (a smoke run against a full baseline) is shown as skipped or absent on that side and is never a regression.

`evals/out/` is ignored by git. To keep a baseline, copy its `report.md` and `summary.json` to `evals/baseline/<skill version>/`. `check.py results` refuses a folder that holds no runs, so it cannot overwrite a kept baseline by mistake.

## Tests

```bash
python3 evals/check.py fixtures
python3 -m unittest discover -s evals/tests -v
```

These run in CI on every pull request (**Eval tools** workflow). They validate the fixture files and test the checker and the runner with a fake agent; no model is called.
