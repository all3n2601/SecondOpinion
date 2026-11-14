// The report as written, cut into display blocks, with every audited claim marked where it sits.
// Pure functions: no React, no fetch. The claims come from second_opinion/extract.py, whose `original_text`
// is the sentence as written with whitespace runs collapsed, blockquote `> ` and bullet markers dropped from
// line starts, and (for a table row) the cells rejoined as "Luminal A | 421 | 49.9%". So a claim is found by
// comparing non-whitespace characters only, walking forward in report order, and the line structure below
// mirrors the extractor's `_blocks` so a claim never straddles two display blocks.

import type { Claim } from "./types";

export type MarkSegment =
  | { kind: "text"; text: string }
  | { kind: "claim"; text: string; claimId: string };

export type ReportBlock =
  | { kind: "heading"; level: 1 | 2 | 3 | 4 | 5 | 6; text: string }
  /** Prose, bullet lists, blockquotes; a "\n" inside a text segment is a line break to keep (between list items). */
  | { kind: "paragraph"; segments: MarkSegment[] }
  /** One entry per table line as written (trimmed); the separator row |---|---| is dropped. */
  | { kind: "table"; rows: MarkSegment[][] }
  | { kind: "code"; text: string };

export interface MarkedReport {
  blocks: ReportBlock[];
  /** Ids of claims that could not be found in the text (e.g. the report was edited after the audit), in claim order. */
  unplaced: string[];
}

type MarkableClaim = Pick<Claim, "id" | "text" | "original_text" | "sentence_index">;

// The extractor's line patterns (second_opinion/extract.py), kept identical so both sides agree on blocks.
const FENCE = /^\s*(```|~~~)/;
const HEADING = /^\s{0,3}(#{1,6})(?:\s|$)/;
const RULE = /^\s{0,3}([-*_])(\s*\1){2,}\s*$/;
const TABLE_SEPARATOR = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/;
const BULLET = /^\s*(?:[-*+]|\d{1,3}[.)])\s+/;
const BLOCKQUOTE = /^\s*(>\s?)+/;
const HTML_COMMENT = /<!--[\s\S]*?-->/g;

type LineKind =
  | "fence" // an opening or closing ``` / ~~~ line
  | "code" // inside a fence
  | "heading"
  | "break" // blank, rule, or a separator that is not part of a table
  | "table-separator"
  | "table"
  | "bullet" // starts a list item
  | "text"; // prose, or the continuation of the paragraph or list item above

interface Line {
  kind: LineKind;
  /** Raw offsets: the line without its line ending. */
  start: number;
  end: number;
  /** Where the content starts once a blockquote prefix is skipped. */
  contentStart: number;
  /** For a bullet: where the item's words start, after the marker. */
  wordsStart: number;
  /** For a heading: how many `#`. */
  level: number;
}

/** Split on \r\n, \n or \r, keeping raw offsets. */
function splitLines(text: string): Array<{ start: number; end: number }> {
  const lines: Array<{ start: number; end: number }> = [];
  let start = 0;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (c === "\n" || c === "\r") {
      lines.push({ start, end: i });
      if (c === "\r" && text[i + 1] === "\n") i++;
      start = i + 1;
    }
  }
  lines.push({ start, end: text.length });
  return lines;
}

/** Each line's role, in the same order of checks as the extractor's `_blocks`. */
function classifyLines(text: string): Line[] {
  let inFence = false;
  return splitLines(text).map(({ start, end }) => {
    const raw = text.slice(start, end);
    const base: Line = { kind: "text", start, end, contentStart: start, wordsStart: start, level: 0 };
    if (FENCE.test(raw)) {
      inFence = !inFence;
      return { ...base, kind: "fence" };
    }
    if (inFence) return { ...base, kind: "code" };

    const quote = BLOCKQUOTE.exec(raw);
    const contentStart = start + (quote ? quote[0].length : 0);
    const line = text.slice(contentStart, end);
    const stripped = line.trim();
    const at = { ...base, contentStart, wordsStart: contentStart };
    if (TABLE_SEPARATOR.test(line) && stripped.startsWith("|")) return { ...at, kind: "table-separator" };
    const heading = HEADING.exec(line);
    if (heading) return { ...at, kind: "heading", level: heading[1].length };
    if (!stripped || RULE.test(line) || TABLE_SEPARATOR.test(line)) return { ...at, kind: "break" };
    if (stripped.startsWith("|")) return { ...at, kind: "table" };
    const bullet = BULLET.exec(line);
    if (bullet) return { ...at, kind: "bullet", wordsStart: contentStart + bullet[0].length };
    return at;
  });
}

