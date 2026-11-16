# Changelog

The skill version is in `.claude-plugin/plugin.json` and follows [Semantic Versioning](https://semver.org/). The result JSON has its own format version (`version` in `result.schema.json`, currently 2), which changes only when the result format changes incompatibly; such a change also raises the skill's major version. See "Versions" and "Releasing" in the README.

## [1.3.0]

- Runs outside Claude: added a Codex plugin manifest (`.codex-plugin/plugin.json`, marketplace in `.agents/plugins/marketplace.json`) and a Gemini CLI extension manifest (`gemini-extension.json`). Other agents that read the Agent Skills format can install `skills/magi` with `npx skills add`.
- The skill text no longer assumes Claude: the moderator is "the agent in the main conversation", and the skill tells the host to use its own way of launching subagents, asking questions, drawing visuals and running commands, with the existing fallbacks where one is missing.
- JSON result and progress log: written wherever the agent can run shell commands and `MAGI_RESULTS_DIR` is set, not only in Claude Code.
- Release tooling: `bump` raises the version in all three manifests, and the version check fails if they disagree.
- The result JSON format is unchanged (version 2).

## [1.2.0]

- Default preset: BALTHASAR-2's perspective is now "risk and cost" instead of "safety and sustainability". Its questions add what the proposal costs to carry (money, time, upkeep, opportunity) and what is lost if it sits unused, so a low-risk adoption is no longer approved on physical safety alone. Its premise-doubt area adds the real cost.
- Default preset: the three questions no longer overlap. MELCHIOR-1 asks whether the means reaches the stated goal (its "simpler alternative" is now a technically simpler way to the same goal, not a cheaper one). CASPER-3 asks whether the goal itself is wanted and what is gained; "is it worth the effort" is removed, since effort is BALTHASAR-2's cost.
- In every preset, custom perspectives included, a unit builds its verdict on its own perspective's question; a point that belongs to another unit's question goes under recommendations.
- Code review preset: MELCHIOR-1 judges correctness on the intended path, BALTHASAR-2 everything off it (security, failure, compatibility), CASPER-3 readability, design and maintainability. "Failure" and "design" no longer sit in two units.
- Personal decision preset: now covers decisions that involve family or an organization as well as one's own. MELCHIOR-1 is "real gain and feasibility" (what it actually gets you, and whether it can be done with the ability and means at hand), and BALTHASAR-2 "risk, cost and relationships" (including what it does to the people affected with you). Before, two of the three perspectives looked only at what is gained, none at whether the plan is realistic, and decisions involving other people fell to custom perspectives.
- Original preset: used only when the user specifies it; the framing agent no longer chooses it. It is now listed in the README.
- Result card: drawn first, before the Markdown result, so the resolution is visible at a glance. The Markdown result still follows in full.
- The result JSON format is unchanged (version 2).

## [1.1.0]

- Debate round: every unit, majority as well as minority, must answer the strongest argument of each unit that voted the other way (rebut or concede).
- Debate round: a position change must quote the argument it relies on and name the source unit. The moderator checks that the argument appeared in that unit's first-round output and not already in the changing unit's own; a change that fails twice is not accepted and the unit's first-round verdict stands.
- Debate units now see the full first-round outputs and receive the input isolation instruction.
- Markdown result records each unit's rebuttals and the outcome of the change check; the round-2 `units_done` progress event adds `changed` and `change_accepted`. The result JSON format is unchanged (version 2).

## [1.0.1]

- No changes to the skill. This release checks the release process end to end: version check on the pull request, then the automatic tag and release on merge.

## [1.0.0]

First tagged release.

- Three-unit deliberation with a separate framing agent, normal and critical grades, debate round, and unanimity check.
- Presets: default, ethics, code review, personal decision, original, or custom perspectives.
- Input isolation: subagents use only the material they are given.
- Questions for the user before deliberation, with re-framing after every round of answers (up to 3 rounds).
- Follow-up proposals with per-unit verdicts in the Markdown result, the result card, and the JSON result.
- Optional result card, JSON result (`result.schema.json`, format version 2), and JSON Lines progress log.
- Claude Code plugin marketplace (`.claude-plugin/`) and a release zip for the Claude app.
- Version check on pull requests and automatic tag and release on merge.
