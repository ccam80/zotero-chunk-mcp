# Stress Test Report: zotero-chunk-rag

**Date**: 2026-02-22 22:36
**Corpus**: 10 papers from live Zotero library

## Executive Summary

- **Total tests**: 272
- **Passed**: 247 (91%)
- **Failed**: 25
- **Major failures**: 4

> **VERDICT**: This tool is NOT reliable for production research use.
> A researcher depending on this tool WILL miss important results.

## Performance

| Operation | Time |
|-----------|------|
| Total indexing | 1938.0s |

## Extraction Quality per Paper

| Paper | Pages | Sections | Tables | Figures | Grade | Issues |
|-------|-------|----------|--------|---------|-------|--------|
| active-inference-tutorial | 60 | 16 | 7 | 17 | B | 1 figs missing; 9 unknown sections; no abstract detected |
| huang-emd-1998 | 96 | 28 | 2 | 85 | A | 21 unknown sections; no abstract detected |
| hallett-tms-primer | 13 | 25 | 1 | 8 | A | 22 unknown sections; no abstract detected |
| laird-fick-polyps | 7 | 20 | 5 | 3 | A | 7 unknown sections |
| helm-coregulation | 10 | 11 | 2 | 2 | A | 4 unknown sections; no abstract detected |
| roland-emg-filter | 24 | 23 | 8 | 17 | A | 2 unknown sections |
| friston-life | 12 | 6 | 1 | 5 | A | 3 unknown sections; no abstract detected |
| yang-ppv-meta | 13 | 18 | 3 | 6 | A | 5 unknown sections |
| fortune-impedance | 11 | 10 | 6 | 7 | A | 3 unknown sections; no abstract detected |
| reyes-lf-hrv | 11 | 12 | 5 | 2 | A | 8 unknown sections |

## Failures (Detailed)

### ! [MINOR] section-detection — active-inference-tutorial

Expected section 'discussion' — MISSING. Got: ['appendix', 'conclusion', 'introduction', 'preamble', 'references', 'unknown']

### !!! [MAJOR] missing-figures — active-inference-tutorial

1 figure(s) have captions but no extracted image. Captions found: 18, figures extracted: 17

### !!! [MAJOR] unmatched-captions — active-inference-tutorial

Caption numbers found on pages but not matched to any extracted object: figures=['A.1'], tables=['A.1', 'A.2', 'A.3']

### ! [MINOR] abstract-detection — active-inference-tutorial

Abstract NOT detected

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

### ! [MINOR] table-content-quality — laird-fick-polyps/table-1

Table 1: 3/10 cells non-empty (30%). Caption: 'Table 2 Distribution of Sex by Histology among 13,881 patien'

### ! [MINOR] table-content-quality — laird-fick-polyps/table-2

Table 2: 3/9 cells non-empty (33%). Caption: 'Table 3 Prevalence of sessile serrated adenomas, 2007-2012 i'

### ! [MINOR] table-content-quality — laird-fick-polyps/table-3

Table 3: 4/8 cells non-empty (50%). Caption: 'Table 4 Odds ratios and 95 % confidence intervals for associ'

### ! [MINOR] section-detection — helm-coregulation

Expected section 'introduction' — MISSING. Got: ['conclusion', 'discussion', 'methods', 'preamble', 'references', 'results', 'unknown']

### ! [MINOR] abstract-detection — helm-coregulation

Abstract NOT detected

### ! [MINOR] table-content-quality — roland-emg-filter/table-2

Table 2: 4/9 cells non-empty (44%). Caption: 'Table 3. Poles of comb filters with quantized coefficients.'

### ! [MINOR] table-content-quality — roland-emg-filter/table-3

Table 3: 5/11 cells non-empty (45%). Caption: 'Table 4. Poles of highpass filters with quantized coefficien'

### ! [MINOR] table-content-quality — roland-emg-filter/table-4

Table 4: 1/2 cells non-empty (50%). Caption: 'Table 5. Runtime per sample of filters in C implementation a'

### !!! [MAJOR] table-dimensions-sanity — roland-emg-filter

1 tables are 1x1 (degenerate)

