"use client";

import Link from "next/link";
import { CircleCheck, CircleHelp, CircleX, Info } from "lucide-react";
import ClaimCard from "@/components/ClaimCard";
import NoAuditNotice from "@/components/NoAuditNotice";
import { useAudit } from "@/lib/audit-context";
import type { Verdict } from "@/lib/types";
import { buttonPrimary, pageTitle, pageWidth } from "@/lib/ui";

const ORDER: Verdict[] = ["supported", "contradicted", "insufficient_evidence"];

const SUMMARY: Record<Verdict, { words: string; icon: typeof CircleCheck; ink: string; fill: string }> = {
  supported: { words: "supported", icon: CircleCheck, ink: "text-supported", fill: "bg-supported" },
  contradicted: { words: "contradicted", icon: CircleX, ink: "text-contradicted", fill: "bg-contradicted" },
  insufficient_evidence: { words: "needs more evidence", icon: CircleHelp, ink: "text-insufficient", fill: "bg-insufficient" },
};

export default function BoardPage() {
  const { audit } = useAudit();

  if (!audit) {
    return (
      <main className={pageWidth}>
        <h1 className={`${pageTitle} mb-6`}>Audit board</h1>
        <NoAuditNotice />
      </main>
    );
  }

  const counts = ORDER.map((v) => ({ verdict: v, n: audit.claims.filter((c) => c.verdict === v).length }));
  const fileCount = audit.release.files.length;

  return (
    <main className={pageWidth}>
      <h1 className={pageTitle}>Audit board</h1>
      <p className="mt-3 max-w-prose text-ink-soft">
        Each claim from the report, checked against release {audit.release.name} ({fileCount} files). Open a claim to
        see the calculation, the samples and the code behind it.
      </p>

      {audit.claims.length > 0 && (
        <div className="mt-6 grid gap-3">
          {/* The bar is a glance; the counts beside it carry the meaning. */}
          <div aria-hidden="true" className="flex h-2.5 gap-0.5 overflow-hidden rounded-stamp bg-wash">
            {counts.map(({ verdict, n }) =>
              n > 0 ? <span key={verdict} className={SUMMARY[verdict].fill} style={{ flexGrow: n, flexBasis: 0 }} /> : null,
            )}
          </div>
          <ul aria-label="Claims by verdict" className="flex flex-wrap gap-x-5 gap-y-1.5 font-medium text-ink">
            {counts.map(({ verdict, n }) => {
              const { words, icon: Icon, ink } = SUMMARY[verdict];
              return (
                <li key={verdict} className="flex items-center gap-1.5">
                  <Icon aria-hidden="true" className={`size-5 shrink-0 ${ink}`} />
                  <span>
                    <span className="num font-mono">{n}</span> {words}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {audit.notes.length > 0 && (
        <section
          aria-label="Notes about this data"
          className="mt-6 flex gap-3 rounded-panel border border-rule bg-wash p-4 text-ink"
        >
          <Info aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-ink-soft" />
          <div>
            <h2 className="font-semibold">About this data</h2>
            <ul className="mt-1 space-y-1 text-ink-soft">
              {audit.notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </div>
        </section>
      )}

      {audit.claims.length === 0 ? (
        <p className="mt-8 text-ink-soft">
          No claims were checked.{" "}
          <Link href="/claims" className="font-medium text-pen underline underline-offset-4 hover:text-pen-deep">
            Pick claims to check
          </Link>
          .
        </p>
      ) : (
        <ol
          aria-label="Checked claims"
          className="mt-8 divide-y divide-rule overflow-hidden rounded-panel border border-rule bg-sheet"
        >
          {audit.claims.map((result) => (
            <li key={result.claim.id}>
              <ClaimCard result={result} />
            </li>
          ))}
        </ol>
      )}

      <div className="mt-8">
        <Link href="/review" className={buttonPrimary}>
          Continue to review
        </Link>
      </div>
    </main>
  );
}
