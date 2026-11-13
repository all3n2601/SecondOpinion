import Link from "next/link";
import { container, focusRingOnDark } from "@/lib/ui";
import ApiStatus from "./ApiStatus";
import NewAuditButton from "./NewAuditButton";

/** Top bar: product identity on the left, system status on the right. */
export default function AppHeader() {
  return (
    <header className="bg-slate-900 text-white">
      <div className={`${container} flex h-14 items-center justify-between gap-4`}>
        <Link href="/" className={`flex items-center gap-3 rounded-sm ${focusRingOnDark}`}>
          <span
            aria-hidden="true"
            className="grid size-8 place-items-center rounded-sm bg-emerald-700 font-mono text-sm font-bold tracking-tight"
          >
            SO
          </span>
          <span className="text-[0.95rem] font-semibold tracking-tight">SecondOpinion</span>
          <span aria-hidden="true" className="hidden h-5 w-px bg-slate-700 sm:block" />
          <span className="hidden text-sm text-slate-300 sm:block">Research Claim Auditor</span>
        </Link>
        <div className="flex items-center gap-4">
          <ApiStatus />
          <NewAuditButton />
          <span className="hidden rounded-sm border border-slate-600 px-2 py-0.5 text-[0.7rem] font-semibold tracking-wider text-slate-300 uppercase lg:inline">
            Dataset · TCGA-BRCA
          </span>
        </div>
      </div>
    </header>
  );
}
