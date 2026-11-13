import { Sparkles } from "lucide-react";

const BASE =
  "inline-flex items-center gap-1.5 whitespace-nowrap rounded-stamp border border-rule-strong bg-sheet text-ink-soft";

/** On a claim row: the optional AI helper found this sentence; the rules had skipped it. */
export function AiFoundStamp() {
  return (
    <span className={`${BASE} px-2 py-0.5 text-sm font-medium`}>
      <Sparkles aria-hidden="true" className="size-4 shrink-0" />
      Found by the AI helper
    </span>
  );
}

/** On a result: the optional AI helper proposed the check plan; our code ran it and set the verdict. */
export function AiAssistedStamp() {
  return (
    <span
      title="The AI helper proposed how to test this. Our code ran the plan on the release and set the verdict."
      className={`${BASE} px-2 py-0.5 text-sm font-medium`}
    >
      <Sparkles aria-hidden="true" className="size-4 shrink-0" />
      AI-assisted check
    </span>
  );
}
