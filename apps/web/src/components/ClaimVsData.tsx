import { CircleHelp } from "lucide-react";
import type { CSSProperties, ReactNode } from "react";
import { formatFact } from "@/lib/claim-format";
import type { ClaimParams, ClaimResult, Verdict } from "@/lib/types";
import { sectionTitle } from "@/lib/ui";

/** What "about" means on the chart: the stated figure plus or minus this many percentage points. */
export const APPROX_POINTS = 2;

const oneDecimal = new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 });
const whole = new Intl.NumberFormat("en-US");
const clamp = (n: number) => Math.min(100, Math.max(0, n));

/** The report's stated share, ready to draw on a 0 to 100 axis. */
export interface StatedShare {
  /** Where the single tick goes; null for a range (the ends get ticks instead). */
  marker: number | null;
  /** Light hatched band: the "about" tolerance, or the stated range. */
  band: [number, number] | null;
  /** "about 62%", "55 to 62%", "every one". */
  phrase: string;
  /** "Report says about 62%". */
  label: string;
}

export function statedShare(p: ClaimParams): StatedShare | null {
  if (p.unit === "all") {
    return { marker: 100, band: null, phrase: "every one", label: "Report says every one" };
  }
  if (p.stated_value === null) return null;
  const v = p.stated_value;
  if (p.stated_high !== null) {
    const phrase = `${oneDecimal.format(v)} to ${oneDecimal.format(p.stated_high)}%`;
    return { marker: null, band: [v, p.stated_high], phrase, label: `Report says ${phrase}` };
  }
  const phrase = `${p.approximate ? "about " : ""}${oneDecimal.format(v)}%`;
  return {
    marker: v,
    band: p.approximate ? [v - APPROX_POINTS, v + APPROX_POINTS] : null,
    phrase,
    label: `Report says ${phrase}`,
  };
}

/** One sentence on how far the data is from the stated figure. */
function shareGap(value: number, s: StatedShare): string {
  const points = (n: number) => `${oneDecimal.format(Math.abs(n))} point${Math.abs(n) === 1 ? "" : "s"}`;
  if (s.marker === null && s.band) {
    const [lo, hi] = s.band;
    if (value < lo) return `The data is ${points(lo - value)} below the stated range.`;
    if (value > hi) return `The data is ${points(value - hi)} above the stated range.`;
    return "The data falls inside the stated range.";
  }
  if (s.marker === null) return "";
  const diff = value - s.marker;
  if (s.band) {
    if (value >= s.band[0] && value <= s.band[1]) {
      return `The data is within ${APPROX_POINTS} points of the stated figure.`;
    }
    return `The data is ${points(diff)} ${diff < 0 ? "below" : "above"} the stated figure, outside the ${APPROX_POINTS}-point band for "about".`;
  }
  if (Math.abs(diff) < 0.05) return "The data matches the stated figure.";
  return `The data is ${points(diff)} ${diff < 0 ? "below" : "above"} the stated figure.`;
}

const TONE: Record<Verdict, { text: string; bg: string }> = {
  supported: { text: "text-supported", bg: "bg-supported" },
  contradicted: { text: "text-contradicted", bg: "bg-contradicted" },
  insufficient_evidence: { text: "text-insufficient", bg: "bg-insufficient" },
};

/** Keep a label inside the track: start-aligned near the left, end-aligned near the right, centred between. */
function place(pos: number): { style: CSSProperties; align: string } {
  if (pos < 35) return { style: { left: `${pos}%` }, align: "text-left" };
  if (pos > 65) return { style: { right: `${100 - pos}%` }, align: "text-right" };
  return { style: { left: `${pos}%`, transform: "translateX(-50%)" }, align: "text-center" };
}

interface TrackProps {
  /** Where the data's bar ends, 0 to 100. */
  dataPos: number;
  dataLabel: ReactNode;
  /** Positions of the report's ticks, 0 to 100. */
  ticks: number[];
  band: [number, number] | null;
  tickLabel: string | null;
  verdict: Verdict;
  axis: { pos: number; label: string }[];
}

