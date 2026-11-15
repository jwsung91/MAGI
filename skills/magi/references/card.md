# MAGI result card

A compact visual summary drawn after the Markdown result, only when a tool that renders interactive visuals inline in the conversation is available. The Markdown result stays complete on its own; the card never replaces it.

## When to draw it

- Draw it only if such a tool is available in this session. Without one, skip the card entirely: do not print its HTML or code, and do not create a file for it.
- Skip it when the user asks for no card (e.g. "no card", "카드 없이").
- One card per deliberation, after the Markdown result.

## Content

Take every value from the same result the Markdown and JSON come from. Field names below match `result.schema.json`.

**Header**
- `agenda` (the main proposal), with `grade` and `preset` as a small caption above it.
- Resolution badge on the right: `verdict` (passed / rejected / on hold / error), with `approve_count`/3 below it. If a debate round was held, add "debate: 1 round".

**Three unit tiles, side by side, in the order MELCHIOR-1, BALTHASAR-2, CASPER-3**
- Unit name, `perspective`, a verdict badge (approve / reject / error), and `confidence`.
- Clicking a tile shows that unit's details in one panel below the tiles: `rationale`, `doubted_premise`, and `recommendations` if any. Only one unit's details are shown at a time. Before any click, the panel says to click a unit.
- A unit with verdict `error` shows its `error` text instead of rationale.

**Footer**
- `minority`, if present.
- `follow_ups`, if present: one short line each with the agenda and its verdict.

**Information mode**
- No resolution badge and no verdict badges. Each tile shows the unit's perspective; clicking it shows that unit's `answer`. Add the common ground and where they diverge in the footer.

## Look

- Neutral and flat: plain rounded cards on the host's surfaces, thin borders, no gradients or shadows.
- Use the host's theme variables so it works in light and dark mode.
- Colors carry meaning only: approve and passed = success, reject and rejected = danger, on hold = warning, error = danger with the error text shown. Everything else stays neutral.
- Do not imitate the screen from the series: no hexagonal or octagonal panel layout, no Japanese labels, no orange-on-black styling.

## Language

All labels and text follow the output language of the result. Unit names (MELCHIOR-1, BALTHASAR-2, CASPER-3) stay as they are. Enum values from the JSON are translated for display.
