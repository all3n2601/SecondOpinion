"use client";

import { useId, useState } from "react";
import { buttonSecondary, card, fieldHint, fieldInput, fieldLabel, focusRing } from "@/lib/ui";

const ACCEPTED = [".md", ".txt"];

interface Props {
  value: string;
  onChange: (text: string) => void;
}

/** Three ways in: upload a .md/.txt file, load the practice report, or paste text. */
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

  async function loadPractice() {
    try {
      const response = await fetch("/practice_brief.md");
      if (!response.ok) throw new Error();
      onChange(await response.text());
      setSource("practice_brief.md");
      setMessage({ kind: "ok", text: "Loaded the practice report." });
    } catch {
      setMessage({ kind: "error", text: "Could not load the practice report." });
    }
  }

  const words = value.trim() ? value.trim().split(/\s+/).length : 0;

  return (
    <section aria-labelledby="report-heading" className={card}>
      <h2 id="report-heading" className="text-xl font-semibold">
        1. The report to check
      </h2>
      <p className={fieldHint}>Upload a Markdown or text file, use the practice report, or paste the text below.</p>

      <div className="mt-5 flex flex-wrap items-end gap-4">
        <div>
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
            className={`mt-2 block text-sm file:mr-3 file:rounded-lg file:border file:border-emerald-900/40 file:bg-white file:px-4 file:py-2 file:font-medium file:text-emerald-950 hover:file:bg-emerald-50 ${focusRing}`}
          />
        </div>
        <span className="pb-2 text-slate-600">or</span>
        <button type="button" onClick={loadPractice} className={buttonSecondary}>
          Use the practice report
        </button>
      </div>

      <div className="mt-5">
        <label htmlFor={pasteId} className={fieldLabel}>
          Report text
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
          className={`${fieldInput} mt-2 font-mono text-sm`}
        />
        <p className={fieldHint}>
          {words === 0 ? "No report yet." : `${words} words${source ? ` from ${source}` : ""}.`}
        </p>
      </div>

      <p
        aria-live="polite"
        className={`mt-2 text-sm ${message?.kind === "error" ? "font-medium text-red-800" : "text-emerald-900"}`}
      >
        {message && (message.kind === "error" ? "✕ " : "✓ ") + message.text}
      </p>
    </section>
  );
}
