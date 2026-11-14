"use client";

import { CircleAlert, CircleCheck } from "lucide-react";
import { useId, useState } from "react";
import { fieldHint, fieldInput, fieldLabel, focusRing, sectionTitle } from "@/lib/ui";

const ACCEPTED = [".md", ".txt"];

interface Props {
  value: string;
  onChange: (text: string) => void;
}

/** Two ways in: upload a .md/.txt file or paste text. The practice report has its own button at the top of Start. */
export default function ReportUpload({ value, onChange }: Props) {
  const fileId = useId();
  const pasteId = useId();
  const [source, setSource] = useState<string | null>(null);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  function readFile(file: File) {
    if (!ACCEPTED.some((ext) => file.name.toLowerCase().endsWith(ext))) {
      setMessage({ kind: "error", text: `“${file.name}” is not a .md or .txt file.` });
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
      <p className={fieldHint}>Upload a Markdown or text file, or paste the text.</p>

      <div className="mt-4 flex flex-wrap items-end gap-x-4 gap-y-2">
        <div className="min-w-0 max-w-full">
          <label htmlFor={fileId} className={fieldLabel}>
            Upload a report (.md or .txt)
          </label>
          <input
            id={fileId}
            type="file"
            accept={ACCEPTED.join(",")}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) readFile(file);
              e.target.value = ""; // allow choosing the same file again
            }}
            className={`mt-2 block max-w-full text-sm text-ink-soft file:mr-3 file:min-h-11 file:cursor-pointer file:rounded-control file:border file:border-rule-strong file:bg-sheet file:px-4 file:py-2 file:text-[0.9375rem] file:font-semibold file:text-ink file:transition-colors file:duration-150 hover:file:bg-wash ${focusRing}`}
          />
        </div>
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
