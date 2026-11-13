"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";

/** Code on a quiet sheet with a Copy button; the result is announced to screen readers. */
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

  const Icon = status === "copied" ? Check : Copy;

  return (
    <div>
      <div className="overflow-hidden rounded-panel border border-rule bg-sheet">
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b border-rule bg-wash px-4 py-2">
          <p className="max-w-prose text-sm text-ink-soft">{label}</p>
          <button
            type="button"
            onClick={copy}
            className="inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-control border border-rule-strong bg-sheet px-4 text-sm font-semibold text-ink transition-colors duration-150 hover:border-ink-soft hover:bg-wash focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-pen"
          >
            <Icon aria-hidden="true" className="size-4" />
            {status === "copied" ? "Copied" : "Copy code"}
          </button>
        </div>
        <pre
          tabIndex={0}
          aria-label={label}
          className="overflow-x-auto p-4 font-mono text-sm leading-6 text-ink focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-pen"
        >
          <code>{code}</code>
        </pre>
      </div>
      <p aria-live="polite" className="sr-only">
        {status === "copied" ? "Code copied to the clipboard." : ""}
      </p>
      {status === "failed" && (
        <p role="alert" className="mt-2 text-sm font-medium text-contradicted">
          Could not copy. Select the code and copy it by hand.
        </p>
      )}
    </div>
  );
}
