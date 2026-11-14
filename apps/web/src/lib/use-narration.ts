"use client";

// Wording for the Review page. The template text renders at once; when the optional AI helper is on,
// we ask it once per narrationKey and swap its slotted text in when it arrives. The browser fills every
// slot from the audit, so a number on screen always comes from the data. Only source "ai" answers are
// cached (sessionStorage, tab-scoped, like persist.ts: the text is derived from patient-research reports).
// A template or failed answer is remembered in memory so the same key is not asked again in this page session.

import { useEffect, useMemo, useRef, useState } from "react";
import { narrate } from "./api";
import { narrationKey, renderNarration, type Slotted } from "./narrate";
import type { ClaimResult, RoleView } from "./types";

export const NARRATION_STORAGE_KEY = "secondopinion:narration:v1";
/** /ai/narrate rejects more claims than this with a 422, so a larger audit keeps its templates. */
export const MAX_NARRATED_CLAIMS = 100;
/** Entries kept in the cache (oldest dropped first) so it cannot grow without bound in one tab. */
const MAX_CACHE_ENTRIES = 20;

function isSlotted(v: unknown): v is Slotted {
  if (typeof v !== "object" || v === null || Array.isArray(v)) return false;
  const o = v as Record<string, unknown>;
  if (typeof o.headline !== "string" || typeof o.caption !== "string") return false;
  const claims = o.claims;
  if (typeof claims !== "object" || claims === null || Array.isArray(claims)) return false;
  return Object.values(claims).every((t) => typeof t === "string");
}

// Every storage access is wrapped: private mode, disabled storage and quota errors must never break the page.
function readAll(): Record<string, unknown> {
  try {
    const raw = globalThis.sessionStorage?.getItem(NARRATION_STORAGE_KEY);
    if (typeof raw !== "string" || raw === "") return {};
    const data: unknown = JSON.parse(raw);
    return typeof data === "object" && data !== null && !Array.isArray(data) ? (data as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

export function readCachedNarration(key: string): Slotted | null {
  const all = readAll();
  if (!Object.prototype.hasOwnProperty.call(all, key)) return null;
  const entry = all[key];
  return isSlotted(entry) ? entry : null;
}

export function writeCachedNarration(key: string, value: Slotted): void {
  try {
    const all = readAll();
    delete all[key]; // re-insert so it counts as the newest
    all[key] = value;
    const keys = Object.keys(all);
    for (const old of keys.slice(0, Math.max(0, keys.length - MAX_CACHE_ENTRIES))) delete all[old];
    globalThis.sessionStorage?.setItem(NARRATION_STORAGE_KEY, JSON.stringify(all));
  } catch {
    // Quota exceeded or storage disabled: the text just is not kept across reloads.
  }
}

// Keys the helper answered "template" or failed for: not retried in this page session.
const unavailable = new Set<string>();
// One request per key at a time, shared by every mounted copy of the hook.
const inflight = new Map<string, Promise<Slotted | null>>();
// Bumped by clearNarrationCache so a response that was in flight during a reset is not stored.
let generation = 0;

export function clearNarrationCache(): void {
  generation += 1;
  unavailable.clear();
  inflight.clear();
  try {
    globalThis.sessionStorage?.removeItem(NARRATION_STORAGE_KEY);
  } catch {
    // nothing to do
  }
}

/** Ask for AI wording; resolves to the slotted text, or null for a template answer or any failure. Never rejects. */
function fetchNarration(key: string, view: RoleView, claims: ClaimResult[]): Promise<Slotted | null> {
  const started = generation;
  const promise = narrate(view, claims)
    .then((res): Slotted | null => {
      if (res.source !== "ai" || res.headline === null || res.caption === null || res.claims === null) return null;
      const value: Slotted = { headline: res.headline, caption: res.caption, claims: res.claims };
      if (!isSlotted(value)) return null;
      if (started === generation) writeCachedNarration(key, value);
      return value;
    })
    .catch(() => null)
    .then((value) => {
      if (started === generation) {
        inflight.delete(key);
        if (value === null) unavailable.add(key);
      }
      return value;
    });
  inflight.set(key, promise);
  return promise;
}

/**
 * The claims to narrate, or null to ask for nothing yet: until saved state has loaded (the hook reads
 * sessionStorage while rendering) and the role's view is settled (otherwise the "checklist" placeholder would
 * cost a model call, then a second one for the real view).
 */
export function narrationClaims(hydrated: boolean, rolesReady: boolean, claims: ClaimResult[] | null): ClaimResult[] | null {
  return hydrated && rolesReady ? claims : null;
}

/**
 * Narration for the Review page. Renders template text immediately (or the cached AI text), fetches AI wording
 * once per key when the helper has not answered yet, and never throws. `pending` is true while that request is open.
 */
export function useNarration(view: RoleView, claims: ClaimResult[] | null) {
  const key = claims && claims.length > 0 ? narrationKey(view, claims) : null;
  const eligible = key !== null && claims !== null && claims.length <= MAX_NARRATED_CLAIMS;
  const [fetched, setFetched] = useState<{ key: string; value: Slotted } | null>(null);
  // Bumped when a request ends without usable text, so `pending` is recomputed.
  const [, setSettledCount] = useState(0);
  const latestKey = useRef<string | null>(null);

  const cached = useMemo(() => (key === null ? null : readCachedNarration(key)), [key]);
  const ai = fetched !== null && fetched.key === key ? fetched.value : cached;

  const claimsRef = useRef(claims);
  useEffect(() => {
    claimsRef.current = claims;
  }, [claims]);

  useEffect(() => {
    latestKey.current = key;
    const current = claimsRef.current;
    if (!eligible || key === null || current === null) return;
    if (readCachedNarration(key) !== null || unavailable.has(key)) return;
    const request = inflight.get(key) ?? fetchNarration(key, view, current);
    void request.then((value) => {
      // A response for a key the page has moved on from must not replace the current text.
      if (latestKey.current !== key) return;
      if (value !== null) setFetched({ key, value });
      else setSettledCount((n) => n + 1);
    });
  }, [key, view, eligible]);

  const rendered = useMemo(() => renderNarration(view, claims ?? [], ai), [view, claims, ai]);
  const pending = eligible && key !== null && ai === null && !unavailable.has(key);
  return { ...rendered, pending };
}
