// Roles shared by every component on the page: one fetch, and a role added in one place
// shows up in every picker straight away.

import { useEffect, useSyncExternalStore } from "react";
import { getRoles } from "./api";
import type { Role } from "./types";

/** Must match VALID_SECTIONS in second_opinion/roles.py. */
export const ROLE_SECTIONS: { id: string; label: string }[] = [
  { id: "decision", label: "Decision" },
  { id: "counts", label: "Counts by verdict" },
  { id: "sign_off", label: "Who must sign off" },
  { id: "claims", label: "Claims and verdicts" },
  { id: "review_queue", label: "Review progress" },
  { id: "decision_record", label: "Decision Record" },
  { id: "corrected_wording", label: "Corrected wording" },
  { id: "robustness", label: "Robustness" },
  { id: "skeptic", label: "Skeptic tests" },
  { id: "sample_ids", label: "Sample IDs" },
  { id: "files", label: "Files and checksums" },
  { id: "code", label: "Code" },
];

export const DETAIL_LABEL: Record<Role["detail"], string> = {
  summary: "Summary",
  standard: "Standard",
  full: "Full",
};

interface RolesSnapshot {
  roles: Role[] | null;
  error: string | null;
}

const EMPTY: RolesSnapshot = { roles: null, error: null };
let snapshot: RolesSnapshot = EMPTY;
let loading = false;
const listeners = new Set<() => void>();

function emit(next: RolesSnapshot) {
  snapshot = next;
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function load() {
  if (loading) return;
  loading = true;
  getRoles()
    .then((roles) => emit({ roles, error: null }))
    .catch((err: Error) => emit({ roles: snapshot.roles, error: err.message }))
    .finally(() => {
      loading = false;
    });
}

export function useRoles() {
  const current = useSyncExternalStore(subscribe, () => snapshot, () => EMPTY);
  useEffect(() => {
    if (snapshot.roles === null) load();
  }, []);
  return {
    roles: current.roles,
    error: current.error,
    setRoles: (roles: Role[]) => emit({ roles, error: null }),
  };
}
