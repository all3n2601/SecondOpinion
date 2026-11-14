"""Sample attributes a claim can be about, read the same way by every check.

An attribute turns each sample of a population into a label, or NaN when the release does not record
it. Shares use the samples with a known label as the denominator, the same rule the organizers'
reference analyses use ("ER-positive" counts Positive among Positive + Negative).

Which column is read depends on the variant, so the robustness check recounts every claim under a
second, reasonable source of the same fact:

  attribute       primary source (what the organizers' reference analyses use)   second source
  er_status       breast_carcinoma_estrogen_receptor_status (clinical IHC)        ER_Status_nature2012
  pr_status       breast_carcinoma_progesterone_receptor_status                   PR_Status_nature2012
  her2_status     lab_proc_her2_neu_immunohistochemistry_receptor_status          HER2_Final_Status_nature2012
  stage           pathologic_stage                                                AJCC_Stage_nature2012
  vital_status    survival.tsv OS (1 = died)                                      clinical vital_status
  subtype         PAM50Call_RNAseq                                                PAM50_mRNA_nature2012

The second source is used when variant.subtype_source == "study_2012_label".
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd

from second_opinion.checks.base import CannotCheck
from second_opinion.checks.population import subtype_column
from second_opinion.release import RELEASE_FILES, Release
from second_opinion.variants import PRIMARY_VARIANT, Variant, normalise_subtype

CLINICAL = RELEASE_FILES["clinical"]
SECOND_SOURCE = "study_2012_label"

STATUS_COLUMNS = {  # attribute -> (primary column, second column, receptor name)
    "er_status": ("breast_carcinoma_estrogen_receptor_status", "ER_Status_nature2012", "ER"),
    "pr_status": ("breast_carcinoma_progesterone_receptor_status", "PR_Status_nature2012", "PR"),
    "her2_status": ("lab_proc_her2_neu_immunohistochemistry_receptor_status", "HER2_Final_Status_nature2012", "HER2"),
}
STAGE_COLUMNS = ("pathologic_stage", "AJCC_Stage_nature2012")
HISTOLOGY_COLUMN = "histological_type"
MENOPAUSE_COLUMN = "menopause_status"
AGE_COLUMNS = ("age_at_initial_pathologic_diagnosis", "Age_at_Initial_Pathologic_Diagnosis_nature2012")
YEAR_COLUMN = "year_of_initial_pathologic_diagnosis"
NODES_COLUMN = "number_of_lymphnodes_positive_by_he"
GENE_ALIASES = {"HER2": "ERBB2", "HER-2": "ERBB2", "ER": "ESR1"}

HISTOLOGY_WORDS = {  # label -> words in histological_type
    "ductal": "ductal", "lobular": "lobular", "mucinous": "mucinous", "metaplastic": "metaplastic",
    "medullary": "medullary", "mixed": "mixed", "papillary": "papillary",
}
_STAGE = re.compile(r"stage\s+(IV|III|II|I)([ABC]?)\b", re.IGNORECASE)

# Plain words for each attribute value, used in labels ("ER-positive primary tumors").
ATTRIBUTE_NOUNS = {
    "er_status": "ER status", "pr_status": "PR status", "her2_status": "HER2 status",
    "hr_status": "hormone-receptor status", "triple_negative": "triple-negative status",
    "stage": "pathologic stage", "histology": "histological type", "sex": "sex",
    "menopause": "menopause status", "subtype": "PAM50 subtype", "vital_status": "vital status",
    "mutation": "mutation call", "amplification": "copy-number call", "deletion": "copy-number call",
    "dss_status": "disease-specific survival status", "pfi_status": "progression-free interval status",
    "slide_kind": "slide record", "age_group": "age at diagnosis", "diagnosis_year": "year of diagnosis", "gain": "copy-number call", "loss": "copy-number call",
}


@dataclass
class AttributeValues:
    values: pd.Series  # index = sampleID; a label, or NaN when unknown
    hit: str  # the label the claim is about ("positive", "mutated", "Stage II", ...)
    files: list[str]
    code: str  # pandas lines that build `vals` from `pop` (indexed by sampleID)
    source: str  # the column or file read, shown to the reviewer


def describe(attribute: str, category: str | None) -> str:
    """Plain words for a category: "ER-positive", "TP53-mutated", "Stage II", "deceased"."""
    category = category or ""
    if attribute in STATUS_COLUMNS:
        return f"{STATUS_COLUMNS[attribute][2]}-{category}"
    if attribute == "hr_status":
        return f"hormone-receptor-{category}"
    if attribute == "mutation":
        return f"{category}-mutated"
    if attribute == "amplification":
        return f"{category}-amplified"
    if attribute == "deletion":
        return f"{category}-deleted"
    if attribute == "histology":
        return f"{category} carcinoma"
    if attribute == "menopause":
        return f"{category}menopausal"
    if attribute == "dss_status":
        return "disease-specific death"
    if attribute == "pfi_status":
        return "progression or recurrence event"
    if attribute == "slide_kind":
        return f"with a {category} slide"
    if attribute == "layer":
        return f"{(category or '').replace('_', '-')}-profiled"
    if attribute == "gain":
        return f"{category}-gained"
    if attribute == "loss":
        return f"{category}-lost"
    if attribute == "diagnosis_year":
        m = re.fullmatch(r"(gt|gte|lt|lte|eq)(\d{4})", category)
        if m:
            return "diagnosed " + {"gt": "after", "gte": "in or after", "lt": "before", "lte": "in or before", "eq": "in"}[m.group(1)] + f" {m.group(2)},"
    if attribute == "age_group":
        m = re.fullmatch(r"(gt|gte|lt|lte)(\d+)", category)
        if m:
            return {"gt": "over", "gte": "at least", "lt": "under", "lte": "at most"}[m.group(1)] + f" {m.group(2)} at diagnosis,"
    return category


def gene_symbol(name: str) -> str:
    return GENE_ALIASES.get(name.upper(), name.upper())


def _column(release: Release, primary: str, second: str | None, variant: Variant) -> str:
    col = second if (variant.subtype_source == SECOND_SOURCE and second) else primary
    if col not in release.clinical.columns:
        raise CannotCheck(f"this release's clinical file has no {col} column")
    return col


def _status(series: pd.Series) -> pd.Series:
    words = series.astype("string").str.strip().str.lower()
    return words.where(words.isin(["positive", "negative"]))


def _stage(series: pd.Series, detail: bool) -> pd.Series:
    def one(raw) -> str | float:
        m = _STAGE.search(str(raw)) if isinstance(raw, str) else None
        if m is None:
            return float("nan")
        return f"Stage {m.group(1).upper()}{m.group(2).upper() if detail else ''}"
    return series.map(one)


def _histology(series: pd.Series) -> pd.Series:
    def one(raw) -> str | float:
        if not isinstance(raw, str) or not raw.strip():
            return float("nan")
        low = raw.lower()
        for label, word in HISTOLOGY_WORDS.items():
            if word in low:
                return label
        return "other"
    return series.map(one)


def _menopause(series: pd.Series) -> pd.Series:
    def one(raw) -> str | float:
        if not isinstance(raw, str):
            return float("nan")
        low = raw.strip().lower()
        for label in ("pre", "peri", "post"):
            if low.startswith(label):
                return label
        return float("nan")
    return series.map(one)


def clinical_frame(pop: pd.DataFrame) -> pd.DataFrame:
    """Population rows indexed by sampleID (first row wins on a duplicate)."""
    frame = pop[pop["sampleID"].notna()].copy()
    frame["sampleID"] = frame["sampleID"].astype(str)
    frame = frame[~frame["sampleID"].duplicated()]
    return frame.set_index("sampleID", drop=False)


def attribute_mask(release: Release, pop: pd.DataFrame, attribute: str, categories: list[str]) -> pd.Series:
    """True for each row of `pop` whose sample has one of `categories` (an AI plan's filter); aligned with pop."""
    frame = clinical_frame(pop)
    hit = pd.Series(False, index=frame.index)
    for category in categories:
        av = attribute_values(release, frame, attribute, category, PRIMARY_VARIANT)
        hit |= (av.values == av.hit).astype(bool)
    return pop["sampleID"].astype(str).map(hit).fillna(False).astype(bool)


def attribute_known(release: Release, pop: pd.DataFrame, attribute: str, category: str | None) -> pd.Series:
    """True for each row of `pop` whose sample has any recorded value for `attribute`; aligned with pop."""
    frame = clinical_frame(pop)
    av = attribute_values(release, frame, attribute, category, PRIMARY_VARIANT)
    return pop["sampleID"].astype(str).map(av.values.notna()).fillna(False).astype(bool)


def attribute_values(
    release: Release, pop: pd.DataFrame, attribute: str, category: str | None, variant: Variant
) -> AttributeValues:
    """Label every sample of `pop` for `attribute`; raises CannotCheck when the release lacks it.

    Labels are plain Python objects with None for unknown, so `vals == "x"` is always True or False.
    """
    av = _attribute_values(release, pop, attribute, category, variant)
    vals = av.values.astype(object)
    av.values = vals.where(vals.notna(), None)
    return av


def _attribute_values(
    release: Release, pop: pd.DataFrame, attribute: str, category: str | None, variant: Variant
) -> AttributeValues:
    frame = clinical_frame(pop)
    idx = frame.index

    if attribute in STATUS_COLUMNS and (category or "").lower() in ("equivocal", "indeterminate"):
        primary, second, _ = STATUS_COLUMNS[attribute]
        col = _column(release, primary, second, variant)
        words = frame[col].astype("string").str.strip().str.lower()
        vals = words.where(words.isin(["positive", "negative", "equivocal", "indeterminate"]))
        code = f'vals = pop["{col}"].str.strip().str.lower()  # Positive / Negative / Equivocal / Indeterminate'
        return AttributeValues(vals, category.lower(), [CLINICAL], code, col)

    if attribute == "diagnosis_year":  # "diagnosed in 2010 or later"
        col = _column(release, YEAR_COLUMN, None, variant)
        years = pd.to_numeric(frame[col], errors="coerce")
        op, cut = _age_cut(category or "")
        test = {"gt": years > cut, "gte": years >= cut, "lt": years < cut, "lte": years <= cut, "eq": years == cut}[op]
        vals = pd.Series("in group", index=frame.index, dtype="object").where(test, "not in group").where(years.notna())
        sign = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<=", "eq": "=="}[op]
        code = f'year = pd.to_numeric(pop["{col}"], errors="coerce")\nvals = (year {sign} {cut:g}).where(year.notna())'
        return AttributeValues(vals, "in group", [CLINICAL], code, col)

    if attribute == "age_group":
        ages, col = age_values(release, frame, variant)
        op, cut = _age_cut(category or "")
        test = {"gt": ages > cut, "gte": ages >= cut, "lt": ages < cut, "lte": ages <= cut}[op]
        vals = pd.Series("in group", index=frame.index, dtype="object").where(test, "not in group").where(ages.notna())
        sign = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<="}[op]
        code = f'age = pd.to_numeric(pop["{col}"], errors="coerce")\nvals = (age {sign} {cut:g}).where(age.notna())'
        return AttributeValues(vals, "in group", [CLINICAL], code, col)

    if attribute in STATUS_COLUMNS:
        primary, second, _ = STATUS_COLUMNS[attribute]
        col = _column(release, primary, second, variant)
        vals = _status(frame[col])
        code = f'vals = pop["{col}"].str.strip().str.lower().where(lambda s: s.isin(["positive", "negative"]))'
        return AttributeValues(vals, (category or "positive").lower(), [CLINICAL], code, col)

    if attribute in ("hr_status", "triple_negative"):
        cols = {a: _column(release, STATUS_COLUMNS[a][0], STATUS_COLUMNS[a][1], variant) for a in STATUS_COLUMNS}
        er, pr, her2 = (_status(frame[cols[a]]) for a in ("er_status", "pr_status", "her2_status"))
        if attribute == "hr_status":
            pos = (er == "positive") | (pr == "positive")
            neg = (er == "negative") & (pr == "negative")
            vals = pd.Series(float("nan"), index=idx, dtype="object")
            vals[pos] = "positive"
            vals[neg & ~pos] = "negative"
            code = (f'er, pr = pop["{cols["er_status"]}"], pop["{cols["pr_status"]}"]\n'
                    'vals = pd.Series(None, index=pop.index, dtype=object)\n'
                    'vals[(er == "Positive") | (pr == "Positive")] = "positive"\n'
                    'vals[(er == "Negative") & (pr == "Negative")] = "negative"')
            return AttributeValues(vals, (category or "positive").lower(), [CLINICAL], code, f"{cols['er_status']} + {cols['pr_status']}")
        # Known only when all three results are recorded (Positive or Negative), as "of tumours with all
        # three results" reads; equivocal or missing in any one leaves the sample unknown.
        all_known = er.notna() & pr.notna() & her2.notna()
        tn = (er == "negative") & (pr == "negative") & (her2 == "negative")
        not_tn = all_known & ~tn
        vals = pd.Series(float("nan"), index=idx, dtype="object")
        vals[not_tn] = "not triple-negative"
        vals[tn] = "triple-negative"
        code = (f'er, pr, her2 = (pop[c] for c in ("{cols["er_status"]}", "{cols["pr_status"]}", "{cols["her2_status"]}"))\n'
                'vals = pd.Series(None, index=pop.index, dtype=object)\n'
                'known = lambda s: s.isin(["Positive", "Negative"])\n'
                'vals[known(er) & known(pr) & known(her2)] = "not triple-negative"\n'
                'vals[(er == "Negative") & (pr == "Negative") & (her2 == "Negative")] = "triple-negative"')
        return AttributeValues(vals, "triple-negative", [CLINICAL], code, "ER, PR and HER2 status columns")

    if attribute == "stage" and category and " or " in category:  # "Stage III or IV": every stage it names
        stages = re.findall(r"IV|III|II|I", category)
        av = _attribute_values(release, pop, "stage", f"Stage {stages[0]}", variant)
        union = {f"Stage {s}": category for s in stages}
        av.values = av.values.replace(union)
        av.code += f"\nvals = vals.map(lambda s: \"{category}\" if s in {sorted(stages)!r} else s)  # one group"
        av.hit = category
        return av
    if attribute == "stage":
        col = _column(release, STAGE_COLUMNS[0], STAGE_COLUMNS[1], variant)
        detail = bool(category and category[-1:].upper() in ("A", "B", "C"))
        vals = _stage(frame[col], detail)
        hit = _stage(pd.Series([category or ""]), detail).iloc[0]
        if not isinstance(hit, str):
            raise CannotCheck(f"'{category}' is not a stage this release records")
        code = (f'vals = pop["{col}"].str.extract(r"Stage (IV|III|II|I){"([ABC]?)" if detail else ""}")'
                + ('.agg("".join, axis=1)' if detail else "[0]") + '  # "Stage IIA" -> ' + ('"IIA"' if detail else '"II"'))
        return AttributeValues(vals, hit, [CLINICAL], code, col)

    if attribute == "histology":
        col = _column(release, HISTOLOGY_COLUMN, None, variant)
        code = f'vals = pop["{col}"].str.lower()  # "{category}" if the type names it'
        return AttributeValues(_histology(frame[col]), (category or "").lower(), [CLINICAL], code, col)

    if attribute == "menopause":
        col = _column(release, MENOPAUSE_COLUMN, None, variant)
        code = f'vals = pop["{col}"].str.lower().str.extract(r"^(pre|peri|post)")[0]'
        return AttributeValues(_menopause(frame[col]), (category or "").lower(), [CLINICAL], code, col)

    if attribute == "sex":
        col = _column(release, "gender", None, variant)
        vals = frame[col].astype("string").str.strip().str.lower()
        vals = vals.where(vals.isin(["female", "male"]))
        code = 'vals = pop["gender"].str.lower()'
        return AttributeValues(vals, (category or "").lower(), [CLINICAL], code, col)

    if attribute == "subtype":
        col = subtype_column(variant)
        if col not in release.clinical.columns:
            raise CannotCheck(f"this release's clinical file has no {col} column")
        raw = frame[col]
        vals = raw.where(raw.isna(), raw.map(lambda v: normalise_subtype(str(v))))
        code = f'vals = pop["{col}"].map(normalise_subtype)'
        if (category or "").lower() == "luminal":  # Luminal A and Luminal B together
            vals = vals.replace({"Luminal A": "Luminal", "Luminal B": "Luminal"})
            code += '.replace({"Luminal A": "Luminal", "Luminal B": "Luminal"})  # A and B together'
            return AttributeValues(vals, "Luminal", [CLINICAL], code, col)
        return AttributeValues(vals, normalise_subtype(category or ""), [CLINICAL], code, col)

    if attribute == "vital_status":
        return _vital_status(release, frame, category, variant)

    if attribute in ("dss_status", "pfi_status"):
        return _survival_event(release, frame, attribute)

    if attribute == "layer":  # "every tumor with protein data ...": whether the sample is in that data file
        layer = (category or "").lower()
        if layer == "rna" and release.rna_ids is None:
            raise CannotCheck("no RNA file in this release")
        try:
            have = release.layer_ids(layer)
        except KeyError:
            raise CannotCheck(f"no {category} data layer in this release") from None
        vals = pd.Series([layer if s in have else f"no {layer}" for s in frame.index], index=frame.index, dtype="object")
        code = f'vals = pop.sampleID.map(lambda s: "{layer}" if s in r.{layer}_ids else "no {layer}")'
        return AttributeValues(vals, layer, [CLINICAL], code, f"{layer} data file")

    if attribute == "slide_kind":
        return _slide_kind(release, frame, category)

    if attribute in GENE_ATTRIBUTES:
        return _gene_calls(release, frame, attribute, category)

    raise CannotCheck(f"no check for {attribute!r} yet")


def _vital_status(release: Release, frame: pd.DataFrame, category: str | None, variant: Variant) -> AttributeValues:
    hit = (category or "deceased").lower()
    if variant.subtype_source == SECOND_SOURCE and "vital_status" in release.clinical.columns:
        raw = frame["vital_status"].astype("string").str.strip().str.upper()
        vals = raw.map({"DECEASED": "deceased", "DEAD": "deceased", "LIVING": "living", "ALIVE": "living"})
        code = 'vals = pop["vital_status"].str.upper().map({"DECEASED": "deceased", "LIVING": "living"})'
        return AttributeValues(vals, hit, [CLINICAL], code, "vital_status")
    survival = release.survival
    if survival is None or "OS" not in survival.columns:
        raise CannotCheck("this release's survival file has no OS (death) column")
    os_by_sample = survival.drop_duplicates("sample").set_index("sample")["OS"]
    os_vals = pd.Series(frame.index.map(lambda s: os_by_sample.get(s, float("nan"))), index=frame.index)
    vals = os_vals.map({1: "deceased", 0: "living", 1.0: "deceased", 0.0: "living"})
    code = ('os = r.survival.drop_duplicates("sample").set_index("sample")["OS"]\n'
            'vals = pop.sampleID.map(os).map({1: "deceased", 0: "living"})  # OS = 1: died')
    return AttributeValues(vals, hit, [CLINICAL, RELEASE_FILES["survival"]], code, "survival.tsv OS")


_EVENT = {  # attribute -> (survival.tsv column, label when 1, label when 0, words)
    "dss_status": ("DSS", "deceased", "living", "disease-specific death (DSS = 1)"),
    "pfi_status": ("PFI", "event", "no event", "progression-free interval event (PFI = 1)"),
}


def _survival_event(release: Release, frame: pd.DataFrame, attribute: str) -> AttributeValues:
    col, yes, no, words = _EVENT[attribute]
    survival = release.survival
    if survival is None or col not in survival.columns:
        raise CannotCheck(f"this release's survival file has no {col} column")
    by_sample = survival.drop_duplicates("sample").set_index("sample")[col]
    raw = pd.Series(frame.index.map(lambda s: by_sample.get(s, float("nan"))), index=frame.index)
    vals = raw.map({1: yes, 0: no, 1.0: yes, 0.0: no})
    code = (f'event = r.survival.drop_duplicates("sample").set_index("sample")["{col}"]\n'
            f'vals = pop.sampleID.map(event).map({{1: "{yes}", 0: "{no}"}})  # {words}')
    return AttributeValues(vals, yes, [CLINICAL, RELEASE_FILES["survival"]], code, f"survival.tsv {col}")


def _slide_kind(release: Release, frame: pd.DataFrame, category: str | None) -> AttributeValues:
    """Whether each sample has at least one slide of the kind (from the slide manifest next to release A)."""
    from second_opinion.release import SLIDE_MANIFEST

    slides = release.slides
    if slides is None:
        raise CannotCheck(f"this release folder has no {SLIDE_MANIFEST} (envelope releases ship without it)")
    kind = (category or "diagnostic").lower()
    has = set(slides.loc[slides["slide_kind"].astype(str).str.lower().str.startswith(kind), "sample_id"].astype(str))
    vals = pd.Series([kind if s in has else f"no {kind}" for s in frame.index], index=frame.index, dtype="object")
    code = (f'slides = pd.read_csv("{SLIDE_MANIFEST}")\n'
            f'has = set(slides[slides.slide_kind.str.lower().str.startswith("{kind}")].sample_id)\n'
            f'vals = pop.sampleID.map(lambda s: "{kind}" if s in has else "no {kind}")')
    return AttributeValues(vals, kind, [CLINICAL, SLIDE_MANIFEST], code, f"{SLIDE_MANIFEST} slide_kind")


def slide_kind_counts(release: Release) -> pd.Series:
    """Slides per kind ("diagnostic", "frozen") in the slide manifest."""
    from second_opinion.release import SLIDE_MANIFEST

    if release.slides is None:
        raise CannotCheck(f"this release folder has no {SLIDE_MANIFEST} (envelope releases ship without it)")
    kind = release.slides["slide_kind"].astype(str).str.lower().str.extract(r"^(diagnostic|frozen)")[0]
    return kind.value_counts()


GENE_ATTRIBUTES = ("mutation", "amplification", "deletion", "gain", "loss")
_GENE_TESTS = {  # attribute -> (word, test on the value, the test as code)
    "mutation": ("mutated", lambda v: v > 0, "> 0"),
    "amplification": ("amplified", lambda v: v >= 2, ">= 2  # GISTIC 2 = high-level amplification"),
    "deletion": ("deleted", lambda v: v <= -2, "<= -2  # GISTIC -2 = deep deletion"),
    "gain": ("gained", lambda v: v >= 1, ">= 1  # GISTIC 1 or 2 = gain or amplification"),
    "loss": ("lost", lambda v: v <= -1, "<= -1  # GISTIC -1 or -2 = loss or deep deletion"),
}


def _age_cut(category: str) -> tuple[str, float]:
    """"gt60" -> ("gt", 60.0); "eq2010" -> ("eq", 2010.0) for a single year."""
    m = re.fullmatch(r"(gt|gte|lt|lte|eq)(\d+(?:\.\d+)?)", category)
    if m is None:
        raise CannotCheck(f"'{category}' is not an age group this tool reads")
    return m.group(1), float(m.group(2))


def _gene_calls(release: Release, frame: pd.DataFrame, attribute: str, category: str | None) -> AttributeValues:
    if not category:
        raise CannotCheck("the claim names no gene")
    genes = [gene_symbol(g) for g in category.split("+")]
    word, test, test_code = _GENE_TESTS[attribute]
    if attribute == "mutation":
        matrix, file = release.mutation(), RELEASE_FILES["mutation"]
    else:
        matrix, file = release.copy_number(), RELEASE_FILES["copy_number"]
    for gene in genes:
        if gene not in matrix.index:
            raise CannotCheck(f"the {file} file has no {gene} row")
    gene = genes[0]
    rows = matrix.loc[genes]
    in_file = [s for s in frame.index if s in matrix.columns]
    vals = pd.Series(float("nan"), index=frame.index, dtype="object")
    called = test(rows[in_file]).all(axis=0)  # with several genes ("TP53 and PIK3CA co-occurred"): all of them
    if len(genes) > 1:
        test_code = f"{test_code.split('  #')[0]} for every gene in {genes}"
    vals[in_file] = [word if bool(x) else f"not {word}" for x in called]
    matrix_name = "r.mutation()" if attribute == "mutation" else "r.copy_number()"
    condition = test_code.split("  #")[0]
    code = (f'm = {matrix_name}.loc[{genes!r}]\n'
            f'vals = pop.sampleID.map(lambda s: ("{word}" if (m[s] {condition.split(" for ")[0]}).all() else "not {word}") '
            f'if s in m.columns else None)' + (f"  #{test_code.split('#')[1]}" if "#" in test_code else ""))
    return AttributeValues(vals, word, [CLINICAL, file], code, f"{file} ({' + '.join(genes)})")


def gene_frequencies(release: Release, sample_ids: list[str], attribute: str = "mutation") -> tuple[pd.Series, int]:
    """Per gene: how many of `sample_ids` (those in the file) carry the call; and how many samples were looked at."""
    matrix = release.mutation() if attribute == "mutation" else release.copy_number()
    cols = [s for s in sample_ids if s in matrix.columns]
    counts = _GENE_TESTS[attribute][1](matrix[cols]).sum(axis=1)
    return counts.sort_values(ascending=False, kind="stable"), len(cols)


def age_values(release: Release, pop: pd.DataFrame, variant: Variant) -> tuple[pd.Series, str]:
    col = _column(release, AGE_COLUMNS[0], AGE_COLUMNS[1], variant)
    vals = pd.to_numeric(clinical_frame(pop)[col], errors="coerce")
    return vals, col
