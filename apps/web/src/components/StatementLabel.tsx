export type StatementKind = "Computed" | "Reported" | "Interpretation";

const HINT: Record<StatementKind, string> = {
  Computed: "Calculated from the data by code",
  Reported: "Taken from the report as written",
  Interpretation: "Our suggested wording, built from fixed rules",
};

const STYLE: Record<StatementKind, string> = {
  Computed: "border-emerald-900 bg-emerald-900 text-white",
  Reported: "border-slate-300 bg-slate-100 text-slate-700",
  Interpretation: "border-slate-400 bg-white text-slate-700",
};

/** Every statement says where it comes from. */
export default function StatementLabel({ kind }: { kind: StatementKind }) {
  return (
    <span
      title={HINT[kind]}
      className={`inline-block rounded-sm border px-1.5 py-px text-[0.65rem] font-semibold tracking-wider uppercase ${STYLE[kind]}`}
    >
      {kind}
    </span>
  );
}
