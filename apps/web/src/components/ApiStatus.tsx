"use client";

import { useEffect, useState } from "react";

type Connection = "checking" | "connected" | "unavailable";

const DOT: Record<Connection, string> = {
  checking: "bg-rule-strong",
  connected: "bg-supported",
  unavailable: "bg-contradicted",
};

/** Quiet status line: is the FastAPI backend reachable through the /api proxy? Always says so in words. */
export default function ApiStatus() {
  const [connection, setConnection] = useState<Connection>("checking");

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/health", { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("API unavailable");
        const result = await response.json();
        setConnection(result.status === "ok" ? "connected" : "unavailable");
      })
      .catch(() => {
        if (!controller.signal.aborted) setConnection("unavailable");
      });
    return () => controller.abort();
  }, []);

  return (
    <p
      role="status"
      className={`flex items-start gap-2 text-sm ${connection === "unavailable" ? "text-contradicted" : "text-ink-soft"}`}
    >
      <span aria-hidden="true" className={`mt-[0.45rem] size-2 shrink-0 rounded-full ${DOT[connection]}`} />
      <span>
        {connection === "checking" && "Checking API connection…"}
        {connection === "connected" && "API connected"}
        {connection === "unavailable" && "API unavailable. Start the backend with npm run dev."}
      </span>
    </p>
  );
}
