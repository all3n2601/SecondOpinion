import { LayoutList } from "lucide-react";
import { finalVerdict, formatCount, VERDICT_LABEL, VERDICTS } from "@/lib/review";
import { OVERVIEW, reviewStatus, type Entry } from "@/lib/review-nav";
import type { ClaimResult, Verdict } from "@/lib/types";
import { focusRing } from "@/lib/ui";

const FILL: Record<Verdict, string> = {
  supported: "bg-supported",
  contradicted: "bg-contradicted",
  insufficient_evidence: "bg-insufficient",
};
const STATUS_INK = { "to review": "text-ink-soft", accepted: "text-supported" } as Record<string, string>;

/** Final verdicts as one stacked bar, with the counts written under it. */
export function VerdictStack({ claims }: { claims: ClaimResult[] }) {
  const counts = VERDICTS.map((v) => ({ v, n: claims.filter((c) => finalVerdict(c) === v).length })).filter((c) => c.n > 0);
  if (!claims.length) return null;
  return (
    <div>
      <div aria-hidden="true" className="flex h-2.5 overflow-hidden rounded-stamp">
        {counts.map(({ v, n }) => (
          <span key={v} className={FILL[v]} style={{ width: `${(n / claims.length) * 100}%` }} />
        ))}
      </div>
      <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-ink-soft">
        {counts.map(({ v, n }) => (
          <li key={v} className="flex items-center gap-1.5">
            <span aria-hidden="true" className={`size-2.5 rounded-full ${FILL[v]}`} />
            <span className="num font-mono text-ink">{formatCount(n)}</span> {VERDICT_LABEL[v].toLowerCase()}
          </li>
        ))}
      </ul>
    </div>
  );
}

const ITEM = `grid w-full min-h-11 cursor-pointer grid-cols-[1rem_minmax(0,1fr)] gap-x-2.5 px-3 py-2.5 text-left text-sm transition-colors duration-150 hover:bg-wash ${focusRing}`;
const SELECTED = "bg-sheet shadow-[inset_3px_0_0_var(--color-pen)]";

/** Overview, then one line per claim: verdict, review status and the start of its sentence. */
export default function ReviewList({ claims, selected, onSelect }: {
  claims: ClaimResult[];
  selected: Entry;
  onSelect: (entry: Entry) => void;
}) {
  return (
    <nav aria-label="Claims to review">
      <ol className="divide-y divide-rule border-y border-rule">
        <li>
          <button
            type="button"
            aria-current={selected === OVERVIEW ? "true" : undefined}
            onClick={() => onSelect(OVERVIEW)}
            className={`${ITEM} items-center ${selected === OVERVIEW ? SELECTED : ""}`}
          >
            <LayoutList aria-hidden="true" className="size-4 text-ink-soft" />
            <span className="font-semibold text-ink">Overview</span>
          </button>
        </li>
        {claims.map((c) => {
          const final = finalVerdict(c);
          const status = reviewStatus(c);
          const isSelected = selected === c.claim.id;
          return (
            <li key={c.claim.id}>
              <button
                type="button"
                aria-current={isSelected ? "true" : undefined}
                onClick={() => onSelect(c.claim.id)}
                className={`${ITEM} ${isSelected ? SELECTED : ""}`}
              >
                <span aria-hidden="true" className={`mt-1 size-3 rounded-full ${FILL[final]}`} />
                <span className="min-w-0">
                  <span className="flex flex-wrap items-baseline gap-x-1.5">
                    <span className="num font-mono font-semibold text-ink">{c.claim.id}</span>
                    <span className="text-ink">{VERDICT_LABEL[final]}</span>
                    <span aria-hidden="true" className="text-ink-faint">
                      ·
                    </span>
                    <span className={STATUS_INK[status] ?? "text-insufficient"}>{status}</span>
                  </span>
                  <span className="mt-0.5 block truncate text-ink-soft">{c.claim.text}</span>
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
