// Shared Tailwind class strings so every screen has the same buttons, fields and panels.
// Colours come from the tokens in globals.css (see apps/web/DESIGN.md); never use raw hex or palette colours.

export const focusRing =
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-pen";

const control =
  "inline-flex min-h-11 cursor-pointer items-center justify-center gap-2 rounded-control px-5 py-2 text-[0.9375rem] font-semibold transition-colors duration-150 disabled:cursor-not-allowed";

/** The one primary action on a screen. */
export const buttonPrimary = `${control} bg-pen text-white hover:bg-pen-deep disabled:bg-rule-strong disabled:text-ink-soft ${focusRing}`;

/** Everything else. */
export const buttonSecondary = `${control} border border-rule-strong bg-sheet text-ink hover:border-ink-soft hover:bg-wash disabled:border-rule disabled:text-ink-faint ${focusRing}`;

/** Low-emphasis actions inside dense rows (copy, download, remove). */
export const buttonQuiet = `inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-control px-3 py-2 text-sm font-medium text-pen underline-offset-4 transition-colors duration-150 hover:bg-pen-tint hover:underline disabled:cursor-not-allowed disabled:text-ink-faint ${focusRing}`;

export const fieldInput = `min-h-11 w-full rounded-control border border-rule-strong bg-sheet px-3 py-2 text-ink placeholder:text-ink-faint transition-colors duration-150 hover:border-ink-soft ${focusRing}`;

export const fieldLabel = "block text-sm font-semibold text-ink";

export const fieldHint = "mt-1 text-sm text-ink-soft";

/** A bordered panel; flat, separated by a hairline rather than a shadow. */
export const card = "rounded-panel border border-rule bg-sheet p-6";

/** Small heading that names a group of facts, in sentence case. */
export const sectionTitle = "text-lg font-semibold tracking-tight text-ink";

/** Page title. */
export const pageTitle = "text-3xl font-semibold tracking-tight text-ink sm:text-4xl";

/** Standard page container inside the shell's main column. */
export const pageWidth = "mx-auto w-full max-w-4xl px-5 py-8 sm:px-8 sm:py-12";
