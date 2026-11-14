import { useEffect, useState, useSyncExternalStore } from "react";
import { STAGES } from "./cohort";

const FIRST_STEP_MS = 2400; // the claim as written, long enough to read before anything moves
const STEP_MS = 2800;
const HOLD_MS = 4500; // on the last stage, long enough to read the correction before it starts over
export const LAST = STAGES.length - 1;

function subscribeMotion(onChange: () => void) {
  const query = window.matchMedia("(prefers-reduced-motion: reduce)");
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}
const prefersReducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/**
 * The one clock behind the hero demo. The report's sentence and the dot figure both read `stage`, so the phrase
 * being checked and the count on screen always agree. It loops until paused; picking a stage by hand pauses it.
 * With reduced motion it sits on the last stage and never advances.
 */
export function useDemoStage() {
  const calm = useSyncExternalStore(subscribeMotion, prefersReducedMotion, () => false);
  const [chosen, setChosen] = useState<number | null>(null);
  const [autoStage, setAutoStage] = useState(0);
  const [playing, setPlaying] = useState(true);

  const stage = chosen ?? (calm ? LAST : autoStage);
  const autoplay = playing && !calm && chosen === null;

  useEffect(() => {
    if (!autoplay) return;
    const atEnd = autoStage >= LAST;
    const timer = setTimeout(
      () => setAutoStage(atEnd ? 0 : autoStage + 1),
      atEnd ? HOLD_MS : autoStage === 0 ? FIRST_STEP_MS : STEP_MS,
    );
    return () => clearTimeout(timer);
  }, [autoplay, autoStage]);

  function choose(index: number) {
    setChosen(index);
    setPlaying(false);
  }

  /** Pause where it is, or resume (from the start if it was paused on the last stage). */
  function toggle() {
    if (autoplay) {
      setPlaying(false);
      setChosen(stage);
      return;
    }
    setAutoStage(stage >= LAST ? 0 : stage);
    setChosen(null);
    setPlaying(true);
  }

  return { stage, calm, autoplay, choose, toggle };
}