### ! [MINOR] abstract-detection — friston-life

Abstract NOT detected

### ! [MINOR] table-content-quality — yang-ppv-meta/table-0

Table 0: 3/10 cells non-empty (30%). Caption: 'Table 1 Selected spectrum characteristics of included studie'

### ! [MINOR] table-content-quality — yang-ppv-meta/table-1

Table 1: 7/21 cells non-empty (33%). Caption: 'Table 2 Selected methodological characteristics of included '

### ! [MINOR] table-content-quality — fortune-impedance/table-1

Table 1: 4/10 cells non-empty (40%). Caption: 'Table 3 Error between the custom impedance analyser (CIA) an'

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
| table-extraction | active-inference-tutorial | Expected tables — found 7 |
| figure-extraction | active-inference-tutorial | Expected figures — found 17 |
| figure-caption-rate | active-inference-tutorial | 17/17 figures have captions (100%) |
| completeness-grade | active-inference-tutorial | Grade: B / Figs: 17 found / 18 captioned / 1 missing / Tables: 7 found / 6 capti |
| content-readability | active-inference-tutorial | 0 tables with readability issues |
| table-dimensions-sanity | active-inference-tutorial | 0 tables are 1x1 (degenerate) |
| caption-encoding-quality | active-inference-tutorial | 0 captions with encoding artifacts |
| caption-number-continuity | active-inference-tutorial | Figure gaps: none, Table gaps: none |
| duplicate-captions | active-inference-tutorial | 0 duplicate caption(s) found |
| chunk-count-sanity | active-inference-tutorial | 337 chunks for 60 pages (expected >= 120) |
| figure-images-saved | active-inference-tutorial | 17/17 figure images saved to disk |
| section-detection | huang-emd-1998 | Expected section 'introduction' — FOUND |
| section-detection | huang-emd-1998 | Expected section 'conclusion' — FOUND |
| figure-extraction | huang-emd-1998 | Expected figures — found 85 |
| figure-caption-rate | huang-emd-1998 | 85/85 figures have captions (100%) |
| completeness-grade | huang-emd-1998 | Grade: A / Figs: 85 found / 83 captioned / 0 missing / Tables: 2 found / 0 capti |
| content-readability | huang-emd-1998 | 0 tables with readability issues |
| table-dimensions-sanity | huang-emd-1998 | 0 tables are 1x1 (degenerate) |
| caption-encoding-quality | huang-emd-1998 | 0 captions with encoding artifacts |
| caption-number-continuity | huang-emd-1998 | Figure gaps: none, Table gaps: none |
| duplicate-captions | huang-emd-1998 | 0 duplicate caption(s) found |
| figure-images-saved | huang-emd-1998 | 85/85 figure images saved to disk |
| table-extraction | hallett-tms-primer | Expected tables — found 1 |
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
| table-extraction | roland-emg-filter | Expected tables — found 8 |
| table-content-quality | roland-emg-filter/table-0 | Table 0: 6/8 cells non-empty (75%). Caption: 'Table 1. Floating-point comb filte |
| table-content-quality | roland-emg-filter/table-5 | Table 5: 4/4 cells non-empty (100%). Caption: 'Table 7. Effect of reducing sampl |
| table-content-quality | roland-emg-filter/table-7 | Table 7: 1/1 cells non-empty (100%). Caption: 'Table 6. Comparison of runtime pe |
| figure-extraction | roland-emg-filter | Expected figures — found 17 |
| figure-caption-rate | roland-emg-filter | 17/17 figures have captions (100%) |
| completeness-grade | roland-emg-filter | Grade: A / Figs: 17 found / 17 captioned / 0 missing / Tables: 8 found / 7 capti |
| abstract-detection | roland-emg-filter | Abstract detected |
| content-readability | roland-emg-filter | 0 tables with readability issues |
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
| table-extraction | yang-ppv-meta | Expected tables — found 3 |
| table-content-quality | yang-ppv-meta/table-2 | Table 2: 9/17 cells non-empty (53%). Caption: 'Table 3 Diagnostic performance of |
| figure-extraction | yang-ppv-meta | Expected figures — found 6 |
| figure-caption-rate | yang-ppv-meta | 6/6 figures have captions (100%) |
| completeness-grade | yang-ppv-meta | Grade: A / Figs: 6 found / 6 captioned / 0 missing / Tables: 3 found / 3 caption |
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
| table-extraction | fortune-impedance | Expected tables — found 6 |
| table-content-quality | fortune-impedance/table-0 | Table 0: 7/7 cells non-empty (100%). Caption: 'Table 1 Component values used for |
| table-content-quality | fortune-impedance/table-4 | Table 4: 8/12 cells non-empty (67%). Caption: 'Table 5 Mean electrode–skin imped |
| table-content-quality | fortune-impedance/table-5 | Table 5: 1/1 cells non-empty (100%). Caption: 'Table 6 Mean and standard deviati |
| figure-extraction | fortune-impedance | Expected figures — found 7 |
| figure-caption-rate | fortune-impedance | 7/7 figures have captions (100%) |
| completeness-grade | fortune-impedance | Grade: A / Figs: 7 found / 7 captioned / 0 missing / Tables: 6 found / 6 caption |
| content-readability | fortune-impedance | 0 tables with readability issues |
| caption-encoding-quality | fortune-impedance | 0 captions with encoding artifacts |
| caption-number-continuity | fortune-impedance | Figure gaps: none, Table gaps: none |
| duplicate-captions | fortune-impedance | 0 duplicate caption(s) found |
| chunk-count-sanity | fortune-impedance | 40 chunks for 11 pages (expected >= 22) |
| figure-images-saved | fortune-impedance | 7/7 figure images saved to disk |
| section-detection | reyes-lf-hrv | Expected section 'conclusion' — FOUND |
| table-extraction | reyes-lf-hrv | Expected tables — found 5 |
| table-content-quality | reyes-lf-hrv/table-0 | Table 0: 6/11 cells non-empty (55%). Caption: 'Table 1. Means and Standard Devia |
| table-content-quality | reyes-lf-hrv/table-1 | Table 1: 5/8 cells non-empty (62%). Caption: 'Table 2. Means and Standard Deviat |
| table-content-quality | reyes-lf-hrv/table-2 | Table 2: 5/6 cells non-empty (83%). Caption: 'Table 4. Correlations of HRV Param |
| table-content-quality | reyes-lf-hrv/table-3 | Table 3: 5/6 cells non-empty (83%). Caption: 'Table 3. Correlations of HRV Param |
| table-content-quality | reyes-lf-hrv/table-4 | Table 4: 9/9 cells non-empty (100%). Caption: 'Table 5. Hypothetical Database Di |
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
| table-search-recall | active-inference-tutorial | Query: 'algorithm update rules' — found 6 matching table(s), best score 0.239, c |
| table-markdown-quality | active-inference-tutorial | Table markdown has pipes and 3 lines. Preview: **Table 1 (continued).** /  / / M |
| table-search-recall | hallett-tms-primer | Query: 'stimulation parameters coil' — found 1 matching table(s), best score 0.3 |
| table-markdown-quality | hallett-tms-primer | Table markdown has pipes and 3 lines. Preview: **Table 1. Summary of Noninvasive |
| table-search-recall | laird-fick-polyps | Query: 'polyp location demographics patient' — found 5 matching table(s), best s |
| table-markdown-quality | laird-fick-polyps | Table markdown has pipes and 3 lines. Preview: **Table 5 Distribution of polyps  |
| table-search-recall | helm-coregulation | Query: 'correlation coefficient RSA' — found 1 matching table(s), best score 0.3 |
| table-markdown-quality | helm-coregulation | Table markdown has pipes and 3 lines. Preview: **Table 2 Coefficients From Best- |
| table-search-recall | roland-emg-filter | Query: 'power consumption filter' — found 8 matching table(s), best score 0.429, |
| table-markdown-quality | roland-emg-filter | Table markdown has pipes and 4 lines. Preview: **Table 7. Effect of reducing sam |
| table-search-recall | yang-ppv-meta | Query: 'sensitivity specificity diagnostic' — found 2 matching table(s), best sc |
| table-markdown-quality | yang-ppv-meta | Table markdown has pipes and 4 lines. Preview: **Table 3 Diagnostic performance  |
| table-search-recall | fortune-impedance | Query: 'impedance measurement electrode' — found 6 matching table(s), best score |
| table-markdown-quality | fortune-impedance | Table markdown has pipes and 2 lines. Preview: **Table 6 Mean and standard devia |
| table-search-recall | reyes-lf-hrv | Query: 'autonomic measures' — found 5 matching table(s), best score 0.393, capti |
| table-markdown-quality | reyes-lf-hrv | Table markdown has pipes and 4 lines. Preview: **Table 4. Correlations of HRV Pa |
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
| author-filter | laird-fick-polyps | Filter author='laird' — target paper found (32 total results after filter) |
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
| context-expansion | roland-emg-filter | Context expansion: before=4, after=2, full_context=9858 chars |
| context-adds-value | roland-emg-filter | Full context (9858 chars) vs hit (1503 chars) |
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
| boundary-chunk-first | huang-emd-1998 | Adjacent chunks for first chunk: got 5 (expected >=1) |
| boundary-chunk-last | huang-emd-1998 | Adjacent chunks for last chunk (idx=184): got 3 |
| section-weight-effect | all | Default top-3 sections: ['table', 'methods', 'methods'], methods-boosted top-3:  |
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

