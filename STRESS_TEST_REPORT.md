# Stress Test Report: zotero-chunk-rag

**Date**: 2026-02-10 09:11
**Corpus**: 10 papers from live Zotero library

## Executive Summary

- **Total tests**: 267
- **Passed**: 221 (83%)
- **Failed**: 46
- **Major failures**: 26

> **VERDICT**: This tool is NOT reliable for production research use.
> A researcher depending on this tool WILL miss important results.

## Performance

| Operation | Time |
|-----------|------|
| Total indexing | 267.8s |

## Extraction Quality per Paper

| Paper | Pages | Sections | Tables | Figures | Grade | Issues |
|-------|-------|----------|--------|---------|-------|--------|
| active-inference-tutorial | 60 | 16 | 8 | 18 | C | 9 unknown sections; no abstract detected |
| huang-emd-1998 | 96 | 28 | 2 | 80 | D | 21 unknown sections; no abstract detected |
| hallett-tms-primer | 13 | 25 | 1 | 7 | B | 1 figs missing; 22 unknown sections; no abstract detected |
| laird-fick-polyps | 7 | 20 | 5 | 3 | A | 7 unknown sections |
| helm-coregulation | 10 | 11 | 2 | 2 | A | 4 unknown sections; no abstract detected |
| roland-emg-filter | 24 | 23 | 8 | 17 | B | 2 unknown sections |
| friston-life | 12 | 6 | 0 | 5 | D | 1 tabs missing; 3 unknown sections; no abstract detected |
| yang-ppv-meta | 13 | 18 | 4 | 6 | C | 5 unknown sections |
| fortune-impedance | 11 | 10 | 6 | 7 | B | 3 unknown sections; no abstract detected |
| reyes-lf-hrv | 11 | 12 | 5 | 2 | A | 8 unknown sections |

## Failures (Detailed)

### ! [MINOR] section-detection — active-inference-tutorial

Expected section 'discussion' — MISSING. Got: ['appendix', 'conclusion', 'introduction', 'preamble', 'references', 'unknown']

### !!! [MAJOR] table-caption-missing — active-inference-tutorial/table-0

Table 0 on page 1: NO CAPTION

### !!! [MAJOR] table-caption-continuation — active-inference-tutorial/table-2

Table 2 on page 16: unverified continuation caption 'Table 1 (continued).'

### ! [MINOR] table-content-quality — active-inference-tutorial/table-3

Table 3: 110/885 cells non-empty (12%). Caption: 'Table 2 Matrix formulation of equations used for inference.'

### ! [MINOR] table-content-quality — active-inference-tutorial/table-4

Table 4: 82/544 cells non-empty (15%). Caption: 'Table 2 (continued).'

### !!! [MAJOR] table-caption-continuation — active-inference-tutorial/table-4

Table 4 on page 19: unverified continuation caption 'Table 2 (continued).'

### !!! [MAJOR] table-caption-continuation — active-inference-tutorial/table-5

Table 5 on page 20: unverified continuation caption 'Table 2 (continued).'

### !!! [MAJOR] table-caption-continuation — active-inference-tutorial/table-7

Table 7 on page 31: unverified continuation caption 'Table 3 (continued).'

### !!! [MAJOR] table-caption-rate — active-inference-tutorial

3/8 tables have verified captions (38%)

### !!! [MAJOR] figure-caption-missing — active-inference-tutorial/fig-0

Figure 0 on page 4: NO CAPTION

### !!! [MAJOR] figure-caption-missing — active-inference-tutorial/fig-2

Figure 2 on page 5: NO CAPTION

### !!! [MAJOR] figure-caption-missing — active-inference-tutorial/fig-4

Figure 4 on page 14: NO CAPTION

### !!! [MAJOR] figure-caption-missing — active-inference-tutorial/fig-6

Figure 6 on page 17: NO CAPTION

### !!! [MAJOR] figure-caption-missing — active-inference-tutorial/fig-7

Figure 7 on page 29: NO CAPTION

### !!! [MAJOR] figure-caption-missing — active-inference-tutorial/fig-8

Figure 8 on page 32: NO CAPTION

### !!! [MAJOR] figure-caption-missing — active-inference-tutorial/fig-13

Figure 13 on page 42: NO CAPTION

### !!! [MAJOR] figure-caption-missing — active-inference-tutorial/fig-16

Figure 16 on page 48: NO CAPTION

### !!! [MAJOR] figure-caption-missing — active-inference-tutorial/fig-17

