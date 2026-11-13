"use client";

import { useId } from "react";
import { describeParams, TYPE_LABEL } from "@/lib/claim-format";
import type { Claim, SentenceInfo } from "@/lib/types";
import { focusRing } from "@/lib/ui";

interface Props {
  sentence: SentenceInfo;
  claim: Claim | undefined;
  disabled: boolean;
  busy: boolean;
  onToggle: () => void;
}

/** One sentence of the report: ticked = checked as a claim, with its type and what we read from it. */
export default function ClaimRow({ sentence, claim, disabled, busy, onToggle }: Props) {
  const boxId = useId();
  const detailId = useId();
  const checked = Boolean(claim);

  return (
    <li
      className={`flex gap-3 rounded-xl border p-4 ${
        checked ? "border-emerald-900/30 bg-white" : "border-slate-200 bg-slate-50"
      }`}
    >
      <input
        id={boxId}
        type="checkbox"
        checked={checked}
        onChange={onToggle}
        disabled={disabled}
        aria-describedby={claim ? detailId : undefined}
        className={`mt-1 size-5 shrink-0 accent-emerald-900 ${focusRing}`}
      />
      <div className="min-w-0 flex-1">
        <label htmlFor={boxId} className={checked ? "text-slate-900" : "text-slate-600"}>
          {claim && <span className="mr-2 font-mono text-sm font-semibold text-emerald-900">{claim.id}</span>}
          {sentence.text}
        </label>
        {busy && <p className="mt-2 text-sm text-slate-600">Reading this sentence…</p>}
        {claim && !busy && (
          <p id={detailId} className="mt-2 flex flex-wrap items-center gap-2 text-sm">
            <span className="rounded-full border border-emerald-900/30 bg-emerald-50 px-2.5 py-0.5 font-medium text-emerald-950">
              <span className="sr-only">Claim type: </span>
              {TYPE_LABEL[claim.type]}
            </span>
            <span className="text-slate-700">{describeParams(claim)}</span>
          </p>
        )}
      </div>
    </li>
  );
}
