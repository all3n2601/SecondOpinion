"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import Breadcrumb from "@/components/Breadcrumb";
import DecisionPanel from "@/components/DecisionPanel";
import NoAuditNotice from "@/components/NoAuditNotice";
import RolePicker from "@/components/RolePicker";
import { useAudit } from "@/lib/audit-context";
import { unreviewedIds } from "@/lib/review";
import { pageTitle, pageWidth } from "@/lib/ui";

export default function DecisionPage() {
  const { audit, hydrated } = useAudit();
  const router = useRouter();
  // The decision comes after the review: until every claim is reviewed, this page sends you to Review.
  const locked = audit !== null && unreviewedIds(audit.claims).length > 0;

  useEffect(() => {
    if (hydrated && locked) router.replace("/review");
  }, [hydrated, locked, router]);

  return (
    <main className={pageWidth}>
      <title>Decision | SecondOpinion</title>
      <Breadcrumb items={[{ label: "Review", href: "/review" }, { label: "Decision" }]} />
      <h1 className={pageTitle}>One decision for this report</h1>
      <p className="mt-2 max-w-prose text-ink-soft">
        The tool suggests a decision from the reviewed verdicts. A person makes the final call.
      </p>
      <div className="mb-8 mt-6">
        <RolePicker />
      </div>
      {locked || !hydrated ? (
        <div aria-hidden="true" className="min-h-40 max-w-prose" />
      ) : audit ? (
        <DecisionPanel audit={audit} />
      ) : (
        <NoAuditNotice />
      )}
    </main>
  );
}