Figure 17 on page 53: NO CAPTION

### !!! [MAJOR] figure-caption-rate — active-inference-tutorial

9/18 figures have verified captions (50%). Orphan pages: [4, 5, 14, 17, 29, 32, 42, 48, 53]

### ! [MINOR] completeness-grade — active-inference-tutorial

Grade: C | Figs: 18 found / 9 captioned / 0 missing | Tables: 8 found / 3 captioned / 0 missing

### ! [MINOR] abstract-detection — active-inference-tutorial

Abstract NOT detected

### !!! [MAJOR] figure-caption-missing — huang-emd-1998/fig-12

Figure 12 on page 30: NO CAPTION

### !!! [MAJOR] figure-caption-missing — huang-emd-1998/fig-16

Figure 16 on page 35: NO CAPTION

### !!! [MAJOR] figure-caption-missing — huang-emd-1998/fig-17

Figure 17 on page 36: NO CAPTION

### !!! [MAJOR] figure-caption-missing — huang-emd-1998/fig-26

Figure 26 on page 44: NO CAPTION

### ! [MINOR] figure-caption-rate — huang-emd-1998

76/80 figures have verified captions (95%). Orphan pages: [30, 35, 36, 44]

### !!! [MAJOR] completeness-grade — huang-emd-1998

Grade: D | Figs: 80 found / 75 captioned / 0 missing | Tables: 2 found / 0 captioned / 0 missing

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

### !!! [MAJOR] table-caption-missing — roland-emg-filter/table-7

Table 7 on page 22: NO CAPTION

### ! [MINOR] table-caption-rate — roland-emg-filter

7/8 tables have verified captions (88%)

### !!! [MAJOR] completeness-grade — friston-life

Grade: D | Figs: 5 found / 5 captioned / 0 missing | Tables: 0 found / 1 captioned / 1 missing

### ! [MINOR] abstract-detection — friston-life

Abstract NOT detected

### !!! [MAJOR] table-caption-missing — yang-ppv-meta/table-3

Table 3 on page 7: NO CAPTION

### !!! [MAJOR] table-caption-rate — yang-ppv-meta

3/4 tables have verified captions (75%)

### ! [MINOR] completeness-grade — yang-ppv-meta

Grade: C | Figs: 6 found / 6 captioned / 0 missing | Tables: 4 found / 3 captioned / 0 missing

### !!! [MAJOR] table-caption-missing — fortune-impedance/table-0

Table 0 on page 1: NO CAPTION

### ! [MINOR] table-caption-rate — fortune-impedance

5/6 tables have verified captions (83%)

### ! [MINOR] abstract-detection — fortune-impedance

Abstract NOT detected

### ! [MINOR] section-detection — reyes-lf-hrv

Expected section 'introduction' — MISSING. Got: ['abstract', 'conclusion', 'methods', 'references', 'unknown']

## Passes

