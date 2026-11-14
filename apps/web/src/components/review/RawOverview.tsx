import { FileChecksums } from "@/components/review/sections";
import { countText, finalVerdict, samplesText, VERDICT_LABEL } from "@/lib/review";
import type { ClaimResult, ReleaseInfo, Verdict } from "@/lib/types";
import { focusRing } from "@/lib/ui";

const INK: Record<Verdict, string> = {
  supported: "text-supported",
  contradicted: "text-contradicted",
  insufficient_evidence: "text-insufficient",
};

const TH = "whitespace-nowrap px-3 py-2 font-semibold";
const TD = "px-3 py-1.5 align-top";

/** Data engineer view: one dense table of what each check counted, then the release files and their checksums. */
export default function RawOverview({ claims, release, headline, caption }: {
  claims: ClaimResult[];
  release: ReleaseInfo;
  headline: string;
  caption: string;
}) {
  return (
    <>
      <p className="mt-2 break-words font-mono text-sm text-ink">{headline}</p>
      <p className="mt-0.5 break-words font-mono text-sm text-ink-soft">{caption}</p>
      {claims.length > 0 && (
        <div
          role="region"
          aria-label="Claims table, scrolls sideways"
          tabIndex={0}
          className={`mt-4 overflow-x-auto rounded-control border border-rule ${focusRing}`}
        >
          <table className="w-full min-w-[40rem] border-collapse text-left font-mono text-xs text-ink sm:text-sm">
            <thead className="bg-wash text-ink-soft">
              <tr>
                <th scope="col" className={TH}>claim</th>
                <th scope="col" className={TH}>verdict</th>
                <th scope="col" className={TH}>count</th>
                <th scope="col" className={`${TH} text-right`}>samples</th>
                <th scope="col" className={TH}>files</th>
              </tr>
            </thead>
            <tbody>
              {claims.map((c) => {
                const final = finalVerdict(c);
                return (
                  <tr key={c.claim.id} className="border-t border-rule">
                    <th scope="row" className={`${TD} whitespace-nowrap text-left font-semibold`}>
                      {c.claim.id}
                    </th>
                    <td className={`${TD} whitespace-nowrap`}>
                      <span className={`font-semibold ${INK[final]}`}>{VERDICT_LABEL[final]}</span>
                      {final !== c.verdict && <span className="block text-ink-soft">tool: {VERDICT_LABEL[c.verdict]}</span>}
                    </td>
                    {(c.parts?.length ?? 0) > 1 ? (
                      // A sentence with several parts: each part's own count, never the first part's for the row.
                      <>
                        <td className={`${TD} whitespace-nowrap`}>
                          {c.parts!.map((p) => (
                            <span key={p.claim.id} className="block">
                              <span className="text-ink-soft">{p.claim.id}</span> {countText(p.fact) ?? "none"}
                            </span>
                          ))}
                        </td>
                        <td className={`${TD} text-right`}>
                          {c.parts!.map((p) => (
                            <span key={p.claim.id} className="block">{samplesText(p.fact)}</span>
                          ))}
                        </td>
                      </>
                    ) : (
                      <>
                        <td className={`${TD} whitespace-nowrap`}>{countText(c.fact) ?? "none"}</td>
                        <td className={`${TD} text-right`}>{samplesText(c.fact)}</td>
                      </>
                    )}
                    <td className={`${TD} whitespace-nowrap`}>
                      {c.fact?.files.length ? c.fact.files.map((f) => <span key={f} className="block">{f}</span>) : "none"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <h3 className="mt-5 text-sm font-semibold text-ink">
        Files in release <span className="font-mono">{release.name}</span>
      </h3>
      <div className="mt-2 text-sm text-ink">
        {release.files.length ? <FileChecksums files={release.files} /> : <p className="text-ink-soft">No files listed.</p>}
      </div>
    </>
  );
}
