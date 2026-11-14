import pytest

from second_opinion.release import RELEASE_FILES, ReleaseError, load_release
from tests.helpers import MINI, make_mini_release


def test_mini_release_layers(mini_release):
    r = load_release(mini_release)
    assert len(r.clinical) == MINI["samples"]
    assert len(r.primary_ids()) == MINI["primary"]
    assert r.rna_ids is None
    full = set(r.primary_ids()) & r.survival_ids & r.mutation_ids & r.copy_number_ids & r.protein_ids
    assert len(full) == MINI["all_layers_primary"]
    assert r.layer_ids("protein") == r.protein_ids == set(r.protein.columns)
    assert "ERALPHA" in r.protein.index


def test_mini_counts_match_the_data(mini_release):
    c = load_release(mini_release).clinical
    primary = c[c["sampleID"].str[13:15] == "01"]
    assert (c["sampleID"].str[13:15] == "11").sum() == MINI["normal"]
    assert (c["sampleID"].str[13:15] == "06").sum() == MINI["metastasis"]
    assert (primary["gender"] == "MALE").sum() == MINI["male_primary"]
    assert primary["gender"].isna().sum() == MINI["unknown_sex_primary"]
    assert primary["PAM50Call_RNAseq"].notna().sum() == MINI["rna_subtyped_primary"]
    assert (primary["PAM50Call_RNAseq"] == "LumA").sum() == MINI["luma_rna_primary"]
    assert primary["PAM50_mRNA_nature2012"].notna().sum() == MINI["study_2012_subtyped_primary"]
    assert (primary["PAM50_mRNA_nature2012"] == "Luminal A").sum() == MINI["luma_2012_primary"]


def test_primary_ids_are_in_file_order(mini_release):
    r = load_release(mini_release)
    ids = r.primary_ids()
    assert ids == [i for i in r.clinical["sampleID"] if i[13:15] == "01"]


def test_checksums_cover_every_file_present(mini_release):
    r = load_release(mini_release)
    assert set(r.checksums) == set(RELEASE_FILES.values())
    assert all(len(v) == 64 for v in r.checksums.values())


def test_missing_rna_is_a_clear_error(mini_release):
    with pytest.raises(KeyError, match="no RNA file in this release"):
        load_release(mini_release).layer_ids("rna")


def test_unknown_layer_is_a_key_error(mini_release):
    with pytest.raises(KeyError):
        load_release(mini_release).layer_ids("methylation")


def test_rna_header_is_loaded_when_present(tmp_path):
    import gzip

    folder = make_mini_release(tmp_path / "with_rna")
    with gzip.open(folder / "rna_hiseq.tsv.gz", "wt") as f:
        f.write("sample\tTCGA-AA-0001-01\tTCGA-AA-0002-01\nTP53\t1\t2\n")
    r = load_release(folder)
    assert r.rna_ids == {"TCGA-AA-0001-01", "TCGA-AA-0002-01"}
    assert r.layer_ids("rna") == r.rna_ids
    assert "rna_hiseq.tsv.gz" in r.checksums


def test_missing_files_listed(tmp_path):
    with pytest.raises(FileNotFoundError, match="clinical.tsv"):
        load_release(tmp_path)


def test_partially_missing_files_listed(tmp_path):
    folder = make_mini_release(tmp_path / "partial")
    (folder / "survival.tsv").unlink()
    with pytest.raises(FileNotFoundError, match="survival.tsv"):
        load_release(folder)


@pytest.mark.realdata
def test_real_release_headline_numbers(release_dir):
    r = load_release(release_dir)
    assert len(r.primary_ids()) == 1101
    full = set(r.primary_ids()) & r.survival_ids & r.mutation_ids & r.copy_number_ids & r.protein_ids
    assert len(full) == 535
    if r.rna_ids is not None:  # fetch.py's default download includes the RNA file; --no-rna leaves it out
        assert len(full & r.rna_ids) == 535


def test_release_error_is_not_a_file_not_found():
    assert not issubclass(ReleaseError, FileNotFoundError)


def test_empty_clinical_file_is_a_release_error_naming_it(tmp_path):
    folder = make_mini_release(tmp_path / "empty")
    (folder / "clinical.tsv").write_text("")
    with pytest.raises(ReleaseError, match="clinical.tsv"):
        load_release(folder)


@pytest.mark.parametrize("name", ["mutation_gene_level.tsv.gz", "copy_number_gistic.tsv.gz", "protein_rppa.tsv.gz"])
def test_junk_gz_is_a_release_error_naming_it(tmp_path, name):
    folder = make_mini_release(tmp_path / "junk")
    (folder / name).write_bytes(b"this is not gzip \x00\xff")
    with pytest.raises(ReleaseError, match=name):
        load_release(folder)


def test_junk_rna_file_is_a_release_error_naming_it(tmp_path):
    folder = make_mini_release(tmp_path / "junk_rna")
    (folder / "rna_hiseq.tsv.gz").write_bytes(b"junk")
    with pytest.raises(ReleaseError, match="rna_hiseq.tsv.gz"):
        load_release(folder)


def test_survival_file_without_sample_column_is_a_release_error(tmp_path):
    folder = make_mini_release(tmp_path / "nosample")
    (folder / "survival.tsv").write_text("a\tb\n1\t2\n")
    with pytest.raises(ReleaseError, match="survival.tsv"):
        load_release(folder)


def test_clinical_without_sample_id_is_a_release_error(tmp_path):
    folder = make_mini_release(tmp_path / "noid")
    (folder / "clinical.tsv").write_text("gender\nFEMALE\n")
    with pytest.raises(ReleaseError, match="clinical.tsv.*sampleID"):
        load_release(folder)


def test_clinical_without_subtype_column_still_loads(tmp_path):
    import pandas as pd

    folder = make_mini_release(tmp_path / "nosubtype")
    clinical = pd.read_csv(folder / "clinical.tsv", sep="\t").drop(columns=["PAM50Call_RNAseq"])
    clinical.to_csv(folder / "clinical.tsv", sep="\t", index=False)
    assert len(load_release(folder).primary_ids()) == 10
