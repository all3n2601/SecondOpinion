// Shared Tailwind class strings: one visual system for every screen.
// Neutral slate surfaces, one deep-green accent, square-ish corners, small-caps labels.

export const container = "mx-auto w-full max-w-6xl px-6";

export const focusRing =
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-800";

export const focusRingOnDark =
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white";

const buttonBase =
  "inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-md px-4 text-sm font-semibold whitespace-nowrap transition-colors disabled:cursor-not-allowed";

export const buttonPrimary = `${buttonBase} bg-emerald-900 text-white shadow-sm hover:bg-emerald-800 disabled:bg-slate-300 disabled:text-slate-600 disabled:shadow-none ${focusRing}`;

export const buttonSecondary = `${buttonBase} border border-slate-300 bg-white text-slate-800 shadow-sm hover:border-slate-400 hover:bg-slate-50 disabled:text-slate-400 ${focusRing}`;

export const linkText = `rounded-sm font-medium text-emerald-900 underline decoration-emerald-900/30 underline-offset-4 hover:decoration-emerald-900 ${focusRing}`;

export const fieldInput = `h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-900 shadow-sm placeholder:text-slate-500 hover:border-slate-400 ${focusRing}`;

export const fieldLabel = "block text-sm font-semibold text-slate-900";

export const fieldHint = "mt-1.5 text-sm text-slate-600";

/** Small-caps label used for eyebrows, table headers and field names. */
export const eyebrow = "text-xs font-semibold tracking-wider text-slate-500 uppercase";

export const panel = "rounded-md border border-slate-200 bg-white shadow-sm";

/** Kept for older call sites: a padded panel. */
export const card = `${panel} p-6`;

export const tableHead = "bg-slate-50 text-xs font-semibold tracking-wider text-slate-600 uppercase";

export const chip = "inline-flex items-center gap-1 rounded-sm border px-2 py-0.5 text-xs font-semibold";