/** The shared drawing: report label and tick above, solid data bar in the track, data label below, axis last. */
function Track({ dataPos, dataLabel, ticks, band, tickLabel, verdict, axis }: TrackProps) {
  const tone = TONE[verdict];
  const data = clamp(dataPos);
  const anchor = ticks.length ? ticks.reduce((a, b) => a + b, 0) / ticks.length : null;
  const tickPlace = anchor === null ? null : place(clamp(anchor));
  const dataPlace = place(data);
  const bandLo = band ? clamp(Math.min(...band)) : 0;
  const bandHi = band ? clamp(Math.max(...band)) : 0;

  return (
    <div aria-hidden="true" className="pt-1">
      {/* report label */}
      <div className="relative h-10">
        {tickLabel && tickPlace && (
          <p
            className={`absolute bottom-4 text-sm leading-5 font-semibold whitespace-nowrap ${tone.text} ${tickPlace.align}`}
            style={tickPlace.style}
          >
            {tickLabel}
          </p>
        )}
      </div>

      {/* track */}
      <div className="relative h-9">
        <div className="absolute inset-0 overflow-hidden rounded-control border border-rule-strong bg-wash">
          <div className="absolute inset-y-0 left-1/2 w-px bg-rule-strong" />
          {band && (
            <div
              className={`absolute inset-y-0 border-x-2 border-current opacity-70 ${tone.text}`}
              style={{
                left: `${bandLo}%`,
                width: `${Math.max(bandHi - bandLo, 0.5)}%`,
                backgroundImage:
                  "repeating-linear-gradient(135deg, currentColor 0 1.5px, transparent 1.5px 6px)",
              }}
            />
          )}
          <div className="absolute inset-y-0 left-0 bg-ink" style={{ width: `${data}%` }} />
        </div>
        {ticks.map((pos) => (
          <div
            key={pos}
            className={`absolute -top-3 -bottom-1 w-0.5 -translate-x-1/2 ${tone.bg}`}
            style={{ left: `${clamp(pos)}%` }}
          >
            <span className={`absolute -top-1 left-1/2 size-2.5 -translate-x-1/2 rotate-45 ${tone.bg}`} />
          </div>
        ))}
      </div>

      {/* data label */}
      <div className="relative h-10">
        <span className="absolute top-0 h-2.5 w-0.5 -translate-x-1/2 bg-ink" style={{ left: `${data}%` }} />
        <p
          className={`absolute top-3 text-sm leading-5 whitespace-nowrap text-ink ${dataPlace.align}`}
          style={dataPlace.style}
        >
          {dataLabel}
        </p>
      </div>

      {/* axis */}
      <div className="relative h-6 border-t border-rule">
        {axis.map((a) => {
          const p = place(a.pos);
          return (
            <span key={a.pos} className="absolute top-0" style={{ left: `${a.pos}%` }}>
              <span className="absolute top-0 h-1.5 w-px -translate-x-1/2 bg-rule-strong" />
              <span
                className="num absolute top-1.5 font-mono text-xs whitespace-nowrap text-ink-faint"
                style={{
                  transform: p.align === "text-left" ? "none" : p.align === "text-right" ? "translateX(-100%)" : "translateX(-50%)",
                }}
              >
                {a.label}
              </span>
            </span>
          );
        })}
      </div>
    </div>
  );
}

function Figure({ title, summary, children, note }: { title: string; summary: string; children: ReactNode; note?: ReactNode }) {
  return (
    <figure aria-label={title} className="mt-8">
      <h2 className={`${sectionTitle} mb-1`}>{title}</h2>
      <p className="sr-only">{summary}</p>
      {children}
      {note && <figcaption className="mt-3 max-w-prose space-y-1 text-sm text-ink-soft">{note}</figcaption>}
    </figure>
  );
}

