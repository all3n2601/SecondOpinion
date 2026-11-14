"use client";

import { CircleAlert, ClipboardCheck, FileText, LayoutList } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import AiStatusChip from "@/components/AiStatusChip";
import ApiStatus from "@/components/ApiStatus";
import PipelineSteps, { seconds, type PipelineStep, type StepState } from "@/components/pipeline/PipelineSteps";
import ReleasePicker from "@/components/ReleasePicker";
import ReportUpload from "@/components/ReportUpload";
import VerdictBadge from "@/components/VerdictBadge";
import { extractClaims, getPracticeRelease, runAudit } from "@/lib/api";
import { useAudit } from "@/lib/audit-context";
import type { AuditResult, Claim, Verdict } from "@/lib/types";
import { buttonPrimary, buttonQuiet, buttonSecondary, pageTitle, sectionTitle } from "@/lib/ui";

/** "data" only happens on a practice run with no data folder: finding or fetching release A. */
type Stage = "data" | "read" | "audit";
type Run =
  | { state: "idle" }
  | { state: "running"; stage: Stage }
  | { state: "error"; stage: Stage; message: string };

const BACKEND_DOWN_HINT = "Start the backend (npm run dev), then try again.";
const VERDICTS: Verdict[] = ["supported", "contradicted", "insufficient_evidence"];

/** Say what went wrong and what to do: an unreachable backend needs starting; anything else came from the API itself. */
function failureText(error: Error, stage: Stage): string {
  const message = error.message.trim();
  if (message.startsWith("Could not reach")) {
    return `${message.replace(/\s*Is the backend running\?$/, "")} ${BACKEND_DOWN_HINT}`;
  }
  const sentence = /[.!?]$/.test(message) ? message : `${message}.`;
  if (stage === "data") return sentence;
  return stage === "audit" ? `${sentence} Check the data folder path, then try again.` : `${sentence} Try again.`;
}

function N({ children }: { children: React.ReactNode }) {
  return <span className="num font-mono text-[0.9em] font-medium">{children}</span>;
}

function readResult(sentenceCount: number, claims: Claim[]) {
  const fromAi = claims.filter((c) => c.source === "ai").length;
  return (
    <p>
      <N>{claims.length}</N> checkable {claims.length === 1 ? "claim" : "claims"} in <N>{sentenceCount}</N>{" "}
      {sentenceCount === 1 ? "sentence" : "sentences"}
      {fromAi > 0 && (
        <>
          , <N>{fromAi}</N> of them flagged by the AI helper
        </>
      )}
      .
    </p>
  );
}

