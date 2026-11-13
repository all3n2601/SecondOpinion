"use client";

import Link from "next/link";
import ClaimCard from "@/components/ClaimCard";
import NoAuditNotice from "@/components/NoAuditNotice";
import PageHeader from "@/components/PageHeader";
import { VERDICT_ICON, VERDICT_LABEL } from "@/lib/claim-format";
import { useAudit } from "@/lib/audit-context";
import type { Verdict } from "@/lib/types";
import { buttonPrimary, container, eyebrow, linkText, panel } from "@/lib/ui";

const ORDER: Verdict[] = ["supported", "contradicted", "insufficient_evidence"];

const TILE_ACCENT: Record<Verdict, string> = {
  supported: "border-t-emerald-700",
  contradicted: "border-t-red-700",
  insufficient_evidence: "border-t-amber-500",
};

function Tile({ label, value, icon, accent }: { label: string; value: number; icon?: string; accent: string }) {
  return (
    <div className={`${panel} border-t-4 px-4 py-3 ${accent}`}>
      <dt className={eyebrow}>
        {icon && <span aria-hidden="true">{icon} </span>}
        {label}
      </dt>
      <dd className="mt-1 text-3xl font-semibold tracking-tight text-slate-900 tabular-nums">{value}</dd>
    </div>
  );
}

export default function BoardPage() {
  const { audit } = useAudit();
  const kicker = "Step 3 of 5 · Audit board";

  if (!audit) {
    return (
      <main className={`${container} py-8`}>
        <PageHeader kicker={kicker} title="Audit results" />
        <div className="mt-6">
          <NoAuditNotice />
        </div>
      </main>
    );
  }

  const fileCount = audit.release.files.length;
  const continueLink = (
    <Link href="/review" className={buttonPrimary}>
      Continue to review →
    </Link>
  );

  return (
    <main className={`${container} py-8`}>
      <PageHeader
        kicker={kicker}
        title="Audit results"
        description={`Each claim from the report, checked against release ${audit.release.name} (${fileCount} files). Open a claim to see the calculation, the samples and the code behind it.`}
        actions={continueLink}
      />

      <dl aria-label="Claims by verdict" className="mt-6 grid grid-cols-2 gap-4 md:grid-cols-4">
        <Tile label="Claims checked" value={audit.claims.length} accent="border-t-slate-700" />
        {ORDER.map((v) => (
          <Tile
            key={v}
            label={VERDICT_LABEL[v]}
            icon={VERDICT_ICON[v]}
            value={audit.claims.filter((c) => c.verdict === v).length}
            accent={TILE_ACCENT[v]}
          />
        ))}
      </dl>

      {audit.notes.length > 0 && (
        <section
          aria-label="Notes about this data"
          className="mt-6 flex gap-3 rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-950"
        >
          <span
            aria-hidden="true"
            className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-amber-600 text-xs font-bold text-white"
          >
            !
          </span>
          <div>
            <h2 className="font-semibold">About this data</h2>
            <ul className="mt-0.5 list-disc pl-5">
              {audit.notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </div>
        </section>
      )}

      {audit.claims.length === 0 ? (
        <p className="mt-8 text-slate-700">
          No claims were checked.{" "}
          <Link href="/claims" className={linkText}>
            Pick claims to check
          </Link>
          .
        </p>
      ) : (
        <ol aria-label="Checked claims" className="mt-6 grid gap-5">
          {audit.claims.map((result) => (
            <li key={result.claim.id}>
              <ClaimCard result={result} />
            </li>
          ))}
        </ol>
      )}

      <div className="mt-8 flex justify-end">{continueLink}</div>
    </main>
  );
}
