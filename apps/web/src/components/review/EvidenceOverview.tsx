import VerdictBadge from "@/components/VerdictBadge";
import { variantWords, VERDICT_LABEL } from "@/lib/claim-format";
import { finalVerdict, formatCount } from "@/lib/review";
import type { ClaimResult } from "@/lib/types";

/** Above this many ways of counting, one continuous bar reads better than a cell per way. */
const MAX_CELLS = 12;

/** "n of m ways of counting agree" as a bar: one cell per way, filled when that way gives the tool's verdict. */
function AgreementBar({ result }: { result: ClaimResult }) {
  const { variants, verdict } = result;
  if (variants.length === 0) return <span className="text-sm text-ink-soft">Only one way to count it</span>;
  const agree = variants.filter((v) => v.verdict === verdict).length;
  const label = `${formatCount(agree)} of ${formatCount(variants.length)} ways of counting agree`;
  return (
    <span className="flex items-center gap-3">
      <span role="img" aria-label={label} className="flex h-3 w-full max-w-48 gap-0.5 overflow-hidden rounded-stamp bg-wash">
        {variants.length <= MAX_CELLS ? (
          variants.map((v) => (
            <span
              key={v.variant_id}
              title={`${variantWords(v.variant_id)}: ${v.verdict ? VERDICT_LABEL[v.verdict] : "no verdict"}`}
              className={`flex-1 ${v.verdict === verdict ? "bg-pen" : "bg-rule-strong"}`}
            />
          ))
        ) : (
          <span className="bg-pen" style={{ width: `${(agree / variants.length) * 100}%` }} />
        )}
      </span>
      <span aria-hidden="true" className="num shrink-0 font-mono text-sm text-ink">
        {formatCount(agree)} of {formatCount(variants.length)}
      </span>
    </span>
  );
}

function SkepticShort({ result }: { result: ClaimResult }) {
  const s = result.skeptic;
  if (!s) return <span className="text-ink-soft">Do not apply</span>;
  return (
    <span className="grid text-ink">
      <span className="num font-mono">p = {s.shuffle_p ?? "unknown"}</span>
      <span className="text-ink-soft">
        {s.site_flips.length
          ? `Flips leaving out ${s.site_flips.join(", ")}`
          : `Holds leaving out any of ${formatCount(s.n_sites)} sites`}
      </span>
    </span>
  );
}

const CELL_LABEL = "text-xs font-semibold text-ink-soft sm:sr-only";
const COLUMNS = "sm:grid-cols-[minmax(0,13rem)_minmax(0,1fr)_minmax(0,1fr)]";

/** Researcher view: claim by claim, how many ways of counting agree and what the skeptic tests found. */
export default function EvidenceOverview({ claims, headline, caption }: {
  claims: ClaimResult[];
  headline: string;
  caption: string;
}) {
  return (
    <>
      <p className="mt-2 max-w-prose text-lg font-semibold leading-snug text-ink">{headline}</p>
      <p className="mt-1 max-w-prose text-sm text-ink-soft">{caption}</p>
      {claims.length > 0 && (
        <div className="mt-4 text-sm">
          <div aria-hidden="true" className={`hidden gap-x-6 border-b border-rule pb-2 font-semibold text-ink-soft sm:grid ${COLUMNS}`}>
            <span>Claim</span>
            <span>Ways of counting that agree</span>
            <span>Skeptic tests</span>
          </div>
          <ul className="divide-y divide-rule">
            {claims.map((c) => {
              const final = finalVerdict(c);
              return (
                <li key={c.claim.id} className={`grid gap-x-6 gap-y-2 py-3 sm:items-center ${COLUMNS}`}>
                  <span className="flex flex-wrap items-center gap-2">
                    <span className="num font-mono font-semibold text-ink">{c.claim.id}</span>
                    <VerdictBadge verdict={final} size="sm" />
                  </span>
                  <span className="grid gap-1">
                    <span className={CELL_LABEL}>Ways of counting that agree</span>
                    <AgreementBar result={c} />
                  </span>
                  <span className="grid gap-1">
                    <span className={CELL_LABEL}>Skeptic tests</span>
                    <SkepticShort result={c} />
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </>
  );
}
