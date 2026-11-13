import { formatFact, solidityText, TYPE_LABEL } from "@/lib/claim-format";
import type { ClaimResult, ReleaseInfo } from "@/lib/types";
import { chip, eyebrow, panel, tableHead } from "@/lib/ui";
import CodeBlock from "./CodeBlock";
import LadderText, { ladderChanges } from "./LadderText";
import Panel from "./Panel";
import RobustnessTable from "./RobustnessTable";
import SampleList, { SampleDownload } from "./SampleList";
import SolidityTag from "./SolidityTag";
import StatementLabel from "./StatementLabel";
import VerdictBadge from "./VerdictBadge";

/** What every release contains, so "can't answer" explanations are honest about what *is* there. */
const RELEASE_CONTAINS = "clinical labels, survival times, mutations, copy number and protein levels";

/** Python that reproduces the number: load the release, then the engine's own snippet. */
function runnableCode(code: string, releaseDir: string): string {
  const folder = releaseDir.trim() || "<release folder>";
  return `from second_opinion.release import load_release\nr = load_release(${JSON.stringify(folder)})\n\n${code.trim()}\n`;
}

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0 px-5 py-4">
      <dt className={eyebrow}>{label}</dt>
      <dd className="mt-1.5 text-sm text-slate-900">{children}</dd>
    </div>
  );
}

function DefRow({ label, children }: { label: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="grid gap-1 py-3 sm:grid-cols-[12rem_minmax(0,1fr)] sm:gap-6">
      <dt className="flex items-center gap-2 text-sm font-medium text-slate-600">{label}</dt>
      <dd className="min-w-0 text-[0.95rem] text-slate-900">{children}</dd>
    </div>
  );
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
  const headline =
    verdict === "contradicted" && result.correct_value
      ? result.correct_value
      : fact
        ? formatFact(fact, claim.type)
        : "Not computable";

  return (
    <div className="grid gap-6">
      <section aria-labelledby="claim-heading" className={panel}>
        <div className="flex flex-wrap items-center gap-2.5 border-b border-slate-200 px-5 py-4">
          <h1 id="claim-heading" className="font-mono text-xl font-bold text-slate-900">
            {claim.id}
          </h1>
          <span className={`${chip} border-slate-300 bg-white text-slate-700`}>{TYPE_LABEL[claim.type]}</span>
          <VerdictBadge verdict={verdict} />
          <SolidityTag result={result} />
        </div>
        <div className="grid gap-3 px-5 py-4">
          <p className="flex flex-wrap items-baseline gap-2 text-[1.05rem] leading-7">
            <StatementLabel kind="Reported" />
            {claim.text}
          </p>
          {ladderChanges(result.ladder) && (
            <div className="flex flex-wrap items-baseline gap-2">
              <StatementLabel kind="Interpretation" />
              <LadderText segments={result.ladder} />
            </div>
          )}
        </div>
        <dl className="grid grid-cols-2 divide-slate-200 border-t border-slate-200 bg-slate-50/70 md:grid-cols-4 md:divide-x">
          <Fact label="Result">
            <span className="text-base font-semibold tabular-nums">{headline}</span>
          </Fact>
          <Fact label="Robustness">{solidityText(result).short}</Fact>
          <Fact label="Samples">
            <span className="tabular-nums">{fact ? fact.sample_ids.length.toLocaleString("en-US") : "—"}</span>
          </Fact>
          <Fact label="Source files">
            <span className="tabular-nums">{fact ? `${fact.files.length} · release ${release.name}` : "—"}</span>
          </Fact>
        </dl>
      </section>

      {verdict === "insufficient_evidence" && (
        <Panel id="missing" title="What’s missing">
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
                  <mark className="rounded-sm bg-amber-100 px-1 text-amber-950">{t}</mark>
                </span>
              ))}
              . We flag it and do not repeat it as fact.
            </p>
          )}
          <p className="mt-3 text-sm text-slate-600">
            This release contains {RELEASE_CONTAINS}. It has no treatment, treatment-response or cause-and-effect
            records.
          </p>
        </Panel>
      )}

      {fact && (
        <Panel id="calculation" title="The calculation">
          <dl className="-my-3 divide-y divide-slate-100">
            <DefRow label="What we counted">{fact.label}</DefRow>
            <DefRow
              label={
                <>
                  Result <StatementLabel kind="Computed" />
                </>
              }
            >
              <span className="text-lg font-semibold tabular-nums">{formatFact(fact, claim.type)}</span>
            </DefRow>
            {claim.type === "COMPARISON" && typeof extra.mean_a === "number" && typeof extra.mean_b === "number" && (
              <DefRow label="Group means">
                <span className="tabular-nums">
                  {claim.params.group_a ?? "group A"}: {extra.mean_a.toFixed(3)} ({extra.n_a} samples) ·{" "}
                  {claim.params.group_b ?? "group B"}: {extra.mean_b.toFixed(3)} ({extra.n_b} samples)
                </span>
              </DefRow>
            )}
            {verdict === "contradicted" && result.correct_value && (
              <DefRow label="Correct value">
                <span className="font-semibold tabular-nums">{result.correct_value}</span>
              </DefRow>
            )}
            {fact.unknown_count > 0 && (
              <DefRow label="Left out as unknown">
                {fact.unknown_count.toLocaleString("en-US")} samples had no value for this, so they are not counted.
              </DefRow>
            )}
            {typeof extra.note === "string" && <DefRow label="Note">{extra.note}</DefRow>}
            {result.limitation && <DefRow label="Limitation">{result.limitation}</DefRow>}
          </dl>
        </Panel>
      )}

      {fact && (
        <Panel id="sources" title="Source files" description={`Release ${release.name}, verified by SHA-256 checksum.`} flush>
          <table className="w-full table-fixed text-left text-sm">
            <caption className="sr-only">Files used for {claim.id}, with SHA-256 checksums</caption>
            <thead className={tableHead}>
              <tr>
                <th scope="col" className="w-2/5 px-5 py-2.5">
                  File
                </th>
                <th scope="col" className="px-5 py-2.5">
                  SHA-256
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {fact.files.map((file) => (
                <tr key={file} className="align-top">
                  <td className="px-5 py-2.5 font-mono text-[0.8rem] break-all">{file}</td>
                  <td className="px-5 py-2.5 font-mono text-xs break-all text-slate-600">{checksum(file)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      )}

      {fact && fact.code.trim() && (
        <Panel id="code" title="The exact code">
          <CodeBlock
            code={runnableCode(fact.code, releaseDir)}
            label="Python (pandas). Run it from the SecondOpinion folder to get the same number."
          />
        </Panel>
      )}

      {fact && (
        <Panel
          id="samples"
          title="Samples"
          actions={<SampleDownload claimId={claim.id} sampleIds={fact.sample_ids} />}
        >
          <SampleList sampleIds={fact.sample_ids} />
        </Panel>
      )}

      {result.variants.length > 0 && (
        <Panel
          id="robustness"
          title="Counted different ways"
          description={`${solidityText(result).long} Only the main definition sets the verdict; the others test how solid it is.`}
          flush
        >
          <RobustnessTable result={result} />
        </Panel>
      )}

      {skeptic && (
        <Panel id="skeptic" title="Skeptic tests">
          <ul className="list-disc space-y-2 pl-5 leading-7">
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
        </Panel>
      )}
    </div>
  );
}
