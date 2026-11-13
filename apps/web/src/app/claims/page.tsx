"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import ClaimRow from "@/components/ClaimRow";
import { runAudit } from "@/lib/api";
import { useAudit } from "@/lib/audit-context";
import { buttonPrimary, card } from "@/lib/ui";

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
  const plural = (n: number) => `${n} claim${n === 1 ? "" : "s"}`;
  const noRelease = !releaseDir.trim();

  if (sentences.length === 0) {
    return (
      <main className="mx-auto max-w-5xl px-6 py-10">
        <h1 className="text-3xl font-semibold tracking-tight">Claims</h1>
        <section className={`${card} mt-6`}>
          <h2 className="text-lg font-semibold">No report yet</h2>
          <p className="mt-2 text-slate-700">
            Add a report and press Find claims:{" "}
            <Link href="/" className="text-emerald-900 underline underline-offset-4">
              go to Start
            </Link>
            .
          </p>
        </section>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <h1 className="text-3xl font-semibold tracking-tight">Claims</h1>
      <p className="mt-3 max-w-2xl leading-7 text-slate-700">
        Every sentence of the report, in order. Ticked sentences will be checked against the data. Untick a sentence
        that is not a real claim, or tick one we missed.
      </p>

      <p className="mt-6 font-medium">
        {claims.length === 0
          ? "Nothing checkable found. Tick a sentence to check it."
          : `${plural(claims.length)} to check, from ${sentences.length} sentences.`}
      </p>

      <ol aria-label="Report sentences" className="mt-4 grid gap-3">
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

      <div className="sticky bottom-0 mt-6 flex flex-wrap items-center gap-4 border-t border-emerald-900/15 bg-background py-4">
        <button
          type="button"
          onClick={startAudit}
          disabled={claims.length === 0 || noRelease || running || pendingIndex !== null}
          className={buttonPrimary}
        >
          {running ? `Checking ${plural(claims.length)}…` : "Run audit →"}
        </button>
        {noRelease && (
          <p className="text-sm text-slate-700">
            Choose a release folder on{" "}
            <Link href="/" className="text-emerald-900 underline underline-offset-4">
              Start
            </Link>{" "}
            first.
          </p>
        )}
        {audit && !running && (
          <Link href="/board" className="text-emerald-900 underline underline-offset-4">
            See the current audit board
          </Link>
        )}
        <p aria-live="polite" className="text-sm font-medium">
          {running && <span className="sr-only">Checking {plural(claims.length)}…</span>}
          {message && (
            <span className="text-red-800">
              <span aria-hidden="true">✕ </span>
              {message}
            </span>
          )}
        </p>
      </div>
    </main>
  );
}