| Test | Paper | Detail |
|------|-------|--------|
| section-detection | active-inference-tutorial | Expected section 'introduction' — FOUND |
| section-detection | active-inference-tutorial | Expected section 'conclusion' — FOUND |
| table-extraction | active-inference-tutorial | Expected tables — found 8 |
| table-content-quality | active-inference-tutorial/table-0 | Table 0: 22/42 cells non-empty (52%). Caption: 'NONE' |
| table-content-quality | active-inference-tutorial/table-1 | Table 1: 85/177 cells non-empty (48%). Caption: 'Table 1 Model variables.' |
| table-content-quality | active-inference-tutorial/table-2 | Table 2: 19/30 cells non-empty (63%). Caption: 'Table 1 (continued).' |
| table-content-quality | active-inference-tutorial/table-5 | Table 5: 53/176 cells non-empty (30%). Caption: 'Table 2 (continued).' |
| table-content-quality | active-inference-tutorial/table-6 | Table 6: 135/280 cells non-empty (48%). Caption: 'Table 3 Output fields for spm_ |
| table-content-quality | active-inference-tutorial/table-7 | Table 7: 41/76 cells non-empty (54%). Caption: 'Table 3 (continued).' |
| figure-extraction | active-inference-tutorial | Expected figures — found 18 |
| chunk-count-sanity | active-inference-tutorial | 337 chunks for 60 pages (expected >= 120) |
| figure-images-saved | active-inference-tutorial | 18/18 figure images saved to disk |
| section-detection | huang-emd-1998 | Expected section 'introduction' — FOUND |
| section-detection | huang-emd-1998 | Expected section 'conclusion' — FOUND |
| figure-extraction | huang-emd-1998 | Expected figures — found 80 |
| figure-images-saved | huang-emd-1998 | 80/80 figure images saved to disk |
| table-extraction | hallett-tms-primer | Expected tables — found 1 |
| table-content-quality | hallett-tms-primer/table-0 | Table 0: 11/35 cells non-empty (31%). Caption: 'Table 1. Summary of Noninvasive  |
| table-caption-rate | hallett-tms-primer | 1/1 tables have verified captions (100%) |
| figure-extraction | hallett-tms-primer | Expected figures — found 7 |
| figure-caption-rate | hallett-tms-primer | 7/7 figures have verified captions (100%). Orphan pages: [] |
| completeness-grade | hallett-tms-primer | Grade: B / Figs: 7 found / 8 captioned / 1 missing / Tables: 1 found / 1 caption |
| chunk-count-sanity | hallett-tms-primer | 71 chunks for 13 pages (expected >= 26) |
| figure-images-saved | hallett-tms-primer | 7/7 figure images saved to disk |
| section-detection | laird-fick-polyps | Expected section 'methods' — FOUND |
| section-detection | laird-fick-polyps | Expected section 'results' — FOUND |
| section-detection | laird-fick-polyps | Expected section 'discussion' — FOUND |
| table-extraction | laird-fick-polyps | Expected tables — found 5 |
| table-content-quality | laird-fick-polyps/table-0 | Table 0: 32/35 cells non-empty (91%). Caption: 'Table 1 Distribution of Sex by A |
| table-content-quality | laird-fick-polyps/table-1 | Table 1: 80/85 cells non-empty (94%). Caption: 'Table 2 Distribution of Sex by H |
| table-content-quality | laird-fick-polyps/table-2 | Table 2: 25/30 cells non-empty (83%). Caption: 'Table 3 Prevalence of sessile se |
| table-content-quality | laird-fick-polyps/table-3 | Table 3: 66/84 cells non-empty (79%). Caption: 'Table 4 Odds ratios and 95 % con |
| table-content-quality | laird-fick-polyps/table-4 | Table 4: 65/72 cells non-empty (90%). Caption: 'Table 5 Distribution of polyps b |
| table-caption-rate | laird-fick-polyps | 5/5 tables have verified captions (100%) |
| completeness-grade | laird-fick-polyps | Grade: A / Figs: 3 found / 3 captioned / 0 missing / Tables: 5 found / 5 caption |
| abstract-detection | laird-fick-polyps | Abstract detected |
| chunk-count-sanity | laird-fick-polyps | 25 chunks for 7 pages (expected >= 14) |
| section-detection | helm-coregulation | Expected section 'methods' — FOUND |
| section-detection | helm-coregulation | Expected section 'results' — FOUND |
| section-detection | helm-coregulation | Expected section 'discussion' — FOUND |
| table-extraction | helm-coregulation | Expected tables — found 2 |
| table-content-quality | helm-coregulation/table-0 | Table 0: 41/48 cells non-empty (85%). Caption: 'Table 1 Comparisons of Model Fit |
| table-content-quality | helm-coregulation/table-1 | Table 1: 43/77 cells non-empty (56%). Caption: 'Table 2 Coefficients From Best-F |
| table-caption-rate | helm-coregulation | 2/2 tables have verified captions (100%) |
| figure-extraction | helm-coregulation | Expected figures — found 2 |
| figure-caption-rate | helm-coregulation | 2/2 figures have verified captions (100%). Orphan pages: [] |
| completeness-grade | helm-coregulation | Grade: A / Figs: 2 found / 2 captioned / 0 missing / Tables: 2 found / 2 caption |
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
| figure-caption-rate | roland-emg-filter | 17/17 figures have verified captions (100%). Orphan pages: [] |
| completeness-grade | roland-emg-filter | Grade: B / Figs: 17 found / 17 captioned / 0 missing / Tables: 8 found / 7 capti |
| abstract-detection | roland-emg-filter | Abstract detected |
| chunk-count-sanity | roland-emg-filter | 73 chunks for 24 pages (expected >= 48) |
| figure-images-saved | roland-emg-filter | 17/17 figure images saved to disk |
| section-detection | friston-life | Expected section 'introduction' — FOUND |
| figure-extraction | friston-life | Expected figures — found 5 |
| figure-caption-rate | friston-life | 5/5 figures have verified captions (100%). Orphan pages: [] |
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
| table-content-quality | yang-ppv-meta/table-3 | Table 3: 2/3 cells non-empty (67%). Caption: 'NONE' |
| figure-extraction | yang-ppv-meta | Expected figures — found 6 |
| figure-caption-rate | yang-ppv-meta | 6/6 figures have verified captions (100%). Orphan pages: [] |
| abstract-detection | yang-ppv-meta | Abstract detected |
| chunk-count-sanity | yang-ppv-meta | 49 chunks for 13 pages (expected >= 26) |
| figure-images-saved | yang-ppv-meta | 6/6 figure images saved to disk |
| section-detection | fortune-impedance | Expected section 'introduction' — FOUND |
| section-detection | fortune-impedance | Expected section 'methods' — FOUND |
| section-detection | fortune-impedance | Expected section 'results' — FOUND |
| table-extraction | fortune-impedance | Expected tables — found 6 |
| table-content-quality | fortune-impedance/table-0 | Table 0: 23/54 cells non-empty (43%). Caption: 'NONE' |
| table-content-quality | fortune-impedance/table-1 | Table 1: 14/16 cells non-empty (88%). Caption: 'Table 1 Component values used fo |
| table-content-quality | fortune-impedance/table-2 | Table 2: 29/35 cells non-empty (83%). Caption: 'Table 2 Error between the custom |
| table-content-quality | fortune-impedance/table-3 | Table 3: 60/60 cells non-empty (100%). Caption: 'Table 3 Error between the custo |
| table-content-quality | fortune-impedance/table-4 | Table 4: 263/287 cells non-empty (92%). Caption: 'Table 4 Electrode–skin impedan |
| table-content-quality | fortune-impedance/table-5 | Table 5: 50/78 cells non-empty (64%). Caption: 'Table 5 Mean electrode–skin impe |
| figure-extraction | fortune-impedance | Expected figures — found 7 |
| figure-caption-rate | fortune-impedance | 7/7 figures have verified captions (100%). Orphan pages: [] |
| completeness-grade | fortune-impedance | Grade: B / Figs: 7 found / 7 captioned / 0 missing / Tables: 6 found / 6 caption |
| chunk-count-sanity | fortune-impedance | 40 chunks for 11 pages (expected >= 22) |
| figure-images-saved | fortune-impedance | 7/7 figure images saved to disk |
| section-detection | reyes-lf-hrv | Expected section 'conclusion' — FOUND |
| table-extraction | reyes-lf-hrv | Expected tables — found 5 |
| table-content-quality | reyes-lf-hrv/table-0 | Table 0: 52/72 cells non-empty (72%). Caption: 'Table 1. Means and Standard Devi |
| table-content-quality | reyes-lf-hrv/table-1 | Table 1: 40/72 cells non-empty (56%). Caption: 'Table 2. Means and Standard Devi |
| table-content-quality | reyes-lf-hrv/table-2 | Table 2: 58/70 cells non-empty (83%). Caption: 'Table 4. Correlations of HRV Par |
| table-content-quality | reyes-lf-hrv/table-3 | Table 3: 58/70 cells non-empty (83%). Caption: 'Table 3. Correlations of HRV Par |
| table-content-quality | reyes-lf-hrv/table-4 | Table 4: 90/90 cells non-empty (100%). Caption: 'Table 5. Hypothetical Database  |
| table-caption-rate | reyes-lf-hrv | 5/5 tables have verified captions (100%) |
| figure-extraction | reyes-lf-hrv | Expected figures — found 2 |
| figure-caption-rate | reyes-lf-hrv | 2/2 figures have verified captions (100%). Orphan pages: [] |
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
| table-search-recall | active-inference-tutorial | Query: 'algorithm update rules' — found 6 matching table(s), best score 0.293, c |
| table-markdown-quality | active-inference-tutorial | Table markdown has pipes and 109 lines. Preview: **Table 2 Matrix formulation of |
| table-search-recall | hallett-tms-primer | Query: 'stimulation parameters coil' — found 1 matching table(s), best score 0.3 |
| table-markdown-quality | hallett-tms-primer | Table markdown has pipes and 14 lines. Preview: **Table 1. Summary of Noninvasiv |
| table-search-recall | laird-fick-polyps | Query: 'polyp location demographics patient' — found 5 matching table(s), best s |
| table-markdown-quality | laird-fick-polyps | Table markdown has pipes and 59 lines. Preview: **Table 5 Distribution of polyps |
| table-search-recall | helm-coregulation | Query: 'dyadic physiological model fit comparison' — found 1 matching table(s),  |
| table-markdown-quality | helm-coregulation | Table markdown has pipes and 34 lines. Preview: **Table 1 Comparisons of Model F |
| table-search-recall | roland-emg-filter | Query: 'power consumption filter' — found 5 matching table(s), best score 0.424, |
| table-markdown-quality | roland-emg-filter | Table markdown has pipes and 23 lines. Preview: **Table 7. Effect of reducing sa |
| table-search-recall | yang-ppv-meta | Query: 'sensitivity specificity diagnostic' — found 3 matching table(s), best sc |
| table-markdown-quality | yang-ppv-meta | Table markdown has pipes and 42 lines. Preview: **Table 3 Diagnostic performance |
| table-search-recall | fortune-impedance | Query: 'component values circuit parasitic inductance' — found 5 matching table( |
| table-markdown-quality | fortune-impedance | Table markdown has pipes and 31 lines. Preview: **Table 1 Component values used  |
| table-search-recall | reyes-lf-hrv | Query: 'frequency domain sympathetic vagal HRV measures' — found 5 matching tabl |
| table-markdown-quality | reyes-lf-hrv | Table markdown has pipes and 65 lines. Preview: **Table 4. Correlations of HRV P |
| figure-search-recall | active-inference-tutorial | Query: 'generative model graphical' — found 8 matching figure(s), best score 0.5 |
| figure-search-recall | huang-emd-1998 | Query: 'intrinsic mode function' — found 8 matching figure(s), best score 0.501, |
| figure-search-recall | hallett-tms-primer | Query: 'magnetic field coil' — found 5 matching figure(s), best score 0.482, cap |
| figure-search-recall | helm-coregulation | Query: 'physiological linkage interaction pattern' — found 2 matching figure(s), |
| figure-search-recall | roland-emg-filter | Query: 'filter frequency response' — found 10 matching figure(s), best score 0.4 |
| figure-search-recall | friston-life | Query: 'Markov blanket' — found 4 matching figure(s), best score 0.553, caption: |
| figure-search-recall | yang-ppv-meta | Query: 'sensitivity specificity receiver operating' — found 1 matching figure(s) |
| figure-search-recall | fortune-impedance | Query: 'electrode skin contact amplifier schematic' — found 7 matching figure(s) |
| figure-search-recall | reyes-lf-hrv | Query: 'baroreflex autonomic nervous system regulation' — found 2 matching figur |
| author-filter | active-inference-tutorial | Filter author='smith' — target paper found (43 total results after filter) |
| author-filter | huang-emd-1998 | Filter author='huang' — target paper found (50 total results after filter) |
| author-filter | hallett-tms-primer | Filter author='hallett' — target paper found (50 total results after filter) |
| author-filter | laird-fick-polyps | Filter author='laird' — target paper found (31 total results after filter) |
| author-filter | helm-coregulation | Filter author='helm' — target paper found (19 total results after filter) |
| author-filter | roland-emg-filter | Filter author='roland' — target paper found (47 total results after filter) |
| author-filter | friston-life | Filter author='friston' — target paper found (43 total results after filter) |
| author-filter | yang-ppv-meta | Filter author='yang' — target paper found (33 total results after filter) |
| author-filter | fortune-impedance | Filter author='fortune' — target paper found (43 total results after filter) |
| author-filter | reyes-lf-hrv | Filter author='reyes' — target paper found (46 total results after filter) |
| year-filter-accuracy | all | Year filter >=2015: 0 papers from before 2015 leaked through (total results: 50) |
| context-expansion | active-inference-tutorial | Context expansion: before=2, after=2, full_context=7924 chars |
| context-adds-value | active-inference-tutorial | Full context (7924 chars) vs hit (1583 chars) |
| context-expansion | huang-emd-1998 | Context expansion: before=4, after=3, full_context=13571 chars |
| context-adds-value | huang-emd-1998 | Full context (13571 chars) vs hit (1591 chars) |
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
| boundary-chunk-first | active-inference-tutorial | Adjacent chunks for first chunk: got 13 (expected >=1) |
| boundary-chunk-last | active-inference-tutorial | Adjacent chunks for last chunk (idx=336): got 3 |
| boundary-chunk-first | huang-emd-1998 | Adjacent chunks for first chunk: got 9 (expected >=1) |
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
