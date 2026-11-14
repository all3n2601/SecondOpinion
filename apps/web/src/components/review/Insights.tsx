import type { ReactNode } from "react";
import {
  countingRange,
  diagnose,
  formatMeasure,
  restsOn,
  statedFigure,
  statedWords,
  type CountingRange,
  type Diagnosis,
  type Measure,
  type RestsOn,
  type Stated,
} from "@/lib/insights";
import { formatCount } from "@/lib/review";
import type { ClaimResult, RoleView, Verdict } from "@/lib/types";
import { focusRing } from "@/lib/ui";

/** What a claim's numbers say beyond its verdict, worded for the viewer's role. Every figure comes from the audit. */

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

/**
 * One dot per way of counting on a number line zoomed to the values, with the report's figure (and its
 * "about" band or range) marked. A dot's colour is that way's verdict; the ringed dot is the standard way.
 */
function CountingStrip({ range, stated, verdict, plain = false }: { range: CountingRange; stated: Stated | null; verdict: Verdict; plain?: boolean }) {
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

  return (
    <figure className="mt-4">
      <div aria-hidden="true">
        <div className="relative h-6">
          {label && labelAt !== null && (
            <span
              className={`absolute bottom-1 text-sm font-semibold whitespace-nowrap ${TONE[verdict]}`}
              style={labelAt > 60 ? { right: `${100 - labelAt}%` } : labelAt < 40 ? { left: `${labelAt}%` } : { left: `${labelAt}%`, transform: "translateX(-50%)" }}
            >
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
        <div className="num mt-1 flex justify-between font-mono text-xs text-ink-faint">
          <span>{tick(lo)}</span>
          <span>{tick(hi)}</span>
        </div>
      </div>
      <figcaption className="mt-2 max-w-prose text-sm text-ink-soft">
        {plain ? "Each dot is one way we counted the data." : `${rangeSentence(range, stated)} Each dot is one way of counting; the ringed dot is the standard way.`}
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
function RestsOnBar({ rests }: { rests: RestsOn }) {
  const parts = [
    { key: "in", n: rests.inGroup, label: "counted for the claim", swatch: "bg-ink", style: undefined },
    { key: "other", n: rests.otherValue, label: "checked, not counted", swatch: "bg-rule-strong", style: undefined },
    { key: "out", n: rests.leftOut, label: "no value recorded, left out", swatch: "text-ink-faint bg-sheet", style: HATCH },
  ].filter((p) => p.n > 0);
  const summary = parts.map((p) => `${formatCount(p.n)} ${p.label}`).join(", ");
  return (
    <figure className="mt-4">
      <figcaption className="text-sm font-semibold text-ink">What the number rests on</figcaption>
      <div
        role="img"
        aria-label={`${summary}; ${formatCount(rests.total)} in all.`}
        className="mt-2 flex h-4 overflow-hidden rounded-control border border-rule"
      >
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
    </figure>
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

function CauseNote({ diagnosis, title = "Where the report's figure might come from" }: { diagnosis: Diagnosis; title?: string }) {
  const text = causeSentence(diagnosis);
  if (!text) return null;
  return (
    <div className="mt-4 max-w-prose text-sm">
      <p className="font-semibold text-ink">{title}</p>
      <p className="mt-1 text-ink">{text}</p>
      {diagnosis.matches.length > 0 && <p className="mt-1 text-ink-soft">A match is a clue to how the figure was made, not proof.</p>}
    </div>
  );
}

function TriedList({ diagnosis, mono = false }: { diagnosis: Diagnosis; mono?: boolean }) {
  return (
    <details className="mt-2 text-sm">
      <summary className={`min-h-11 cursor-pointer rounded-control py-2 font-medium text-pen underline-offset-4 hover:underline ${focusRing}`}>
        Every reading we tried <span className="num font-mono">({formatCount(diagnosis.tried.length)})</span>
      </summary>
      <ul className="mt-1 divide-y divide-rule border-y border-rule">
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
    </details>
  );
}

/** Plain sentences for the story view: no dots legend, no jargon, the same figures. */
function StoryFindings({ range, rests, diagnosis, stated }: { range: CountingRange | null; rests: RestsOn | null; diagnosis: Diagnosis | null; stated: Stated | null }) {
  const lines: string[] = [];
  if (range) {
    const lo = formatMeasure(range.low.value, range.measure);
    const hi = formatMeasure(range.high.value, range.measure);
    const gave = range.distinct === 1 ? `the data gave ${lo}` : `the data gave between ${lo} and ${hi}`;
    const never = stated && range.ways.every((w) => w.verdict === "contradicted") ? `, never close to the report's ${statedWords(stated, range.measure)}` : "";
    lines.push(`However we counted it, ${gave}${never}.`);
  }
  if (rests?.bounds) {
    const [lo, hi] = rests.bounds.map((b) => formatMeasure(b, "percent"));
    lines.push(
      `Some records are missing this detail (${formatCount(rests.leftOut)} of ${formatCount(rests.total)}). Whatever they are, the true figure lies between ${lo} and ${hi}.`,
    );
  }
  if (diagnosis) {
    const said = statedWords(diagnosis.stated, diagnosis.measure);
    const match = diagnosis.matches[0];
    if (match) lines.push(`The report's figure, ${said}, is what you get if you ${match.plain ?? match.how}. That may be how it was worked out.`);
    else if (stated && diagnosis.tried.length) lines.push(`We tried ${formatCount(diagnosis.tried.length)} other ways of reading the data and none gives ${said}.`);
  }
  if (!lines.length) return null;
  return (
    <div className="mt-4 max-w-prose rounded-control border-l-4 border-rule-strong bg-wash px-4 py-3 text-ink">
      <p className="text-sm font-semibold">What else we found</p>
      {lines.map((l) => (
        <p key={l} className="mt-1 leading-relaxed">
          {l}
        </p>
      ))}
    </div>
  );
}

function RawInsights({ range, rests, diagnosis }: { range: CountingRange | null; rests: RestsOn | null; diagnosis: Diagnosis | null }) {
  const rows: [string, ReactNode][] = [];
  if (rests) {
    rows.push(["rests on", `${formatCount(rests.inGroup)} in / ${formatCount(rests.otherValue)} other / ${formatCount(rests.leftOut)} missing = ${formatCount(rests.total)}`]);
    if (rests.bounds) rows.push(["missing bounds", rests.bounds.map((b) => formatMeasure(b, "percent")).join(" to ")]);
  }
  if (range) rows.push(["variant range", `${formatMeasure(range.low.value, range.measure)} to ${formatMeasure(range.high.value, range.measure)} (${range.ways.length} ways, ${range.distinct} distinct)`]);
  if (diagnosis) rows.push(["reproduces stated", diagnosis.matches.length ? diagnosis.matches.map((m) => m.how).join("; ") : "none"]);
  if (!rows.length && !range) return null;
  return (
    <div className="mt-3 text-sm">
      <dl className="grid gap-x-6 gap-y-1 font-mono sm:grid-cols-[max-content_minmax(0,1fr)]">
        {rows.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-ink-soft">{k}</dt>
            <dd className="num text-ink">{v}</dd>
          </div>
        ))}
      </dl>
      {range && (
        <details className="mt-2">
          <summary className={`min-h-11 cursor-pointer rounded-control py-2 font-medium text-pen underline-offset-4 hover:underline ${focusRing}`}>
            Value per variant <span className="num font-mono">({formatCount(range.ways.length)})</span>
          </summary>
          <table className="mt-1 w-full font-mono text-xs">
            <tbody className="divide-y divide-rule">
              {range.ways.map((w) => (
                <tr key={w.id}>
                  <td className="py-1 pr-3 text-ink">{w.id}{w.primary ? " (primary)" : ""}</td>
                  <td className="num py-1 pr-3 text-right text-ink">{formatMeasure(w.value, range.measure)}</td>
                  <td className="py-1 text-ink-soft">{w.verdict ?? "none"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
      {diagnosis && <TriedList diagnosis={diagnosis} mono />}
    </div>
  );
}

/** The claim's deeper readings, shown below its body in every view; for a sentence of several parts, one block per part. */
export default function ClaimInsights({ view, result }: { view: RoleView; result: ClaimResult }) {
  if (!result.parts?.length) return <Readings view={view} result={result} />;
  const shown = result.parts.filter((p) => p.verdict !== "insufficient_evidence" && (countingRange(p) || restsOn(p) || diagnose(p)));
  if (!shown.length) return null;
  return (
    <>
      {shown.map((p) => (
        <section key={p.claim.id} aria-label={`About: ${p.claim.part_label || p.claim.text}`} className="mt-5">
          <p className="text-sm text-ink-soft">
            About <q className="reported text-ink">{p.claim.part_label || p.claim.text}</q>
          </p>
          <Readings view={view} result={p} />
        </section>
      ))}
    </>
  );
}

/** Nothing for a claim the data cannot check. */
function Readings({ view, result }: { view: RoleView; result: ClaimResult }) {
  if (result.verdict === "insufficient_evidence") return null;
  const range = countingRange(result);
  const rests = restsOn(result);
  const diagnosis = diagnose(result);
  const stated = statedFigure(result);
  if (!range && !rests && !diagnosis) return null;

  switch (view) {
    case "story":
      return (
        <>
          {range && <CountingStrip range={range} stated={stated} verdict={result.verdict} plain />}
          <StoryFindings range={range} rests={rests} diagnosis={diagnosis} stated={stated} />
        </>
      );
    case "checklist":
      return (
        <>
          {range && <CountingStrip range={range} stated={stated} verdict={result.verdict} />}
          {rests && (rests.leftOut > 0 || rests.measure === "percent") && <RestsOnBar rests={rests} />}
          {diagnosis && <CauseNote diagnosis={diagnosis} />}
        </>
      );
    case "evidence":
      return (
        <>
          {range && <CountingStrip range={range} stated={stated} verdict={result.verdict} />}
          {rests && <RestsOnBar rests={rests} />}
          {diagnosis && (
            <>
              <CauseNote diagnosis={diagnosis} />
              <TriedList diagnosis={diagnosis} />
            </>
          )}
        </>
      );
    case "raw":
      return <RawInsights range={range} rests={rests} diagnosis={diagnosis} />;
  }
}
