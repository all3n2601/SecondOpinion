import type { CSSProperties, ReactNode } from "react";
import {
  countingRange,
  diagnose,
  formatMeasure,
  restsOn,
  statedWords,
  storyLines,
  type CountingRange,
  type Diagnosis,
  type Measure,
  type RestsOn,
  type Stated,
} from "@/lib/insights";
import { formatCount } from "@/lib/review";
import type { ClaimResult, Verdict } from "@/lib/types";

/**
 * The pieces that show what a claim's numbers say beyond its verdict. ClaimBody places them: the strip as the
 * claim's one chart, the rest inside folds. Every figure comes from the audit.
 */

const DOT: Record<Verdict, string> = {
  supported: "bg-supported",
  contradicted: "bg-contradicted",
  insufficient_evidence: "bg-insufficient",
};
const TONE: Record<Verdict, string> = {
  supported: "text-supported",
  contradicted: "text-contradicted",
  insufficient_evidence: "text-insufficient",
};
const HATCH = { backgroundImage: "repeating-linear-gradient(135deg, currentColor 0 1.5px, transparent 1.5px 6px)" };

/** Dots closer than this (percent of the track) go on a new row so none hides another. */
const MIN_GAP = 3;
const ROW_PX = 14;

/** A claim, or one part of a multi-part sentence, that has something to show here. */
export interface ReadingTarget {
  result: ClaimResult;
  /** The part's words; null for a whole sentence. */
  label: string | null;
}

/** What to show readings for: the claim itself, or each checkable part that has a reading. */
export function readingTargets(result: ClaimResult): ReadingTarget[] {
  const has = (r: ClaimResult) => r.verdict !== "insufficient_evidence" && Boolean(countingRange(r) || restsOn(r) || diagnose(r));
  if (!result.parts?.length) return has(result) ? [{ result, label: null }] : [];
  return result.parts.filter(has).map((p) => ({ result: p, label: p.claim.part_label || p.claim.text }));
}

export function PartLabel({ label }: { label: string | null }) {
  if (!label) return null;
  return (
    <p className="text-sm text-ink-soft">
      About <q className="reported text-ink">{label}</q>
    </p>
  );
}

/** The stated figure's band on the number line: the range, or what "about" allows. */
function statedBand(stated: Stated, measure: Measure): [number, number] {
  if (stated.high !== null) return [stated.value, stated.high];
  if (!stated.approximate) return [stated.value, stated.value];
  const allow = measure === "percent" ? 2 : 0.02 * stated.value;
  return [stated.value - allow, stated.value + allow];
}

function rangeSentence(range: CountingRange, stated: Stated | null): string {
  const lo = formatMeasure(range.low.value, range.measure);
  const hi = formatMeasure(range.high.value, range.measure);
  const span = range.distinct === 1 ? `every one gives ${lo}` : `they give between ${lo} and ${hi}`;
  const said = stated ? ` The report says ${statedWords(stated, range.measure)}.` : "";
  return `The data was counted ${formatCount(range.ways.length)} ways; ${span}.${said}`;
}

/** Keep a label inside the track: start-aligned near the left, end-aligned near the right, centred between. */
function place(pos: number): CSSProperties {
  if (pos < 35) return { left: `${pos}%` };
  if (pos > 65) return { right: `${100 - pos}%` };
  return { left: `${pos}%`, transform: "translateX(-50%)" };
}

/**
 * One dot per way of counting on a number line zoomed to the values, with the report's figure (and its
 * "about" band or range) marked above and the standard way's value labelled under its ringed dot.
 */
