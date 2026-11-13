"use client";

import { useState } from "react";
import { buttonSecondary } from "@/lib/ui";

/** Code with a Copy button; the result is announced to screen readers. */
export default function CodeBlock({ code, label }: { code: string; label: string }) {
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
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-slate-600">{label}</p>
        <button type="button" onClick={copy} className={buttonSecondary}>
          <span aria-hidden="true">{status === "copied" ? "✓" : "⧉"}</span>
          {status === "copied" ? "Copied" : "Copy code"}
        </button>
      </div>
      <pre
        tabIndex={0}
        aria-label={label}
        className="mt-3 overflow-x-auto rounded-xl bg-slate-900 p-4 text-sm leading-6 text-slate-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-900"
      >
        <code>{code}</code>
      </pre>
      <p aria-live="polite" className="sr-only">
        {status === "copied" ? "Code copied to the clipboard." : ""}
      </p>
      {status === "failed" && (
        <p className="mt-2 text-sm font-medium text-red-800">Could not copy. Select the code and copy it by hand.</p>
      )}
    </div>
  );
}
