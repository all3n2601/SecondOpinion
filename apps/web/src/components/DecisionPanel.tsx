"use client";

import {
  Circle,
  CircleAlert,
  CircleCheck,
  Download,
  GitCompareArrows,
  LoaderCircle,
  RefreshCcw,
  TriangleAlert,
  UserCheck,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useId, useState } from "react";
import MarkedReport from "@/components/MarkedReport";
import VerdictBadge from "@/components/VerdictBadge";
import { exportAudit, suggestDecision } from "@/lib/api";
import { useAudit } from "@/lib/audit-context";
import { actionSummary, DECISION_HEADLINE } from "@/lib/decision-report";
import { DECISIONS, plural, unreviewedIds } from "@/lib/review";
import { useRoles } from "@/lib/roles";
import type { AuditResult, Decision, DecisionChoice, DecisionSuggestion } from "@/lib/types";
import { buttonPrimary, buttonSecondary, fieldHint, fieldInput, fieldLabel, focusRing, sectionTitle } from "@/lib/ui";
import RoleSummary from "./RoleSummary";

const DECISION_MEANING: Record<Decision, string> = {
  Proceed: "Every claim holds up. Collect the sign-offs and publish.",
  "Fix a problem": "Some claims do not match the data. Reword them to what the data shows, then audit again.",
  "Narrow the question": "The data cannot answer everything. Limit the report to what it can answer.",
  Stop: "Something basic is wrong, such as the data files. Do not publish until it is resolved.",
};

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
  // The recorded (exported) decision lives in the audit context, so it survives a trip to a claim's evidence and a
  // reload; the form starts from it.
  const { role, decision: recorded, setDecision, reportText } = useAudit();
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

  const [picked, setPicked] = useState<Decision | null>(recorded?.choice ?? null);
  const choice = picked ?? suggestion?.decision ?? null;
  const [reason, setReason] = useState(recorded?.reason ?? "");
  const [pickedRole, setPickedRole] = useState<string | null>(recorded?.reviewer_role ?? null);
  const reviewerRole = pickedRole ?? role;

  const [exportError, setExportError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  // The downloads and the report after the decision belong to the decision as exported: change the choice, the
  // reason or the role and they wait for the next export. (A change to the audit clears the recorded decision.)
  const recordedNow =
    recorded && recorded.choice === choice && recorded.reason === reason.trim() && recorded.reviewer_role === reviewerRole
      ? recorded
      : null;
  const files = recordedNow?.files ?? null;

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
      setDecision({ ...decision, files: await exportAudit(audit, decision) });
    } catch (err) {
      setExportError((err as Error).message);
    } finally {
      setExporting(false);
    }
  }

  const gateId = `${id}-gate`;
  const errorId = `${id}-export-error`;

  return (
    <div className="space-y-10">
      <section
        aria-labelledby={`${id}-suggested`}
        aria-busy={!current}
        className="rounded-panel border border-rule bg-sheet p-6 sm:p-8"
      >
        {suggestion ? (
          <h2 id={`${id}-suggested`} className="text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
            The tool suggests: {suggestion.decision}
          </h2>
        ) : (
          <h2 id={`${id}-suggested`} className="text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
            Suggested decision
          </h2>
        )}
        {!current && (
          <p className="mt-3 flex items-center gap-2 text-ink-soft">
            <LoaderCircle aria-hidden="true" className="size-5 animate-spin" />
            Working out the suggested decision…
          </p>
        )}
        {current?.error && (
          <p role="alert" className="mt-3 flex max-w-prose items-start gap-2 text-contradicted">
            <CircleAlert aria-hidden="true" className="mt-1 size-5 shrink-0" />
            <span>
              Could not get a suggestion: {current.error}
              <span className="mt-1 block text-ink-soft">
                Check that the audit service is running, then reload this page.
              </span>
            </span>
          </p>
        )}
        {suggestion && (
          <>
            <p className="mt-2 max-w-prose text-lg text-ink-soft">{suggestion.rule}.</p>

            <h3 className="mt-6 text-sm font-semibold text-ink">Why</h3>
            <ul className="mt-2 max-w-prose list-disc space-y-1.5 pl-5 marker:text-ink-faint">
              {suggestion.reasons.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>

            <div className="mt-6 grid gap-6 border-t border-rule pt-6 md:grid-cols-2 md:gap-10">
              <div>
                <h3 className="flex items-center gap-2 text-sm font-semibold text-ink">
                  <UserCheck aria-hidden="true" className="size-4 text-ink-soft" />
                  Who must sign off
                </h3>
                <ul className="mt-2 list-disc space-y-1.5 pl-5 marker:text-ink-faint">
                  {suggestion.sign_off.map((who) => (
                    <li key={who}>{who}</li>
                  ))}
                </ul>
              </div>
              <div>
                <h3 className="flex items-center gap-2 text-sm font-semibold text-ink">
                  <RefreshCcw aria-hidden="true" className="size-4 text-ink-soft" />
                  What would change this decision
                </h3>
                <ul className="mt-2 list-disc space-y-1.5 pl-5 marker:text-ink-faint">
                  {suggestion.would_change.map((w) => (
                    <li key={w}>{w}</li>
                  ))}
                </ul>
              </div>
            </div>
          </>
        )}
      </section>

      <RoleSummary audit={audit} suggestion={suggestion} />

      {overrides.length > 0 && (
        <section aria-labelledby={`${id}-conflicts`}>
          <h2 id={`${id}-conflicts`} className={`${sectionTitle} flex items-center gap-2`}>
            <GitCompareArrows aria-hidden="true" className="size-5 text-insufficient" />
            Where a person disagreed with the tool
          </h2>
          <ul className="mt-3 divide-y divide-rule rounded-panel border border-rule bg-sheet">
            {overrides.map((c) => (
              <li key={c.claim.id} className="p-5 sm:p-6">
                <p className="num font-mono text-sm font-semibold">{c.claim.id}</p>
                <p className="reported mt-1 max-w-prose">{c.claim.text}</p>
                <div className="mt-3 flex flex-wrap gap-x-10 gap-y-3">
                  <div>
                    <p className="mb-1.5 text-sm text-ink-soft">The tool said</p>
                    <VerdictBadge verdict={c.verdict} />
                  </div>
                  <div>
                    <p className="mb-1.5 text-sm text-ink-soft">The reviewer said</p>
                    <VerdictBadge verdict={c.review!.final_verdict} />
                  </div>
                </div>
                <p className="mt-3 text-sm text-ink-soft">
                  Resolved by {c.review!.reviewer_role}: {c.review!.reason}
                </p>
              </li>
            ))}
          </ul>
        </section>
      )}

      <form
        onSubmit={runExport}
        noValidate
        aria-labelledby={`${id}-choose`}
        className="rounded-panel border border-rule bg-sheet p-6 sm:p-8"
      >
        <h2 id={`${id}-choose`} className={sectionTitle}>
          Your decision
        </h2>
        <p className={fieldHint}>You make the final call. Pick one, say why, and export.</p>
        <fieldset className="mt-4" disabled={!suggestion}>
          <legend className={fieldLabel}>Decision</legend>
          <div className="mt-2 grid gap-3 sm:grid-cols-2">
            {DECISIONS.map((d) => {
              const selected = choice === d;
              return (
                <label key={d} className="relative flex cursor-pointer">
                  <input
                    type="radio"
                    name={`${id}-decision`}
                    value={d}
                    checked={selected}
                    onChange={() => setPicked(d)}
                    className="peer sr-only"
                  />
                  <span
                    className={`flex min-h-11 w-full items-start gap-3 rounded-control border-2 p-4 transition-colors duration-150 peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-pen peer-disabled:cursor-not-allowed peer-disabled:opacity-60 ${
                      selected ? "border-pen bg-pen-tint" : "border-rule bg-sheet hover:border-rule-strong hover:bg-wash"
                    }`}
                  >
                    {selected ? (
                      <CircleCheck aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-pen" strokeWidth={2.25} />
                    ) : (
                      <Circle aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-ink-faint" />
                    )}
                    <span className="min-w-0">
                      <span className={`flex flex-wrap items-center gap-x-2 gap-y-1 text-ink ${selected ? "font-semibold" : "font-medium"}`}>
                        {d}
                        {d === suggestion?.decision && (
                          <span className="rounded-stamp border border-rule-strong bg-sheet px-1.5 py-px text-xs font-medium text-ink-soft">
                            Suggested by the tool
                          </span>
                        )}
                      </span>
                      <span className="mt-1 block text-sm text-ink-soft">{DECISION_MEANING[d]}</span>
                    </span>
                  </span>
                </label>
              );
            })}
          </div>
        </fieldset>

        <div className="mt-6 grid gap-5">
          <div>
            <label htmlFor={`${id}-reason`} className={fieldLabel}>
              Reason (required)
            </label>
            <textarea
              id={`${id}-reason`}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={3}
              required
              aria-invalid={exportError ? true : undefined}
              aria-describedby={exportError ? errorId : undefined}
              className={`${fieldInput} mt-1 max-w-prose`}
            />
          </div>

          <div>
            <label htmlFor={`${id}-role`} className={fieldLabel}>
              Your role
            </label>
            <select
              id={`${id}-role`}
              value={reviewerRole}
              onChange={(e) => setPickedRole(e.target.value)}
              className={`${fieldInput} mt-1 w-full sm:w-72`}
            >
              {roleNames.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {left.length > 0 && (
          <p className="mt-6 flex max-w-prose items-start gap-2 rounded-control border border-insufficient bg-insufficient-tint p-3 text-sm text-insufficient">
            <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            <span>
              {plural(left.length, "claim", "claims")} not reviewed yet ({left.join(", ")}).{" "}
              <Link
                href="/review"
                className={`inline-flex min-h-11 items-center rounded-control font-semibold underline underline-offset-4 ${focusRing}`}
              >
                Go to Review
              </Link>
            </span>
          </p>
        )}
        {exportError && (
          <p
            id={errorId}
            role="alert"
            className="mt-6 flex max-w-prose items-start gap-2 text-sm font-medium text-contradicted"
          >
            <CircleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            <span>
              {exportError}
              {exportError !== "Write a reason for the decision." && (
                <span className="mt-1 block font-normal text-ink-soft">
                  Nothing was exported. Check that the audit service is running, then try again.
                </span>
              )}
            </span>
          </p>
        )}

        <div className="mt-6 flex flex-wrap items-center gap-x-4 gap-y-3">
          <button
            type="submit"
            disabled={!choice || exporting}
            aria-describedby={!choice ? gateId : undefined}
            className={buttonPrimary}
          >
            {exporting && <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />}
            {exporting ? "Exporting…" : "Export"}
          </button>
          {!choice && (
            <p id={gateId} className="text-sm text-ink-soft">
              Export is available once the suggested decision has loaded.
            </p>
          )}
        </div>
      </form>

      {files && (
        <section
          aria-labelledby={`${id}-downloads`}
          className="rounded-panel border border-supported bg-supported-tint p-6 sm:p-8"
        >
          <h2 id={`${id}-downloads`} className={`${sectionTitle} flex items-center gap-2`}>
            <CircleCheck aria-hidden="true" className="size-5 text-supported" />
            Downloads
          </h2>
          <p className="mt-1 max-w-prose text-sm text-ink-soft">
            audit.json follows the shared findings format v0.2. The Decision Record lists who must sign off.
          </p>
          <div className="mt-4 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => download("audit.json", JSON.stringify(files.audit_json, null, 2), "application/json")}
              className={buttonSecondary}
            >
              <Download aria-hidden="true" className="size-4" />
              Download audit.json
            </button>
            <button
              type="button"
              onClick={() => download("decision_record.md", files.decision_record_md, "text/markdown")}
              className={buttonSecondary}
            >
              <Download aria-hidden="true" className="size-4" />
              Download decision_record.md
            </button>
          </div>
        </section>
      )}

      {recordedNow && reportText.trim() && (
        <section aria-labelledby={`${id}-after`}>
          <h2 id={`${id}-after`} className={sectionTitle}>
            The report after this decision
          </h2>
          <p className="mt-1 max-w-prose text-ink">
            <span className="font-semibold">{recordedNow.choice}.</span> {DECISION_HEADLINE[recordedNow.choice]}
          </p>
          <p className="mt-1 max-w-prose text-sm text-ink-soft">
            {actionSummary(audit.claims, recordedNow.choice)}. Each claim is marked with what this decision does to it and
            its final verdict. Click a marked sentence to open its evidence; you come back to the same place.
          </p>
          <div className="mt-6">
            <MarkedReport
              audit={audit}
              reportText={reportText}
              from="decision"
              decision={recordedNow.choice}
              label="The report after this decision"
            />
          </div>
        </section>
      )}
    </div>
  );
}
