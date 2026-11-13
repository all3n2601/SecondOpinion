"use client";

import { useEffect, useState } from "react";

type Connection = "checking" | "connected" | "unavailable";

/** Small badge: is the FastAPI backend reachable through the /api proxy? */
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
      className={`rounded-full border px-3 py-1 text-sm ${
        connection === "unavailable" ? "border-red-800/40 text-red-800" : "border-emerald-900/20 text-slate-700"
      }`}
    >
      {connection === "checking" && "Checking API connection…"}
      {connection === "connected" && "✓ API connected"}
      {connection === "unavailable" && "✕ API unavailable. Start the backend with npm run dev."}
    </p>
  );
}
