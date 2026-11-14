"use client";

import { motion, MotionConfig, useScroll, useSpring, type Variants } from "motion/react";
import type { ReactNode } from "react";

/** Shared easing: quick start, soft landing. */
export const EASE = [0.22, 1, 0.36, 1] as const;

/** Fire once, a little before the element is fully on screen. */
const VIEWPORT = { once: true, margin: "0px 0px -12% 0px" } as const;

/** Wraps the landing page: with "reduce motion" on, movement is dropped and only fades remain. */
export function LandingMotion({ children }: { children: ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
}

/** A thin bar along the top edge that fills as you scroll the page. */
export function ScrollProgress() {
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, { stiffness: 140, damping: 24, mass: 0.4 });
  return (
    <motion.div
      aria-hidden="true"
      style={{ scaleX }}
      className="fixed inset-x-0 top-0 z-50 h-[3px] origin-left bg-pen"
    />
  );
}

/** Fades and rises into place once, when scrolled into view. */
export function Reveal({
  children,
  className,
  delay = 0,
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
}) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={VIEWPORT}
      transition={{ duration: 0.6, ease: EASE, delay }}
    >
      {children}
    </motion.div>
  );
}

const LIST: Variants = { hidden: {}, show: { transition: { staggerChildren: 0.09 } } };
const ITEM: Variants = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: EASE } },
};

const LISTS = { div: motion.div, ol: motion.ol, ul: motion.ul, dl: motion.dl } as const;
const ITEMS = { div: motion.div, li: motion.li } as const;

/** A list whose children (`StaggerItem`) arrive one after another when scrolled into view. */
export function Stagger({
  as = "div",
  className,
  label,
  children,
}: {
  as?: keyof typeof LISTS;
  className?: string;
  label?: string;
  children: ReactNode;
}) {
  const Tag = LISTS[as] as typeof motion.div;
  return (
    <Tag
      aria-label={label}
      className={className}
      variants={LIST}
      initial="hidden"
      whileInView="show"
      viewport={VIEWPORT}
    >
      {children}
    </Tag>
  );
}

export function StaggerItem({
  as = "div",
  className,
  lift = false,
  children,
}: {
  as?: keyof typeof ITEMS;
  className?: string;
  /** Rise a few pixels under the pointer. */
  lift?: boolean;
  children: ReactNode;
}) {
  const Tag = ITEMS[as] as typeof motion.div;
  return (
    <Tag
      className={className}
      variants={ITEM}
      whileHover={lift ? { y: -4, transition: { duration: 0.2, ease: EASE } } : undefined}
    >
      {children}
    </Tag>
  );
}
