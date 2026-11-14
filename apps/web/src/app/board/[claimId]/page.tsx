"use client";

import { ArrowLeft, ArrowRight } from "lucide-react";
import Link from "next/link";
import { use } from "react";
import Breadcrumb from "@/components/Breadcrumb";
import EvidencePanel from "@/components/EvidencePanel";
import NoAuditNotice from "@/components/NoAuditNotice";
import { useAudit } from "@/lib/audit-context";
import { evidenceHref, RETURN_LABEL, returnHref, returnView } from "@/lib/report-nav";
import { buttonQuiet, pageTitle, pageWidth } from "@/lib/ui";

export default function EvidencePage({
  params,
  searchParams,
}: {
  params: Promise<{ claimId: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const { claimId: raw } = use(params);
  const claimId = decodeURIComponent(raw);
  // Opened from a marked report (`?from=report` on the board, `?from=decision` after the decision): every way
  // back leads to this claim's place in that report.
  const from = returnView(use(searchParams).from);
  const { audit, releaseDir } = useAudit();
  const back = from
    ? { href: returnHref(from, claimId), label: RETURN_LABEL[from].back }
    : { href: "/board", label: "Back to the audit board" };
  const crumbs =
    from === "decision"
      ? [{ label: "Decision", href: back.href }, { label: claimId }]
      : [
          { label: "Audit board", href: "/board" },
          ...(from ? [{ label: RETURN_LABEL[from].crumb, href: back.href }] : []),
          { label: claimId },
        ];

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
          <Link href={back.href} className="rounded-control font-medium text-pen underline underline-offset-4 hover:text-pen-deep">
            {back.label}
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
          <Link href={evidenceHref(prev, from ?? undefined)} className={`${buttonQuiet} -ml-3`}>
            <ArrowLeft aria-hidden="true" className="size-4" />
            Evidence for {prev}
          </Link>
        ) : (
          <span />
        )}
        <Link href={back.href} className={buttonQuiet}>
          {back.label}
        </Link>
        {next ? (
          <Link href={evidenceHref(next, from ?? undefined)} className={`${buttonQuiet} -mr-3`}>
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
