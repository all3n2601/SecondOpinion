// The storyboard (/demo): the whole audit played as a sequence of scenes, so a viewer can watch it start to finish
// with almost no clicks. Pure: no React, no fetch. The player (components/storyboard/Storyboard.tsx) owns the clock;
// this file says which scenes there are, how long each runs, and which beat of a scene is showing at a given time.

export type SceneKind = "cover" | "report" | "data" | "claim" | "findings" | "review" | "decision" | "result";

export interface Scene {
  /** Unique within a storyboard: "report", "claim-C2", ... */
  id: string;
  kind: SceneKind;
  /** Short name in the chapter strip. */
  label: string;
  /** Set on claim scenes. */
  claimId?: string;
  /** How many things appear one after another in this scene. At least 1. */
  beats: number;
  /** Time between beats while playing. */
  beatMs: number;
  /** How long the last beat stays up before the next scene. */
  holdMs: number;
  /** A gate waits for the viewer (a person reviews, a person decides); the clock never moves past it on its own. */
  gate: boolean;
}

const BEAT = { report: 1400, data: 1300, claim: 2200, findings: 1600 } as const;

/** The scenes, in order. `claimIds` is null until the report has been read: the claim scenes are not known yet. */
export function buildScenes(claimIds: string[] | null): Scene[] {
  const ids = claimIds ?? [];
  const scenes: Scene[] = [
    { id: "cover", kind: "cover", label: "Start", beats: 1, beatMs: 0, holdMs: 0, gate: true },
    // The report appears, then each claim lights up in turn.
    { id: "report", kind: "report", label: "The report", beats: 1 + ids.length, beatMs: BEAT.report, holdMs: 1800, gate: false },
    // The release, its files and checksums, then the tally of verdicts.
    { id: "data", kind: "data", label: "The data", beats: 3, beatMs: BEAT.data, holdMs: 1800, gate: false },
  ];
  for (const id of ids) {
    // The sentence, what the data shows, the verdict, the wording the data supports.
    scenes.push({ id: `claim-${id}`, kind: "claim", label: id, claimId: id, beats: 4, beatMs: BEAT.claim, holdMs: 3200, gate: false });
  }
  scenes.push(
    { id: "findings", kind: "findings", label: "Findings", beats: 2, beatMs: BEAT.findings, holdMs: 3000, gate: false },
    { id: "review", kind: "review", label: "Review", beats: 1, beatMs: 0, holdMs: 900, gate: true },
    { id: "decision", kind: "decision", label: "Decision", beats: 1, beatMs: 0, holdMs: 900, gate: true },
    { id: "result", kind: "result", label: "Result", beats: 1, beatMs: 0, holdMs: 0, gate: true },
  );
  return scenes;
}

/** Time from the start of a scene until its last beat has been up for `holdMs`. */
export function sceneDuration(scene: Scene): number {
  return (scene.beats - 1) * scene.beatMs + scene.holdMs;
}

/** Which beat is showing `elapsed` ms into the scene: 0 at the start, never past the last one. */
export function beatAt(scene: Scene, elapsed: number): number {
  if (scene.beats <= 1 || scene.beatMs <= 0) return scene.beats - 1;
  return Math.max(0, Math.min(scene.beats - 1, Math.floor(elapsed / scene.beatMs)));
}

/**
 * Should the player move on from this scene by itself? Only once its time is up, the data it shows has arrived
 * (`ready`), and it is not a gate, unless the gate has been passed (`passed`: every claim reviewed, the decision
 * recorded), in which case it waits `holdMs` so the viewer sees what they did, then goes on.
 */
export function shouldAdvance(scene: Scene, elapsed: number, ready: boolean, passed: boolean): boolean {
  if (!ready) return false;
  if (scene.gate) return passed && elapsed >= scene.holdMs;
  return elapsed >= sceneDuration(scene);
}

/** Where a scene id sits in a (possibly rebuilt) list; the first scene when it is gone. */
export function indexOfScene(scenes: Scene[], id: string): number {
  const i = scenes.findIndex((s) => s.id === id);
  return i === -1 ? 0 : i;
}

/** The decision reason recorded when the viewer signs off on the tool's suggestion in one click. */
export function agreedReason(rule: string): string {
  const plain = rule.trim().replace(/[.\s]+$/, "");
  return `Agreed with the tool's suggestion (${plain}) after reviewing every verdict.`;
}
