"use client";

import DecisionPanel from "@/components/DecisionPanel";
import NoAuditNotice from "@/components/NoAuditNotice";
import PageHeader from "@/components/PageHeader";
import RestoringState from "@/components/RestoringState";
import RolePicker from "@/components/RolePicker";
import { useAudit } from "@/lib/audit-context";
import { container } from "@/lib/ui";

export default function DecisionPage() {
  const { audit, restored } = useAudit();

  return (
    <main className={`${container} py-8`}>
      <title>Decision | SecondOpinion</title>
      <PageHeader
        kicker="Step 5 of 5 · Decision"
        title="One decision for this report"
        description="The tool suggests a decision from the reviewed verdicts. A person makes the final call."
        actions={<RolePicker />}
      />
      {!restored ? (
        <RestoringState />
      ) : (
        <div className="mt-6">{audit ? <DecisionPanel audit={audit} /> : <NoAuditNotice />}</div>
      )}
    </main>
  );
}