// ---- Finding each claim in the text ----

/** Non-whitespace characters of the searchable text, each with its raw offset. A NUL marks a block edge. */
interface Skeleton {
  chars: string;
  where: number[];
}

const EDGE = "\u0000";

function isSpace(c: string): boolean {
  return /\s/.test(c);
}

/**
 * The report's searchable characters. Fences, headings, rules and separators are left out (claims never sit
 * there), and an EDGE goes wherever the extractor starts a new block, so a match cannot run across two blocks.
 * `loose` also drops `|` and `%`: a table row's claim has its empty cells removed and may carry a `%` the
 * extractor added from the column header.
 */
function reportSkeleton(text: string, lines: Line[], loose: boolean): Skeleton {
  let chars = "";
  const where: number[] = [];
  const edge = () => {
    if (chars.length && chars[chars.length - 1] !== EDGE) {
      chars += EDGE;
      where.push(where[where.length - 1]);
    }
  };
  for (const line of lines) {
    if (line.kind !== "text") edge();
    if (line.kind !== "text" && line.kind !== "bullet" && line.kind !== "table") continue;
    for (let i = line.wordsStart; i < line.end; i++) {
      const c = text[i];
      if (isSpace(c) || (loose && (c === "|" || c === "%"))) continue;
      chars += c;
      where.push(i);
    }
    if (line.kind === "table") edge();
  }
  return { chars, where };
}

function needleSkeleton(needle: string, loose: boolean): string {
  let out = "";
  for (const c of needle) {
    if (isSpace(c) || c === EDGE || (loose && (c === "|" || c === "%"))) continue;
    out += c;
  }
  return out;
}

/** The first skeleton index whose raw offset is at or after `offset`. */
function skeletonIndexAt(skeleton: Skeleton, offset: number): number {
  let lo = 0;
  let hi = skeleton.where.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (skeleton.where[mid] < offset) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}

/** Inclusive raw span of the first match at or after `cursor`, or null. */
function find(skeleton: Skeleton, needle: string, cursor: number): [number, number] | null {
  if (!needle) return null;
  const at = skeleton.chars.indexOf(needle, skeletonIndexAt(skeleton, cursor));
  if (at < 0) return null;
  return [skeleton.where[at], skeleton.where[at + needle.length - 1]];
}

interface Span {
  start: number;
  end: number; // inclusive
  claimId: string;
}

function placeClaims(text: string, lines: Line[], claims: ReadonlyArray<MarkableClaim>): { spans: Span[]; unplaced: Set<string> } {
  const strict = reportSkeleton(text, lines, false);
  const loose = reportSkeleton(text, lines, true);
  // Report order; the sort is stable, so claims sharing an index keep their given order.
  const ordered = [...claims].sort((a, b) => a.sentence_index - b.sentence_index);
  const spans: Span[] = [];
  const unplaced = new Set<string>();
  let cursor = 0;
  for (const claim of ordered) {
    const needle = claim.original_text || claim.text;
    const hit = find(strict, needleSkeleton(needle, false), cursor) ?? find(loose, needleSkeleton(needle, true), cursor);
    const last = spans[spans.length - 1];
    // Matching from the cursor already rules out overlap; the check guards against a future change to that.
    if (!hit || (last && hit[0] <= last.end)) {
      unplaced.add(claim.id);
      continue;
    }
    spans.push({ start: hit[0], end: hit[1], claimId: claim.id });
    cursor = hit[1] + 1;
  }
  return { spans, unplaced };
}

// ---- Display ----

/**
 * Markdown we strip for display: links and images keep their words; bold, `__` and code ticks go, and so does a
 * `*` pair around words (`*fictional*`) but not a lone `*` or one inside a word or number (`2*3*4`). Single `_` is
 * left alone: it is common in column names like protein_rppa.
 */
