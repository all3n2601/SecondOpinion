"use client";

import { BotOff, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { getAiStatus } from "@/lib/api";
import type { AiStatus } from "@/lib/types";

const OFF_HINT = "Rules only. Set SO_AI_API_KEY to turn on the AI helper.";

/**
 * Quiet chip: is the optional AI helper switched on? It says so in words, never by colour alone.
 * The helper only proposes check plans; our code runs them and sets every verdict (see the evidence panel).
 */
export default function AiStatusChip({ showHint = true }: { showHint?: boolean }) {
  const [status, setStatus] = useState<AiStatus | null>(null);

  useEffect(() => {
    let live = true;
    getAiStatus().then((next) => {
      if (live) setStatus(next);
    });
    return () => {
      live = false;
    };
  }, []);

  if (status === null) {
    return (
      <p role="status" className="text-sm text-ink-soft">
        Checking the AI helper…
      </p>
    );
  }

  const Icon = status.enabled ? Sparkles : BotOff;
  const title = status.enabled
    ? `The AI helper reads sentences the rules cannot handle and proposes a check plan. Our code runs the plan and sets the verdict.${status.host ? ` Host: ${status.host}.` : ""}`
    : (status.reason ?? OFF_HINT);

  return (
    <div role="status" className="max-w-[36ch] text-sm text-ink-soft sm:text-right">
      <span
        title={title}
        className="inline-flex items-center gap-1.5 rounded-stamp border border-rule-strong bg-sheet px-2.5 py-1 font-medium text-ink"
      >
        <Icon aria-hidden="true" className="size-4 shrink-0" />
        {status.enabled ? `AI helper on${status.model ? `: ${status.model}` : ""}` : "AI helper off"}
      </span>
      {!status.enabled && showHint && <p className="mt-1.5">{OFF_HINT}</p>}
      {!status.enabled && status.reason && <span className="sr-only">{status.reason}</span>}
    </div>
  );
}
