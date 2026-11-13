"use client";

import { Check, CircleAlert, LoaderCircle } from "lucide-react";
import { useId } from "react";
import { describeParams, TYPE_LABEL } from "@/lib/claim-format";
import { AiFoundStamp } from "./AiStamp";
import type { Claim, SentenceInfo } from "@/lib/types";

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
  const aiFound = claim?.source === "ai";
  const noCheck = !aiFound && (claim?.type === "UNMAPPED" || claim?.type === "NOT_ANSWERABLE");

  return (
    <li
      className={`flex items-start gap-1 border-l-[3px] py-3 pr-2 sm:gap-2 ${
        checked ? "border-l-pen" : "border-l-transparent"
      }`}
    >
      <span className="relative flex size-11 shrink-0 items-center justify-center">
        <input
          id={boxId}
          type="checkbox"
          checked={checked}
          onChange={onToggle}
          disabled={disabled}
          aria-describedby={claim ? detailId : undefined}
          className="peer absolute inset-0 size-11 cursor-pointer opacity-0 disabled:cursor-not-allowed"
        />
        <span
          aria-hidden="true"
          className={`flex size-6 items-center justify-center rounded-stamp border-2 transition-colors duration-150 peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-pen peer-disabled:opacity-60 ${
            checked ? "border-pen bg-pen text-white" : "border-rule-strong bg-sheet text-transparent"
          }`}
        >
          <Check className="size-4" strokeWidth={3} />
        </span>
      </span>
      <div className="min-w-0 flex-1 pt-1">
        <label
          htmlFor={boxId}
          className={`reported block cursor-pointer ${checked ? "text-ink" : "text-ink-soft"} ${
            disabled ? "cursor-not-allowed" : ""
          }`}
        >
          {sentence.text}
        </label>
        {busy && (
          <p role="status" className="mt-1 flex items-center gap-2 text-sm text-ink-soft">
            <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
            Reading this sentence…
          </p>
        )}
        {claim && !busy && (
          <div id={detailId} className="mt-1 text-sm">
            <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <span className="font-mono text-xs font-medium text-ink-soft">{claim.id}</span>
              <span className="rounded-stamp border border-pen/40 bg-pen-tint px-2 py-0.5 font-medium text-pen-deep">
                <span className="sr-only">Claim type: </span>
                {aiFound ? "No rule-based check yet" : TYPE_LABEL[claim.type]}
              </span>
              {aiFound && <AiFoundStamp />}
            </p>
            {noCheck ? (
              <p className="mt-1.5 flex items-start gap-2 text-insufficient">
                <CircleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
                <span>{describeParams(claim)}</span>
              </p>
            ) : (
              <p className="mt-1.5 text-ink-soft">{describeParams(claim)}</p>
            )}
          </div>
        )}
      </div>
    </li>
  );
}
