"use client";

// The one place that holds the working state of an audit: the report, the claims the user keeps,
// the audit result and the reviews. The API is stateless, so the browser owns all of this and sends
// it back on each call. The provider sits in the root layout, so state survives page navigation.
// It is also copied to sessionStorage (tab-scoped, see persist.ts) so a reload does not lose it.
// The first render is always the empty state, so server and client markup match; the stored copy is
// restored in an effect after mount, and `hydrated` says when that has happened.

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { classifySentence } from "./api";
import { clearNarrationCache } from "./use-narration";
import {
  clearPersisted,
  DEFAULT_ROLE,
  emptyState,
  loadPersisted,
  savePersisted,
  type PersistedState,
  type DecisionDraft,
  type RecordedDecision,
} from "./persist";
import type { AuditResult, Claim, ExtractResult, Review, SentenceInfo } from "./types";

export { DEFAULT_ROLE };

const WRITE_DELAY_MS = 250;
const defaultReleaseDir = () => process.env.NEXT_PUBLIC_DEFAULT_RELEASE_DIR ?? "";

export interface AuditState {
  reportText: string;
  setReportText: (text: string) => void;
  releaseDir: string;
  setReleaseDir: (dir: string) => void;

  sentences: SentenceInfo[];
  claims: Claim[];
  /** Store a fresh extraction. Clears any earlier audit, since it no longer matches. */
  setExtract: (result: ExtractResult) => void;
  /** Untick a claim sentence, or tick a skipped one (asks the API to classify it). Throws on API error. */
  toggleClaim: (sentenceIndex: number) => Promise<void>;

  audit: AuditResult | null;
  setAudit: (result: AuditResult | null) => void;
  /** Record (or clear, with null) a person's review of one claim; stored on audit.claims[i].review. */
  setReview: (claimId: string, review: Review | null) => void;

  role: string;
  setRole: (name: string) => void;

  /** The exported decision, or null. Any change to the audit or its reviews clears it: it no longer applies. */
  decision: RecordedDecision | null;
  setDecision: (decision: RecordedDecision | null) => void;
  /** The decision form before export (choice, reason, role); cleared together with the decision. */
  draft: DecisionDraft | null;
  updateDraft: (patch: Partial<DecisionDraft>) => void;

  /** False on the server and on the first client render; true once any stored state has been restored. */
  hydrated: boolean;
  /** Forget everything (memory and sessionStorage): report, extraction, audit, reviews and role. */
  reset: () => void;
}

const AuditContext = createContext<AuditState | null>(null);

/** Next free id after the highest "C<n>" in use, so a ticked sentence never reuses an id. */
function nextClaimId(claims: Claim[]): string {
  const highest = claims.reduce((max, c) => {
    const n = Number(/^C(\d+)$/.exec(c.id)?.[1] ?? 0);
    return Math.max(max, n);
  }, 0);
  return `C${highest + 1}`;
}

