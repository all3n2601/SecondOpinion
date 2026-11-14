// Where a marked report keeps the reader's place: the URL hash names the marked claim (`#mark-C2`), so
// reload, Back and "Back to the report" all land on it. A marked report appears in two places: the Report
// view of the board (/board/report) and, once a decision is recorded, the Decision page (/decision). An
// evidence link opened from either carries `?from=report` or `?from=decision`, so its way back leads to the
// same sentence. Pure functions: no React, no window.

export const REPORT_PATH = "/board/report";
export const DECISION_PATH = "/decision";

/** The page a marked claim was opened from, and so the page its evidence leads back to. */
export type ReturnView = "report" | "decision";

const PATHS: Record<ReturnView, string> = { report: REPORT_PATH, decision: DECISION_PATH };

/** How the evidence page names its way back. */
export const RETURN_LABEL: Record<ReturnView, { crumb: string; back: string }> = {
  report: { crumb: "Report", back: "Back to the report" },
  decision: { crumb: "Decision", back: "Back to the decision" },
};

/** The element id (and hash fragment, without "#") of a claim's mark in the report. */
export function markAnchor(id: string): string {
  return `mark-${id}`;
}

const PREFIX = `#${markAnchor("")}`;

/** The claim id a hash names (`#mark-C2` -> "C2"); null for no hash, another fragment or a garbled one. */
export function markIdFromHash(hash: string): string | null {
  if (!hash.startsWith(PREFIX) || hash.length === PREFIX.length) return null;
  try {
    return decodeURIComponent(hash.slice(PREFIX.length));
  } catch {
    return null;
  }
}

/** A page with a marked report, opened at one claim's mark when `id` is given. */
export function returnHref(view: ReturnView, id?: string): string {
  return id === undefined ? PATHS[view] : `${PATHS[view]}#${markAnchor(encodeURIComponent(id))}`;
}

/** The board's Report view, opened at one claim's mark when `id` is given. */
export function reportHref(id?: string): string {
  return returnHref("report", id);
}

/** A claim's evidence page; opened from a marked report it carries `?from=…` so its way back leads there. */
export function evidenceHref(id: string, from?: ReturnView): string {
  return `/board/${encodeURIComponent(id)}${from ? `?from=${from}` : ""}`;
}

/** Which marked report an evidence page's `from` search param says it was opened from, if any. */
export function returnView(from: string | string[] | undefined): ReturnView | null {
  const value = Array.isArray(from) ? from[0] : from;
  return value === "report" || value === "decision" ? value : null;
}
