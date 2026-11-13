"use client";

import { useId, useState } from "react";
import { useAudit } from "@/lib/audit-context";
import { keyNumber, SOLIDITY_LABEL, VERDICT_LABEL, VERDICT_STYLE, VERDICTS } from "@/lib/review";
import { useRoles } from "@/lib/roles";
import type { ClaimResult, Verdict } from "@/lib/types";

const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-900";

type Choice = "accept" | "override";

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

  return (
    <form
      onSubmit={save}
      aria-labelledby={titleId}
      className="rounded-xl border border-emerald-900/15 bg-white p-6"
      noValidate
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h2 id={titleId} className="text-lg font-semibold">
          {result.claim.id}
        </h2>
        <p role="status" className="text-sm">
          {saved && !dirty ? (
            <span className="font-medium text-emerald-900">
              ✓ Reviewed: {saved.decision === "accept" ? "accepted" : `overridden to ${VERDICT_LABEL[saved.final_verdict]}`}
            </span>
          ) : saved ? (
            <span className="text-amber-900">Unsaved changes</span>
          ) : (
            <span className="text-slate-600">Not reviewed yet</span>
          )}
        </p>
      </div>
      <blockquote className="mt-2 border-l-4 border-slate-300 pl-3 text-slate-800">{result.claim.text}</blockquote>

      <dl className="mt-4 grid gap-x-4 gap-y-1 text-sm sm:grid-cols-[max-content_1fr]">
        <dt className="font-medium">Tool verdict</dt>
        <dd>
          <span className={`inline-block rounded border px-2 py-0.5 font-medium ${VERDICT_STYLE[result.verdict]}`}>
            {VERDICT_LABEL[result.verdict]}
          </span>
        </dd>
        <dt className="font-medium">Key number</dt>
        <dd>{keyNumber(result)}</dd>
        <dt className="font-medium">Solidity</dt>
        <dd>{SOLIDITY_LABEL[result.solidity]}</dd>
      </dl>

      <fieldset className="mt-4">
        <legend className="text-sm font-medium">Your review</legend>
        <div className="mt-2 flex flex-wrap gap-4 text-sm">
          {(["accept", "override"] as const).map((value) => (
            <label key={value} className="flex items-center gap-2">
              <input
                type="radio"
                name={`${id}-choice`}
                value={value}
                checked={choice === value}
                onChange={() => setChoice(value)}
                className={FOCUS}
              />
              {value === "accept" ? "Accept the tool's verdict" : "Override"}
            </label>
          ))}
        </div>
      </fieldset>

      {choice === "override" && (
        <div className="mt-3">
          <label htmlFor={`${id}-verdict`} className="block text-sm font-medium">
            Your verdict
          </label>
          <select
            id={`${id}-verdict`}
            value={overrideTo}
            onChange={(e) => setOverrideTo(e.target.value as Verdict)}
            className={`mt-1 rounded-md border border-slate-400 bg-white px-3 py-2 text-sm ${FOCUS}`}
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

      <div className="mt-3">
        <label htmlFor={`${id}-reason`} className="block text-sm font-medium">
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
          className={`mt-1 w-full rounded-md border border-slate-400 px-3 py-2 text-sm ${FOCUS}`}
        />
      </div>

      <div className="mt-3">
        <label htmlFor={`${id}-role`} className="block text-sm font-medium">
          Reviewer role
        </label>
        <select
          id={`${id}-role`}
          value={reviewerRole}
          onChange={(e) => setReviewerRole(e.target.value)}
          className={`mt-1 rounded-md border border-slate-400 bg-white px-3 py-2 text-sm ${FOCUS}`}
        >
          {roleNames.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
      </div>

      {error && (
        <p id={`${id}-error`} role="alert" className="mt-3 text-sm font-medium text-rose-800">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={!dirty}
        className={`mt-4 rounded-md bg-emerald-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 ${FOCUS}`}
      >
        {saved ? "Update review" : "Save review"}
      </button>
    </form>
  );
}
