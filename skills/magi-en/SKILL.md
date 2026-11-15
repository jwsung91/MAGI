---
name: "magi"
description: "MAGI-style decision deliberation: three perspectives (technical, safety, human) judge independently, resolved by 2/3 majority, or unanimity for critical items. Use for /magi, 'decide with MAGI', go/no-go calls, and design reviews."
---

# MAGI — Three-Perspective Majority Deliberation

Three different perspectives evaluate one proposal **independently**, and the result is resolved by a voting rule. The purpose is to keep a judgment from leaning on a single viewpoint and to keep dissent on the record instead of erasing it. The final decision always belongs to the user; the MAGI resolution is presented as input to that decision.

## Roles

| Role | Who | Responsibility |
|---|---|---|
| Moderator | Claude in the main conversation | Gathers material, runs each agent, tallies the vote, reports |
| Framing agent | Separate subagent | Decides the proposal wording, premises, grade, and preset |
| MELCHIOR-1 · BALTHASAR-2 · CASPER-3 | Three separate subagents | Independent review |

Why framing is separated from the moderator: how the proposal is worded and which premises go into it affect the outcome more than anything else. If the party that summarizes the result also writes the proposal, judgment is concentrated in one place.

## 1. Framing the proposal

### Moderator: gathering material

- Keep the user's original request **verbatim**. Do not summarize or rewrite it.
- If facts are needed for the decision (code, documents, numbers), check them first. Do not fill gaps with guesses.
- Collect facts only about the **targets the user specified** (model, date, options). Do not collect information about alternatives the user did not ask about (a higher-tier model, a different product). Once alternative information enters the material, the proposal drifts into a comparison of alternatives.
- Summarize relevant circumstances known from the conversation, memory, or files as a **list of facts** only. Do not attach interpretation or evaluation. (e.g. "The move is scheduled three weeks from now" ✓ / "The schedule is tight these days" ✗)
- If the user specified a preset, note it.
- The moderator does not decide the proposal wording, how premises are interpreted, the grade, or the preset.

### Framing agent

Takes the original request, the list of facts, and (if any) the user-specified preset, and produces the following.

1. **Mode:** deliberation / information. If turning the question into approve/reject would change its meaning (an explanation, a comparison, an open question), use information mode (section 4).
2. **Proposal:** one sentence that can be answered with approve or reject. State what approve and what reject each mean, without overlap.
   - **One action per proposal.** Do not bundle actions that can be decided separately (e.g. buying a new device and selling the old one; whether to take time off and how to take it). Make the most essential action the **main proposal** and split the rest into **follow-up proposals** (at most 2).
   - **Use the targets the user specified as they are.** Do not widen a model, date, or option the user named into a "family" or "similar items". Alternatives are listed by name only under item 6 (options outside the binary).
3. **Grade:** normal / critical, with a one-line reason (section 2).
4. **Premises:** split into confirmed facts / assumptions / unconfirmed. Assumptions are what the framing agent filled in, and must be marked as assumptions. Write important variables that were not given as unconfirmed. Variables that could decide the outcome and that only the user can answer must not be filled in as [assumption]; send them to item 7, questions for the user.
5. **Preset:** the chosen preset, a one-line reason, and one runner-up. If the user specified one, follow it. If no preset fits, design three new perspectives (section 3).
6. **Options outside the binary:** options that were dropped by turning the proposal into approve/reject (a reduced version, phased adoption, a different method, a change of timing).
7. **Questions for the user:** from the unconfirmed variables, those that **could decide the outcome and only the user can answer**, as at most 3 questions. Attach one line to each question on how its answer could change the outcome. Do not ask the user about things that can be checked from sources (prices, specs); ask the moderator to check them instead. If there are none, write "none".

### Moderator: handling the result

