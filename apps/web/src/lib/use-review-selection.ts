"use client";

import { useCallback, useSyncExternalStore } from "react";
import { entryFromHash, hashFor, isOwnHash, type Entry } from "./review-nav";

// The Review page's open entry lives in the URL hash, so reload, back / forward and plain `#review-C2` links all
// select it. Our own changes use pushState, which fires no event, so they announce themselves with this one.
const CHANGED = "secondopinion:review-entry";

/** Next's own link navigation (the steps rail's "Review") calls pushState with no event; the Navigation API, where
 * the browser has it, reports every URL change. */
function navigationApi(): EventTarget | undefined {
  return (window as Window & { navigation?: EventTarget }).navigation;
}

function subscribe(onChange: () => void): () => void {
  // Next updates history from inside its own commit, where React allows no new update: answer a moment later.
  const later = () => queueMicrotask(onChange);
  window.addEventListener("hashchange", onChange);
  window.addEventListener("popstate", onChange);
  window.addEventListener(CHANGED, onChange);
  navigationApi()?.addEventListener("currententrychange", later);
  return () => {
    window.removeEventListener("hashchange", onChange);
    window.removeEventListener("popstate", onChange);
    window.removeEventListener(CHANGED, onChange);
    navigationApi()?.removeEventListener("currententrychange", later);
  };
}

// The last hash that was ours. Another fragment (the skip link's `#content`) leaves the open entry as it was.
let lastOwn = "";
const readHash = () => {
  const hash = window.location.hash;
  if (isOwnHash(hash)) lastOwn = hash;
  return lastOwn;
};
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
