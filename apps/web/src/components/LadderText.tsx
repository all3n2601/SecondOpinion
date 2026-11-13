import type { LadderSegment } from "@/lib/types";

/** The Claim Ladder: over-strong words struck through, the honest replacement in bold. */
export default function LadderText({ segments }: { segments: LadderSegment[] }) {
  return (
    <p className="leading-7">
      {segments.map((s, i) =>
        s.struck ? (
          <del key={i} className="text-red-900 decoration-red-800 decoration-2">
            <span className="sr-only">[removed: </span>
            {s.text}
            <span className="sr-only">]</span>
          </del>
        ) : s.inserted ? (
          <ins key={i} className="mx-0.5 rounded bg-emerald-50 px-1 font-semibold text-emerald-950 no-underline">
            <span className="sr-only">[added: </span>
            {s.text}
            <span className="sr-only">]</span>
          </ins>
        ) : (
          <span key={i}>{s.text}</span>
        ),
      )}
    </p>
  );
}

/** True when the ladder actually changes the sentence. */
export function ladderChanges(segments: LadderSegment[]): boolean {
  return segments.some((s) => s.struck || s.inserted);
}
