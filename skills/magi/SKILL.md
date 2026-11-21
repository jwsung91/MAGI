---
name: "magi"
description: "Three-perspective MAGI deliberation: technical, risk and human views judge independently; 2/3 majority, or unanimity if critical. Use for /magi, 'decide with MAGI', 'MAGI로 판단해줘', go/no-go calls."
---

# MAGI — Three-Perspective Majority Deliberation

Three different perspectives evaluate one proposal **independently**, and the result is resolved by a voting rule. The purpose is to keep a judgment from leaning on a single viewpoint and to keep dissent on the record instead of erasing it. The final decision always belongs to the user; the MAGI resolution is presented as input to that decision.

Inspired by the MAGI system in *Neon Genesis Evangelion*. This is an unofficial skill, not affiliated with the series or its rights holders.

## Roles

| Role | Who | Responsibility |
|---|---|---|
| Moderator | The agent in the main conversation | Gathers material, runs each agent, tallies the vote, reports |
| Framing agent | Separate subagent | Decides the proposal wording, premises, grade, and preset |
| MELCHIOR-1 · BALTHASAR-2 · CASPER-3 | Three separate subagents | Independent review |

This skill follows the open Agent Skills format and runs in any agent that loads it (Claude Code, the Claude app, Codex, Gemini CLI, and others). Use whatever the host offers for each step: its way of launching subagents, asking the user questions, drawing inline visuals, and running shell commands. Where a capability is missing, follow the fallback given for that step.

Why framing is separated from the moderator: how the proposal is worded and which premises go into it affect the outcome more than anything else. If the party that summarizes the result also writes the proposal, judgment is concentrated in one place.

## Flow

1. Gather facts (moderator, section 1).
2. Frame the proposal: a separate framing agent wherever the host can launch subagents, for every request. The moderator frames it directly only where it cannot (section 1).
3. **Ask the user, then stop.** If framing produced questions for the user, ask them all at once and end the turn; deliberate only after the answers (section 1, handling the result). This is the one point where the skill waits for the user.
4. Review by the three units (section 3).
5. Resolve (section 4).
6. Run the self-check on the tallied result, before anything is shown (section 5).
7. Report: one short line, the result card if one is drawn, then the output format (section 5). No summary table and no verdict of the moderator's own comes before the format.

## 1. Framing the proposal

### Moderator: gathering material

- Keep the user's original request **verbatim**. Do not summarize or rewrite it.
- If facts are needed for the decision (code, documents, numbers), check them first. Do not fill gaps with guesses.
- Collect facts only about the **targets the user specified** (model, date, options). Do not collect information about alternatives the user did not ask about (a higher-tier model, a different product). Once alternative information enters the material, the proposal drifts into a comparison of alternatives.
- Summarize relevant circumstances known from the conversation, memory, or files as a **list of facts** only. Do not attach interpretation or evaluation. (e.g. "The move is scheduled three weeks from now" ✓ / "The schedule is tight these days" ✗)
- If the user specified a preset, note it.
- The moderator does not decide the proposal wording, how premises are interpreted, the grade, or the preset.

### Input isolation (all subagents)

