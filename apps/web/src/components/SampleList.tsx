"use client";

import { buttonSecondary } from "@/lib/ui";

const SHOWN = 20;

/** The first 20 sample IDs, plus a CSV download of all of them (built in the browser). */
export default function SampleList({ claimId, sampleIds }: { claimId: string; sampleIds: string[] }) {
  function download() {
    const csv = ["sample_id", ...sampleIds].join("\n") + "\n";
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `${claimId}-samples.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  if (sampleIds.length === 0) return <p className="text-slate-700">No samples were used for this number.</p>;

  return (
    <div>
      <p className="text-slate-700">
        {sampleIds.length.toLocaleString("en-US")} sample IDs
        {sampleIds.length > SHOWN && `; the first ${SHOWN} are shown`}.
      </p>
      <ul aria-label={`First ${Math.min(SHOWN, sampleIds.length)} sample IDs`} className="mt-3 flex flex-wrap gap-2">
        {sampleIds.slice(0, SHOWN).map((id) => (
          <li key={id} className="rounded bg-slate-100 px-2 py-0.5 font-mono text-sm text-slate-800">
            {id}
          </li>
        ))}
      </ul>
      <button type="button" onClick={download} className={`${buttonSecondary} mt-4`}>
        <span aria-hidden="true">↓</span>
        Download all {sampleIds.length.toLocaleString("en-US")} sample IDs (CSV)
      </button>
    </div>
  );
}
