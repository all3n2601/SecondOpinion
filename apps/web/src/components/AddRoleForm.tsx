"use client";

import { Check, CircleAlert } from "lucide-react";
import { useId, useState } from "react";
import { saveRole } from "@/lib/api";
import { DETAIL_LABEL, ROLE_SECTIONS, ROLE_VIEWS } from "@/lib/roles";
import type { Role, RoleView } from "@/lib/types";
import { buttonSecondary, fieldInput, fieldLabel } from "@/lib/ui";

/** Add a reviewer role without touching code. Saved to roles.yaml by the API. */
export default function AddRoleForm({ onAdded }: { onAdded: (roles: Role[], added: Role) => void }) {
  const id = useId();
  const [name, setName] = useState("");
  const [sections, setSections] = useState<string[]>([]);
  const [detail, setDetail] = useState<Role["detail"]>("standard");
  const [view, setView] = useState<RoleView>("checklist");
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
      const roles = await saveRole({ name: name.trim(), sections: ordered, detail, explain_terms: explainTerms, view });
      const added = roles[roles.length - 1];
      setName("");
      setSections([]);
      setDetail("standard");
      setView("checklist");
      setExplainTerms(false);
      onAdded(roles, added);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  const levels = Object.keys(DETAIL_LABEL) as Role["detail"][];

  return (
    <form
      onSubmit={submit}
      className="mt-2 max-w-2xl space-y-5 rounded-panel border border-rule bg-sheet p-5"
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
          className={`${fieldInput} mt-1 max-w-sm`}
        />
      </div>

      <fieldset>
        <legend className={fieldLabel}>What this role sees</legend>
        <div className="mt-1 grid gap-x-4 sm:grid-cols-2">
          {ROLE_SECTIONS.map((section) => (
            <label key={section.id} className="flex min-h-11 cursor-pointer items-center gap-3 text-sm text-ink">
              <input
                type="checkbox"
                checked={sections.includes(section.id)}
                onChange={() => toggleSection(section.id)}
                className="size-5 shrink-0 cursor-pointer accent-pen"
              />
              {section.label}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset>
        <legend className={fieldLabel}>Level of detail</legend>
        <div className="mt-2 grid grid-cols-3 sm:inline-grid">
          {levels.map((level, i) => {
            const selected = detail === level;
            return (
              <label key={level} className="relative flex cursor-pointer">
                <input
                  type="radio"
                  name={`${id}-detail`}
                  value={level}
                  checked={selected}
                  onChange={() => setDetail(level)}
                  className="peer sr-only"
                />
                <span
                  className={`flex min-h-11 w-full items-center justify-center gap-1.5 border px-4 py-2 text-sm transition-colors duration-150 peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-pen ${
                    i === 0 ? "rounded-l-control" : "-ml-px"
                  } ${i === levels.length - 1 ? "rounded-r-control" : ""} ${
                    selected
                      ? "border-pen bg-pen font-semibold text-white"
                      : "border-rule-strong bg-sheet font-medium text-ink hover:bg-wash"
                  }`}
                >
                  {selected && <Check aria-hidden="true" className="size-4 shrink-0" strokeWidth={2.5} />}
                  {DETAIL_LABEL[level]}
                </span>
              </label>
            );
          })}
        </div>
      </fieldset>

      <fieldset>
        <legend className={fieldLabel}>How it looks</legend>
        <div className="mt-1">
          {ROLE_VIEWS.map((option) => (
            <label key={option.id} className="flex min-h-11 cursor-pointer items-start gap-3 py-2 text-sm text-ink">
              <input
                type="radio"
                name={`${id}-view`}
                value={option.id}
                checked={view === option.id}
                onChange={() => setView(option.id)}
                className="mt-0.5 size-5 shrink-0 cursor-pointer accent-pen"
              />
              <span>
                <span className="font-medium">{option.label}</span>
                <span className="block text-ink-soft">{option.description}</span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      <label className="flex min-h-11 cursor-pointer items-center gap-3 text-sm text-ink">
        <input
          type="checkbox"
          checked={explainTerms}
          onChange={(e) => setExplainTerms(e.target.checked)}
          className="size-5 shrink-0 cursor-pointer accent-pen"
        />
        Explain terms in plain words
      </label>

      {error && (
        <p role="alert" className="flex items-start gap-1.5 text-sm font-medium text-contradicted">
          <CircleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          {error}
        </p>
      )}

      <button type="submit" disabled={saving} className={buttonSecondary}>
        {saving ? "Saving…" : "Add role"}
      </button>
    </form>
  );
}
