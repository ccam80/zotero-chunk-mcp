# Stress Test Report: zotero-chunk-rag

**Date**: 2026-02-09 22:11
**Corpus**: 10 papers from live Zotero library

## Executive Summary

- **Total tests**: 237
- **Passed**: 221 (93%)
- **Failed**: 16
- **Major failures**: 2

> **VERDICT**: This tool is NOT reliable for production research use.
> A researcher depending on this tool WILL miss important results.

## Performance

| Operation | Time |
|-----------|------|
| Total indexing | 274.7s |

## Extraction Quality per Paper

| Paper | Pages | Sections | Tables | Figures | Grade | Issues |
|-------|-------|----------|--------|---------|-------|--------|
| active-inference-tutorial | 60 | 16 | 7 | 18 | A | 9 unknown sections; no abstract detected |
| huang-emd-1998 | 96 | 28 | 2 | 80 | A | 21 unknown sections; no abstract detected |
| hallett-tms-primer | 13 | 25 | 1 | 7 | B | 1 figs missing; 22 unknown sections; no abstract detected |
| laird-fick-polyps | 7 | 20 | 5 | 3 | A | 7 unknown sections |
| helm-coregulation | 10 | 11 | 2 | 2 | A | 4 unknown sections; no abstract detected |
| roland-emg-filter | 24 | 23 | 8 | 17 | A | 2 unknown sections |
| friston-life | 12 | 6 | 0 | 5 | B | 1 tabs missing; 3 unknown sections; no abstract detected |
| yang-ppv-meta | 13 | 18 | 4 | 5 | A | 5 unknown sections |
| fortune-impedance | 11 | 10 | 6 | 7 | A | 3 unknown sections; no abstract detected |
| reyes-lf-hrv | 11 | 12 | 5 | 2 | A | 8 unknown sections |

## Failures (Detailed)

### ! [MINOR] section-detection — active-inference-tutorial

Expected section 'discussion' — MISSING. Got: ['appendix', 'conclusion', 'introduction', 'preamble', 'references', 'unknown']

### ! [MINOR] table-content-quality — active-inference-tutorial/table-3

Table 3: 82/544 cells non-empty (15%). Caption: 'Table 2 (continued).'

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

### ! [MINOR] section-detection — helm-coregulation

Expected section 'introduction' — MISSING. Got: ['conclusion', 'discussion', 'methods', 'preamble', 'references', 'results', 'unknown']

### ! [MINOR] abstract-detection — helm-coregulation

Abstract NOT detected

### ! [MINOR] table-content-quality — roland-emg-filter/table-1

Table 1: 156/550 cells non-empty (28%). Caption: 'Table 2. Floating-point highpass ﬁlter coefﬁcients.'

### ! [MINOR] abstract-detection — friston-life

Abstract NOT detected

### !!! [MAJOR] figure-caption-rate — yang-ppv-meta

0/5 figures have captions (0%). Orphan pages: [3, 7, 8, 9, 10]

### ! [MINOR] abstract-detection — fortune-impedance

Abstract NOT detected

### ! [MINOR] section-detection — reyes-lf-hrv

Expected section 'introduction' — MISSING. Got: ['abstract', 'conclusion', 'methods', 'references', 'unknown']

### !!! [MAJOR] figure-search-recall — helm-coregulation

Query: 'coregulation respiratory' — NOT FOUND in top 10. Got: ['The empirical mode decompositi', 'The utility of low frequency h', 'The empirical mode decompositi']

## Passes

