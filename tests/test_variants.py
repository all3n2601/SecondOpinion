from claim_ladder.variants import all_variants, normalise_subtype


def test_eight_variants_with_unique_ids():
    variants = all_variants()
    assert len(variants) == 8
    assert len({v.id for v in variants}) == 8


def test_subtype_spellings_collapse():
    assert normalise_subtype("LumA") == normalise_subtype("Luminal A") == "Luminal A"
    assert normalise_subtype("Basal") == normalise_subtype("Basal-like")
