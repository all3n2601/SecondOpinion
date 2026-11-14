"""Validate, run and judge a query plan. Everything here is deterministic pandas; no model is involved.

A plan is data (see `plan.py`). `validate_plan` checks it against whitelists and the release, and checks
that the claim the plan says it is testing is really in the sentence. `execute_plan` maps every filter to
an explicit pandas expression through lookup tables (nothing from the plan is ever evaluated as code) and
returns a `Fact` whose `code` is generated from the same tables, so the snippet is what actually ran.
`judge_plan` compares the stated number with the Fact, reusing `verdict.judge` where it fits.
"""

import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal

import pandas as pd

from second_opinion.ai.plan import (
    CompareGroupsPlan, CompareMeansPlan, CountPlan, Filter, OrderPlan, QueryPlan, RankGroupsPlan, RankPlan, SharePlan,
    Stated, SummaryStatPlan,
)
from second_opinion.checks.attributes import (
    ATTRIBUTE_NOUNS, attribute_known, attribute_mask, attribute_values, clinical_frame, describe, gene_symbol,
)
from second_opinion.checks.base import CannotCheck
from second_opinion.extract import ZERO_AMOUNT, bound_op, find_amounts
from second_opinion.model import Claim, ClaimParams, ClaimType, Fact, Verdict
from second_opinion.numwords import WORDS, fraction_amounts, word_numbers
from second_opinion.release import RELEASE_FILES, RNA_FILE, Release
from second_opinion.variants import PRIMARY_VARIANT, normalise_subtype
from second_opinion.verdict import (
    RATIO_TOLERANCE_EXACT, RATIO_TOLERANCE_FRACTION, _bounded, _dec, _infer_decimals, _round_half_up, format_fact, judge,
)


class PlanRejected(Exception):
    """The plan (or the quote it rests on) is not acceptable; the message says why, in plain words."""


# ------------------------------------------------------------------ whitelists

SUBTYPES = ("Luminal A", "Luminal B", "HER2-enriched", "Basal-like", "Normal-like")
_SAMPLE_TYPE_CODES = {"primary": "01", "normal_tissue": "11", "metastatic": "06"}
_SEX_VALUES = {"female": "FEMALE", "male": "MALE"}
_STATUS_VALUES = {"positive": "Positive", "negative": "Negative"}
_LAYERS = ("survival", "mutation", "copy_number", "protein", "rna")
_COLUMNS = {
    "sex": "gender",
    "subtype_rna": "PAM50Call_RNAseq",
    "subtype_2012": "PAM50_mRNA_nature2012",
    "er_status": "breast_carcinoma_estrogen_receptor_status",
    "her2_status": "lab_proc_her2_neu_immunohistochemistry_receptor_status",
    "age_years": "age_at_initial_pathologic_diagnosis",
    "diagnosis_year": "year_of_initial_pathologic_diagnosis",
    "positive_lymph_nodes": "number_of_lymphnodes_positive_by_he",
}
_NUMERIC_WORDS = {"age_years": "age at diagnosis", "diagnosis_year": "year of diagnosis",
                  "positive_lymph_nodes": "number of positive lymph nodes"}
_FIELD_WORDS = {
    "sample_type": "sample type", "sex": "sex", "subtype_rna": "PAM50 RNA-seq subtype",
    "subtype_2012": "2012 study PAM50 subtype", "er_status": "ER status", "her2_status": "HER2 status",
    "has_layer": "data file", **_NUMERIC_WORDS,
}
_AGE_OPS = {"eq": ("==", lambda s, v: s == v), "gt": (">", lambda s, v: s > v), "gte": (">=", lambda s, v: s >= v),
            "lt": ("<", lambda s, v: s < v), "lte": ("<=", lambda s, v: s <= v)}
_AGE_WORDS = {"eq": "is", "gt": "is over", "gte": "is at least", "lt": "is under", "lte": "is at most"}
_STATS = {"median": "median", "mean": "mean", "min": "youngest", "max": "oldest", "range": "youngest and oldest"}
_IMPORT_SUBTYPE = "from second_opinion.variants import normalise_subtype"
_IMPORT_PANDAS = "import pandas as pd"


# ------------------------------------------------------------------ filters -> pandas, through lookup tables


@dataclass
class _Cond:
    """One compiled filter: how to apply it, how to write it as pandas, and how to say it in words."""

    field: str
    mask: Callable[[pd.DataFrame], pd.Series]
    code: Callable[[str], str]  # variable name -> boolean pandas expression
    phrase: str
    files: tuple[str, ...] = (RELEASE_FILES["clinical"],)
    imports: tuple[str, ...] = ()
    known_mask: Callable[[pd.DataFrame], pd.Series] | None = None  # rows where this field has a usable value
    known_code: Callable[[str], str] | None = None
    known_phrase: str = ""
    needs_known: bool = False  # as a share numerator, the denominator keeps only rows where it is known


def _text_values(f: Filter, allowed: dict[str, str]) -> list[str]:
    """Legal values for a categorical filter, mapped to canonical spellings (PlanRejected otherwise)."""
    if f.op == "eq":
        if not isinstance(f.value, str):
            raise PlanRejected(f"filter on {f.field} needs one text value")
        raw = [f.value]
    elif f.op == "in":
        if not isinstance(f.value, list) or not f.value or not all(isinstance(v, str) for v in f.value):
            raise PlanRejected(f"filter on {f.field} with 'in' needs a non-empty list of text values")
        raw = f.value
    else:
        raise PlanRejected(f"filter on {f.field} cannot use '{f.op}'")
    out = []
    for v in raw:
        key = " ".join(v.strip().lower().replace("-", " ").split()).replace(" ", "_")
        if key not in allowed:
            raise PlanRejected(f"'{v}' is not a legal value for {f.field}; use one of {', '.join(allowed)}")
        out.append(allowed[key])
    return out


def _require_column(release: Release, col: str) -> None:
    if col not in release.clinical.columns:
        raise PlanRejected(f"this release's clinical file has no {col} column")


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else " or ".join(items)


