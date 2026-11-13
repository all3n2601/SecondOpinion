"use client";

import Link from "next/link";
import { useEffect, useId, useState } from "react";
import { exportAudit, suggestDecision } from "@/lib/api";
import { useAudit } from "@/lib/audit-context";
import { DECISIONS, plural, unreviewedIds, VERDICT_LABEL, VERDICT_STYLE } from "@/lib/review";
import { useRoles } from "@/lib/roles";
import type { AuditResult, Decision, DecisionChoice, DecisionSuggestion, ExportResponse } from "@/lib/types";
import RoleSummary from "./RoleSummary";

const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-900";

function download(filename: string, text: string, type: string) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

interface Suggested {
  audit: AuditResult;
  suggestion?: DecisionSuggestion;
  error?: string;
}

/** Suggested decision, the reviewer's choice, and the two downloads. */
export default function DecisionPanel({ audit }: { audit: AuditResult }) {
  const id = useId();
  const { role } = useAudit();
  const { roles } = useRoles();

  const [suggested, setSuggested] = useState<Suggested | null>(null);
  useEffect(() => {
    let live = true;
    suggestDecision(audit)
      .then((suggestion) => live && setSuggested({ audit, suggestion }))
      .catch((err: Error) => live && setSuggested({ audit, error: err.message }));
    return () => {
      live = false;
    };
  }, [audit]);
  const current = suggested?.audit === audit ? suggested : null; // null while (re)loading
  const suggestion = current?.suggestion ?? null;

  const [picked, setPicked] = useState<Decision | null>(null);
  const choice = picked ?? suggestion?.decision ?? null;
  const [reason, setReason] = useState("");
  const [pickedRole, setPickedRole] = useState<string | null>(null);
  const reviewerRole = pickedRole ?? role;

  const [exported, setExported] = useState<{ key: string; files: ExportResponse } | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const exportKey = JSON.stringify([audit, choice, reason.trim(), reviewerRole]);
  const files = exported?.key === exportKey ? exported.files : null; // stale once anything changes

  const left = unreviewedIds(audit.claims);
  const overrides = audit.claims.filter((c) => c.review?.decision === "override");
  const roleNames = roles?.map((r) => r.name) ?? [];
  if (!roleNames.includes(reviewerRole)) roleNames.unshift(reviewerRole);

  async function runExport(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!choice) return;
    if (!reason.trim()) {
      setExportError("Write a reason for the decision.");
      return;
    }
    const decision: DecisionChoice = { choice, reason: reason.trim(), reviewer_role: reviewerRole };
    setExporting(true);
    setExportError(null);
    try {
      setExported({ key: exportKey, files: await exportAudit(audit, decision) });
    } catch (err) {
      setExportError((err as Error).message);
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="space-y-8">
      <RoleSummary audit={audit} suggestion={suggestion} />

      <section aria-labelledby={`${id}-suggested`} aria-busy={!current} className="rounded-xl border border-emerald-900/15 bg-white p-6">
        <h2 id={`${id}-suggested`} className="text-xl font-semibold">
          Suggested decision
        </h2>
        {!current && <p className="mt-2 text-slate-700">Working out the suggested decision…</p>}
        {current?.error && (
          <p role="alert" className="mt-2 text-rose-800">
            Could not get a suggestion: {current.error}
          </p>
        )}
        {suggestion && (
          <>
            <p className="mt-2 text-2xl font-semibold text-emerald-900">{suggestion.decision}</p>
            <p className="mt-1 text-slate-700">{suggestion.rule}.</p>
            <h3 className="mt-4 font-semibold">Why</h3>
            <ul className="mt-1 list-disc space-y-1 pl-5">
              {suggestion.reasons.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
            <h3 className="mt-4 font-semibold">Who must sign off</h3>
            <ul className="mt-1 list-disc pl-5">
              {suggestion.sign_off.map((who) => (
                <li key={who}>{who}</li>
              ))}
            </ul>
            <h3 className="mt-4 font-semibold">What would change this decision</h3>
            <ul className="mt-1 list-disc space-y-1 pl-5">
              {suggestion.would_change.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          </>
        )}
      </section>

      {overrides.length > 0 && (
        <section aria-labelledby={`${id}-conflicts`} className="rounded-xl border border-amber-300 bg-amber-50 p-6">
          <h2 id={`${id}-conflicts`} className="text-xl font-semibold">
            Where a person disagreed with the tool
          </h2>
          <ul className="mt-3 space-y-4">
            {overrides.map((c) => (
              <li key={c.claim.id}>
                <p className="font-medium">{c.claim.id}: {c.claim.text}</p>
                <div className="mt-2 grid gap-2 sm:grid-cols-2">
                  <p className={`rounded border px-3 py-2 ${VERDICT_STYLE[c.verdict]}`}>
                    Tool: <strong>{VERDICT_LABEL[c.verdict]}</strong>
                  </p>
                  <p className={`rounded border px-3 py-2 ${VERDICT_STYLE[c.review!.final_verdict]}`}>
                    Reviewer: <strong>{VERDICT_LABEL[c.review!.final_verdict]}</strong>
                  </p>
                </div>
                <p className="mt-1 text-sm">
                  Resolved by {c.review!.reviewer_role}: {c.review!.reason}
                </p>
              </li>
            ))}
          </ul>
        </section>
      )}

      <form onSubmit={runExport} noValidate aria-labelledby={`${id}-choose`} className="rounded-xl border border-emerald-900/15 bg-white p-6">
        <h2 id={`${id}-choose`} className="text-xl font-semibold">
          Your decision
        </h2>
        <fieldset className="mt-3" disabled={!suggestion}>
          <legend className="text-sm font-medium">Decision</legend>
          <div className="mt-2 grid gap-2 sm:grid-cols-2">
            {DECISIONS.map((d) => (
              <label key={d} className="flex items-center gap-2">
                <input
                  type="radio"
                  name={`${id}-decision`}
                  value={d}
                  checked={choice === d}
                  onChange={() => setPicked(d)}
                  className={FOCUS}
                />
                {d}
                {d === suggestion?.decision && <span className="text-sm text-slate-600">(suggested)</span>}
              </label>
            ))}
          </div>
        </fieldset>

        <label htmlFor={`${id}-reason`} className="mt-4 block text-sm font-medium">
          Reason (required)
        </label>
        <textarea
          id={`${id}-reason`}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={3}
          required
          className={`mt-1 w-full rounded-md border border-slate-400 px-3 py-2 text-sm ${FOCUS}`}
        />

        <label htmlFor={`${id}-role`} className="mt-4 block text-sm font-medium">
          Your role
        </label>
        <select
          id={`${id}-role`}
          value={reviewerRole}
          onChange={(e) => setPickedRole(e.target.value)}
          className={`mt-1 rounded-md border border-slate-400 bg-white px-3 py-2 text-sm ${FOCUS}`}
        >
          {roleNames.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>

        {left.length > 0 && (
          <p className="mt-4 text-sm text-amber-900">
            {plural(left.length, "claim", "claims")} not reviewed yet ({left.join(", ")}).{" "}
            <Link href="/review" className="underline underline-offset-4">
              Go to Review
            </Link>
          </p>
        )}
        {exportError && (
          <p role="alert" className="mt-4 text-sm font-medium text-rose-800">
            {exportError}
          </p>
        )}

        <button
          type="submit"
          disabled={!choice || exporting}
          className={`mt-4 block rounded-lg bg-emerald-900 px-5 py-3 font-medium text-white disabled:opacity-50 ${FOCUS}`}
        >
          {exporting ? "Exporting…" : "Export"}
        </button>
      </form>

      {files && (
        <section aria-labelledby={`${id}-downloads`} className="rounded-xl border border-emerald-700 bg-emerald-50 p-6">
          <h2 id={`${id}-downloads`} className="text-xl font-semibold">
            Downloads
          </h2>
          <p className="mt-1 text-sm text-slate-700">
            audit.json follows the shared findings format v0.2. The Decision Record lists who must sign off.
          </p>
          <div className="mt-4 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => download("audit.json", JSON.stringify(files.audit_json, null, 2), "application/json")}
              className={`rounded-md bg-emerald-900 px-4 py-2 font-medium text-white ${FOCUS}`}
            >
              Download audit.json
            </button>
            <button
              type="button"
              onClick={() => download("decision_record.md", files.decision_record_md, "text/markdown")}
              className={`rounded-md border border-emerald-900 px-4 py-2 font-medium text-emerald-900 ${FOCUS}`}
            >
              Download decision_record.md
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
