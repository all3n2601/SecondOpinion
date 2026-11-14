import VerdictBadge from "@/components/VerdictBadge";
import type { Verdict } from "@/lib/types";
import { Stagger, StaggerItem } from "./motion";
import Section from "./Section";

function N({ children }: { children: React.ReactNode }) {
  return <span className="num font-mono text-[0.9em]">{children}</span>;
}

const ROWS: { id: string; verdict: Verdict; finding: React.ReactNode }[] = [
  {
    id: "C1",
    verdict: "supported",
    finding: (
      <>
        <N>535 of 1,101</N> primary tumors have all the data layers.
      </>
    ),
  },
  {
    id: "C2",
    verdict: "contradicted",
    finding: (
      <>
        The report said about 62%. The data shows <N>49.9% (421 of 844)</N>, and that holds under all 8 ways of
        counting (robust).
      </>
    ),
  },
  {
    id: "C3",
    verdict: "insufficient_evidence",
    finding: (
      <>
        The data has no treatment or response records. Checking this would need treatment and treatment-response
        data.
      </>
    ),
  },
];

/** A static, honest example of the result: the practice report's three claims with their verdicts. */
export default function FinishedPreview() {
  return (
    <Section
      id="preview"
      title="What a finished audit looks like"
      intro="One verdict per claim, each with the reason in plain words. A person then reviews every one."
    >
      <figure>
        <Stagger
          as="ol"
          label="Practice report, three claims"
          className="divide-y divide-rule overflow-hidden rounded-panel border border-rule bg-sheet shadow-[0_24px_60px_-40px_rgb(158_42_94/0.35)]"
        >
          {ROWS.map((row) => (
            <StaggerItem
              as="li"
              key={row.id}
              className="grid gap-x-5 gap-y-2 p-4 sm:grid-cols-[2.5rem_13rem_minmax(0,1fr)] sm:items-start sm:p-5"
            >
              <span className="num font-mono text-sm font-medium text-ink-soft sm:pt-1">{row.id}</span>
              <div>
                <VerdictBadge verdict={row.verdict} />
              </div>
              <p className="max-w-prose">{row.finding}</p>
            </StaggerItem>
          ))}
        </Stagger>
        <figcaption className="mt-3 text-sm text-ink-soft">
          Example: the practice report, audited against the TCGA-BRCA release. Your own report gets the same
          treatment.
        </figcaption>
      </figure>
    </Section>
  );
}
