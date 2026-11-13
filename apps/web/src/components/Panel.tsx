import { panel } from "@/lib/ui";

interface Props {
  /** Used for the heading id; the section is labelled by its title. */
  id: string;
  title: string;
  description?: React.ReactNode;
  /** Buttons or status shown at the right of the title bar. */
  actions?: React.ReactNode;
  /** Remove body padding (for full-bleed tables and lists). */
  flush?: boolean;
  className?: string;
  headingLevel?: "h2" | "h3";
  children: React.ReactNode;
}

/** A titled panel: header bar with title and actions, then the body. */
export default function Panel({ id, title, description, actions, flush, className = "", headingLevel = "h2", children }: Props) {
  const Heading = headingLevel;
  return (
    <section aria-labelledby={id} className={`${panel} ${className}`}>
      <header className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b border-slate-200 px-5 py-3">
        <div className="min-w-0">
          <Heading id={id} className="text-sm font-semibold text-slate-900">
            {title}
          </Heading>
          {description && <p className="mt-0.5 text-sm text-slate-600">{description}</p>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </header>
      <div className={flush ? "" : "p-5"}>{children}</div>
    </section>
  );
}
