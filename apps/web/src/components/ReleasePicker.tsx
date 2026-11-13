"use client";

import { useId, useState } from "react";
import { runAudit } from "@/lib/api";
import type { ReleaseInfo } from "@/lib/types";
import { buttonSecondary, fieldHint, fieldInput, fieldLabel, tableHead } from "@/lib/ui";
import Panel from "./Panel";

/** Mirrors RELEASE_FILES in second_opinion/release.py. The RNA file is optional. */
export const REQUIRED_FILES = [
  "clinical.tsv",
  "survival.tsv",
  "mutation_gene_level.tsv.gz",
  "copy_number_gistic.tsv.gz",
  "protein_rppa.tsv.gz",
];

export type ReleaseCheck =
  | { state: "idle" }
  | { state: "checking" }
  | { state: "ok"; release: ReleaseInfo; notes: string[]; found: number }
  | { state: "error"; message: string };

interface Props {
  value: string;
  onChange: (dir: string) => void;
  onCheck?: (check: ReleaseCheck) => void;
}

/** Where the data lives. "Check the files" runs an audit with no claims, which verifies the folder. */
export default function ReleasePicker({ value, onChange, onCheck }: Props) {
  const inputId = useId();
  const hintId = useId();
  const [check, setCheckState] = useState<ReleaseCheck>({ state: "idle" });

  function setCheck(next: ReleaseCheck) {
    setCheckState(next);
    onCheck?.(next);
  }

  async function checkFiles() {
    setCheck({ state: "checking" });
    try {
      const result = await runAudit(value.trim(), []);
      const found = REQUIRED_FILES.filter((f) => result.release.files.some((r) => r.file === f)).length;
      setCheck({ state: "ok", release: result.release, notes: result.notes, found });
    } catch (error) {
      setCheck({ state: "error", message: (error as Error).message });
    }
  }

  return (
    <Panel id="release-heading" title="2 · Data source" description="The TCGA-BRCA release the report describes.">
      <label htmlFor={inputId} className={fieldLabel}>
        Release folder
      </label>
      <div className="mt-2 flex flex-wrap gap-3">
        <input
          id={inputId}
          type="text"
          value={value}
          onChange={(e) => {
            onChange(e.target.value);
            setCheck({ state: "idle" });
          }}
          aria-describedby={hintId}
          placeholder="/path/to/oncosys-hackathon-challenge/data/tcga-brca/raw"
          spellCheck={false}
          className={`${fieldInput} min-w-0 flex-1 font-mono text-[0.8rem]`}
        />
        <button
          type="button"
          onClick={checkFiles}
          disabled={!value.trim() || check.state === "checking"}
          className={buttonSecondary}
        >
          {check.state === "checking" ? "Checking…" : "Check the files"}
        </button>
      </div>
      <p id={hintId} className={fieldHint}>
        A full release, or an unsealed envelope’s <code className="font-mono text-[0.8rem]">release/</code> folder.
      </p>

      <div aria-live="polite" className="mt-4 text-sm">
        {check.state === "error" && (
          <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 font-medium text-red-900">
            <span aria-hidden="true">✕ </span>
            {check.message}
          </p>
        )}
        {check.state === "ok" && (
          <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-emerald-950">
            <p className="font-medium">
              <span aria-hidden="true">✓ </span>
              {check.found} of {REQUIRED_FILES.length} data files found (release {check.release.name}). Checksums below.
            </p>
            {check.notes.length > 0 && (
              <ul className="mt-1 list-disc pl-5 text-amber-900">
                {check.notes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      {check.state === "ok" && (
        <div className="mt-4 overflow-hidden rounded-md border border-slate-200">
          <table className="w-full table-fixed text-left text-sm">
            <caption className="sr-only">Release files and their SHA-256 checksums</caption>
            <thead className={tableHead}>
              <tr>
                <th scope="col" className="w-2/5 px-3 py-2">
                  File
                </th>
                <th scope="col" className="px-3 py-2">
                  SHA-256
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {check.release.files.map((f) => (
                <tr key={f.file} className="align-top">
                  <td className="px-3 py-2 font-mono text-[0.8rem] break-all">{f.file}</td>
                  <td className="px-3 py-2 font-mono text-xs break-all text-slate-600">{f.sha256}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}
