"use client";

import { ChevronRight, CircleAlert } from "lucide-react";
import { useId } from "react";
import { useAudit } from "@/lib/audit-context";
import { useRoles } from "@/lib/roles";
import { fieldInput, fieldLabel, focusRing } from "@/lib/ui";
import AddRoleForm from "./AddRoleForm";

/** "Viewing as" role select. The choice is kept in the shared audit state (setRole). */
export default function RolePicker({ allowAdd = true }: { allowAdd?: boolean }) {
  const id = useId();
  const { role, setRole } = useAudit();
  const { roles, error, setRoles } = useRoles();
  const known = roles?.some((r) => r.name === role) ?? false;

  return (
    <div className="text-sm">
      <div className="flex flex-col gap-1">
        <label htmlFor={id} className={fieldLabel}>
          Viewing as
        </label>
        <select
          id={id}
          value={role}
          onChange={(e) => setRole(e.target.value)}
          disabled={roles === null}
          className={`${fieldInput} sm:max-w-xs`}
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
        <p role="alert" className="mt-2 flex items-start gap-1.5 font-medium text-contradicted">
          <CircleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          Could not load roles: {error}
        </p>
      )}
      {allowAdd && (
        <details className="group mt-1">
          <summary
            className={`inline-flex min-h-11 cursor-pointer list-none items-center gap-1.5 rounded-control pr-2 font-medium text-pen underline-offset-4 hover:underline [&::-webkit-details-marker]:hidden ${focusRing}`}
          >
            <ChevronRight
              aria-hidden="true"
              className="size-4 transition-transform duration-150 group-open:rotate-90"
            />
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
