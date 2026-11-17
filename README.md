# MAGI — Three-Perspective Majority Deliberation Skill

Inspired by the MAGI system in *Neon Genesis Evangelion*.

An agent skill (Claude, Codex, Gemini CLI, and other agents that read the open Agent Skills format) that has three perspectives evaluate one proposal **without seeing each other's results**, then resolves it by a voting rule. The goal is to keep a decision from leaning on a single viewpoint and to keep dissent on the record instead of erasing it. The final decision always belongs to the user; the MAGI resolution is input to that decision.

![MAGI deliberation flow](docs/flow.svg)

> The skill is written in English, and MAGI answers in the language of your request. Ask in Korean and you get the result in Korean; you can also name a language explicitly (e.g. "answer in Japanese").

## Roles

| Role | Responsibility |
|---|---|
| Moderator (main conversation) | Gathers facts, runs the agents, tallies the vote, reports |
| Framing agent | Writes the proposal, grade, premises, preset, follow-up items, and questions for the user |
| MELCHIOR-1 · BALTHASAR-2 · CASPER-3 | Independent review (approve/reject, confidence, rationale, doubted premise) |

The agent that frames the proposal is separate from the one that summarizes the result, so judgment is not concentrated in one place.

## Resolution rules

| Grade | Criteria | Rule |
|---|---|---|
| Normal | Reversible, limited impact | Passes with 2/3 approval |
| Critical | Hard to reverse, or affects safety, security, data, or significant cost | Passes only if unanimous; on a split, one debate round and a revote; still split → on hold |

- Every vote is a plain approve or reject; there is no conditional approval. A condition is settled before the vote (checked as a fact, asked of the user, or proposed as a modified version), and advice for carrying out the decision is kept as a non-binding recommendation.
- Approve always means the change from the current state, so a question asked in the negative ("should we not add X?") gets the same result as its affirmative form. The result names the default (what happens if the proposal does not pass) and marks it when the default is itself harmful.
- If any unit objects to the grade, the item is raised to critical.
- In the debate round, every unit, majority as well as minority, must answer the other side's strongest argument. A unit may change position only by citing an argument another unit raised in the first round that it had not already weighed itself; the moderator checks this, and a change that fails keeps the unit's first-round verdict.
- If a unit fails, the other two do not vote alone; the result is reported as an **error**.
- When all three agree, shared premises and missing alternatives are checked once more.
- Questions that cannot be answered with approve/reject go to **information** mode: each perspective answers, with no vote.

## Presets

| Preset | MELCHIOR-1 | BALTHASAR-2 | CASPER-3 |
|---|---|---|---|
| Default | Technical feasibility | Risk and cost | Needs and value |
| Ethics | Consequentialism | Deontology | Virtue ethics and relationships |
| Code review | Correctness on the intended path | Security, failure, compatibility | Readability, design, maintainability |
| Personal decision | Real gain and feasibility | Risk, cost and relationships | Motivation and satisfaction |
| Original (only on request) | Scientist | Mother | Woman |

The framing agent picks the preset unless the user specifies one. If none fits, it designs three new perspectives that can genuinely conflict. In every preset, each unit builds its verdict on its own perspective's question, so two units do not vote on the same argument.

## Installation

Pick one way per agent. If you use both the Claude app and Claude Code with the same account, skills enabled in the app also load in Claude Code, so installing both ways gives you two copies of MAGI.

**Claude Code (plugin)**

```
/plugin marketplace add jwsung91/MAGI
/plugin install magi@jwsung91
```

On Claude Code 2.1.275 or later, one line does both: `/plugin install magi --marketplace jwsung91/MAGI`. Updates arrive through the marketplace when a new version is released.

**Claude app**

