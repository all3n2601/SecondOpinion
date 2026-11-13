"use client";

import { useRouter } from "next/navigation";
import { useAudit } from "@/lib/audit-context";
import { focusRingOnDark } from "@/lib/ui";

/** Header action: clear the current audit (after confirming if there is work to lose) and go to Start. */
export default function NewAuditButton() {
  const router = useRouter();
  const { reset, reportText, audit } = useAudit();

  function startOver() {
    const hasWork = Boolean(reportText.trim() || audit);
    if (hasWork && !window.confirm("Start a new audit? The current report, claims and reviews will be cleared.")) return;
    reset();
    router.push("/");
  }

  return (
    <button
      type="button"
      onClick={startOver}
      className={`inline-flex h-8 items-center gap-1.5 rounded-md border border-slate-600 px-3 text-xs font-semibold text-slate-100 hover:border-slate-400 hover:bg-slate-800 ${focusRingOnDark}`}
    >
      <span aria-hidden="true">+</span>
      New audit
    </button>
  );
}
