import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { focusRing } from "@/lib/ui";

export interface Crumb {
  label: string;
  /** Omit for the last crumb (the current page). */
  href?: string;
}

/** Keeps the user's place, e.g. Audit board > C2. The last item is the current page. */
export default function Breadcrumb({ items }: { items: Crumb[] }) {
  return (
    <nav aria-label="Breadcrumb" className="mb-6 text-sm">
      <ol className="flex flex-wrap items-center gap-x-1 text-ink-soft">
        {items.map((item, i) => {
          const last = i === items.length - 1;
          return (
            <li key={`${item.label}-${i}`} className="flex items-center gap-1">
              {i > 0 && <ChevronRight aria-hidden="true" className="size-4 text-ink-faint" />}
              {item.href && !last ? (
                <Link
                  href={item.href}
                  className={`inline-flex min-h-11 items-center rounded-control px-1 underline underline-offset-4 transition-colors duration-150 hover:text-pen ${focusRing}`}
                >
                  {item.label}
                </Link>
              ) : (
                <span aria-current={last ? "page" : undefined} className={last ? "font-semibold text-ink" : undefined}>
                  {item.label}
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
