"use client";

import { useId } from "react";
import { useAudit } from "@/lib/audit-context";
import { useRoles } from "@/lib/roles";
import AddRoleForm from "./AddRoleForm";

/** "Viewing as" role select. The choice is kept in the shared audit state (setRole). */
export default function RolePicker({ allowAdd = true }: { allowAdd?: boolean }) {
  const id = useId();
  const { role, setRole } = useAudit();
  const { roles, error, setRoles } = useRoles();
  const known = roles?.some((r) => r.name === role) ?? false;

  return (
    <div className="text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor={id} className="font-medium">
          Viewing as
        </label>
        <select
          id={id}
          value={role}
          onChange={(e) => setRole(e.target.value)}
          disabled={roles === null}
          className="rounded-md border border-slate-400 bg-white px-3 py-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-900"
        >
          {roles === null && <option value={role}>Loading roles…</option>}
          {roles !== null && !known && <option value={role}>{role}</option>}
          {roles?.map((r) => (
            <option key={r.name} value={r.name}>
              {r.name}
            </option>
          ))}
        </select>
      </div>
      {error && (
        <p role="alert" className="mt-2 text-rose-800">
          Could not load roles: {error}
        </p>
      )}
      {allowAdd && (
        <details className="mt-2">
          <summary className="cursor-pointer text-emerald-900 underline underline-offset-4">Add a role</summary>
          <AddRoleForm
            onAdded={(list, added) => {
              setRoles(list);
              setRole(added.name);
            }}
          />
        </details>
      )}
    </div>
  );
}
