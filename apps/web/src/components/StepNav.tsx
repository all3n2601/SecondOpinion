"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

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

export default function StepNav() {
  const pathname = usePathname();

  return (
    <nav aria-label="Audit steps" className="border-b border-emerald-900/15 bg-white">
      <ol className="mx-auto flex max-w-5xl flex-wrap gap-x-1 gap-y-2 px-6 py-3 text-sm">
        {STEPS.map((step, i) => {
          const current = isCurrent(step.href, pathname);
          return (
            <li key={step.href} className="flex items-center">
              {i > 0 && (
                <span aria-hidden="true" className="mx-1 text-slate-400">
                  →
                </span>
              )}
              <Link
                href={step.href}
                aria-current={current ? "step" : undefined}
                className={`rounded-md px-2 py-1 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-900 ${
                  current
                    ? "bg-emerald-900 font-semibold text-white"
                    : "text-slate-700 underline-offset-4 hover:underline"
                }`}
              >
                <span className="sr-only">Step {i + 1}: </span>
                {step.label}
              </Link>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