export function CountingStrip({ range, stated, verdict, plain = false }: { range: CountingRange; stated: Stated | null; verdict: Verdict; plain?: boolean }) {
  const { measure, ways } = range;
  const band = stated ? statedBand(stated, measure) : null;
  const values = [...ways.map((w) => w.value), ...(band ?? [])];
  let lo = Math.min(...values);
  let hi = Math.max(...values);
  const pad = Math.max((hi - lo) * 0.08, measure === "percent" ? 0.5 : 1);
  lo -= pad;
  hi += pad;
  const at = (x: number) => ((x - lo) / (hi - lo)) * 100;

  const rows: number[] = [];
  const placed = ways.map((w) => {
    const pos = at(w.value);
    let row = rows.findIndex((last) => pos - last >= MIN_GAP);
    if (row < 0) row = rows.length;
    rows[row] = pos;
    return { ...w, pos, row };
  });
  const height = Math.max(rows.length, 1) * ROW_PX + 12;
  const tick = (x: number) => (measure === "percent" ? `${Math.round(x)}%` : formatCount(Math.round(x)));
  const label = stated ? `Report says ${statedWords(stated, measure)}` : null;
  const labelAt = band ? at((band[0] + band[1]) / 2) : null;
  const standard = placed.find((w) => w.primary);

  return (
    <figure className="mt-5">
      <div aria-hidden="true">
        <div className="relative h-6">
          {label && labelAt !== null && (
            <span className={`absolute bottom-1 text-sm font-semibold whitespace-nowrap ${TONE[verdict]}`} style={place(labelAt)}>
              {label}
            </span>
          )}
        </div>
        <div className="relative rounded-control border border-rule bg-wash" style={{ height }}>
          {band && (
            <span
              className={`absolute inset-y-0 border-x-2 border-current opacity-60 ${TONE[verdict]}`}
              style={{ left: `${at(band[0])}%`, width: `${Math.max(at(band[1]) - at(band[0]), 0.4)}%`, ...HATCH }}
            />
          )}
          {placed.map((w) => (
            <span
              key={w.id}
              title={`${w.words}: ${formatMeasure(w.value, measure)}`}
              className={`absolute size-3 -translate-x-1/2 rounded-full ${w.verdict ? DOT[w.verdict] : "bg-ink-faint"} ${
                w.primary ? "ring-2 ring-ink ring-offset-1 ring-offset-wash" : ""
              }`}
              style={{ left: `${w.pos}%`, top: 6 + w.row * ROW_PX }}
            />
          ))}
        </div>
        {standard && (
          <div className="relative h-6">
            <span className="absolute top-0 h-1.5 w-px -translate-x-1/2 bg-ink" style={{ left: `${standard.pos}%` }} />
            <span className="num absolute top-1.5 text-sm whitespace-nowrap text-ink" style={place(standard.pos)}>
              <span className="text-ink-soft">Data </span>
              <span className="font-mono font-semibold">{formatMeasure(standard.value, measure)}</span>
            </span>
          </div>
        )}
        <div className="num mt-1 flex justify-between font-mono text-xs text-ink-faint">
          <span>{tick(lo)}</span>
          <span>{tick(hi)}</span>
        </div>
      </div>
      <figcaption className="mt-2 max-w-prose text-sm text-ink-soft">
        <span className={plain ? "sr-only" : undefined}>{rangeSentence(range, stated)} </span>
        {plain ? "Each dot is one way we counted the data." : "Ringed dot: the standard way."}
      </figcaption>
    </figure>
  );
}

function boundsSentence(rests: RestsOn): string | null {
  if (!rests.bounds) return null;
  const [lo, hi] = rests.bounds.map((b) => formatMeasure(b, "percent"));
  return `The share is out of ${formatCount(rests.inGroup + rests.otherValue)}, not ${formatCount(rests.total)}: ${formatCount(
    rests.leftOut,
  )} have no value recorded. Whatever those are, the true share lies between ${lo} and ${hi}.`;
}

/** Counted for the claim, checked but not counted, and left out for a missing value, as one stacked bar. */
export function RestsOnBar({ rests }: { rests: RestsOn }) {
  const parts = [
    { key: "in", n: rests.inGroup, label: "counted for the claim", swatch: "bg-ink", style: undefined },
    { key: "other", n: rests.otherValue, label: "checked, not counted", swatch: "bg-rule-strong", style: undefined },
    { key: "out", n: rests.leftOut, label: "no value recorded, left out", swatch: "text-ink-faint bg-sheet", style: HATCH },
  ].filter((p) => p.n > 0);
  const summary = parts.map((p) => `${formatCount(p.n)} ${p.label}`).join(", ");
  return (
    <div>
      <div role="img" aria-label={`${summary}; ${formatCount(rests.total)} in all.`} className="flex h-4 overflow-hidden rounded-control border border-rule">
        {parts.map((p) => (
          <span key={p.key} className={p.swatch} style={{ width: `${(p.n / rests.total) * 100}%`, ...p.style }} />
        ))}
      </div>
      <ul aria-hidden="true" className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-sm text-ink-soft">
        {parts.map((p) => (
          <li key={p.key} className="flex items-center gap-1.5">
            <span className={`inline-block size-3 rounded-sm border border-rule ${p.swatch}`} style={p.style} />
            <span className="num font-mono text-ink">{formatCount(p.n)}</span> {p.label}
          </li>
        ))}
      </ul>
      {rests.bounds && <p className="mt-2 max-w-prose text-sm text-ink-soft">{boundsSentence(rests)}</p>}
    </div>
  );
}

function causeSentence(d: Diagnosis): string {
  const said = statedWords(d.stated, d.measure);
  if (d.matches.length) {
    const ifs = d.matches.map((m) => `if you ${m.how} (${formatMeasure(m.value, d.measure)})`);
    return `The report's figure, ${said}, is what you get ${ifs.join(", or ")}.`;
  }
  const near = d.tried[0];
  if (!near) return "";
  return `None of the ${formatCount(d.tried.length)} other readings we tried gives ${said}. The nearest is ${formatMeasure(
    near.value,
    d.measure,
  )}, if you ${near.how}.`;
}

