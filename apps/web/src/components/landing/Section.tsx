import type { ReactNode } from "react";
import { Reveal } from "./motion";

/**
 * One band of the front door: a hairline above, the heading in a left column, content beside it. Lines up with
 * the hero. The heading reveals on scroll; the content animates itself.
 */
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
      <div className="mx-auto grid w-full max-w-6xl gap-x-12 gap-y-6 px-5 py-14 sm:px-8 sm:py-20 lg:grid-cols-[15rem_minmax(0,1fr)]">
        <Reveal>
          <h2 id={`${id}-heading`} className="text-2xl font-semibold tracking-tight text-ink sm:text-[1.75rem]">
            {title}
          </h2>
          {intro && <p className="mt-2 max-w-prose text-ink-soft">{intro}</p>}
        </Reveal>
        <div className="min-w-0">{children}</div>
      </div>
    </section>
  );
}
