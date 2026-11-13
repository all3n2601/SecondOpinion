"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import PageHeader from "@/components/PageHeader";
import Panel from "@/components/Panel";
import ReleasePicker, { REQUIRED_FILES, type ReleaseCheck } from "@/components/ReleasePicker";
import ReportUpload from "@/components/ReportUpload";
import RolePicker from "@/components/RolePicker";
import { extractClaims } from "@/lib/api";
import { useAudit } from "@/lib/audit-context";
import { buttonPrimary, container } from "@/lib/ui";

type ItemState = "done" | "warn" | "todo";

const MARK: Record<ItemState, { icon: string; style: string; sr: string }> = {
  done: { icon: "✓", style: "border-emerald-800 bg-emerald-50 text-emerald-900", sr: "Ready" },
  warn: { icon: "!", style: "border-red-800 bg-red-50 text-red-900", sr: "Problem" },
  todo: { icon: "", style: "border-slate-300 bg-white text-slate-400", sr: "Not done" },
};

function ChecklistItem({ state, title, detail }: { state: ItemState; title: string; detail: string }) {
  const m = MARK[state];
  return (
    <li className="flex gap-3 py-3">
      <span aria-hidden="true" className={`mt-0.5 grid size-5 shrink-0 place-items-center rounded-full border text-[0.7rem] font-bold ${m.style}`}>
        {m.icon}
      </span>
      <div className="min-w-0">
        <p className="text-sm font-semibold text-slate-900">
          <span className="sr-only">{m.sr}: </span>
          {title}
        </p>
        <p className="text-sm break-words text-slate-600">{detail}</p>
      </div>
    </li>
  );
}

export default function StartPage() {
  const router = useRouter();
  const { reportText, setReportText, releaseDir, setReleaseDir, setExtract, role } = useAudit();
  const [check, setCheck] = useState<ReleaseCheck>({ state: "idle" });
  const [finding, setFinding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function findClaims() {
    setFinding(true);
    setError(null);
    try {
      setExtract(await extractClaims(reportText));
      router.push("/claims");
    } catch (e) {
      setError((e as Error).message);
      setFinding(false);
    }
  }

  const words = reportText.trim() ? reportText.trim().split(/\s+/).length : 0;
  const hasReport = words > 0;
  const hasFolder = releaseDir.trim().length > 0;

  const dataItem: { state: ItemState; detail: string } =
    check.state === "ok"
      ? { state: "done", detail: `Release ${check.release.name}: ${check.found} of ${REQUIRED_FILES.length} files verified` }
      : check.state === "error"
        ? { state: "warn", detail: check.message }
        : check.state === "checking"
          ? { state: "todo", detail: "Checking…" }
          : hasFolder
            ? { state: "todo", detail: "Folder set; not checked yet" }
            : { state: "todo", detail: "No folder chosen" };

  return (
    <main className={`${container} py-8`}>
      <PageHeader
        kicker="Step 1 of 5 · Start"
        title="New audit"
        description="Check every factual sentence of a research report against the data it describes, and see how solid each answer is."
      />

      <div className="mt-6 grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="grid gap-6">
          <ReportUpload value={reportText} onChange={setReportText} />
          <ReleasePicker value={releaseDir} onChange={setReleaseDir} onCheck={setCheck} />
        </div>

        <div className="grid gap-6 lg:sticky lg:top-6">
          <Panel id="setup-heading" title="Audit setup">
            <ul className="-my-3 divide-y divide-slate-200">
              <ChecklistItem
                state={hasReport ? "done" : "todo"}
                title="Report"
                detail={hasReport ? `${words.toLocaleString("en-US")} words loaded` : "No report yet"}
              />
              <ChecklistItem state={dataItem.state} title="Data source" detail={dataItem.detail} />
              <ChecklistItem state="done" title="Reviewer role" detail={role} />
            </ul>
            <button
              type="button"
              onClick={findClaims}
              disabled={!hasReport || finding}
              className={`${buttonPrimary} mt-5 w-full`}
            >
              {finding ? "Finding claims…" : "Find claims →"}
            </button>
            {!hasReport && <p className="mt-2 text-center text-xs text-slate-600">Add a report first.</p>}
            <p aria-live="polite" className="mt-2 text-sm font-medium text-red-800">
              {error && (
                <>
                  <span aria-hidden="true">✕ </span>
                  {error}
                </>
              )}
            </p>
          </Panel>

          <Panel id="role-heading" title="Reviewer" description="Changes the wording and detail, never the numbers.">
            <RolePicker />
          </Panel>
        </div>
      </div>
    </main>
  );
}
