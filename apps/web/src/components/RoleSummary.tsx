"use client";

import { useAudit } from "@/lib/audit-context";
import {
  countText,
  DECISION_NEXT_STEP,
  finalVerdict,
  formatCount,
  plural,
  SOLIDITY_LABEL,
  unreviewedIds,
  VERDICT_LABEL,
  VERDICTS,
} from "@/lib/review";
import { ROLE_SECTIONS, useRoles } from "@/lib/roles";
import type { AuditResult, ClaimResult, DecisionSuggestion, Role } from "@/lib/types";

const GLOSSARY: { term: string; meaning: string }[] = [
  { term: "Supported", meaning: "We recounted it from the data and got the number the report states." },
  { term: "Contradicted", meaning: "The data gives a different number; the corrected value is shown." },
  { term: "Insufficient evidence", meaning: "This data has no field that can test the sentence, so we do not guess." },
  { term: "Robust", meaning: "The answer stays the same under every reasonable way of counting (8 tried)." },
  { term: "Fragile", meaning: "The answer changes with how you count, e.g. which subtype label is used." },
];

const SAMPLE_PREVIEW: Record<Role["detail"], number> = { summary: 3, standard: 5, full: 20 };

function mainRisk(audit: AuditResult): string {
  const contradicted = audit.claims.find((c) => finalVerdict(c) === "contradicted");
  if (contradicted) {
    const shows = contradicted.correct_value ? `; the data shows ${contradicted.correct_value}` : "";
    return `${contradicted.claim.id} is contradicted${shows}`;
  }
  const open = audit.claims.find((c) => finalVerdict(c) === "insufficient_evidence");
  if (open) return `${open.claim.id} cannot be answered by this data`;
  const fragile = audit.claims.find((c) => c.solidity === "holds_under_some_variants");
  if (fragile) return `${fragile.claim.id} depends on how it is counted`;
  return "no problems found in the checked claims";
}

function Counts({ audit }: { audit: AuditResult }) {
  return (
    <ul className="flex flex-wrap gap-3">
      {VERDICTS.map((v) => (
        <li key={v} className="rounded-md border border-slate-300 bg-white px-3 py-1">
          {VERDICT_LABEL[v]}: <strong>{audit.claims.filter((c) => finalVerdict(c) === v).length}</strong> of{" "}
          {audit.claims.length}
        </li>
      ))}
    </ul>
  );
}

function corrected(result: ClaimResult) {
  if (!result.ladder.length) return result.claim.text;
  return result.ladder
    .filter((s) => !s.struck)
    .map((s, i) => (s.inserted ? <strong key={i}>{s.text}</strong> : <span key={i}>{s.text}</span>));
}

