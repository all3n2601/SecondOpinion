"use client";

import { Check, CircleAlert, CircleCheck, KeyRound, LoaderCircle } from "lucide-react";
import { useId, useRef, useState } from "react";
import { unsealEnvelope, type OpenedEnvelope } from "@/lib/api";
import { buttonQuiet, buttonSecondary, fieldInput, fieldLabel, sectionTitle } from "@/lib/ui";

/** The public practice envelope (envelopes/README.md in the challenge repository). */
const PRACTICE = { number: "practice", words: ["orange", "meadow", "pilot", "lantern"] };
const EMPTY_WORDS = ["", "", "", ""];

type Which = "release_a" | "envelope";
type State =
  | { state: "idle" }
  | { state: "opening"; label: string }
  | { state: "error"; message: string }
  | { state: "opened"; envelope: OpenedEnvelope };

interface Props {
  disabled?: boolean;
  /** The envelope's report and the chosen data folder, to fill in the Start page. */
  onOpened: (reportText: string | null, releaseDir: string) => void;
  /** Change the data folder when the user picks the other release. */
  onReleaseChange: (releaseDir: string) => void;
  /** Run the audit on what was filled in. */
  onAudit: () => void;
  canAudit: boolean;
}

/** "07", "7" or "E07" as the card shows it; "practice" for the rehearsal envelope. */
function label(number: string): string {
  const raw = number.trim();
  if (raw.toLowerCase() === "practice") return "practice";
  const digits = raw.replace(/^e/i, "");
  return /^\d+$/.test(digits) ? `E${digits.padStart(2, "0")}` : raw;
}

