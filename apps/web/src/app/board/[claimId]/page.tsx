"use client";

import { ArrowLeft, ArrowRight } from "lucide-react";
import Link from "next/link";
import { use } from "react";
import Breadcrumb from "@/components/Breadcrumb";
import EvidencePanel from "@/components/EvidencePanel";
import NoAuditNotice from "@/components/NoAuditNotice";
import { useAudit } from "@/lib/audit-context";
import { buttonQuiet, pageTitle, pageWidth } from "@/lib/ui";

export default function EvidencePage({ params }: { params: Promise<{ claimId: string }> }) {
  const { claimId: raw } = use(params);
  const claimId = decodeURIComponent(raw);
  const { audit, releaseDir } = useAudit();
  const crumbs = [{ label: "Audit board", href: "/board" }, { label: claimId }];

  if (!audit) {
    return (
      <main className={pageWidth}>
        <Breadcrumb items={crumbs} />
        <h1 className={`${pageTitle} mb-6`}>Evidence for {claimId}</h1>
        <NoAuditNotice />
      </main>
    );
  }

  const index = audit.claims.findIndex((c) => c.claim.id === claimId);
  if (index === -1) {
    return (
      <main className={pageWidth}>
        <Breadcrumb items={crumbs} />
        <h1 className={pageTitle}>No claim {claimId}</h1>
        <p className="mt-4 max-w-prose text-ink-soft">
          This audit has no claim called {claimId}.{" "}
          <Link href="/board" className="rounded-control font-medium text-pen underline underline-offset-4 hover:text-pen-deep">
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
    <main className={pageWidth}>
      <Breadcrumb items={crumbs} />
      <EvidencePanel result={audit.claims[index]} release={audit.release} releaseDir={releaseDir} />
      <nav aria-label="Other claims" className="mt-12 flex flex-wrap items-center justify-between gap-x-4 gap-y-1 border-t border-rule pt-6">
        {prev ? (
          <Link href={`/board/${encodeURIComponent(prev)}`} className={`${buttonQuiet} -ml-3`}>
            <ArrowLeft aria-hidden="true" className="size-4" />
            Evidence for {prev}
          </Link>
        ) : (
          <span />
        )}
        <Link href="/board" className={buttonQuiet}>
          Back to the audit board
        </Link>
        {next ? (
          <Link href={`/board/${encodeURIComponent(next)}`} className={`${buttonQuiet} -mr-3`}>
            Evidence for {next}
            <ArrowRight aria-hidden="true" className="size-4" />
          </Link>
        ) : (
          <span />
        )}
      </nav>
    </main>
  );
}
