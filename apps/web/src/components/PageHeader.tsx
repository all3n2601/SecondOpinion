import { eyebrow } from "@/lib/ui";

interface Props {
  /** Small line above the title, e.g. "Step 2 of 5". */
  kicker?: string;
  title: string;
  description?: React.ReactNode;
  actions?: React.ReactNode;
}

/** Page title block: kicker, title, one-line description and page-level actions. */
export default function PageHeader({ kicker, title, description, actions }: Props) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-4 border-b border-slate-200 pb-6">
      <div className="min-w-0 max-w-3xl">
        {kicker && <p className={eyebrow}>{kicker}</p>}
        <h1 className="mt-1 text-2xl font-semibold tracking-tight text-slate-900 sm:text-[1.75rem]">{title}</h1>
        {description && <p className="mt-2 text-[0.95rem] leading-6 text-slate-600">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-3">{actions}</div>}
    </div>
  );
}
