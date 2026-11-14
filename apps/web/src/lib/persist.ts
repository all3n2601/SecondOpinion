// Pure parse / validate / serialize logic for the sessionStorage copy of the audit state.
// No React imports, so it can be checked on its own with node. The audit is derived from
// patient-derived research data, so it goes in sessionStorage (cleared when the tab closes), never localStorage.

import { DECISIONS } from "./review";
import type { AuditResult, Claim, Decision, ExportResponse, SentenceInfo } from "./types";

export const STORAGE_KEY = "secondopinion:v1";
export const STORAGE_VERSION = 1;
export const DEFAULT_ROLE = "Data-use reviewer";
/** Above this many characters we skip persisting (sessionStorage is about 5 MB and a failed write is wasted work). */
export const MAX_PERSIST_CHARS = 4_000_000;

/** The decision a person recorded by exporting, with the files it produced. Only ever about the current audit. */
export interface RecordedDecision {
  choice: Decision;
  reason: string;
  reviewer_role: string;
  files: ExportResponse;
}

/** The decision form before export: what is picked so far. Null fields mean "not chosen yet" (the suggestion or the
 * viewing role stands in). Kept so a trip to a claim's evidence, or a reload, does not lose it. */
export interface DecisionDraft {
  choice: Decision | null;
  reason: string;
  reviewer_role: string | null;
}

/** The part of the audit context that survives a reload. Transient UI state is not in here. */
export interface PersistedState {
  reportText: string;
  releaseDir: string;
  sentences: SentenceInfo[];
  claims: Claim[];
  audit: AuditResult | null;
  role: string;
  /** Null until the decision is exported; cleared whenever the audit or a review changes. */
  decision: RecordedDecision | null;
  /** The decision form as last edited; cleared with the decision. */
  draft: DecisionDraft | null;
}

export function emptyState(releaseDir = ""): PersistedState {
  return { reportText: "", releaseDir, sentences: [], claims: [], audit: null, role: DEFAULT_ROLE, decision: null, draft: null };
}

/** Nothing worth keeping: no report, no extraction, no audit. */
export function isEmptyState(s: PersistedState): boolean {
  return s.audit === null && s.reportText.trim() === "" && s.sentences.length === 0 && s.claims.length === 0;
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function isSentence(v: unknown): v is SentenceInfo {
  return (
    isRecord(v) &&
    typeof v.index === "number" &&
    typeof v.text === "string" &&
    (v.claim_id === null || typeof v.claim_id === "string")
  );
}

function isClaim(v: unknown): v is Claim {
  return (
    isRecord(v) &&
    typeof v.id === "string" &&
    typeof v.text === "string" &&
    typeof v.sentence_index === "number" &&
    typeof v.type === "string" &&
    isRecord(v.params)
  );
}

function isAudit(v: unknown): v is AuditResult {
  if (!isRecord(v) || !isRecord(v.release) || !Array.isArray(v.claims)) return false;
  if (typeof v.release.name !== "string" || !Array.isArray(v.release.files)) return false;
  return v.claims.every((c) => isRecord(c) && isClaim(c.claim) && typeof c.verdict === "string");
}

function isDecision(v: unknown): v is RecordedDecision {
  return (
    isRecord(v) &&
    DECISIONS.includes(v.choice as Decision) &&
    typeof v.reason === "string" &&
    typeof v.reviewer_role === "string" &&
    isRecord(v.files) &&
    isRecord(v.files.audit_json) &&
    typeof v.files.decision_record_md === "string"
  );
}

function isDraft(v: unknown): v is DecisionDraft {
  return (
    isRecord(v) &&
    (v.choice === null || DECISIONS.includes(v.choice as Decision)) &&
    typeof v.reason === "string" &&
    (v.reviewer_role === null || typeof v.reviewer_role === "string")
  );
}

/**
 * Turn the raw stored string into state, or null when there is nothing usable (missing, not JSON,
 * wrong version, wrong shape). Missing or malformed individual fields fall back to their defaults;
 * a malformed audit is dropped rather than risk crashing a page that trusts its shape.
 */
export function parsePersisted(raw: string | null | undefined, releaseDirDefault = ""): PersistedState | null {
  if (typeof raw !== "string" || raw === "" || raw.length > MAX_PERSIST_CHARS) return null;
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!isRecord(data) || data.version !== STORAGE_VERSION || !isRecord(data.state)) return null;

  const s = data.state;
  const sentences = Array.isArray(s.sentences) ? s.sentences.filter(isSentence) : [];
  const claims = Array.isArray(s.claims) ? s.claims.filter(isClaim) : [];
  const audit = isAudit(s.audit) ? s.audit : null;
  const state: PersistedState = {
    reportText: typeof s.reportText === "string" ? s.reportText : "",
    releaseDir: typeof s.releaseDir === "string" ? s.releaseDir : releaseDirDefault,
    sentences,
    claims,
    audit,
    role: typeof s.role === "string" && s.role.trim() !== "" ? s.role : DEFAULT_ROLE,
    // A decision without the audit it was about means nothing, so it is dropped with it.
    decision: audit && isDecision(s.decision) ? s.decision : null,
    draft: audit && isDraft(s.draft) ? s.draft : null,
  };
  return isEmptyState(state) ? null : state;
}

/** The string to store, or null when the state is empty or too large (the caller then clears the key). */
export function serializeState(state: PersistedState): string | null {
  if (isEmptyState(state)) return null;
  try {
    const text = JSON.stringify({ version: STORAGE_VERSION, state });
    return text.length > MAX_PERSIST_CHARS ? null : text;
  } catch {
    return null;
  }
}

// Storage access. Every call is wrapped: private mode, disabled storage and quota errors must never break the app.

function store(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.sessionStorage;
  } catch {
    return null;
  }
}

export function loadPersisted(releaseDirDefault = ""): PersistedState | null {
  try {
    return parsePersisted(store()?.getItem(STORAGE_KEY), releaseDirDefault);
  } catch {
    return null;
  }
}

/** Write the state, or clear the key when there is nothing (or too much) to keep. Never throws. */
export function savePersisted(state: PersistedState): void {
  try {
    const s = store();
    if (!s) return;
    const text = serializeState(state);
    if (text === null) s.removeItem(STORAGE_KEY);
    else s.setItem(STORAGE_KEY, text);
  } catch {
    // Quota exceeded or storage disabled: the app keeps working from memory.
    clearPersisted();
  }
}

export function clearPersisted(): void {
  try {
    store()?.removeItem(STORAGE_KEY);
  } catch {
    // nothing to do
  }
}