def _compile(f: Filter, release: Release) -> _Cond:
    """Validate one filter against the whitelist and the release, and build it. PlanRejected if it is not legal."""
    fld, op = f.field, f.op
    if op == "is_unknown":  # "lacks an age at diagnosis": the rows is_known leaves out
        if f.value is not None:
            raise PlanRejected(f"filter on {fld} with 'is_unknown' takes no value")
        known = _compile(f.model_copy(update={"op": "is_known"}), release)
        return _Cond(fld, lambda d: ~known.mask(d).astype(bool), lambda v: f"~({known.code(v)})",
                     known.phrase.replace("has ", "has no ", 1), files=known.files, imports=known.imports)
    if op == "is_known":
        if f.value is not None:
            raise PlanRejected(f"filter on {fld} with 'is_known' takes no value")
    elif op not in ("eq", "in", "gt", "gte", "lt", "lte") or f.value is None:
        raise PlanRejected(f"filter on {fld} needs a value")
    if fld not in _NUMERIC_WORDS and op in ("gt", "gte", "lt", "lte"):
        raise PlanRejected(f"filter on {fld} cannot use '{op}'; only numbers (age, year, lymph nodes) can be compared")

    if fld == "sample_type":
        if op == "is_known":
            return _Cond(fld, lambda d: d["sampleID"].notna(), lambda v: f"{v}['sampleID'].notna()", "has a sample ID")
        keys = [k.strip().lower().replace("-", " ").replace(" ", "_") for k in (f.value if isinstance(f.value, list) else [f.value])
                if isinstance(k, str)]
        codes = [_SAMPLE_TYPE_CODES[k] for k in _text_values(f, {k: k for k in _SAMPLE_TYPE_CODES})]
        names = [k.replace("_", " ") for k in keys]

        def code(v: str) -> str:
            sl = f"{v}['sampleID'].astype(str).str[13:15]"
            return f"({sl} == {codes[0]!r})" if len(codes) == 1 else f"{sl}.isin({codes!r})"

        return _Cond(fld, lambda d: d["sampleID"].astype(str).str[13:15].isin(codes), code, f"sample type is {_join(names)}")

    if fld == "has_layer":
        if op == "is_known":
            raise PlanRejected("filter on has_layer cannot use 'is_known'")
        layers = [k for k in _text_values(f, {k: k for k in _LAYERS})]
        if "rna" in layers and release.rna_ids is None:
            raise PlanRejected("no RNA file in this release")
        files = tuple(RNA_FILE if k == "rna" else RELEASE_FILES[k] for k in layers)
        ids = set().union(*(release.layer_ids(k) for k in layers))
        pool = " | ".join(f'set(r.layer_ids("{k}"))' for k in layers)
        return _Cond(
            fld, lambda d: d["sampleID"].astype(str).isin(ids),
            lambda v: f"{v}['sampleID'].astype(str).isin({pool})",
            f"is in the {_join([k.replace('_', ' ') for k in layers])} file", files=(RELEASE_FILES["clinical"], *files),
        )

    if fld == "attribute":
        return _attribute_filter(f, release)

    col = _COLUMNS[fld]
    _require_column(release, col)
    notna = (lambda d: d[col].notna(), lambda v: f"{v}[{col!r}].notna()")

    if fld in _NUMERIC_WORDS:
        words = _NUMERIC_WORDS[fld]
        known = (lambda d: pd.to_numeric(d[col], errors="coerce").notna(),
                 lambda v: f"pd.to_numeric({v}[{col!r}], errors='coerce').notna()")
        if op == "is_known":
            return _Cond(fld, known[0], known[1], f"has a recorded {words}", imports=(_IMPORT_PANDAS,))
        if op not in _AGE_OPS:
            raise PlanRejected(f"filter on {fld} cannot use '{op}'")
        value = f.value
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise PlanRejected(f"{fld} needs a number")
        symbol, fn = _AGE_OPS[op]
        shown = int(value) if float(value).is_integer() else float(value)
        return _Cond(
            fld, lambda d: fn(pd.to_numeric(d[col], errors="coerce"), value),
            lambda v: f"(pd.to_numeric({v}[{col!r}], errors='coerce') {symbol} {shown!r})",
            f"{words} {_AGE_WORDS[op]} {shown}", imports=(_IMPORT_PANDAS,),
            known_mask=known[0], known_code=known[1], known_phrase=f"a recorded {words}", needs_known=True,
        )

    if fld == "sex":
        known = notna
        if op == "is_known":
            return _Cond(fld, known[0], known[1], "has a recorded sex")
        vals = _text_values(f, _SEX_VALUES)
        words = [k.lower() for k in vals]
        return _simple(fld, col, vals, f"sex is {_join(words)}", known, "a recorded sex")

    if fld in ("er_status", "her2_status"):
        known = (lambda d: d[col].isin(list(_STATUS_VALUES.values())),
                 lambda v: f"{v}[{col!r}].isin({list(_STATUS_VALUES.values())!r})")
        label = "ER" if fld == "er_status" else "HER2"
        if op == "is_known":
            return _Cond(fld, known[0], known[1], f"has a positive or negative {label} status")
        vals = _text_values(f, _STATUS_VALUES)
        return _simple(fld, col, vals, f"{label} status is {_join([k.lower() for k in vals])}", known,
                       f"a positive or negative {label} status")

    # subtype_rna / subtype_2012
    known = notna
    label = _FIELD_WORDS[fld]
    if op == "is_known":
        return _Cond(fld, known[0], known[1], f"has a {label} call")
    vals = _subtype_values(f)
    return _Cond(
        fld, lambda d: d[col].map(normalise_subtype).isin(vals),
        lambda v: (f"({v}[{col!r}].map(normalise_subtype) == {vals[0]!r})" if len(vals) == 1
                   else f"{v}[{col!r}].map(normalise_subtype).isin({vals!r})"),
        f"{label} is {_join(vals)}", imports=(_IMPORT_SUBTYPE,),
        known_mask=known[0], known_code=known[1], known_phrase=f"a {label} call", needs_known=True,
    )


_GENE_ATTRIBUTES = ("mutation", "amplification", "deletion", "gain", "loss")
_IMPORT_ATTRIBUTES = "from second_opinion.checks.attributes import attribute_known, attribute_mask"


def _stage_name(value: str) -> str:
    """"IV", "stage iv", "Stage 4" -> "Stage IV" (the spelling the attribute layer reads)."""
    m = re.fullmatch(r"(?:stage\s*)?(IV|III|II|I|[1-4])([ABC])?", value.strip(), re.IGNORECASE)
    if m is None:
        return value
    roman = {"1": "I", "2": "II", "3": "III", "4": "IV"}.get(m.group(1), m.group(1).upper())
    return f"Stage {roman}{(m.group(2) or '').upper()}"


