"use client";

import Link from "next/link";
import ClaimCard from "@/components/ClaimCard";
import NoAuditNotice from "@/components/NoAuditNotice";
import { VERDICT_ICON, VERDICT_LABEL } from "@/lib/claim-format";
import { useAudit } from "@/lib/audit-context";
import type { Verdict } from "@/lib/types";
import { buttonPrimary } from "@/lib/ui";

const ORDER: Verdict[] = ["supported", "contradicted", "insufficient_evidence"];

export default function BoardPage() {
  const { audit } = useAudit();

  if (!audit) {
    return (
      <main className="mx-auto max-w-5xl px-6 py-10">
        <h1 className="mb-6 text-3xl font-semibold tracking-tight">Audit board</h1>
        <NoAuditNotice />
      </main>
    );
  }

  const counts = ORDER.map((v) => ({ verdict: v, n: audit.claims.filter((c) => c.verdict === v).length }));
  const fileCount = audit.release.files.length;

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <h1 className="text-3xl font-semibold tracking-tight">Audit board</h1>
      <p className="mt-3 max-w-2xl leading-7 text-slate-700">
        Each claim from the report, checked against release {audit.release.name} ({fileCount} files). Open a claim to
        see the calculation, the samples and the code behind it.
      </p>

      <p className="mt-6 flex flex-wrap gap-x-3 gap-y-1 text-lg font-medium" aria-label="Claims by verdict">
        {counts.map(({ verdict, n }, i) => (
          <span key={verdict}>
            {i > 0 && (
              <span aria-hidden="true" className="mr-3 text-slate-400">
                ·
              </span>
            )}
            <span aria-hidden="true">{VERDICT_ICON[verdict]} </span>
            {n} {VERDICT_LABEL[verdict].toLowerCase()}
          </span>
        ))}
      </p>

      {audit.notes.length > 0 && (
        <section
          aria-label="Notes about this data"
          className="mt-5 rounded-xl border border-amber-700/50 bg-amber-50 p-4 text-amber-950"
        >
          <h2 className="font-semibold">
            <span aria-hidden="true">⚠ </span>About this data
          </h2>
          <ul className="mt-1 list-disc pl-6">
            {audit.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </section>
      )}

      {audit.claims.length === 0 ? (
        <p className="mt-8 text-slate-700">
          No claims were checked.{" "}
          <Link href="/claims" className="text-emerald-900 underline underline-offset-4">
            Pick claims to check
          </Link>
          .
        </p>
      ) : (
        <ol aria-label="Checked claims" className="mt-8 grid gap-6">
          {audit.claims.map((result) => (
            <li key={result.claim.id}>
              <ClaimCard result={result} />
            </li>
          ))}
        </ol>
      )}

      <div className="mt-8">
        <Link href="/review" className={buttonPrimary}>
          Continue to review →
        </Link>
      </div>
    </main>
  );
}
