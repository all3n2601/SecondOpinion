"use client";

import { useEffect, useState } from "react";

type Connection = "checking" | "connected" | "unavailable";

const DOT: Record<Connection, string> = {
  checking: "bg-slate-400",
  connected: "bg-emerald-400",
  unavailable: "bg-red-400",
};

const TEXT: Record<Connection, string> = {
  checking: "Checking API…",
  connected: "API connected",
  unavailable: "API unavailable",
};

/** System status for the header: is the FastAPI backend reachable through the /api proxy? */
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
      title={connection === "unavailable" ? "Start the backend with npm run dev" : undefined}
      className="inline-flex items-center gap-2 text-xs font-medium text-slate-300"
    >
      <span aria-hidden="true" className={`size-2 rounded-full ${DOT[connection]}`} />
      <span className="max-sm:sr-only">{TEXT[connection]}</span>
      {connection === "unavailable" && <span className="sr-only">. Start the backend with npm run dev.</span>}
    </p>
  );
}
