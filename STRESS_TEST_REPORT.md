# Stress Test Report: zotero-chunk-rag

**Date**: 2026-02-14 23:29
**Corpus**: 10 papers from live Zotero library

## Executive Summary

- **Total tests**: 296
- **Passed**: 269 (91%)
- **Failed**: 27
- **Major failures**: 3

> **VERDICT**: This tool is NOT reliable for production research use.
> A researcher depending on this tool WILL miss important results.

## Performance

| Operation | Time |
|-----------|------|
| Total indexing | 369.1s |

## Extraction Quality per Paper

| Paper | Pages | Sections | Tables | Figures | Grade | Issues |
|-------|-------|----------|--------|---------|-------|--------|
| active-inference-tutorial | 60 | 16 | 8 | 18 | B | 9 unknown sections; no abstract detected |
| huang-emd-1998 | 96 | 28 | 2 | 84 | D | 21 unknown sections; no abstract detected |
| hallett-tms-primer | 13 | 25 | 1 | 8 | A | 22 unknown sections; no abstract detected |
| laird-fick-polyps | 7 | 20 | 5 | 3 | A | 7 unknown sections |
| helm-coregulation | 10 | 11 | 2 | 2 | A | 4 unknown sections; no abstract detected |
| roland-emg-filter | 24 | 23 | 9 | 17 | C | 2 unknown sections |
| friston-life | 12 | 6 | 1 | 5 | A | 3 unknown sections; no abstract detected |
| yang-ppv-meta | 13 | 18 | 4 | 6 | C | 5 unknown sections |
| fortune-impedance | 11 | 10 | 7 | 7 | B | 3 unknown sections; no abstract detected |
| reyes-lf-hrv | 11 | 12 | 5 | 2 | A | 8 unknown sections |

## Failures (Detailed)

### ! [MINOR] section-detection — active-inference-tutorial

Expected section 'discussion' — MISSING. Got: ['appendix', 'conclusion', 'introduction', 'preamble', 'references', 'unknown']

### ! [MINOR] table-content-quality — active-inference-tutorial/table-3

Table 3: 46/117 cells non-empty (39%). Caption: 'Table 2 Matrix formulation of equations used for inference.'

### ! [MINOR] table-content-quality — active-inference-tutorial/table-4

Table 4: 38/84 cells non-empty (45%). Caption: 'Table 2 (continued).'

### ! [MINOR] orphan-tables — active-inference-tutorial

1 table(s) extracted without a real caption. Unmatched caption numbers: none

### ! [MINOR] abstract-detection — active-inference-tutorial

Abstract NOT detected

### !!! [MAJOR] completeness-grade — huang-emd-1998

Grade: D | Figs: 84 found / 83 captioned / 0 missing | Tables: 2 found / 0 captioned / 0 missing

### ! [MINOR] orphan-tables — huang-emd-1998

2 table(s) extracted without a real caption. Unmatched caption numbers: none

### !!! [MAJOR] unmatched-captions — huang-emd-1998

Caption numbers found on pages but not matched to any extracted object: figures=['6'], tables=none

### ! [MINOR] abstract-detection — huang-emd-1998

Abstract NOT detected

### ! [MINOR] chunk-count-sanity — huang-emd-1998

185 chunks for 96 pages (expected >= 192)

### ! [MINOR] section-detection — hallett-tms-primer

Expected section 'introduction' — MISSING. Got: ['appendix', 'conclusion', 'preamble', 'references', 'unknown']

### ! [MINOR] abstract-detection — hallett-tms-primer

Abstract NOT detected

### ! [MINOR] section-detection — laird-fick-polyps

Expected section 'introduction' — MISSING. Got: ['abstract', 'background', 'conclusion', 'discussion', 'methods', 'preamble', 'references', 'results', 'unknown']

### ! [MINOR] section-detection — helm-coregulation

Expected section 'introduction' — MISSING. Got: ['conclusion', 'discussion', 'methods', 'preamble', 'references', 'results', 'unknown']

### ! [MINOR] abstract-detection — helm-coregulation

Abstract NOT detected

### ! [MINOR] table-content-quality — roland-emg-filter/table-0

Table 0: 33/138 cells non-empty (24%). Caption: 'Uncaptioned table on page 5'

### ! [MINOR] table-content-quality — roland-emg-filter/table-3

