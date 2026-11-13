export type StatementKind = "Computed" | "Reported" | "Interpretation";

const HINT: Record<StatementKind, string> = {
  Computed: "Calculated from the data by code",
  Reported: "Taken from the report as written",
  Interpretation: "Our suggested wording, built from fixed rules",
};

// Reported text is set in the report's serif elsewhere; the label itself stays quiet.
const STYLE: Record<StatementKind, string> = {
  Computed: "border-pen bg-pen-tint text-pen",
  Reported: "border-rule-strong bg-sheet text-ink-soft",
  Interpretation: "border-dashed border-rule-strong bg-wash text-ink-soft",
};

/** Every statement says where it comes from. */
export default function StatementLabel({ kind }: { kind: StatementKind }) {
  return (
    <span
      title={HINT[kind]}
      className={`inline-block rounded-stamp border px-1.5 py-px text-xs font-medium ${STYLE[kind]}`}
    >
      {kind}
    </span>
  );
}
