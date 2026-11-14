"use client";

import { Check, Lock } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAudit } from "@/lib/audit-context";
import { unreviewedIds } from "@/lib/review";

export const STEPS = [
  { href: "/start", label: "Start", hint: "Report and data" },
  { href: "/claims", label: "Claims", hint: "What the report states" },
  { href: "/board", label: "Audit board", hint: "Verdicts and evidence" },
  { href: "/review", label: "Review", hint: "Confirm each verdict" },
  { href: "/decision", label: "Decision", hint: "Sign off and export" },
] as const;

/** "/board/C2" belongs to the "/board" step. The landing page ("/") is not a step. */
function isCurrent(href: string, pathname: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

/**
 * The five steps, in order. Numbers are meaningful here: it is a sequence.
 * Left rail on large screens, a five-column strip on small ones.
 */
export default function StepNav() {
  const pathname = usePathname();
  const currentIndex = STEPS.findIndex((step) => isCurrent(step.href, pathname));
  const { audit } = useAudit();
  // Decision comes after Review: while any claim is unreviewed, the Decision step leads to Review instead.
  const decisionLocked = audit !== null && unreviewedIds(audit.claims).length > 0;

  return (
    <nav aria-label="Audit steps">
      <ol className="grid grid-cols-5 gap-1 lg:grid-cols-1 lg:gap-0">
        {STEPS.map((step, i) => {
          const current = i === currentIndex;
          const done = currentIndex > i;
          const locked = step.href === "/decision" && decisionLocked && !current;
          return (
            <li key={step.href} className="relative lg:pb-1">
              {/* the vertical line that joins the steps in the rail */}
              {i < STEPS.length - 1 && (
                <span
                  aria-hidden="true"
                  className={`absolute top-10 bottom-0 left-[1.0625rem] hidden w-px lg:block ${done ? "bg-pen" : "bg-rule"}`}
                />
              )}
              <Link
                href={locked ? "/review" : step.href}
                title={locked ? "Review every claim first" : undefined}
                aria-current={current ? "step" : undefined}
                className="group flex min-h-11 flex-col items-center gap-1 rounded-control px-1 py-2 text-center focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-pen lg:flex-row lg:items-start lg:gap-3 lg:px-0 lg:py-1.5 lg:text-left"
              >
                <span
                  aria-hidden="true"
                  className={`num grid size-[2.125rem] shrink-0 place-items-center rounded-full border text-sm font-semibold transition-colors duration-150 ${
                    current
                      ? "border-pen bg-pen text-white"
                      : done
                        ? "border-pen bg-pen-tint text-pen"
                        : "border-rule-strong bg-sheet text-ink-soft group-hover:border-ink-soft"
                  }`}
                >
                  {done ? (
                    <Check className="size-4" strokeWidth={2.5} />
                  ) : locked ? (
                    <Lock className="size-3.5" strokeWidth={2.25} />
                  ) : (
                    i + 1
                  )}
                </span>
                <span className="min-w-0">
                  <span
                    className={`block text-xs leading-tight lg:text-[0.9375rem] ${
                      current ? "font-semibold text-ink" : "font-medium text-ink-soft group-hover:text-ink"
                    }`}
                  >
                    <span className="sr-only">Step {i + 1}: </span>
                    {step.label}
                    {locked && <span className="sr-only"> (locked: review every claim first; opens Review)</span>}
                  </span>
                  <span className="mt-0.5 hidden text-sm text-ink-faint lg:block">
                    {locked ? "Review every claim first" : step.hint}
                  </span>
                </span>
              </Link>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
