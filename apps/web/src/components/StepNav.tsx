"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAudit } from "@/lib/audit-context";
import { container, focusRing } from "@/lib/ui";

export const STEPS = [
  { href: "/", label: "Start" },
  { href: "/claims", label: "Claims" },
  { href: "/board", label: "Audit board" },
  { href: "/review", label: "Review" },
  { href: "/decision", label: "Decision" },
] as const;

/** "/board/C2" belongs to the "/board" step; "/" only matches itself. */
function isCurrent(href: string, pathname: string): boolean {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

/** Numbered stepper. A step shows a tick once the work it stands for is done. */
export default function StepNav() {
  const pathname = usePathname();
  const { sentences, audit } = useAudit();
  const allReviewed = Boolean(audit && audit.claims.length > 0 && audit.claims.every((c) => c.review));
  const done = [sentences.length > 0, Boolean(audit), Boolean(audit), allReviewed, false];

  return (
    <nav aria-label="Audit steps" className="border-b border-slate-200 bg-white">
      <ol className={`${container} flex flex-wrap items-center gap-x-2 gap-y-1 py-2`}>
        {STEPS.map((step, i) => {
          const current = isCurrent(step.href, pathname);
          const complete = done[i] && !current;
          return (
            <li key={step.href} className="flex items-center gap-2">
              {i > 0 && <span aria-hidden="true" className="hidden h-px w-6 bg-slate-300 sm:block lg:w-10" />}
              <Link
                href={step.href}
                aria-current={current ? "step" : undefined}
                className={`group flex items-center gap-2 rounded-md px-2 py-1.5 text-sm ${focusRing} ${
                  current ? "font-semibold text-slate-900" : "text-slate-600 hover:text-slate-900"
                }`}
              >
                <span
                  aria-hidden="true"
                  className={`grid size-6 place-items-center rounded-full border text-xs font-semibold tabular-nums ${
                    current
                      ? "border-emerald-900 bg-emerald-900 text-white"
                      : complete
                        ? "border-emerald-800 bg-emerald-50 text-emerald-900"
                        : "border-slate-300 bg-white text-slate-500 group-hover:border-slate-400"
                  }`}
                >
                  {complete ? "✓" : i + 1}
                </span>
                <span className="sr-only">Step {i + 1}: </span>
                {step.label}
                {complete && <span className="sr-only"> (done)</span>}
              </Link>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
