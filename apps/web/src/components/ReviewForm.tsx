"use client";

import { Check, CircleAlert, CircleCheck, Circle, PencilLine } from "lucide-react";
import { useId, useState } from "react";
import SolidityExplained from "@/components/SolidityExplained";
import VerdictBadge from "@/components/VerdictBadge";
import { useAudit } from "@/lib/audit-context";
import { keyNumber, VERDICT_LABEL, VERDICTS } from "@/lib/review";
import { useRoles } from "@/lib/roles";
import type { ClaimResult, Verdict } from "@/lib/types";
import { buttonSecondary, fieldHint, fieldInput, fieldLabel } from "@/lib/ui";

type Choice = "accept" | "override";

const CHOICE_LABEL: Record<Choice, string> = { accept: "Accept the tool's verdict", override: "Override" };

/** One ledger entry: the tool's verdict and key number, and a person's Accept / Override with a reason. */
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
  const [noteOpen, setNoteOpen] = useState(Boolean(saved?.reason));

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
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;

  const reasonField = (
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
        aria-describedby={error ? errorId : undefined}
        className={`${fieldInput} mt-1 ${error ? "border-contradicted" : ""}`}
      />
      {error && (
        <p id={errorId} role="alert" className="mt-1.5 flex items-start gap-1.5 text-sm font-medium text-contradicted">
          <CircleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          {error}
        </p>
      )}
    </div>
  );

  const roleField = (
    <div>
      <label htmlFor={`${id}-role`} className={fieldLabel}>
        Reviewer role
      </label>
      <select
        id={`${id}-role`}
        value={reviewerRole}
        onChange={(e) => setReviewerRole(e.target.value)}
        className={`${fieldInput} mt-1`}
      >
        {roleNames.map((name) => (
          <option key={name} value={name}>
            {name}
          </option>
        ))}
      </select>
    </div>
  );

  return (
    <form onSubmit={save} aria-labelledby={titleId} className="p-5 sm:p-6" noValidate>
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <div className="flex flex-wrap items-center gap-3">
          <h2 id={titleId} className="num font-mono text-base font-semibold text-ink">
            {result.claim.id}
          </h2>
          <VerdictBadge verdict={result.verdict} />
        </div>
        <p role="status" className="text-sm">
          {saved && !dirty ? (
            <span className="inline-flex items-center gap-1.5 font-semibold text-supported">
              <CircleCheck aria-hidden="true" className="size-4" />
              Reviewed: {saved.decision === "accept" ? "accepted" : `overridden to ${VERDICT_LABEL[saved.final_verdict]}`}
            </span>
          ) : saved ? (
            <span className="inline-flex items-center gap-1.5 font-semibold text-insufficient">
              <PencilLine aria-hidden="true" className="size-4" />
              Unsaved changes
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 text-ink-soft">
              <Circle aria-hidden="true" className="size-4" />
              Not reviewed yet
            </span>
          )}
        </p>
      </div>

      <blockquote className="reported mt-3 max-w-prose text-ink">{result.claim.text}</blockquote>

      <dl className="mt-4 grid items-center gap-x-6 gap-y-2 text-sm sm:grid-cols-[max-content_1fr]">
        <dt className="font-semibold text-ink">Key number</dt>
        <dd className="num text-ink">{keyNumber(result)}</dd>
        <dt className="font-semibold text-ink">Solidity</dt>
        <dd>
          <SolidityExplained result={result} />
        </dd>
      </dl>

      <fieldset className="mt-5">
        <legend className={fieldLabel}>Your review</legend>
        <div className="mt-2 grid grid-cols-2 sm:inline-grid sm:grid-cols-[auto_auto]">
          {(["accept", "override"] as const).map((value) => {
            const selected = choice === value;
            return (
              <label key={value} className="relative flex cursor-pointer">
                <input
                  type="radio"
                  name={`${id}-choice`}
                  value={value}
                  checked={selected}
                  onChange={() => setChoice(value)}
                  className="peer sr-only"
                />
                <span
                  className={`flex min-h-11 w-full items-center justify-center gap-2 border px-4 py-2 text-center text-sm transition-colors duration-150 peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-pen ${
                    value === "accept" ? "rounded-l-control" : "-ml-px rounded-r-control"
                  } ${
                    selected
                      ? "border-pen bg-pen-tint font-semibold text-pen-deep"
                      : "border-rule-strong bg-sheet font-medium text-ink hover:bg-wash"
                  }`}
                >
                  {selected && <Check aria-hidden="true" className="size-4 shrink-0" strokeWidth={2.5} />}
                  {CHOICE_LABEL[value]}
                </span>
              </label>
            );
          })}
        </div>
      </fieldset>

      {choice === "override" ? (
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor={`${id}-verdict`} className={fieldLabel}>
              Your verdict
            </label>
            <select
              id={`${id}-verdict`}
              value={overrideTo}
              onChange={(e) => setOverrideTo(e.target.value as Verdict)}
              aria-describedby={hintId}
              className={`${fieldInput} mt-1`}
            >
              {otherVerdicts.map((v) => (
                <option key={v} value={v}>
                  {VERDICT_LABEL[v]}
                </option>
              ))}
            </select>
            <p id={hintId} className={fieldHint}>
              The tool&apos;s verdict is kept next to yours.
            </p>
          </div>
          {roleField}
          <div className="sm:col-span-2">{reasonField}</div>
        </div>
      ) : (
        <details
          className="mt-4"
          open={noteOpen || Boolean(error)}
          onToggle={(e) => setNoteOpen(e.currentTarget.open)}
        >
          <summary className="inline-flex min-h-11 cursor-pointer list-none items-center gap-1.5 rounded-control text-sm font-medium text-pen underline-offset-4 hover:underline [&::-webkit-details-marker]:hidden">
            <PencilLine aria-hidden="true" className="size-4" />
            Add a note or change the reviewer role
          </summary>
          <div className="mt-2 grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">{reasonField}</div>
            {roleField}
          </div>
        </details>
      )}

      <div className="mt-5">
        <button type="submit" disabled={!dirty} className={buttonSecondary}>
          {saved ? "Update review" : "Save review"}
        </button>
      </div>
    </form>
  );
}
