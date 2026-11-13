"use client";

import { useId, useState } from "react";
import { saveRole } from "@/lib/api";
import { DETAIL_LABEL, ROLE_SECTIONS } from "@/lib/roles";
import type { Role } from "@/lib/types";
import { buttonPrimary, fieldInput, fieldLabel, focusRing } from "@/lib/ui";

const CONTROL = `size-4 accent-emerald-900 ${focusRing}`;

/** Add a reviewer role without touching code. Saved to roles.yaml by the API. */
export default function AddRoleForm({ onAdded }: { onAdded: (roles: Role[], added: Role) => void }) {
  const id = useId();
  const [name, setName] = useState("");
  const [sections, setSections] = useState<string[]>([]);
  const [detail, setDetail] = useState<Role["detail"]>("standard");
  const [explainTerms, setExplainTerms] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function toggleSection(section: string) {
    setSections((prev) => (prev.includes(section) ? prev.filter((s) => s !== section) : [...prev, section]));
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim()) return setError("Give the role a name.");
    if (sections.length === 0) return setError("Pick at least one section.");
    setSaving(true);
    setError(null);
    try {
      const ordered = ROLE_SECTIONS.map((s) => s.id).filter((s) => sections.includes(s));
      const roles = await saveRole({ name: name.trim(), sections: ordered, detail, explain_terms: explainTerms });
      const added = roles[roles.length - 1];
      setName("");
      setSections([]);
      setDetail("standard");
      setExplainTerms(false);
      onAdded(roles, added);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form
      onSubmit={submit}
      className="mt-3 space-y-4 rounded-md border border-slate-200 bg-slate-50 p-4 text-left"
      noValidate
    >
      <div>
        <label htmlFor={`${id}-name`} className={fieldLabel}>
          Role name
        </label>
        <input
          id={`${id}-name`}
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          className={`${fieldInput} mt-1.5 max-w-sm`}
        />
      </div>

      <fieldset>
        <legend className={fieldLabel}>What this role sees</legend>
        <div className="mt-2 grid gap-x-4 gap-y-2 sm:grid-cols-2">
          {ROLE_SECTIONS.map((section) => (
            <label key={section.id} className="flex items-center gap-2 text-sm text-slate-800">
              <input
                type="checkbox"
                checked={sections.includes(section.id)}
                onChange={() => toggleSection(section.id)}
                className={CONTROL}
              />
              {section.label}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset>
        <legend className={fieldLabel}>Level of detail</legend>
        <div className="mt-2 flex flex-wrap gap-4">
          {(Object.keys(DETAIL_LABEL) as Role["detail"][]).map((level) => (
            <label key={level} className="flex items-center gap-2 text-sm text-slate-800">
              <input
                type="radio"
                name={`${id}-detail`}
                value={level}
                checked={detail === level}
                onChange={() => setDetail(level)}
                className={CONTROL}
              />
              {DETAIL_LABEL[level]}
            </label>
          ))}
        </div>
      </fieldset>

      <label className="flex items-center gap-2 text-sm text-slate-800">
        <input
          type="checkbox"
          checked={explainTerms}
          onChange={(e) => setExplainTerms(e.target.checked)}
          className={CONTROL}
        />
        Explain terms in plain words
      </label>

      {error && (
        <p role="alert" className="text-sm font-medium text-red-800">
          {error}
        </p>
      )}

      <button type="submit" disabled={saving} className={`${buttonPrimary} h-9`}>
        {saving ? "Saving…" : "Add role"}
      </button>
    </form>
  );
}
