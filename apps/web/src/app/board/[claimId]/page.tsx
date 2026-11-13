"use client";

import Link from "next/link";
import { use } from "react";
import Breadcrumb from "@/components/Breadcrumb";
import EvidencePanel from "@/components/EvidencePanel";
import NoAuditNotice from "@/components/NoAuditNotice";
import { useAudit } from "@/lib/audit-context";
import { focusRing } from "@/lib/ui";

export default function EvidencePage({ params }: { params: Promise<{ claimId: string }> }) {
  const { claimId: raw } = use(params);
  const claimId = decodeURIComponent(raw);
  const { audit, releaseDir } = useAudit();
  const crumbs = [{ label: "Audit board", href: "/board" }, { label: claimId }];

  if (!audit) {
    return (
      <main className="mx-auto max-w-5xl px-6 py-10">
        <Breadcrumb items={crumbs} />
        <h1 className="mb-6 text-3xl font-semibold tracking-tight">Evidence for {claimId}</h1>
        <NoAuditNotice />
      </main>
    );
  }

  const index = audit.claims.findIndex((c) => c.claim.id === claimId);
  if (index === -1) {
    return (
      <main className="mx-auto max-w-5xl px-6 py-10">
        <Breadcrumb items={crumbs} />
        <h1 className="text-3xl font-semibold tracking-tight">No claim {claimId}</h1>
        <p className="mt-4 text-slate-700">
          This audit has no claim called {claimId}.{" "}
          <Link href="/board" className="text-emerald-900 underline underline-offset-4">
            Back to the audit board
          </Link>
          .
        </p>
      </main>
    );
  }

  const prev = audit.claims[index - 1]?.claim.id;
  const next = audit.claims[index + 1]?.claim.id;
  const navLink = `rounded-lg font-medium text-emerald-900 underline underline-offset-4 hover:text-emerald-700 ${focusRing}`;

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <Breadcrumb items={crumbs} />
      <EvidencePanel result={audit.claims[index]} release={audit.release} releaseDir={releaseDir} />
      <nav aria-label="Other claims" className="mt-8 flex flex-wrap justify-between gap-4">
        {prev ? (
          <Link href={`/board/${encodeURIComponent(prev)}`} className={navLink}>
            ← Evidence for {prev}
          </Link>
        ) : (
          <span />
        )}
        <Link href="/board" className={navLink}>
          Back to the audit board
        </Link>
        {next ? (
          <Link href={`/board/${encodeURIComponent(next)}`} className={navLink}>
            Evidence for {next} →
          </Link>
        ) : (
          <span />
        )}
      </nav>
    </main>
  );
}