/** At the Q&A the judges give an envelope number and a four-word code: open it here, then audit its report. */
export default function EnvelopeOpener({ disabled, onOpened, onReleaseChange, onAudit, canAudit }: Props) {
  const numberId = useId();
  const numberHint = useId();
  const codeHint = useId();
  const statusId = useId();
  const [number, setNumber] = useState("");
  const [words, setWords] = useState<string[]>(EMPTY_WORDS);
  const [result, setResult] = useState<State>({ state: "idle" });
  const [which, setWhich] = useState<Which>("release_a");
  const wordRefs = useRef<(HTMLInputElement | null)[]>([]);

  const opening = result.state === "opening";
  const complete = number.trim().length > 0 && words.every((w) => w.length > 0);

  /** Typing or pasting "amber falcon river quartz" (or with hyphens) into any box fills the boxes from there on. */
  function setWord(index: number, raw: string) {
    const parts = raw.toLowerCase().replace(/[^a-z\s-]/g, "").split(/[\s-]+/);
    const next = [...words];
    if (parts.length === 1) {
      next[index] = parts[0];
      setWords(next);
      return;
    }
    let at = index;
    for (const part of parts) {
      if (at > 3) break;
      if (part) next[at++] = part;
      else if (at === index) at++; // "amber " moves on to the next box
    }
    setWords(next);
    wordRefs.current[Math.min(at, 3)]?.focus();
  }

  function onWordKey(index: number, event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Backspace" && words[index] === "" && index > 0) {
      event.preventDefault();
      wordRefs.current[index - 1]?.focus();
    }
  }

  async function open(envelopeNumber: string, code: string[]) {
    if (opening || disabled) return;
    setResult({ state: "opening", label: label(envelopeNumber) });
    try {
      const envelope = await unsealEnvelope(envelopeNumber.trim(), code.join(" "));
      setWhich("release_a");
      setResult({ state: "opened", envelope });
      onOpened(envelope.report_text, envelope.release_a_dir);
    } catch (error) {
      const message = (error as Error).message.trim();
      setResult({ state: "error", message: /[.!?]$/.test(message) ? message : `${message}.` });
    }
  }

  function rehearse() {
    setNumber(PRACTICE.number);
    setWords(PRACTICE.words);
    void open(PRACTICE.number, PRACTICE.words);
  }

  function choose(next: Which) {
    if (result.state !== "opened") return;
    setWhich(next);
    onReleaseChange(next === "release_a" ? result.envelope.release_a_dir : result.envelope.envelope_release_dir);
  }

  return (
    <section aria-labelledby="envelope-heading" className="rounded-panel border border-rule bg-sheet">
      <div className="p-5 sm:p-6">
        <div className="flex items-start gap-3">
          <KeyRound aria-hidden="true" size={20} strokeWidth={1.75} className="mt-0.5 shrink-0 text-pen" />
          <div>
            <h2 id="envelope-heading" className={sectionTitle}>
              Open a sealed envelope
            </h2>
            <p className="mt-1 max-w-prose text-[0.9375rem] text-ink-soft">
              At your Q&amp;A the judges give you an envelope number and a four-word code. Opening it fills in the
              report and the data folder above.
            </p>
          </div>
        </div>

        <form
          className="mt-5 flex flex-wrap items-start gap-x-4 gap-y-4"
          aria-describedby={statusId}
          onSubmit={(event) => {
            event.preventDefault();
            if (complete) void open(number, words);
          }}
        >
          <div className="w-28 shrink-0">
            <label htmlFor={numberId} className={fieldLabel}>
              Envelope
            </label>
            <input
              id={numberId}
              value={number}
              onChange={(e) => setNumber(e.target.value.replace(/\s/g, ""))}
              aria-describedby={numberHint}
              placeholder="07"
              autoComplete="off"
              autoCapitalize="off"
              spellCheck={false}
              disabled={opening}
              className={`${fieldInput} mt-1.5 font-mono`}
            />
            <p id={numberHint} className="sr-only">
              The number on the card, for example 07.
            </p>
          </div>

          <fieldset className="w-full min-w-0 sm:w-auto sm:flex-1" aria-describedby={codeHint}>
            <legend className={fieldLabel}>Four-word code</legend>
            <div className="mt-1.5 grid grid-cols-2 gap-2 sm:grid-cols-4">
              {words.map((word, i) => (
                <input
                  key={i}
                  ref={(el) => {
                    wordRefs.current[i] = el;
                  }}
                  value={word}
                  onChange={(e) => setWord(i, e.target.value)}
                  onKeyDown={(e) => onWordKey(i, e)}
                  aria-label={`Word ${i + 1} of 4`}
                  autoComplete="off"
                  autoCapitalize="off"
                  spellCheck={false}
                  disabled={opening}
                  className={`${fieldInput} min-w-0 font-mono`}
                />
              ))}
            </div>
            <p id={codeHint} className="mt-1.5 text-sm text-ink-faint">
              Paste all four words into the first box if you like; spaces or hyphens both work.
            </p>
          </fieldset>

          <div className="flex basis-full flex-wrap items-center gap-x-4 gap-y-2">
            <button
              type="submit"
              disabled={!complete || opening || disabled}
              className={`${buttonSecondary} w-full sm:w-auto`}
            >
              {opening ? (
                <LoaderCircle aria-hidden="true" size={18} strokeWidth={1.75} className="animate-spin motion-reduce:animate-none" />
              ) : (
                <KeyRound aria-hidden="true" size={18} strokeWidth={1.75} />
              )}
              {opening ? "Unsealing…" : "Unseal envelope"}
            </button>
            <button type="button" onClick={rehearse} disabled={opening || disabled} className={buttonQuiet}>
              Rehearse with the practice envelope
            </button>
          </div>
        </form>
      </div>

      <div id={statusId} aria-live="polite">
        {result.state === "opening" && (
          <p className="border-t border-rule px-5 py-4 text-[0.9375rem] text-ink-soft sm:px-6">
            Checking fingerprints and opening envelope <span className="font-mono">{result.label}</span>. This takes
            10 to 20 seconds.
          </p>
        )}
        {result.state === "error" && (
          <p role="alert" className="flex items-start gap-2 border-t border-rule px-5 py-4 font-medium text-contradicted sm:px-6">
            <CircleAlert aria-hidden="true" size={16} strokeWidth={1.75} className="mt-1 shrink-0" />
            <span>{result.message}</span>
          </p>
        )}
        {result.state === "opened" && (
          <Opened envelope={result.envelope} which={which} onChoose={choose} onAudit={onAudit} canAudit={canAudit} />
        )}
      </div>
    </section>
  );
}

