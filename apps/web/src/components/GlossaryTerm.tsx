"use client";

import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { GLOSSARY, type GlossaryKey } from "@/lib/glossary";
import { focusRing } from "@/lib/ui";

interface Props {
  /** Which glossary entry to explain. */
  term: GlossaryKey;
  /** The visible text; defaults to the glossary term. */
  children?: React.ReactNode;
  /** A second, case-specific sentence shown under the definition. */
  detail?: string;
  /** Extra classes for the trigger. */
  className?: string;
  /** No dotted underline: for a trigger that already looks like a tag. */
  bare?: boolean;
}

const GAP = 6;
const MARGIN = 8;
const CLOSE_DELAY = 120;

/**
 * A technical word with its plain meaning. The word is a button: the meaning shows on keyboard
 * focus, on hover (and stays while the pointer is over it) and on tap. Escape hides it. Screen
 * readers get the meaning through aria-describedby, whether or not it is showing.
 *
 * The tooltip is position: fixed so panels with overflow (tables, cards) never clip it.
 */
export default function GlossaryTerm({ term, children, detail, className = "", bare = false }: Props) {
  const entry = GLOSSARY[term];
  const id = useId();
  const tipId = `${id}-tip`;
  const triggerRef = useRef<HTMLButtonElement>(null);
  const tipRef = useRef<HTMLSpanElement>(null);
  const closeTimer = useRef<number | undefined>(undefined);
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);

  const show = useCallback(() => {
    window.clearTimeout(closeTimer.current);
    setOpen(true);
  }, []);
  const hideSoon = useCallback(() => {
    window.clearTimeout(closeTimer.current);
    closeTimer.current = window.setTimeout(() => setOpen(false), CLOSE_DELAY);
  }, []);
  const hide = useCallback(() => {
    window.clearTimeout(closeTimer.current);
    setOpen(false);
  }, []);

  // Place the tooltip below the word (above it when there is no room), kept inside the viewport.
  useLayoutEffect(() => {
    if (!open) return;
    const place = () => {
      const trigger = triggerRef.current?.getBoundingClientRect();
      const tip = tipRef.current?.getBoundingClientRect();
      if (!trigger || !tip) return;
      const below = trigger.bottom + GAP;
      const top = below + tip.height > window.innerHeight - MARGIN ? trigger.top - GAP - tip.height : below;
      const left = Math.min(Math.max(trigger.left, MARGIN), window.innerWidth - tip.width - MARGIN);
      setPos({ top: Math.max(top, MARGIN), left: Math.max(left, MARGIN) });
    };
    place();
    window.addEventListener("scroll", place, true);
    window.addEventListener("resize", place);
    return () => {
      window.removeEventListener("scroll", place, true);
      window.removeEventListener("resize", place);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") hide();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, hide]);

  useEffect(() => () => window.clearTimeout(closeTimer.current), []);

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        aria-describedby={tipId}
        onFocus={show}
        onBlur={hide}
        onMouseEnter={show}
        onMouseLeave={hideSoon}
        onClick={() => (open ? hide() : show())}
        className={`cursor-help rounded-stamp text-left ${bare ? "" : "underline decoration-ink-faint decoration-dotted underline-offset-4 transition-colors duration-150 hover:decoration-ink"} ${focusRing} ${className}`}
      >
        {children ?? entry.term}
      </button>
      <span
        ref={tipRef}
        id={tipId}
        role="tooltip"
        onMouseEnter={show}
        onMouseLeave={hideSoon}
        style={pos ? { top: pos.top, left: pos.left } : { top: 0, left: 0 }}
        className={`fixed z-50 block w-72 max-w-[calc(100vw-1rem)] rounded-control border border-rule bg-sheet px-3.5 py-2.5 text-left font-sans text-sm leading-5 font-normal tracking-normal text-ink normal-case shadow-raised ${
          open && pos ? "visible" : "invisible"
        }`}
      >
        <span className="block font-semibold">{entry.term}</span>
        <span className="mt-0.5 block text-ink-soft">{entry.meaning}</span>
        {detail && <span className="mt-2 block border-t border-rule pt-2 text-ink-soft">{detail}</span>}
      </span>
    </>
  );
}
