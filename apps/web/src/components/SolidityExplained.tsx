import { solidityText } from "@/lib/claim-format";
import type { ClaimResult } from "@/lib/types";
import GlossaryTerm from "./GlossaryTerm";
import SolidityTag from "./SolidityTag";

/** The solidity tag, made a glossary term: focus, hover or tap explains "Robust" / "Fragile" for this claim. */
export default function SolidityExplained({ result }: { result: ClaimResult }) {
  if (result.solidity === "not_applicable") return <SolidityTag result={result} />;
  return (
    <GlossaryTerm
      term={result.solidity === "holds_under_every_variant" ? "robust" : "fragile"}
      detail={solidityText(result).long}
      bare
    >
      <SolidityTag result={result} />
    </GlossaryTerm>
  );
}