/** The clue sentence: which reading gives the stated figure, or the nearest when none does. */
export function CauseNote({ diagnosis }: { diagnosis: Diagnosis }) {
  const text = causeSentence(diagnosis);
  if (!text) return null;
  return (
    <div className="max-w-prose text-sm">
      <p className="text-ink">{text}</p>
      {diagnosis.matches.length > 0 && <p className="mt-1 text-ink-soft">A match is a clue to how the figure was made, not proof.</p>}
    </div>
  );
}

/** Every reading tried, nearest to the stated figure first, matches in bold. */
export function TriedList({ diagnosis, mono = false }: { diagnosis: Diagnosis; mono?: boolean }) {
  return (
    <ul aria-label="Every reading we tried" className="mt-3 divide-y divide-rule border-y border-rule text-sm">
      {diagnosis.tried.map((t) => {
        const hit = diagnosis.matches.includes(t);
        return (
          <li key={t.how} className="grid grid-cols-[5rem_minmax(0,1fr)] gap-3 py-2">
            <span className={`num font-mono ${hit ? "font-semibold text-ink" : "text-ink-soft"}`}>{formatMeasure(t.value, diagnosis.measure)}</span>
            <span className={mono ? "font-mono text-ink" : "text-ink"}>
              if you {t.how}
              {hit && <span className="font-semibold"> (matches the report)</span>}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

/** Plain sentences for the story view, one block per claim or part: no legend, no jargon, the same figures. */
export function StoryFindings({ result }: { result: ClaimResult }) {
  const blocks = readingTargets(result)
    .map((t) => ({ ...t, lines: storyLines(t.result) }))
    .filter((b) => b.lines.length);
  if (!blocks.length) return null;
  return (
    <div className="mt-4 max-w-prose rounded-control border-l-4 border-rule-strong bg-wash px-4 py-3 text-ink">
      <p className="text-sm font-semibold">What else we found</p>
      {blocks.map((b) => (
        <div key={b.result.claim.id} className="mt-1">
          {blocks.length > 1 && <PartLabel label={b.label} />}
          {b.lines.map((l) => (
            <p key={l} className="mt-1 leading-relaxed">
              {l}
            </p>
          ))}
        </div>
      ))}
    </div>
  );
}

function RawRows({ result }: { result: ClaimResult }) {
  const range = countingRange(result);
  const rests = restsOn(result);
  const diagnosis = diagnose(result);
  const rows: [string, ReactNode][] = [];
  if (rests) {
    rows.push(["rests on", `${formatCount(rests.inGroup)} in / ${formatCount(rests.otherValue)} other / ${formatCount(rests.leftOut)} missing = ${formatCount(rests.total)}`]);
    if (rests.bounds) rows.push(["missing bounds", rests.bounds.map((b) => formatMeasure(b, "percent")).join(" to ")]);
  }
  if (range) rows.push(["variant range", `${formatMeasure(range.low.value, range.measure)} to ${formatMeasure(range.high.value, range.measure)} (${range.ways.length} ways, ${range.distinct} distinct)`]);
  if (diagnosis) rows.push(["reproduces stated", diagnosis.matches.length ? diagnosis.matches.map((m) => m.how).join("; ") : "none"]);
  return (
    <>
      <dl className="grid gap-x-6 gap-y-1 font-mono sm:grid-cols-[max-content_minmax(0,1fr)]">
        {rows.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-ink-soft">{k}</dt>
            <dd className="num text-ink">{v}</dd>
          </div>
        ))}
      </dl>
      {range && (
        <table className="mt-3 w-full font-mono text-xs">
          <caption className="sr-only">Value per variant</caption>
          <tbody className="divide-y divide-rule border-y border-rule">
            {range.ways.map((w) => (
              <tr key={w.id}>
                <td className="py-1 pr-3 text-ink">
                  {w.id}
                  {w.primary ? " (primary)" : ""}
                </td>
                <td className="num py-1 pr-3 text-right text-ink">{formatMeasure(w.value, range.measure)}</td>
                <td className="py-1 text-ink-soft">{w.verdict ?? "none"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {diagnosis && <TriedList diagnosis={diagnosis} mono />}
    </>
  );
}

/** Raw view: the readings as terse numbers, a per-variant table and every reading tried, per claim or part. */
export function RawNumbers({ result }: { result: ClaimResult }) {
  const targets = readingTargets(result);
  if (!targets.length) return null;
  return (
    <div className="space-y-4 text-sm">
      {targets.map((t) => (
        <div key={t.result.claim.id}>
          <PartLabel label={t.label} />
          <div className={t.label ? "mt-2" : undefined}>
            <RawRows result={t.result} />
          </div>
        </div>
      ))}
    </div>
  );
}