## Ground Truth Comparison

| Paper | Table ID | Fuzzy Accuracy | Precision | Recall | Splits | Merges | Cell Diffs |
|-------|----------|----------------|-----------|--------|--------|--------|------------|
| laird-fick-polyps | 5SIZVS65_table_1 | 6.3% | 16.8% | 3.8% | 0 | 0 | 0 |
| laird-fick-polyps | 5SIZVS65_table_2 | 3.6% | 13.0% | 2.1% | 0 | 0 | 0 |
| laird-fick-polyps | 5SIZVS65_table_3 | 14.7% | 25.7% | 10.3% | 0 | 0 | 0 |
| laird-fick-polyps | 5SIZVS65_table_4 | 6.1% | 19.4% | 3.6% | 0 | 0 | 0 |
| laird-fick-polyps | 5SIZVS65_table_5 | 4.0% | 13.9% | 2.4% | 0 | 0 | 0 |
| helm-coregulation | 9GKLLJH9_table_1 | 1.9% | 4.0% | 1.2% | 0 | 0 | 0 |
| helm-coregulation | 9GKLLJH9_table_2 | 1.9% | 8.2% | 1.1% | 0 | 0 | 0 |
| reyes-lf-hrv | AQ3D94VC_table_1 | 10.9% | 23.6% | 7.1% | 0 | 0 | 0 |
| reyes-lf-hrv | AQ3D94VC_table_2 | 12.5% | 27.9% | 8.0% | 0 | 0 | 2 |
| reyes-lf-hrv | AQ3D94VC_table_3 | 11.8% | 39.1% | 6.9% | 1 | 0 | 3 |
| reyes-lf-hrv | AQ3D94VC_table_4 | 11.6% | 38.6% | 6.9% | 1 | 0 | 3 |
| reyes-lf-hrv | AQ3D94VC_table_5 | 14.5% | 47.0% | 8.5% | 0 | 0 | 8 |
| hallett-tms-primer | C626CYVT_table_1 | 13.1% | 39.3% | 7.9% | 0 | 0 | 0 |
| yang-ppv-meta | DPYRZTFI_table_1 | 2.3% | 15.3% | 1.2% | 0 | 0 | 1 |
| yang-ppv-meta | DPYRZTFI_table_2 | 3.7% | 23.1% | 2.0% | 0 | 0 | 2 |
| yang-ppv-meta | DPYRZTFI_table_3 | 5.0% | 26.7% | 2.7% | 0 | 0 | 4 |
| active-inference-tutorial | SCPXVBLY_table_1 | 3.7% | 4.6% | 3.1% | 0 | 0 | 0 |
| active-inference-tutorial | SCPXVBLY_table_1_p16 | 9.0% | 6.9% | 13.0% | 0 | 0 | 0 |
| active-inference-tutorial | SCPXVBLY_table_2 | 4.8% | 4.8% | 4.8% | 0 | 0 | 0 |
| active-inference-tutorial | SCPXVBLY_table_2_p19 | 6.3% | 5.1% | 8.1% | 0 | 0 | 0 |
| active-inference-tutorial | SCPXVBLY_table_2_p20 | 4.7% | 3.6% | 6.8% | 0 | 0 | 0 |
| active-inference-tutorial | SCPXVBLY_table_3 | 3.6% | 6.7% | 2.5% | 0 | 0 | 0 |
| active-inference-tutorial | SCPXVBLY_table_3_p31 | 9.3% | 10.9% | 8.2% | 0 | 0 | 0 |
| fortune-impedance | VP3NJ74M_table_1 | 17.5% | 26.2% | 13.1% | 0 | 1 | 0 |
| fortune-impedance | VP3NJ74M_table_2 | 3.2% | 9.6% | 1.9% | 0 | 0 | 0 |
| fortune-impedance | VP3NJ74M_table_3 | 8.2% | 21.6% | 5.0% | 0 | 0 | 0 |
| fortune-impedance | VP3NJ74M_table_4 | 1.3% | 12.3% | 0.7% | 0 | 0 | 0 |
| fortune-impedance | VP3NJ74M_table_5 | 10.2% | 10.2% | 10.2% | 0 | 0 | 0 |
| fortune-impedance | VP3NJ74M_table_6 | 0.5% | 5.3% | 0.3% | 0 | 0 | 0 |
| huang-emd-1998 | XIAINRVS_orphan_p1_t0 | 0.0% | 0.0% | 0.0% | 0 | 0 | 0 |
| huang-emd-1998 | XIAINRVS_orphan_p2_t1 | 0.0% | 0.0% | 0.0% | 0 | 0 | 0 |
| friston-life | YMWV46JA_table_1 | 33.8% | 26.0% | 48.3% | 0 | 0 | 0 |
| roland-emg-filter | Z9X4JVZ5_table_1 | 8.8% | 32.8% | 5.1% | 1 | 0 | 1 |
| roland-emg-filter | Z9X4JVZ5_table_2 | 0.4% | 4.3% | 0.2% | 0 | 0 | 0 |
| roland-emg-filter | Z9X4JVZ5_table_3 | 26.3% | 28.4% | 24.6% | 0 | 0 | 0 |
| roland-emg-filter | Z9X4JVZ5_table_4 | 11.5% | 17.6% | 8.5% | 0 | 0 | 0 |
| roland-emg-filter | Z9X4JVZ5_table_5 | 18.2% | 42.5% | 11.6% | 0 | 0 | 1 |
| roland-emg-filter | Z9X4JVZ5_table_6 | 3.4% | 20.5% | 1.9% | 0 | 0 | 0 |
| roland-emg-filter | Z9X4JVZ5_table_7 | 20.6% | 41.2% | 13.7% | 0 | 0 | 3 |

