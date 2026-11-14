"""The query-plan schema: everything the AI is allowed to ask for, and nothing else.

A plan names whitelisted operations over whitelisted fields. `executor.py` turns a plan into a Fact by
running pandas on the release; the AI never supplies data. Anything outside this schema fails
validation and the claim falls back to `insufficient_evidence`.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

# Fields a filter may use, with the values each accepts (the executor maps them onto clinical columns).
#   sample_type   "primary" | "normal_tissue" | "metastatic"          (barcode code 01 / 11 / 06)
#   sex           "female" | "male"
#   subtype_rna   Luminal A | Luminal B | HER2-enriched | Basal-like | Normal-like   (PAM50Call_RNAseq)
#   subtype_2012  same names                                                          (PAM50_mRNA_nature2012)
#   er_status / her2_status   "positive" | "negative"   (clinical IHC status columns)
#   has_layer     survival | mutation | copy_number | protein | rna  (the sample appears in that file)
#   age_years     number (age at initial diagnosis)
#   diagnosis_year        number (year of initial diagnosis)
#   positive_lymph_nodes  number (lymph nodes positive by H&E)
#   attribute     any attribute the rules read (checks/attributes.py), named in `attribute`, with its value:
#                 pr_status / hr_status "positive" | "negative"; triple_negative "triple-negative";
#                 stage "Stage I" ... "Stage IV" (or "Stage IIA"); histology "ductal" | "lobular" | "mucinous" | ...;
#                 menopause "pre" | "peri" | "post"; vital_status "deceased" | "living"; dss_status "deceased";
#                 pfi_status "event"; mutation / amplification / deletion / gain / loss: a gene symbol ("TP53")
FilterField = Literal[
    "sample_type", "sex", "subtype_rna", "subtype_2012", "er_status", "her2_status", "has_layer", "age_years",
    "diagnosis_year", "positive_lymph_nodes", "attribute",
]
NumericField = Literal["age_years", "diagnosis_year", "positive_lymph_nodes"]
AttributeName = Literal[
    "er_status", "pr_status", "her2_status", "hr_status", "triple_negative", "stage", "histology", "menopause",
    "vital_status", "dss_status", "pfi_status", "mutation", "amplification", "deletion", "gain", "loss",
]
FilterOp = Literal["eq", "in", "gt", "gte", "lt", "lte", "is_known", "is_unknown"]  # is_unknown: no recorded value


class Filter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: FilterField
    op: FilterOp = "eq"
    value: str | float | list[str] | None = None  # None only for op "is_known"
    attribute: AttributeName | None = None  # only with field "attribute"


class _Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    where: list[Filter] = Field(default_factory=list, description="Rows kept before the operation (AND).")


class CountPlan(_Plan):
    """How many samples (or distinct patients) match."""

    op: Literal["count"] = "count"
    of: Literal["samples", "patients"] = "samples"


class SharePlan(_Plan):
    """Percent of the rows kept by `where` (the denominator) that also match `numerator` (AND)."""

    op: Literal["share"] = "share"
    numerator: list[Filter]


class CompareMeansPlan(_Plan):
    """Mean of a protein measurement in group A minus group B (rows kept by `where`, primary tumors by default)."""

    op: Literal["compare_means"] = "compare_means"
    measure: str = Field(description="Protein name as in the release, e.g. ERALPHA or HER2 (validated against the file).")
    group_field: Literal["er_status", "her2_status", "sex"]
    group_a: str
    group_b: str


class SummaryStatPlan(_Plan):
    """A summary statistic of a numeric field over the rows kept by `where`."""

    op: Literal["summary_stat"] = "summary_stat"
    field: NumericField
    stat: Literal["median", "mean", "min", "max", "range"] = Field(
        description="range: the smallest and largest value, stated as value and high (\"1988 to 2013\").")


class RankPlan(_Plan):
    """Where one category ranks by size among the rows kept by `where` that have a call (1 = most common)."""

    op: Literal["rank"] = "rank"
    category_field: Literal["subtype_rna", "subtype_2012", "mutated_gene"] = Field(
        description="mutated_gene: rank a gene among all genes by how many primary tumors carry a mutation in it.")
    category: str


class OrderPlan(_Plan):
    """Whether category A has more, or fewer, rows than category B among the rows kept by `where`."""

    op: Literal["order"] = "order"
    category_field: Literal["subtype_rna", "subtype_2012"]
    category_a: str
    category_b: str


class CompareGroupsPlan(_Plan):
    """Group A against group B (both inside `where`): their count, their share with `numerator`, or a statistic of
    a numeric field. `compare` gives A minus B (difference) or A divided by B (ratio, for "eight times as common")."""

    op: Literal["compare_groups"] = "compare_groups"
    measure: Literal["count", "share", "stat"]
    compare: Literal["difference", "ratio"] = "difference"
    group_a: list[Filter] = Field(min_length=1)
    group_b: list[Filter] = Field(min_length=1)
    numerator: list[Filter] = Field(default_factory=list, description="For measure share.")
    field: NumericField | None = Field(default=None, description="For measure stat.")
    stat: Literal["median", "mean"] | None = Field(default=None, description="For measure stat.")


class RankGroupsPlan(_Plan):
    """Where one subtype ranks among all subtypes by a share with `numerator`, or by a statistic of a numeric
    field; order highest (1 = highest, "most common in", "oldest") or lowest (1 = lowest, "rarest in", "youngest")."""

    op: Literal["rank_groups"] = "rank_groups"
    measure: Literal["share", "stat"]
    order: Literal["highest", "lowest"] = "highest"
    category_field: Literal["subtype_rna", "subtype_2012"]
    category: str
    numerator: list[Filter] = Field(default_factory=list, description="For measure share.")
    field: NumericField | None = Field(default=None, description="For measure stat.")
    stat: Literal["median", "mean"] | None = Field(default=None, description="For measure stat.")


Plan = Annotated[
    CountPlan | SharePlan | CompareMeansPlan | SummaryStatPlan | RankPlan | OrderPlan | CompareGroupsPlan | RankGroupsPlan,
    Field(discriminator="op"),
]


class Stated(BaseModel):
    """What the sentence asserts, quoted from it. `span` must appear verbatim in the sentence."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["percent", "count", "number", "rank", "relation", "direction"]
    span: str = Field(description="The words of the sentence that state it, copied exactly (e.g. 'roughly one in six').")
    value: float | None = Field(default=None, description="Numeric value stated; percent as 16.7 for 16.7%.")
    high: float | None = Field(default=None, description="Upper end for a range.")
    total: float | None = Field(default=None, description="Stated denominator, e.g. 1101 in '535 of 1,101'.")
    approximate: bool = False
    relation: Literal["more", "less"] | None = Field(default=None, description="For kind 'relation' or 'direction'.")


class QueryPlan(BaseModel):
    """The AI's whole answer for one sentence."""

    model_config = ConfigDict(extra="forbid")

    answerable: bool = Field(description="False when the release cannot answer the sentence (treatment, cause, missing data).")
    needed_data: str | None = Field(default=None, description="When not answerable: what data would be needed, in plain words.")
    plan: Plan | None = None
    stated: Stated | None = None
    rationale: str = Field(default="", description="One sentence on how the plan tests the claim. Shown to the reviewer.")
