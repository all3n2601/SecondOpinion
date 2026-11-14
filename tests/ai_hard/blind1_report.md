# Data coverage and subtype mix in TCGA breast cancer

*A fictional report written for testing. It describes TCGA-BRCA release A.*

TCGA's breast cancer collection remains a reference point for multi-omic studies, and this summary describes what release A actually contains. The release contains 1,247 samples from 1,101 patients: 1,101 primary tumors, 139 normal tissue samples and 7 metastases. RNA sequencing is close to complete, with 1,097 of the 1,101 primary tumors present in the expression file. Copy-number profiles cover 1,080 primary tumors, or 99% of the cohort. Protein coverage is thinner, with RPPA measurements for 747 primary tumors. Restricting the analysis to tumors with both mutation and copy-number data still leaves 785 primary tumors.

Luminal A is the most common RNA subtype, at 49.9% of primary tumors with a PAM50 call. Luminal B ranks second at 22.8%. Basal-like tumors form roughly one in six subtyped tumors and outnumber HER2-enriched tumors by about two to one. By the RNA-seq PAM50 call, 231 primary tumors are Luminal A. Under the 2012 consortium labels, Normal-like is the rarest group, at under 2% of labelled tumors.

The 257 primary tumors without an RNA subtype call were left out because their RNA quality was too low. Black and Hispanic patients together make up about a fifth of the cohort, so these subtype shares may not generalize.
