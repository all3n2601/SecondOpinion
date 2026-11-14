import { STORY_WORDS } from "@/components/review/ClaimBody";
import { finalVerdict, formatCount, VERDICTS } from "@/lib/review";
import type { ClaimResult, Verdict } from "@/lib/types";

/** "5 held up", "1 was wrong", "2 couldn't be checked". */
function countWords(verdict: Verdict, n: number): string {
  const count = formatCount(n);
  if (verdict === "supported") return `${count} held up`;
  if (verdict === "contradicted") return `${count} ${n === 1 ? "was" : "were"} wrong`;
  return `${count} couldn't be checked`;
}

/** Program leader view: a short briefing. Big headline, one stacked bar, the counts in words beside it. */
export default function StoryOverview({ claims, headline, caption }: {
  claims: ClaimResult[];
  headline: string;
  caption: string;
}) {
  const total = claims.length;
  const counts = VERDICTS.map((v) => ({ verdict: v, n: claims.filter((c) => finalVerdict(c) === v).length }));
  const summary = `${counts.map(({ verdict, n }) => countWords(verdict, n)).join(", ")}, out of ${formatCount(total)} ${
    total === 1 ? "claim" : "claims"
  }.`;

  return (
    <>
      <p className="mt-2 max-w-[38ch] text-2xl font-semibold leading-snug tracking-tight text-ink sm:text-[1.75rem]">
        {headline}
      </p>
      {total > 0 && (
        <div className="mt-6 grid gap-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:gap-8">
          <div role="img" aria-label={summary} className="flex h-6 gap-0.5 overflow-hidden rounded-stamp bg-wash">
            {counts.map(({ verdict, n }) =>
              n > 0 ? (
                <span
                  key={verdict}
                  title={countWords(verdict, n)}
                  className={`${STORY_WORDS[verdict].fill} transition-[flex-grow] duration-300`}
                  style={{ flexGrow: n, flexBasis: 0 }}
                />
              ) : null,
            )}
          </div>
          <ul aria-label="Claims by what we found" className="grid gap-1.5 text-base text-ink">
            {counts.map(({ verdict, n }) => {
              const { icon: Icon, ink } = STORY_WORDS[verdict];
              return (
                <li key={verdict} className="flex items-center gap-2">
                  <Icon aria-hidden="true" className={`size-5 shrink-0 ${ink}`} strokeWidth={2.25} />
                  <span className="num">{countWords(verdict, n)}</span>
                </li>
              );
            })}
          </ul>
        </div>
      )}
      <p className="mt-5 max-w-prose text-ink-soft">{caption}</p>
    </>
  );
}