**Overall corpus fuzzy accuracy**: 8.4% (39 tables compared)


## Pipeline Depth Report

### Per-Method Win Rates

**Structure method wins** (how often each method's boundaries produce the best cell accuracy):

| Structure Method | Wins | Participated | Win Rate |
|-----------------|------|-------------|----------|
| pymupdf_lines | 19 | 117 | 16% |
| pymupdf_text | 10 | 117 | 9% |
| ruled_lines | 4 | 87 | 5% |
| single_point_hotspot | 3 | 114 | 3% |
| camelot_hybrid | 2 | 78 | 3% |
| header_anchor | 1 | 111 | 1% |
| global_cliff | 1 | 42 | 2% |

**Cell method wins** (how often each method is selected as best):

| Cell Method | Wins | Participated | Win Rate |
|------------|------|-------------|----------|
| rawdict | 29 | 377 | 8% |
| word_assignment | 10 | 377 | 3% |
| pdfminer | 1 | 377 | 0% |

### Combination Value

Comparison of best-single-method accuracy vs pipeline (consensus boundaries) accuracy:

- **Avg best-single-method accuracy**: 62.0%
- **Avg pipeline (consensus) accuracy**: 8.4%
- **Delta (positive = combination helps)**: -53.6%
- **Tables compared**: 39

### Per-Table Accuracy Chain

| Table ID | Best Single Method | Best Accuracy | Pipeline Accuracy | Delta |
|----------|-------------------|---------------|-------------------|-------|
| SCPXVBLY_table_1 | ruled_lines+rawdict | 37.5% | 3.7% | -33.8% |
| SCPXVBLY_table_1_p16 | pymupdf_lines+rawdict | 45.4% | 9.0% | -36.4% |
| SCPXVBLY_table_2 | ruled_lines+rawdict | 24.0% | 4.8% | -19.1% |
| SCPXVBLY_table_2_p19 | ruled_lines+rawdict | 17.5% | 6.3% | -11.2% |
| SCPXVBLY_table_2_p20 | ruled_lines+rawdict | 19.8% | 4.7% | -15.1% |
| SCPXVBLY_table_3 | pymupdf_lines+rawdict | 33.8% | 3.6% | -30.1% |
| SCPXVBLY_table_3_p31 | pymupdf_lines+rawdict | 43.9% | 9.3% | -34.5% |
| XIAINRVS_orphan_p1_t0 | single_point_hotspot+rawdict | 0.0% | 0.0% | +0.0% |
| XIAINRVS_orphan_p2_t1 | single_point_hotspot+rawdict | 0.0% | 0.0% | +0.0% |
| C626CYVT_table_1 | pymupdf_lines+word_assignment | 87.1% | 13.1% | -74.0% |
| 5SIZVS65_table_1 | pymupdf_lines+word_assignment | 94.7% | 6.3% | -88.4% |
| 5SIZVS65_table_2 | pymupdf_lines+word_assignment | 89.6% | 3.6% | -86.0% |
| 5SIZVS65_table_3 | pymupdf_text+word_assignment | 57.2% | 14.7% | -42.5% |
| 5SIZVS65_table_4 | pymupdf_text+word_assignment | 92.2% | 6.1% | -86.1% |
| 5SIZVS65_table_5 | pymupdf_lines+rawdict | 93.3% | 4.0% | -89.2% |
| 9GKLLJH9_table_1 | pymupdf_text+word_assignment | 71.8% | 1.9% | -69.9% |
| 9GKLLJH9_table_2 | pymupdf_text+word_assignment | 58.6% | 1.9% | -56.7% |
| Z9X4JVZ5_table_1 | pymupdf_lines+rawdict | 100.0% | 8.8% | -91.2% |
| Z9X4JVZ5_table_2 | pymupdf_text+word_assignment | 83.6% | 0.4% | -83.2% |
| Z9X4JVZ5_table_3 | pymupdf_lines+rawdict | 90.2% | 26.3% | -63.8% |
| Z9X4JVZ5_table_4 | pymupdf_lines+rawdict | 100.0% | 11.5% | -88.5% |
| Z9X4JVZ5_table_5 | pymupdf_text+rawdict | 100.0% | 18.2% | -81.8% |
| Z9X4JVZ5_table_7 | pymupdf_text+rawdict | 100.0% | 20.6% | -79.4% |
| Z9X4JVZ5_table_6 | header_anchor+rawdict | 4.3% | 3.4% | -0.8% |
| YMWV46JA_table_1 | global_cliff+rawdict | 3.6% | 33.8% | +30.2% |
| DPYRZTFI_table_1 | pymupdf_lines+rawdict | 99.8% | 2.3% | -97.6% |
| DPYRZTFI_table_2 | pymupdf_text+rawdict | 96.5% | 3.7% | -92.8% |
| DPYRZTFI_table_3 | pymupdf_lines+rawdict | 95.3% | 5.0% | -90.3% |
| VP3NJ74M_table_1 | pymupdf_text+rawdict | 85.7% | 17.5% | -68.3% |
| VP3NJ74M_table_3 | pymupdf_text+word_assignment | 29.6% | 8.2% | -21.5% |
| VP3NJ74M_table_2 | pymupdf_lines+rawdict | 29.6% | 3.2% | -26.4% |
| VP3NJ74M_table_4 | camelot_hybrid+rawdict | 94.8% | 1.3% | -93.5% |
| VP3NJ74M_table_5 | camelot_hybrid+word_assignment | 41.0% | 10.2% | -30.7% |
| VP3NJ74M_table_6 | pymupdf_lines+pdfminer | 13.4% | 0.5% | -12.9% |
| AQ3D94VC_table_1 | pymupdf_lines+rawdict | 98.1% | 10.9% | -87.3% |
| AQ3D94VC_table_2 | pymupdf_lines+rawdict | 97.8% | 12.5% | -85.3% |
| AQ3D94VC_table_4 | pymupdf_lines+rawdict | 44.9% | 11.6% | -33.3% |
| AQ3D94VC_table_3 | pymupdf_lines+rawdict | 44.9% | 11.8% | -33.1% |
| AQ3D94VC_table_5 | pymupdf_lines+rawdict | 100.0% | 14.5% | -85.5% |


## Variant Comparison

Accuracy and speed across named pipeline configs on corpus tables.

### Summary

| Config | Tables | Avg Accuracy | Avg Time (s) |
|--------|--------|-------------|-------------|
| DEFAULT | 24 | 7.2% | 25.653 |
| FAST | 24 | 7.7% | 1.480 |
| RULED | 24 | 7.2% | 25.076 |
| MINIMAL | 24 | 55.7% | 1.154 |

### Per-Table Detail

| Table ID | Paper | DEFAULT | FAST | RULED | MINIMAL | |
|----------|------|-----|-----|-----|-----||
| SCPXVBLY_table_1 | active-inference-tutorial | 3.8% | 3.8% | 3.8% | 22.1% | |
| SCPXVBLY_table_1_p16 | active-inference-tutorial | 9.0% | 11.0% | 9.0% | 45.4% | |
| SCPXVBLY_table_2 | active-inference-tutorial | 4.8% | 5.2% | 4.8% | 6.3% | |
| XIAINRVS_orphan_p1_t0 | huang-emd-1998 | 0.0% | 0.0% | 0.0% | 0.0% | |
| XIAINRVS_orphan_p2_t1 | huang-emd-1998 | 0.0% | 0.0% | 0.0% | 0.0% | |
| C626CYVT_table_1 | hallett-tms-primer | 13.1% | 13.1% | 13.1% | 77.9% | |
| 5SIZVS65_table_1 | laird-fick-polyps | 6.3% | 8.1% | 6.3% | 84.1% | |
| 5SIZVS65_table_2 | laird-fick-polyps | 3.6% | 2.8% | 3.6% | 86.5% | |
| 5SIZVS65_table_3 | laird-fick-polyps | 14.7% | 14.7% | 14.7% | 48.5% | |
| 9GKLLJH9_table_1 | helm-coregulation | 1.9% | 1.9% | 1.9% | 54.6% | |
| 9GKLLJH9_table_2 | helm-coregulation | 1.9% | 2.0% | 1.9% | 31.9% | |
| Z9X4JVZ5_table_1 | roland-emg-filter | 8.8% | 13.2% | 8.8% | 100.0% | |
| Z9X4JVZ5_table_2 | roland-emg-filter | 0.4% | 1.0% | 0.4% | 72.6% | |
| Z9X4JVZ5_table_3 | roland-emg-filter | 26.3% | 26.3% | 26.3% | 90.2% | |
| YMWV46JA_table_1 | friston-life | 3.6% | 0.0% | 3.6% | 0.0% | |
| DPYRZTFI_table_1 | yang-ppv-meta | 2.3% | 1.6% | 2.3% | 99.8% | |
| DPYRZTFI_table_2 | yang-ppv-meta | 3.7% | 6.1% | 3.7% | 88.0% | |
| DPYRZTFI_table_3 | yang-ppv-meta | 5.0% | 5.5% | 5.0% | 95.3% | |
| VP3NJ74M_table_1 | fortune-impedance | 17.5% | 17.5% | 17.5% | 65.8% | |
| VP3NJ74M_table_3 | fortune-impedance | 8.2% | 6.9% | 8.2% | 24.7% | |

