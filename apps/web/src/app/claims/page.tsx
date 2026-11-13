"use client";

import { CircleAlert, ClipboardCheck, FileText, LoaderCircle } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import ClaimRow from "@/components/ClaimRow";
import { runAudit } from "@/lib/api";
import { useAudit } from "@/lib/audit-context";
import { buttonPrimary, buttonSecondary, pageTitle, pageWidth, sectionTitle } from "@/lib/ui";

export default function ClaimsPage() {
  const router = useRouter();
  const { reportText, sentences, claims, toggleClaim, releaseDir, audit, setAudit, hydrated } = useAudit();
  const [pendingIndex, setPendingIndex] = useState<number | null>(null);
  const [running, setRunning] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function toggle(index: number) {
    setPendingIndex(index);
    setMessage(null);
    try {
      await toggleClaim(index);
    } catch (e) {
      setMessage((e as Error).message);
    } finally {
      setPendingIndex(null);
    }
  }

  async function startAudit() {
    setRunning(true);
    setMessage(null);
    try {
      setAudit(await runAudit(releaseDir.trim(), claims));
      router.push("/board");
    } catch (e) {
      setMessage((e as Error).message);
      setRunning(false);
    }
  }

  const claimFor = (claimId: string | null) => (claimId ? claims.find((c) => c.id === claimId) : undefined);
  const plural = (n: number) => `${n} claim${n === 1 ? "" : "s"}`;
  const noRelease = !releaseDir.trim();

  // Wait for the saved state to load, so a reload does not flash "No report yet".
  if (!hydrated) return <main className={pageWidth} aria-busy="true" />;

  if (sentences.length === 0 && reportText.trim() === "") {
    return (
      <main className={pageWidth}>
        <h1 className={pageTitle}>Claims</h1>
        <section className="mt-8 max-w-prose border-y border-rule py-6">
          <div className="flex items-start gap-3">
            <FileText aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-ink-soft" />
            <div>
              <h2 className={sectionTitle}>No report yet</h2>
              <p className="mt-1 text-ink-soft">Add a report and press Find claims.</p>
              <Link href="/" className={`${buttonSecondary} mt-4`}>
                Go to Start
              </Link>
            </div>
          </div>
        </section>
      </main>
    );
  }

  const disabledReason = !running && claims.length === 0 ? "Tick at least one sentence to run the audit." : null;

  return (
    <main className={pageWidth}>
      <h1 className={pageTitle}>Claims</h1>
      <p className="mt-3 max-w-prose text-ink-soft">
        Every sentence of the report, in order. Ticked sentences will be checked against the data. Untick a sentence
        that is not a real claim, or tick one we missed.
      </p>

      <div className="mt-8 max-w-[44rem]">
        <p aria-live="polite" className="font-medium text-ink">
          {sentences.length === 0
            ? "No sentences were found in the report."
            : `${claims.length} of ${sentences.length} sentence${sentences.length === 1 ? "" : "s"} will be checked`}
        </p>
        {claims.length === 0 && sentences.length > 0 && (
          <p className="mt-1 flex items-start gap-2 text-ink-soft">
            <CircleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            Nothing checkable found. Tick any sentence to check it.
          </p>
        )}

        <ol aria-label="Report sentences" className="mt-4 divide-y divide-rule border-y border-rule">
          {sentences.map((s) => (
            <ClaimRow
              key={s.index}
              sentence={s}
              claim={claimFor(s.claim_id)}
              disabled={pendingIndex !== null || running}
              busy={pendingIndex === s.index}
              onToggle={() => toggle(s.index)}
            />
          ))}
        </ol>

        <div className="sticky bottom-0 mt-6 flex flex-wrap items-center gap-x-4 gap-y-3 border-t border-rule-strong bg-paper py-4">
          <button
            type="button"
            onClick={startAudit}
            disabled={claims.length === 0 || noRelease || running || pendingIndex !== null}
            className={buttonPrimary}
          >
            {running ? (
              <LoaderCircle aria-hidden="true" className="size-5 animate-spin" />
            ) : (
              <ClipboardCheck aria-hidden="true" className="size-5" />
            )}
            {running ? `Checking ${plural(claims.length)}` : "Run audit"}
          </button>
          {disabledReason && <p className="text-sm text-ink-soft">{disabledReason}</p>}
          {noRelease && (
            <p className="text-sm text-ink-soft">
              Choose a release folder on{" "}
              <Link href="/" className="font-medium text-pen underline underline-offset-4">
                Start
              </Link>{" "}
              first.
            </p>
          )}
          {audit && !running && (
            <Link href="/board" className="text-sm font-medium text-pen underline underline-offset-4">
              See the current audit board
            </Link>
          )}
          <p aria-live="polite" className="text-sm font-medium">
            {running && <span className="sr-only">Checking {plural(claims.length)}…</span>}
            {message && (
              <span className="flex items-start gap-2 text-contradicted">
                <CircleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
                {message}
              </span>
            )}
          </p>
        </div>
      </div>
    </main>
  );
}
