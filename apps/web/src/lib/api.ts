// Browser client for the FastAPI backend. Every call goes through the Next.js `/api/*` proxy.
// On a non-2xx response each function throws Error(detail), using the API's "detail" text.

import type {
  AuditResult,
  Claim,
  DecisionChoice,
  DecisionSuggestion,
  ExportResponse,
  ExtractResult,
  Role,
} from "./types";

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
    response = await fetch(`/api${path}`, {
      method: init?.method ?? "GET",
      headers: init?.body === undefined ? undefined : { "Content-Type": "application/json" },
      body: init?.body === undefined ? undefined : JSON.stringify(init.body),
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
    throw new Error(message ?? `The API returned an error (HTTP ${response.status}).`);
  }
  return (await response.json()) as T;
}

export function extractClaims(reportText: string): Promise<ExtractResult> {
  return request("/extract", { method: "POST", body: { report_text: reportText } });
}

export function classifySentence(text: string, sentenceIndex: number): Promise<Claim> {
  return request("/classify", { method: "POST", body: { text, sentence_index: sentenceIndex } });
}

export function runAudit(releaseDir: string, claims: Claim[]): Promise<AuditResult> {
  return request("/audit", { method: "POST", body: { release_dir: releaseDir, claims } });
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

export function saveRole(role: Role): Promise<Role[]> {
  return request("/roles", { method: "POST", body: role });
}
