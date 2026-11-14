import type { LadderSegment } from "@/lib/types";

/**
 * The Claim Ladder: the report's sentence with over-strong words struck through (<del>) and the honest
 * replacement written in (<ins>). Redline styling comes from globals.css; screen readers get the markup in words.
 */
export default function LadderText({ segments, inline = false }: { segments: LadderSegment[]; inline?: boolean }) {
  // Inline, it sits inside a sentence of the report (the report shown after the decision), so no paragraph of its own.
  const Tag = inline ? "span" : "p";
  return (
    <Tag className={inline ? undefined : "reported text-ink"}>
      {segments.map((s, i) =>
        s.struck ? (
          <del key={i}>
            <span className="sr-only">[removed: </span>
            {s.text}
            <span className="sr-only">]</span>
          </del>
        ) : s.inserted ? (
          <ins key={i} className="mx-0.5">
            <span className="sr-only">[added: </span>
            {s.text}
            <span className="sr-only">]</span>
          </ins>
        ) : (
          <span key={i}>{s.text}</span>
        ),
      )}
    </Tag>
  );
}

/** True when the ladder actually changes the sentence. */
export function ladderChanges(segments: LadderSegment[]): boolean {
  return segments.some((s) => s.struck || s.inserted);
}