def _attribute_filter(f: Filter, release: Release) -> _Cond:
    """Any attribute the rules read, through the rules' own definitions (checks/attributes.py)."""
    attr = f.attribute
    if attr is None:
        raise PlanRejected("an attribute filter needs an attribute name")
    if f.op == "is_known":
        if attr in _GENE_ATTRIBUTES:
            raise PlanRejected(f"'is_known' on {attr} needs a gene; filter on the data file with has_layer instead")
        categories: list[str | None] = [None]
    elif f.op == "eq" and isinstance(f.value, str):
        categories = [f.value.strip()]
    elif f.op == "in" and isinstance(f.value, list) and f.value and all(isinstance(v, str) for v in f.value):
        categories = [v.strip() for v in f.value]
    else:
        raise PlanRejected(f"filter on {attr} needs a text value, or a list of them with 'in'")
    if attr == "stage":
        categories = [_stage_name(c) if c else c for c in categories]
    frame = clinical_frame(release.clinical)
    hits, files = [], [RELEASE_FILES["clinical"]]
    for category in categories:
        try:
            av = attribute_values(release, frame, attr, category, PRIMARY_VARIANT)
        except CannotCheck as exc:
            raise PlanRejected(str(exc)) from exc
        labels = set(av.values.dropna().unique())
        if category is not None and av.hit not in labels:
            shown = ", ".join(sorted(str(x) for x in labels)[:8])
            raise PlanRejected(f"'{category}' is not a value of {attr} in this release; it has {shown}")
        hits.append(av.hit)
        files += [x for x in av.files if x not in files]
    words = _join([describe(attr, c) for c in categories]) if categories != [None] else f"a recorded {ATTRIBUTE_NOUNS[attr]}"
    known_cat = categories[0]
    known = (lambda d: attribute_known(release, d, attr, known_cat),
             lambda v: f"attribute_known(r, {v}, {attr!r}, {known_cat!r})")
    if categories == [None]:
        return _Cond("attribute", known[0], known[1], f"has {words}", files=tuple(files), imports=(_IMPORT_ATTRIBUTES,))
    cats = [c for c in categories if c is not None]
    return _Cond(
        "attribute", lambda d: attribute_mask(release, d, attr, cats),
        lambda v: f"attribute_mask(r, {v}, {attr!r}, {cats!r})", f"is {words}", files=tuple(files),
        imports=(_IMPORT_ATTRIBUTES,), known_mask=known[0], known_code=known[1],
        known_phrase=f"a recorded {ATTRIBUTE_NOUNS[attr]}", needs_known=True,
    )


def _simple(fld: str, col: str, vals: list[str], phrase: str, known, known_phrase: str) -> _Cond:
    return _Cond(
        fld, lambda d: d[col].isin(vals),
        lambda v: f"({v}[{col!r}] == {vals[0]!r})" if len(vals) == 1 else f"{v}[{col!r}].isin({vals!r})",
        phrase, known_mask=known[0], known_code=known[1], known_phrase=known_phrase, needs_known=True,
    )


def _subtype_values(f: Filter) -> list[str]:
    raw = [f.value] if f.op == "eq" else f.value
    if f.op not in ("eq", "in"):
        raise PlanRejected(f"filter on {f.field} cannot use '{f.op}'")
    if f.op == "eq" and not isinstance(f.value, str):
        raise PlanRejected(f"filter on {f.field} needs one text value")
    if f.op == "in" and (not isinstance(raw, list) or not raw or not all(isinstance(v, str) for v in raw)):
        raise PlanRejected(f"filter on {f.field} with 'in' needs a non-empty list of text values")
    out = []
    for v in raw:
        name = normalise_subtype(v.strip())
        if name not in SUBTYPES:
            raise PlanRejected(f"'{v}' is not a subtype this release uses; use one of {', '.join(SUBTYPES)}")
        out.append(name)
    return out


def _subtype_name(value: str) -> str:
    name = normalise_subtype(value.strip()) if isinstance(value, str) else None
    if name not in SUBTYPES:
        raise PlanRejected(f"'{value}' is not a subtype this release uses; use one of {', '.join(SUBTYPES)}")
    return name


# ------------------------------------------------------------------ prepared plans


@dataclass
class _Prepared:
    plan: object
    where: list[_Cond]
    numerator: list[_Cond] = field(default_factory=list)
    extras: dict = field(default_factory=dict)


def _all_conds(p: _Prepared) -> list[_Cond]:
    return [*p.where, *p.numerator]


def _protein_row(release: Release, measure: str) -> str:
    wanted = str(measure).strip().lower()
    rows = [str(i) for i in release.protein.index]
    for row in rows:
        if row == measure:
            return row
    for row in rows:
        if row.lower() == wanted:
            return row
    raise PlanRejected(f"this release's protein file has no {measure} measurement")


_GROUP_FIELDS = {
    "er_status": ("ER", _STATUS_VALUES, _COLUMNS["er_status"]),
    "her2_status": ("HER2", _STATUS_VALUES, _COLUMNS["her2_status"]),
    "sex": ("", _SEX_VALUES, _COLUMNS["sex"]),
}


def _group(field_name: str, raw: str) -> tuple[str, str]:
    """(clinical value, display name) of one comparison group."""
    prefix, allowed, _ = _GROUP_FIELDS[field_name]
    key = raw.strip().lower().replace("-", " ").split()[-1] if isinstance(raw, str) and raw.strip() else ""
    if key not in allowed or len(raw.strip().split()) > 1 and not raw.strip().lower().startswith(prefix.lower()):
        raise PlanRejected(f"'{raw}' is not a legal group for {field_name}; use {' or '.join(allowed)}")
    return allowed[key], (f"{prefix}-{key}" if prefix else key)


def _prepare(plan, release: Release) -> _Prepared:
    where = [_compile(f, release) for f in plan.where]
    prep = _Prepared(plan, where)
    if isinstance(plan, SharePlan):
        if not plan.numerator:
            raise PlanRejected("a share needs at least one numerator filter")
        prep.numerator = [_compile(f, release) for f in plan.numerator]
    elif isinstance(plan, CompareMeansPlan):
        row = _protein_row(release, plan.measure)
        _, _, col = _GROUP_FIELDS[plan.group_field]
        _require_column(release, col)
        a, b = _group(plan.group_field, plan.group_a), _group(plan.group_field, plan.group_b)
        if a[0] == b[0]:
            raise PlanRejected("the two groups being compared are the same")
        prep.extras = {"row": row, "col": col, "a": a, "b": b}
    elif isinstance(plan, SummaryStatPlan):
        _require_column(release, _COLUMNS[plan.field])
    elif isinstance(plan, RankPlan) and plan.category_field == "mutated_gene":
        gene = gene_symbol(plan.category.strip())
        if gene not in release.mutation().index:
            raise PlanRejected(f"the mutation file has no gene {plan.category!r}")
        prep.extras = {"gene": gene}
    elif isinstance(plan, (CompareGroupsPlan, RankGroupsPlan)):
        _prepare_groups(plan, release, prep)
    elif isinstance(plan, RankPlan):
        _require_column(release, _COLUMNS[plan.category_field])
        prep.extras = {"col": _COLUMNS[plan.category_field], "cat": _subtype_name(plan.category)}
    elif isinstance(plan, OrderPlan):
        _require_column(release, _COLUMNS[plan.category_field])
        a, b = _subtype_name(plan.category_a), _subtype_name(plan.category_b)
        if a == b:
            raise PlanRejected("the two subtypes being compared are the same")
        prep.extras = {"col": _COLUMNS[plan.category_field], "a": a, "b": b}
    elif not isinstance(plan, CountPlan):
        raise PlanRejected("unsupported plan")
    return prep


