"use client";

import { useId, useState } from "react";
import { buttonSecondary, fieldHint, fieldInput, fieldLabel, focusRing } from "@/lib/ui";
import Panel from "./Panel";

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
    <Panel
      id="report-heading"
      title="1 · Report"
      description="The research report to check. Markdown or plain text."
      actions={
        <button type="button" onClick={loadPractice} className={buttonSecondary}>
          Use the practice report
        </button>
      }
    >
      <div>
        <label htmlFor={fileId} className={fieldLabel}>
          Upload a file (.md or .txt)
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
          className={`mt-2 block w-full rounded-md border border-dashed border-slate-300 bg-slate-50 p-3 text-sm text-slate-700 file:mr-3 file:h-9 file:rounded-md file:border file:border-slate-300 file:bg-white file:px-3 file:text-sm file:font-semibold file:text-slate-800 hover:border-slate-400 ${focusRing}`}
        />
      </div>

      <div className="mt-5">
        <div className="flex items-baseline justify-between gap-3">
          <label htmlFor={pasteId} className={fieldLabel}>
            Report text
          </label>
          <span className="text-xs text-slate-500 tabular-nums">
            {words === 0 ? "Empty" : `${words.toLocaleString("en-US")} words${source ? ` · ${source}` : ""}`}
          </span>
        </div>
        <textarea
          id={pasteId}
          value={value}
          onChange={(e) => {
            onChange(e.target.value);
            setSource(null);
          }}
          rows={10}
          placeholder="Paste the report here…"
          className={`${fieldInput} mt-2 h-auto py-2 font-mono text-[0.8rem] leading-5`}
        />
        <p className={fieldHint}>Headings and formatting are ignored; each sentence is read on its own.</p>
      </div>

      <p
        aria-live="polite"
        className={`mt-3 text-sm ${message?.kind === "error" ? "font-medium text-red-800" : "text-emerald-900"}`}
      >
        {message && (message.kind === "error" ? "✕ " : "✓ ") + message.text}
      </p>
    </Panel>
  );
}
