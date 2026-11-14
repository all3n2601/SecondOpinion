"use client";

import { ChevronLeft, ChevronRight, Pause, Play } from "lucide-react";
import { AnimatePresence, motion, MotionConfig } from "motion/react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { EASE } from "@/components/landing/motion";
import Wordmark from "@/components/Wordmark";
import { extractClaims, getPracticeRelease, runAudit } from "@/lib/api";
import { useAudit } from "@/lib/audit-context";
import { unreviewedIds } from "@/lib/review";
import { beatAt, buildScenes, indexOfScene, sceneDuration, shouldAdvance, type Scene } from "@/lib/storyboard";
import { focusRing } from "@/lib/ui";
import {
  ClaimScene,
  CoverScene,
  DataScene,
  DecisionScene,
  FindingsScene,
  ReportScene,
  ResultScene,
  ReviewScene,
} from "./scenes";

/** Where the run has got to. "current" = playing the audit already in this tab: nothing to run. */
type Phase = "idle" | "reading" | "checking" | "done";
interface RunError {
  phase: "reading" | "checking";
  message: string;
}

const TICK_MS = 100;

function failure(error: unknown): string {
  const message = (error as Error).message?.trim() || "Something went wrong.";
  if (message.startsWith("Could not reach")) return "Could not reach the SecondOpinion API. Start it with npm run dev, then try again.";
  return /[.!?]$/.test(message) ? message : `${message}.`;
}