function ShareGauge({ result }: { result: ClaimResult }) {
  const { claim, fact, verdict } = result;
  if (!fact || fact.value === null) return null;
  const value = fact.value;
  const stated = statedShare(claim.params);
  const data = formatFact(fact, "SHARE");

  const ticks = stated ? (stated.marker !== null ? [stated.marker] : stated.band ? [...stated.band] : []) : [];
  const gap = stated ? shareGap(value, stated) : "";
  const bandNote =
    stated?.band && stated.marker !== null
      ? `Hatched band: what "about" allows, ${APPROX_POINTS} points either side (${oneDecimal.format(stated.band[0])}% to ${oneDecimal.format(stated.band[1])}%).`
      : stated?.band
        ? "Hatched band: the range the report states."
        : null;

  const summary = `${stated ? `${stated.label}. ` : "The report states no figure. "}The data says ${data}. ${gap}`.trim();

  return (
    <Figure
      title="Report versus data"
      summary={summary}
      note={
        <>
          {gap && <p>{gap}</p>}
          {bandNote && <p>{bandNote}</p>}
        </>
      }
    >
      <Track
        dataPos={value}
        dataLabel={
          <>
            <span className="text-ink-soft">Data </span>
            <span className="num font-mono font-semibold">{data}</span>
          </>
        }
        ticks={ticks}
        band={stated?.band ?? null}
        tickLabel={stated?.label ?? null}
        verdict={verdict}
        axis={[
          { pos: 0, label: "0%" },
          { pos: 50, label: "50%" },
          { pos: 100, label: "100%" },
        ]}
      />
    </Figure>
  );
}

function CountGauge({ result }: { result: ClaimResult }) {
  const { claim, fact, verdict } = result;
  if (!fact || fact.numerator === null || fact.denominator === null || fact.denominator <= 0) return null;
  const { numerator, denominator } = fact;
  const p = claim.params;
  const statedCount = p.unit === "all" ? denominator : p.stated_value;
  const statedPos = statedCount === null ? null : (statedCount / denominator) * 100;
  const statedLabel = statedCount === null ? null : p.unit === "all" ? "Report says every one" : `Report says ${whole.format(statedCount)}`;
  const data = `${whole.format(numerator)} of ${whole.format(denominator)}`;
  const same = statedCount !== null && statedCount === numerator;

  const summary = `${statedLabel ? `${statedLabel}. ` : "The report states no figure. "}The data counts ${data}.${
    statedCount === null ? "" : same ? " They match." : ` The data differs by ${whole.format(Math.abs(numerator - statedCount))}.`
  }`;

  return (
    <Figure title="Report versus data" summary={summary}>
      <Track
        dataPos={(numerator / denominator) * 100}
        dataLabel={
          <>
            <span className="text-ink-soft">Data </span>
            <span className="num font-mono font-semibold">{data}</span>
          </>
        }
        ticks={statedPos === null ? [] : [statedPos]}
        band={null}
        tickLabel={statedLabel}
        verdict={verdict}
        axis={[
          { pos: 0, label: "0" },
          { pos: 50, label: whole.format(Math.round(denominator / 2)) },
          { pos: 100, label: whole.format(denominator) },
        ]}
      />
    </Figure>
  );
}

