// Roles shared by every component on the page: one fetch, and a role added in one place
// shows up in every picker straight away.

import { useEffect, useSyncExternalStore } from "react";
import { getRoles } from "./api";
import { useAudit } from "./audit-context";
import type { Role, RoleView } from "./types";

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

/** Must match VALID_VIEWS in second_opinion/roles.py. */
export const ROLE_VIEWS: { id: RoleView; label: string; description: string }[] = [
  { id: "story", label: "Story", description: "A short written summary of what held up and what did not." },
  { id: "checklist", label: "Checklist", description: "Claims in a list to accept or override, one by one." },
  { id: "evidence", label: "Evidence", description: "Each claim next to the numbers and checks behind it." },
  { id: "raw", label: "Raw data", description: "Plain tables and files, with only a terse one-line summary." },
];

const VIEW_IDS = new Set<string>(ROLE_VIEWS.map((v) => v.id));

/** The view for a role name. Unknown name, roles not loaded, or a hand-edited unknown value all read as "checklist". */
export function viewFor(roles: Role[] | null, name: string): RoleView {
  const view = roles?.find((r) => r.name === name)?.view;
  return view !== undefined && VIEW_IDS.has(view) ? view : "checklist";
}

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

/** True once the roles have loaded or failed to load: the view will not change on its own after that. */
export function rolesSettled(roles: Role[] | null, error: string | null): boolean {
  return roles !== null || error !== null;
}

/**
 * The view of the role currently chosen on the Review page. `view` reads "checklist" while the roles load, so the
 * layout can render at once; `ready` turns true when that answer is final (roles loaded, or failed to load).
 */
export function useRoleView(): { view: RoleView; ready: boolean } {
  const { role } = useAudit();
  const { roles, error } = useRoles();
  return { view: viewFor(roles, role), ready: rolesSettled(roles, error) };
}
