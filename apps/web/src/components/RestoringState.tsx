import { panel } from "@/lib/ui";

/** Placeholder while a saved session is restored, so pages don't flash "No audit yet". */
export default function RestoringState() {
  return (
    <div role="status" aria-live="polite" className={`${panel} mt-6 animate-pulse p-6`}>
      <span className="sr-only">Loading your audit…</span>
      <div aria-hidden="true" className="space-y-3">
        <div className="h-4 w-1/3 rounded bg-slate-200" />
        <div className="h-4 w-2/3 rounded bg-slate-200" />
        <div className="h-4 w-1/2 rounded bg-slate-200" />
      </div>
    </div>
  );
}
