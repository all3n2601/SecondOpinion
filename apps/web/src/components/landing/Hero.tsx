import { ClipboardCheck } from "lucide-react";
import Link from "next/link";
import { buttonPrimary, focusRing } from "@/lib/ui";
import CohortFigure from "./CohortFigure";

/** The front door: what the tool does, one real correction, and the count behind it. The audit itself starts on /start. */
export default function Hero() {
  return (
    <header className="mx-auto w-full max-w-6xl px-5 pt-10 pb-14 sm:px-8 sm:pt-14 sm:pb-20">
      <div className="grid gap-x-12 gap-y-10 xl:grid-cols-[minmax(0,1fr)_minmax(0,27rem)] xl:items-start">
        <div className="min-w-0">
          <h1 className="max-w-[18ch] text-4xl font-semibold tracking-[-0.025em] text-ink sm:text-5xl sm:leading-[1.08]">
            Check every claim in a report against the data
          </h1>
          <p className="mt-5 max-w-[58ch] text-lg text-ink-soft">
            SecondOpinion reads a research report, checks each factual sentence against the TCGA-BRCA breast cancer
            data with ordinary code, and writes the wording the data does support.
          </p>

          <figure className="mt-10 border-l-2 border-contradicted pl-5 sm:pl-6">
            <blockquote className="reported max-w-[38ch] text-[1.375rem]! leading-[1.55]! sm:text-[1.75rem]!">
              Luminal A is the largest RNA subtype, accounting for <del>about 62%</del>{" "}
              <ins className="whitespace-nowrap">49.9% (421 of 844)</ins> of primary tumors with an RNA subtype call.
            </blockquote>
            <figcaption className="mt-3 max-w-[60ch] text-sm text-ink-soft">
              From the practice report. The figure beside it shows where 421 and 844 come from.
            </figcaption>
          </figure>

          <div className="mt-10 flex flex-wrap items-center gap-x-5 gap-y-3">
            <Link href="/start" className={buttonPrimary}>
              <ClipboardCheck aria-hidden="true" size={18} strokeWidth={1.75} />
              Start an audit
            </Link>
            <a
              href="#how"
              className={`inline-flex min-h-11 items-center rounded-control px-1 text-[0.9375rem] font-medium text-pen underline underline-offset-4 transition-colors duration-150 hover:text-pen-deep ${focusRing}`}
            >
              How it works
            </a>
          </div>
        </div>

        <CohortFigure />
      </div>
    </header>
  );
}