Table 3: 10/24 cells non-empty (42%). Caption: 'Table 3. Poles of comb filters with quantized coefficients.'

### ! [MINOR] table-content-quality — roland-emg-filter/table-7

Table 7: 20/55 cells non-empty (36%). Caption: 'Table 7. Effect of reducing sampling and clock frequency on '

### ! [MINOR] completeness-grade — roland-emg-filter

Grade: C | Figs: 17 found / 17 captioned / 0 missing | Tables: 9 found / 7 captioned / 0 missing

### ! [MINOR] orphan-tables — roland-emg-filter

2 table(s) extracted without a real caption. Unmatched caption numbers: none

### ! [MINOR] abstract-detection — friston-life

Abstract NOT detected

### ! [MINOR] completeness-grade — yang-ppv-meta

Grade: C | Figs: 6 found / 6 captioned / 0 missing | Tables: 4 found / 3 captioned / 0 missing

### ! [MINOR] orphan-tables — yang-ppv-meta

1 table(s) extracted without a real caption. Unmatched caption numbers: none

### ! [MINOR] orphan-tables — fortune-impedance

1 table(s) extracted without a real caption. Unmatched caption numbers: none

### ! [MINOR] abstract-detection — fortune-impedance

Abstract NOT detected

### !!! [MAJOR] table-dimensions-sanity — fortune-impedance

1 tables are 1x1 (degenerate)

### ! [MINOR] section-detection — reyes-lf-hrv

Expected section 'introduction' — MISSING. Got: ['abstract', 'conclusion', 'methods', 'references', 'unknown']

## Passes

