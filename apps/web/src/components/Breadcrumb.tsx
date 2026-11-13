import Link from "next/link";
import { focusRing } from "@/lib/ui";

export interface Crumb {
  label: string;
  /** Omit for the last crumb (the current page). */
  href?: string;
}

/** Keeps the user's place, e.g. Audit board / C2. The last item is the current page. */
export default function Breadcrumb({ items }: { items: Crumb[] }) {
  return (
    <nav aria-label="Breadcrumb" className="mb-4 text-sm">
      <ol className="flex flex-wrap items-center gap-1.5 text-slate-600">
        {items.map((item, i) => {
          const last = i === items.length - 1;
          return (
            <li key={`${item.label}-${i}`} className="flex items-center gap-1.5">
              {i > 0 && (
                <span aria-hidden="true" className="text-slate-400">
                  /
                </span>
              )}
              {item.href && !last ? (
                <Link href={item.href} className={`rounded-sm hover:text-slate-900 hover:underline ${focusRing}`}>
                  {item.label}
                </Link>
              ) : (
                <span aria-current={last ? "page" : undefined} className={last ? "font-medium text-slate-900" : undefined}>
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
