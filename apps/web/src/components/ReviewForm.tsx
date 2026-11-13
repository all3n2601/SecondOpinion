"use client";

import { useId, useState } from "react";
import { useAudit } from "@/lib/audit-context";
import { keyNumber, SOLIDITY_LABEL, VERDICT_LABEL, VERDICTS } from "@/lib/review";
import { useRoles } from "@/lib/roles";
import type { ClaimResult, Verdict } from "@/lib/types";
import { buttonPrimary, eyebrow, fieldInput, fieldLabel, focusRing, panel } from "@/lib/ui";
import StatementLabel from "./StatementLabel";
import VerdictBadge from "./VerdictBadge";

type Choice = "accept" | "override";

const OPTION = `flex cursor-pointer items-start gap-3 rounded-md border border-slate-300 bg-white p-3 text-sm hover:border-slate-400 has-[:checked]:border-emerald-800 has-[:checked]:bg-emerald-50 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-emerald-800`;

/** One claim: the tool's verdict and key number, and a person's Accept / Override with a reason. */
export default function ReviewForm({ result }: { result: ClaimResult }) {
  const id = useId();
  const { setReview, role } = useAudit();
  const { roles } = useRoles();
  const saved = result.review;

  const [choice, setChoice] = useState<Choice>(saved?.decision ?? "accept");
  const otherVerdicts = VERDICTS.filter((v) => v !== result.verdict);
  const [overrideTo, setOverrideTo] = useState<Verdict>(
    saved?.decision === "override" ? saved.final_verdict : otherVerdicts[0],
  );
  const [reason, setReason] = useState(saved?.reason ?? "");
  const [reviewerRole, setReviewerRole] = useState(saved?.reviewer_role ?? role);
  const [error, setError] = useState<string | null>(null);

  const draft = {
    decision: choice,
    final_verdict: choice === "accept" ? result.verdict : overrideTo,
    reason: reason.trim(),
    reviewer_role: reviewerRole,
  };
  const dirty =
    !saved ||
    saved.decision !== draft.decision ||
    saved.final_verdict !== draft.final_verdict ||
    saved.reason !== draft.reason ||
    saved.reviewer_role !== draft.reviewer_role;

  function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (choice === "override" && !draft.reason) {
      setError("An override needs a reason.");
      return;
    }
    setError(null);
    setReview(result.claim.id, draft);
  }

  const roleNames = roles?.map((r) => r.name) ?? [];
  if (!roleNames.includes(reviewerRole)) roleNames.unshift(reviewerRole);
  const titleId = `${id}-title`;
  const reviewed = saved && !dirty;

  return (
    <form
      onSubmit={save}
      aria-labelledby={titleId}
      className={`${panel} relative overflow-hidden before:absolute before:inset-y-0 before:left-0 before:w-1 ${
        reviewed ? "before:bg-emerald-700" : saved ? "before:bg-amber-500" : "before:bg-slate-300"
      }`}
      noValidate
    >
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-slate-50/70 px-5 py-3">
        <div className="flex flex-wrap items-center gap-2.5">
          <h2 id={titleId} className="font-mono text-sm font-bold text-slate-900">
            {result.claim.id}
          </h2>
          <VerdictBadge verdict={result.verdict} />
        </div>
        <p role="status" className="text-xs font-semibold">
          {reviewed ? (
            <span className="text-emerald-900">
              ✓ Reviewed: {saved.decision === "accept" ? "accepted" : `overridden to ${VERDICT_LABEL[saved.final_verdict]}`}
            </span>
          ) : saved ? (
            <span className="text-amber-900">● Unsaved changes</span>
          ) : (
            <span className="text-slate-500">○ Not reviewed yet</span>
          )}
        </p>
      </header>

      <div className="grid gap-6 p-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:gap-8">
        <div>
          <p className={eyebrow}>Tool result</p>
          <blockquote className="mt-2 flex flex-wrap items-baseline gap-2 text-[0.95rem] leading-7 text-slate-900">
            <StatementLabel kind="Reported" />
            {result.claim.text}
          </blockquote>
          <dl className="mt-4 divide-y divide-slate-100 rounded-md border border-slate-200 text-sm">
            <div className="grid grid-cols-[7rem_minmax(0,1fr)] gap-3 px-3 py-2">
              <dt className="font-medium text-slate-600">Tool verdict</dt>
              <dd>{VERDICT_LABEL[result.verdict]}</dd>
            </div>
            <div className="grid grid-cols-[7rem_minmax(0,1fr)] gap-3 px-3 py-2">
              <dt className="font-medium text-slate-600">Key number</dt>
              <dd className="font-semibold tabular-nums">{keyNumber(result)}</dd>
            </div>
            <div className="grid grid-cols-[7rem_minmax(0,1fr)] gap-3 px-3 py-2">
              <dt className="font-medium text-slate-600">Solidity</dt>
              <dd>{SOLIDITY_LABEL[result.solidity]}</dd>
            </div>
          </dl>
        </div>

        <div className="space-y-4">
          <fieldset>
            <legend className={eyebrow}>Your review</legend>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {(["accept", "override"] as const).map((value) => (
                <label key={value} className={OPTION}>
                  <input
                    type="radio"
                    name={`${id}-choice`}
                    value={value}
                    checked={choice === value}
                    onChange={() => setChoice(value)}
                    className="mt-0.5 size-4 accent-emerald-900 focus-visible:outline-none"
                  />
                  <span>
                    <span className="block font-semibold text-slate-900">
                      {value === "accept" ? "Accept the tool's verdict" : "Override"}
                    </span>
                    <span className="block text-xs text-slate-600">
                      {value === "accept" ? "The verdict stands as computed." : "Record a different verdict, with a reason."}
                    </span>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>

          {choice === "override" && (
            <div>
              <label htmlFor={`${id}-verdict`} className={fieldLabel}>
                Your verdict
              </label>
              <select
                id={`${id}-verdict`}
                value={overrideTo}
                onChange={(e) => setOverrideTo(e.target.value as Verdict)}
                className={`${fieldInput} mt-1.5`}
              >
                {otherVerdicts.map((v) => (
                  <option key={v} value={v}>
                    {VERDICT_LABEL[v]}
                  </option>
                ))}
              </select>
              <p className="mt-1 text-xs text-slate-600">The tool&apos;s verdict is kept next to yours.</p>
            </div>
          )}

          <div>
            <label htmlFor={`${id}-reason`} className={fieldLabel}>
              Reason {choice === "override" ? "(required)" : "(optional)"}
            </label>
            <textarea
              id={`${id}-reason`}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={2}
              required={choice === "override"}
              aria-invalid={error ? true : undefined}
              aria-describedby={error ? `${id}-error` : undefined}
              className={`${fieldInput} mt-1.5 h-auto py-2 ${error ? "border-red-700" : ""}`}
            />
            {error && (
              <p id={`${id}-error`} role="alert" className="mt-1.5 text-sm font-medium text-red-800">
                {error}
              </p>
            )}
          </div>

          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <label htmlFor={`${id}-role`} className={fieldLabel}>
                Reviewer role
              </label>
              <select
                id={`${id}-role`}
                value={reviewerRole}
                onChange={(e) => setReviewerRole(e.target.value)}
                className={`${fieldInput} mt-1.5 w-auto min-w-[12rem]`}
              >
                {roleNames.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </div>
            <button type="submit" disabled={!dirty} className={`${buttonPrimary} ${focusRing}`}>
              {saved ? "Update review" : "Save review"}
            </button>
          </div>
        </div>
      </div>
    </form>
  );
}