| Test | Paper | Detail |
|------|-------|--------|
| section-detection | active-inference-tutorial | Expected section 'introduction' — FOUND |
| section-detection | active-inference-tutorial | Expected section 'conclusion' — FOUND |
| table-extraction | active-inference-tutorial | Expected tables — found 7 |
| table-content-quality | active-inference-tutorial/table-0 | Table 0: 22/42 cells non-empty (52%). Caption: 'NONE' |
| table-content-quality | active-inference-tutorial/table-1 | Table 1: 85/177 cells non-empty (48%). Caption: 'NONE' |
| table-content-quality | active-inference-tutorial/table-2 | Table 2: 19/30 cells non-empty (63%). Caption: 'Table 1 (continued).' |
| table-content-quality | active-inference-tutorial/table-4 | Table 4: 53/176 cells non-empty (30%). Caption: 'Table 2 (continued).' |
| table-content-quality | active-inference-tutorial/table-5 | Table 5: 135/280 cells non-empty (48%). Caption: 'NONE' |
| table-content-quality | active-inference-tutorial/table-6 | Table 6: 41/76 cells non-empty (54%). Caption: 'Table 3 (continued).' |
| figure-extraction | active-inference-tutorial | Expected figures — found 18 |
| figure-caption-rate | active-inference-tutorial | 9/18 figures have captions (50%). Orphan pages: [4, 5, 14, 17, 29, 32, 42, 48, 5 |
| completeness-grade | active-inference-tutorial | Grade: A / Figs: 18 found / 9 captioned / 0 missing / Tables: 7 found / 3 captio |
| chunk-count-sanity | active-inference-tutorial | 337 chunks for 60 pages (expected >= 120) |
| figure-images-saved | active-inference-tutorial | 18/18 figure images saved to disk |
| section-detection | huang-emd-1998 | Expected section 'introduction' — FOUND |
| section-detection | huang-emd-1998 | Expected section 'conclusion' — FOUND |
| figure-extraction | huang-emd-1998 | Expected figures — found 80 |
| figure-caption-rate | huang-emd-1998 | 76/80 figures have captions (95%). Orphan pages: [30, 35, 36, 44] |
| completeness-grade | huang-emd-1998 | Grade: A / Figs: 80 found / 75 captioned / 0 missing / Tables: 2 found / 0 capti |
| figure-images-saved | huang-emd-1998 | 80/80 figure images saved to disk |
| table-extraction | hallett-tms-primer | Expected tables — found 1 |
| table-content-quality | hallett-tms-primer/table-0 | Table 0: 11/35 cells non-empty (31%). Caption: 'Table 1. Summary of Noninvasive  |
| figure-extraction | hallett-tms-primer | Expected figures — found 7 |
| figure-caption-rate | hallett-tms-primer | 7/7 figures have captions (100%). Orphan pages: [] |
| completeness-grade | hallett-tms-primer | Grade: B / Figs: 7 found / 8 captioned / 1 missing / Tables: 1 found / 1 caption |
| chunk-count-sanity | hallett-tms-primer | 71 chunks for 13 pages (expected >= 26) |
| figure-images-saved | hallett-tms-primer | 7/7 figure images saved to disk |
| section-detection | laird-fick-polyps | Expected section 'methods' — FOUND |
| section-detection | laird-fick-polyps | Expected section 'results' — FOUND |
| section-detection | laird-fick-polyps | Expected section 'discussion' — FOUND |
| table-extraction | laird-fick-polyps | Expected tables — found 5 |
| table-content-quality | laird-fick-polyps/table-0 | Table 0: 32/35 cells non-empty (91%). Caption: 'NONE' |
| table-content-quality | laird-fick-polyps/table-1 | Table 1: 80/85 cells non-empty (94%). Caption: 'NONE' |
| table-content-quality | laird-fick-polyps/table-2 | Table 2: 25/30 cells non-empty (83%). Caption: 'NONE' |
| table-content-quality | laird-fick-polyps/table-3 | Table 3: 66/84 cells non-empty (79%). Caption: 'NONE' |
| table-content-quality | laird-fick-polyps/table-4 | Table 4: 65/72 cells non-empty (90%). Caption: 'NONE' |
| completeness-grade | laird-fick-polyps | Grade: A / Figs: 3 found / 0 captioned / 0 missing / Tables: 5 found / 0 caption |
| abstract-detection | laird-fick-polyps | Abstract detected |
| chunk-count-sanity | laird-fick-polyps | 25 chunks for 7 pages (expected >= 14) |
| section-detection | helm-coregulation | Expected section 'methods' — FOUND |
| section-detection | helm-coregulation | Expected section 'results' — FOUND |
| section-detection | helm-coregulation | Expected section 'discussion' — FOUND |
| table-extraction | helm-coregulation | Expected tables — found 2 |
| table-content-quality | helm-coregulation/table-0 | Table 0: 41/48 cells non-empty (85%). Caption: 'NONE' |
| table-content-quality | helm-coregulation/table-1 | Table 1: 43/77 cells non-empty (56%). Caption: 'NONE' |
| figure-extraction | helm-coregulation | Expected figures — found 2 |
| figure-caption-rate | helm-coregulation | 2/2 figures have captions (100%). Orphan pages: [] |
| completeness-grade | helm-coregulation | Grade: A / Figs: 2 found / 2 captioned / 0 missing / Tables: 2 found / 0 caption |
| chunk-count-sanity | helm-coregulation | 55 chunks for 10 pages (expected >= 20) |
| figure-images-saved | helm-coregulation | 2/2 figure images saved to disk |
| section-detection | roland-emg-filter | Expected section 'introduction' — FOUND |
| section-detection | roland-emg-filter | Expected section 'results' — FOUND |
| section-detection | roland-emg-filter | Expected section 'conclusion' — FOUND |
| table-extraction | roland-emg-filter | Expected tables — found 8 |
| table-content-quality | roland-emg-filter/table-0 | Table 0: 81/81 cells non-empty (100%). Caption: 'Table 1. Floating-point comb ﬁl |
| table-content-quality | roland-emg-filter/table-2 | Table 2: 10/24 cells non-empty (42%). Caption: 'Table 3. Poles of comb ﬁlters wi |
| table-content-quality | roland-emg-filter/table-3 | Table 3: 27/30 cells non-empty (90%). Caption: 'Table 4. Poles of highpass ﬁlter |
| table-content-quality | roland-emg-filter/table-4 | Table 4: 9/12 cells non-empty (75%). Caption: 'Table 5. Runtime per sample of ﬁl |
| table-content-quality | roland-emg-filter/table-5 | Table 5: 10/10 cells non-empty (100%). Caption: 'Table 6. Comparison of runtime  |
| table-content-quality | roland-emg-filter/table-6 | Table 6: 20/55 cells non-empty (36%). Caption: 'Table 7. Effect of reducing samp |
| table-content-quality | roland-emg-filter/table-7 | Table 7: 26/26 cells non-empty (100%). Caption: 'NONE' |
| figure-extraction | roland-emg-filter | Expected figures — found 17 |
| figure-caption-rate | roland-emg-filter | 17/17 figures have captions (100%). Orphan pages: [] |
| completeness-grade | roland-emg-filter | Grade: A / Figs: 17 found / 17 captioned / 0 missing / Tables: 8 found / 7 capti |
| abstract-detection | roland-emg-filter | Abstract detected |
| chunk-count-sanity | roland-emg-filter | 73 chunks for 24 pages (expected >= 48) |
| figure-images-saved | roland-emg-filter | 17/17 figure images saved to disk |
| section-detection | friston-life | Expected section 'introduction' — FOUND |
| figure-extraction | friston-life | Expected figures — found 5 |
| figure-caption-rate | friston-life | 5/5 figures have captions (100%). Orphan pages: [] |
| completeness-grade | friston-life | Grade: B / Figs: 5 found / 5 captioned / 0 missing / Tables: 0 found / 1 caption |
| chunk-count-sanity | friston-life | 60 chunks for 12 pages (expected >= 24) |
| figure-images-saved | friston-life | 5/5 figure images saved to disk |
| section-detection | yang-ppv-meta | Expected section 'introduction' — FOUND |
| section-detection | yang-ppv-meta | Expected section 'methods' — FOUND |
| section-detection | yang-ppv-meta | Expected section 'results' — FOUND |
| section-detection | yang-ppv-meta | Expected section 'discussion' — FOUND |
| table-extraction | yang-ppv-meta | Expected tables — found 4 |
| table-content-quality | yang-ppv-meta/table-0 | Table 0: 154/154 cells non-empty (100%). Caption: 'NONE' |
| table-content-quality | yang-ppv-meta/table-1 | Table 1: 298/338 cells non-empty (88%). Caption: 'NONE' |
| table-content-quality | yang-ppv-meta/table-2 | Table 2: 255/385 cells non-empty (66%). Caption: 'NONE' |
| table-content-quality | yang-ppv-meta/table-3 | Table 3: 2/3 cells non-empty (67%). Caption: 'NONE' |
| figure-extraction | yang-ppv-meta | Expected figures — found 5 |
| completeness-grade | yang-ppv-meta | Grade: A / Figs: 5 found / 0 captioned / 0 missing / Tables: 4 found / 0 caption |
| abstract-detection | yang-ppv-meta | Abstract detected |
| chunk-count-sanity | yang-ppv-meta | 49 chunks for 13 pages (expected >= 26) |
| figure-images-saved | yang-ppv-meta | 5/5 figure images saved to disk |
| section-detection | fortune-impedance | Expected section 'introduction' — FOUND |
| section-detection | fortune-impedance | Expected section 'methods' — FOUND |
| section-detection | fortune-impedance | Expected section 'results' — FOUND |
| table-extraction | fortune-impedance | Expected tables — found 6 |
| table-content-quality | fortune-impedance/table-0 | Table 0: 23/54 cells non-empty (43%). Caption: 'NONE' |
| table-content-quality | fortune-impedance/table-1 | Table 1: 14/16 cells non-empty (88%). Caption: 'NONE' |
| table-content-quality | fortune-impedance/table-2 | Table 2: 29/35 cells non-empty (83%). Caption: 'NONE' |
| table-content-quality | fortune-impedance/table-3 | Table 3: 60/60 cells non-empty (100%). Caption: 'NONE' |
| table-content-quality | fortune-impedance/table-4 | Table 4: 263/287 cells non-empty (92%). Caption: 'NONE' |
| table-content-quality | fortune-impedance/table-5 | Table 5: 50/78 cells non-empty (64%). Caption: 'NONE' |
| figure-extraction | fortune-impedance | Expected figures — found 7 |
| figure-caption-rate | fortune-impedance | 7/7 figures have captions (100%). Orphan pages: [] |
| completeness-grade | fortune-impedance | Grade: A / Figs: 7 found / 7 captioned / 0 missing / Tables: 6 found / 0 caption |
| chunk-count-sanity | fortune-impedance | 40 chunks for 11 pages (expected >= 22) |
| figure-images-saved | fortune-impedance | 7/7 figure images saved to disk |
| section-detection | reyes-lf-hrv | Expected section 'conclusion' — FOUND |
| table-extraction | reyes-lf-hrv | Expected tables — found 5 |
| table-content-quality | reyes-lf-hrv/table-0 | Table 0: 52/72 cells non-empty (72%). Caption: 'Table 1. Means and Standard Devi |
| table-content-quality | reyes-lf-hrv/table-1 | Table 1: 40/72 cells non-empty (56%). Caption: 'Table 2. Means and Standard Devi |
| table-content-quality | reyes-lf-hrv/table-2 | Table 2: 58/70 cells non-empty (83%). Caption: 'Table 4. Correlations of HRV Par |
| table-content-quality | reyes-lf-hrv/table-3 | Table 3: 58/70 cells non-empty (83%). Caption: 'Table 3. Correlations of HRV Par |
| table-content-quality | reyes-lf-hrv/table-4 | Table 4: 90/90 cells non-empty (100%). Caption: 'Table 5. Hypothetical Database  |
| figure-extraction | reyes-lf-hrv | Expected figures — found 2 |
| figure-caption-rate | reyes-lf-hrv | 2/2 figures have captions (100%). Orphan pages: [] |
| completeness-grade | reyes-lf-hrv | Grade: A / Figs: 2 found / 2 captioned / 0 missing / Tables: 5 found / 5 caption |
| abstract-detection | reyes-lf-hrv | Abstract detected |
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
| table-search-recall | active-inference-tutorial | Query: 'algorithm update rules' — found 6 matching table(s), best score 0.271, c |
| table-markdown-quality | active-inference-tutorial | Table markdown has pipes and 76 lines. Preview: **Table 2 (continued).** /  / /  |
| table-search-recall | hallett-tms-primer | Query: 'stimulation parameters coil' — found 1 matching table(s), best score 0.3 |
| table-markdown-quality | hallett-tms-primer | Table markdown has pipes and 14 lines. Preview: **Table 1. Summary of Noninvasiv |
| table-search-recall | laird-fick-polyps | Query: 'polyp location demographics patient' — found 5 matching table(s), best s |
| table-markdown-quality | laird-fick-polyps | Table markdown has pipes and 54 lines. Preview: / patients /  /  /  /  /  / / /  |
| table-search-recall | helm-coregulation | Query: 'correlation coefficient RSA' — found 1 matching table(s), best score 0.2 |
| table-markdown-quality | helm-coregulation | Table markdown has pipes and 66 lines. Preview: / Task /  / Coefficient / Estima |
| table-search-recall | roland-emg-filter | Query: 'power consumption filter' — found 5 matching table(s), best score 0.424, |
| table-markdown-quality | roland-emg-filter | Table markdown has pipes and 23 lines. Preview: **Table 7. Effect of reducing sa |
| table-search-recall | yang-ppv-meta | Query: 'sensitivity specificity diagnostic' — found 1 matching table(s), best sc |
| table-markdown-quality | yang-ppv-meta | Table markdown has pipes and 56 lines. Preview: /  /  /  / / / --- / --- / --- / |
| table-search-recall | fortune-impedance | Query: 'impedance measurement electrode' — found 4 matching table(s), best score |
| table-markdown-quality | fortune-impedance | Table markdown has pipes and 28 lines. Preview: / A R T I C L E / I N F O / A B  |
| table-search-recall | reyes-lf-hrv | Query: 'autonomic measures' — found 5 matching table(s), best score 0.421, capti |
| table-markdown-quality | reyes-lf-hrv | Table markdown has pipes and 65 lines. Preview: **Table 4. Correlations of HRV P |
| figure-search-recall | active-inference-tutorial | Query: 'generative model graphical' — found 6 matching figure(s), best score 0.6 |
| figure-search-recall | huang-emd-1998 | Query: 'intrinsic mode function' — found 6 matching figure(s), best score 0.796, |
| figure-search-recall | hallett-tms-primer | Query: 'magnetic field coil' — found 3 matching figure(s), best score 0.526, cap |
| figure-search-recall | roland-emg-filter | Query: 'filter frequency response' — found 7 matching figure(s), best score 0.45 |
| figure-search-recall | friston-life | Query: 'Markov blanket' — found 4 matching figure(s), best score 0.553, caption: |
| figure-search-recall | yang-ppv-meta | Query: 'forest plot' — found 1 matching figure(s), best score 0.264, caption: '' |
| figure-search-recall | fortune-impedance | Query: 'impedance frequency' — found 3 matching figure(s), best score 0.373, cap |
| figure-search-recall | reyes-lf-hrv | Query: 'heart rate variability' — found 1 matching figure(s), best score 0.308,  |
| author-filter | active-inference-tutorial | Filter author='smith' — target paper found (43 total results after filter) |
| author-filter | huang-emd-1998 | Filter author='huang' — target paper found (49 total results after filter) |
| author-filter | hallett-tms-primer | Filter author='hallett' — target paper found (50 total results after filter) |
| author-filter | laird-fick-polyps | Filter author='laird' — target paper found (27 total results after filter) |
| author-filter | helm-coregulation | Filter author='helm' — target paper found (20 total results after filter) |
| author-filter | roland-emg-filter | Filter author='roland' — target paper found (47 total results after filter) |
| author-filter | friston-life | Filter author='friston' — target paper found (43 total results after filter) |
| author-filter | yang-ppv-meta | Filter author='yang' — target paper found (29 total results after filter) |
| author-filter | fortune-impedance | Filter author='fortune' — target paper found (41 total results after filter) |
| author-filter | reyes-lf-hrv | Filter author='reyes' — target paper found (45 total results after filter) |
| year-filter-accuracy | all | Year filter >=2015: 0 papers from before 2015 leaked through (total results: 50) |
| context-expansion | active-inference-tutorial | Context expansion: before=2, after=2, full_context=7924 chars |
| context-adds-value | active-inference-tutorial | Full context (7924 chars) vs hit (1583 chars) |
| context-expansion | huang-emd-1998 | Context expansion: before=2, after=2, full_context=7705 chars |
| context-adds-value | huang-emd-1998 | Full context (7705 chars) vs hit (1591 chars) |
| context-expansion | hallett-tms-primer | Context expansion: before=8, after=2, full_context=8265 chars |
| context-adds-value | hallett-tms-primer | Full context (8265 chars) vs hit (1411 chars) |
| context-expansion | laird-fick-polyps | Context expansion: before=2, after=2, full_context=7703 chars |
| context-adds-value | laird-fick-polyps | Full context (7703 chars) vs hit (1576 chars) |
| context-expansion | helm-coregulation | Context expansion: before=4, after=2, full_context=6687 chars |
| context-adds-value | helm-coregulation | Full context (6687 chars) vs hit (1600 chars) |
| context-expansion | roland-emg-filter | Context expansion: before=2, after=2, full_context=7693 chars |
| context-adds-value | roland-emg-filter | Full context (7693 chars) vs hit (1503 chars) |
| context-expansion | friston-life | Context expansion: before=2, after=2, full_context=7897 chars |
| context-adds-value | friston-life | Full context (7897 chars) vs hit (1591 chars) |
| context-expansion | yang-ppv-meta | Context expansion: before=2, after=2, full_context=8007 chars |
| context-adds-value | yang-ppv-meta | Full context (8007 chars) vs hit (1600 chars) |
| context-expansion | fortune-impedance | Context expansion: before=2, after=2, full_context=7774 chars |
| context-adds-value | fortune-impedance | Full context (7774 chars) vs hit (1482 chars) |
| context-expansion | reyes-lf-hrv | Context expansion: before=7, after=2, full_context=9017 chars |
| context-adds-value | reyes-lf-hrv | Full context (9017 chars) vs hit (1361 chars) |
| topic-search-multi-paper | HRV papers | Topic search for HRV: found 2/2 expected papers in 2 total docs. Keys found: {'9 |
| topic-search-engineering | impedance papers | Topic search for impedance: found 1/1 expected. Total docs: 2. Keys: {'VP3NJ74M' |
| ocr-text-extraction | active-inference-tutorial | OCR extracted 63342 chars from 3 image pages. OCR pages detected: 3 |
| ocr-page-detection | active-inference-tutorial | OCR page detection: 3/3 pages flagged as OCR |
| nonsense-query-no-crash | all | Nonsense query returned 5 results (top score: 0.311) |
| empty-rerank-no-crash | all | Reranker handles empty input gracefully |
| boundary-chunk-first | active-inference-tutorial | Adjacent chunks for first chunk: got 28 (expected >=1) |
| boundary-chunk-last | active-inference-tutorial | Adjacent chunks for last chunk (idx=336): got 3 |
| boundary-chunk-first | huang-emd-1998 | Adjacent chunks for first chunk: got 85 (expected >=1) |
| boundary-chunk-last | huang-emd-1998 | Adjacent chunks for last chunk (idx=184): got 3 |
| section-weight-effect | all | Default top-3 sections: ['methods', 'methods', 'table'], methods-boosted top-3:  |
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