def _prepare_groups(plan, release: Release, prep: _Prepared) -> None:
    """The measure each group is reduced to (count, share with a numerator, or a statistic), and the groups."""
    if plan.measure == "share":
        if not plan.numerator:
            raise PlanRejected("a share needs at least one numerator filter")
        prep.numerator = [_compile(f, release) for f in plan.numerator]
    elif plan.measure == "stat":
        if plan.field is None or plan.stat is None:
            raise PlanRejected("a statistic needs a numeric field and a stat")
        _require_column(release, _COLUMNS[plan.field])
    elif plan.numerator or plan.field:
        raise PlanRejected("a count takes no numerator or field")
    if isinstance(plan, CompareGroupsPlan):
        prep.extras["a"] = [_compile(f, release) for f in plan.group_a]
        prep.extras["b"] = [_compile(f, release) for f in plan.group_b]
    else:
        _require_column(release, _COLUMNS[plan.category_field])
        prep.extras.update(col=_COLUMNS[plan.category_field], cat=_subtype_name(plan.category))


# ------------------------------------------------------------------ the quote check


_ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8,
             "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12}
_PARTS = {"half": 2, "halves": 2, "third": 3, "thirds": 3, "quarter": 4, "quarters": 4, "fourth": 4, "fourths": 4,
          "fifth": 5, "fifths": 5, "sixth": 6, "sixths": 6, "seventh": 7, "sevenths": 7, "eighth": 8, "eighths": 8,
          "ninth": 9, "ninths": 9, "tenth": 10, "tenths": 10}
_NUM = re.compile(r"(?<![\w.])\d{1,3}(?:,\d{3})+(?:\.\d+)?|(?<![\w.])\d+(?:\.\d+)?")
_WORD = "|".join(sorted(WORDS, key=len, reverse=True))
_PART_RE = re.compile(rf"\b(a|an|{_WORD})[\s-]+({'|'.join(_PARTS)})\b", re.I)
_HALF_RE = re.compile(r"\bhalf\b", re.I)
_ORD_RE = re.compile(rf"\b({'|'.join(_ORDINALS)})\b", re.I)
_TOP_RE = re.compile(r"\b(most (common|frequent|prevalent)|commonest|largest|biggest|leading|dominant)\b", re.I)
_BOTTOM_RE = re.compile(r"\b(least (common|frequent|prevalent)|rarest|smallest)\b", re.I)
_HEDGE_RE = re.compile(r"\b(about|around|roughly|approximately|approx\.?|nearly|almost|circa|close to)\b|~|≈|\bca\.", re.I)
_FRACTION_TOLERANCE = 0.1


def _squash(text: str) -> str:
    return " ".join(text.split()).casefold()


def _word_value(token: str) -> float | None:
    t = token.lower()
    if t in ("a", "an"):
        return 1.0
    if t in WORDS:
        return float(WORDS[t])
    return float(t) if t.isdigit() else None


def _fractions(text: str) -> list[float]:
    """Percentages spelled as fractions: 'one in six' 16.7, 'half' 50, 'two thirds' 66.7, 'a quarter' 25."""
    out = [f.value for f in fraction_amounts(text)]
    for m in _PART_RE.finditer(text):
        top = _word_value(m.group(1))
        if top is not None:
            out.append(100 * top / _PARTS[m.group(2).lower()])
    if _HALF_RE.search(text):
        out.append(50.0)
    return out


def _literal_numbers(text: str) -> list[float]:
    nums = [float(m.group().replace(",", "")) for m in _NUM.finditer(text)]
    nums += [w.value for w in word_numbers(text)]  # whole phrases: "ninety-seven" is 97, never 7 or 90
    return nums


def _rank_numbers(text: str) -> list[float]:
    ords = [float(_ORDINALS[m.group().lower()]) for m in _ORD_RE.finditer(text)]
    if ords:
        return ords
    out = []
    if _TOP_RE.search(text):
        out.append(1.0)
    if _BOTTOM_RE.search(text):
        out.append(float(len(SUBTYPES)))
    return out


def _derivable(value: float, sentence: str, kind: str) -> bool:
    if value == 0 and ZERO_AMOUNT.search(sentence):  # "None of the", "Not a single", "No men"
        return True
    if kind == "percent" and any(a.words and abs(a.value - value) < 1e-6 for a in find_amounts(sentence)):
        return True  # "most" 50, "nearly all" 90, "a minority" 50, read the rules' way
    literal = _literal_numbers(sentence)
    if kind == "number":
        literal += [-x for x in literal]
    if any(abs(value - x) < 1e-9 for x in literal):
        return True
    if kind == "rank" and any(abs(value - x) < 1e-9 for x in _rank_numbers(sentence)):
        return True
    return any(abs(value - x) <= _FRACTION_TOLERANCE for x in _fractions(sentence))


# kinds a stated claim may have for each plan op
_KINDS = {
    "count": {"count", "number"}, "share": {"percent", "count"}, "compare_means": {"direction", "relation", "number"},
    "summary_stat": {"number"}, "rank": {"rank"}, "order": {"relation", "direction"},
    "compare_groups": {"relation", "direction", "number"}, "rank_groups": {"rank"},
}


def _check_kind(plan, stated: Stated) -> None:
    if stated.kind not in _KINDS[plan.op]:
        raise PlanRejected(f"a {stated.kind} claim cannot be checked by a {plan.op.replace('_', ' ')} plan")
    if stated.kind in ("direction", "relation"):
        if stated.relation is None:
            raise PlanRejected("the claim says more or less but the plan does not say which")
    elif stated.value is None:
        raise PlanRejected(f"the {stated.kind} claim has no number")
    if stated.high is not None and stated.value is not None and stated.high < stated.value:
        raise PlanRejected("the top of the stated range is below its bottom")
    if stated.total is not None and not (plan.op == "share" and stated.kind == "count"):
        raise PlanRejected("a stated total can only be checked against a share plan")


_SUPERLATIVE_RE = re.compile(
    r"\b(?:most|least|highest|lowest|youngest|oldest|greatest|smallest|largest|rarest|commonest|fewest)\b", re.I)


def _check_quote(stated: Stated, sentence: str, op: str | None = None) -> None:
    span = _squash(stated.span)
    if not span or span not in _squash(sentence):
        raise PlanRejected("the quoted span is not in the sentence")
    for name, value in (("number", stated.value), ("upper end", stated.high), ("total", stated.total)):
        if op == "rank_groups" and name == "number" and value == 1 and _SUPERLATIVE_RE.search(stated.span):
            continue  # "the youngest", "rarest in": first, in the plan's own order
        if value is not None and not _derivable(float(value), sentence, stated.kind):
            raise PlanRejected(f"the quoted {name} {value:g} is not in the sentence")


# ------------------------------------------------------------------ validate


