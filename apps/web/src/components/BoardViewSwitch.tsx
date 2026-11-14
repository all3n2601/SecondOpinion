import { FileText, List } from "lucide-react";
import Link from "next/link";
import { REPORT_PATH } from "@/lib/report-nav";
import { focusRing } from "@/lib/ui";

const VIEWS = [
  { key: "list", href: "/board", label: "List", icon: List },
  { key: "report", href: REPORT_PATH, label: "Report", icon: FileText },
] as const;

/** Switches the audit board between the claim list and the report with its claims marked. */
export default function BoardViewSwitch({ current }: { current: (typeof VIEWS)[number]["key"] }) {
  return (
    <nav aria-label="Board view">
      <ul className="inline-flex gap-0.5 rounded-control border border-rule-strong bg-sheet p-0.5">
        {VIEWS.map(({ key, href, label, icon: Icon }) => {
          const here = key === current;
          return (
            <li key={key}>
              <Link
                href={href}
                aria-current={here ? "page" : undefined}
                className={`inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-stamp px-4 text-sm transition-colors duration-150 ${
                  here ? "bg-pen-tint font-semibold text-pen-deep" : "font-medium text-ink-soft hover:bg-wash hover:text-ink"
                } ${focusRing}`}
              >
                <Icon aria-hidden="true" className="size-4" />
                {label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
