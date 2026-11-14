"use client";

import { Pause, Play, RotateCcw } from "lucide-react";
import { useState } from "react";
import { focusRing } from "@/lib/ui";
import CohortCanvas from "./CohortCanvas";
import { STAGES } from "./cohort";
import { LAST } from "./useDemoStage";

/**
 * The hero's counting figure: the release's samples, counted down to the denominator of the practice
 * report's Luminal A claim. It follows the stage handed to it (the hero's shared clock), so the report's sentence
 * beside it stays in step; the stage list is the text version and lets you step through it by hand.
 */
export default function CohortFigure({
  stage,
  calm,
  autoplay,
  onChoose,
  onToggle,
}: {
  stage: number;
  calm: boolean;
  autoplay: boolean;
  onChoose: (index: number) => void;
  onToggle: () => void;
}) {
  const [webgl, setWebgl] = useState(true);

  const ControlIcon = autoplay ? Pause : stage >= LAST ? RotateCcw : Play;
  const controlLabel = autoplay ? "Pause" : stage >= LAST ? "Play again" : "Play";

  return (
    <figure className="rounded-panel border border-rule bg-sheet">
      {webgl && (
        <div className="aspect-[5/4] w-full px-4 pt-4 sm:px-5 sm:pt-5">
          <CohortCanvas stage={stage} instant={calm} onUnsupported={() => setWebgl(false)} />
        </div>
      )}

      <div className="border-t border-rule px-4 py-4 sm:px-5">
        <ol aria-label="From the release to the claim’s denominator" className="space-y-0.5">
          {STAGES.map((s, i) => {
            const current = i === stage;
            return (
              <li key={s.figure}>
                <button
                  type="button"
                  onClick={() => onChoose(i)}
                  aria-current={current ? "step" : undefined}
                  className={`grid min-h-11 w-full cursor-pointer grid-cols-[4.25rem_minmax(0,1fr)] items-baseline gap-3 rounded-control border-l-2 py-1.5 pr-2 pl-3 text-left text-[0.9375rem] transition-colors duration-150 ${
                    current ? "border-pen bg-pen-tint text-ink" : "border-transparent text-ink-soft hover:bg-wash hover:text-ink"
                  } ${focusRing}`}
                >
                  <span
                    className={`num text-right font-mono font-medium ${
                      s.showClaim ? "text-contradicted" : current ? "text-pen" : ""
                    }`}
                  >
                    {s.figure}
                  </span>
                  <span>{s.label}</span>
                </button>
              </li>
            );
          })}
        </ol>

        <div className="mt-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
          <figcaption className="max-w-[44ch] text-sm text-ink-soft">
            Each dot is one sample in release A of TCGA-BRCA, the practice data.
          </figcaption>
          {!calm && (
            <button
              type="button"
              onClick={onToggle}
              className={`inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-control px-3 text-sm font-medium text-pen transition-colors duration-150 hover:bg-pen-tint ${focusRing}`}
            >
              <ControlIcon aria-hidden="true" size={16} strokeWidth={1.75} />
              {controlLabel}
            </button>
          )}
        </div>
      </div>
    </figure>
  );
}