- If there are questions for the user, ask them **all at once** before deliberation (with a question tool if available). Add the answers to the list of facts and run the framing agent again. Do not proceed on assumptions while things remain ambiguous.
- If the user does not answer or says "just go ahead", leave those variables as [assumption] and proceed, stating so in the result.
- If the framing agent asks for something to be checked from sources, the moderator checks it and adds it to the list of facts.
- The moderator **does not rewrite** the framing result. If a part clearly contradicts what the user said, point out only that contradiction and run the framing agent once more.
- If subagents are not available, the moderator frames the proposal directly and states "Framing: moderator directly" in the output.

## 2. Grade

| Grade | Criteria | Resolution rule |
|---|---|---|
| Normal | Reversible and limited in impact | 2/3 majority |
| Critical | Hard to reverse, or affects safety, security, data loss, production environments, or large costs | Passes if unanimous (rejected if all reject; on a split, one debate round then a revote; still split → on hold) |

The framing agent decides the grade and gives a one-line reason. When in doubt, treat it as critical.

## 3. Independent review by the three units

Independence is the core.
- If subagents can be launched, run the three units as **separate agents** that cannot see each other's results.
- If not, write one unit at a time, without referring to or aligning with earlier units' conclusions.
- Pass the framing result (proposal, premises, preset perspectives, options outside the binary) to the three units unchanged. If there are follow-up proposals, each unit gives a separate verdict on the main proposal and on each follow-up.

| Unit | Perspective | Main questions |
|---|---|---|
| **MELCHIOR-1** (scientist) | Technical feasibility | Is the evidence right? Does it work? Complexity, performance, correctness? Is there a simpler alternative? |
| **BALTHASAR-2** (guardian) | Safety and sustainability | What breaks if it fails? Can it be reversed? Operations and maintenance burden? Who gets hurt? |
| **CASPER-3** (human) | Needs and value | Is this what the user and stakeholders really want? What do motivation and intuition say? Is it worth the effort? |

### Presets

The table above is the **default** preset. Keep the unit names and change only the perspectives depending on the kind of proposal. If the perspectives do not fit the proposal, the three units lean the same way or an important position is missing entirely.

| Preset | MELCHIOR-1 | BALTHASAR-2 | CASPER-3 |
|---|---|---|---|
| Default (engineering, product) | Technical feasibility | Safety and sustainability | Needs and value |
| Ethics | Consequentialism: does the sum of outcomes improve? | Deontology: rights and duties; is this something that must not be done regardless of outcome? | Virtue ethics and relationships: what kind of person does this choice make you; relationships and emotions |
| Code review | Correctness and design | Security, failure, compatibility | The colleague who will read and change it: readability, maintainability |
| Personal decision (career, etc.) | Growth and capability | Risk and stability of life | Motivation and satisfaction |
| Original | Scientist: understanding and technological progress | Mother: protection and well-being | Woman: love, dreams, desire |

The framing agent chooses the preset (section 1). If the user specifies one, follow it. If no preset fits, the framing agent designs three new perspectives for the proposal, chosen so that they can conflict with each other.

Each unit produces:
- **Verdict:** approve / conditional approve / reject (for conditional approve, state the conditions concretely in a checkable form)
- **Confidence:** high / medium / low
- **Key rationale:** at most 3 points
- **What would flip the verdict:** what would have to change for the unit to vote the other way
- **Doubted premise:** the one premise the unit finds most doubtful from its perspective, and how its verdict would change if that premise were wrong
- **Grade objection:** (only if any) if the unit thinks the grade is wrong, give the reason (e.g. "the judgment that this is reversible is wrong")

Premise doubts are split by perspective. If all three units accept the same premises unchanged, a common-mode failure arises at the input stage.
- MELCHIOR-1: technical premises (performance, how things work, accuracy of data)
- BALTHASAR-2: safety and operational premises (what is the safe state, the blast radius of failure)
- CASPER-3: requirement premises (is this a problem worth solving, who wants it)

With other presets, adapt the premise-doubt areas to each unit's perspective.

## 4. Resolution

Decide in this order.

