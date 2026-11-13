// Plain-word labels for claims, shared by the claims list and the audit board.

import type { Claim, ClaimType } from "./types";

export const TYPE_LABEL: Record<ClaimType, string> = {
  COUNT: "Count",
  SHARE: "Share",
  COMPARISON: "Comparison",
  AGREEMENT: "Agreement",
  COVERAGE: "Coverage",
  NOT_ANSWERABLE: "Not answerable",
  UNMAPPED: "No check yet",
};

const SUBJECT_LABEL: Record<string, string> = {
  primary_tumors: "primary tumors",
  all_five_layers: "all five data layers",
  samples: "samples",
  patients: "patients",
  has_protein: "protein data",
  has_survival: "survival data",
  has_mutation: "mutation data",
  has_copy_number: "copy number data",
  has_rna: "RNA data",
};

const number = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });

function fmt(value: number, unit: string | null): string {
  return unit === "percent" ? `${number.format(value)}%` : number.format(value);
}

/** What we read from the sentence, in words: "62%, approximate, Luminal A". */
export function describeParams(claim: Claim): string {
  const p = claim.params;
  const parts: string[] = [];

  if (claim.type === "NOT_ANSWERABLE") {
    if (claim.clinical_terms.length) parts.push(`flagged words: ${claim.clinical_terms.join(", ")}`);
    if (claim.needed_data) parts.push(`would need: ${claim.needed_data}`);
    return parts.join(" · ") || "The data cannot answer this kind of claim";
  }
  if (claim.type === "UNMAPPED") return "No check exists yet for this kind of claim";

  if (p.unit === "all") {
    parts.push("every one");
  } else if (p.stated_value !== null) {
    let stated = fmt(p.stated_value, p.unit);
    if (p.stated_high !== null) stated = `${fmt(p.stated_value, null)}–${fmt(p.stated_high, p.unit)}`;
    if (p.stated_total !== null) stated += ` of ${number.format(p.stated_total)}`;
    parts.push(stated);
  }
  if (p.approximate) parts.push("approximate");
  if (p.subtype) parts.push(p.subtype);
  if (p.subject) parts.push(SUBJECT_LABEL[p.subject] ?? p.subject.replaceAll("_", " "));
  if (p.measure) parts.push(p.measure);
  if (p.direction && p.group_a && p.group_b) parts.push(`${p.direction} in ${p.group_a} than ${p.group_b}`);
  else if (p.direction) parts.push(p.direction);

  return parts.join(", ") || "No details read from this sentence";
}
