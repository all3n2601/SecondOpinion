// Shared Tailwind class strings so every screen has the same buttons, fields and focus rings.

export const focusRing =
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-900";

export const buttonPrimary = `inline-flex items-center justify-center gap-2 rounded-lg bg-emerald-900 px-5 py-2.5 font-medium text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:bg-slate-400 ${focusRing}`;

export const buttonSecondary = `inline-flex items-center justify-center gap-2 rounded-lg border border-emerald-900/40 bg-white px-4 py-2 font-medium text-emerald-950 hover:bg-emerald-50 disabled:cursor-not-allowed disabled:text-slate-400 ${focusRing}`;

export const fieldInput = `w-full rounded-lg border border-slate-400 bg-white px-3 py-2 text-slate-900 placeholder:text-slate-500 ${focusRing}`;

export const fieldLabel = "block font-medium text-slate-900";

export const fieldHint = "mt-1 text-sm text-slate-600";

export const card = "rounded-2xl border border-emerald-900/15 bg-white p-6";