export function AuditProvider({ children }: { children: React.ReactNode }) {
  const [reportText, setReportText] = useState("");
  const [releaseDir, setReleaseDir] = useState(defaultReleaseDir);
  const [sentences, setSentences] = useState<SentenceInfo[]>([]);
  const [claims, setClaims] = useState<Claim[]>([]);
  const [audit, setAudit] = useState<AuditResult | null>(null);
  const [role, setRole] = useState(DEFAULT_ROLE);
  const [decision, setRecorded] = useState<RecordedDecision | null>(null);
  const [draft, setDraft] = useState<DecisionDraft | null>(null);
  // The draft and the recorded decision are about the same audit, so they always go together.
  const setDecision = useCallback((next: RecordedDecision | null) => {
    setRecorded(next);
    if (next === null) setDraft(null);
  }, []);
  const updateDraft = useCallback((patch: Partial<DecisionDraft>) => {
    setDraft((prev) => ({ choice: null, reason: "", reviewer_role: null, ...prev, ...patch }));
  }, []);
  const [hydrated, setHydrated] = useState(false);
  // The latest state worth saving; null until restore has run, so we never overwrite storage with the empty first render.
  const latest = useRef<PersistedState | null>(null);

  // Restore after mount (never during render, so hydration matches). Reading an external store
  // (sessionStorage) into state on mount is exactly what this lint rule cannot tell from a cascade.
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    const stored = loadPersisted(defaultReleaseDir());
    if (stored) {
      setReportText(stored.reportText);
      setReleaseDir(stored.releaseDir);
      setSentences(stored.sentences);
      setClaims(stored.claims);
      setAudit(stored.audit);
      setRole(stored.role);
      setRecorded(stored.decision);
      setDraft(stored.draft);
    }
    setHydrated(true);
  }, []);
  /* eslint-enable react-hooks/set-state-in-effect */

  const snapshot = useMemo<PersistedState>(
    () => ({ reportText, releaseDir, sentences, claims, audit, role, decision, draft }),
    [reportText, releaseDir, sentences, claims, audit, role, decision, draft],
  );

  // Debounced write: typing in the report box must not hit storage on every keystroke.
  useEffect(() => {
    if (!hydrated) return;
    latest.current = snapshot;
    const timer = setTimeout(() => savePersisted(snapshot), WRITE_DELAY_MS);
    return () => clearTimeout(timer);
  }, [hydrated, snapshot]);

  // A reload or tab switch inside the debounce window would lose the last edit, so flush on the way out.
  useEffect(() => {
    const flush = () => {
      if (latest.current) savePersisted(latest.current);
    };
    const onVisibility = () => {
      if (document.visibilityState === "hidden") flush();
    };
    window.addEventListener("pagehide", flush);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.removeEventListener("pagehide", flush);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

  const reset = useCallback(() => {
    const fresh = emptyState(defaultReleaseDir());
    latest.current = fresh;
    clearPersisted();
    clearNarrationCache();
    setReportText(fresh.reportText);
    setReleaseDir(fresh.releaseDir);
    setSentences(fresh.sentences);
    setClaims(fresh.claims);
    setAudit(fresh.audit);
    setRole(fresh.role);
    setRecorded(fresh.decision);
    setDraft(fresh.draft);
  }, []);

  const setExtract = useCallback((result: ExtractResult) => {
    setSentences(result.sentences);
    setClaims(result.claims);
    setAudit(null);
    setRecorded(null);
    setDraft(null);
  }, []);

  const toggleClaim = useCallback(
    async (sentenceIndex: number) => {
      const sentence = sentences.find((s) => s.index === sentenceIndex);
      if (!sentence) return;

      if (sentence.claim_id) {
        const removedId = sentence.claim_id;
        setClaims((prev) => prev.filter((c) => c.id !== removedId));
        setSentences((prev) => prev.map((s) => (s.index === sentenceIndex ? { ...s, claim_id: null } : s)));
      } else {
        const classified = await classifySentence(sentence.text, sentenceIndex);
        const claim: Claim = { ...classified, id: nextClaimId(claims) };
        setClaims((prev) => [...prev, claim].sort((a, b) => a.sentence_index - b.sentence_index));
        setSentences((prev) => prev.map((s) => (s.index === sentenceIndex ? { ...s, claim_id: claim.id } : s)));
      }
      // The claim set changed, so an earlier audit (and any decision on it) no longer describes it.
      setAudit(null);
      setRecorded(null);
      setDraft(null);
    },
    [sentences, claims],
  );

  // A new audit replaces the old one, so a decision recorded on the old one goes with it.
  const replaceAudit = useCallback((result: AuditResult | null) => {
    setAudit(result);
    setRecorded(null);
    setDraft(null);
  }, []);

  const setReview = useCallback((claimId: string, review: Review | null) => {
    // The decision (and its draft) was made on the reviews as they were.
    setRecorded(null);
    setDraft(null);
    setAudit((prev) =>
      prev && {
        ...prev,
        claims: prev.claims.map((c) => (c.claim.id === claimId ? { ...c, review } : c)),
      },
    );
  }, []);

  const value = useMemo<AuditState>(
    () => ({
      reportText,
      setReportText,
      releaseDir,
      setReleaseDir,
      sentences,
      claims,
      setExtract,
      toggleClaim,
      audit,
      setAudit: replaceAudit,
      setReview,
      role,
      setRole,
      decision,
      setDecision,
      draft,
      updateDraft,
      hydrated,
      reset,
    }),
    [reportText, releaseDir, sentences, claims, setExtract, toggleClaim, audit, replaceAudit, setReview, role, decision, setDecision, draft, updateDraft, hydrated, reset],
  );

  return <AuditContext.Provider value={value}>{children}</AuditContext.Provider>;
}

export function useAudit(): AuditState {
  const state = useContext(AuditContext);
  if (!state) throw new Error("useAudit() must be used inside <AuditProvider> (it is in the root layout).");
  return state;
}