def validate_plan(qp: QueryPlan, sentence: str, release: Release) -> None:
    """Raise PlanRejected unless the plan is legal for this release and quotes the sentence honestly."""
    if not qp.answerable:
        raise PlanRejected("not answerable")
    if qp.plan is None:
        raise PlanRejected("the plan is missing")
    if qp.stated is None:
        raise PlanRejected("the plan does not say what the sentence claims")
    _check_quote(qp.stated, sentence, qp.plan.op)
    _check_kind(qp.plan, qp.stated)
    _prepare(qp.plan, release)


# ------------------------------------------------------------------ execute


def _where_text(where: list[_Cond]) -> str:
    return " and ".join(c.phrase for c in where)


def _population_words(where: list[_Cond]) -> str:
    return f"samples where {_where_text(where)}" if where else "all samples"


def _population_code(where: list[_Cond]) -> list[str]:
    lines = ["base = r.clinical[r.clinical.sampleID.notna()]"]
    if where:
        lines.append("pop = base[" + " & ".join(c.code("base") for c in where) + "]")
    else:
        lines.append("pop = base")
    return lines


def _imports(conds: list[_Cond], *more: str) -> list[str]:
    seen = []
    for imp in (*more, *(i for c in conds for i in c.imports)):
        if imp not in seen:
            seen.append(imp)
    return seen


def _files(conds: list[_Cond], *more: str) -> list[str]:
    out: list[str] = []
    for name in (RELEASE_FILES["clinical"], *(n for c in conds for n in c.files), *more):
        if name not in out:
            out.append(name)
    return out


def _population(release: Release, where: list[_Cond]) -> pd.DataFrame:
    df = release.clinical[release.clinical["sampleID"].notna()]
    for cond in where:
        df = df[cond.mask(df)]
    return df


def _sex_note(release: Release, where: list[_Cond]) -> dict[str, int]:
    """Rows dropped because their sex is unknown, when a filter asks about sex (population.py's convention)."""
    sex = [c for c in where if c.field == "sex" and c.known_mask is not None]
    if not sex:
        return {}
    others = [c for c in where if c.field != "sex"]
    df = _population(release, others)
    return {"excluded_unknown_sex": int((~sex[0].known_mask(df)).sum())}


def _ids(df: pd.DataFrame) -> list[str]:
    return df["sampleID"].astype(str).tolist()


def _count(release: Release, prep: _Prepared) -> Fact:
    plan: CountPlan = prep.plan
    pop = _population(release, prep.where)
    lines = [*_imports(prep.where), *_population_code(prep.where)]
    if plan.of == "patients":
        n = int(pop["sampleID"].astype(str).str[:12].nunique())
        lines.append("n = pop['sampleID'].astype(str).str[:12].nunique()  # distinct patients")
        label = f"patients with samples where {_where_text(prep.where)}" if prep.where else "patients with samples"
    else:
        n = len(pop)
        lines.append("n = len(pop)")
        label = _population_words(prep.where)
    return Fact(
        label=f"number of {label}", value=n, numerator=n, denominator=None, sample_ids=_ids(pop),
        files=_files(prep.where), code="\n".join(lines), extra=_sex_note(release, prep.where),
    )


def _share(release: Release, prep: _Prepared) -> Fact:
    pop = _population(release, prep.where)
    needs = {c.field: c for c in prep.numerator if c.needs_known and c.known_mask is not None}
    known_conds = list(needs.values())
    called = pop
    for c in known_conds:
        called = called[c.known_mask(called)]
    hit = called
    for c in prep.numerator:
        hit = hit[c.mask(hit)]
    n, total = len(hit), len(called)
    if total == 0:
        raise PlanRejected("no rows to take a share of: nothing matches the population")

    lines = [*_imports(_all_conds(prep)), *_population_code(prep.where)]
    if known_conds:
        lines.append("called = pop[" + " & ".join(c.known_code("pop") for c in known_conds) + "]  # rows where it is recorded")
    else:
        lines.append("called = pop")
    lines.append("hit = called[" + " & ".join(c.code("called") for c in prep.numerator) + "]")
    lines.append("n, total = len(hit), len(called)")
    lines.append("n_unrecorded = len(pop) - len(called)")
    lines.append("percent = 100 * n / total")
    note = f", among those with {' and '.join(c.known_phrase for c in known_conds)}" if known_conds else ""
    label = f"percent of {_population_words(prep.where)} where {' and '.join(c.phrase for c in prep.numerator)}{note}"
    return Fact(
        label=label, value=100 * n / total, numerator=n, denominator=total, sample_ids=_ids(hit),
        files=_files(_all_conds(prep)), code="\n".join(lines), unknown_count=len(pop) - len(called),
        extra=_sex_note(release, prep.where),
    )


def _compare(release: Release, prep: _Prepared) -> Fact:
    where = list(prep.where)
    ex = prep.extras
    default_primary = not any(c.field == "sample_type" for c in where)
    if default_primary:
        primary = _compile(Filter(field="sample_type", op="eq", value="primary"), release)
        where = [primary, *where]
    pop = _population(release, where)
    row, col = ex["row"], ex["col"]
    (val_a, name_a), (val_b, name_b) = ex["a"], ex["b"]
    status = pop.set_index("sampleID")[col]
    samples = [s for s in release.protein.columns if s in status.index and status[s] in (val_a, val_b)]
    in_a = [s for s in samples if status[s] == val_a]
    in_b = [s for s in samples if status[s] == val_b]
    if not in_a or not in_b:
        empty = name_a if not in_a else name_b
        raise PlanRejected(f"this release has no {empty} samples with a {row} measurement")
    values = release.protein.loc[row, samples]
    mean_a, mean_b = float(values[in_a].mean()), float(values[in_b].mean())

    lines = [*_imports(where), *_population_code(where)]
    lines += [
        f"status = pop.set_index('sampleID')[{col!r}]",
        f"samples = [s for s in r.protein.columns if s in status.index and status[s] in ({val_a!r}, {val_b!r})]",
        f"values = r.protein.loc[{row!r}, samples]",
        f"mean_a = values[[s for s in samples if status[s] == {val_a!r}]].mean()  # {name_a}",
        f"mean_b = values[[s for s in samples if status[s] == {val_b!r}]].mean()  # {name_b}",
        "difference = mean_a - mean_b",
    ]
    who = "primary tumors" if default_primary and len(where) == 1 else _population_words(where)
    return Fact(
        label=f"mean {row} in {name_a} minus {name_b} ({who})", value=mean_a - mean_b, numerator=None,
        denominator=None, sample_ids=samples, files=_files(where, RELEASE_FILES["protein"]),
        code="\n".join(lines), extra={"n_a": len(in_a), "n_b": len(in_b), "mean_a": round(mean_a, 3),
                                      "mean_b": round(mean_b, 3)},
    )


