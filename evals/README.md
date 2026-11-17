# MAGI evals

A fixed set of requests, run through the skill in a headless agent, with the results checked by a script. The purpose is to see whether a change to `SKILL.md` changes how MAGI behaves, before the change is released.

Nothing here is part of the skill: `evals/` is not in any release zip, and changing it needs no version bump.

## What is checked

| Check | Strictness | What it catches |
|---|---|---|
| Result schema | fails the fixture | A result JSON that does not match [`result.schema.json`](../skills/magi/result.schema.json) |
| Resolution rules | fails the fixture | A resolution that does not follow from the votes: a critical proposal passed by 2/3, a normal proposal on hold, a unit error outvoted, `approve_count` that disagrees with the units, on hold with no debate record |
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
| `outcome` | `change` / `no_change` | `change`: the resolution is passed. `no_change`: rejected or on hold. Approve is always the change, so this is what happens to the current state |
| `verdict` | list of resolutions | the resolution is one of them (use `outcome` unless the difference between rejected and on hold matters) |
| `split` | `true` / `false` | the three units did (not) vote on both sides |
| `follow_ups_min` | 0–2 | at least that many follow-up proposals |
| `agenda_match`, `agenda_not_match`, `preset_match` | regex, case-insensitive | the text does (not) match. For the agenda, quoted text (`'…'`, `"…"`, `“…”`, `「…」`, backticks) and parenthetical notes (`(…)`) are left out first, so a note that cites the original question or spells out what the vote means does not count as the proposal |
| `asks_questions` | `true` | the run stopped to ask: no result file, and the progress log shows a framing with questions and no `final` event. Needs `interaction: "ask"` and cannot be combined with other checks |

The current set:

| Category | Fixtures | Question |
|---|---|---|
| `direction` | 4 pairs | Does the wording of the request (add / not add, remove / keep) change the outcome? The lint pair is asked in Korean (`direction-lint`) and in English (`direction-lint-en`) with the same facts, so the language can be compared too |
| `clear` | 2 approve, 2 reject | Does a case with one defensible answer get that answer? |
| `grade` | 2 | Is an irreversible action critical, and a thought experiment normal? |
| `information` | 1 | Does an open question stay a question instead of a vote? |
| `pressure` | 2 | Does "the CTO decided" or "eight months already spent" move the result? |
| `split` | 4 | On a trade-off, do the three perspectives actually disagree? These have no expected outcome; what is tracked is how often the units vote on both sides. One is a personal decision, so it also shows whether that preset is chosen |
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

Each execution is a full deliberation (framing plus three units, and a debate round on a critical split), so a run costs real quota and time: the 1.5.0 baseline was 60 executions for about $49, roughly $0.80 each. Which run to use:

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

An execution in which the agent reports an error instead of working (not logged in, out of quota) is shown as `agent error: …` by both scripts.

The default agent is Claude Code (`claude -p`) with this repository loaded as a plugin through `--plugin-dir`, so the skill under test is the one in the working tree, not an installed copy. Bash, Read, Write, Agent and Skill are allowed and web tools are denied; the agent runs in an empty temporary folder outside the repository, with the results folder added through `--add-dir`, and both are copied to `evals/out/` when it ends. (Claude Code denies Write anywhere under the `--plugin-dir` tree as a sensitive file, so the results folder cannot live under `evals/out/` while the agent runs.) To run another agent, give the whole command as a JSON list, with that agent's own flags; `{prompt}`, `{plugin_dir}` and `{results_dir}` are filled in:

```bash
python3 evals/run.py --name codex-trial --cmd-json '["codex", "exec", "{prompt}"]'
```

The agent has to have the skill installed in that case, and has to be able to run shell commands, because results are collected through `MAGI_RESULTS_DIR`.

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
