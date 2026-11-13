import { Building2, Shuffle } from "lucide-react";
import { describeParams, formatFact, solidityText, TYPE_LABEL } from "@/lib/claim-format";
import type { ClaimResult, ReleaseInfo } from "@/lib/types";
import { sectionTitle } from "@/lib/ui";
import ClaimVsData from "./ClaimVsData";
import CodeBlock from "./CodeBlock";
import LadderText, { ladderChanges } from "./LadderText";
import RobustnessTable from "./RobustnessTable";
import SampleList from "./SampleList";
import GlossaryTerm from "./GlossaryTerm";
import SolidityExplained from "./SolidityExplained";
import StatementLabel from "./StatementLabel";
import VerdictBadge from "./VerdictBadge";

/** What every release contains, so "can't answer" explanations are honest about what *is* there. */
const RELEASE_CONTAINS = "clinical labels, survival times, mutations, copy number and protein levels";

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section aria-labelledby={id} className="mt-8 border-t border-rule pt-8">
      <h2 id={id} className={`${sectionTitle} mb-4`}>
        {title}
      </h2>
      {children}
    </section>
  );
}

/** A label and its value, in a two-column list that stacks on small screens. */
function Facts({ children }: { children: React.ReactNode }) {
  return <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-[11rem_1fr]">{children}</dl>;
}

