"use client";

import { ClipboardCheck } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { buttonSecondary } from "@/lib/ui";
import { Reveal } from "./motion";

/** The closing invitation: one deep-berry panel with the way in. */
export default function FinalCta() {
  return (
    <section aria-labelledby="begin-heading" className="border-t border-rule">
      <div className="mx-auto w-full max-w-6xl px-5 py-14 sm:px-8 sm:py-20">
        <Reveal className="relative isolate overflow-hidden rounded-[1.25rem] bg-pen-deep px-6 py-12 text-white sm:px-12 sm:py-16">
          <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10">
            <motion.div
              className="absolute -top-24 -right-16 size-80 rounded-full bg-[radial-gradient(closest-side,var(--color-pen),transparent)]"
              animate={{ x: [0, -24, 0], y: [0, 18, 0] }}
              transition={{ duration: 14, repeat: Infinity, ease: "easeInOut" }}
            />
            <motion.div
              className="absolute -bottom-32 left-1/3 size-72 rounded-full bg-[radial-gradient(closest-side,var(--color-pen),transparent)] opacity-70"
              animate={{ x: [0, 28, 0], y: [0, -16, 0] }}
              transition={{ duration: 18, repeat: Infinity, ease: "easeInOut" }}
            />
          </div>
          <h2 id="begin-heading" className="max-w-[20ch] text-3xl font-semibold tracking-tight sm:text-4xl">
            Try it on a report
          </h2>
          <p className="mt-3 max-w-[52ch] text-lg text-white/85">
            Bring a report and the TCGA-BRCA data folder it describes, or run the practice report to see a whole audit
            first.
          </p>
          <div className="mt-8">
            <Link href="/start" className={`${buttonSecondary} min-h-12 px-6 text-base active:scale-[0.98]`}>
              <ClipboardCheck aria-hidden="true" size={18} strokeWidth={1.75} />
              Start an audit
            </Link>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