function checkResult(audit: AuditResult) {
  return (
    <div>
      <p>
        <N>{audit.claims.length}</N> checked against release <N>{audit.release.name}</N>.
      </p>
      <ul aria-label="Verdicts" className="mt-2 flex flex-wrap gap-2">
        {VERDICTS.map((verdict) => {
          const count = audit.claims.filter((c) => c.verdict === verdict).length;
          return (
            <li key={verdict} className="flex items-center gap-1.5">
              <VerdictBadge verdict={verdict} size="sm" />
              <N>{count}</N>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function recountResult(audit: AuditResult) {
  const every = audit.claims.filter((c) => c.solidity === "holds_under_every_variant").length;
  const some = audit.claims.filter((c) => c.solidity === "holds_under_some_variants").length;
  const none = audit.claims.length - every - some;
  return (
    <p>
      <N>{every}</N> {every === 1 ? "holds" : "hold"} under every way of counting, <N>{some}</N>{" "}
      {some === 1 ? "changes" : "change"} with the count
      {none > 0 && (
        <>
          , <N>{none}</N> {none === 1 ? "has" : "have"} no count to vary
        </>
      )}
      .
    </p>
  );
}

function rewriteResult(audit: AuditResult) {
  const rewritten = audit.claims.filter((c) => c.ladder.some((s) => s.struck || s.inserted)).length;
  return (
    <p>
      <N>{rewritten}</N> {rewritten === 1 ? "sentence" : "sentences"} rewritten to what the data supports, the rest kept
      as written.
    </p>
  );
}

/** Start: the report, the data folder, then the audit, shown step by step as it runs. */
export default function StartPage() {
  const router = useRouter();
  const { reportText, setReportText, releaseDir, setReleaseDir, sentences, claims, setExtract, audit, setAudit, hydrated } =
    useAudit();
  const [run, setRun] = useState<Run>({ state: "idle" });
  const [timing, setTiming] = useState<Partial<Record<Stage, number>>>({});
  const [dataNote, setDataNote] = useState<string | null>(null);

  const running = run.state === "running";
  const hasReport = reportText.trim().length > 0;
  const hasFolder = releaseDir.trim().length > 0;
  const missing = [!hasReport && "a report", !hasFolder && "the data folder"].filter(Boolean).join(" and ");

  /** Run the pipeline on `text` against `dir`. `stopAfterRead` sends the user to Claims to adjust the list first. */
  async function start(text: string, dir: string, stopAfterRead = false) {
    let stage: Stage = "read";
    setTiming({});
    try {
      setRun({ state: "running", stage });
      let t0 = performance.now();
      const extracted = await extractClaims(text);
      setExtract(extracted);
      setTiming({ read: performance.now() - t0 });
      if (stopAfterRead) {
        router.push("/claims");
        return;
      }
      if (extracted.claims.length === 0) {
        throw new Error("No checkable claims were found. Open Claims to tick sentences yourself");
      }

      stage = "audit";
      setRun({ state: "running", stage });
      t0 = performance.now();
      setAudit(await runAudit(dir.trim(), extracted.claims));
      setTiming((prev) => ({ ...prev, audit: performance.now() - t0 }));
      setRun({ state: "idle" });
    } catch (error) {
      setRun({ state: "error", stage, message: failureText(error as Error, stage) });
    }
  }

  /** Load the practice report; with no data folder entered, fill it in with release A (local or a temporary download). */
  async function startPractice() {
    if (running) return;
    let stage: Stage = "read";
    try {
      const response = await fetch("/practice_brief.md");
      if (!response.ok) throw new Error("Could not load the practice report");
      const text = await response.text();
      setReportText(text);
      let dir = releaseDir;
      if (!hasFolder) {
        stage = "data";
        setRun({ state: "running", stage });
        const practice = await getPracticeRelease();
        dir = practice.release_dir;
        setReleaseDir(dir);
        setDataNote(
          practice.source === "temporary"
            ? `Practice data (release A) ${practice.downloaded.length > 0 ? "downloaded" : "reused"} in a temporary folder.`
            : "Practice data (release A) found on this computer.",
        );
      }
      await start(text, dir);
    } catch (error) {
      setRun({ state: "error", stage, message: failureText(error as Error, stage) });
    }
  }

  function stateOf(stage: Stage, done: boolean): StepState {
    if (run.state === "running" && run.stage === stage) return "running";
    if (run.state === "error" && run.stage === stage) return "failed";
    // A step after the running or failed one has not run in this attempt.
    if (run.state !== "idle" && run.stage === "data") return "waiting";
    if (run.state !== "idle" && stage === "audit" && run.stage === "read") return "waiting";
    return done ? "done" : "waiting";
  }

  const readState = stateOf("read", sentences.length > 0);
  const auditState = stateOf("audit", audit !== null);
  const auditDone = auditState === "done" && audit !== null;

  const before: PipelineStep[] = [
    {
      id: "read",
      title: "Read the report",
      does: "Split it into sentences and pick out the ones that state something the data can check.",
      state: readState,
      result: readState === "done" ? readResult(sentences.length, claims) : undefined,
      ms: timing.read,
    },
  ];
  const grouped: PipelineStep[] = [
    {
      id: "check",
      title: "Check each claim",
      does: "Count the release with ordinary code and compare the result with the report’s figure.",
      state: auditState,
      result: auditDone ? checkResult(audit) : undefined,
    },
    {
      id: "recount",
      title: "Recount eight ways",
      does: "Repeat each count with the other reasonable choices: subtype label, sex filter and which samples count.",
      state: auditState,
      result: auditDone ? recountResult(audit) : undefined,
    },
    {
      id: "rewrite",
      title: "Write the supported wording",
      does: "Strike what the data does not support and write the version it does.",
      state: auditState,
      result: auditDone ? rewriteResult(audit) : undefined,
    },
  ];
  const after: PipelineStep[] = [
    {
      id: "review",
      title: "Review and decide",
      does: "You confirm or override each verdict on the next screens, then record one decision and export audit.json.",
      state: "waiting",
    },
  ];

  const canRun = hasReport && hasFolder && !running && hydrated;
  const message = run.state === "error" ? run.message : null;

  return (
    <main className="mx-auto w-full max-w-6xl px-5 py-8 sm:px-8 sm:py-12">
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <h1 className={pageTitle}>Start an audit</h1>
        <div className="flex flex-wrap items-start gap-x-6 gap-y-2 sm:justify-end">
          <ApiStatus />
          <AiStatusChip showHint={false} />
        </div>
      </div>
      <p className="mt-3 max-w-prose text-ink-soft">
        Add a report and the data folder it describes. SecondOpinion then runs the audit step by step and shows what
        each step found.
      </p>

      <div className="mt-6 flex flex-wrap items-center gap-x-3 gap-y-2 rounded-panel border border-rule bg-sheet px-4 py-3">
        <FileText aria-hidden="true" size={18} strokeWidth={1.75} className="shrink-0 text-ink-soft" />
        <p className="text-[0.9375rem] text-ink-soft">No report to hand? The practice report has three claims.</p>
        <button
          type="button"
          onClick={startPractice}
          disabled={running || !hydrated}
          className={`${buttonQuiet} -my-1`}
        >
          {running && run.stage === "data" ? "Getting the practice data…" : "Run the practice audit"}
        </button>
        {!hasFolder && !running && (
          <p className="text-sm text-ink-faint">With no data folder, it fills one in with the practice data.</p>
        )}
        {running && run.stage === "data" && (
          <p className="text-sm text-ink-faint">The first time, this downloads about 70 MB.</p>
        )}
        {dataNote && !running && <p className="text-sm text-ink-faint">{dataNote}</p>}
      </div>

      <div className="mt-8 grid gap-x-10 gap-y-10 xl:grid-cols-[minmax(0,1fr)_minmax(0,25rem)] xl:items-start">
        <div className="min-w-0 divide-y divide-rule rounded-panel border border-rule bg-sheet">
          <div className="p-5 sm:p-6">
            <ReportUpload value={reportText} onChange={setReportText} />
          </div>
          <div className="p-5 sm:p-6">
            <ReleasePicker
              value={releaseDir}
              onChange={(dir) => {
                setReleaseDir(dir);
                setDataNote(null);
              }}
            />
          </div>
        </div>

        <section aria-labelledby="pipeline-heading" className="xl:sticky xl:top-8">
          <h2 id="pipeline-heading" className={sectionTitle}>
            3. Run the audit
          </h2>
          <div className="mt-4" aria-busy={running || undefined}>
            <PipelineSteps
              before={before}
              grouped={grouped}
              groupNote={`These three run together for every claim, in one request${
                timing.audit !== undefined && auditState === "done" ? ` (${seconds(timing.audit)})` : ""
              }.`}
              after={after}
            />
          </div>

          <div className="mt-6 border-t border-rule-strong pt-4">
            <div className="flex flex-wrap items-center gap-3">
              {auditDone ? (
                <>
                  <Link href="/board" className={buttonPrimary}>
                    <LayoutList aria-hidden="true" size={18} strokeWidth={1.75} />
                    Open the audit board
                  </Link>
                  <button type="button" onClick={() => start(reportText, releaseDir)} disabled={!canRun} className={buttonSecondary}>
                    Run it again
                  </button>
                </>
              ) : (
                <>
                  <button type="button" onClick={() => start(reportText, releaseDir)} disabled={!canRun} className={buttonPrimary}>
                    <ClipboardCheck aria-hidden="true" size={18} strokeWidth={1.75} />
                    {running ? "Running the audit…" : "Run the audit"}
                  </button>
                  <button
                    type="button"
                    onClick={() => start(reportText, releaseDir, true)}
                    disabled={!canRun}
                    className={buttonSecondary}
                  >
                    Find claims only
                  </button>
                </>
              )}
            </div>
            {!running && missing && !auditDone && <p className="mt-2 text-sm text-ink-soft">Add {missing} to run.</p>}
            {!auditDone && !missing && !running && (
              <p className="mt-2 text-sm text-ink-soft">
                “Find claims only” stops after reading, so you can change which sentences get checked.
              </p>
            )}
            <div aria-live="polite" className="mt-2 text-[0.9375rem]">
              {running && (
                <p className="sr-only">
                  {run.stage === "data"
                    ? "Getting the practice data…"
                    : run.stage === "read"
                      ? "Reading the report…"
                      : "Checking the claims…"}
                </p>
              )}
              {auditDone && !running && <p className="sr-only">Audit finished. Open the audit board to see it.</p>}
              {message && (
                <p className="flex items-start gap-2 font-medium text-contradicted">
                  <CircleAlert aria-hidden="true" size={16} strokeWidth={1.75} className="mt-1 shrink-0" />
                  <span>{message}</span>
                </p>
              )}
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