function Opened({
  envelope,
  which,
  onChoose,
  onAudit,
  canAudit,
}: {
  envelope: OpenedEnvelope;
  which: Which;
  onChoose: (next: Which) => void;
  onAudit: () => void;
  canAudit: boolean;
}) {
  const name = envelope.envelope === "practice" ? "the practice envelope" : `envelope ${envelope.envelope}`;
  const choices: { id: Which; title: string; detail: string; path: string }[] = [
    {
      id: "release_a",
      title: "Release A (recommended)",
      detail: "The files from fetch.py, which our product brief names as the data to check.",
      path: envelope.release_a_dir,
    },
    {
      id: "envelope",
      title: `The ${envelope.envelope === "practice" ? "practice envelope" : `envelope ${envelope.envelope}`} release`,
      detail: "The new release inside the envelope, with no RNA file. Use it if the judges ask.",
      path: envelope.envelope_release_dir,
    },
  ];
  return (
    <div className="grid gap-5 border-t border-rule px-5 py-5 sm:px-6">
      <div>
        <p className="flex flex-wrap items-baseline gap-x-2 font-semibold text-ink">
          <CircleCheck aria-hidden="true" size={18} strokeWidth={1.75} className="shrink-0 self-center text-supported" />
          Opened {name}
          <span className="num whitespace-nowrap font-mono text-sm font-normal text-ink-faint">
            in {envelope.seconds.toFixed(1)} s
          </span>
        </p>
        <ul aria-label="Checks the organizers' unseal.py passed" className="mt-3 grid gap-x-6 gap-y-1.5 text-sm text-ink-soft sm:grid-cols-2">
          {envelope.checks.map((check) => (
            <li key={check} className="flex items-start gap-2">
              <Check aria-hidden="true" size={16} strokeWidth={1.75} className="mt-0.5 shrink-0 text-supported" />
              <span>{check}</span>
            </li>
          ))}
        </ul>
        <p className="mt-4 text-sm text-ink-soft">
          {envelope.report_name ? (
            <>
              Report loaded: <span className="font-mono text-ink">{envelope.report_name}</span>
            </>
          ) : (
            "No report was loaded."
          )}
        </p>
        {envelope.notes.map((note) => (
          <p key={note} className="mt-1 text-sm text-ink-faint">
            {note}
          </p>
        ))}
      </div>

      <div>
        <fieldset>
          <legend className={fieldLabel}>Check the report against</legend>
          <div className="mt-2 grid gap-2 sm:grid-cols-2">
            {choices.map((c) => (
              <label
                key={c.id}
                className={`flex cursor-pointer items-start gap-3 rounded-control border px-3 py-2.5 transition-colors duration-150 ${
                  which === c.id ? "border-pen bg-pen-tint" : "border-rule hover:border-rule-strong"
                }`}
              >
                <input
                  type="radio"
                  name="envelope-release"
                  checked={which === c.id}
                  onChange={() => onChoose(c.id)}
                  className="mt-1 size-4 shrink-0 accent-pen"
                />
                <span className="min-w-0">
                  <span className="block text-[0.9375rem] font-semibold text-ink">{c.title}</span>
                  <span className="block text-sm text-ink-soft">{c.detail}</span>
                  <span className="mt-0.5 block break-all font-mono text-xs text-ink-faint">{c.path}</span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>
        <button type="button" onClick={onAudit} disabled={!canAudit} className={`${buttonQuiet} mt-2 -ml-3`}>
          Run the audit now
        </button>
      </div>
    </div>
  );
}
