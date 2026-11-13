"use client";

import { CircleAlert, CircleCheck, CircleX, TriangleAlert } from "lucide-react";
import { useId, useState } from "react";
import { runAudit } from "@/lib/api";
import type { ReleaseInfo } from "@/lib/types";
import { buttonSecondary, fieldHint, fieldInput, fieldLabel, sectionTitle } from "@/lib/ui";
import GlossaryTerm from "./GlossaryTerm";

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

  const extraFiles = check.state === "ok" ? check.release.files.filter((f) => !REQUIRED_FILES.includes(f.file)) : [];

  return (
    <section aria-labelledby="release-heading">
      <h3 id="release-heading" className={sectionTitle}>
        2. Data folder
      </h3>

      <div className="mt-3">
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
            className={`${fieldInput} min-w-0 flex-1 basis-64 font-mono text-sm`}
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
          The folder with the TCGA-BRCA <GlossaryTerm term="release">release</GlossaryTerm> files, for example an unsealed envelope’s <code className="font-mono">release/</code>{" "}
          folder.
        </p>
      </div>

      <div aria-live="polite" className="mt-4">
        {check.state === "error" && (
          <p className="flex items-start gap-2 font-medium text-contradicted">
            <CircleAlert aria-hidden="true" size={16} strokeWidth={1.75} className="mt-1 shrink-0" />
            <span>
              {check.message} Check the folder path, then choose “Check the files” again.
            </span>
          </p>
        )}
        {check.state === "ok" && (
          <div>
            <p className={`flex items-start gap-2 font-medium ${found === REQUIRED_FILES.length ? "text-supported" : "text-insufficient"}`}>
              {found === REQUIRED_FILES.length ? (
                <CircleCheck aria-hidden="true" size={16} strokeWidth={1.75} className="mt-1 shrink-0" />
              ) : (
                <CircleAlert aria-hidden="true" size={16} strokeWidth={1.75} className="mt-1 shrink-0" />
              )}
              <span>
                {found} of {REQUIRED_FILES.length} data files found (release {check.release.name}).{" "}
                <GlossaryTerm term="checksum">Checksums</GlossaryTerm> below.
              </span>
            </p>
            {check.notes.length > 0 && (
              <ul className="mt-2 space-y-1 text-sm text-insufficient">
                {check.notes.map((note) => (
                  <li key={note} className="flex items-start gap-2">
                    <TriangleAlert aria-hidden="true" size={16} strokeWidth={1.75} className="mt-0.5 shrink-0" />
                    <span>{note}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      {check.state === "ok" && (
        <ul aria-label="Release files and their SHA-256 checksums" className="mt-3 divide-y divide-rule rounded-control border border-rule bg-paper">
          {REQUIRED_FILES.map((name) => {
            const file = check.release.files.find((r) => r.file === name);
            return <FileRow key={name} name={name} sha256={file?.sha256 ?? null} />;
          })}
          {extraFiles.map((f) => (
            <FileRow key={f.file} name={f.file} sha256={f.sha256} />
          ))}
        </ul>
      )}
    </section>
  );
}

function FileRow({ name, sha256 }: { name: string; sha256: string | null }) {
  return (
    <li className="flex items-start gap-2 px-3 py-2 text-sm">
      {sha256 ? (
        <CircleCheck aria-hidden="true" size={16} strokeWidth={1.75} className="mt-1 shrink-0 text-supported" />
      ) : (
        <CircleX aria-hidden="true" size={16} strokeWidth={1.75} className="mt-1 shrink-0 text-contradicted" />
      )}
      <div className="min-w-0">
        <p className="font-mono break-all">
          {name}
          {!sha256 && <span className="font-sans font-medium text-contradicted"> is missing from this folder</span>}
        </p>
        {sha256 && (
          <p className="num font-mono text-xs break-all text-ink-soft">
            <span className="sr-only">SHA-256 </span>
            {sha256}
          </p>
        )}
      </div>
    </li>
  );
}
