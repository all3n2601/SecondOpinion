"use client";

import { buttonSecondary } from "@/lib/ui";

const SHOWN = 20;

/** Download for every sample ID, built in the browser as CSV. */
export function SampleDownload({ claimId, sampleIds }: { claimId: string; sampleIds: string[] }) {
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
  if (sampleIds.length === 0) return null;
  return (
    <button type="button" onClick={download} className={`${buttonSecondary} h-8 px-3 text-xs`}>
      <span aria-hidden="true">↓</span>
      Download all {sampleIds.length.toLocaleString("en-US")} sample IDs (CSV)
    </button>
  );
}

/** The first 20 sample IDs. */
export default function SampleList({ sampleIds }: { sampleIds: string[] }) {
  if (sampleIds.length === 0) return <p className="text-slate-700">No samples were used for this number.</p>;

  return (
    <div>
      <p className="text-sm text-slate-600 tabular-nums">
        {sampleIds.length.toLocaleString("en-US")} sample IDs
        {sampleIds.length > SHOWN && `; the first ${SHOWN} are shown`}.
      </p>
      <ul
        aria-label={`First ${Math.min(SHOWN, sampleIds.length)} sample IDs`}
        className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-3 lg:grid-cols-5"
      >
        {sampleIds.slice(0, SHOWN).map((id) => (
          <li key={id} className="font-mono text-[0.8rem] text-slate-800">
            {id}
          </li>
        ))}
      </ul>
    </div>
  );
}