| Test | Paper | Detail |
|------|-------|--------|
| section-detection | active-inference-tutorial | Expected section 'introduction' — FOUND |
| section-detection | active-inference-tutorial | Expected section 'conclusion' — FOUND |
| table-extraction | active-inference-tutorial | Expected tables — found 8 |
| table-content-quality | active-inference-tutorial/table-0 | Table 0: 16/24 cells non-empty (67%). Caption: 'Uncaptioned table on page 1' |
| table-content-quality | active-inference-tutorial/table-1 | Table 1: 22/24 cells non-empty (92%). Caption: 'Table 1 Model variables.' |
| table-content-quality | active-inference-tutorial/table-2 | Table 2: 9/9 cells non-empty (100%). Caption: 'Table 1 (continued).' |
| table-content-quality | active-inference-tutorial/table-5 | Table 5: 10/12 cells non-empty (83%). Caption: 'Table 2 (continued).' |
| table-content-quality | active-inference-tutorial/table-6 | Table 6: 56/56 cells non-empty (100%). Caption: 'Table 3 Output fields for spm_M |
| table-content-quality | active-inference-tutorial/table-7 | Table 7: 16/16 cells non-empty (100%). Caption: 'Table 3 (continued).' |
| figure-extraction | active-inference-tutorial | Expected figures — found 18 |
| figure-caption-rate | active-inference-tutorial | 18/18 figures have captions (100%) |
| completeness-grade | active-inference-tutorial | Grade: B / Figs: 18 found / 17 captioned / 0 missing / Tables: 8 found / 3 capti |
| content-readability | active-inference-tutorial | 0 tables with readability issues |
| table-dimensions-sanity | active-inference-tutorial | 0 tables are 1x1 (degenerate) |
| caption-encoding-quality | active-inference-tutorial | 0 captions with encoding artifacts |
| caption-number-continuity | active-inference-tutorial | Figure gaps: none, Table gaps: none |
| duplicate-captions | active-inference-tutorial | 0 duplicate caption(s) found |
| chunk-count-sanity | active-inference-tutorial | 337 chunks for 60 pages (expected >= 120) |
| figure-images-saved | active-inference-tutorial | 18/18 figure images saved to disk |
| section-detection | huang-emd-1998 | Expected section 'introduction' — FOUND |
| section-detection | huang-emd-1998 | Expected section 'conclusion' — FOUND |
| figure-extraction | huang-emd-1998 | Expected figures — found 84 |
| figure-caption-rate | huang-emd-1998 | 84/84 figures have captions (100%) |
| content-readability | huang-emd-1998 | 0 tables with readability issues |
| table-dimensions-sanity | huang-emd-1998 | 0 tables are 1x1 (degenerate) |
| caption-encoding-quality | huang-emd-1998 | 0 captions with encoding artifacts |
| caption-number-continuity | huang-emd-1998 | Figure gaps: none, Table gaps: none |
| duplicate-captions | huang-emd-1998 | 0 duplicate caption(s) found |
| figure-images-saved | huang-emd-1998 | 84/84 figure images saved to disk |
| table-extraction | hallett-tms-primer | Expected tables — found 1 |
| table-content-quality | hallett-tms-primer/table-0 | Table 0: 11/12 cells non-empty (92%). Caption: 'Table 1. Summary of Noninvasive  |
| figure-extraction | hallett-tms-primer | Expected figures — found 8 |
| figure-caption-rate | hallett-tms-primer | 8/8 figures have captions (100%) |
| completeness-grade | hallett-tms-primer | Grade: A / Figs: 8 found / 8 captioned / 0 missing / Tables: 1 found / 1 caption |
| content-readability | hallett-tms-primer | 0 tables with readability issues |
| table-dimensions-sanity | hallett-tms-primer | 0 tables are 1x1 (degenerate) |
| caption-encoding-quality | hallett-tms-primer | 0 captions with encoding artifacts |
| caption-number-continuity | hallett-tms-primer | Figure gaps: none, Table gaps: none |
| duplicate-captions | hallett-tms-primer | 0 duplicate caption(s) found |
| chunk-count-sanity | hallett-tms-primer | 71 chunks for 13 pages (expected >= 26) |
| figure-images-saved | hallett-tms-primer | 8/8 figure images saved to disk |
| section-detection | laird-fick-polyps | Expected section 'methods' — FOUND |
| section-detection | laird-fick-polyps | Expected section 'results' — FOUND |
| section-detection | laird-fick-polyps | Expected section 'discussion' — FOUND |
| table-extraction | laird-fick-polyps | Expected tables — found 5 |
| table-content-quality | laird-fick-polyps/table-0 | Table 0: 32/35 cells non-empty (91%). Caption: 'Table 1 Distribution of Sex by A |
| table-content-quality | laird-fick-polyps/table-1 | Table 1: 80/85 cells non-empty (94%). Caption: 'Table 2 Distribution of Sex by H |
| table-content-quality | laird-fick-polyps/table-2 | Table 2: 25/30 cells non-empty (83%). Caption: 'Table 3 Prevalence of sessile se |
| table-content-quality | laird-fick-polyps/table-3 | Table 3: 66/84 cells non-empty (79%). Caption: 'Table 4 Odds ratios and 95 % con |
| table-content-quality | laird-fick-polyps/table-4 | Table 4: 65/72 cells non-empty (90%). Caption: 'Table 5 Distribution of polyps b |
| completeness-grade | laird-fick-polyps | Grade: A / Figs: 3 found / 3 captioned / 0 missing / Tables: 5 found / 5 caption |
| abstract-detection | laird-fick-polyps | Abstract detected |
| content-readability | laird-fick-polyps | 0 tables with readability issues |
| table-dimensions-sanity | laird-fick-polyps | 0 tables are 1x1 (degenerate) |
| caption-encoding-quality | laird-fick-polyps | 0 captions with encoding artifacts |
| caption-number-continuity | laird-fick-polyps | Figure gaps: none, Table gaps: none |
| duplicate-captions | laird-fick-polyps | 0 duplicate caption(s) found |
| chunk-count-sanity | laird-fick-polyps | 25 chunks for 7 pages (expected >= 14) |
| section-detection | helm-coregulation | Expected section 'methods' — FOUND |
| section-detection | helm-coregulation | Expected section 'results' — FOUND |
| section-detection | helm-coregulation | Expected section 'discussion' — FOUND |
| table-extraction | helm-coregulation | Expected tables — found 2 |
| table-content-quality | helm-coregulation/table-0 | Table 0: 41/48 cells non-empty (85%). Caption: 'Table 1 Comparisons of Model Fit |
| table-content-quality | helm-coregulation/table-1 | Table 1: 13/18 cells non-empty (72%). Caption: 'Table 2 Coefficients From Best-F |
| figure-extraction | helm-coregulation | Expected figures — found 2 |
| figure-caption-rate | helm-coregulation | 2/2 figures have captions (100%) |
| completeness-grade | helm-coregulation | Grade: A / Figs: 2 found / 2 captioned / 0 missing / Tables: 2 found / 2 caption |
| content-readability | helm-coregulation | 0 tables with readability issues |
| table-dimensions-sanity | helm-coregulation | 0 tables are 1x1 (degenerate) |
| caption-encoding-quality | helm-coregulation | 0 captions with encoding artifacts |
| caption-number-continuity | helm-coregulation | Figure gaps: none, Table gaps: none |
| duplicate-captions | helm-coregulation | 0 duplicate caption(s) found |
| chunk-count-sanity | helm-coregulation | 55 chunks for 10 pages (expected >= 20) |
| figure-images-saved | helm-coregulation | 2/2 figure images saved to disk |
| section-detection | roland-emg-filter | Expected section 'introduction' — FOUND |
| section-detection | roland-emg-filter | Expected section 'results' — FOUND |
| section-detection | roland-emg-filter | Expected section 'conclusion' — FOUND |
| table-extraction | roland-emg-filter | Expected tables — found 9 |
| table-content-quality | roland-emg-filter/table-1 | Table 1: 81/81 cells non-empty (100%). Caption: 'Table 1. Floating-point comb fi |
| table-content-quality | roland-emg-filter/table-2 | Table 2: 27/48 cells non-empty (56%). Caption: 'Table 2. Floating-point highpass |
| table-content-quality | roland-emg-filter/table-4 | Table 4: 27/30 cells non-empty (90%). Caption: 'Table 4. Poles of highpass filte |
| table-content-quality | roland-emg-filter/table-5 | Table 5: 9/12 cells non-empty (75%). Caption: 'Table 5. Runtime per sample of fi |
| table-content-quality | roland-emg-filter/table-6 | Table 6: 10/10 cells non-empty (100%). Caption: 'Table 6. Comparison of runtime  |
| table-content-quality | roland-emg-filter/table-8 | Table 8: 26/26 cells non-empty (100%). Caption: 'Uncaptioned table on page 22' |
| figure-extraction | roland-emg-filter | Expected figures — found 17 |
| figure-caption-rate | roland-emg-filter | 17/17 figures have captions (100%) |
| abstract-detection | roland-emg-filter | Abstract detected |
| content-readability | roland-emg-filter | 0 tables with readability issues |
| table-dimensions-sanity | roland-emg-filter | 0 tables are 1x1 (degenerate) |
| caption-encoding-quality | roland-emg-filter | 0 captions with encoding artifacts |
| caption-number-continuity | roland-emg-filter | Figure gaps: none, Table gaps: none |
| duplicate-captions | roland-emg-filter | 0 duplicate caption(s) found |
| chunk-count-sanity | roland-emg-filter | 73 chunks for 24 pages (expected >= 48) |
| figure-images-saved | roland-emg-filter | 17/17 figure images saved to disk |
| section-detection | friston-life | Expected section 'introduction' — FOUND |
| figure-extraction | friston-life | Expected figures — found 5 |
| figure-caption-rate | friston-life | 5/5 figures have captions (100%) |
| completeness-grade | friston-life | Grade: A / Figs: 5 found / 5 captioned / 0 missing / Tables: 1 found / 1 caption |
| content-readability | friston-life | 0 tables with readability issues |
| table-dimensions-sanity | friston-life | 0 tables are 1x1 (degenerate) |
| caption-encoding-quality | friston-life | 0 captions with encoding artifacts |
| caption-number-continuity | friston-life | Figure gaps: none, Table gaps: none |
| duplicate-captions | friston-life | 0 duplicate caption(s) found |
| chunk-count-sanity | friston-life | 60 chunks for 12 pages (expected >= 24) |
| figure-images-saved | friston-life | 5/5 figure images saved to disk |
| section-detection | yang-ppv-meta | Expected section 'introduction' — FOUND |
| section-detection | yang-ppv-meta | Expected section 'methods' — FOUND |
| section-detection | yang-ppv-meta | Expected section 'results' — FOUND |
| section-detection | yang-ppv-meta | Expected section 'discussion' — FOUND |
| table-extraction | yang-ppv-meta | Expected tables — found 4 |
| table-content-quality | yang-ppv-meta/table-0 | Table 0: 154/154 cells non-empty (100%). Caption: 'Table 1 Selected spectrum cha |
| table-content-quality | yang-ppv-meta/table-1 | Table 1: 298/338 cells non-empty (88%). Caption: 'Table 2 Selected methodologica |
| table-content-quality | yang-ppv-meta/table-2 | Table 2: 255/385 cells non-empty (66%). Caption: 'Table 3 Diagnostic performance |
| table-content-quality | yang-ppv-meta/table-3 | Table 3: 2/2 cells non-empty (100%). Caption: 'Uncaptioned table on page 7' |
| figure-extraction | yang-ppv-meta | Expected figures — found 6 |
| figure-caption-rate | yang-ppv-meta | 6/6 figures have captions (100%) |
| abstract-detection | yang-ppv-meta | Abstract detected |
| content-readability | yang-ppv-meta | 0 tables with readability issues |
| table-dimensions-sanity | yang-ppv-meta | 0 tables are 1x1 (degenerate) |
| caption-encoding-quality | yang-ppv-meta | 0 captions with encoding artifacts |
| caption-number-continuity | yang-ppv-meta | Figure gaps: none, Table gaps: none |
| duplicate-captions | yang-ppv-meta | 0 duplicate caption(s) found |
| chunk-count-sanity | yang-ppv-meta | 49 chunks for 13 pages (expected >= 26) |
| figure-images-saved | yang-ppv-meta | 6/6 figure images saved to disk |
| section-detection | fortune-impedance | Expected section 'introduction' — FOUND |
| section-detection | fortune-impedance | Expected section 'methods' — FOUND |
| section-detection | fortune-impedance | Expected section 'results' — FOUND |
| table-extraction | fortune-impedance | Expected tables — found 7 |
| table-content-quality | fortune-impedance/table-0 | Table 0: 10/15 cells non-empty (67%). Caption: 'Uncaptioned table on page 1' |
| table-content-quality | fortune-impedance/table-1 | Table 1: 14/16 cells non-empty (88%). Caption: 'Table 1 Component values used fo |
| table-content-quality | fortune-impedance/table-2 | Table 2: 29/35 cells non-empty (83%). Caption: 'Table 3 Error between the custom |
| table-content-quality | fortune-impedance/table-3 | Table 3: 60/60 cells non-empty (100%). Caption: 'Table 2 Error between the custo |
| table-content-quality | fortune-impedance/table-4 | Table 4: 263/287 cells non-empty (92%). Caption: 'Table 4 Electrode–skin impedan |
| table-content-quality | fortune-impedance/table-5 | Table 5: 50/78 cells non-empty (64%). Caption: 'Table 5 Mean electrode–skin impe |
| table-content-quality | fortune-impedance/table-6 | Table 6: 1/1 cells non-empty (100%). Caption: 'Table 6 Mean and standard deviati |
| figure-extraction | fortune-impedance | Expected figures — found 7 |
| figure-caption-rate | fortune-impedance | 7/7 figures have captions (100%) |
| completeness-grade | fortune-impedance | Grade: B / Figs: 7 found / 7 captioned / 0 missing / Tables: 7 found / 6 caption |
| content-readability | fortune-impedance | 0 tables with readability issues |
| caption-encoding-quality | fortune-impedance | 0 captions with encoding artifacts |
| caption-number-continuity | fortune-impedance | Figure gaps: none, Table gaps: none |
| duplicate-captions | fortune-impedance | 0 duplicate caption(s) found |
| chunk-count-sanity | fortune-impedance | 40 chunks for 11 pages (expected >= 22) |
| figure-images-saved | fortune-impedance | 7/7 figure images saved to disk |
| section-detection | reyes-lf-hrv | Expected section 'conclusion' — FOUND |
| table-extraction | reyes-lf-hrv | Expected tables — found 5 |
| table-content-quality | reyes-lf-hrv/table-0 | Table 0: 52/72 cells non-empty (72%). Caption: 'Table 1. Means and Standard Devi |
| table-content-quality | reyes-lf-hrv/table-1 | Table 1: 40/72 cells non-empty (56%). Caption: 'Table 2. Means and Standard Devi |
| table-content-quality | reyes-lf-hrv/table-2 | Table 2: 58/70 cells non-empty (83%). Caption: 'Table 3. Correlations of HRV Par |
| table-content-quality | reyes-lf-hrv/table-3 | Table 3: 58/70 cells non-empty (83%). Caption: 'Table 4. Correlations of HRV Par |
| table-content-quality | reyes-lf-hrv/table-4 | Table 4: 90/90 cells non-empty (100%). Caption: 'Table 5. Hypothetical Database  |
| figure-extraction | reyes-lf-hrv | Expected figures — found 2 |
| figure-caption-rate | reyes-lf-hrv | 2/2 figures have captions (100%) |
| completeness-grade | reyes-lf-hrv | Grade: A / Figs: 2 found / 2 captioned / 0 missing / Tables: 5 found / 5 caption |
| abstract-detection | reyes-lf-hrv | Abstract detected |
| content-readability | reyes-lf-hrv | 0 tables with readability issues |
| table-dimensions-sanity | reyes-lf-hrv | 0 tables are 1x1 (degenerate) |
| caption-encoding-quality | reyes-lf-hrv | 0 captions with encoding artifacts |
| caption-number-continuity | reyes-lf-hrv | Figure gaps: none, Table gaps: none |
| duplicate-captions | reyes-lf-hrv | 0 duplicate caption(s) found |
| chunk-count-sanity | reyes-lf-hrv | 66 chunks for 11 pages (expected >= 22) |
| figure-images-saved | reyes-lf-hrv | 2/2 figure images saved to disk |
| semantic-search-recall | active-inference-tutorial | Query: 'active inference free energy' — found at rank 1/10 (score 0.606) |
| semantic-search-ranking | active-inference-tutorial | Ranked 1/10 for its own core content query |
| semantic-search-recall | huang-emd-1998 | Query: 'empirical mode decomposition Hilbert spectrum' — found at rank 1/10 (sco |
| semantic-search-ranking | huang-emd-1998 | Ranked 1/10 for its own core content query |
| semantic-search-recall | hallett-tms-primer | Query: 'transcranial magnetic stimulation motor cortex' — found at rank 1/10 (sc |
| semantic-search-ranking | hallett-tms-primer | Ranked 1/10 for its own core content query |
| semantic-search-recall | laird-fick-polyps | Query: 'colonic polyp histopathology colonoscopy' — found at rank 1/10 (score 0. |
| semantic-search-ranking | laird-fick-polyps | Ranked 1/10 for its own core content query |
| semantic-search-recall | helm-coregulation | Query: 'respiratory sinus arrhythmia coregulation romantic' — found at rank 1/10 |
| semantic-search-ranking | helm-coregulation | Ranked 1/10 for its own core content query |
| semantic-search-recall | roland-emg-filter | Query: 'ultra-low-power digital filtering EMG' — found at rank 1/10 (score 0.761 |
| semantic-search-ranking | roland-emg-filter | Ranked 1/10 for its own core content query |
| semantic-search-recall | friston-life | Query: 'free energy principle self-organization' — found at rank 1/10 (score 0.6 |
| semantic-search-ranking | friston-life | Ranked 1/10 for its own core content query |
| semantic-search-recall | yang-ppv-meta | Query: 'pulse pressure variation fluid responsiveness' — found at rank 1/10 (sco |
| semantic-search-ranking | yang-ppv-meta | Ranked 1/10 for its own core content query |
| semantic-search-recall | fortune-impedance | Query: 'electrode skin impedance imbalance frequency' — found at rank 1/10 (scor |
| semantic-search-ranking | fortune-impedance | Ranked 1/10 for its own core content query |
| semantic-search-recall | reyes-lf-hrv | Query: 'low frequency heart rate variability sympathetic' — found at rank 1/10 ( |
| semantic-search-ranking | reyes-lf-hrv | Ranked 1/10 for its own core content query |
| table-search-recall | active-inference-tutorial | Query: 'algorithm update rules' — found 7 matching table(s), best score 0.217, c |
| table-markdown-quality | active-inference-tutorial | Table markdown has pipes and 48 lines. Preview: **Table 2 (continued).** /  / /  |
| table-search-recall | hallett-tms-primer | Query: 'stimulation parameters coil' — found 1 matching table(s), best score 0.3 |
| table-markdown-quality | hallett-tms-primer | Table markdown has pipes and 11 lines. Preview: **Table 1. Summary of Noninvasiv |
| table-search-recall | laird-fick-polyps | Query: 'polyp location demographics patient' — found 5 matching table(s), best s |
| table-markdown-quality | laird-fick-polyps | Table markdown has pipes and 59 lines. Preview: **Table 5 Distribution of polyps |
| table-search-recall | helm-coregulation | Query: 'correlation coefficient RSA' — found 1 matching table(s), best score 0.4 |
| table-markdown-quality | helm-coregulation | Table markdown has pipes and 60 lines. Preview: **Table 2 Coefficients From Best |
| table-search-recall | roland-emg-filter | Query: 'power consumption filter' — found 7 matching table(s), best score 0.424, |
| table-markdown-quality | roland-emg-filter | Table markdown has pipes and 23 lines. Preview: **Table 7. Effect of reducing sa |
| table-search-recall | yang-ppv-meta | Query: 'sensitivity specificity diagnostic' — found 3 matching table(s), best sc |
| table-markdown-quality | yang-ppv-meta | Table markdown has pipes and 42 lines. Preview: **Table 3 Diagnostic performance |
| table-search-recall | fortune-impedance | Query: 'impedance measurement electrode' — found 7 matching table(s), best score |
| table-markdown-quality | fortune-impedance | Table markdown has pipes and 4 lines. Preview: **Table 6 Mean and standard devia |
| table-search-recall | reyes-lf-hrv | Query: 'autonomic measures' — found 5 matching table(s), best score 0.422, capti |
| table-markdown-quality | reyes-lf-hrv | Table markdown has pipes and 67 lines. Preview: **Table 4. Correlations of HRV P |
| figure-search-recall | active-inference-tutorial | Query: 'generative model graphical' — found 10 matching figure(s), best score 0. |
| figure-search-recall | huang-emd-1998 | Query: 'intrinsic mode function' — found 8 matching figure(s), best score 0.501, |
| figure-search-recall | hallett-tms-primer | Query: 'magnetic field coil' — found 5 matching figure(s), best score 0.597, cap |
| figure-search-recall | helm-coregulation | Query: 'RSA dynamics time series' — found 2 matching figure(s), best score 0.415 |
| figure-search-recall | roland-emg-filter | Query: 'filter frequency response' — found 10 matching figure(s), best score 0.4 |
| figure-search-recall | friston-life | Query: 'Markov blanket' — found 3 matching figure(s), best score 0.553, caption: |
| figure-search-recall | yang-ppv-meta | Query: 'sensitivity specificity receiver operating' — found 1 matching figure(s) |
| figure-search-recall | fortune-impedance | Query: 'impedance frequency' — found 5 matching figure(s), best score 0.443, cap |
| figure-search-recall | reyes-lf-hrv | Query: 'heart rate variability' — found 1 matching figure(s), best score 0.421,  |
| author-filter | active-inference-tutorial | Filter author='smith' — target paper found (42 total results after filter) |
| author-filter | huang-emd-1998 | Filter author='huang' — target paper found (50 total results after filter) |
| author-filter | hallett-tms-primer | Filter author='hallett' — target paper found (50 total results after filter) |
| author-filter | laird-fick-polyps | Filter author='laird' — target paper found (31 total results after filter) |
| author-filter | helm-coregulation | Filter author='helm' — target paper found (19 total results after filter) |
| author-filter | roland-emg-filter | Filter author='roland' — target paper found (47 total results after filter) |
| author-filter | friston-life | Filter author='friston' — target paper found (42 total results after filter) |
| author-filter | yang-ppv-meta | Filter author='yang' — target paper found (33 total results after filter) |
| author-filter | fortune-impedance | Filter author='fortune' — target paper found (43 total results after filter) |
| author-filter | reyes-lf-hrv | Filter author='reyes' — target paper found (46 total results after filter) |
| year-filter-accuracy | all | Year filter >=2015: 0 papers from before 2015 leaked through (total results: 50) |
| context-expansion | active-inference-tutorial | Context expansion: before=2, after=2, full_context=7924 chars |
| context-adds-value | active-inference-tutorial | Full context (7924 chars) vs hit (1583 chars) |
| context-expansion | huang-emd-1998 | Context expansion: before=4, after=3, full_context=13576 chars |
| context-adds-value | huang-emd-1998 | Full context (13576 chars) vs hit (1591 chars) |
| context-expansion | hallett-tms-primer | Context expansion: before=0, after=3, full_context=6152 chars |
| context-adds-value | hallett-tms-primer | Full context (6152 chars) vs hit (1411 chars) |
| context-expansion | laird-fick-polyps | Context expansion: before=2, after=2, full_context=7703 chars |
| context-adds-value | laird-fick-polyps | Full context (7703 chars) vs hit (1576 chars) |
| context-expansion | helm-coregulation | Context expansion: before=0, after=2, full_context=4450 chars |
| context-adds-value | helm-coregulation | Full context (4450 chars) vs hit (1600 chars) |
| context-expansion | roland-emg-filter | Context expansion: before=4, after=2, full_context=10073 chars |
| context-adds-value | roland-emg-filter | Full context (10073 chars) vs hit (1503 chars) |
| context-expansion | friston-life | Context expansion: before=2, after=2, full_context=7897 chars |
| context-adds-value | friston-life | Full context (7897 chars) vs hit (1591 chars) |
| context-expansion | yang-ppv-meta | Context expansion: before=2, after=2, full_context=8007 chars |
| context-adds-value | yang-ppv-meta | Full context (8007 chars) vs hit (1600 chars) |
| context-expansion | fortune-impedance | Context expansion: before=2, after=3, full_context=9518 chars |
| context-adds-value | fortune-impedance | Full context (9518 chars) vs hit (1482 chars) |
| context-expansion | reyes-lf-hrv | Context expansion: before=0, after=2, full_context=4355 chars |
| context-adds-value | reyes-lf-hrv | Full context (4355 chars) vs hit (1361 chars) |
| topic-search-multi-paper | HRV papers | Topic search for HRV: found 2/2 expected papers in 2 total docs. Keys found: {'A |
| topic-search-engineering | impedance papers | Topic search for impedance: found 1/1 expected. Total docs: 2. Keys: {'VP3NJ74M' |
| ocr-text-extraction | active-inference-tutorial | OCR extracted 63342 chars from 3 image pages. OCR pages detected: 3 |
| ocr-page-detection | active-inference-tutorial | OCR page detection: 3/3 pages flagged as OCR |
| nonsense-query-no-crash | all | Nonsense query returned 5 results (top score: 0.265) |
| empty-rerank-no-crash | all | Reranker handles empty input gracefully |
| boundary-chunk-first | active-inference-tutorial | Adjacent chunks for first chunk: got 3 (expected >=1) |
| boundary-chunk-last | active-inference-tutorial | Adjacent chunks for last chunk (idx=336): got 3 |
| boundary-chunk-first | huang-emd-1998 | Adjacent chunks for first chunk: got 4 (expected >=1) |
| boundary-chunk-last | huang-emd-1998 | Adjacent chunks for last chunk (idx=184): got 3 |
| section-weight-effect | all | Default top-3 sections: ['methods', 'table', 'methods'], methods-boosted top-3:  |
| section-labels-valid | active-inference-tutorial | All 17 section labels are valid |
| section-coverage | active-inference-tutorial | Section spans cover 100% of document (first: 0, last: 371254, total: 371254) |
| section-labels-valid | huang-emd-1998 | All 29 section labels are valid |
| section-coverage | huang-emd-1998 | Section spans cover 100% of document (first: 0, last: 205332, total: 205332) |
| section-labels-valid | hallett-tms-primer | All 26 section labels are valid |
| section-coverage | hallett-tms-primer | Section spans cover 100% of document (first: 0, last: 79023, total: 79023) |
| section-labels-valid | laird-fick-polyps | All 21 section labels are valid |
| section-coverage | laird-fick-polyps | Section spans cover 100% of document (first: 0, last: 27023, total: 27023) |
| section-labels-valid | helm-coregulation | All 12 section labels are valid |
| section-coverage | helm-coregulation | Section spans cover 100% of document (first: 0, last: 60993, total: 60993) |
| section-labels-valid | roland-emg-filter | All 25 section labels are valid |
| section-coverage | roland-emg-filter | Section spans cover 100% of document (first: 0, last: 81643, total: 81643) |
| section-labels-valid | friston-life | All 7 section labels are valid |
| section-coverage | friston-life | Section spans cover 100% of document (first: 0, last: 65237, total: 65237) |
| section-labels-valid | yang-ppv-meta | All 19 section labels are valid |
| section-coverage | yang-ppv-meta | Section spans cover 100% of document (first: 0, last: 54080, total: 54080) |
| section-labels-valid | fortune-impedance | All 11 section labels are valid |
| section-coverage | fortune-impedance | Section spans cover 100% of document (first: 0, last: 43880, total: 43880) |
| section-labels-valid | reyes-lf-hrv | All 12 section labels are valid |
| section-coverage | reyes-lf-hrv | Section spans cover 100% of document (first: 0, last: 72358, total: 72358) |

## OCR Pathway Test

_(See OCR test results in the test output above)_
