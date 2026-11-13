from pathlib import Path

from second_opinion.extract import split_sentences

PRACTICE_BRIEF = Path(__file__).resolve().parents[1] / "docs/challenge/products/research-claim-auditor/practice_brief.md"


def texts(report):
    return [s.text for s in split_sentences(report)]


def test_numbers_and_filenames_do_not_split():
    out = split_sentences("The cohort has 1,101 tumors (49.9% subtyped). See fetch.py for details.")
    assert [s.text for s in out] == ["The cohort has 1,101 tumors (49.9% subtyped).", "See fetch.py for details."]


def test_headings_and_emphasis():
    out = split_sentences("# Title\n\n*A note.* Body text.")
    assert [s.text for s in out] == ["A note.", "Body text."]


def test_empty_report():
    assert split_sentences("  \n ") == []


def test_indexes_count_from_zero_and_claim_id_is_none():
    out = split_sentences("One. Two! Three?")
    assert [s.index for s in out] == [0, 1, 2]
    assert all(s.claim_id is None for s in out)


def test_abbreviations_do_not_split():
    assert texts("Some subtypes, e.g. Luminal A, are common. Others vs. these are rare.") == [
        "Some subtypes, e.g. Luminal A, are common.",
        "Others vs. these are rare.",
    ]
    assert texts("Smith et al. Reported this first.") == ["Smith et al. Reported this first."]


def test_sentence_ending_in_subtype_letter_still_splits():
    assert texts("The largest group is Luminal A. Basal-like is smaller.") == [
        "The largest group is Luminal A.",
        "Basal-like is smaller.",
    ]


def test_split_before_a_number():
    assert texts("There are 1,101 primary tumors. 535 have all five layers.") == [
        "There are 1,101 primary tumors.",
        "535 have all five layers.",
    ]


def test_bullets_are_their_own_sentences():
    report = "Findings:\n- 535 tumors have all layers\n* Luminal A is about 62%\n1. Twelve samples are male"
    assert texts(report) == [
        "Findings:",
        "535 tumors have all layers",
        "Luminal A is about 62%",
        "Twelve samples are male",
    ]


def test_bullet_continuation_line_joins_the_bullet():
    assert texts("- First part of a bullet\n  that wraps. Second sentence.") == [
        "First part of a bullet that wraps.",
        "Second sentence.",
    ]


def test_paragraph_lines_are_joined():
    assert texts("A sentence that\nwraps onto two lines.\n\nNext paragraph.") == [
        "A sentence that wraps onto two lines.",
        "Next paragraph.",
    ]


def test_code_fences_and_rules_are_skipped():
    report = "Before.\n\n```python\nx = 1. Not a sentence.\n```\n\n---\n\nAfter."
    assert texts(report) == ["Before.", "After."]


def test_backticks_stripped_but_snake_case_kept():
    assert texts("Counts come from `protein_rppa.tsv.gz` and _clinical.tsv_.") == [
        "Counts come from protein_rppa.tsv.gz and clinical.tsv.",
    ]


def test_bold_and_links_keep_their_words():
    assert texts("**Luminal A** is common, see [the brief](brief.md).") == [
        "Luminal A is common, see the brief.",
    ]


def test_closing_quote_or_bracket_stays_with_sentence():
    assert texts('He said "it is 62%." Then he left.') == ['He said "it is 62%."', "Then he left."]


def test_blockquote_marker_removed():
    assert texts("> Quoted claim here.") == ["Quoted claim here."]


def test_table_separator_skipped_and_rows_kept():
    report = "| Subtype | Share |\n|---|---|\n| Luminal A | 49.9% |"
    assert texts(report) == ["Subtype | Share", "Luminal A | 49.9%"]


def test_practice_brief():
    out = texts(PRACTICE_BRIEF.read_text(encoding="utf-8"))
    assert "Of the 1,101 primary tumors in the release, 535 have survival, mutation, copy number, RNA and protein data." in out
    assert "Luminal A is the largest RNA subtype, accounting for about 62% of primary tumors with an RNA subtype call." in out
    assert (
        "Patients whose tumors had the highest ER-alpha protein responded best to hormone therapy, "
        "which suggests protein data could guide treatment research." in out
    )
    assert out[-1] == "We recommend future work combine all available layers."
    assert not any(s.startswith("#") for s in out)


def test_original_text_keeps_the_markdown_as_written():
    report = "**Luminal A** is the largest subtype. The cohort has `1,101` primary tumors. See [the table](t.md) for 535 samples."
    originals = [s.original_text for s in split_sentences(report)]
    assert originals == [
        "**Luminal A** is the largest subtype.",
        "The cohort has `1,101` primary tumors.",
        "See [the table](t.md) for 535 samples.",
    ]


def test_original_text_keeps_markup_that_wraps_the_whole_sentence():
    [info] = split_sentences("**All 1,101 primary tumors have RNA data.**")
    assert info.text == "All 1,101 primary tumors have RNA data."
    assert info.original_text == "**All 1,101 primary tumors have RNA data.**"


def test_a_repeated_sentence_is_listed_once():
    report = "Luminal A is the largest subtype.\n\n- **Luminal A** is the largest subtype.\n\nLuminal A is the largest subtype."
    assert [s.text for s in split_sentences(report)] == ["Luminal A is the largest subtype."]
