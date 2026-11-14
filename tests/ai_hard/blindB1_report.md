# Receptor status and RNA subtypes in TCGA breast cancer

*A fictional research report written for testing. It describes the TCGA-BRCA files of release A.*

## Results

Release A holds 1,247 samples from 1,101 patients: 1,101 primary tumors, 139 normal tissue samples and 7 metastases. All figures below are for primary tumors.

**Table 1.** PAM50 RNA subtype of primary tumors with an RNA-seq subtype call (n = 844).

| Group | n | % |
|---|---|---|
| Luminal A | 421 | 49.9 |
| Luminal B | 192 | 22.7 |
| Basal-like | 141 | 12.8 |
| HER2-enriched | 67 | 7.9 |
| Normal-like | 32 | 3.8 |

The RNA-seq calls agree well with the labels from the 2012 TCGA study: of the 508 tumors that carry both labels, 456 (89.8%) receive the same subtype. The largest single disagreement is a group of 31 tumors that the 2012 study placed in LumB and that RNA-seq calls LumA.

**Table 2.** Clinical receptor status of primary tumors. Percentages count positive tumors among those with a positive or negative result.

| Group | Positive n | Tested n | % positive |
|---|---|---|---|
| ER-positive | 808 | 1,046 | 77.2 |
| PR-positive | 699 | 1,043 | 67.0 |
| HER2-positive (IHC) | 164 | 728 | 22.5 |
| Triple-negative | 141 | 722 | 19.5 |

Protein levels follow the clinical calls. Mean ERALPHA protein (RPPA) is 2.18 in the 529 ER+ tumors with protein data against -0.87 in the 169 ER- tumors, a gap of about 3.1 units. At the DNA level, nearly all HER2 IHC-positive tumors (87 of 162 with copy-number data) carry an ERBB2 amplification.

Patients with TNBC benefited most from platinum chemotherapy, which supports platinum as the backbone of TNBC treatment.
