"use client";

import { CircleAlert, CircleCheck, LoaderCircle } from "lucide-react";
import { useId, useState } from "react";
import { readReportFile } from "@/lib/api";
import { fieldHint, fieldInput, fieldLabel, focusRing, sectionTitle } from "@/lib/ui";

const ACCEPTED = [".md", ".markdown", ".txt", ".pdf"];

interface Props {
  value: string;
  onChange: (text: string) => void;
}

/**
 * Two ways in: upload a Markdown, text or PDF file, or paste text. The practice report has its own button
 * at the top of Start. Markdown and text are read in the browser; a PDF goes to the API (`POST /report-file`),
 * which pulls out its text, and the text lands in the box so the reader can check it before the audit.
 */
export default function ReportUpload({ value, onChange }: Props) {
  const fileId = useId();
  const pasteId = useId();
  const [source, setSource] = useState<string | null>(null);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [reading, setReading] = useState<string | null>(null);

  async function readPdf(file: File) {
    setReading(file.name);
    setMessage(null);
    try {
      const read = await readReportFile(file);
      onChange(read.text);
      setSource(file.name);
      const pages = read.pages === 1 ? "1 page" : `${read.pages} pages`;
      setMessage({
        kind: "ok",
        text: `Read the text of ${file.name} (${pages}). Check it below: a PDF can split words or keep a heading or table in odd places.`,
      });
    } catch (error) {
      setMessage({ kind: "error", text: error instanceof Error ? error.message : `Could not read ${file.name}.` });
    } finally {
      setReading(null);
    }
  }

  function readFile(file: File) {
    const name = file.name.toLowerCase();
    if (!ACCEPTED.some((ext) => name.endsWith(ext))) {
      setMessage({ kind: "error", text: `“${file.name}” is not a Markdown (.md), text (.txt) or PDF (.pdf) file.` });
      return;
    }
    if (name.endsWith(".pdf")) {
      void readPdf(file);
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      onChange(String(reader.result ?? ""));
      setSource(file.name);
      setMessage({ kind: "ok", text: `Loaded ${file.name}.` });
    };
    reader.onerror = () => setMessage({ kind: "error", text: `Could not read ${file.name}.` });
    reader.readAsText(file);
  }

  const words = value.trim() ? value.trim().split(/\s+/).length : 0;

  return (
    <section aria-labelledby="report-heading">
      <h2 id="report-heading" className={sectionTitle}>
        1. Report
      </h2>
      <p className={fieldHint}>Upload a Markdown, text or PDF file, or paste the text.</p>

      <div className="mt-4 flex flex-wrap items-end gap-x-4 gap-y-2">
        <div className="min-w-0 max-w-full">
          <label htmlFor={fileId} className={fieldLabel}>
            Upload a report (.md, .txt or .pdf)
          </label>
          <input
            id={fileId}
            type="file"
            accept={[...ACCEPTED, "application/pdf"].join(",")}
            disabled={reading !== null}
            aria-describedby={reading ? `${fileId}-reading` : undefined}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) readFile(file);
              e.target.value = ""; // allow choosing the same file again
            }}
            className={`mt-2 block max-w-full text-sm text-ink-soft file:mr-3 file:min-h-11 file:cursor-pointer file:rounded-control file:border file:border-rule-strong file:bg-sheet file:px-4 file:py-2 file:text-[0.9375rem] file:font-semibold file:text-ink file:transition-colors file:duration-150 hover:file:bg-wash ${focusRing}`}
          />
        </div>
        {reading && (
          <p id={`${fileId}-reading`} className={`${fieldHint} flex items-center gap-2`}>
            <LoaderCircle aria-hidden="true" size={16} strokeWidth={1.75} className="animate-spin motion-reduce:animate-none" />
            Reading the text of {reading}…
          </p>
        )}
      </div>

      <div className="mt-4">
        <label htmlFor={pasteId} className={fieldLabel}>
          Or paste the report text
        </label>
        <textarea
          id={pasteId}
          value={value}
          onChange={(e) => {
            onChange(e.target.value);
            setSource(null);
          }}
          rows={8}
          placeholder="Paste the report here…"
          className={`${fieldInput} mt-2 font-serif text-base leading-7`}
        />
        <p className={fieldHint}>
          {words === 0 ? "No report yet." : `${words} words${source ? ` from ${source}` : ""}.`}
        </p>
      </div>

      <p
        aria-live="polite"
        className={`mt-2 text-sm ${message?.kind === "error" ? "font-medium text-contradicted" : "text-supported"}`}
      >
        {message && (
          <span className="flex items-start gap-2">
            {message.kind === "error" ? (
              <CircleAlert aria-hidden="true" size={16} strokeWidth={1.75} className="mt-0.5 shrink-0" />
            ) : (
              <CircleCheck aria-hidden="true" size={16} strokeWidth={1.75} className="mt-0.5 shrink-0" />
            )}
            <span>{message.text}</span>
          </span>
        )}
      </p>
    </section>
  );
}
