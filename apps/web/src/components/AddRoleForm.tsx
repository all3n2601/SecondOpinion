"use client";

import { useId, useState } from "react";
import { saveRole } from "@/lib/api";
import { DETAIL_LABEL, ROLE_SECTIONS } from "@/lib/roles";
import type { Role } from "@/lib/types";

const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-900";

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
    <form onSubmit={submit} className="mt-3 space-y-4 rounded-lg border border-slate-300 bg-white p-4" noValidate>
      <div>
        <label htmlFor={`${id}-name`} className="block text-sm font-medium">
          Role name
        </label>
        <input
          id={`${id}-name`}
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          className={`mt-1 w-full max-w-sm rounded-md border border-slate-400 px-3 py-2 ${FOCUS}`}
        />
      </div>

      <fieldset>
        <legend className="text-sm font-medium">What this role sees</legend>
        <div className="mt-2 grid gap-2 sm:grid-cols-3">
          {ROLE_SECTIONS.map((section) => (
            <label key={section.id} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={sections.includes(section.id)}
                onChange={() => toggleSection(section.id)}
                className={FOCUS}
              />
              {section.label}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset>
        <legend className="text-sm font-medium">Level of detail</legend>
        <div className="mt-2 flex flex-wrap gap-4">
          {(Object.keys(DETAIL_LABEL) as Role["detail"][]).map((level) => (
            <label key={level} className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name={`${id}-detail`}
                value={level}
                checked={detail === level}
                onChange={() => setDetail(level)}
                className={FOCUS}
              />
              {DETAIL_LABEL[level]}
            </label>
          ))}
        </div>
      </fieldset>

      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={explainTerms}
          onChange={(e) => setExplainTerms(e.target.checked)}
          className={FOCUS}
        />
        Explain terms in plain words
      </label>

      {error && (
        <p role="alert" className="text-sm font-medium text-rose-800">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={saving}
        className={`rounded-md bg-emerald-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-60 ${FOCUS}`}
      >
        {saving ? "Saving…" : "Add role"}
      </button>
    </form>
  );
}
