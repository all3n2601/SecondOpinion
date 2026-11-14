// Browser client for the FastAPI backend. Every call goes through the Next.js `/api/*` proxy.
// On a non-2xx response each function throws Error(detail), using the API's "detail" text.

import type {
  AiStatus,
  AuditResult,
  Claim,
  DecisionChoice,
  DecisionSuggestion,
  ExportResponse,
  ExtractResult,
  ClaimResult,
  NarrateResponse,
  Role,
  RoleView,
} from "./types";
import { claimSlots } from "./narrate";
import { finalVerdict } from "./review";

/** FastAPI sends `detail` as a string for our own errors and as a list for request validation errors. */
function detailText(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => (item && typeof item === "object" && "msg" in item ? String(item.msg) : null))
      .filter((msg): msg is string => Boolean(msg));
    return messages.length ? messages.join("; ") : null;
  }
  return null;
}

async function request<T>(path: string, init?: { method?: "GET" | "POST"; body?: unknown }): Promise<T> {
  let response: Response;
  try {
    const body = init?.body;
    const form = body instanceof FormData; // the browser sets the multipart Content-Type itself
    response = await fetch(`/api${path}`, {
      method: init?.method ?? "GET",
      headers: body === undefined || form ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : form ? body : JSON.stringify(body),
    });
  } catch {
    throw new Error("Could not reach the SecondOpinion API. Is the backend running?");
  }

  if (!response.ok) {
    let message: string | null = null;
    try {
      message = detailText((await response.json())?.detail);
    } catch {
      // Body was not JSON; fall through to the generic message.
    }
    // A 5xx with no detail usually means the dev proxy could not connect to the backend at all.
    if (message === null && response.status >= 500) {
      throw new Error(`Could not reach the SecondOpinion API (HTTP ${response.status}). Is the backend running?`);
    }
    throw new Error(message ?? `The API returned an error (HTTP ${response.status}).`);
  }
  return (await response.json()) as T;
}

export function extractClaims(reportText: string): Promise<ExtractResult> {
  return request("/extract", { method: "POST", body: { report_text: reportText } });
}

export interface ReportFile {
  filename: string;
  kind: "markdown" | "text" | "pdf";
  text: string;
  /** Page count, for PDFs only. */
  pages: number | null;
}

/** A report file read to text on the server; used for PDFs, whose text the browser cannot read itself. */
export function readReportFile(file: File): Promise<ReportFile> {
  const form = new FormData();
  form.append("file", file);
  return request("/report-file", { method: "POST", body: form });
}

export function classifySentence(text: string, sentenceIndex: number): Promise<Claim> {
  return request("/classify", { method: "POST", body: { text, sentence_index: sentenceIndex } });
}

export function runAudit(releaseDir: string, claims: Claim[]): Promise<AuditResult> {
  return request("/audit", { method: "POST", body: { release_dir: releaseDir, claims } });
}

export interface PracticeRelease {
  release_dir: string;
  /** Where it came from: SO_RELEASE_DIR, the challenge repo next to this one, or a temporary download. */
  source: "environment" | "challenge_repo" | "temporary";
  downloaded: string[];
}

/** A release-A folder for the practice run. The first call may download about 70 MB. */
export function getPracticeRelease(): Promise<PracticeRelease> {
  return request("/practice-release", { method: "POST" });
}

export interface OpenedEnvelope {
  envelope: string;
  opened_dir: string;
  /** The file the report came from (claim_auditor_report.md, or the practice brief), null if there is none. */
  report_name: string | null;
  report_text: string | null;
  release_a_dir: string;
  envelope_release_dir: string;
  files: string[];
  /** The checks the organizers' unseal.py passed, in its own words. */
  checks: string[];
  seconds: number;
  notes: string[];
}

/** Open a sealed envelope with the organizers' unseal.py. Takes 10 to 20 seconds. */
export function unsealEnvelope(envelope: string, code: string): Promise<OpenedEnvelope> {
  return request("/envelope/unseal", { method: "POST", body: { envelope, code } });
}

export function suggestDecision(audit: AuditResult): Promise<DecisionSuggestion> {
  return request("/decision", { method: "POST", body: { audit } });
}

export function exportAudit(audit: AuditResult, decision: DecisionChoice): Promise<ExportResponse> {
  return request("/export", { method: "POST", body: { audit, decision } });
}

export function getRoles(): Promise<Role[]> {
  return request("/roles");
}

/** `view` is optional: the server picks it from `detail` when it is left out. */
export function saveRole(role: Omit<Role, "view"> & { view?: RoleView }): Promise<Role[]> {
  return request("/roles", { method: "POST", body: role });
}

/**
 * Ask the optional AI helper for slotted wording. Only these fields per claim leave the browser: id, final verdict,
 * solidity, overridden, the report sentence and the NAMES of the claim slots that claim has a value for. Never a
 * count, a value, a fact or a sample id. Throws like any other call; the caller falls back to templates.
 */
export function narrate(view: RoleView, claims: ClaimResult[]): Promise<NarrateResponse> {
  return request("/ai/narrate", {
    method: "POST",
    body: {
      view,
      claims: claims.map((c) => ({
        id: c.claim.id,
        verdict: finalVerdict(c),
        solidity: c.solidity,
        overridden: c.review?.decision === "override",
        text: c.claim.text,
        slots: Object.keys(claimSlots(c)),
      })),
    },
  });
}

/** Is the optional AI helper switched on? Never throws: an unreachable API reads as "off". */
export async function getAiStatus(): Promise<AiStatus> {
  try {
    const status = await request<Partial<AiStatus>>("/ai/status");
    return {
      enabled: status.enabled === true,
      model: status.model ?? null,
      host: status.host ?? null,
      reason: status.reason ?? null,
    };
  } catch {
    return { enabled: false, model: null, host: null, reason: "The API did not answer" };
  }
}
