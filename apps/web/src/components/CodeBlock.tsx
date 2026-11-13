"use client";

import { useState } from "react";
import { focusRing } from "@/lib/ui";

/** Code in an editor-style frame with a Copy button; the result is announced to screen readers. */
export default function CodeBlock({ code, label, language = "python" }: { code: string; label: string; language?: string }) {
  const [status, setStatus] = useState<"idle" | "copied" | "failed">("idle");

  async function copy() {
    try {
      await navigator.clipboard.writeText(code);
      setStatus("copied");
      window.setTimeout(() => setStatus("idle"), 2500);
    } catch {
      setStatus("failed");
    }
  }

  return (
    <div>
      <p className="mb-3 text-sm text-slate-600">{label}</p>
      <div className="overflow-hidden rounded-md border border-slate-800 bg-slate-950">
        <div className="flex items-center justify-between gap-3 border-b border-slate-800 bg-slate-900 px-3 py-1.5">
          <span className="font-mono text-xs text-slate-400">{language}</span>
          <button
            type="button"
            onClick={copy}
            className={`inline-flex h-7 items-center gap-1.5 rounded-sm border border-slate-600 px-2.5 text-xs font-semibold text-slate-100 hover:bg-slate-800 ${focusRing}`}
          >
            <span aria-hidden="true">{status === "copied" ? "✓" : "⧉"}</span>
            {status === "copied" ? "Copied" : "Copy code"}
          </button>
        </div>
        <pre
          tabIndex={0}
          aria-label={label}
          className={`overflow-x-auto p-4 font-mono text-[0.8rem] leading-6 text-slate-100 ${focusRing}`}
        >
          <code>{code}</code>
        </pre>
      </div>
      <p aria-live="polite" className="sr-only">
        {status === "copied" ? "Code copied to the clipboard." : ""}
      </p>
      {status === "failed" && (
        <p className="mt-2 text-sm font-medium text-red-800">Could not copy. Select the code and copy it by hand.</p>
      )}
    </div>
  );
}
