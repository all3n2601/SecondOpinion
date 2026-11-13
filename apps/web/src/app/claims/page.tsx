"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import ClaimRow from "@/components/ClaimRow";
import PageHeader from "@/components/PageHeader";
import Panel from "@/components/Panel";
import { runAudit } from "@/lib/api";
import { useAudit } from "@/lib/audit-context";
import { buttonPrimary, container, linkText } from "@/lib/ui";

const plural = (n: number) => `${n} claim${n === 1 ? "" : "s"}`;

export default function ClaimsPage() {
  const router = useRouter();
  const { sentences, claims, toggleClaim, releaseDir, audit, setAudit } = useAudit();
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
  const noRelease = !releaseDir.trim();
  const header = (
    <PageHeader
      kicker="Step 2 of 5 · Claims"
      title="Confirm the claims to check"
      description="Every sentence of the report, in order. Ticked sentences are checked against the data. Untick a sentence that is not a real claim, or tick one we missed."
    />
  );

  if (sentences.length === 0) {
    return (
      <main className={`${container} py-8`}>
        {header}
        <Panel id="no-report" title="No report yet" className="mt-6">
          <p className="text-slate-700">
            Add a report and press Find claims:{" "}
            <Link href="/" className={linkText}>
              go to Start
            </Link>
            .
          </p>
        </Panel>
      </main>
    );
  }

  return (
    <main className={`${container} py-8`}>
      {header}

      <Panel
        id="sentences-heading"
        title="Report sentences"
        description={
          claims.length === 0
            ? "Nothing checkable found. Tick a sentence to check it."
            : `${plural(claims.length)} to check, from ${sentences.length} sentences.`
        }
        flush
        className="mt-6"
      >
        <ol aria-label="Report sentences" className="divide-y divide-slate-200">
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
      </Panel>

      <div className="sticky bottom-0 z-10 mt-6 -mx-6 border-t border-slate-200 bg-white/95 px-6 py-3 shadow-[0_-4px_12px_-8px_rgba(15,23,42,0.25)] backdrop-blur sm:mx-0 sm:rounded-md sm:border">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0 text-sm">
            <p className="font-semibold text-slate-900 tabular-nums">{plural(claims.length)} selected</p>
            {noRelease ? (
              <p className="text-slate-600">
                Choose a release folder on{" "}
                <Link href="/" className={linkText}>
                  Start
                </Link>{" "}
                first.
              </p>
            ) : (
              <p className="truncate font-mono text-xs text-slate-500" title={releaseDir}>
                {releaseDir}
              </p>
            )}
            <p aria-live="polite" className="font-medium">
              {running && <span className="sr-only">Checking {plural(claims.length)}…</span>}
              {message && (
                <span className="text-red-800">
                  <span aria-hidden="true">✕ </span>
                  {message}
                </span>
              )}
            </p>
          </div>
          <div className="flex items-center gap-4">
            {audit && !running && (
              <Link href="/board" className={`${linkText} text-sm`}>
                See the current audit board
              </Link>
            )}
            <button
              type="button"
              onClick={startAudit}
              disabled={claims.length === 0 || noRelease || running || pendingIndex !== null}
              className={buttonPrimary}
            >
              {running ? `Checking ${plural(claims.length)}…` : "Run audit →"}
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}
