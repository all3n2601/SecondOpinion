"use client";

import { useId } from "react";
import { describeParams, TYPE_LABEL } from "@/lib/claim-format";
import type { Claim, SentenceInfo } from "@/lib/types";
import { chip, focusRing } from "@/lib/ui";

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
    <li className={`grid grid-cols-[1.25rem_3rem_minmax(0,1fr)] gap-x-3 px-5 py-4 ${checked ? "bg-white" : "bg-slate-50/60"}`}>
      <input
        id={boxId}
        type="checkbox"
        checked={checked}
        onChange={onToggle}
        disabled={disabled}
        aria-describedby={claim ? detailId : undefined}
        className={`mt-0.5 size-[1.125rem] accent-emerald-900 ${focusRing}`}
      />
      <span className={`pt-px font-mono text-xs font-semibold ${claim ? "text-emerald-900" : "text-slate-400"}`}>
        {claim ? claim.id : `S${sentence.index + 1}`}
      </span>
      <div className="min-w-0">
        <label htmlFor={boxId} className={`text-[0.95rem] leading-6 ${checked ? "text-slate-900" : "text-slate-500"}`}>
          {sentence.text}
        </label>
        {busy && <p className="mt-1.5 text-sm text-slate-600">Reading this sentence…</p>}
        {claim && !busy && (
          <p id={detailId} className="mt-2 flex flex-wrap items-center gap-2 text-sm">
            <span className={`${chip} border-slate-300 bg-slate-50 text-slate-700`}>
              <span className="sr-only">Claim type: </span>
              {TYPE_LABEL[claim.type]}
            </span>
            <span className="text-slate-600">{describeParams(claim)}</span>
          </p>
        )}
      </div>
    </li>
  );
}
