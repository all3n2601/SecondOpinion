"use client";

import { useId } from "react";
import { useAudit } from "@/lib/audit-context";
import { useRoles } from "@/lib/roles";
import { fieldInput, focusRing } from "@/lib/ui";
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
        <label htmlFor={id} className="font-semibold whitespace-nowrap text-slate-700">
          Viewing as
        </label>
        <select
          id={id}
          value={role}
          onChange={(e) => setRole(e.target.value)}
          disabled={roles === null}
          className={`${fieldInput} w-auto min-w-[12rem] pr-8`}
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
        <p role="alert" className="mt-2 text-red-800">
          Could not load roles: {error}
        </p>
      )}
      {allowAdd && (
        <details className="group mt-2">
          <summary
            className={`inline-flex cursor-pointer list-none items-center gap-1 rounded-sm font-medium text-emerald-900 hover:underline ${focusRing}`}
          >
            <span aria-hidden="true" className="transition-transform group-open:rotate-45">
              +
            </span>
            Add a role
          </summary>
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