function Term({ children }: { children: React.ReactNode }) {
  return <dt className="flex flex-wrap items-center gap-2 text-sm font-medium text-ink-soft sm:pt-0.5">{children}</dt>;
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
    <article>
      <header>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <h1 className="num font-mono text-3xl font-semibold tracking-tight text-ink">{claim.id}</h1>
          <VerdictBadge verdict={verdict} />
          <span className="inline-flex items-center rounded-stamp border border-rule-strong bg-sheet px-2.5 py-1 text-sm font-medium text-ink-soft">
            {TYPE_LABEL[claim.type]}
          </span>
          <SolidityExplained result={result} />
        </div>

        <div className="mt-6 max-w-prose border-l-2 border-rule-strong pl-4">
          <StatementLabel kind="Reported" />
          <p className="reported mt-1.5 text-ink">{claim.text}</p>
        </div>
        {ladderChanges(result.ladder) && (
          <div className="mt-4 max-w-prose border-l-2 border-pen pl-4">
            <StatementLabel kind="Interpretation" />
            <div className="mt-1.5">
              <LadderText segments={result.ladder} />
            </div>
          </div>
        )}
      </header>

      <ClaimVsData result={result} />

      {verdict === "insufficient_evidence" && (
        <Section id="missing" title="Why we cannot check it">
          <div className="max-w-prose space-y-3 leading-7">
            {claim.clinical_terms.length > 0 && (
              <p>
                Clinical or causal wording in the report:{" "}
                {claim.clinical_terms.map((t, i) => (
                  <span key={t}>
                    {i > 0 && ", "}
                    <mark className="rounded-stamp bg-insufficient-tint px-1 text-insufficient">{t}</mark>
                  </span>
                ))}
                . We flag it and do not repeat it as fact.
              </p>
            )}
            <p className="text-ink-soft">
              This release contains {RELEASE_CONTAINS}. It has no treatment, treatment-response or cause-and-effect
              records.
            </p>
          </div>
        </Section>
      )}

      {fact && (
        <Section id="calculation" title="How we calculated it">
          <div className="max-w-prose space-y-3 leading-7">
            <p>
              We counted <strong className="font-semibold">{fact.label}</strong>.
            </p>
            <p className="text-ink-soft">What we read from the sentence: {describeParams(claim)}.</p>
            {fact.unknown_count > 0 && (
              <p>
                {fact.unknown_count.toLocaleString("en-US")} samples had no value for this, so they are left out of the{" "}
                <GlossaryTerm term="denominator">denominator</GlossaryTerm>.
              </p>
            )}
            {typeof extra.note === "string" && <p>{extra.note}</p>}
          </div>
        </Section>
      )}

      {fact && (
        <Section id="numbers" title="Numbers">
          <Facts>
            <Term>
              Result <StatementLabel kind="Computed" />
            </Term>
            <dd className="num font-mono text-lg font-semibold text-ink">{formatFact(fact, claim.type)}</dd>
            {claim.type === "COMPARISON" && typeof extra.mean_a === "number" && typeof extra.mean_b === "number" && (
              <>
                <Term>Group means</Term>
                <dd className="num font-mono text-sm leading-7">
                  {claim.params.group_a ?? "group A"}: {extra.mean_a.toFixed(3)} ({extra.n_a} samples)
                  <br />
                  {claim.params.group_b ?? "group B"}: {extra.mean_b.toFixed(3)} ({extra.n_b} samples)
                </dd>
              </>
            )}
            {verdict === "contradicted" && result.correct_value && (
              <>
                <Term>Correct value</Term>
                <dd className="num font-mono text-lg font-semibold text-ink">{result.correct_value}</dd>
              </>
            )}
          </Facts>
        </Section>
      )}

      {fact && (
        <Section id="sources" title="Source files and checksums">
          <p className="mb-4 text-sm text-ink-soft">
            <GlossaryTerm term="release">Release</GlossaryTerm> <span className="num font-mono">{release.name}</span>. Each{" "}
            <GlossaryTerm term="checksum">checksum</GlossaryTerm> is the file&apos;s SHA-256, shown
            in full so you can compare it with your own copy.
          </p>
          <ul aria-label={`Files used for ${claim.id}, with SHA-256 checksums`} className="divide-y divide-rule">
            {fact.files.map((file) => (
              <li key={file} className="py-3">
                <p className="num font-mono text-sm font-medium break-all text-ink">{file}</p>
                <p className="mt-1 text-sm text-ink-soft">
                  <span className="mr-2">SHA-256</span>
                  <span className="num font-mono text-[0.8125rem] break-all text-ink select-all">{checksum(file)}</span>
                </p>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {fact && fact.code.trim() && (
        <Section id="code" title="Code">
          <CodeBlock
            code={runnableCode(fact.code, releaseDir)}
            label="Python (pandas). Run it from the SecondOpinion folder to get the same number."
          />
        </Section>
      )}

      {fact && (
        <Section id="samples" title="Samples used">
          <SampleList claimId={claim.id} sampleIds={fact.sample_ids} denominator={fact.denominator} />
        </Section>
      )}

      {result.variants.length > 0 && (
        <Section id="robustness" title="Count it differently">
          <p className="mb-4 max-w-prose leading-7 text-ink-soft">
            {solidityText(result).long} Each row is one <GlossaryTerm term="variant">way of counting</GlossaryTerm>:
            which <GlossaryTerm term="subtypeCall">subtype call</GlossaryTerm>, who is counted and which samples. Only the
            main definition sets the verdict; the others only test how solid it is.
          </p>
          <RobustnessTable result={result} />
        </Section>
      )}

      {skeptic && (
        <Section id="skeptic" title="Skeptic tests">
          <ul className="max-w-prose space-y-3 leading-7">
            {skeptic.shuffle_p !== null && (
              <li className="flex gap-3">
                <Shuffle aria-hidden="true" className="mt-1.5 size-4 shrink-0 text-ink-soft" />
                <span>
                  Shuffled the group labels 200 times: the real difference was larger than{" "}
                  {Math.floor((1 - skeptic.shuffle_p) * 100)}% of the shuffled ones (p ={" "}
                  <span className="num font-mono">{skeptic.shuffle_p.toFixed(3)}</span>).
                </span>
              </li>
            )}
            <li className="flex gap-3">
              <Building2 aria-hidden="true" className="mt-1.5 size-4 shrink-0 text-ink-soft" />
              <span>
                Left out each of {skeptic.n_sites} hospitals one at a time:{" "}
                {skeptic.site_flips.length === 0
                  ? "the direction never flips."
                  : `the direction flips without site ${skeptic.site_flips.join(", ")}. One hospital may be driving the result.`}
              </span>
            </li>
          </ul>
        </Section>
      )}

      {result.limitation && (
        <Section id="limitation" title="Limitation">
          <p className="max-w-prose leading-7">{result.limitation}</p>
        </Section>
      )}
    </article>
  );
}
