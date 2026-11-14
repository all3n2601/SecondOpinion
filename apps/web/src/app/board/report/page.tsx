"use client";

import Link from "next/link";
import BoardViewSwitch from "@/components/BoardViewSwitch";
import Breadcrumb from "@/components/Breadcrumb";
import MarkedReport from "@/components/MarkedReport";
import NoAuditNotice from "@/components/NoAuditNotice";
import VerdictBadge from "@/components/VerdictBadge";
import { useAudit } from "@/lib/audit-context";
import { VERDICTS } from "@/lib/review";
import { buttonPrimary, pageTitle, pageWidth } from "@/lib/ui";

export default function ReportViewPage() {
  const { audit, reportText } = useAudit();

  return (
    <main className={pageWidth}>
      <title>Report | SecondOpinion</title>
      <Breadcrumb items={[{ label: "Audit board", href: "/board" }, { label: "Report" }]} />
      <h1 className={pageTitle}>The report, with its claims marked</h1>

      {!audit ? (
        <div className="mt-6">
          <NoAuditNotice />
        </div>
      ) : (
        <>
          <p className="mt-3 max-w-prose text-ink-soft">
            Each claim checked against release {audit.release.name}, marked where it sits in the report. The verdict
            shown is the final one, after any review.
          </p>

          <div className="mt-5">
            <BoardViewSwitch current="report" />
          </div>

          {!reportText.trim() ? (
            <p className="mt-8 max-w-prose text-ink">
              There is no report text to show, so nothing can be marked. The checked claims are still on the board:{" "}
              <Link href="/board" className="rounded-control font-medium text-pen underline underline-offset-4 hover:text-pen-deep">
                see them as a list
              </Link>
              .
            </p>
          ) : (
            <>
              <div className="mt-6 border-y border-rule py-4">
                <ul aria-label="What the marks mean" className="flex flex-wrap gap-x-4 gap-y-2">
                  {VERDICTS.map((v) => (
                    <li key={v}>
                      <VerdictBadge verdict={v} size="sm" />
                    </li>
                  ))}
                </ul>
                <p className="mt-2 text-sm text-ink-soft">
                  Click a marked sentence to open its evidence; you come back to the same place.
                </p>
              </div>

              <div className="mt-8">
                <MarkedReport audit={audit} reportText={reportText} from="report" label="The report" />
              </div>
            </>
          )}

          <div className="mt-10">
            <Link href="/review" className={buttonPrimary}>
              Continue to review
            </Link>
          </div>
        </>
      )}
    </main>
  );
}
