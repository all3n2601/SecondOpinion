"use client";

import Breadcrumb from "@/components/Breadcrumb";
import DecisionPanel from "@/components/DecisionPanel";
import NoAuditNotice from "@/components/NoAuditNotice";
import RolePicker from "@/components/RolePicker";
import { useAudit } from "@/lib/audit-context";
import { pageTitle, pageWidth } from "@/lib/ui";

export default function DecisionPage() {
  const { audit } = useAudit();

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
      {audit ? <DecisionPanel audit={audit} /> : <NoAuditNotice />}
    </main>
  );
}
