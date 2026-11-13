# SecondOpinion design system: "the proofreader's desk"

The product marks up a report the way an editor does: it strikes out what the data doesn't support and writes the honest wording beneath. The interface should feel like a calm, precise editing desk: paper, ink, a fountain pen, a red correcting line. Not a SaaS dashboard.

## Voices (typography carries the meaning)

| Voice | Font | Use |
| --- | --- | --- |
| The report | Newsreader (serif), class `.reported` or `font-serif` | Any sentence quoted from the report, claim text, the Claim Ladder |
| The tool | IBM Plex Sans (default) | Interface text, labels, buttons, explanations |
| The data | IBM Plex Mono (`font-mono`), class `num` for tabular figures | Numbers with denominators, sample IDs, checksums, code, claim ids |

Scale: page title `pageTitle` (30/36px, semibold, tight), section title `sectionTitle` (18px), body 16px, small 14px, never below 12px (only for dense stepper/caption text). Line length under 75 characters for prose (`max-w-prose` / `max-w-[65ch]`). Sentence case everywhere. No ALL-CAPS labels, no tracked-out eyebrows.

## Colour tokens (Tailwind utilities: `bg-paper`, `text-ink`, `border-rule` ...)

paper (page), sheet (panels, fields), wash (quiet inset), ink / ink-soft / ink-faint (text), rule / rule-strong (lines), pen / pen-deep / pen-tint (the one primary action colour), supported / contradicted / insufficient with `-tint` backgrounds. **Never use raw hex or Tailwind palette colours (`emerald-*`, `slate-*`, `red-*`) in components.** Colour is never the only signal: pair every verdict colour with an icon and the word.

## Shape and depth

Radii: `rounded-control` (buttons, fields), `rounded-panel` (panels), `rounded-stamp` (verdict stamps, chips). Depth comes from hairlines (`border-rule`) and whitespace, not shadows. `shadow-raised` only for popovers. Do not wrap everything in identical cards: use rules, columns and indentation to group; use a bordered panel only for a genuinely separate object (a form, a code block, a result).

## Components you can import

`@/lib/ui`: `buttonPrimary` (one per screen), `buttonSecondary`, `buttonQuiet`, `fieldInput`, `fieldLabel`, `fieldHint`, `card`, `sectionTitle`, `pageTitle`, `pageWidth`, `focusRing`.
Shared (do not edit): `VerdictBadge`, `SolidityTag`, `StatementLabel`, `StepNav`, `ResearchBanner`, `Wordmark`.
Icons: `lucide-react` only (stroke icons, `aria-hidden` when decorative, 16 or 20px, one stroke weight). No emoji, no unicode glyphs as icons, no inline `⚠ ✓ ✕ →`.

## Rules every screen follows

- Page container: `<main className={pageWidth}>` (max 56rem, generous padding); the shell already supplies the left step rail, skip link and research banner.
- One primary action per screen. Disabled primary actions say why in text next to them.
- Touch targets at least 44px (`min-h-11`). Visible focus (already global). `cursor-pointer` on clickable things. Hover and press feedback 150-200ms colour/opacity only, never layout shift. Respect reduced motion (already global).
- Motion only answers an action (expanding, copying, confirming). No entrance animations on load.
- Plain words from the user's side: "Check the files", not "Validate release". Buttons name the action. Errors say what happened and what to do, in `role="alert"` or `aria-live="polite"` regions.
- Responsive from 375px: single column, no horizontal page scroll; wide tables scroll inside their own container with a visible label. Test mentally at 375, 768, 1280.
- Redline styling is global: `<del>` is a red line-through, `<ins>` is the underlined green correction. Use those elements for the Claim Ladder, never custom spans.
- Avoid the generic tells: one-word colour accents in headlines, identical rounded cards with identical shadows, middle-dot meta strings, `WORD - fragment` labels, mono for every small label, arrows appended to buttons, gradient washes.
- Keep every existing behaviour, prop, text constant used by tests, route and a11y relationship (labels, aria-live, aria-current) intact. This is a visual and layout change, not a behaviour change.
