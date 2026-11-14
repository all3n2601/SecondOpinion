"use client";

import { ClipboardCheck } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import type { ReactNode } from "react";
import { buttonPrimary, focusRing } from "@/lib/ui";
import CohortFigure from "./CohortFigure";
import { EASE } from "./motion";
import { LAST, useDemoStage } from "./useDemoStage";

const HEADLINE = "Does the data say what the report says?".split(" ");

/** The words of the sentence that the figure is counting at a given stage (see cohort.ts STAGES). */
const PRIMARY = 1;
const CALLED = 2;
const LUM_A = 3;

/** Marker-pen highlight on the phrase being checked; it follows the figure's stage. */
function Checked({ on, children }: { on: boolean; children: ReactNode }) {
  return (
    <span
      className={`-mx-[0.12em] rounded-[2px] bg-transparent px-[0.12em] transition-[background-color,box-shadow] duration-500 ${
        on ? "bg-blush/60 shadow-[inset_0_-2px_0_var(--color-pen)]" : ""
      }`}
    >
      {children}
    </span>
  );
}

const rise = (delay: number) => ({
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.6, ease: EASE, delay },
});

/**
 * The front door: the question the tool answers, one real correction, and the count behind it.
 * On load the headline arrives word by word, then the report's sentence is corrected in place.
 */
export default function Hero() {
  const { stage, calm, autoplay, choose, toggle } = useDemoStage();
  const corrected = stage >= LAST;

  return (
    <header className="relative isolate overflow-x-clip">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10">
        <motion.div
          className="absolute -top-40 -right-32 size-[38rem] rounded-full bg-[radial-gradient(closest-side,var(--color-blush),transparent)] opacity-70"
          animate={{ x: [0, -36, 0], y: [0, 24, 0] }}
          transition={{ duration: 16, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.div
          className="absolute top-40 -left-48 size-[30rem] rounded-full bg-[radial-gradient(closest-side,var(--color-pen-tint),transparent)] opacity-90"
          animate={{ x: [0, 30, 0], y: [0, -20, 0] }}
          transition={{ duration: 19, repeat: Infinity, ease: "easeInOut" }}
        />
      </div>

      <div className="mx-auto w-full max-w-6xl px-5 pt-8 pb-16 sm:px-8 sm:pt-12 sm:pb-24">
        <div className="grid gap-x-12 gap-y-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,24rem)] lg:items-start xl:grid-cols-[minmax(0,1fr)_minmax(0,27rem)]">
          <div className="min-w-0">
            <h1 className="max-w-[16ch] text-4xl font-semibold tracking-[-0.03em] text-ink sm:text-5xl sm:leading-[1.04] xl:text-6xl">
              {HEADLINE.map((word, i) => (
                <motion.span
                  key={`${word}-${i}`}
                  className="inline-block"
                  initial={{ opacity: 0, y: 14, filter: "blur(6px)" }}
                  animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                  transition={{ duration: 0.6, ease: EASE, delay: 0.08 + i * 0.07 }}
                >
                  {word}
                  {i < HEADLINE.length - 1 && " "}
                </motion.span>
              ))}
            </h1>
            <motion.p {...rise(0.7)} className="mt-6 max-w-[56ch] text-lg text-ink-soft sm:text-xl sm:leading-8">
              SecondOpinion recounts each figure in a research report from the TCGA-BRCA breast cancer data, shows the
              calculation, and writes the wording the data supports.
            </motion.p>

            <motion.figure
              {...rise(0.95)}
              className="mt-10 rounded-r-panel border-l-2 border-contradicted bg-sheet/70 py-4 pr-5 pl-5 backdrop-blur-sm sm:pl-6"
            >
              <blockquote className="reported max-w-[38ch] text-[1.375rem]! leading-[1.55]! sm:text-[1.75rem]!">
                <Checked on={stage === LUM_A}>Luminal A</Checked> is the largest RNA subtype, accounting for{" "}
                {/* The strike is drawn by the bar, so the <del> turns its own line-through off. */}
                <del className="relative" style={{ textDecorationLine: "none" }}>
                  about 62%
                  <motion.span
                    aria-hidden="true"
                    className="absolute inset-x-0 top-[56%] h-0.5 origin-left bg-contradicted"
                    initial={{ scaleX: calm ? 1 : 0 }}
                    animate={{ scaleX: corrected ? 1 : 0 }}
                    transition={{ duration: 0.45, ease: EASE }}
                  />
                </del>
                {/* The correction takes no room until it arrives, so the sentence has no gap. */}
                <motion.span
                  className="inline-block overflow-hidden whitespace-nowrap align-bottom"
                  initial={{ width: calm ? "auto" : 0 }}
                  animate={{ width: corrected ? "auto" : 0 }}
                  transition={{ duration: 0.45, ease: EASE }}
                >
                  {"\u00A0"}
                  <motion.ins
                    className="inline-block"
                    initial={{ opacity: calm ? 1 : 0, y: calm ? 0 : 6 }}
                    animate={{ opacity: corrected ? 1 : 0, y: corrected ? 0 : 6 }}
                    transition={{ duration: 0.5, ease: EASE, delay: corrected ? 0.25 : 0 }}
                  >
                    49.9% (421 of 844)
                  </motion.ins>
                </motion.span>{" "}
                of <Checked on={stage === PRIMARY}>primary tumors</Checked>{" "}
                <Checked on={stage === CALLED}>with an RNA subtype call</Checked>.
              </blockquote>
              <figcaption className="mt-3 max-w-[60ch] text-sm text-ink-soft">
                From the practice report. The highlighted words are what the figure beside it is counting.
              </figcaption>
            </motion.figure>

            <motion.div {...rise(1.15)} className="mt-10 flex flex-wrap items-center gap-x-5 gap-y-3">
              <Link
                href="/start"
                className={`${buttonPrimary} min-h-12 px-6 text-base shadow-[0_10px_24px_-12px_rgb(158_42_94/0.6)] active:scale-[0.98]`}
              >
                <ClipboardCheck aria-hidden="true" size={18} strokeWidth={1.75} />
                Start an audit
              </Link>
              <a
                href="#why"
                className={`inline-flex min-h-11 items-center rounded-control px-1 text-[0.9375rem] font-medium text-pen underline underline-offset-4 transition-colors duration-150 hover:text-pen-deep ${focusRing}`}
              >
                Why this exists
              </a>
            </motion.div>
          </div>

          <motion.div
            initial={{ opacity: 0, y: 28, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.8, ease: EASE, delay: 0.35 }}
            className="rounded-panel shadow-[0_30px_70px_-34px_rgb(158_42_94/0.4)]"
          >
            <CohortFigure stage={stage} calm={calm} autoplay={autoplay} onChoose={choose} onToggle={toggle} />
          </motion.div>
        </div>
      </div>
    </header>
  );
}
