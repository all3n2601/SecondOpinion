"use client";

import { useCallback, useSyncExternalStore } from "react";
import { entryFromHash, hashFor, type Entry } from "./review-nav";

// The Review page's open entry lives in the URL hash, so reload, back / forward and plain `#review-C2` links all
// select it. Our own changes use pushState, which fires no event, so they announce themselves with this one.
const CHANGED = "secondopinion:review-entry";

function subscribe(onChange: () => void): () => void {
  window.addEventListener("hashchange", onChange);
  window.addEventListener("popstate", onChange);
  window.addEventListener(CHANGED, onChange);
  return () => {
    window.removeEventListener("hashchange", onChange);
    window.removeEventListener("popstate", onChange);
    window.removeEventListener(CHANGED, onChange);
  };
}

const readHash = () => window.location.hash;
const serverHash = () => "";

/** The open entry (Overview or a claim id in `ids`) and a setter that records it in the hash and history. */
export function useReviewSelection(ids: string[]): [Entry, (entry: Entry) => void] {
  const hash = useSyncExternalStore(subscribe, readHash, serverHash);
  const entry = entryFromHash(hash, ids);
  const select = useCallback((next: Entry) => {
    const url = `${window.location.pathname}${window.location.search}${hashFor(next)}`;
    if (url === `${window.location.pathname}${window.location.search}${window.location.hash}`) return;
    window.history.pushState(null, "", url);
    window.dispatchEvent(new Event(CHANGED));
  }, []);
  return [entry, select];
}
