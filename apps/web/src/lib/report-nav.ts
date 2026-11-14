// Where the Report view (/board/report) keeps the reader's place: the URL hash names the marked claim
// (`#mark-C2`), so reload, Back and "Back to the report" all land on it. Pure functions: no React, no window.

export const REPORT_PATH = "/board/report";

/** The `from` value an evidence link carries when it was opened from the Report view. */
export const FROM_REPORT = "report";

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

/** The Report view, opened at one claim's mark when `id` is given. */
export function reportHref(id?: string): string {
  return id === undefined ? REPORT_PATH : `${REPORT_PATH}#${markAnchor(encodeURIComponent(id))}`;
}

/** A claim's evidence page; from the Report view it carries `?from=report` so its way back leads to the report. */
export function evidenceHref(id: string, fromReport = false): string {
  return `/board/${encodeURIComponent(id)}${fromReport ? `?from=${FROM_REPORT}` : ""}`;
}

/** Whether an evidence page's `from` search param says it was opened from the Report view. */
export function cameFromReport(from: string | string[] | undefined): boolean {
  return (Array.isArray(from) ? from[0] : from) === FROM_REPORT;
}
