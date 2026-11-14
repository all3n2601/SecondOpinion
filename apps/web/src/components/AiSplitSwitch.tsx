"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import { getAiStatus } from "@/lib/api";

const KEY = "so.aiSplit";
const listeners = new Set<() => void>();
let fallback = true; // the choice when storage is blocked: it still holds for this page

/** The remembered choice (on unless the viewer turned it off). A preference, not report data, so localStorage. */
function readAiSplit(): boolean {
  try {
    const stored = window.localStorage.getItem(KEY);
    return stored === null ? fallback : stored !== "off";
  } catch {
    return fallback;
  }
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  window.addEventListener("storage", listener); // another tab changed it
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

function writeAiSplit(on: boolean): void {
  fallback = on;
  try {
    window.localStorage.setItem(KEY, on ? "on" : "off");
  } catch {
    // Storage blocked: `fallback` keeps the choice for this page.
  }
  listeners.forEach((listener) => listener());
}

/** The AI split choice and its setter. On before hydration, then whatever this browser remembered. */
export function useAiSplit(): [boolean, (on: boolean) => void] {
  return [useSyncExternalStore(subscribe, readAiSplit, () => true), writeAiSplit];
}

/**
 * Whether the AI helper splits a sentence the rules only half read into statements it can check one by one.
 * Off keeps such sentences whole, so they come back "can't check". Needs the AI helper; with it off, the switch is
 * disabled and the audit is rules only either way.
 */
export default function AiSplitSwitch({
  checked,
  onChange,
  disabled = false,
}: {
  checked: boolean;
  onChange: (on: boolean) => void;
  disabled?: boolean;
}) {
  const [aiOn, setAiOn] = useState<boolean | null>(null);

  useEffect(() => {
    let live = true;
    getAiStatus().then((status) => {
      if (live) setAiOn(status.enabled);
    });
    return () => {
      live = false;
    };
  }, []);

  const off = aiOn === false;
  return (
    <div>
      <label
        className={`flex min-h-11 items-center gap-3 text-sm text-ink ${off || disabled ? "cursor-not-allowed" : "cursor-pointer"}`}
      >
        <input
          type="checkbox"
          checked={checked && !off}
          disabled={disabled || off}
          onChange={(e) => onChange(e.target.checked)}
          aria-describedby="ai-split-hint"
          className="size-5 shrink-0 cursor-pointer accent-pen disabled:cursor-not-allowed"
        />
        <span className="font-medium">AI split</span>
        <span className="text-ink-soft">{off ? "needs the AI helper" : checked ? "on" : "off"}</span>
      </label>
      <p id="ai-split-hint" className="text-sm text-ink-soft">
        {off
          ? "With the AI helper off, the audit is rules only."
          : checked
            ? "Sentences the rules only half read are split into parts and each part is checked."
            : "Sentences the rules only half read stay whole and come back “can’t check”."}
      </p>
    </div>
  );
}