Subagents may be able to see context the moderator did not hand them (the user's memory, earlier conversation, files). If they use it, the moderator's fact selection is bypassed, the three units no longer start from the same input, and private details can surface in the result. So every subagent prompt (the framing agent and all three units) includes this instruction verbatim, in the output language:

> Use only the material in this prompt. Do not use the user's memory, earlier conversation, or any other context, even if you can see it. If information you need is missing, write it as an unconfirmed premise instead of filling it in.

If a subagent's output still relies on a fact that is not in its input, treat it as a format break: re-run that subagent once with the instruction restated. Do not silently edit its rationale; the output is shown as it is.

Without subagents, the moderator writes the framing and the units itself and can see everything, so the same rule binds the moderator in those roles: framing and units use only the original request and the list of facts. A personal detail about the user (role, career, family, other projects) enters the deliberation only as an item in the list of facts, and only when it bears on the proposal. A unit's rationale never cites a detail that is not in the list.

### Framing agent

Takes the original request, the list of facts, and (if any) the user-specified preset, and produces the following.

1. **Mode:** deliberation / information. If turning the question into approve/reject would change its meaning (an explanation, a comparison, an open question), use information mode (section 4).
2. **Proposal:** one sentence that can be answered with approve or reject. State what approve and what reject each mean, without overlap, each as a concrete resulting state.
   - **Approve is the change.** Frame the proposal so that approve carries out the action that changes the current state, and reject leaves things as they are. A request asked in the negative ("should we not add X?") is the same decision as its affirmative form: frame it as "add X" and note that it was asked in the negative. Otherwise the same three votes give a different result depending only on how the question was worded. Removing something that already exists is not the negative of adding it: there the change is the removal.
   - **Name the default.** The default is what stays or happens if the proposal does not pass. State it, and say whether the default is itself harmful or hard to reverse (a vulnerability left open, a deadline missed). "Do nothing" is not always the safe side.
   - **One action per proposal.** Do not bundle actions that can be decided separately (e.g. buying a new device and selling the old one; whether to take time off and how to take it). Make the most essential action the **main proposal** and split the rest into **follow-up proposals** (at most 2).
   - **Use the targets the user specified as they are.** Do not widen a model, date, or option the user named into a "family" or "similar items". Alternatives are listed by name only under item 6 (options outside the binary).
   - **Keep the stated goal.** If the request says what the action is for ("to make our pages faster"), the proposal sentence keeps that goal. If it states none, the goal is a premise: an [assumption], or a question for the user under item 7 if only the user can answer it and it could decide the outcome.
3. **Grade:** normal / critical, with a one-line reason (section 2). Grade each follow-up proposal separately; it need not match the main proposal's grade.
4. **Premises:** split into confirmed facts / assumptions / unconfirmed. Assumptions are what the framing agent filled in, and must be marked as assumptions. Write important variables that were not given as unconfirmed. Variables that could decide the outcome and that only the user can answer must not be filled in as [assumption]; send them to item 7, questions for the user.
5. **Preset:** the chosen preset, a one-line reason, and one runner-up. If the user specified one, follow it. If no preset fits, design three new perspectives (section 3), each a question whose yes means approve, with one line on which kind of fact each unit takes.
6. **Options outside the binary:** options that were dropped by turning the proposal into approve/reject (a reduced version, phased adoption, a different method, a change of timing).
7. **Questions for the user:** from the unconfirmed variables, those that **could decide the outcome and only the user can answer**, as at most 3 questions. Attach one line to each question on how its answer could change the outcome. Do not ask the user about things that can be checked from sources (prices, specs); ask the moderator to check them instead. If there are none, write "none".

### Moderator: handling the result

- If there are questions for the user, ask them **all at once** (with a question tool if available) and end the turn there. Do not deliberate in the same turn, and do not answer the questions yourself. This holds in every host, including hosts that usually proceed on reasonable assumptions. Add the answers to the list of facts and run the framing agent again.
- **What the request means is the user's to answer.** If the request can be read in more than one way and the readings lead to different proposals (for example, "release" as declaring a stable 1.0 or as opening the current version to users), that is a question for the user, not an assumption. Facts the moderator found while gathering material do not settle it.
- **Every round of answers is followed by re-framing.** Do not append answers to the previous framing result and pass it to the units directly; the units always receive a framing result produced after the latest answers.
- If the re-framed result has new questions for the user, ask them again in the same way. A precise result is worth another round. Stop after 3 rounds of questions; anything still open after that stays as [assumption] and is stated in the result.
- If the user does not answer or says "just go ahead", leave those variables as [assumption] and proceed, stating so in the result.
- **If deliberation happens without the user having been asked** (an unattended run, or a host that does not hand the turn back), do not settle an ambiguity silently. Make the reading closest to the user's words the main proposal and each other reading a follow-up proposal, deliberate each, and list the questions that were not asked under **Additional information**, each with how its answer would change the outcome, so the user can answer and run MAGI again. This is a fallback, not an alternative: wherever the turn can end, end it.
- If the framing agent asks for something to be checked from sources, the moderator checks it and adds it to the list of facts.
- The moderator **does not rewrite** the framing result. If a part clearly contradicts what the user said, point out only that contradiction and run the framing agent once more.
- Where subagents can be launched, the framing agent frames every request. A short request, or one whose wording already looks clear, is not a reason to skip it: the wording that looks clear is the moderator's own reading, which is the judgment the separate agent is there to take over.
- If subagents are not available, the moderator frames the proposal directly and states "Framing: moderator directly" in the output. Write "framing agent" only when a separate agent actually produced the framing. Framing directly still produces all seven items above, questions for the user included, and every rule in this list applies unchanged.

## 2. Grade

| Grade | Criteria | Resolution rule |
|---|---|---|
| Normal | Reversible and limited in impact | 2/3 majority |
| Critical | Hard to reverse, or affects safety, security, data loss, production environments, or large costs | Passes only if all 3 approve; otherwise rejected |

The framing agent decides the grade and gives a one-line reason. When in doubt, treat it as critical. Either side can make a proposal critical: the action, or the default if the proposal does not pass.

The grade follows what the facts say about how reversible the action is and how large its impact is:
- A change the facts say can be undone (a pull request that reverts cleanly, a setting that can be switched off) is not critical only because it reaches production.
- The default makes a proposal critical only when its harm is itself hard to reverse or severe (data lost, a vulnerability left open, a deadline missed for good). An ongoing cost, or a risk that can still be dealt with later, does not.
- "When in doubt" is doubt about what the facts say. A term the facts do not state (a contract length, a billing period) is an [assumption] under premises; grade on the stated facts.

None of this lowers a proposal that really is hard to reverse or large in impact.

A thought experiment or discussion question, where nothing will actually be carried out, is **normal** even if its subject is life or safety. The critical grade exists to stop irreversible actions; applied to a question with no action, it mostly turns splits into rejections without protecting anyone.

## 3. Independent review by the three units

Independence is the core.
- If subagents can be launched, run the three units as **separate agents** that cannot see each other's results.
- If not, write one unit at a time, without referring to or aligning with earlier units' conclusions, and say on the result's **Limitations** line (section 5) that one agent wrote all three units in turn. Do not call such units independent agents.
- Pass the framing result (proposal, default, premises, preset perspectives, options outside the binary) to the three units unchanged. If there are follow-up proposals, each unit gives a separate verdict on the main proposal and on each follow-up.
- Each unit prompt includes the input isolation instruction (section 1).

| Unit | Perspective | Main questions |
|---|---|---|
| **MELCHIOR-1** (scientist) | Technical feasibility | Is the evidence right? Does it work, and does it reach the stated goal? Complexity, performance, correctness? Is there a technically simpler way to the same goal? |
| **BALTHASAR-2** (guardian) | Risk and cost | What is lost if it fails or sits unused? Can it be reversed? What does it cost to carry: money, time, upkeep, opportunity? What does the default cost, and what does the change save? |
| **CASPER-3** (human) | Needs and value | Do the people affected by the result (the user, stakeholders, the people who will live with it) want it? What do motivation and intuition say? |

The three questions are kept apart, one kind of fact to each: whether the means reaches the stated goal, and whether a simpler way reaches it, is MELCHIOR-1's; money, time, risk, reversibility, savings and the cost of the default are BALTHASAR-2's; whether the people affected want the result is CASPER-3's.

### Presets

The table above is the **default** preset. Keep the unit names and change only the perspectives depending on the kind of proposal. If the perspectives do not fit the proposal, the three units lean the same way or an important position is missing entirely.

| Preset | MELCHIOR-1 | BALTHASAR-2 | CASPER-3 |
|---|---|---|---|
| Default (engineering, product) | Technical feasibility | Risk and cost | Needs and value |
| Ethics | Consequentialism: does the sum of outcomes improve? | Deontology: can it be done without violating a right or a duty, whatever the outcome? | Virtue ethics and relationships: does this choice make you the kind of person you would want to be, and is it good for the relationships and emotions involved? |
| Code review | Correctness: does it do what it claims on the intended path? | Off the intended path: is it sound for security, on failure, and for existing callers? | The colleague who will read and change it: is it readable, well designed and maintainable? |
| Personal decision (career, family, organization) | Real gain and feasibility: does it actually get you something (growth, standing, use), and can you do it with the ability and means you have now? | Risk, cost and relationships: are what you could lose, what it costs to carry, the stability of your life, and what it does to the people affected with you (family, team) acceptable? | Motivation and satisfaction: do you really want it? |
| Original | Scientist: does it advance understanding or technology? | Mother: does it protect people and their well-being? | Woman: does it answer love, dreams or desire? |

Each perspective is a question whose yes means approve. One kind of fact to each unit:
- Ethics: outcomes for those affected → MELCHIOR-1; rights, duties, promises, consent → BALTHASAR-2; character, motives, relationships and emotions → CASPER-3.
- Code review: behaviour and tests on the intended path → MELCHIOR-1; security, failure, existing callers → BALTHASAR-2; readability, structure, how the people who maintain it find it → CASPER-3.
- Personal decision: what it gets you and whether you can do it → MELCHIOR-1; money, time, risk, reversibility, and the people affected with you → BALTHASAR-2; whether you want it → CASPER-3.
- Original: knowledge and technology → MELCHIOR-1; safety and well-being → BALTHASAR-2; love, dreams and desire → CASPER-3.

The original preset is inspired by the three aspects given to the MAGI in *Neon Genesis Evangelion*. Its perspectives run along the same lines as the default preset, so use it only when the user specifies it; the framing agent does not choose it or name it as runner-up.

The framing agent chooses the preset (section 1). If the user specifies one, follow it. If no preset fits, the framing agent designs three new perspectives for the proposal, chosen so that they can conflict with each other and do not judge the same question. Each is written as a question whose yes means approve, with one line on which kind of fact each unit takes.

In every preset, custom perspectives included, a unit builds its verdict on its own perspective's question. A point that belongs to another unit's question goes under recommendations, not in the key rationale. Otherwise two units vote on the same argument and the majority is narrower than it looks.

**What approve means.** A unit approves when the answer to its own question is yes. Weighing every gain against every cost is the tally's job, not one unit's. In the default preset:
- MELCHIOR-1 approves if the means reaches the stated goal.
- BALTHASAR-2 approves if, compared with the default, the cost and the loss if it fails are acceptable.
- CASPER-3 approves if the stakeholders want the result.

In other presets, each unit approves when its own perspective's question is answered yes.

The options outside the binary are a reason for a verdict only for the unit whose question asks for a simpler way to the same goal (MELCHIOR-1 in the default preset). For the other units a better option is a recommendation, not a reason to reject.

Each unit produces:
- **Verdict:** approve / reject. There is no conditional verdict: the vote must commit. If the verdict depends on a condition, handle the condition before voting:
  - a fact that can be checked from sources → report it as a needed check; the moderator checks it and re-runs that unit once with the result;
  - a fact only the user can answer → vote on the proposal as framed and write the condition under the doubted premise;
  - a modified version of the proposal (e.g. "only if done at off-peak hours"), or a proposal with a different goal → vote on the proposal as framed, and suggest the other version only as a candidate for a separate decision. It is not deliberated or voted on in this run: changing the proposal or its goal is the user's decision;
  - advice for carrying it out → put it under recommendations; it does not change the vote.
- **Confidence:** high / medium / low
- **Key rationale:** at most 3 points
- **What would flip the verdict:** what would have to change for the unit to vote the other way
- **Recommendations:** (optional, non-binding) advice for carrying out the proposal, or a modified version worth deciding separately. Recommendations are not counted in the vote.
- **Doubted premise:** the one premise the unit finds most doubtful from its perspective, and how its verdict would change if that premise were wrong
- **Grade objection:** (only if any) on a normal proposal, and only by naming a fact in the list of facts that meets one of the critical criteria of section 2: hard to reverse, safety, security, data loss, or large cost (e.g. "fact 3: any logged-in user can overwrite server files; security"). A strong objection to the proposal is not a grade objection; it is a reject vote.

Premise doubts are split by perspective. If all three units accept the same premises unchanged, a common-mode failure arises at the input stage.
- MELCHIOR-1: technical premises (performance, how things work, accuracy of data)
- BALTHASAR-2: risk and cost premises (what is the safe state, the blast radius of failure, what it really costs to carry)
- CASPER-3: requirement premises (is this a problem worth solving, who wants it)

With other presets, adapt the premise-doubt areas to each unit's perspective.

## 4. Resolution

Decide in this order.

1. **Error:** if a unit failed, gave no answer, or broke the format, re-run only that unit once. If it fails again, the resolution is **error**. Do not vote with the remaining two units only. Expose the failure instead of hiding it.
2. **Information mode:** if the proposal is a question that cannot be answered with approve/reject, do not vote. Present each unit's answer, what they share, and where they diverge.
3. **Grade objection:** if a unit raised a grade objection on a normal proposal, check that the fact it names is in the list of facts and meets a critical criterion of section 2. If so, raise the proposal to critical and resolve accordingly (the "when in doubt, critical" principle); the resolution line says the grade was raised by that unit's objection. If not, do not accept the objection: keep the grade and say on the Grade line which objection was not accepted and why.
4. **Vote:** count approvals. Follow-up proposals are resolved separately by the same rules.
   - Normal proposal: 2 or more approvals → **passed**; otherwise **rejected**.
   - Critical proposal: all 3 approve → **passed**; otherwise **rejected**. There is no debate round and no on hold: the units answer different questions, so a second round gives a unit no reason of its own to move.
5. **Resolution line:** a resolution that is not unanimous names, whether passed or rejected and whatever the grade, the unit or units that voted against the proposal and the reason in one phrase, e.g. "rejected (approve 2/3; a critical proposal needs all three. Against: BALTHASAR-2, the logs are the only record)". If a grade objection made the proposal critical, the line says so.
   - If a proposal is rejected and its default is itself harmful or costly, say with the resolution that not passing it is also a choice, and by when it has to be made if that is known.
- **Unanimity check:** if all three units reached the same conclusion (all approve or all reject), suspect that they share the same blind spot because they come from the same model, check the following two points, and record the result. Record both points every time, writing "none found" for a point with nothing to report; this applies to follow-up proposals that were unanimous as well.
  1. **Shared premise:** do all three units' judgments rest on the same premise? Especially if it is an assumption filled in by the framing agent, state whether the resolution would flip if that premise were wrong.
  2. **Missing alternative:** by treating the proposal only as "do it or not", did the units miss options in between (a reduced version, phased adoption, a different method)? Compare with the framing agent's "options outside the binary", and reflect anything the units did not address in the next actions.

## 5. Output format

Use the format below as it is, with the headings in this order and none merged. A heading marked "(if any)" or "(if applicable)" is left out when it does not apply; every other heading is required. Anything beyond it (an action plan, extra tables, research notes) goes after the format, under its own heading, so the user can tell the deliberation result from the moderator's additions.

```
## MAGI Deliberation Result

**Proposal:** ... (main proposal; what approve and reject each mean; if the request was asked in the negative, say so)
**Default if not passed:** ... (what stays or happens; mark it if the default is itself harmful or hard to reverse)
**Follow-up proposals:** (if any)
**Grade:** normal / critical — (one-line reason; mark if raised by a grade objection; name an objection that was not accepted and why)
**Additional information:** (answers received from the user before deliberation; items left as assumptions without an answer; questions that were not asked, each with how its answer would change the outcome)
**Preset:** default / ethics / code review / personal decision / original / custom — (one-line reason, runner-up)
**Premises:** confirmed facts / assumptions / unconfirmed (mark assumptions)
**Options outside the binary:** (from the framing)
**Framing:** framing agent / moderator directly

| Unit | Verdict | Confidence | Key rationale | Doubted premise |
|---|---|---|---|---|
| MELCHIOR-1 | Approve | High | ... | ... |
| BALTHASAR-2 | Reject | Medium | ... | ... |
| CASPER-3 | Approve | Medium | ... | ... |

**Resolution:** passed / rejected / error (approve n/3; if not unanimous, the units that voted against and their reason; if a grade objection made it critical, say so) — the outcome in plain words (what is done or not done), answering the question as the user asked it; if rejected with a harmful or costly default, that not passing is also a choice
(only if not unanimous; "the other way" is against a passed proposal, for a rejected one, e.g. the two approving units of a critical proposal rejected at 2/3) This resolution counts the answers of three aspects; it is not a judgment that the proposal is best overall. Weigh for yourself the aspect that voted the other way from the resolution.
**Follow-up resolutions:** (if any) for each follow-up proposal, its resolution line and a per-unit table, so the user can see why each unit voted as it did:

**Follow-up 1:** (follow-up text) — normal / critical — passed / rejected (approve n/3; if not unanimous, the units that voted against and their reason)
(only if not unanimous) the same notice line as under the resolution

| Unit | Verdict | Confidence | Key rationale |
|---|---|---|---|
| MELCHIOR-1 | Approve | ... | ... (1-2 points) |
| BALTHASAR-2 | Reject | ... | ... |
| CASPER-3 | Approve | ... | ... |

**Recommendations:** (if any, per unit; non-binding. If units recommend modified versions of the proposal or a different goal, list them as candidates for a separate decision without merging, deliberating or voting on them)

**Unanimity check:** (if applicable) shared premise, missing alternative

**Minority opinion:** keep the dissenting unit's argument without shortening it.

**What would flip the resolution:** ...
**Next actions:** ...
**Limitations:** how the units were run (separate agents of one model / one agent writing each unit in turn); for an important proposal, also a recommendation to get a review from other sources, other people, or another model.
```

In information mode, use this format instead of a resolution.

```
## MAGI Information

**Question:** ...
**Preset:** ...

| Unit | Answer |
|---|---|
| MELCHIOR-1 | ... |
| BALTHASAR-2 | ... |
| CASPER-3 | ... |

**Common ground:** ...
**Where they diverge:** ...
```

### Result card (optional)

If a tool that renders interactive visuals inline in the conversation is available, draw a result card first, before the Markdown result, following `references/card.md` in this skill's folder. Finish the tally before drawing, so the card and the Markdown come from the same result; the card may be preceded only by one short line saying that the result follows. If the copy of `references/card.md` at hand still says to draw the card after the Markdown result, this section takes precedence. In short: the proposal and resolution at the top, the three units side by side with their verdicts, one unit's rationale shown when it is clicked, and the minority opinion at the bottom, in a neutral design that follows the host's theme. Unit tiles are filled with their verdict color (approve blue, reject red); the resolution badge is passed green, rejected red; confidence appears only as text in the details. Follow-up proposals get their own rows below the main units: the follow-up text, its resolution badge, and three small unit chips filled with each unit's verdict color; clicking a chip shows that unit's rationale for that follow-up in the same details area. If `references/card.md` is not available, follow this summary.

Implementation rules (hosts pre-style form controls, which can silently erase colors):
- Build clickable tiles and chips as `<div role="button" tabindex="0">`, not `<button>`; handle Enter/Space as well as click.
- Put fill, text, and border colors in inline `style`, each with a fallback: `background: var(--bg-danger, #FCEBEB); color: var(--text-danger, #A32D2D)` for reject, `var(--bg-accent, #E6F1FB)` / `var(--text-accent, #185FA5)` for approve, `var(--bg-success, #EAF3DE)` / `var(--text-success, #3B6D11)` for passed.
- Show selection by changing the tile's own border color (keep a 2px transparent border at rest so the layout does not shift), not with `outline`.

Without such a tool, skip the card: do not print its HTML or create a file for it. Also skip it when the user asks for no card. The Markdown result is always complete on its own.

### Self-check (before reporting)

Check the result once it is tallied and before any of it is shown, so the card, the Markdown and the JSON all come from the checked result. It matters most when one agent wrote everything, because nothing else checked the units. Repair a failed check by the rule that covers it: a unit that ran as a subagent is re-run, never edited (sections 1 and 4); what the moderator wrote itself, it rewrites.
- **Questions:** the user was asked and answered, or framing found no question, or the user said to go ahead. Otherwise the questions that were not asked are listed under Additional information and each reading has its own proposal.
- **Framing line:** says "framing agent" only if a separate agent framed the proposal. If the moderator framed it although subagents can be launched here, the framing was skipped: run the framing agent now and repeat the review from its result.
- **Direction:** approve is the change from the current state and the default is stated; for a request asked in the negative, the resolution says what it means for the question as asked.
- **Facts:** every fact a unit cites is in the list of facts; no personal detail about the user appears that is not in the list.
- **Cells:** every verdict is approve, reject, or error, and every confidence is high, medium, or low (in the output language). No placeholder from the format is left as written ("...", "Follow-up 1" with no text after it).
- **Resolution line:** a resolution that is not unanimous names the units that voted against the proposal and their reason, whether it passed or was rejected.
- **Notice line:** every resolution line that is not unanimous (main and follow-up) is followed directly by the notice line of the format, in the output language, and it points to the units that voted the other way from the resolution (against if passed, for if rejected); a unanimous one is not.
- **Proposals:** only the main and follow-up proposals from the framing were deliberated; no alternative proposal was made up and voted on.
- **Unanimity check (if any proposal was unanimous):** both points are recorded.
- **Limitations line:** says how the units were actually run.
- **Language:** headings, labels, and verdict words are in the output language; only the unit names stay in English.

### Before finishing

Check each output in this order before ending the reply:
1. The result card, if a tool that renders inline visuals is available.
2. The Markdown result, complete even when a card was drawn.
3. The JSON result and the `final` progress event, if `MAGI_RESULTS_DIR` is set (sections 6 and 7).

## Output language

These instructions are in English, but the result is written in the language of the user's request: a request in Korean gets a Korean result. If the user asks for a specific language, use that language instead. Translate the headings, labels, and verdict words of the formats above as well; keep only the unit names (MELCHIOR-1, BALTHASAR-2, CASPER-3) as they are. Subagents receive the same language instruction, so each unit writes in that language too.

## 6. JSON output (optional, for viewers)

Write a JSON copy of the result only in these cases:
- where the agent can run shell commands and write files (Claude Code, Codex, Gemini CLI, and the like), when the environment variable `MAGI_RESULTS_DIR` is set (check with `echo "$MAGI_RESULTS_DIR"` at the start of the run);
- when the user asks for JSON.

Otherwise skip this section entirely.

Rules:
- Build the result once, then derive both the Markdown and the JSON from it, so the two never disagree.
- Enum values are always the English values below, whatever the output language. Free text (agenda, rationale, perspective, and so on) is written in the output language.
- When `MAGI_RESULTS_DIR` is set, save to `$MAGI_RESULTS_DIR/YYYYMMDD-HHMMSS-<short-slug>.json` (create the folder if needed), show the Markdown result as usual, and add one line with the file path. Where files cannot be written, output the JSON as a code block only when the user asked for it.
- In information mode nothing is voted on: leave out `grade`, `grade_raised`, `verdict` and `approve_count`, even if the framing named a grade.
- The full schema is `result.schema.json` next to this file. The fields:

```
version: 2
mode: "deliberation" | "information"
agenda: main proposal (or the question)
grade: "normal" | "critical"            (deliberation)
grade_raised: true if raised by a grade objection
preset, framing, minority: text (optional)
verdict: "passed" | "rejected" | "error"   (deliberation; the schema keeps "on_hold" and `debate` for results of earlier versions, and this version writes neither)
approve_count: 0-3
follow_ups: [{agenda, grade, verdict, approve_count, units}]  (at most 2)
  units: {melchior, balthasar, casper}, each: verdict, confidence, rationale (at most 3)
units: {melchior, balthasar, casper}, each:
  perspective: text
  verdict: "approve" | "reject" | "error"   (main proposal)
  confidence: "high" | "medium" | "low"
  rationale: [text] (at most 3)
  flip_condition, doubted_premise: text
  recommendations: [text]
  answer: text                              (information mode)
  error: text                               (when verdict is "error")
```

## 7. Progress log (optional, JSON Lines)

Where the agent can run shell commands and `MAGI_RESULTS_DIR` is set, also record the run as it happens, one JSON line per event, in `$MAGI_RESULTS_DIR/<run_id>.jsonl`. `<run_id>` is the same `YYYYMMDD-HHMMSS-<short-slug>` used for the JSON result. Anyone can follow it live (`tail -f`) or review it afterwards.

- Only the moderator writes. Units keep returning text.
- Write with the helper in this skill's folder, passing the event on stdin through a quoted heredoc, so no shell escaping is needed:

  ```bash
  python3 <skill_dir>/scripts/log_event.py "$MAGI_RESULTS_DIR/<run_id>.jsonl" <<'EOF'
  {"run_id": "<run_id>", "event": "framing_done", "data": {...}}
  EOF
  ```

  The helper adds `v`, `seq` and `ts` and appends one line.
- Events, at these moments (combine events from the same moment into one call by running the helper once per event inside one shell command):

  | event | when | data |
  |---|---|---|
  | `run_started` | start | `request` (verbatim), `lang` |
  | `facts_gathered` | after gathering facts | `facts` |
  | `framing_done` | after framing (again after re-framing) | `mode`, `agenda`, `follow_ups`, `grade`, `preset`, `questions` |
  | `questions_answered` | after the user answers | `answers` |
  | `units_started` | before running the units | `round` (always 1) |
  | `units_done` | when the units' results arrive (all three at once) | `round`, and per unit `verdict` and `confidence` |
  | `final` | at the end | `result`: the full version 2 result object |
  | `error` | on failure | `stage`, `message` |

- Logging is best-effort. If the helper is missing (for example, in an account skill without the scripts folder) or a write fails, do not retry and do not stop: continue the deliberation and mention the skipped logging in one line at the end.

## On limitations

If the three units come from the same model, this is not true design diversity. Just as the original MAGI came from one person's personality, common-mode failure remains. The **Limitations** line of the result says how the units were run, and for important proposals recommends a review from other sources, other people, or another model as well.

Separating the framing agent does not change the fact that it is the same model. The point of judgment moves from the moderator to an independent agent; it does not disappear. The framing result is shown in the output as is so that the user can review this point directly.
