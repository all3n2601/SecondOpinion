import VerdictBadge from "@/components/VerdictBadge";
import {
  countText,
  finalVerdict,
  formatCount,
  SOLIDITY_LABEL,
  VERDICTS,
} from "@/lib/review";
import { focusRing } from "@/lib/ui";
import type { ClaimResult, ReleaseInfo } from "@/lib/types";

/** Shared renderers for role sections (Decision page) and review views. */

export const LIST = "list-disc space-y-2 pl-5 marker:text-ink-faint";
export const ID = "num font-mono text-sm font-semibold";

export function Counts({ claims }: { claims: ClaimResult[] }) {
  return (
    <ul className="flex flex-wrap gap-x-5 gap-y-2">
      {VERDICTS.map((v) => (
        <li key={v} className="flex items-center gap-2">
          <VerdictBadge verdict={v} size="sm" />
          <span className="num font-mono text-sm">
            {claims.filter((c) => finalVerdict(c) === v).length} of {claims.length}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function CorrectedWording({ result }: { result: ClaimResult }) {
  if (!result.ladder.length) return <>{result.claim.text}</>;
  return (
    <>
      {result.ladder
        .filter((s) => !s.struck)
        .map((s, i) => (s.inserted ? <ins key={i}>{s.text}</ins> : <span key={i}>{s.text}</span>))}
    </>
  );
}

export function RobustnessLine({ result, full }: { result: ClaimResult; full: boolean }) {
  const c = result;
  return (
    <>
      {SOLIDITY_LABEL[c.solidity]}
      {c.flips_on.length > 0 && ` (changes on ${c.flips_on.join(", ")})`}
      {full && c.variants.length > 0 &&
        `; ${c.variants.filter((v) => v.verdict === c.verdict).length} of ${c.variants.length} ways of counting agree`}
    </>
  );
}

export function SkepticLine({ result }: { result: ClaimResult }) {
  const c = result;
  return (
    <>
      {c.skeptic
        ? `shuffled-label p = ${c.skeptic.shuffle_p ?? "unknown"}; leaving out one of ${c.skeptic.n_sites} sites ` +
          (c.skeptic.site_flips.length ? `flips it (${c.skeptic.site_flips.join(", ")})` : "never flips it")
        : "skeptic tests do not apply"}
    </>
  );
}

export function SampleIds({ result, limit }: { result: ClaimResult; limit: number }) {
  const c = result;
  const ids = c.fact?.sample_ids ?? [];
  const shown = ids.slice(0, limit);
  return (
    <>
      {countText(c.fact) ?? "no samples"}
      {shown.length > 0 && (
        <>
          : <code className="num break-all font-mono text-sm">{shown.join(", ")}</code>
          {ids.length > shown.length && ` and ${formatCount(ids.length - shown.length)} more`}
        </>
      )}
    </>
  );
}

/** The code behind a claim's check, as a scrollable block; null when there is none. */
export function CodeBlock({ result }: { result: ClaimResult }) {
  const c = result;
  if (!c.fact?.code) return null;
  return (
    <pre
      tabIndex={0}
      aria-label={`Code for ${c.claim.id}`}
      className={`mt-1 overflow-x-auto rounded-control bg-ink p-3 font-mono text-xs leading-5 text-paper ${focusRing}`}
    >
      <code>{c.fact.code}</code>
    </pre>
  );
}

export function CodeFor({ result }: { result: ClaimResult }) {
  if (!result.fact?.code) return null;
  return (
    <details>
      <summary className={`min-h-11 cursor-pointer rounded-control py-2 text-sm font-medium text-pen underline-offset-4 hover:underline ${focusRing}`}>
        Code for {result.claim.id}
      </summary>
      <CodeBlock result={result} />
    </details>
  );
}

export function FileChecksums({ files }: { files: ReleaseInfo["files"] }) {
  return (
    <ul className={LIST}>
      {files.map((f) => (
        <li key={f.file}>
          {f.file}: <code className="num break-all font-mono text-sm">{f.sha256 || "checksum missing"}</code>
        </li>
      ))}
    </ul>
  );
}
