import { Check, Circle, CircleX, LoaderCircle } from "lucide-react";
import type { ReactNode } from "react";

export type StepState = "waiting" | "running" | "done" | "failed";

export interface PipelineStep {
  id: string;
  title: string;
  /** What the step does, in the user's words. */
  does: string;
  state: StepState;
  /** What it found, once done (real counts from the result). */
  result?: ReactNode;
  /** Wall-clock time of the request that ran it, when it ran in this visit. */
  ms?: number;
}

const MARKER: Record<StepState, string> = {
  waiting: "border-rule-strong bg-sheet text-ink-faint",
  running: "border-pen bg-sheet text-pen",
  done: "border-pen bg-pen text-white",
  failed: "border-contradicted bg-contradicted-tint text-contradicted",
};

const STATE_WORD: Record<StepState, string> = {
  waiting: "Not run yet",
  running: "Running",
  done: "Done",
  failed: "Stopped",
};

export function seconds(ms: number): string {
  return ms < 1000 ? `${Math.max(ms, 1).toFixed(0)} ms` : `${(ms / 1000).toFixed(1)} s`;
}

function Marker({ state }: { state: StepState }) {
  const Icon = state === "done" ? Check : state === "failed" ? CircleX : state === "running" ? LoaderCircle : Circle;
  return (
    <span
      aria-hidden="true"
      className={`relative z-10 grid size-8 shrink-0 place-items-center rounded-full border-2 transition-colors duration-200 ${MARKER[state]}`}
    >
      <Icon
        className={`${state === "waiting" ? "size-2.5 fill-current" : "size-4"} ${state === "running" ? "motion-safe:animate-spin" : ""}`}
        strokeWidth={state === "waiting" ? 0 : 2.5}
      />
    </span>
  );
}

function Row({ step, last }: { step: PipelineStep; last: boolean }) {
  return (
    <li className="relative grid grid-cols-[2rem_minmax(0,1fr)] gap-x-4 pb-6 last:pb-0">
      {!last && (
        <span
          aria-hidden="true"
          className={`absolute top-8 bottom-0 left-4 w-px -translate-x-1/2 ${step.state === "done" ? "bg-pen" : "bg-rule"}`}
        />
      )}
      <Marker state={step.state} />
      <div className="min-w-0 pt-0.5">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4">
          <h3 className="font-semibold text-ink">
            {step.title}
            <span className="sr-only">: {STATE_WORD[step.state]}</span>
          </h3>
          {step.ms !== undefined && step.state === "done" && (
            <span className="num font-mono text-xs text-ink-faint">{seconds(step.ms)}</span>
          )}
        </div>
        <p className="mt-0.5 max-w-[60ch] text-[0.9375rem] text-ink-soft">{step.does}</p>
        {step.result && <div className="mt-2 text-[0.9375rem] text-ink">{step.result}</div>}
      </div>
    </li>
  );
}

/**
 * The audit as a vertical sequence. `grouped` steps ran in one request, so they are drawn inside one bracket
 * with a note saying so, instead of pretending to report progress the API does not send.
 */
export default function PipelineSteps({
  before,
  grouped,
  groupNote,
  after,
}: {
  before: PipelineStep[];
  grouped: PipelineStep[];
  groupNote: string;
  after: PipelineStep[];
}) {
  return (
    <ol aria-label="Audit steps for this report" className="relative">
      {before.map((step) => (
        <Row key={step.id} step={step} last={false} />
      ))}
      <li className="relative pb-6">
        <span aria-hidden="true" className="absolute top-0 bottom-0 left-4 w-px -translate-x-1/2 bg-rule" />
        <div className="relative -ml-2 rounded-panel border border-dashed border-rule-strong bg-paper/60 py-3 pr-3 pl-2 sm:pr-4">
          <p className="mb-3 pl-12 text-sm text-ink-faint">{groupNote}</p>
          <ol className="relative">
            {grouped.map((step, i) => (
              <Row key={step.id} step={step} last={i === grouped.length - 1} />
            ))}
          </ol>
        </div>
      </li>
      {after.map((step, i) => (
        <Row key={step.id} step={step} last={i === after.length - 1} />
      ))}
    </ol>
  );
}