function Section({ id, audit, suggestion, role }: {
  id: string;
  audit: AuditResult;
  suggestion: DecisionSuggestion | null;
  role: Role;
}) {
  const claims = audit.claims;
  switch (id) {
    case "decision":
      return suggestion ? (
        <p>
          Suggested decision: <strong>{suggestion.decision}</strong>. {suggestion.rule}.
        </p>
      ) : (
        <p>Working out the suggested decision…</p>
      );
    case "counts":
      return <Counts audit={audit} />;
    case "sign_off":
      return suggestion ? <p>{suggestion.sign_off.join(" and ")} must sign off.</p> : null;
    case "claims":
      return (
        <ul className="list-disc space-y-1 pl-5">
          {claims.map((c) => (
            <li key={c.claim.id}>
              <strong>{c.claim.id}</strong> {VERDICT_LABEL[finalVerdict(c)]}
              {c.review?.decision === "override" && ` (tool said ${VERDICT_LABEL[c.verdict]})`}: {c.claim.text}
            </li>
          ))}
        </ul>
      );
    case "review_queue": {
      const left = unreviewedIds(claims).length;
      return (
        <p>
          {claims.length - left} of {claims.length} claims reviewed
          {left ? `; ${plural(left, "claim still needs", "claims still need")} a review.` : "."}
        </p>
      );
    }
    case "decision_record":
      return <p>The Decision Record downloads with audit.json after export, below.</p>;
    case "corrected_wording":
      return (
        <ul className="list-disc space-y-1 pl-5">
          {claims.map((c) => (
            <li key={c.claim.id}>
              <strong>{c.claim.id}</strong> {corrected(c)}
            </li>
          ))}
        </ul>
      );
    case "robustness":
      return (
        <ul className="list-disc space-y-1 pl-5">
          {claims.map((c) => (
            <li key={c.claim.id}>
              <strong>{c.claim.id}</strong> {SOLIDITY_LABEL[c.solidity]}
              {c.flips_on.length > 0 && ` (changes on ${c.flips_on.join(", ")})`}
              {role.detail === "full" && c.variants.length > 0 &&
                `; ${c.variants.filter((v) => v.verdict === c.verdict).length} of ${c.variants.length} ways of counting agree`}
            </li>
          ))}
        </ul>
      );
    case "skeptic":
      return (
        <ul className="list-disc space-y-1 pl-5">
          {claims.map((c) => (
            <li key={c.claim.id}>
              <strong>{c.claim.id}</strong>{" "}
              {c.skeptic
                ? `shuffled-label p = ${c.skeptic.shuffle_p ?? "unknown"}; leaving out one of ${c.skeptic.n_sites} sites ` +
                  (c.skeptic.site_flips.length ? `flips it (${c.skeptic.site_flips.join(", ")})` : "never flips it")
                : "skeptic tests do not apply"}
            </li>
          ))}
        </ul>
      );
    case "sample_ids":
      return (
        <ul className="list-disc space-y-1 pl-5">
          {claims.map((c) => {
            const ids = c.fact?.sample_ids ?? [];
            const shown = ids.slice(0, SAMPLE_PREVIEW[role.detail]);
            return (
              <li key={c.claim.id}>
                <strong>{c.claim.id}</strong> {countText(c.fact) ?? "no samples"}
                {shown.length > 0 && (
                  <>
                    : <code className="break-all">{shown.join(", ")}</code>
                    {ids.length > shown.length && ` and ${formatCount(ids.length - shown.length)} more`}
                  </>
                )}
              </li>
            );
          })}
        </ul>
      );
    case "files":
      return (
        <ul className="list-disc space-y-1 pl-5">
          {audit.release.files.map((f) => (
            <li key={f.file}>
              {f.file}: <code className="break-all">{f.sha256 || "checksum missing"}</code>
            </li>
          ))}
        </ul>
      );
    case "code":
      return (
        <div className="space-y-2">
          {claims
            .filter((c) => c.fact?.code)
            .map((c) => (
              <details key={c.claim.id}>
                <summary className="cursor-pointer">Code for {c.claim.id}</summary>
                <pre className="mt-1 overflow-x-auto rounded-md bg-slate-900 p-3 text-xs text-slate-100">
                  <code>{c.fact?.code}</code>
                </pre>
              </details>
            ))}
        </div>
      );
    default:
      return null;
  }
}

/** Decision page header: the same facts, worded for the chosen role. */
export default function RoleSummary({ audit, suggestion }: {
  audit: AuditResult;
  suggestion: DecisionSuggestion | null;
}) {
  const { role: roleName } = useAudit();
  const { roles } = useRoles();
  const role: Role = roles?.find((r) => r.name === roleName) ?? {
    name: roleName,
    sections: ["decision", "counts", "sign_off"],
    detail: "standard",
    explain_terms: false,
  };

  return (
    <section aria-labelledby="role-summary-title" className="rounded-xl border border-emerald-900/15 bg-white p-6">
      <h2 id="role-summary-title" className="text-sm font-semibold uppercase tracking-widest text-emerald-800">
        For the {role.name}
      </h2>
      {role.detail === "summary" && suggestion && (
        <p className="mt-3 text-lg">
          The tool suggests <strong>{suggestion.decision}</strong>; the main risk is {mainRisk(audit)}; next step:{" "}
          {DECISION_NEXT_STEP[suggestion.decision]}.
        </p>
      )}
      <div className="mt-4 space-y-4">
        {role.sections.map((id) => (
          <div key={id}>
            <h3 className="mb-1 font-semibold">{ROLE_SECTIONS.find((s) => s.id === id)?.label ?? id}</h3>
            <Section id={id} audit={audit} suggestion={suggestion} role={role} />
          </div>
        ))}
      </div>
      {role.explain_terms && (
        <details className="mt-4">
          <summary className="cursor-pointer text-sm text-emerald-900 underline underline-offset-4">
            What the words mean
          </summary>
          <dl className="mt-2 grid gap-x-4 gap-y-1 text-sm sm:grid-cols-[max-content_1fr]">
            {GLOSSARY.map((g) => (
              <div key={g.term} className="contents">
                <dt className="font-medium">{g.term}</dt>
                <dd className="text-slate-700">{g.meaning}</dd>
              </div>
            ))}
          </dl>
        </details>
      )}
    </section>
  );
}
