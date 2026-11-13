import type { ReactNode } from "react";

/** One band of the front door: a hairline above, a heading, then content. Wider than pageWidth, still readable. */
export default function Section({
  id,
  title,
  intro,
  children,
}: {
  id: string;
  title: string;
  intro?: string;
  children: ReactNode;
}) {
  return (
    <section aria-labelledby={`${id}-heading`} className="border-t border-rule">
      <div className="mx-auto w-full max-w-5xl px-5 py-12 sm:px-8 sm:py-16">
        <h2 id={`${id}-heading`} className="text-2xl font-semibold tracking-tight text-ink">
          {title}
        </h2>
        {intro && <p className="mt-2 max-w-prose text-ink-soft">{intro}</p>}
        <div className="mt-8">{children}</div>
      </div>
    </section>
  );
}
