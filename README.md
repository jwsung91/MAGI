# MAGI — Three-Perspective Majority Deliberation Skill

A Claude skill that has three perspectives evaluate one proposal **without seeing each other's results**, then resolves it by a voting rule. The goal is to keep a decision from leaning on a single viewpoint and to keep dissent on the record instead of erasing it. The final decision always belongs to the user; the MAGI resolution is input to that decision.

![MAGI deliberation flow](docs/flow.svg)

> Two versions of the same skill are included: `skills/magi-en/` (English) and `skills/magi/` (Korean, the original). Both use the skill name `magi`, so install only one of them.

## Roles

| Role | Responsibility |
|---|---|
| Moderator (main conversation) | Gathers facts, runs the agents, tallies the vote, reports |
| Framing agent | Writes the proposal, grade, premises, preset, follow-up items, and questions for the user |
| MELCHIOR-1 · BALTHASAR-2 · CASPER-3 | Independent review (verdict, confidence, rationale, doubted premise) |

The agent that frames the proposal is separate from the one that summarizes the result, so judgment is not concentrated in one place.

## Resolution rules

| Grade | Criteria | Rule |
|---|---|---|
| Normal | Reversible, limited impact | Passes with 2/3 approval |
| Critical | Hard to reverse, or affects safety, security, data, or significant cost | Passes only if unanimous; on a split, one debate round and a revote; still split → on hold |

- A conditional approval counts as approval, but all conditions are collected and the result is marked **conditionally passed**. Conflicting conditions are not merged; the user chooses.
- If any unit objects to the grade, the item is raised to critical.
- If a unit fails, the other two do not vote alone; the result is reported as an **error**.
- When all three agree, shared premises and missing alternatives are checked once more.
- Questions that cannot be answered with approve/reject go to **information** mode: each perspective answers, with no vote.

## Presets

| Preset | MELCHIOR-1 | BALTHASAR-2 | CASPER-3 |
|---|---|---|---|
| Default | Technical feasibility | Safety and sustainability | Needs and value |
| Ethics | Consequentialism | Deontology | Virtue ethics and relationships |
| Code review | Correctness and design | Security, failure, compatibility | Readability and maintainability |
| Personal decision | Growth and capability | Risk and stability | Motivation and satisfaction |

The framing agent picks the preset unless the user specifies one. If none fits, it designs three new perspectives that can genuinely conflict.

## Installation

**Claude Code**

```bash
git clone https://github.com/jwsung91/MAGI.git
mkdir -p ~/.claude/skills
cp -r MAGI/skills/magi-en ~/.claude/skills/magi   # English
# or
cp -r MAGI/skills/magi ~/.claude/skills/magi      # Korean
```

**Claude app**

Zip one of the two folders (`skills/magi-en` or `skills/magi`) and upload it with the Claude app's skill upload feature.

## Usage

```
/magi Replace keyword search with embedding search in the team wiki
/magi Open-source my side project next quarter
Decide with MAGI: should this PR go into this release?
```

Works best where subagents are available (Claude Code, or agent features in the Claude app). Otherwise the units are written one at a time, and the output says so.

## Limitations

All three units come from the same model, so this is not true design diversity; common-mode failure remains. For important decisions, also get a review from other sources, other people, or another model.

## Notice

- This is an unofficial personal project and is not affiliated with *Neon Genesis Evangelion* or its rights holders. It only borrows the decision-making idea of the MAGI system from the series.
- No artwork, logos, or images from the series are included. `docs/flow.svg` is an original diagram made for this repository.
- If you want to view results in a series-style screen, see [TomaszRewak/MAGI](https://github.com/TomaszRewak/MAGI) (MIT). This repository does not include its code.

## License

[MIT](LICENSE)
