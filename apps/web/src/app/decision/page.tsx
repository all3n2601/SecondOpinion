"use client";

import Breadcrumb from "@/components/Breadcrumb";
import DecisionPanel from "@/components/DecisionPanel";
import NoAuditNotice from "@/components/NoAuditNotice";
import RolePicker from "@/components/RolePicker";
import { useAudit } from "@/lib/audit-context";

export default function DecisionPage() {
  const { audit } = useAudit();

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <title>Decision | SecondOpinion</title>
      <Breadcrumb items={[{ label: "Review", href: "/review" }, { label: "Decision" }]} />
      <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">One decision for this report</h1>
          <p className="mt-2 max-w-2xl text-slate-700">
            The tool suggests a decision from the reviewed verdicts. A person makes the final call.
          </p>
        </div>
        <RolePicker />
      </div>
      {audit ? <DecisionPanel audit={audit} /> : <NoAuditNotice />}
    </main>
  );
}
