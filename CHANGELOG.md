# Changelog

The skill version is in `.claude-plugin/plugin.json` and follows [Semantic Versioning](https://semver.org/). The result JSON has its own format version (`version` in `result.schema.json`, currently 2), which changes only when the result format changes incompatibly; such a change also raises the skill's major version. See "Versions" and "Releasing" in the README.

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