/** The audit as a storyboard: scenes that play by themselves, with a person's two clicks at the review and decision. */
export default function Storyboard() {
  const { reportText, setReportText, setReleaseDir, claims, setExtract, audit, setAudit, decision, hydrated } = useAudit();
  const [phase, setPhase] = useState<Phase>("idle");
  const [runError, setRunError] = useState<RunError | null>(null);
  const [sceneId, setSceneId] = useState("cover");
  const [playing, setPlaying] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const runToken = useRef(0);

  // The claims are known once the report has been read; the audit's own list wins once it exists.
  const claimIds = useMemo(() => {
    if (phase === "idle" || phase === "reading") return null;
    return audit?.claims.map((c) => c.claim.id) ?? claims.map((c) => c.id);
  }, [phase, audit, claims]);
  const scenes = useMemo(() => buildScenes(claimIds), [claimIds]);
  const index = indexOfScene(scenes, sceneId);
  const scene = scenes[index];
  const beat = beatAt(scene, elapsed);

  const ready = useCallback(
    (s: Scene): boolean => {
      switch (s.kind) {
        case "cover":
          return true;
        case "report":
          return phase === "checking" || phase === "done";
        default:
          return phase === "done" && audit !== null;
      }
    },
    [phase, audit],
  );
  const passed = useCallback(
    (s: Scene): boolean => {
      if (s.kind === "cover") return phase !== "idle";
      if (s.kind === "review") return audit !== null && unreviewedIds(audit.claims).length === 0;
      if (s.kind === "decision") return decision !== null;
      if (s.kind === "result") return false;
      return true;
    },
    [phase, audit, decision],
  );

  // The furthest scene you can step to: up to the first one still waiting for data or for a person.
  const lastReachable = useMemo(() => {
    for (let i = 0; i < scenes.length; i++) {
      if (!ready(scenes[i])) return Math.max(0, i - 1);
      if (scenes[i].gate && !passed(scenes[i])) return i;
    }
    return scenes.length - 1;
  }, [scenes, ready, passed]);

  const goTo = useCallback(
    (i: number, autoplay?: boolean) => {
      const target = scenes[Math.max(0, Math.min(i, scenes.length - 1))];
      setSceneId(target.id);
      const play = autoplay ?? playing;
      if (autoplay !== undefined) setPlaying(autoplay);
      // Stepping by hand while paused shows the whole scene; while playing it plays from the top.
      setElapsed(play ? 0 : sceneDuration(target));
    },
    [scenes, playing],
  );

  // ---- Running the audit --------------------------------------------------------------------------------------

  const runPractice = useCallback(async () => {
    const token = ++runToken.current;
    const stale = () => token !== runToken.current;
    setRunError(null);
    setPhase("reading");
    setSceneId("report");
    setElapsed(0);
    setPlaying(true);
    let step: RunError["phase"] = "reading";
    try {
      const [text, release] = await Promise.all([
        fetch("/practice_brief.md").then((r) => {
          if (!r.ok) throw new Error("Could not load the practice report");
          return r.text();
        }),
        getPracticeRelease(),
      ]);
      if (stale()) return;
      setReportText(text);
      setReleaseDir(release.release_dir);
      const extracted = await extractClaims(text);
      if (stale()) return;
      setExtract(extracted);
      if (extracted.claims.length === 0) throw new Error("No checkable claims were found in the report");
      setPhase("checking");
      step = "checking";
      const result = await runAudit(release.release_dir, extracted.claims);
      if (stale()) return;
      setAudit(result);
      setPhase("done");
    } catch (error) {
      if (stale()) return;
      setRunError({ phase: step, message: failure(error) });
      setPlaying(false);
    }
  }, [setReportText, setReleaseDir, setExtract, setAudit]);

  const playCurrent = useCallback(() => {
    runToken.current++;
    setRunError(null);
    setPhase("done");
    setSceneId("report");
    setElapsed(0);
    setPlaying(true);
  }, []);

  // ---- The clock ----------------------------------------------------------------------------------------------

  // A scene still waiting for its data holds its first beat, so nothing is shown before it exists.
  const sceneReady = ready(scene);
  // The latest of what the tick needs, read inside the interval rather than restarting it on every change.
  const now = useRef({ scene, next: scenes[index + 1] as Scene | undefined, elapsed, ready: sceneReady, passed: passed(scene) });
  useEffect(() => {
    now.current = { scene, next: scenes[index + 1], elapsed, ready: sceneReady, passed: passed(scene) };
  });

  // The result is the end: the clock never runs there.
  const running = playing && scene.kind !== "result";
  useEffect(() => {
    if (!running) return;
    let last = performance.now();
    const timer = setInterval(() => {
      const t = performance.now();
      const dt = t - last;
      last = t;
      const cur = now.current;
      if (!cur.ready) return;
      if (cur.next && shouldAdvance(cur.scene, cur.elapsed, cur.ready, cur.passed)) {
        setSceneId(cur.next.id);
        setElapsed(0);
        // The result is the end: playing stops there, so stepping back from it stays where you step.
        if (cur.next.kind === "result") setPlaying(false);
      } else {
        setElapsed((e) => e + dt);
      }
    }, TICK_MS);
    return () => clearInterval(timer);
  }, [running]);

  /** A person acted at a gate (accepted the verdicts, signed off): carry on from there. */
  const onGatePassed = useCallback(() => {
    setPlaying(true);
    setElapsed(0);
  }, []);

  // ---- Keyboard: space plays and pauses, arrows step ----------------------------------------------------------

  const canPlay = phase !== "idle" && scene.kind !== "result";
  const shownPlaying = running;
  const toggle = useCallback(() => {
    if (!canPlay) return;
    setPlaying((p) => !p);
  }, [canPlay]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const t = e.target as HTMLElement | null;
      const tag = t?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || t?.isContentEditable) return;
      if (e.key === " " && (tag === "BUTTON" || tag === "A")) return; // Space presses the focused button
      if (e.key === " " || e.key === "k") {
        e.preventDefault();
        toggle();
      } else if (e.key === "ArrowRight" && index < lastReachable) {
        e.preventDefault();
        goTo(index + 1);
      } else if (e.key === "ArrowLeft" && index > 1) {
        e.preventDefault();
        goTo(index - 1);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggle, goTo, index, lastReachable]);

  // ---- The stage ----------------------------------------------------------------------------------------------

  const claimResults = audit?.claims ?? [];
  let body: React.ReactNode = null;
  switch (scene.kind) {
    case "cover":
      body = <CoverScene hasAudit={hydrated && audit !== null} onPractice={runPractice} onCurrent={playCurrent} />;
      break;
    case "report":
      body = (
        <ReportScene
          reportText={reportText}
          claims={claims}
          beat={beat}
          reading={phase === "reading" && !runError}
          error={runError?.phase === "reading" ? runError.message : null}
          onRetry={runPractice}
        />
      );
      break;
    case "data":
      body = (
        <DataScene
          audit={phase === "done" ? audit : null}
          beat={beat}
          error={runError?.phase === "checking" ? runError.message : null}
          onRetry={runPractice}
        />
      );
      break;
    case "claim": {
      const i = claimResults.findIndex((c) => c.claim.id === scene.claimId);
      if (i !== -1) body = <ClaimScene result={claimResults[i]} beat={beat} index={i} total={claimResults.length} />;
      break;
    }
    case "findings":
      if (audit) body = <FindingsScene audit={audit} beat={beat} />;
      break;
    case "review":
      if (audit) body = <ReviewScene audit={audit} onDone={onGatePassed} />;
      break;
    case "decision":
      if (audit) body = <DecisionScene audit={audit} onDone={onGatePassed} />;
      break;
    case "result":
      if (audit) body = <ResultScene audit={audit} onReplay={playCurrent} />;
      break;
  }

  // How far through the current scene, for its chapter's fill.
  const duration = sceneDuration(scene);
  const progress = scene.kind === "result" ? 1 : scene.gate ? (passed(scene) ? 1 : 0) : duration > 0 ? Math.min(1, elapsed / duration) : 1;
  const chapters = scenes.slice(1); // the cover is not a chapter

  return (
    <MotionConfig reducedMotion="user">
      <div className="flex min-h-[calc(100dvh-2.75rem)] flex-col">
        <header className="mx-auto flex w-full max-w-7xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-5 py-3 sm:px-8">
          <Wordmark />
          <Link
            href={audit ? "/board" : "/start"}
            className={`inline-flex min-h-11 items-center rounded-control px-2 text-[0.9375rem] font-medium text-pen underline-offset-4 hover:underline ${focusRing}`}
          >
            {audit ? "Open the full workspace" : "Start your own audit"}
          </Link>
        </header>

        <main id="storyboard" className="mx-auto w-full max-w-7xl flex-1 px-5 pt-6 pb-40 sm:px-8 sm:pt-10">
          <p aria-live="polite" className="sr-only">
            {scene.kind === "cover" ? "" : `Scene ${index} of ${chapters.length}: ${scene.label}`}
          </p>
          <AnimatePresence mode="wait" initial={false}>
            <motion.section
              key={scene.id}
              aria-label={scene.label}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.4, ease: EASE }}
            >
              {body}
            </motion.section>
          </AnimatePresence>
        </main>

        {scene.kind !== "cover" && (
          <nav
            aria-label="Storyboard controls"
            className="fixed inset-x-0 bottom-0 z-40 border-t border-rule bg-sheet/95 backdrop-blur supports-[backdrop-filter]:bg-sheet/85"
          >
            <div className="mx-auto flex w-full max-w-7xl items-center gap-3 px-5 py-3 sm:gap-4 sm:px-8">
              <div className="flex shrink-0 items-center gap-1">
                <button
                  type="button"
                  onClick={() => goTo(index - 1)}
                  disabled={index <= 1}
                  aria-label="Previous scene"
                  className={`grid size-11 cursor-pointer place-items-center rounded-control text-ink transition-colors duration-150 hover:bg-wash disabled:cursor-not-allowed disabled:text-ink-faint ${focusRing}`}
                >
                  <ChevronLeft aria-hidden="true" className="size-5" />
                </button>
                <button
                  type="button"
                  onClick={toggle}
                  disabled={!canPlay}
                  aria-label={shownPlaying ? "Pause" : "Play"}
                  className={`grid size-12 cursor-pointer place-items-center rounded-full bg-pen text-white transition-colors duration-150 hover:bg-pen-deep disabled:cursor-not-allowed disabled:bg-rule-strong ${focusRing}`}
                >
                  {shownPlaying ? <Pause aria-hidden="true" className="size-5" /> : <Play aria-hidden="true" className="ml-0.5 size-5" />}
                </button>
                <button
                  type="button"
                  onClick={() => goTo(index + 1)}
                  disabled={index >= lastReachable}
                  aria-label="Next scene"
                  className={`grid size-11 cursor-pointer place-items-center rounded-control text-ink transition-colors duration-150 hover:bg-wash disabled:cursor-not-allowed disabled:text-ink-faint ${focusRing}`}
                >
                  <ChevronRight aria-hidden="true" className="size-5" />
                </button>
              </div>

              <ol aria-label="Scenes" className="flex min-w-0 flex-1 gap-1.5 overflow-x-auto py-1">
                {chapters.map((s, k) => {
                  const i = k + 1;
                  const current = i === index;
                  const done = i < index;
                  const reachable = i <= lastReachable;
                  const waiting = current && scene.gate && scene.kind !== "result" && !passed(scene);
                  return (
                    <li key={s.id} className="min-w-[3.5rem] flex-1">
                      <button
                        type="button"
                        onClick={() => goTo(i)}
                        disabled={!reachable}
                        aria-current={current ? "step" : undefined}
                        className={`group flex min-h-11 w-full cursor-pointer flex-col justify-center gap-1.5 rounded-control px-1 text-left disabled:cursor-not-allowed ${focusRing}`}
                      >
                        <span aria-hidden="true" className="block h-1 w-full overflow-hidden rounded-full bg-rule">
                          <span
                            className={`block h-full rounded-full ${waiting ? "animate-pulse bg-pen/60" : "bg-pen"}`}
                            style={{ width: done ? "100%" : current ? `${(waiting ? 1 : progress) * 100}%` : "0%" }}
                          />
                        </span>
                        <span
                          className={`truncate text-xs ${
                            current ? "font-semibold text-ink" : reachable ? "text-ink-soft group-hover:text-ink" : "text-ink-faint"
                          }`}
                        >
                          {s.label}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ol>

              <p className="hidden shrink-0 text-sm text-ink-soft md:block" aria-hidden="true">
                <span className="num font-mono text-ink">{index}</span> / <span className="num font-mono">{chapters.length}</span>
              </p>
            </div>
          </nav>
        )}
      </div>
    </MotionConfig>
  );
}
