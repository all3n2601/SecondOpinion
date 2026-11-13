"use client";

import Link from "next/link";
import { use } from "react";
import Breadcrumb from "@/components/Breadcrumb";
import EvidencePanel from "@/components/EvidencePanel";
import NoAuditNotice from "@/components/NoAuditNotice";
import PageHeader from "@/components/PageHeader";
import { useAudit } from "@/lib/audit-context";
import { buttonSecondary, container, linkText } from "@/lib/ui";

export default function EvidencePage({ params }: { params: Promise<{ claimId: string }> }) {
  const { claimId: raw } = use(params);
  const claimId = decodeURIComponent(raw);
  const { audit, releaseDir } = useAudit();
  const crumbs = [{ label: "Audit board", href: "/board" }, { label: claimId }];

  if (!audit) {
    return (
      <main className={`${container} py-8`}>
        <Breadcrumb items={crumbs} />
        <PageHeader kicker="Evidence" title={`Evidence for ${claimId}`} />
        <div className="mt-6">
          <NoAuditNotice />
        </div>
      </main>
    );
  }

  const index = audit.claims.findIndex((c) => c.claim.id === claimId);
  if (index === -1) {
    return (
      <main className={`${container} py-8`}>
        <Breadcrumb items={crumbs} />
        <PageHeader kicker="Evidence" title={`No claim ${claimId}`} />
        <p className="mt-6 text-slate-700">
          This audit has no claim called {claimId}.{" "}
          <Link href="/board" className={linkText}>
            Back to the audit board
          </Link>
          .
        </p>
      </main>
    );
  }

  const prev = audit.claims[index - 1]?.claim.id;
  const next = audit.claims[index + 1]?.claim.id;

  return (
    <main className={`${container} py-8`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Breadcrumb items={crumbs} />
        <p className="mb-4 text-sm text-slate-600 tabular-nums">
          Claim {index + 1} of {audit.claims.length}
        </p>
      </div>
      <EvidencePanel result={audit.claims[index]} release={audit.release} releaseDir={releaseDir} />
      <nav aria-label="Other claims" className="mt-8 flex flex-wrap items-center justify-between gap-4 border-t border-slate-200 pt-6">
        {prev ? (
          <Link href={`/board/${encodeURIComponent(prev)}`} className={buttonSecondary}>
            ← Evidence for {prev}
          </Link>
        ) : (
          <span />
        )}
        <Link href="/board" className={linkText}>
          Back to the audit board
        </Link>
        {next ? (
          <Link href={`/board/${encodeURIComponent(next)}`} className={buttonSecondary}>
            Evidence for {next} →
          </Link>
        ) : (
          <span />
        )}
      </nav>
    </main>
  );
}