1. **Error:** if a unit failed, gave no answer, or broke the format, re-run only that unit once. If it fails again, the resolution is **error**. Do not vote with the remaining two units only. Expose the failure instead of hiding it.
2. **Information mode:** if the proposal is a question that cannot be answered with approve/reject, do not vote. Present each unit's answer, what they share, and where they diverge.
3. **Grade objection:** if even one unit raised a grade objection on a normal proposal, raise it to critical and resolve accordingly (the "when in doubt, critical" principle).
4. **Vote:** a conditional approve counts as approve. However, if a passed proposal has at least one conditional approve, the resolution is **conditionally passed**, and all conditions are combined. Follow-up proposals are resolved separately by the same rules.
   - Normal proposal: 2 or more approvals → **passed**; otherwise **rejected**.
   - Critical proposal: all 3 approve → **passed**; all 3 reject → **rejected**; a split opens a debate round.
   - **Conflicting conditions:** if the units' conditions do not fit together (e.g. one unit specifies an option and another says to choose based on usage), the moderator does not merge them. Show the conflict as is and let the user choose.
5. **Debate round (only when a critical proposal is split):** show each unit the other two units' verdicts and rationale, and let it give a verdict once more. Debate is limited to 1 round.
   - To change position, a unit must cite a **new argument** raised by another unit. "Because the majority saw it that way" is not an argument. This prevents conformity pressure from breaking independence.
   - A unit that changed position states what made it change.
   - If the revote is still split, the result is **on hold** (until the rejecting unit's concerns are resolved).
- **Unanimity check:** if all three units reached the same conclusion (all approve or all reject), suspect that they share the same blind spot because they come from the same model, check the following two points, and record the result.
  1. **Shared premise:** do all three units' judgments rest on the same premise? Especially if it is an assumption filled in by the framing agent, state whether the resolution would flip if that premise were wrong.
  2. **Missing alternative:** by treating the proposal only as "do it or not", did the units miss options in between (a reduced version, phased adoption, a different method)? Compare with the framing agent's "options outside the binary", and reflect anything the units did not address in the next actions.

## 5. Output format

```
## MAGI Deliberation Result

**Proposal:** ... (main proposal)
**Follow-up proposals:** (if any)
**Grade:** normal / critical — (one-line reason; mark if raised by a grade objection)
**Additional information:** (answers received from the user before deliberation; items left as assumptions without an answer)
**Preset:** default / ethics / code review / personal decision / original / custom — (one-line reason, runner-up)
**Premises:** confirmed facts / assumptions / unconfirmed (mark assumptions)
**Options outside the binary:** (found by the framing agent)
**Framing:** framing agent / moderator directly

| Unit | Verdict | Confidence | Key rationale | Doubted premise |
|---|---|---|---|---|
| MELCHIOR-1 | Approve | High | ... | ... |
| BALTHASAR-2 | Reject | Medium | ... | ... |
| CASPER-3 | Approve | Medium | ... | ... |

**Resolution:** passed / conditionally passed / rejected / on hold / error (approve n/3, of which m conditional)
**Follow-up resolutions:** (if any, per proposal)
**Conflicting conditions:** (if any, shown as is for the user to choose)
**Conditions:** (if conditionally passed, all conditions combined)
**Debate round:** (if held) who changed position on what new argument, or that no one changed

**Unanimity check:** (if applicable) shared premise, missing alternative

**Minority opinion:** keep the dissenting unit's argument without shortening it.

**What would flip the resolution:** ...
**Next actions:** ...
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

Write the result in the language of the user's request.

## On limitations

If the three units come from the same model, this is not true design diversity. Just as the original MAGI came from one person's personality, common-mode failure remains. For important proposals, add one line at the end of the result recommending a review from other sources, other people, or another model as well.

Separating the framing agent does not change the fact that it is the same model. The point of judgment moves from the moderator to an independent agent; it does not disappear. The framing result is shown in the output as is so that the user can review this point directly.