def _summary(release: Release, prep: _Prepared) -> Fact:
    plan: SummaryStatPlan = prep.plan
    col = _COLUMNS[plan.field]
    pop = _population(release, prep.where)
    ages = pd.to_numeric(pop[col], errors="coerce")
    used = pop[ages.notna()]
    ages = ages.dropna()
    words = _NUMERIC_WORDS[plan.field]
    if ages.empty:
        raise PlanRejected("no recorded ages among the matching samples" if plan.field == "age_years"
                           else f"no recorded {words} among the matching samples")
    stat = "min" if plan.stat == "range" else plan.stat
    value = float(getattr(ages, stat)())
    lines = [*_imports(prep.where, _IMPORT_PANDAS), *_population_code(prep.where)]
    lines += [
        f"ages = pd.to_numeric(pop[{col!r}], errors='coerce').dropna()",
        "result = ages.min(), ages.max()" if plan.stat == "range" else f"result = ages.{plan.stat}()",
        "n = len(ages)",
        "n_no_age = len(pop) - n",
    ]
    extra = {"n": len(ages), "stat": plan.stat, **_sex_note(release, prep.where)}
    if plan.stat == "range":
        extra["max"] = float(ages.max())
    label = (f"{_STATS[plan.stat]} age at diagnosis in years" if plan.field == "age_years"
             else f"{'smallest and largest' if plan.stat == 'range' else _STATS[plan.stat].replace('youngest', 'smallest').replace('oldest', 'largest')} {words}")
    return Fact(
        label=f"{label}, {_population_words(prep.where)}", value=value,
        numerator=len(ages), denominator=len(pop), sample_ids=_ids(used), files=_files(prep.where),
        code="\n".join(lines), unknown_count=len(pop) - len(ages), extra=extra,
    )


def _subtype_counts(release: Release, prep: _Prepared) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, list[str]]:
    col = prep.extras["col"]
    pop = _population(release, prep.where)
    called = pop[pop[col].notna()]
    counts = called[col].map(normalise_subtype).value_counts().reindex(list(SUBTYPES), fill_value=0)
    lines = [*_imports(prep.where, _IMPORT_SUBTYPE), *_population_code(prep.where)]
    lines += [
        f"called = pop[pop[{col!r}].notna()]",
        f"counts = called[{col!r}].map(normalise_subtype).value_counts().reindex({list(SUBTYPES)!r}, fill_value=0)",
    ]
    return pop, called, counts, lines


def _rank(release: Release, prep: _Prepared) -> Fact:
    cat = prep.extras["cat"]
    pop, called, counts, lines = _subtype_counts(release, prep)
    if called.empty:
        raise PlanRejected("no subtype calls among the matching samples")
    rank = 1 + int((counts > counts[cat]).sum())
    lines.append(f"rank = 1 + int((counts > counts[{cat!r}]).sum())  # 1 = most common")
    extra: dict = {"ranked_of": len(SUBTYPES), "n_called": len(called)}
    for name in SUBTYPES:
        extra[f"count_{name}"] = int(counts[name])
        extra[f"share_{name}"] = round(100 * int(counts[name]) / len(called), 1)
    if int((counts == counts[cat]).sum()) > 1:
        extra["tied"] = "yes"
    return Fact(
        label=f"rank of {cat} by number of samples with a subtype call, {_population_words(prep.where)}",
        value=rank, numerator=None, denominator=None, sample_ids=_ids(called), files=_files(prep.where),
        code="\n".join(lines), unknown_count=len(pop) - len(called), extra=extra,
    )


def _order(release: Release, prep: _Prepared) -> Fact:
    a, b = prep.extras["a"], prep.extras["b"]
    pop, called, counts, lines = _subtype_counts(release, prep)
    count_a, count_b = int(counts[a]), int(counts[b])
    lines += [f"count_a, count_b = int(counts[{a!r}]), int(counts[{b!r}])", "difference = count_a - count_b"]
    col = prep.extras["col"]
    used = called[called[col].map(normalise_subtype).isin([a, b])]
    return Fact(
        label=f"samples called {a} minus samples called {b}, {_population_words(prep.where)}",
        value=count_a - count_b, numerator=None, denominator=None, sample_ids=_ids(used), files=_files(prep.where),
        code="\n".join(lines), unknown_count=len(pop) - len(called),
        extra={"category_a": a, "category_b": b, "count_a": count_a, "count_b": count_b},
    )


def _measure(release: Release, prep: _Prepared, df: pd.DataFrame) -> float | None:
    """One group reduced to its count, share or statistic; None when the group has nothing to measure."""
    plan = prep.plan
    if plan.measure == "count":
        return float(len(df))
    if plan.measure == "share":
        called = df
        for c in prep.numerator:
            if c.needs_known and c.known_mask is not None:
                called = called[c.known_mask(called)]
        hit = called
        for c in prep.numerator:
            hit = hit[c.mask(hit)]
        return 100 * len(hit) / len(called) if len(called) else None
    values = pd.to_numeric(df[_COLUMNS[plan.field]], errors="coerce").dropna()
    return float(getattr(values, plan.stat)()) if len(values) else None


def _measure_code(prep: _Prepared) -> list[str]:
    plan = prep.plan
    if plan.measure == "count":
        return ["def measure(df):", "    return len(df)"]
    if plan.measure == "share":
        known = [c for c in prep.numerator if c.needs_known and c.known_code is not None]
        return [
            "def measure(df):  # percent, among rows where it is recorded",
            "    called = df[" + " & ".join(c.known_code("df") for c in known) + "]" if known else "    called = df",
            "    hit = called[" + " & ".join(c.code("called") for c in prep.numerator) + "]",
            "    return 100 * len(hit) / len(called)",
        ]
    col = _COLUMNS[plan.field]
    return ["def measure(df):", f"    return pd.to_numeric(df[{col!r}], errors='coerce').dropna().{plan.stat}()"]


def _measure_words(prep: _Prepared) -> str:
    plan = prep.plan
    if plan.measure == "count":
        return "number of samples"
    if plan.measure == "share":
        return "percent where " + " and ".join(c.phrase for c in prep.numerator)
    return f"{plan.stat} {_NUMERIC_WORDS[plan.field]}"