function cleanInline(text: string): string {
  return text
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/\*\*|__|`/g, "")
    .replace(/(?<![\w*])\*(?=\S)([^*\n]+?)(?<=\S)\*(?![\w*])/g, "$1");
}

/** Builds segments one character at a time, each tagged with the claim covering it (or null). */
class SegmentBuilder {
  private runs: Array<{ text: string; claimId: string | null }> = [];

  push(text: string, claimId: string | null): void {
    const last = this.runs[this.runs.length - 1];
    if (last && last.claimId === claimId) last.text += text;
    else this.runs.push({ text, claimId });
  }

  build(): MarkSegment[] {
    const out: MarkSegment[] = [];
    for (const run of this.runs) {
      // Clean per run, after splitting: offsets were mapped on the raw text, so cleanup must not move them.
      const text = cleanInline(run.text);
      if (!text) continue;
      const last = out[out.length - 1];
      if (run.claimId === null && last?.kind === "text") last.text += text;
      else if (run.claimId === null) out.push({ kind: "text", text });
      else out.push({ kind: "claim", text, claimId: run.claimId });
    }
    // Collapse spaces (not the kept "\n" line breaks) once neighbouring text runs are joined.
    for (const segment of out) segment.text = segment.text.replace(/[^\S\n]+/g, " ");
    return out;
  }
}

/** The raw span `[from, to)` trimmed of whitespace. */
function trimmed(text: string, from: number, to: number): [number, number] {
  while (from < to && isSpace(text[from])) from++;
  while (to > from && isSpace(text[to - 1])) to--;
  return [from, to];
}

function headingText(text: string, line: Line): string {
  const words = text
    .slice(line.contentStart, line.end)
    .replace(/^\s*#{1,6}/, "")
    .replace(/\s#+\s*$/, "");
  return cleanInline(words).replace(/\s+/g, " ").trim();
}

/**
 * Cut a report into display blocks and mark every claim found in it.
 *
 * Claims are matched in report order (`sentence_index`) on their non-whitespace characters, then on the same
 * without `|` and `%` (table rows). A claim not found after the previous one is listed in `unplaced`.
 */
export function markReport(reportText: string, claims: ReadonlyArray<MarkableClaim>): MarkedReport {
  // The extractor drops HTML comments before anything else. Blanking them (newlines kept) drops them here too
  // while every offset still points into the report as given.
  const text = reportText.replace(HTML_COMMENT, (m) => m.replace(/[^\r\n]/g, " "));
  const lines = classifyLines(text);
  const { spans, unplaced } = placeClaims(text, lines, claims);

  const claimAt: Array<string | null> = new Array<string | null>(text.length).fill(null);
  for (const span of spans) for (let i = span.start; i <= span.end; i++) claimAt[i] = span.claimId;

  /** Adds the trimmed raw span to a builder, each character tagged with its claim. */
  const addRange = (builder: SegmentBuilder, from: number, to: number) => {
    for (let i = from; i < to; i++) builder.push(text[i], claimAt[i]);
  };

  const blocks: ReportBlock[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (line.kind === "fence" || line.kind === "code") {
      const body: string[] = [];
      if (line.kind === "fence") i++;
      while (i < lines.length && lines[i].kind === "code") body.push(text.slice(lines[i].start, lines[i++].end));
      if (i < lines.length && lines[i].kind === "fence") i++; // the closing fence
      if (body.length) blocks.push({ kind: "code", text: body.join("\n") });
      continue;
    }
    if (line.kind === "heading") {
      blocks.push({ kind: "heading", level: line.level as 1 | 2 | 3 | 4 | 5 | 6, text: headingText(text, line) });
      i++;
      continue;
    }
    if (line.kind === "break") {
      i++;
      continue;
    }
    if (line.kind === "table" || line.kind === "table-separator") {
      const rows: MarkSegment[][] = [];
      for (; i < lines.length && (lines[i].kind === "table" || lines[i].kind === "table-separator"); i++) {
        if (lines[i].kind === "table-separator") continue;
        const builder = new SegmentBuilder();
        addRange(builder, ...trimmed(text, lines[i].contentStart, lines[i].end));
        rows.push(builder.build());
      }
      if (rows.length) blocks.push({ kind: "table", rows });
      continue;
    }

    // A paragraph: prose and list items up to the next blank line or other block.
    const builder = new SegmentBuilder();
    let prevEnd = -1; // raw offset of the previous line's last character
    for (; i < lines.length && (lines[i].kind === "text" || lines[i].kind === "bullet"); i++) {
      const [from, to] = trimmed(text, lines[i].contentStart, lines[i].end);
      if (from === to) continue;
      if (prevEnd >= 0) {
        // The line break belongs to a claim only when that claim runs on into this line.
        const joined = claimAt[prevEnd] !== null && claimAt[prevEnd] === claimAt[from] ? claimAt[from] : null;
        builder.push(lines[i].kind === "bullet" ? "\n" : " ", joined);
      }
      addRange(builder, from, to);
      prevEnd = to - 1;
    }
    const segments = builder.build();
    if (segments.length) blocks.push({ kind: "paragraph", segments });
  }

  return { blocks, unplaced: claims.filter((c) => unplaced.has(c.id)).map((c) => c.id) };
}
