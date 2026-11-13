import { formatFact, solidityText, TYPE_LABEL } from "@/lib/claim-format";
import type { ClaimResult, ReleaseInfo } from "@/lib/types";
import { card } from "@/lib/ui";
import CodeBlock from "./CodeBlock";
import LadderText, { ladderChanges } from "./LadderText";
import RobustnessTable from "./RobustnessTable";
import SampleList from "./SampleList";
import SolidityTag from "./SolidityTag";
import StatementLabel from "./StatementLabel";
import VerdictBadge from "./VerdictBadge";

/** What every release contains, so "can't answer" explanations are honest about what *is* there. */
const RELEASE_CONTAINS = "clinical labels, survival times, mutations, copy number and protein levels";

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section aria-labelledby={id} className={card}>
      <h2 id={id} className="mb-4 text-xl font-semibold">
        {title}
      </h2>
      {children}
    </section>
  );
}

/** Python that reproduces the number: load the release, then the engine's own snippet. */
function runnableCode(code: string, releaseDir: string): string {
  const folder = releaseDir.trim() || "<release folder>";
  return `from second_opinion.release import load_release\nr = load_release(${JSON.stringify(folder)})\n\n${code.trim()}\n`;
}

interface Props {
  result: ClaimResult;
  release: ReleaseInfo;
  releaseDir: string;
}