Download `magi-<version>.zip` from the [latest release](https://github.com/jwsung91/MAGI/releases/latest) and upload it in Customize > Skills. To update, upload the new zip and remove the old copy if it remains.

**Manual (Claude Code, no plugin)**

```bash
git clone https://github.com/jwsung91/MAGI.git
mkdir -p ~/.claude/skills
cp -r MAGI/skills/magi ~/.claude/skills/magi
```

A manual copy does not update itself. If you switch to the plugin, delete `~/.claude/skills/magi` first.

**Codex (plugin)** — not run yet; see Host support

```bash
codex plugin marketplace add jwsung91/MAGI
codex plugin add magi@jwsung91
```

**ChatGPT (plugin upload)**

Download `magi-plugin-<version>.zip` from the [latest release](https://github.com/jwsung91/MAGI/releases/latest) and upload it where ChatGPT accepts plugin ZIPs. The archive has `.codex-plugin/plugin.json` and `skills/magi/` at its root. ChatGPT has no subagents in a chat, so the units are written one at a time and the result says "Framing: moderator directly".

**Gemini app (skill upload)**

The Gemini app refuses skills that contain executable files, so upload `magi-chat-<version>.zip` from the [latest release](https://github.com/jwsung91/MAGI/releases/latest): the same skill without `scripts/` (the optional progress-log helper, which a chat app cannot run anyway). The units are written one at a time and the result says "Framing: moderator directly".

**Gemini CLI (extension)** — not run yet; see Host support

```bash
gemini extensions install https://github.com/jwsung91/MAGI
```

Update with `gemini extensions update magi`.

**Other agents (GitHub Copilot, Cursor, and others)**

Agents that read the Agent Skills format can install the skill folder with the [skills CLI](https://github.com/vercel-labs/skills):

```bash
npx skills add jwsung91/MAGI --skill magi
```

Or copy `skills/magi` into the agent's skills folder by hand (for example `.agents/skills/magi`).

## Host support

MAGI is developed on Claude. Other hosts load the same skill; what differs is whether they can run the units as separate agents and whether they stop to ask.

| Host | Units | Questions before deliberation | Status |
|---|---|---|---|
| Claude app, Claude Code | Separate subagents | Asks and waits | Primary host |
| ChatGPT (plugin upload) | One agent, each unit in turn | Did not stop in test runs; readings of an ambiguous request are deliberated as separate proposals | Tried by hand, 1.3.0 to 1.4.0 |
| Gemini app (skill upload) | One agent, each unit in turn | Varied between runs and models | Tried by hand, 1.3.0 to 1.4.0 |
| Codex CLI, Gemini CLI | Depends on the host | Not known | Manifests only; not run yet |
| Other agents via `npx skills` | Depends on the host | Not known | Install checked; not run yet |

Where one agent writes all three units, the result says so on its Limitations line; treat such a result as one model looking from three angles, not three independent reviews.

## Versions

The skill version is in [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json), mirrored in [`.codex-plugin/plugin.json`](.codex-plugin/plugin.json) and [`gemini-extension.json`](gemini-extension.json), and follows Semantic Versioning; changes are listed in [CHANGELOG.md](CHANGELOG.md). Version 1.0.0 marks the first public release, not a stability promise.

The result JSON has its own format version (`version` in [`result.schema.json`](skills/magi/result.schema.json)). Two rules connect the two:

- The format version changes only for an incompatible change to the result format. Adding an optional field keeps it.
- When the format version changes, the skill's major version goes up, because viewers that read the old format stop working.

| Skill | Result format | [MAGI-UI](https://github.com/jwsung91/MAGI-UI) |
|---|---|---|
| 1.x | 2 | reads format 2 |

## Releasing

Claude Code installs a plugin update only when the version string changes, so every change under `skills/` needs a new version.

1. In the pull request, raise the version and fill in the new CHANGELOG section:
   ```bash
   python3 .github/scripts/release_tools.py bump patch   # or minor / major
   ```
2. The **Version check** workflow fails the pull request if `skills/` changed without a bump, the version went down, the three manifests disagree, or the new version has no CHANGELOG entry.
3. After the merge, the **Release** workflow sees a version with no tag, creates tag `v<version>`, and publishes a GitHub Release with `magi-<version>.zip` and the CHANGELOG section. A push that keeps the version does nothing. To retry a failed release, run the workflow manually from the Actions tab.

## Evaluation

[`evals/`](evals/) holds a fixed set of requests (the same decision asked in opposite directions, clear-cut cases, grading, pressure, ambiguous requests) and scripts that run them through the skill in a headless agent and check the result JSON against the resolution rules and each fixture's expectations. Run it before releasing a change to `SKILL.md` and compare with the previous version; see [evals/README.md](evals/README.md). A real run uses quota, so CI only validates the fixtures and tests the scripts.

## Usage

```
/magi Replace keyword search with embedding search in the team wiki
/magi Open-source my side project next quarter
Decide with MAGI: should this PR go into this release?
/magi 이번 주에 운영 DB 스키마를 마이그레이션한다   # answered in Korean
```

Installed as a Claude Code plugin, the command is namespaced: `/magi:magi <proposal>`. Command forms differ between agents; asking in words ("decide with MAGI: …") works in all of them.

Works best where the agent can launch subagents, so the three units really cannot see each other. Otherwise the units are written one at a time, and the output says so.

## Result card

Where the agent can draw interactive visuals in the conversation (for example, the Claude app), MAGI shows a small result card first, followed by the full Markdown result: the resolution, the three units' verdicts, and each unit's rationale on click, including how each unit voted on any follow-up proposals. Elsewhere, such as a terminal agent, the card is skipped and the Markdown result is unchanged. Say "no card" to turn it off. The card is specified in [`skills/magi/references/card.md`](skills/magi/references/card.md).

## JSON output (optional)

Where the agent can run shell commands (Claude Code, Codex, Gemini CLI, and the like), if the environment variable `MAGI_RESULTS_DIR` is set, MAGI also saves each result as a JSON file in that folder, so other tools can read it. The format is described in [`skills/magi/result.schema.json`](skills/magi/result.schema.json). Enum values are always English; free text follows the output language. Without the variable, nothing is written.

With the same variable, MAGI also writes a progress log, one JSON line per step, to `$MAGI_RESULTS_DIR/<run_id>.jsonl`. Follow a run live with `tail -f "$MAGI_RESULTS_DIR"/*.jsonl`, or read it afterwards.

To view results on a screen, see [MAGI-UI](https://github.com/jwsung91/MAGI-UI), a separate local viewer.

## Limitations

All three units come from the same model, so this is not true design diversity; common-mode failure remains. For important decisions, also get a review from other sources, other people, or another model.

## Notice

- This is an unofficial personal project and is not affiliated with *Neon Genesis Evangelion* or its rights holders. It only borrows the decision-making idea of the MAGI system from the series.
- No artwork, logos, or images from the series are included. `docs/flow.svg` is an original diagram made for this repository.
- [MAGI-UI](https://github.com/jwsung91/MAGI-UI) shows results on the screen of [TomaszRewak/MAGI](https://github.com/TomaszRewak/MAGI) (MIT), a fan recreation. It lives in a separate repository; this repository includes none of its code or graphics.

## License

[MIT](LICENSE)