def _compare_groups(release: Release, prep: _Prepared) -> Fact:
    plan: CompareGroupsPlan = prep.plan
    pop = _population(release, prep.where)
    a, b = pop, pop
    for c in prep.extras["a"]:
        a = a[c.mask(a)]
    for c in prep.extras["b"]:
        b = b[c.mask(b)]
    ma, mb = _measure(release, prep, a), _measure(release, prep, b)
    if ma is None or mb is None:
        raise PlanRejected("one of the two groups has nothing to measure")
    if plan.compare == "ratio" and mb == 0:
        raise PlanRejected("the second group measures zero, so there is no ratio")
    value = ma / mb if plan.compare == "ratio" else ma - mb
    conds = [*prep.where, *prep.numerator, *prep.extras["a"], *prep.extras["b"]]
    lines = [*_imports(conds, _IMPORT_PANDAS), *_population_code(prep.where), *_measure_code(prep)]
    lines += ["a = pop[" + " & ".join(c.code("pop") for c in prep.extras["a"]) + "]",
              "b = pop[" + " & ".join(c.code("pop") for c in prep.extras["b"]) + "]",
              "result = measure(a) " + ("/" if plan.compare == "ratio" else "-") + " measure(b)"]
    words_a = " and ".join(c.phrase for c in prep.extras["a"])
    words_b = " and ".join(c.phrase for c in prep.extras["b"])
    return Fact(
        label=f"{_measure_words(prep)}: samples where {words_a} {'divided by' if plan.compare == 'ratio' else 'minus'} "
              f"samples where {words_b}, {_population_words(prep.where)}",
        value=value, numerator=None, denominator=None, sample_ids=_ids(pd.concat([a, b])), files=_files(conds),
        code="\n".join(lines), extra={"a": round(ma, 3), "b": round(mb, 3), "n_a": len(a), "n_b": len(b),
                                     "words_a": words_a, "words_b": words_b},
    )


def _rank_groups(release: Release, prep: _Prepared) -> Fact:
    plan: RankGroupsPlan = prep.plan
    col, cat = prep.extras["col"], prep.extras["cat"]
    pop = _population(release, prep.where)
    calls = pop[col].map(normalise_subtype)
    values = {name: v for name in SUBTYPES if (v := _measure(release, prep, pop[calls == name])) is not None}
    if cat not in values:
        raise PlanRejected(f"no {cat} samples to measure")
    mine = values[cat]
    beaten = sum(1 for v in values.values() if (v < mine if plan.order == "lowest" else v > mine))
    rank = 1 + beaten
    conds = [*prep.where, *prep.numerator]
    lines = [*_imports(conds, _IMPORT_PANDAS, _IMPORT_SUBTYPE), *_population_code(prep.where), *_measure_code(prep)]
    sign = "<" if plan.order == "lowest" else ">"
    lines += [f"calls = pop[{col!r}].map(normalise_subtype)",
              f"values = {{s: measure(pop[calls == s]) for s in {list(SUBTYPES)!r} if (calls == s).any()}}",
              f"rank = 1 + sum(1 for v in values.values() if v {sign} values[{cat!r}])  # 1 = the {plan.order}"]
    return Fact(
        label=f"rank of {cat} by {_measure_words(prep)} ({plan.order} first), {_population_words(prep.where)}",
        value=rank, numerator=None, denominator=None, sample_ids=_ids(pop[calls.notna()]), files=_files(conds),
        code="\n".join(lines), extra={"order": plan.order, **{f"value_{k}": round(v, 2) for k, v in values.items()}},
    )


def _gene_rank(release: Release, prep: _Prepared) -> Fact:
    gene = prep.extras["gene"]
    pop = _population(release, prep.where)
    calls = release.mutation()
    ids = [i for i in calls.columns if i in set(pop["sampleID"].astype(str))]
    counts = (calls[ids] > 0).sum(axis=1)
    rank = 1 + int((counts > counts[gene]).sum())
    top = counts.sort_values(ascending=False).head(max(5, rank))
    lines = [*_imports(prep.where), *_population_code(prep.where),
             "ids = [i for i in r.mutation().columns if i in set(pop['sampleID'].astype(str))]",
             "counts = (r.mutation()[ids] > 0).sum(axis=1)  # tumors with a mutation, per gene",
             f"rank = 1 + int((counts > counts[{gene!r}]).sum())  # 1 = most often mutated"]
    return Fact(
        label=f"rank of {gene} among genes by number of mutated samples, {_population_words(prep.where)}",
        value=rank, numerator=int(counts[gene]), denominator=len(ids), sample_ids=[], files=_files(prep.where, RELEASE_FILES["mutation"]),
        code="\n".join(lines), extra={"genes": ", ".join(f"{g} {int(n)}" for g, n in top.items())},
    )


def _rank_any(release: Release, prep: _Prepared) -> Fact:
    return _gene_rank(release, prep) if "gene" in prep.extras else _rank(release, prep)


_RUNNERS = {"count": _count, "share": _share, "compare_means": _compare, "summary_stat": _summary,
            "rank": _rank_any, "order": _order, "compare_groups": _compare_groups, "rank_groups": _rank_groups}


def execute_plan(qp: QueryPlan, release: Release) -> Fact:
    """Run the plan on the release with pandas. The plan is re-checked first; PlanRejected if it cannot run."""
    if not qp.answerable or qp.plan is None:
        raise PlanRejected("not answerable")
    prep = _prepare(qp.plan, release)
    return _RUNNERS[qp.plan.op](release, prep)


# ------------------------------------------------------------------ judge


def _span_decimals(span: str, value: float | None) -> int | None:
    """Digits after the point the report wrote for `value` inside `span`; None when it is not written as digits."""
    if value is None:
        return None
    for m in _NUM.finditer(span):
        text = m.group().replace(",", "")
        if abs(float(text) - value) < 1e-9:
            return len(text.split(".")[1]) if "." in text else 0
    return None


def _is_approximate(sentence: str, stated: Stated) -> bool:
    """Hedged in the sentence's own words (we do not trust the model's flag), or a fraction like 'one in six'."""
    flat, span = _squash(sentence), _squash(stated.span)
    at = flat.find(span)
    window = flat[max(0, at - 30): at + len(span)] if at >= 0 else span
    if _HEDGE_RE.search(window):
        return True
    written = stated.value is not None and _span_decimals(stated.span, stated.value) is not None
    return bool(not written and _fractions(stated.span))


def _sentence_bound(sentence: str, stated: Stated) -> str | None:
    """"under", "more than", "at least" ... from the sentence's own words before the stated number (not the model's flag)."""
    if stated.high is not None:
        return None
    vague = [a for a in find_amounts(stated.span) if a.words and a.bound]
    if vague:  # "Most" is more than 50%, "nearly all" at least 90%: the word carries its own bound
        return vague[0].bound
    flat, span = _squash(sentence), _squash(stated.span)
    at = flat.find(span)
    if at < 0:
        return None
    first = re.search(rf"\d|\b(?:a|an|{_WORD})\b", span, re.I)
    return bound_op(flat[: at + (first.start() if first else len(span))])


def _num(x: float) -> str:
    return f"{x:,.0f}" if float(x).is_integer() else f"{x:,}"


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _judge_number(sentence: str, stated: Stated, ours: float) -> bool:
    """Equal after rounding to the span's precision; within 2% when hedged; inside the range or past the bound when given."""
    value = stated.value
    if stated.high is not None:
        return value <= ours <= stated.high
    bound = _sentence_bound(sentence, stated)
    if bound:
        return _bounded(_dec(ours), _dec(value), bound)
    if _is_approximate(sentence, stated):
        return abs(_dec(ours) - _dec(value)) <= Decimal("0.02") * abs(_dec(ours))
    decimals = _span_decimals(stated.span, value)
    decimals = _infer_decimals(value) if decimals is None else decimals
    return _round_half_up(ours, decimals) == _dec(value)


