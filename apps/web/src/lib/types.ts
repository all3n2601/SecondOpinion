// Mirror of second_opinion/model.py. snake_case, same field names as the Python dataclasses.

export type Verdict = "supported" | "contradicted" | "insufficient_evidence";

export type Solidity =
  | "holds_under_every_variant"
  | "holds_under_some_variants"
  | "not_applicable";

export type Decision = "Proceed" | "Fix a problem" | "Narrow the question" | "Stop";

export type ClaimType =
  | "COUNT"
  | "SHARE"
  | "COMPARISON"
  | "AGREEMENT"
  | "COVERAGE"
  | "NOT_ANSWERABLE"
  | "UNMAPPED";

export interface ClaimParams {
  stated_value: number | null;
  stated_high: number | null;
  stated_total: number | null;
  unit: string | null;
  decimals: number | null;
  approximate: boolean;
  subject: string | null;
  subtype: string | null;
  direction: string | null;
  measure: string | null;
  group_a: string | null;
  group_b: string | null;
}

export interface Claim {
  id: string;
  text: string;
  sentence_index: number;
  type: ClaimType;
  params: ClaimParams;
  needed_data: string | null;
  clinical_terms: string[];
  /** "ai" = a sentence the rules skipped that the optional AI helper flagged. Absent in older saved state: treat as "rules". */
  source?: ClaimSource;
  /** The sentence copied exactly as written in the report, Markdown included. Absent or "" = same as `text`. */
  original_text?: string;
}

export type ClaimSource = "rules" | "ai";

// ---- The optional AI helper's check plan (mirror of second_opinion/ai/plan.py) ----

export type FilterField =
  | "sample_type"
  | "sex"
  | "subtype_rna"
  | "subtype_2012"
  | "er_status"
  | "her2_status"
  | "has_layer"
  | "age_years";

export type FilterOp = "eq" | "in" | "gt" | "gte" | "lt" | "lte" | "is_known";

export interface PlanFilter {
  field: FilterField;
  op: FilterOp;
  value: string | number | string[] | null;
}

export type Plan =
  | { op: "count"; of: "samples" | "patients"; where: PlanFilter[] }
  | { op: "share"; where: PlanFilter[]; numerator: PlanFilter[] }
  | {
      op: "compare_means";
      measure: string;
      group_field: "er_status" | "her2_status" | "sex";
      group_a: string;
      group_b: string;
      where: PlanFilter[];
    }
  | { op: "summary_stat"; field: "age_years"; stat: "median" | "mean" | "min" | "max"; where: PlanFilter[] }
  | { op: "rank"; category_field: "subtype_rna" | "subtype_2012"; category: string; where: PlanFilter[] }
  | {
      op: "order";
      category_field: "subtype_rna" | "subtype_2012";
      category_a: string;
      category_b: string;
      where: PlanFilter[];
    };

export type PlanOp = Plan["op"];

export interface Stated {
  kind: "percent" | "count" | "number" | "rank" | "relation" | "direction";
  /** The words of the sentence that state the claim, copied exactly. */
  span: string;
  value: number | null;
  high: number | null;
  total: number | null;
  approximate: boolean;
  relation: "more" | "less" | null;
}

/** What the AI helper proposed. Our code validates it, runs it on the release and sets the verdict. */
export interface AiPlan {
  answerable: boolean;
  needed_data: string | null;
  plan: Plan | null;
  stated: Stated | null;
  rationale: string;
}

export interface AiStatus {
  enabled: boolean;
  model: string | null;
  host: string | null;
  reason: string | null;
}

export interface SentenceInfo {
  index: number;
  text: string;
  claim_id: string | null;
}

export interface ExtractResult {
  sentences: SentenceInfo[];
  claims: Claim[];
}

export interface Fact {
  label: string;
  value: number | null;
  numerator: number | null;
  denominator: number | null;
  sample_ids: string[];
  files: string[];
  code: string;
  unknown_count: number;
  extra: Record<string, number | string>;
}

export interface VariantResult {
  variant_id: string;
  fact: Fact | null;
  verdict: Verdict | null;
}

export interface SkepticResult {
  shuffle_p: number | null;
  n_sites: number;
  site_flips: string[];
}

export interface LadderSegment {
  text: string;
  struck: boolean;
  inserted: boolean;
}

export interface Review {
  decision: "accept" | "override";
  final_verdict: Verdict;
  reason: string;
  reviewer_role: string;
}

export interface ClaimResult {
  claim: Claim;
  verdict: Verdict;
  solidity: Solidity;
  fact: Fact | null;
  correct_value: string | null;
  missing_evidence: string | null;
  variants: VariantResult[];
  flips_on: string[];
  skeptic: SkepticResult | null;
  ladder: LadderSegment[];
  limitation: string | null;
  review: Review | null;
  /** Present only when the optional AI helper proposed the check plan for this claim. */
  ai_plan?: AiPlan | null;
}

export interface ReleaseInfo {
  name: string;
  files: { file: string; sha256: string }[];
}

export interface AuditResult {
  release: ReleaseInfo;
  claims: ClaimResult[];
  notes: string[];
}

export interface DecisionSuggestion {
  decision: Decision;
  rule: string;
  reasons: string[];
  sign_off: string[];
  would_change: string[];
}

export interface DecisionChoice {
  choice: Decision;
  reason: string;
  reviewer_role: string;
}

// API request / response bodies
export interface ExtractRequest {
  report_text: string;
}

export interface ClassifyRequest {
  text: string;
  sentence_index: number;
}

export interface AuditRequest {
  release_dir: string;
  claims: Claim[];
}

export interface DecisionRequest {
  audit: AuditResult;
}

export interface ExportRequest {
  audit: AuditResult;
  decision: DecisionChoice;
}

export interface ExportResponse {
  audit_json: Record<string, unknown>;
  decision_record_md: string;
}

export interface Role {
  name: string;
  sections: string[];
  detail: "summary" | "standard" | "full";
  explain_terms: boolean;
}
