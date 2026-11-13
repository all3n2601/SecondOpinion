"use client";

import { useEffect, useState } from "react";

type Connection = "checking" | "connected" | "unavailable";

export default function Home() {
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
    <main className="mx-auto max-w-5xl px-6 py-12 sm:py-20">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-emerald-900/15 pb-6">
        <span className="text-xl font-bold tracking-tight">SecondOpinion</span>
        <p role="status" className="rounded-full border border-emerald-900/20 px-4 py-2 text-sm">
          {connection === "checking" && "Checking API connection…"}
          {connection === "connected" && "API connected"}
          {connection === "unavailable" && "API unavailable — start the backend"}
        </p>
      </header>
      <section className="py-16">
        <p className="mb-4 text-sm font-semibold uppercase tracking-widest text-emerald-800">Research Claim Auditor</p>
        <h1 className="max-w-3xl text-5xl leading-tight font-semibold tracking-tight sm:text-6xl">Can the evidence support the claim?</h1>
        <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-600">Check research claims against the underlying data, explore alternative ways of counting, and trace each result back to its source.</p>
      </section>
      <section aria-labelledby="ladder-title" className="rounded-2xl border border-emerald-900/15 bg-white p-8">
        <p className="text-sm font-medium text-slate-500">Workspace scaffold</p>
        <h2 id="ladder-title" className="mt-2 text-2xl font-semibold">The Claim Ladder starts here</h2>
        <p className="mt-3 max-w-2xl leading-7 text-slate-600">Report upload, claim checks, evidence views, and audit export are planned. No report has been audited yet.</p>
        <a href="/api/docs" className="mt-6 inline-block rounded-lg bg-emerald-900 px-5 py-3 font-medium text-white focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-emerald-900">Explore the API</a>
      </section>
      <footer className="mt-8 text-sm text-slate-600">Research prototype. No diagnosis, treatment advice, or risk scores.</footer>
    </main>
  );
}
