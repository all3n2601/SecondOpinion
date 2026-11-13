"use client";

import { ChevronRight } from "lucide-react";
import VerdictBadge from "@/components/VerdictBadge";
import { useAudit } from "@/lib/audit-context";
import { GLOSSARY as GLOSSARY_TERMS } from "@/lib/glossary";
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
import { focusRing, sectionTitle } from "@/lib/ui";
import { ROLE_SECTIONS, useRoles } from "@/lib/roles";
import type { AuditResult, ClaimResult, DecisionSuggestion, Role } from "@/lib/types";

const GLOSSARY: { term: string; meaning: string }[] = [
  { term: "Supported", meaning: "We recounted it from the data and got the number the report states." },
  { term: "Contradicted", meaning: "The data gives a different number; the corrected value is shown." },
  { term: "Insufficient evidence", meaning: "This data has no field that can test the sentence, so we do not guess." },
  GLOSSARY_TERMS.robust,
  GLOSSARY_TERMS.fragile,
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
    <ul className="flex flex-wrap gap-x-5 gap-y-2">
      {VERDICTS.map((v) => (
        <li key={v} className="flex items-center gap-2">
          <VerdictBadge verdict={v} size="sm" />
          <span className="num font-mono text-sm">
            {audit.claims.filter((c) => finalVerdict(c) === v).length} of {audit.claims.length}
          </span>
        </li>
      ))}
    </ul>
  );
}

const LIST = "list-disc space-y-2 pl-5 marker:text-ink-faint";
const ID = "num font-mono text-sm font-semibold";

function corrected(result: ClaimResult) {
  if (!result.ladder.length) return result.claim.text;
  return result.ladder
    .filter((s) => !s.struck)
    .map((s, i) => (s.inserted ? <ins key={i}>{s.text}</ins> : <span key={i}>{s.text}</span>));
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
        <ul className={LIST}>
          {claims.map((c) => (
            <li key={c.claim.id}>
              <strong className={ID}>{c.claim.id}</strong> {VERDICT_LABEL[finalVerdict(c)]}
              {c.review?.decision === "override" && ` (tool said ${VERDICT_LABEL[c.verdict]})`}:{" "}
              <span className="font-serif">{c.claim.text}</span>
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
        <ul className={LIST}>
          {claims.map((c) => (
            <li key={c.claim.id}>
              <strong className={ID}>{c.claim.id}</strong> {corrected(c)}
            </li>
          ))}
        </ul>
      );
    case "robustness":
      return (
        <ul className={LIST}>
          {claims.map((c) => (
            <li key={c.claim.id}>
              <strong className={ID}>{c.claim.id}</strong> {SOLIDITY_LABEL[c.solidity]}
              {c.flips_on.length > 0 && ` (changes on ${c.flips_on.join(", ")})`}
              {role.detail === "full" && c.variants.length > 0 &&
                `; ${c.variants.filter((v) => v.verdict === c.verdict).length} of ${c.variants.length} ways of counting agree`}
            </li>
          ))}
        </ul>
      );
    case "skeptic":
      return (
        <ul className={LIST}>
          {claims.map((c) => (
            <li key={c.claim.id}>
              <strong className={ID}>{c.claim.id}</strong>{" "}
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
        <ul className={LIST}>
          {claims.map((c) => {
            const ids = c.fact?.sample_ids ?? [];
            const shown = ids.slice(0, SAMPLE_PREVIEW[role.detail]);
            return (
              <li key={c.claim.id}>
                <strong className={ID}>{c.claim.id}</strong> {countText(c.fact) ?? "no samples"}
                {shown.length > 0 && (
                  <>
                    : <code className="num break-all font-mono text-sm">{shown.join(", ")}</code>
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
        <ul className={LIST}>
          {audit.release.files.map((f) => (
            <li key={f.file}>
              {f.file}: <code className="num break-all font-mono text-sm">{f.sha256 || "checksum missing"}</code>
            </li>
          ))}
        </ul>
      );
    case "code":
      return (
        <div className="space-y-1">
          {claims
            .filter((c) => c.fact?.code)
            .map((c) => (
              <details key={c.claim.id}>
                <summary className={`min-h-11 cursor-pointer rounded-control py-2 text-sm font-medium text-pen underline-offset-4 hover:underline ${focusRing}`}>
                  Code for {c.claim.id}
                </summary>
                <pre
                  tabIndex={0}
                  aria-label={`Code for ${c.claim.id}`}
                  className={`mt-1 overflow-x-auto rounded-control bg-ink p-3 font-mono text-xs leading-5 text-paper ${focusRing}`}
                >
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
    <section aria-labelledby="role-summary-title">
      <h2 id="role-summary-title" className={sectionTitle}>
        For the {role.name}
      </h2>
      {role.detail === "summary" && suggestion && (
        <p className="mt-3 max-w-prose text-lg">
          The tool suggests <strong>{suggestion.decision}</strong>; the main risk is {mainRisk(audit)}; next step:{" "}
          {DECISION_NEXT_STEP[suggestion.decision]}.
        </p>
      )}
      <div className="mt-3 border-t border-rule">
        {role.sections.map((id) => (
          <div
            key={id}
            className="grid gap-1 border-b border-rule py-4 sm:grid-cols-[11rem_1fr] sm:gap-x-6"
          >
            <h3 className="text-sm font-semibold text-ink">
              {ROLE_SECTIONS.find((s) => s.id === id)?.label ?? id}
            </h3>
            <div className="min-w-0 text-ink">
              <Section id={id} audit={audit} suggestion={suggestion} role={role} />
            </div>
          </div>
        ))}
      </div>
      {role.explain_terms && (
        <details className="group mt-3">
          <summary
            className={`inline-flex min-h-11 cursor-pointer list-none items-center gap-1.5 rounded-control pr-2 text-sm font-medium text-pen underline-offset-4 hover:underline [&::-webkit-details-marker]:hidden ${focusRing}`}
          >
            <ChevronRight
              aria-hidden="true"
              className="size-4 transition-transform duration-150 group-open:rotate-90"
            />
            What the words mean
          </summary>
          <dl className="mt-2 grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[max-content_1fr]">
            {GLOSSARY.map((g) => (
              <div key={g.term} className="contents">
                <dt className="font-semibold text-ink">{g.term}</dt>
                <dd className="mb-2 text-ink-soft sm:mb-0">{g.meaning}</dd>
              </div>
            ))}
          </dl>
        </details>
      )}
    </section>
  );
}
