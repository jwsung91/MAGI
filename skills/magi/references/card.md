# MAGI result card

A compact visual summary drawn first, before the Markdown result, only when a tool that renders interactive visuals inline in the conversation is available. The Markdown result stays complete on its own; the card never replaces it.

## When to draw it

- Draw it only if such a tool is available in this session. Without one, skip the card entirely: do not print its HTML or code, and do not create a file for it.
- Skip it when the user asks for no card (e.g. "no card", "카드 없이").
- One card per deliberation, before the Markdown result. Draw it only once the resolution is tallied; at most one short line may come before it. The full Markdown result follows the card.

## Content

Take every value from the same result the Markdown and JSON come from. Field names below match `result.schema.json`.

**Header**
- `agenda` (the main proposal), with `grade` and `preset` as a small caption above it.
- Resolution badge on the right: `verdict` (passed / rejected / on hold / error), with `approve_count`/3 below it. If a debate round was held, add "debate: 1 round".

**Three unit tiles, side by side, in the order MELCHIOR-1, BALTHASAR-2, CASPER-3**
- Unit name, `perspective`, and the verdict (approve / reject / error). Fill the whole tile with the verdict's color, with the matching text color (see Look). Do not show confidence on the tile.
- Build the tiles as plain block elements (`div` with `role="button"` and `tabindex="0"`), not `<button>`: some hosts restyle buttons with a transparent background, which wipes out the fill. Handle Enter and Space as well as click.
- Show the selected tile by changing its own border color. Give every tile a 2px transparent border at rest so selecting one does not shift the layout. Do not use `outline` for selection.
- Clicking a tile shows that unit's details in one panel below the tiles: `confidence` as small text, then `rationale`, `doubted_premise`, and `recommendations` if any. Only one unit's details are shown at a time. Before any click, the panel says to click a unit.
- A unit with verdict `error` shows its `error` text instead of rationale.

**Footer**
- `minority`, if present.
- `follow_ups`, if present: one row each with the agenda, its resolution badge (`verdict`, `approve_count`/3), and three small unit chips in the order MELCHIOR-1, BALTHASAR-2, CASPER-3, filled with each unit's verdict color from `follow_ups[].units`. Chips follow the same rules as tiles (block elements, keyboard support, border for selection). Clicking a chip shows that unit's `confidence` and `rationale` for that follow-up in the same details panel, labeled with the follow-up it belongs to. Only one tile or chip is selected at a time.

**Information mode**
- No resolution badge and no verdict badges. Each tile shows the unit's perspective; clicking it shows that unit's `answer`. Add the common ground and where they diverge in the footer.

## Look

- Neutral and flat: plain rounded cards on the host's surfaces, thin borders, no gradients or shadows.
- Use the host's theme variables so it works in light and dark mode.
- Colors carry meaning only. Unit tiles: approve = blue, reject = red, error = gray with the error text shown. Resolution badge: passed = green, rejected = red, on hold = yellow, error = red. Everything else, including the card background, stays neutral.
- Set these colors inline on each element, never only in a `<style>` block, and never by mixing host variables, which may not render. Use the host's role variable with a fixed fallback, so the color shows even where the variable is missing:

  | Meaning | Fill | Text |
  |---|---|---|
  | Approve | `var(--bg-accent, #E6F1FB)` | `var(--text-accent, #185FA5)` |
  | Reject, rejected | `var(--bg-danger, #FCEBEB)` | `var(--text-danger, #A32D2D)` |
  | Passed | `var(--bg-success, #EAF3DE)` | `var(--text-success, #3B6D11)` |
  | On hold | `var(--bg-warning, #FAEEDA)` | `var(--text-warning, #854F0B)` |
  | Error (unit) | `var(--surface-1, #F1EFE8)` | `var(--text-secondary, #5F5E5A)` |

  The selected tile's border uses its own text color.
- Confidence has no color of its own; it appears only as text in the details panel.
- Do not imitate the screen from the series: no hexagonal or octagonal panel layout, no Japanese labels, no orange-on-black styling.

## Language

All labels and text follow the output language of the result. Unit names (MELCHIOR-1, BALTHASAR-2, CASPER-3) stay as they are. Enum values from the JSON are translated for display.