/** Everything behind one claim's verdict, so a reviewer can check it without us. */
export default function EvidencePanel({ result, release, releaseDir }: Props) {
  const { claim, fact, verdict } = result;
  const checksum = (file: string) => release.files.find((f) => f.file === file)?.sha256 ?? "not in this release";
  const extra = fact?.extra ?? {};
  const skeptic = result.skeptic;

  return (
    <div className="grid gap-6">
      <header className={card}>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="font-mono text-2xl font-semibold">{claim.id}</h1>
          <span className="rounded-full border border-emerald-900/30 bg-emerald-50 px-2.5 py-0.5 text-sm font-medium text-emerald-950">
            {TYPE_LABEL[claim.type]}
          </span>
          <VerdictBadge verdict={verdict} />
          <SolidityTag result={result} />
        </div>
        <p className="mt-4 flex flex-wrap items-baseline gap-2 text-lg leading-8">
          <StatementLabel kind="Reported" />
          {claim.text}
        </p>
        {ladderChanges(result.ladder) && (
          <div className="mt-3 flex flex-wrap items-baseline gap-2">
            <StatementLabel kind="Interpretation" />
            <LadderText segments={result.ladder} />
          </div>
        )}
      </header>

      {verdict === "insufficient_evidence" && (
        <Section id="missing" title="What’s missing">
          <p className="leading-7">
            {result.missing_evidence ? (
              <>
                This data cannot answer the claim. <strong>Would need: {result.missing_evidence}.</strong>
              </>
            ) : (
              "This data cannot answer the claim."
            )}
          </p>
          {claim.clinical_terms.length > 0 && (
            <p className="mt-3 leading-7">
              Clinical or causal wording in the report:{" "}
              {claim.clinical_terms.map((t, i) => (
                <span key={t}>
                  {i > 0 && ", "}
                  <mark className="rounded bg-amber-100 px-1 text-amber-950">{t}</mark>
                </span>
              ))}
              . We flag it and do not repeat it as fact.
            </p>
          )}
          <p className="mt-3 text-slate-700">
            This release contains {RELEASE_CONTAINS}. It has no treatment, treatment-response or cause-and-effect
            records.
          </p>
        </Section>
      )}

      {fact && (
        <Section id="calculation" title="The calculation">
          <dl className="grid gap-3 sm:grid-cols-[12rem_1fr]">
            <dt className="font-medium text-slate-600">What we counted</dt>
            <dd>{fact.label}</dd>
            <dt className="flex items-center gap-2 font-medium text-slate-600">
              Result <StatementLabel kind="Computed" />
            </dt>
            <dd className="text-lg font-semibold">{formatFact(fact, claim.type)}</dd>
            {claim.type === "COMPARISON" && typeof extra.mean_a === "number" && typeof extra.mean_b === "number" && (
              <>
                <dt className="font-medium text-slate-600">Group means</dt>
                <dd>
                  {claim.params.group_a ?? "group A"}: {extra.mean_a.toFixed(3)} ({extra.n_a} samples) ·{" "}
                  {claim.params.group_b ?? "group B"}: {extra.mean_b.toFixed(3)} ({extra.n_b} samples)
                </dd>
              </>
            )}
            {verdict === "contradicted" && result.correct_value && (
              <>
                <dt className="font-medium text-slate-600">Correct value</dt>
                <dd className="font-semibold">{result.correct_value}</dd>
              </>
            )}
            {fact.unknown_count > 0 && (
              <>
                <dt className="font-medium text-slate-600">Left out as unknown</dt>
                <dd>
                  {fact.unknown_count.toLocaleString("en-US")} samples had no value for this, so they are not
                  counted.
                </dd>
              </>
            )}
            {typeof extra.note === "string" && (
              <>
                <dt className="font-medium text-slate-600">Note</dt>
                <dd>{extra.note}</dd>
              </>
            )}
            {result.limitation && (
              <>
                <dt className="font-medium text-slate-600">Limitation</dt>
                <dd>{result.limitation}</dd>
              </>
            )}
          </dl>
        </Section>
      )}

      {fact && (
        <Section id="sources" title="Source files">
          <table className="w-full table-fixed text-left text-sm">
            <caption className="sr-only">Files used for {claim.id}, with SHA-256 checksums</caption>
            <thead>
              <tr className="border-b border-slate-300 text-slate-700">
                <th scope="col" className="w-2/5 py-2 pr-3 font-semibold">
                  File (release {release.name})
                </th>
                <th scope="col" className="py-2 font-semibold">
                  SHA-256 checksum
                </th>
              </tr>
            </thead>
            <tbody>
              {fact.files.map((file) => (
                <tr key={file} className="border-b border-slate-200 align-top">
                  <td className="py-2 pr-3 font-mono break-all">{file}</td>
                  <td className="py-2 font-mono text-xs break-all text-slate-700">{checksum(file)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      )}

      {fact && fact.code.trim() && (
        <Section id="code" title="The exact code">
          <CodeBlock
            code={runnableCode(fact.code, releaseDir)}
            label="Python (pandas). Run it from the SecondOpinion folder to get the same number."
          />
        </Section>
      )}

      {fact && (
        <Section id="samples" title="Samples">
          <SampleList claimId={claim.id} sampleIds={fact.sample_ids} />
        </Section>
      )}

      {result.variants.length > 0 && (
        <Section id="robustness" title="Counted different ways">
          <p className="mb-4 leading-7 text-slate-700">{solidityText(result).long} Only the main definition sets the verdict; the others only test how solid it is.</p>
          <RobustnessTable result={result} />
        </Section>
      )}

      {skeptic && (
        <Section id="skeptic" title="Skeptic tests">
          <ul className="list-disc space-y-2 pl-6 leading-7">
            {skeptic.shuffle_p !== null && (
              <li>
                Shuffled the group labels 200 times: the real difference was larger than{" "}
                {Math.floor((1 - skeptic.shuffle_p) * 100)}% of the shuffled ones (p = {skeptic.shuffle_p.toFixed(3)}).
              </li>
            )}
            <li>
              Left out each of {skeptic.n_sites} hospitals one at a time:{" "}
              {skeptic.site_flips.length === 0
                ? "the direction never flips."
                : `the direction flips without site ${skeptic.site_flips.join(", ")}. One hospital may be driving the result.`}
            </li>
          </ul>
        </Section>
      )}
    </div>
  );
}
