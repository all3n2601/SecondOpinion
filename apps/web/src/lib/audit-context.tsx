"use client";

// The one place that holds the working state of an audit: the report, the claims the user keeps,
// the audit result and the reviews. The API is stateless, so the browser owns all of this and sends
// it back on each call. The provider sits in the root layout, so state survives page navigation,
// and it is mirrored to sessionStorage so a page refresh keeps it (closing the tab clears it).

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { classifySentence } from "./api";
import type { AuditResult, Claim, ExtractResult, Review, SentenceInfo } from "./types";

export const DEFAULT_ROLE = "Data-use reviewer";

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

  /** False until the saved session (if any) has been restored after the first render. */
  restored: boolean;
  /** Clear everything and start a new audit. */
  reset: () => void;
}

const STORAGE_KEY = "second-opinion:audit:v1";

interface Saved {
  reportText: string;
  releaseDir: string;
  sentences: SentenceInfo[];
  claims: Claim[];
  audit: AuditResult | null;
  role: string;
}

function readSaved(): Partial<Saved> | null {
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Partial<Saved>) : null;
  } catch {
    return null; // storage blocked or corrupt: start fresh
  }
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
  const [releaseDir, setReleaseDir] = useState(process.env.NEXT_PUBLIC_DEFAULT_RELEASE_DIR ?? "");
  const [sentences, setSentences] = useState<SentenceInfo[]>([]);
  const [claims, setClaims] = useState<Claim[]>([]);
  const [audit, setAudit] = useState<AuditResult | null>(null);
  const [role, setRole] = useState(DEFAULT_ROLE);
  const [restored, setRestored] = useState(false);
  const defaultDir = useRef(process.env.NEXT_PUBLIC_DEFAULT_RELEASE_DIR ?? "");

  // Restore after mount (not during render) so server and client HTML match.
  useEffect(() => {
    const saved = readSaved();
    if (saved) {
      /* eslint-disable react-hooks/set-state-in-effect -- one-time restore from browser storage */
      if (typeof saved.reportText === "string") setReportText(saved.reportText);
      if (typeof saved.releaseDir === "string" && saved.releaseDir) setReleaseDir(saved.releaseDir);
      if (Array.isArray(saved.sentences)) setSentences(saved.sentences);
      if (Array.isArray(saved.claims)) setClaims(saved.claims);
      if (saved.audit) setAudit(saved.audit);
      if (typeof saved.role === "string" && saved.role) setRole(saved.role);
    }
    setRestored(true);
    /* eslint-enable react-hooks/set-state-in-effect */
  }, []);

  useEffect(() => {
    if (!restored) return;
    try {
      const data: Saved = { reportText, releaseDir, sentences, claims, audit, role };
      window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    } catch {
      // Storage full or blocked: the app still works, it just won't survive a refresh.
    }
  }, [restored, reportText, releaseDir, sentences, claims, audit, role]);

  const reset = useCallback(() => {
    setReportText("");
    setReleaseDir(defaultDir.current);
    setSentences([]);
    setClaims([]);
    setAudit(null);
    try {
      window.sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore
    }
  }, []);

  const setExtract = useCallback((result: ExtractResult) => {
    setSentences(result.sentences);
    setClaims(result.claims);
    setAudit(null);
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
      // The claim set changed, so an earlier audit no longer describes it.
      setAudit(null);
    },
    [sentences, claims],
  );

  const setReview = useCallback((claimId: string, review: Review | null) => {
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
      setAudit,
      setReview,
      role,
      setRole,
      restored,
      reset,
    }),
    [reportText, releaseDir, sentences, claims, setExtract, toggleClaim, audit, setReview, role, restored, reset],
  );

  return <AuditContext.Provider value={value}>{children}</AuditContext.Provider>;
}

export function useAudit(): AuditState {
  const state = useContext(AuditContext);
  if (!state) throw new Error("useAudit() must be used inside <AuditProvider> (it is in the root layout).");
  return state;
}
