"use client";

import { useId, useState } from "react";
import { runAudit } from "@/lib/api";
import type { ReleaseInfo } from "@/lib/types";
import { buttonSecondary, card, fieldHint, fieldInput, fieldLabel } from "@/lib/ui";

/** Mirrors RELEASE_FILES in second_opinion/release.py. The RNA file is optional. */
const REQUIRED_FILES = [
  "clinical.tsv",
  "survival.tsv",
  "mutation_gene_level.tsv.gz",
  "copy_number_gistic.tsv.gz",
  "protein_rppa.tsv.gz",
];

type Check =
  | { state: "idle" }
  | { state: "checking" }
  | { state: "ok"; release: ReleaseInfo; notes: string[] }
  | { state: "error"; message: string };

interface Props {
  value: string;
  onChange: (dir: string) => void;
}

/** Where the data lives. "Check the files" runs an audit with no claims, which verifies the folder. */
export default function ReleasePicker({ value, onChange }: Props) {
  const inputId = useId();
  const hintId = useId();
  const [check, setCheck] = useState<Check>({ state: "idle" });

  async function checkFiles() {
    setCheck({ state: "checking" });
    try {
      const result = await runAudit(value.trim(), []);
      setCheck({ state: "ok", release: result.release, notes: result.notes });
    } catch (error) {
      setCheck({ state: "error", message: (error as Error).message });
    }
  }

  const found =
    check.state === "ok" ? REQUIRED_FILES.filter((f) => check.release.files.some((r) => r.file === f)).length : 0;

  return (
    <section aria-labelledby="release-heading" className={card}>
      <h2 id="release-heading" className="text-xl font-semibold">
        2. The data to check it against
      </h2>

      <div className="mt-5">
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
            className={`${fieldInput} min-w-0 flex-1 font-mono text-sm`}
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
          The folder with the TCGA-BRCA files, for example an unsealed envelope’s <code>release/</code> folder.
        </p>
      </div>

      <div aria-live="polite" className="mt-4">
        {check.state === "error" && (
          <p className="font-medium text-red-800">
            <span aria-hidden="true">✕ </span>
            {check.message}
          </p>
        )}
        {check.state === "ok" && (
          <div>
            <p className="font-medium text-emerald-900">
              <span aria-hidden="true">✓ </span>
              {found} of {REQUIRED_FILES.length} data files found (release {check.release.name}). Checksums below.
            </p>
            {check.notes.length > 0 && (
              <ul className="mt-2 list-disc pl-6 text-sm text-amber-900">
                {check.notes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      {check.state === "ok" && (
        <table className="mt-3 w-full table-fixed text-left text-sm">
          <caption className="sr-only">Release files and their SHA-256 checksums</caption>
          <thead>
            <tr className="border-b border-slate-300 text-slate-700">
              <th scope="col" className="w-2/5 py-2 pr-3 font-semibold">
                File
              </th>
              <th scope="col" className="py-2 font-semibold">
                SHA-256 checksum
              </th>
            </tr>
          </thead>
          <tbody>
            {check.release.files.map((f) => (
              <tr key={f.file} className="border-b border-slate-200 align-top">
                <td className="py-2 pr-3 font-mono break-all">{f.file}</td>
                <td className="py-2 font-mono text-xs break-all text-slate-700">{f.sha256}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
