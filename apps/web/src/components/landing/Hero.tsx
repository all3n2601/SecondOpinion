"use client";

import { CircleAlert, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useId, useRef, useState } from "react";
import ApiStatus from "@/components/ApiStatus";
import { extractClaims, runAudit } from "@/lib/api";
import { useAudit } from "@/lib/audit-context";
import { buttonPrimary, fieldHint, fieldInput, fieldLabel, focusRing, pageTitle } from "@/lib/ui";

type Run = { state: "idle" } | { state: "running"; message: string } | { state: "error"; message: string };

const BACKEND_DOWN_HINT = "Start the backend (npm run dev), then try again.";

/** Say what went wrong and what to do: an unreachable backend needs starting; anything else came from the API itself. */
function failureText(error: Error, stage: "report" | "claims" | "audit"): string {
  const message = error.message.trim();
  if (message.startsWith("Could not reach")) {
    return `${message.replace(/\s*Is the backend running\?$/, "")} ${BACKEND_DOWN_HINT}`;
  }
  const sentence = /[.!?]$/.test(message) ? message : `${message}.`;
  if (stage === "audit") return `${sentence} Check the data folder path, then try again.`;
  return `${sentence} Try again.`;
}

/** Move to the "Audit your own report" form and put the cursor in its first field. */
function goToForm(event: React.MouseEvent<HTMLAnchorElement>) {
  const target = document.getElementById("start");
  if (!target) return;
  event.preventDefault();
  const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  target.scrollIntoView({ behavior: calm ? "auto" : "smooth", block: "start" });
  history.replaceState(null, "", "#start");
  target.querySelector<HTMLElement>("input, textarea")?.focus({ preventScroll: true });
}

export default function Hero() {
  const router = useRouter();
  const { setReportText, releaseDir, setReleaseDir, setExtract, setAudit } = useAudit();
  const folderId = useId();
  const hintId = useId();
  const noteId = useId();
  const folderRef = useRef<HTMLInputElement>(null);
  const [run, setRun] = useState<Run>({ state: "idle" });
  const [folderMissing, setFolderMissing] = useState(false);

  const running = run.state === "running";

  async function runPractice() {
    if (running) return;
    if (!releaseDir.trim()) {
      setFolderMissing(true);
      setRun({ state: "idle" });
      folderRef.current?.focus();
      return;
    }
    setFolderMissing(false);
    setRun({ state: "running", message: "Reading the report…" });

    let stage: "report" | "claims" | "audit" = "report";
    try {
      const response = await fetch("/practice_brief.md");
      if (!response.ok) throw new Error("Could not load the practice report");
      const text = await response.text();
      setReportText(text);

      stage = "claims";
      setRun({ state: "running", message: "Finding the checkable sentences…" });
      const extracted = await extractClaims(text);
      setExtract(extracted);
      if (extracted.claims.length === 0) {
        throw new Error("No checkable claims were found in the practice report");
      }

      stage = "audit";
      const count = extracted.claims.length;
      setRun({ state: "running", message: `Checking ${count} ${count === 1 ? "claim" : "claims"} against the data…` });
      setAudit(await runAudit(releaseDir.trim(), extracted.claims));
      router.push("/board");
    } catch (error) {
      setRun({ state: "error", message: failureText(error as Error, stage) });
    }
  }

  const describedBy = folderMissing ? `${hintId} ${noteId}` : hintId;

  return (
    <header className="mx-auto w-full max-w-5xl px-5 pt-6 pb-12 sm:px-8 sm:pt-8 sm:pb-16">
      <div className="flex justify-end">
        <ApiStatus />
      </div>

      <h1 className={`${pageTitle} mt-6 max-w-[22ch] sm:mt-10`}>Check every claim in a report against the data</h1>
      <p className="mt-4 max-w-prose text-lg text-ink-soft">
        SecondOpinion reads a research report, checks each factual sentence against the TCGA-BRCA breast cancer data
        with ordinary code, and writes the wording the data does support.
      </p>

      <figure className="mt-8 rounded-panel border border-rule bg-sheet p-5 sm:mt-10 sm:p-8">
        <blockquote className="reported max-w-[40ch] text-[1.5rem]! leading-[1.5]! sm:text-[1.875rem]!">
          Luminal A is the largest RNA subtype, accounting for <del>about 62%</del> <ins className="whitespace-nowrap">49.9% (421 of 844)</ins> of
          primary tumors with an RNA subtype call.
        </blockquote>
        <figcaption className="mt-4 max-w-[65ch] text-sm text-ink-soft">
          From the practice report. The report claimed about 62%; the data shows 421 of 844, so the tool struck the
          figure and wrote the supported one.
        </figcaption>
      </figure>

      <div className="mt-8 max-w-2xl">
        <label htmlFor={folderId} className={fieldLabel}>
          Data folder
        </label>
        <div className="mt-2 flex flex-col gap-3 sm:flex-row">
          <input
            ref={folderRef}
            id={folderId}
            type="text"
            value={releaseDir}
            onChange={(e) => {
              setReleaseDir(e.target.value);
              if (e.target.value.trim()) setFolderMissing(false);
            }}
            aria-describedby={describedBy}
            aria-invalid={folderMissing || undefined}
            placeholder="/path/to/oncosys-hackathon-challenge/data/tcga-brca/raw"
            spellCheck={false}
            className={`${fieldInput} min-w-0 flex-1 font-mono text-sm ${folderMissing ? "border-contradicted" : ""}`}
          />
          <button type="button" onClick={runPractice} disabled={running} className={`${buttonPrimary} sm:shrink-0`}>
            {running && <Loader2 aria-hidden="true" size={16} strokeWidth={1.75} className="motion-safe:animate-spin" />}
            {running ? "Running the audit…" : "Run the practice audit"}
          </button>
        </div>
        <p id={hintId} className={fieldHint}>
          The folder with the TCGA-BRCA files. The form further down uses the same folder.
        </p>

        <div aria-live="polite" className="mt-3 min-h-6 text-[0.9375rem]">
          {folderMissing && (
            <p id={noteId} className="flex items-start gap-2 font-medium text-contradicted">
              <CircleAlert aria-hidden="true" size={16} strokeWidth={1.75} className="mt-1 shrink-0" />
              <span>Enter the data folder first.</span>
            </p>
          )}
          {run.state === "running" && <p className="text-ink-soft">{run.message}</p>}
          {run.state === "error" && (
            <p className="flex items-start gap-2 font-medium text-contradicted">
              <CircleAlert aria-hidden="true" size={16} strokeWidth={1.75} className="mt-1 shrink-0" />
              <span>{run.message}</span>
            </p>
          )}
        </div>

        <p className="mt-2">
          <a
            href="#start"
            onClick={goToForm}
            className={`inline-flex min-h-11 cursor-pointer items-center rounded-control px-1 text-[0.9375rem] font-medium text-pen underline underline-offset-4 transition-colors duration-150 hover:text-pen-deep ${focusRing}`}
          >
            Audit my own report
          </a>
        </p>
      </div>
    </header>
  );
}
