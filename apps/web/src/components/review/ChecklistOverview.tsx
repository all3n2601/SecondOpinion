import { Circle, CircleCheck } from "lucide-react";
import { Counts } from "@/components/review/sections";
import type { ClaimResult } from "@/lib/types";
import { focusRing } from "@/lib/ui";

/** The anchor each claim row carries on the Review page, so the checklist can jump to it. */
export function claimAnchor(id: string): string {
  return `review-${id}`;
}

/** Data-use reviewer view: counts by verdict, then every claim as a tick box that jumps to its row. */
export default function ChecklistOverview({ claims, headline, caption }: {
  claims: ClaimResult[];
  headline: string;
  caption: string;
}) {
  return (
    <>
      <p className="mt-2 max-w-prose text-lg font-semibold leading-snug text-ink">{headline}</p>
      {claims.length > 0 && (
        <>
          <div className="mt-4">
            <Counts claims={claims} />
          </div>
          <h3 className="mt-5 text-sm font-semibold text-ink">Go to a claim</h3>
          <ol className="mt-2 flex flex-wrap gap-2">
            {claims.map((c) => {
              const done = c.review !== null;
              return (
                <li key={c.claim.id}>
                  <a
                    href={`#${claimAnchor(c.claim.id)}`}
                    className={`inline-flex min-h-11 items-center gap-1.5 rounded-control border px-3 text-sm transition-colors duration-150 hover:bg-wash ${
                      done ? "border-supported text-ink" : "border-rule-strong text-ink-soft"
                    } ${focusRing}`}
                  >
                    {done ? (
                      <CircleCheck aria-hidden="true" className="size-4 shrink-0 text-supported" strokeWidth={2.25} />
                    ) : (
                      <Circle aria-hidden="true" className="size-4 shrink-0" />
                    )}
                    <span className="num font-mono font-semibold">{c.claim.id}</span>
                    <span className="sr-only">{done ? "reviewed" : "not reviewed yet"}</span>
                  </a>
                </li>
              );
            })}
          </ol>
        </>
      )}
      <p className="mt-4 max-w-prose text-sm text-ink-soft">{caption}</p>
    </>
  );
}
