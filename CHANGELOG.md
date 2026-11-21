# Changelog

The skill version is in `.claude-plugin/plugin.json` and follows [Semantic Versioning](https://semver.org/). The result JSON has its own format version (`version` in `result.schema.json`, currently 2), which changes only when the result format changes incompatibly; such a change also raises the skill's major version. See "Versions" and "Releasing" in the README.

## [1.6.2]

Follow-up proposals come only from the request. In the 1.6.1 runs the framing agent turned an alternative into a voted follow-up proposal in 9 of 30 runs ("store passwords with bcrypt instead of MD5", "run the tests, then merge", "speed up the slowest pages separately", the footbridge variant of the trolley problem). Facts are not gathered for alternatives, so those votes had little to stand on, and they put a resolution on something nobody asked.

- The framing makes a follow-up proposal only for another action in the request that can be decided separately, or for another reading of the request when the user cannot be asked. Another means to the same goal, doing it after a fix, trying a smaller version first, or a variant of a thought experiment is named under options outside the binary only.
- The moderator points out a follow-up proposal that is an alternative not in the request and runs the framing agent once more before the units run, as for a contradiction.
- Self-check: every follow-up proposal is another action in the request or another reading of it.
- Resolution rules, grades, presets and the result JSON format (version 2) are unchanged.

Evidence (claude-opus-5-5): on the seven fixtures where an alternative had become a follow-up in the 1.6.1 runs, one run each, one follow-up remained (the trolley case: "permissible, not required", closer to another reading of "should" than to an alternative); the alternatives stayed under options outside the binary or recommendations. Legitimate follow-ups were kept: a request with two separate actions got one in 2 of 2 runs, and the unattended ambiguous release kept its other reading. The framing agent was never re-run by the moderator. No `must` failures.

## [1.6.1]

Fills gaps in the 1.6.0 rules and records the hand checks on ChatGPT and the Gemini app. The default preset, the resolution rules, the grade criteria and the result JSON format (version 2) are unchanged.

- The perspectives of the ethics, code review, personal decision and original presets are rewritten as questions whose yes means approve, with the same content, and each preset says which kind of fact goes to which unit. In 1.6.0 they were lists of topics, and the ethics preset's deontology question ("must this not be done?") meant reject when answered yes. A custom preset designed by the framing agent takes the same form.
- A grade objection needs a fact from the list of facts that meets a critical criterion (hard to reverse, safety, security, data loss, large cost). A strong objection alone is a reject vote. The moderator checks the named fact; an objection without one is not accepted and the Grade line says so. A grade raised by an objection is named on the resolution line.
- The resolution line names the units that voted against the proposal, whether it passed or was rejected (it said "the minority").
- A resolution that is not unanimous is followed by one fixed line, in the output language: the resolution counts the answers of three aspects and is not a judgment that the proposal is best overall; weigh the aspect that voted the other way from the resolution (against a passed proposal, for a rejected one). No new JSON field.
- A modified version or a proposal with a different goal suggested by a unit is listed only as a candidate for a separate decision and is not deliberated or voted on in the same run.
- The progress log no longer describes round 2 fields in `units_done`.

What was verified (claude-opus-5-5, five new preset fixtures: 1.6.0 once each, 1.6.1 three times each; 15 regression fixtures once):
- Preset perspectives as questions: unit votes as designed 12 of 15 before and 38 of 45 after, no measurable difference. This change makes the wording clear rather than fixing a measured failure.
- Grade objection rule: no run raised a grade objection, so the path that raises a grade by objection is not verified. The security fixture was graded critical by the framing every time.
- Notice line and resolution line: present on every non-unanimous resolution (26 of 26), absent on every unanimous one.
- The separate-decision rule binds the units and the moderator. Follow-up proposals that the framing agent makes up from alternatives not in the request (seen before 1.6.0 too) are left to 1.6.2.

## [1.6.0]

**What a resolution means has changed.** Each unit now votes on its own perspective's question only, and the resolution counts those answers. A pass means two of the three aspects hold on a normal proposal, and all three on a critical one; it no longer means "best on balance". How much the failing aspect weighs is the user's to judge, and the resolution line names it. Results from earlier versions, where each unit weighed the whole decision, cannot be compared with these directly.

- A unit approves when the answer to its own question is yes; weighing every gain against every cost is left to the tally. In the default preset MELCHIOR-1 approves if the means reaches the stated goal, BALTHASAR-2 if the cost and the loss on failure are acceptable against the default, and CASPER-3 if the people affected want the result.
- One kind of fact per unit in the default preset: reaching the goal and simpler ways to it (MELCHIOR-1); money, time, risk, reversibility, savings and the cost of the default (BALTHASAR-2); whether the people affected want the result (CASPER-3).
- The options outside the binary are a reason for a verdict only for the unit that asks for a simpler way to the same goal (MELCHIOR-1 by default); for the others they are recommendations.
- A critical proposal passes only with all three approvals and is otherwise rejected. The debate round and on hold are gone. A resolution that is not unanimous names the minority unit and its reason; a rejection whose default is harmful or costly says that not passing is also a choice.
- The grade follows what the facts say about reversibility and impact: a change the facts say reverts cleanly is not critical only because it reaches production; the default makes a proposal critical only when its harm is hard to reverse or severe, not for an ongoing cost; an unstated term is an assumption, not a reason to raise the grade.
- The result JSON format is unchanged (version 2). `on_hold` and `debate` stay in the schema for earlier results and are no longer written. The result card no longer has an on-hold badge, and a critical rejection with one or two approvals says that all three were needed.

Evidence (second round of the experiment, claude-opus-5-5, five designed-conflict fixtures x 3 and 15 regression fixtures x 1): designed conclusion in 12 of 15 conflict runs, unit votes as designed in 37 of 45, expected grade in 15 of 15, and no change in the outcome of any clear-cut case.

Known limits:
- A 2-1 result is one vote from the other outcome: in the experiment, running the same request again gave a different conclusion about one time in five.
- A fact on the border of two perspectives (for example, people's dislike of a change) may be counted by a different unit from run to run.
- Verified only in Claude Code with subagents.

## [1.5.2]

From the per-unit vote experiment (#18), where this was the one change that worked on its own.

- Framing keeps a goal the request states ("to make our pages faster") in the proposal sentence. In the experiment's runs on 1.5.1 the goal was dropped from the proposal in 8 of 11 runs where the request stated one, which left the technical unit nothing to measure the means against; with this rule it stayed in 15 of 15. A request with no stated goal is unchanged: the goal is a premise, or a question for the user when only the user can answer it and it could decide the outcome.
- Resolution rules, grades and the result JSON format are unchanged (version 2).

## [1.5.1]

Fixes from the 1.5.0 eval baseline (60 runs in Claude Code, where subagents are available).

- The framing agent frames every request wherever subagents can be launched. In 6 of 60 runs the moderator had framed the proposal itself; the Flow summary read as a free choice ("framing agent, or the moderator directly"), and the condition came only later. A short or clear-looking request is not a reason to skip the framing agent.
- Self-check: a proposal the moderator framed although subagents can be launched is framed again by the framing agent, and the review is repeated from that result.
- Result JSON in information mode leaves out `grade`, `grade_raised`, `verdict` and `approve_count`. One run had carried the framing's grade into a result with no vote.
- Resolution rules and the result JSON format are unchanged (version 2).

## [1.5.0]

- Proposal direction: approve is always the action that changes the current state. A request asked in the negative ("should we not add X?") is framed in its affirmative form, so the same votes no longer give a different result depending on how the question was worded. Removing something that exists is a different decision from not adding it.
- The framing names the default (what stays or happens if the proposal does not pass) and marks it when the default is itself harmful or hard to reverse; either side can make a proposal critical. The units receive the default with the proposal.
- Output format: a "Default if not passed" line; the resolution line says the outcome in plain words, answering the question as the user asked it. On hold with a harmful default says that leaving it on hold is also a choice.
- Self-check: direction.
- Resolution rules are unchanged. The result JSON format is unchanged (version 2).

## [1.4.0]

Fixes from test runs in ChatGPT and the Gemini app with 1.3.2, where one agent writes everything and no subagents exist.

- New "Flow" section near the top: gather facts, frame, ask the user and stop, review, resolve, self-check, report.
- Questions for the user end the turn: the moderator does not deliberate in the same turn or answer them itself. A request whose readings lead to different proposals is a question, not an assumption. Both hosts had skipped the questions and filled in what the request meant.
- Fallback when deliberation happens without the user having been asked (an unattended run, or a host that does not hand the turn back): the reading closest to the user's words is the main proposal, each other reading a follow-up, and the questions that were not asked are listed under Additional information.
- Input isolation also binds the moderator when it writes the framing and the units itself: a personal detail about the user enters only through the list of facts. A Gemini run had units cite the user's job from outside the material.
- The framing line says "framing agent" only when a separate agent framed the proposal, and units written in turn by one agent are not called independent agents.
- Output format: a **Limitations** line at the end says how the units were run; each follow-up has its own grade and a "Follow-up 1: … — grade — resolution" line (the stray "Then Resolution" template line is gone); headings marked "(if any)" are left out when they do not apply, every other heading is required.
- Self-check before reporting: questions, framing line, facts, cell values, debate answers from every unit, both unanimity points, the Limitations line, translated headings. Subagent output that fails is re-run, never edited.
- The result JSON format is unchanged (version 2).

## [1.3.2]

- Framing by the moderator directly (no subagents) still asks the user questions before deliberating, with the same rounds and re-framing. Found in a ChatGPT run, where the moderator resolved what "release" meant from its own research instead of asking.
- Output format: every heading of the result format is required, in order; anything the moderator adds (an action plan, extra tables) goes after it under its own heading.
- Unanimity check: both points (shared premise, missing alternative) are recorded every time, "none found" when empty, including for unanimous follow-up proposals.
- Releases now also include `magi-chat-<version>.zip`, the skill without `scripts/`, for the Gemini app, which refuses skills that contain executable files.
- The result JSON format is unchanged (version 2).

## [1.3.1]

- No changes to the skill.
- Releases now also include `magi-plugin-<version>.zip` for uploading MAGI as a plugin in ChatGPT or Codex: `.codex-plugin/plugin.json` and `skills/magi/` at the archive root, with readable file permissions. The existing `magi-<version>.zip` (skill folder at the root) stays for the Claude app.

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
