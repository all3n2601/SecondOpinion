export type StatementKind = "Computed" | "Reported" | "Interpretation";

const HINT: Record<StatementKind, string> = {
  Computed: "Calculated from the data by code",
  Reported: "Taken from the report as written",
  Interpretation: "Our suggested wording, built from fixed rules",
};

const STYLE: Record<StatementKind, string> = {
  Computed: "bg-emerald-900 text-white",
  Reported: "bg-slate-200 text-slate-900",
  Interpretation: "border border-slate-500 text-slate-800",
};

/** Every statement says where it comes from. */
export default function StatementLabel({ kind }: { kind: StatementKind }) {
  return (
    <span
      title={HINT[kind]}
      className={`inline-block rounded px-1.5 py-0.5 text-xs font-semibold tracking-wide uppercase ${STYLE[kind]}`}
    >
      {kind}
    </span>
  );
}
