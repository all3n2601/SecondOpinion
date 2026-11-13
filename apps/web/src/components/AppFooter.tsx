import { container } from "@/lib/ui";

/** Product footer: version, the research-only line and data credits. */
export default function AppFooter() {
  return (
    <footer className="mt-16 border-t border-slate-200 bg-white">
      <div className={`${container} flex flex-wrap items-center justify-between gap-x-6 gap-y-2 py-5 text-xs text-slate-600`}>
        <p>
          <span className="font-semibold text-slate-800">SecondOpinion</span> v0.1.0 · Research prototype, not a
          clinical decision system.
        </p>
        <p>Data: TCGA Research Network, via UCSC Xena and NCI IDC.</p>
      </div>
    </footer>
  );
}
