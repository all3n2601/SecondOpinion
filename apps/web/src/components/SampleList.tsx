"use client";

import { Download } from "lucide-react";
import { buttonQuiet } from "@/lib/ui";

const SHOWN = 20;
const count = new Intl.NumberFormat("en-US");

/** The first 20 sample IDs, plus a CSV download of all of them (built in the browser). */
export default function SampleList({
  claimId,
  sampleIds,
  denominator = null,
}: {
  claimId: string;
  sampleIds: string[];
  /** How many samples were considered in total, when the claim is a share of something. */
  denominator?: number | null;
}) {
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

  if (sampleIds.length === 0) return <p className="text-ink-soft">No samples were used for this number.</p>;

  const total = count.format(sampleIds.length);
  const shown = Math.min(SHOWN, sampleIds.length);

  return (
    <div>
      <p className="text-ink">
        <span className="num font-mono font-semibold">
          {denominator !== null && denominator !== sampleIds.length ? `${total} of ${count.format(denominator)}` : total}
        </span>{" "}
        {denominator !== null && denominator !== sampleIds.length ? "samples counted" : "sample IDs"}.
        {sampleIds.length > SHOWN && (
          <span className="text-ink-soft">{` The first ${SHOWN} are shown; the CSV has all of them.`}</span>
        )}
      </p>
      <ul aria-label={`First ${shown} sample IDs`} className="mt-3 flex flex-wrap gap-1.5">
        {sampleIds.slice(0, SHOWN).map((id) => (
          <li key={id} className="num rounded-stamp border border-rule bg-wash px-2 py-0.5 font-mono text-sm text-ink">
            {id}
          </li>
        ))}
      </ul>
      <button type="button" onClick={download} className={`${buttonQuiet} mt-3 -ml-3`}>
        <Download aria-hidden="true" className="size-4" />
        Download all {total} sample IDs (CSV)
      </button>
    </div>
  );
}
