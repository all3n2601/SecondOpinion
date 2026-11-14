"use client";

import { ClipboardCheck } from "lucide-react";
import { AnimatePresence, motion, useMotionValueEvent, useScroll } from "motion/react";
import Link from "next/link";
import { useState } from "react";
import Wordmark from "@/components/Wordmark";
import { buttonSecondary } from "@/lib/ui";
import { EASE } from "./motion";

/** Sticky top bar: the wordmark, which gains a frosted backdrop on scroll, and a quick way in once the hero is behind you. */
export default function LandingBar() {
  const { scrollY } = useScroll();
  const [scrolled, setScrolled] = useState(false);
  const [pastHero, setPastHero] = useState(false);

  useMotionValueEvent(scrollY, "change", (y) => {
    setScrolled(y > 8);
    setPastHero(y > 560);
  });

  return (
    <div
      className={`sticky top-0 z-40 border-b transition-colors duration-200 ${
        scrolled ? "border-rule bg-paper/80 backdrop-blur-md" : "border-transparent"
      }`}
    >
      <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-5 py-1 sm:px-8">
        <Wordmark />
        <AnimatePresence>
          {pastHero && (
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.2, ease: EASE }}
            >
              <Link href="/start" className={`${buttonSecondary} min-h-10 py-1.5`}>
                <ClipboardCheck aria-hidden="true" size={18} strokeWidth={1.75} />
                Start an audit
              </Link>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