def _judge_groups(sentence: str, plan: CompareGroupsPlan, stated: Stated, fact: Fact) -> tuple[Verdict, str | None]:
    """A against B: "fewer than" by sign, "eight times as common" by the ratio (the rules' ratio tolerance)."""
    ratio = plan.compare == "ratio"
    if stated.kind in ("relation", "direction"):
        more = fact.value > 1 if ratio else fact.value > 0
        same = abs(fact.value - (1 if ratio else 0)) < 1e-12
        ok = not same and more == (stated.relation == "more")
    elif ratio:
        bound = _sentence_bound(sentence, stated)
        if bound:
            ok = _bounded(_dec(fact.value), _dec(stated.value), bound)
        else:
            tol = RATIO_TOLERANCE_FRACTION if _is_approximate(sentence, stated) else RATIO_TOLERANCE_EXACT
            ok = abs(fact.value - stated.value) <= tol * stated.value
    else:
        ok = _judge_number(sentence, stated, fact.value)
    if ok:
        return Verdict.SUPPORTED, None
    x = fact.extra
    shown = f"{fact.value:.2f} times" if ratio else f"difference {round(fact.value, 3):g}"
    return Verdict.CONTRADICTED, f"{x['words_a']} {x['a']:g} vs {x['words_b']} {x['b']:g} ({shown})"


def judge_plan(sentence: str, qp: QueryPlan, fact: Fact) -> tuple[Verdict, str | None]:
    """(SUPPORTED, None) or (CONTRADICTED, what the data says). PlanRejected when the quote does not fit the plan."""
    plan, stated = qp.plan, qp.stated
    if plan is None or stated is None:
        raise PlanRejected("the plan does not say what the sentence claims")
    _check_kind(plan, stated)
    op = plan.op

    if op in ("share", "count"):
        params = ClaimParams(
            stated_value=stated.value, stated_high=stated.high, stated_total=stated.total,
            unit="percent" if stated.kind == "percent" else "count",
            decimals=_span_decimals(stated.span, stated.value), approximate=_is_approximate(sentence, stated),
            bound=_sentence_bound(sentence, stated),
        )
        ctype = ClaimType.SHARE if stated.kind == "percent" else ClaimType.COUNT
        return judge(Claim("AI", sentence, 0, ctype, params), fact)

    if op == "compare_means" and stated.kind in ("direction", "relation"):
        params = ClaimParams(direction="higher" if stated.relation == "more" else "lower", group_a=_group(plan.group_field, plan.group_a)[1])
        return judge(Claim("AI", sentence, 0, ClaimType.COMPARISON, params), fact)

    if op == "compare_means":
        if _judge_number(sentence, stated, fact.value):
            return Verdict.SUPPORTED, None
        text = f"difference {round(fact.value, 3):g}"
        n_a, n_b = fact.extra.get("n_a"), fact.extra.get("n_b")
        if n_a is not None and n_b is not None:
            text += f" ({int(n_a):,} vs {int(n_b):,} samples)"
        return Verdict.CONTRADICTED, text

    if op == "summary_stat" and plan.stat == "range":  # "1988 to 2013": both ends, as written
        if stated.high is None:
            raise PlanRejected("a range claim needs both ends")
        lo, hi = fact.value, fact.extra["max"]
        if _round_half_up(lo, _infer_decimals(stated.value)) == _dec(stated.value) and \
                _round_half_up(hi, _infer_decimals(stated.high)) == _dec(stated.high):
            return Verdict.SUPPORTED, None
        return Verdict.CONTRADICTED, f"{_num(lo)} to {_num(hi)}"

    if op == "compare_groups":
        return _judge_groups(sentence, plan, stated, fact)

    if op == "rank_groups":
        if abs(fact.value - stated.value) < 1e-9:
            return Verdict.SUPPORTED, None
        listing = ", ".join(f"{k[6:]} {v:g}" for k, v in sorted(
            ((k, v) for k, v in fact.extra.items() if k.startswith("value_")), key=lambda kv: kv[1],
            reverse=plan.order == "highest"))
        return Verdict.CONTRADICTED, f"{_subtype_name(plan.category)} is {_ordinal(int(fact.value))} ({plan.order} first): {listing}"

    if op == "rank" and plan.category_field == "mutated_gene":
        if abs(fact.value - stated.value) < 1e-9:
            return Verdict.SUPPORTED, None
        return Verdict.CONTRADICTED, f"{gene_symbol(plan.category)} is {_ordinal(int(fact.value))}: {fact.extra['genes']}"

    if op == "summary_stat":
        if _judge_number(sentence, stated, fact.value):
            return Verdict.SUPPORTED, None
        n = fact.numerator if fact.numerator is not None else fact.extra.get("n")
        text = f"{plan.stat} {fact.value:.1f} years"
        return Verdict.CONTRADICTED, text + (f" (n={int(n):,})" if n is not None else "")

    if op == "rank":
        if abs(fact.value - stated.value) < 1e-9:
            return Verdict.SUPPORTED, None
        cat = _subtype_name(plan.category)
        names = sorted(SUBTYPES, key=lambda s: (-fact.extra.get(f"count_{s}", 0), SUBTYPES.index(s)))
        listing = ", ".join(f"{s} {_num(fact.extra[f'count_{s}'])}" for s in names if f"count_{s}" in fact.extra)
        tied = " (tied)" if fact.extra.get("tied") else ""
        return Verdict.CONTRADICTED, f"{cat} is {_ordinal(int(fact.value))} of {len(SUBTYPES)}{tied}: {listing}"

    # order
    if fact.value != 0 and (fact.value > 0) == (stated.relation == "more"):
        return Verdict.SUPPORTED, None
    a, b = _subtype_name(plan.category_a), _subtype_name(plan.category_b)
    ca, cb = fact.extra.get("count_a"), fact.extra.get("count_b")
    if ca is None or cb is None:
        return Verdict.CONTRADICTED, f"{a} minus {b}: {round(fact.value):,}"
    return Verdict.CONTRADICTED, f"{a} {_num(ca)} vs {b} {_num(cb)}"


def run_plan(sentence: str, qp: QueryPlan, release: Release) -> tuple[Fact, Verdict, str | None]:
    """Validate, execute and judge one plan. PlanRejected (plain words) if any step refuses."""
    validate_plan(qp, sentence, release)
    fact = execute_plan(qp, release)
    verdict, correct = judge_plan(sentence, qp, fact)
    return fact, verdict, correct