function ComparisonGauge({ result }: { result: ClaimResult }) {
  const { claim, fact } = result;
  const x = fact?.extra ?? {};
  if (!fact || typeof x.mean_a !== "number" || typeof x.mean_b !== "number") return null;
  const p = claim.params;
  const groups = [
    { name: p.group_a ?? "Group A", mean: x.mean_a, n: x.n_a, fill: "bg-ink" },
    { name: p.group_b ?? "Group B", mean: x.mean_b, n: x.n_b, fill: "bg-ink-soft" },
  ];
  const lo = Math.min(0, ...groups.map((g) => g.mean));
  const hi = Math.max(0, ...groups.map((g) => g.mean));
  const span = hi - lo || 1;
  const at = (v: number) => ((v - lo) / span) * 100;
  const zero = at(0);
  const said =
    p.direction && p.group_a && p.group_b
      ? `Report says ${p.measure ?? "the measure"} is ${p.direction} in ${p.group_a} than ${p.group_b}.`
      : null;
  const diff = formatFact(fact, "COMPARISON");
  const sampleWords = (n: number | string | undefined) => (n === undefined ? "" : `${whole.format(Number(n))} samples`);

  const summary = `${said ? `${said} ` : ""}The data: ${groups
    .map((g) => `${g.name} mean ${g.mean.toFixed(3)}${g.n === undefined ? "" : ` (${sampleWords(g.n)})`}`)
    .join("; ")}. ${diff}.`;

  return (
    <Figure
      title="Report versus data"
      summary={summary}
      note={
        <>
          {said && <p>{said}</p>}
          <p>The bars share one scale, starting from a mean of 0.</p>
        </>
      }
    >
      <div aria-hidden="true" className="mt-4 grid gap-4">
        {groups.map((g) => (
          <div key={g.name}>
            <p className="flex flex-wrap items-baseline justify-between gap-x-4 text-sm">
              <span className="font-medium text-ink">{g.name}</span>
              <span className="num font-mono text-ink-soft">
                {g.n !== undefined && <>{sampleWords(g.n)}, </>}mean{" "}
                <span className="font-semibold text-ink">{g.mean.toFixed(3)}</span>
              </span>
            </p>
            <div className="relative mt-1 h-7 overflow-hidden rounded-control border border-rule-strong bg-wash">
              <div
                className={`absolute inset-y-0 ${g.fill}`}
                style={{ left: `${Math.min(zero, at(g.mean))}%`, width: `${Math.abs(at(g.mean) - zero)}%` }}
              />
              <div className="absolute inset-y-0 w-px bg-ink-faint" style={{ left: `${zero}%` }} />
            </div>
          </div>
        ))}
        <div className="relative h-5 border-t border-rule">
          {[
            ...(lo < 0 ? [{ pos: 0, label: oneDecimal.format(lo) }] : []),
            { pos: zero, label: "0" },
            ...(hi > 0 ? [{ pos: 100, label: oneDecimal.format(hi) }] : []),
          ].map((a, i) => {
            const t = a.pos <= 4 ? "none" : a.pos >= 96 ? "translateX(-100%)" : "translateX(-50%)";
            return (
              <span key={i} className="num absolute top-1 font-mono text-xs text-ink-faint" style={{ left: `${a.pos}%`, transform: t }}>
                {a.label}
              </span>
            );
          })}
        </div>
      </div>
      <p className="num mt-2 font-mono text-sm font-semibold text-ink">{diff}</p>
    </Figure>
  );
}

function Needs({ result }: { result: ClaimResult }) {
  return (
    <section aria-labelledby="needs-title" className="mt-8 rounded-panel border border-insufficient bg-insufficient-tint p-5">
      <h2 id="needs-title" className="flex items-center gap-2 text-lg font-semibold tracking-tight text-insufficient">
        <CircleHelp aria-hidden="true" className="size-5 shrink-0" strokeWidth={2.25} />
        What the data would need
      </h2>
      <p className="mt-2 max-w-prose leading-7 text-ink">
        {result.missing_evidence ? (
          <>
            This data cannot answer the claim. It would need <strong>{result.missing_evidence}</strong>.
          </>
        ) : (
          "This data cannot answer the claim."
        )}
      </p>
    </section>
  );
}

/** "Stated vs actual": what the report says beside what the data says, labelled directly on the chart. */
export default function ClaimVsData({ result }: { result: ClaimResult }) {
  if (result.verdict === "insufficient_evidence") return <Needs result={result} />;
  const { claim, fact } = result;
  if (!fact) return null;

  if (claim.type === "COMPARISON") return <ComparisonGauge result={result} />;
  if (claim.type === "SHARE" || (claim.params.unit === "percent" && fact.value !== null)) {
    return <ShareGauge result={result} />;
  }
  return <CountGauge result={result} />;
}
