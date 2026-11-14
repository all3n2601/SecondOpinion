import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { markReport, type MarkSegment, type MarkedReport, type ReportBlock } from "./report-marks";

type TestClaim = { id: string; text: string; original_text?: string; sentence_index: number };

/** Claims in report order, `original_text` as the extractor would give it. */
function claims(...sentences: string[]): TestClaim[] {
  return sentences.map((s, i) => ({ id: `C${i + 1}`, text: s.replace(/\*\*|`/g, ""), original_text: s, sentence_index: i }));
}

function paragraphs(report: MarkedReport): MarkSegment[][] {
  return report.blocks.flatMap((b) => (b.kind === "paragraph" ? [b.segments] : []));
}

function segmentsOf(block: ReportBlock): MarkSegment[] {
  if (block.kind === "paragraph") return block.segments;
  if (block.kind === "table") return block.rows.flat();
  return [];
}

function claimSegments(report: MarkedReport): Array<Extract<MarkSegment, { kind: "claim" }>> {
  return report.blocks.flatMap(segmentsOf).flatMap((s) => (s.kind === "claim" ? [s] : []));
}

const squash = (s: string) => s.replace(/\s+/g, "");

describe("markReport: real extractor output", () => {
  const dir = join(__dirname, "__fixtures__", "report-marks");
  const fixtures = readdirSync(dir).filter((f) => f.endsWith(".json"));

  it("has fixtures to check", () => {
    expect(fixtures.length).toBeGreaterThanOrEqual(5);
  });

  for (const file of fixtures) {
    const { reportText, claims: given } = JSON.parse(readFileSync(join(dir, file), "utf-8")) as {
      reportText: string;
      claims: TestClaim[];
    };

    describe(file, () => {
      const report = markReport(reportText, given);
      const marked = claimSegments(report);

      it("places every claim, once each, in claim order", () => {
        expect(report.unplaced).toEqual([]);
        expect(marked.map((s) => s.claimId)).toEqual(given.map((c) => c.id));
      });

      it("marks exactly the claim's words", () => {
        for (const seg of marked) {
          const claim = given.find((c) => c.id === seg.claimId)!;
          const want = (claim.original_text || claim.text).replace(/\[([^\]]+)\]\([^)]*\)/g, "$1").replace(/\*\*|__|`/g, "");
          // A table row's claim drops empty cells and may add a "%" from the header.
          const loose = (s: string) => squash(s).replace(/[|%]/g, "");
          expect(loose(seg.text)).toBe(loose(want));
        }
      });

      it("keeps every word of the report body outside headings", () => {
        const body = reportText
          .split(/\r?\n/)
          .filter((line) => !/^\s{0,3}#{1,6}(\s|$)/.test(line) && !/^\s*\|?[\s:|]*-{2,}[\s:|-]*$/.test(line))
          .join(" ")
          .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
          .replace(/\*\*|__|`/g, "");
        const shown = report.blocks
          .flatMap(segmentsOf)
          .map((s) => s.text)
          .join(" ");
        expect(shown.split(/\s+/).filter(Boolean)).toEqual(body.split(/\s+/).filter(Boolean));
      });

      it("never emits an empty segment or two text segments in a row", () => {
        for (const block of report.blocks) {
          const runs = block.kind === "table" ? block.rows : block.kind === "paragraph" ? [block.segments] : [];
          for (const run of runs) {
            run.forEach((s, i) => {
              expect(s.text).not.toBe("");
              if (i > 0) expect(s.kind === "text" && run[i - 1].kind === "text").toBe(false);
            });
          }
        }
      });
    });
  }
});

describe("markReport: blocks", () => {
  it("turns headings, code, rules and comments into display blocks", () => {
    const text = [
      "# Title #",
      "",
      "Intro line.",
      "",
      "---",
      "<!-- a note -->",
      "```",
      "x = 1",
      "```",
      "### Methods",
    ].join("\n");
    expect(markReport(text, []).blocks).toEqual([
      { kind: "heading", level: 1, text: "Title" },
      { kind: "paragraph", segments: [{ kind: "text", text: "Intro line." }] },
      { kind: "code", text: "x = 1" },
      { kind: "heading", level: 3, text: "Methods" },
    ]);
  });

  it("joins a wrapped sentence and marks it across the line break", () => {
    const report = markReport("Of the 1,101 tumors, 535 have\nall five data types. Next.", claims("Of the 1,101 tumors, 535 have all five data types."));
    expect(paragraphs(report)).toEqual([
      [
        { kind: "claim", text: "Of the 1,101 tumors, 535 have all five data types.", claimId: "C1" },
        { kind: "text", text: " Next." },
      ],
    ]);
  });

  it("finds a blockquoted sentence over two lines and strips the > markers", () => {
    const report = markReport("> Luminal A makes up\n> about 62% of tumors.", claims("Luminal A makes up about 62% of tumors."));
    expect(report.unplaced).toEqual([]);
    expect(paragraphs(report)).toEqual([[{ kind: "claim", text: "Luminal A makes up about 62% of tumors.", claimId: "C1" }]]);
  });

  it("finds a table row whose % came from the header, and drops the separator", () => {
    const text = "| Group | n | % |\n|---|---|---|\n| Luminal A | 421 | 49.9 |\n| Luminal B | 192 | 22.7 |";
    const report = markReport(text, claims("Luminal A | 421 | 49.9%"));
    expect(report.unplaced).toEqual([]);
    expect(report.blocks).toEqual([
      {
        kind: "table",
        rows: [
          [{ kind: "text", text: "| Group | n | % |" }],
          [
            { kind: "text", text: "| " },
            { kind: "claim", text: "Luminal A | 421 | 49.9", claimId: "C1" },
            { kind: "text", text: " |" },
          ],
          [{ kind: "text", text: "| Luminal B | 192 | 22.7 |" }],
        ],
      },
    ]);
  });

  it("lists a claim edited out of the report as unplaced and still places the rest", () => {
    const report = markReport("First has 10 samples. Third has 30 samples.", claims("First has 10 samples.", "Second has 20 samples.", "Third has 30 samples."));
    expect(report.unplaced).toEqual(["C2"]);
    expect(claimSegments(report).map((s) => s.claimId)).toEqual(["C1", "C3"]);
  });

  it("marks the later copy of a repeated sentence when the claim comes after", () => {
    const text = "Most tumors are ER-positive. 535 have all data. Most tumors are ER-positive.";
    const given = [
      { id: "C1", text: "535 have all data.", sentence_index: 1 },
      { id: "C2", text: "Most tumors are ER-positive.", sentence_index: 2 },
    ];
    expect(paragraphs(markReport(text, given))).toEqual([
      [
        { kind: "text", text: "Most tumors are ER-positive. " },
        { kind: "claim", text: "535 have all data.", claimId: "C1" },
        { kind: "text", text: " " },
        { kind: "claim", text: "Most tumors are ER-positive.", claimId: "C2" },
      ],
    ]);
  });

  it("sorts claims by sentence_index before matching", () => {
    const given = [
      { id: "C2", text: "B has 2.", sentence_index: 1 },
      { id: "C1", text: "A has 1.", sentence_index: 0 },
    ];
    const report = markReport("A has 1. B has 2.", given);
    expect(report.unplaced).toEqual([]);
    expect(claimSegments(report).map((s) => s.claimId)).toEqual(["C1", "C2"]);
  });

  it("keeps line breaks between list items and joins wrapped items", () => {
    const text = "Findings:\n- About half (50%) are Luminal A.\n- Two in five carry\n  a TP53 mutation.\n1. Third item.";
    const report = markReport(text, claims("About half (50%) are Luminal A.", "Two in five carry a TP53 mutation."));
    expect(paragraphs(report)).toEqual([
      [
        { kind: "text", text: "Findings:\n- " },
        { kind: "claim", text: "About half (50%) are Luminal A.", claimId: "C1" },
        { kind: "text", text: "\n- " },
        { kind: "claim", text: "Two in five carry a TP53 mutation.", claimId: "C2" },
        { kind: "text", text: "\n1. Third item." },
      ],
    ]);
  });

  it("strips bold, code ticks and link syntax inside a claim", () => {
    const sentence = "**Luminal A** is the largest `subtype_rna` group ([table](https://x.org/t)).";
    const report = markReport(`${sentence} ![chart](c.png)`, claims(sentence));
    expect(paragraphs(report)).toEqual([
      [
        { kind: "claim", text: "Luminal A is the largest subtype_rna group (table).", claimId: "C1" },
        { kind: "text", text: " chart" },
      ],
    ]);
  });

  it("handles CRLF line endings", () => {
    const text = "# Brief\r\n\r\nOf the 1,101 tumors, 535 have\r\nall data. Next.\r\n\r\n| A | 1 |\r\n|---|---|\r\n| B | 2 |\r\n";
    const report = markReport(text, claims("Of the 1,101 tumors, 535 have all data.", "B | 2"));
    expect(report.unplaced).toEqual([]);
    expect(report.blocks).toEqual([
      { kind: "heading", level: 1, text: "Brief" },
      {
        kind: "paragraph",
        segments: [
          { kind: "claim", text: "Of the 1,101 tumors, 535 have all data.", claimId: "C1" },
          { kind: "text", text: " Next." },
        ],
      },
      {
        kind: "table",
        rows: [
          [{ kind: "text", text: "| A | 1 |" }],
          [{ kind: "text", text: "| " }, { kind: "claim", text: "B | 2", claimId: "C2" }, { kind: "text", text: " |" }],
        ],
      },
    ]);
  });

  it("does not match a claim across a paragraph break", () => {
    const report = markReport("A has 1\n\nsample.", claims("A has 1 sample."));
    expect(report.unplaced).toEqual(["C1"]);
  });

  it("falls back to `text` when original_text is empty", () => {
    const report = markReport("A has 1 sample.", [{ id: "C1", text: "A has 1 sample.", original_text: "", sentence_index: 0 }]);
    expect(report.unplaced).toEqual([]);
  });
});
