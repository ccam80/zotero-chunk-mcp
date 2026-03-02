# Stress Test Report: zotero-chunk-rag

**Date**: 2026-03-02 10:33
**Corpus**: 20 papers from live Zotero library

## Executive Summary

- **Total tests**: 564
- **Passed**: 512 (91%)
- **Failed**: 52
- **Major failures**: 24

> **VERDICT**: This tool is NOT reliable for production research use.
> A researcher depending on this tool WILL miss important results.

## Performance

| Operation | Time |
|-----------|------|
| Total indexing | 2086.2s |

## Extraction Quality per Paper

| Paper | Pages | Sections | Tables | Figures | Grade | Issues |
|-------|-------|----------|--------|---------|-------|--------|
| active-inference-tutorial | 60 | 16 | 7 | 17 | B | 1 figs missing; 9 unknown sections; no abstract detected |
| huang-emd-1998 | 96 | 28 | 0 | 85 | A | 21 unknown sections; no abstract detected |
| hallett-tms-primer | 13 | 25 | 1 | 8 | A | 22 unknown sections; no abstract detected |
| laird-fick-polyps | 7 | 20 | 5 | 3 | A | 7 unknown sections |
| helm-coregulation | 10 | 11 | 2 | 2 | A | 4 unknown sections; no abstract detected |
| roland-emg-filter | 24 | 23 | 7 | 17 | A | 2 unknown sections |
| friston-life | 12 | 6 | 1 | 5 | A | 3 unknown sections; no abstract detected |
| yang-ppv-meta | 13 | 18 | 3 | 6 | A | 5 unknown sections |
| fortune-impedance | 11 | 10 | 6 | 7 | A | 3 unknown sections; no abstract detected |
| reyes-lf-hrv | 11 | 12 | 5 | 2 | A | 8 unknown sections |
| osterrieder-ach-kinetics- | 9 | 22 | 1 | 7 | A | 16 unknown sections |
| linssen-emg-fatigue-1993 | 8 | 7 | 3 | 1 | B | 1 figs missing; 3 unknown sections; no abstract detected |
| berntson-hrv-origins-1997 | 27 | 36 | 0 | 0 | A | 31 unknown sections |
| ats-ers-respiratory-muscl | 107 | 313 | 18 | 55 | A | 271 unknown sections; no abstract detected |
| schroeder-hrv-repeatabili | 10 | 8 | 5 | 0 | A | none |
| raez-emg-techniques-2006 | 25 | 21 | 4 | 7 | B | 4 figs missing; 13 unknown sections |
| daly-hodgkin-huxley-bayes | 20 | 10 | 3 | 4 | A | no abstract detected |
| shaffer-hrv-norms-2017 | 17 | 35 | 7 | 0 | A | 31 unknown sections; no abstract detected |
| charlton-wearable-ppg-202 | 27 | 41 | 3 | 4 | A | 39 unknown sections |
| flett-wearable-hr-accurac | 19 | 1 | 6 | 12 | A | 1 unknown sections; no abstract detected |

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

### ! [MINOR] section-detection — helm-coregulation

Expected section 'introduction' — MISSING. Got: ['conclusion', 'discussion', 'methods', 'preamble', 'references', 'results', 'unknown']

### ! [MINOR] abstract-detection — helm-coregulation

Abstract NOT detected

### ! [MINOR] abstract-detection — friston-life

Abstract NOT detected

### ! [MINOR] abstract-detection — fortune-impedance

Abstract NOT detected

### ! [MINOR] section-detection — reyes-lf-hrv

Expected section 'introduction' — MISSING. Got: ['abstract', 'conclusion', 'methods', 'references', 'unknown']

### !!! [MAJOR] caption-number-continuity — osterrieder-ach-kinetics-1980

Figure gaps: ['5'], Table gaps: none

### ! [MINOR] section-detection — linssen-emg-fatigue-1993

Expected section 'introduction' — MISSING. Got: ['discussion', 'methods', 'preamble', 'references', 'results', 'unknown']

### !!! [MAJOR] missing-figures — linssen-emg-fatigue-1993

1 figure(s) have captions but no extracted image. Captions found: 2, figures extracted: 1

### !!! [MAJOR] unmatched-captions — linssen-emg-fatigue-1993

Caption numbers found on pages but not matched to any extracted object: figures=['2'], tables=none

### ! [MINOR] abstract-detection — linssen-emg-fatigue-1993

Abstract NOT detected

### !!! [MAJOR] table-dimensions-sanity — linssen-emg-fatigue-1993

1 tables are 1x1 (degenerate)

### ! [MINOR] section-detection — berntson-hrv-origins-1997

Expected section 'introduction' — MISSING. Got: ['abstract', 'methods', 'unknown']

### !!! [MAJOR] table-extraction — berntson-hrv-origins-1997

Expected tables — found 0

### !!! [MAJOR] figure-extraction — berntson-hrv-origins-1997

Expected figures — found 0

### ! [MINOR] table-content-quality — ats-ers-respiratory-muscle-2002/table-0

Table 0: 25/50 cells non-empty (50%). Caption: 'TABLE 1. PRESSURES FOR BASIC RESPIRATORY MECHANICS'

### !!! [MAJOR] unmatched-captions — ats-ers-respiratory-muscle-2002

Caption numbers found on pages but not matched to any extracted object: figures=['10', '12', '14'], tables=none

### ! [MINOR] abstract-detection — ats-ers-respiratory-muscle-2002

Abstract NOT detected

### ! [MINOR] section-detection — schroeder-hrv-repeatability-2004

Expected section 'introduction' — MISSING. Got: ['abstract', 'appendix', 'discussion', 'methods', 'preamble', 'references', 'results']

### !!! [MAJOR] figure-extraction — schroeder-hrv-repeatability-2004

Expected figures — found 0

### !!! [MAJOR] missing-figures — raez-emg-techniques-2006

4 figure(s) have captions but no extracted image. Captions found: 11, figures extracted: 7

### !!! [MAJOR] unmatched-captions — raez-emg-techniques-2006

Caption numbers found on pages but not matched to any extracted object: figures=['2', '3', '5', '8'], tables=none

### !!! [MAJOR] caption-number-continuity — raez-emg-techniques-2006

Figure gaps: none, Table gaps: ['1']

### !!! [MAJOR] duplicate-captions — raez-emg-techniques-2006

1 duplicate caption(s) found

### ! [MINOR] abstract-detection — daly-hodgkin-huxley-bayesian-2015

Abstract NOT detected

### !!! [MAJOR] caption-number-continuity — daly-hodgkin-huxley-bayesian-2015

Figure gaps: ['1', '3', '4', '5', '6'], Table gaps: none

### ! [MINOR] section-detection — shaffer-hrv-norms-2017

Expected section 'introduction' — MISSING. Got: ['appendix', 'conclusion', 'methods', 'preamble', 'references', 'unknown']

### !!! [MAJOR] figure-extraction — shaffer-hrv-norms-2017

Expected figures — found 0

### ! [MINOR] abstract-detection — shaffer-hrv-norms-2017

Abstract NOT detected

### ! [MINOR] section-detection — charlton-wearable-ppg-2022

Expected section 'introduction' — MISSING. Got: ['abstract', 'methods', 'unknown']

### ! [MINOR] section-detection — charlton-wearable-ppg-2022

Expected section 'conclusion' — MISSING. Got: ['abstract', 'methods', 'unknown']

### ! [MINOR] section-detection — flett-wearable-hr-accuracy-2025

Expected section 'introduction' — MISSING. Got: ['unknown']

### !!! [MAJOR] section-detection — flett-wearable-hr-accuracy-2025

Expected section 'methods' — MISSING. Got: ['unknown']

### !!! [MAJOR] section-detection — flett-wearable-hr-accuracy-2025

Expected section 'results' — MISSING. Got: ['unknown']

### ! [MINOR] section-detection — flett-wearable-hr-accuracy-2025

Expected section 'discussion' — MISSING. Got: ['unknown']

### !!! [MAJOR] unmatched-captions — flett-wearable-hr-accuracy-2025

Caption numbers found on pages but not matched to any extracted object: figures=['12'], tables=none

### ! [MINOR] abstract-detection — flett-wearable-hr-accuracy-2025

Abstract NOT detected

### !!! [MAJOR] table-dimensions-sanity — flett-wearable-hr-accuracy-2025

1 tables are 1x1 (degenerate)

### ! [MINOR] chunk-count-sanity — flett-wearable-hr-accuracy-2025

27 chunks for 19 pages (expected >= 38)

### ! [MINOR] semantic-search-ranking — berntson-hrv-origins-1997

Ranked 4/10 for its own core content query

### !!! [MAJOR] semantic-search-ranking — shaffer-hrv-norms-2017

Ranked 10/10 for its own core content query

### !!! [MAJOR] table-search-recall — helm-coregulation

Query: 'correlation coefficient RSA' — NOT FOUND. Got: ['Repeatability of heart rate va', 'Repeatability of heart rate va', 'Repeatability of heart rate va']

### !!! [MAJOR] figure-search-recall — reyes-lf-hrv

Query: 'heart rate variability' — NOT FOUND in top 10. Got: ['Assessing the Accuracy of a Wr', 'Assessing the Accuracy of a Wr', 'Assessing the Accuracy of a Wr']

### !!! [MAJOR] figure-search-recall — daly-hodgkin-huxley-bayesian-2015

Query: 'posterior distribution action potential' — NOT FOUND in top 10. Got: ['A step-by-step tutorial on act', 'A step-by-step tutorial on act', 'A step-by-step tutorial on act']

## Passes

| Test | Paper | Detail |
|------|-------|--------|
| section-detection | active-inference-tutorial | Expected section 'introduction' — FOUND |
| section-detection | active-inference-tutorial | Expected section 'conclusion' — FOUND |
| table-extraction | active-inference-tutorial | Expected tables — found 7 |
| table-content-quality | active-inference-tutorial/table-0 | Table 0: 18/18 cells non-empty (100%). Caption: 'Table 1 Model variables.' |
| table-content-quality | active-inference-tutorial/table-1 | Table 1: 6/6 cells non-empty (100%). Caption: 'Table 1 (continued).' |
| table-content-quality | active-inference-tutorial/table-2 | Table 2: 12/12 cells non-empty (100%). Caption: 'Table 2 Matrix formulation of e |
| table-content-quality | active-inference-tutorial/table-3 | Table 3: 8/8 cells non-empty (100%). Caption: 'Table 2 (continued).' |
| table-content-quality | active-inference-tutorial/table-4 | Table 4: 4/4 cells non-empty (100%). Caption: 'Table 2 (continued).' |
| table-content-quality | active-inference-tutorial/table-5 | Table 5: 44/44 cells non-empty (100%). Caption: 'Table 3 Output fields for spm_M |
| table-content-quality | active-inference-tutorial/table-6 | Table 6: 16/16 cells non-empty (100%). Caption: 'Table 3 (continued).' |
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
| completeness-grade | huang-emd-1998 | Grade: A / Figs: 85 found / 83 captioned / 0 missing / Tables: 0 found / 0 capti |
| table-dimensions-sanity | huang-emd-1998 | 0 tables are 1x1 (degenerate) |
| caption-encoding-quality | huang-emd-1998 | 0 captions with encoding artifacts |
| caption-number-continuity | huang-emd-1998 | Figure gaps: none, Table gaps: none |
| duplicate-captions | huang-emd-1998 | 0 duplicate caption(s) found |
| figure-images-saved | huang-emd-1998 | 85/85 figure images saved to disk |
| table-extraction | hallett-tms-primer | Expected tables — found 1 |
| table-content-quality | hallett-tms-primer/table-0 | Table 0: 12/12 cells non-empty (100%). Caption: 'Table 1. Summary of Noninvasive |
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
| table-content-quality | laird-fick-polyps/table-0 | Table 0: 30/30 cells non-empty (100%). Caption: 'Table 1 Distribution of Sex by  |
| table-content-quality | laird-fick-polyps/table-1 | Table 1: 75/75 cells non-empty (100%). Caption: 'Table 2 Distribution of Sex by  |
| table-content-quality | laird-fick-polyps/table-2 | Table 2: 25/25 cells non-empty (100%). Caption: 'Table 3 Prevalence of sessile s |
| table-content-quality | laird-fick-polyps/table-3 | Table 3: 52/70 cells non-empty (74%). Caption: 'Table 4 Odds ratios and 95 % con |
| table-content-quality | laird-fick-polyps/table-4 | Table 4: 59/60 cells non-empty (98%). Caption: 'Table 5 Distribution of polyps b |
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
| table-content-quality | helm-coregulation/table-0 | Table 0: 35/35 cells non-empty (100%). Caption: 'Table 1. Comparisons of Model F |
| table-content-quality | helm-coregulation/table-1 | Table 1: 62/72 cells non-empty (86%). Caption: 'Table 2. Coefficients From Best- |
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
| table-extraction | roland-emg-filter | Expected tables — found 7 |
| table-content-quality | roland-emg-filter/table-0 | Table 0: 81/81 cells non-empty (100%). Caption: 'Table 1. Floating-point comb fi |
| table-content-quality | roland-emg-filter/table-1 | Table 1: 126/126 cells non-empty (100%). Caption: 'Table 2. Floating-point highp |
| table-content-quality | roland-emg-filter/table-2 | Table 2: 10/10 cells non-empty (100%). Caption: 'Table 3. Poles of comb filters  |
| table-content-quality | roland-emg-filter/table-3 | Table 3: 27/30 cells non-empty (90%). Caption: 'Table 4. Poles of highpass filte |
| table-content-quality | roland-emg-filter/table-4 | Table 4: 10/10 cells non-empty (100%). Caption: 'Table 5. Runtime per sample of  |
| table-content-quality | roland-emg-filter/table-5 | Table 5: 10/10 cells non-empty (100%). Caption: 'Table 6. Comparison of runtime  |
| table-content-quality | roland-emg-filter/table-6 | Table 6: 20/20 cells non-empty (100%). Caption: 'Table 7. Effect of reducing sam |
| figure-extraction | roland-emg-filter | Expected figures — found 17 |
| figure-caption-rate | roland-emg-filter | 17/17 figures have captions (100%) |
| completeness-grade | roland-emg-filter | Grade: A / Figs: 17 found / 17 captioned / 0 missing / Tables: 7 found / 7 capti |
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
| table-extraction | yang-ppv-meta | Expected tables — found 3 |
| table-content-quality | yang-ppv-meta/table-0 | Table 0: 154/154 cells non-empty (100%). Caption: 'Table 1 Selected spectrum cha |
| table-content-quality | yang-ppv-meta/table-1 | Table 1: 308/308 cells non-empty (100%). Caption: 'Table 2 Selected methodologic |
| table-content-quality | yang-ppv-meta/table-2 | Table 2: 242/242 cells non-empty (100%). Caption: 'Table 3 Diagnostic performanc |
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
| table-content-quality | fortune-impedance/table-0 | Table 0: 21/21 cells non-empty (100%). Caption: 'Table 1 Component values used f |
| table-content-quality | fortune-impedance/table-1 | Table 1: 20/20 cells non-empty (100%). Caption: 'Table 2 Error between the custo |
| table-content-quality | fortune-impedance/table-2 | Table 2: 55/55 cells non-empty (100%). Caption: 'Table 3. Error between the cust |
| table-content-quality | fortune-impedance/table-3 | Table 3: 233/245 cells non-empty (95%). Caption: 'Table 4. Electrode–skin impeda |
| table-content-quality | fortune-impedance/table-4 | Table 4: 15/15 cells non-empty (100%). Caption: 'Table 5 Mean electrode–skin imp |
| table-content-quality | fortune-impedance/table-5 | Table 5: 15/15 cells non-empty (100%). Caption: 'Table 6 Mean and standard devia |
| figure-extraction | fortune-impedance | Expected figures — found 7 |
| figure-caption-rate | fortune-impedance | 7/7 figures have captions (100%) |
| completeness-grade | fortune-impedance | Grade: A / Figs: 7 found / 7 captioned / 0 missing / Tables: 6 found / 6 caption |
| content-readability | fortune-impedance | 0 tables with readability issues |
| table-dimensions-sanity | fortune-impedance | 0 tables are 1x1 (degenerate) |
| caption-encoding-quality | fortune-impedance | 0 captions with encoding artifacts |
| caption-number-continuity | fortune-impedance | Figure gaps: none, Table gaps: none |
| duplicate-captions | fortune-impedance | 0 duplicate caption(s) found |
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
| section-detection | osterrieder-ach-kinetics-1980 | Expected section 'introduction' — FOUND |
| figure-extraction | osterrieder-ach-kinetics-1980 | Expected figures — found 7 |
| figure-caption-rate | osterrieder-ach-kinetics-1980 | 7/7 figures have captions (100%) |
| completeness-grade | osterrieder-ach-kinetics-1980 | Grade: A / Figs: 7 found / 7 captioned / 0 missing / Tables: 1 found / 1 caption |
| abstract-detection | osterrieder-ach-kinetics-1980 | Abstract detected |
| content-readability | osterrieder-ach-kinetics-1980 | 0 tables with readability issues |
| table-dimensions-sanity | osterrieder-ach-kinetics-1980 | 0 tables are 1x1 (degenerate) |
| caption-encoding-quality | osterrieder-ach-kinetics-1980 | 0 captions with encoding artifacts |
| duplicate-captions | osterrieder-ach-kinetics-1980 | 0 duplicate caption(s) found |
| chunk-count-sanity | osterrieder-ach-kinetics-1980 | 37 chunks for 9 pages (expected >= 18) |
| figure-images-saved | osterrieder-ach-kinetics-1980 | 7/7 figure images saved to disk |
| section-detection | linssen-emg-fatigue-1993 | Expected section 'methods' — FOUND |
| section-detection | linssen-emg-fatigue-1993 | Expected section 'results' — FOUND |
| section-detection | linssen-emg-fatigue-1993 | Expected section 'discussion' — FOUND |
| table-extraction | linssen-emg-fatigue-1993 | Expected tables — found 3 |
| table-content-quality | linssen-emg-fatigue-1993/table-1 | Table 1: 69/108 cells non-empty (64%). Caption: 'Table 1. Results and reproducib |
| table-content-quality | linssen-emg-fatigue-1993/table-2 | Table 2: 50/50 cells non-empty (100%). Caption: 'Table 2. Correlations.' |
| figure-extraction | linssen-emg-fatigue-1993 | Expected figures — found 1 |
| figure-caption-rate | linssen-emg-fatigue-1993 | 1/1 figures have captions (100%) |
| completeness-grade | linssen-emg-fatigue-1993 | Grade: B / Figs: 1 found / 2 captioned / 1 missing / Tables: 3 found / 2 caption |
| content-readability | linssen-emg-fatigue-1993 | 0 tables with readability issues |
| caption-encoding-quality | linssen-emg-fatigue-1993 | 0 captions with encoding artifacts |
| caption-number-continuity | linssen-emg-fatigue-1993 | Figure gaps: none, Table gaps: none |
| duplicate-captions | linssen-emg-fatigue-1993 | 0 duplicate caption(s) found |
| chunk-count-sanity | linssen-emg-fatigue-1993 | 32 chunks for 8 pages (expected >= 16) |
| figure-images-saved | linssen-emg-fatigue-1993 | 1/1 figure images saved to disk |
| completeness-grade | berntson-hrv-origins-1997 | Grade: A / Figs: 0 found / 0 captioned / 0 missing / Tables: 0 found / 0 caption |
| abstract-detection | berntson-hrv-origins-1997 | Abstract detected |
| table-dimensions-sanity | berntson-hrv-origins-1997 | 0 tables are 1x1 (degenerate) |
| caption-encoding-quality | berntson-hrv-origins-1997 | 0 captions with encoding artifacts |
| caption-number-continuity | berntson-hrv-origins-1997 | Figure gaps: none, Table gaps: none |
| duplicate-captions | berntson-hrv-origins-1997 | 0 duplicate caption(s) found |
| chunk-count-sanity | berntson-hrv-origins-1997 | 150 chunks for 27 pages (expected >= 54) |
| section-detection | ats-ers-respiratory-muscle-2002 | Expected section 'introduction' — FOUND |
| table-extraction | ats-ers-respiratory-muscle-2002 | Expected tables — found 18 |
| table-content-quality | ats-ers-respiratory-muscle-2002/table-1 | Table 1: 62/84 cells non-empty (74%). Caption: 'TABLE 2. REFERENCE NORMAL RANGES |
| table-content-quality | ats-ers-respiratory-muscle-2002/table-2 | Table 2: 24/24 cells non-empty (100%). Caption: 'TABLE 3. TRANSDIAPHRAGMATIC PRE |
| table-content-quality | ats-ers-respiratory-muscle-2002/table-3 | Table 3: 75/87 cells non-empty (86%). Caption: 'TABLE 4. TWITCH TRANSDIAPHRAGMAT |
| table-content-quality | ats-ers-respiratory-muscle-2002/table-4 | Table 4: 10/12 cells non-empty (83%). Caption: 'TABLE 1. TYPES OF RECORDING ELEC |
| table-content-quality | ats-ers-respiratory-muscle-2002/table-5 | Table 5: 20/27 cells non-empty (74%). Caption: 'TABLE 2. APPLICATIONS FOR RESPIR |
| table-content-quality | ats-ers-respiratory-muscle-2002/table-6 | Table 6: 10/12 cells non-empty (83%). Caption: 'TABLE 3. TYPES OF RESPIRATORY MU |
| table-content-quality | ats-ers-respiratory-muscle-2002/table-7 | Table 7: 9/9 cells non-empty (100%). Caption: 'TABLE 4. APPLICATIONS OF RESPIRAT |
| table-content-quality | ats-ers-respiratory-muscle-2002/table-8 | Table 8: 30/30 cells non-empty (100%). Caption: 'TABLE 1. PREDICTED VALUES FOR M |
| table-content-quality | ats-ers-respiratory-muscle-2002/table-9 | Table 9: 24/24 cells non-empty (100%). Caption: 'TABLE 2. PREDICTED VALUES FOR I |
| table-content-quality | ats-ers-respiratory-muscle-2002/table-10 | Table 10: 12/12 cells non-empty (100%). Caption: 'TABLE 1. RADIOGRAPHY' |
| table-content-quality | ats-ers-respiratory-muscle-2002/table-11 | Table 11: 18/28 cells non-empty (64%). Caption: 'TABLE 2. ULTRASOUND' |
| table-content-quality | ats-ers-respiratory-muscle-2002/table-12 | Table 12: 60/102 cells non-empty (59%). Caption: 'TABLE 1. NORMAL VALUES OF CHES |
| table-content-quality | ats-ers-respiratory-muscle-2002/table-13 | Table 13: 80/144 cells non-empty (56%). Caption: 'TABLE 2. NORMAL VALUES OF MAXI |
| table-content-quality | ats-ers-respiratory-muscle-2002/table-14 | Table 14: 66/98 cells non-empty (67%). Caption: 'TABLE 3. NORMAL VALUES OF OCCLU |
| table-content-quality | ats-ers-respiratory-muscle-2002/table-15 | Table 15: 14/15 cells non-empty (93%). Caption: 'TABLE 4. AXIAL DIAPHRAGM DISPLA |
| table-content-quality | ats-ers-respiratory-muscle-2002/table-16 | Table 16: 60/60 cells non-empty (100%). Caption: 'TABLE 1. ACCURACY OF MAXIMAL I |
| table-content-quality | ats-ers-respiratory-muscle-2002/table-17 | Table 17: 6/6 cells non-empty (100%). Caption: 'TABLE 2. LIKELIHOOD OF SUCCESSFU |
| figure-extraction | ats-ers-respiratory-muscle-2002 | Expected figures — found 55 |
| figure-caption-rate | ats-ers-respiratory-muscle-2002 | 55/55 figures have captions (100%) |
| completeness-grade | ats-ers-respiratory-muscle-2002 | Grade: A / Figs: 55 found / 14 captioned / 0 missing / Tables: 18 found / 4 capt |
| content-readability | ats-ers-respiratory-muscle-2002 | 0 tables with readability issues |
| table-dimensions-sanity | ats-ers-respiratory-muscle-2002 | 0 tables are 1x1 (degenerate) |
| caption-encoding-quality | ats-ers-respiratory-muscle-2002 | 0 captions with encoding artifacts |
| caption-number-continuity | ats-ers-respiratory-muscle-2002 | Figure gaps: none, Table gaps: none |
| duplicate-captions | ats-ers-respiratory-muscle-2002 | 0 duplicate caption(s) found |
| chunk-count-sanity | ats-ers-respiratory-muscle-2002 | 618 chunks for 107 pages (expected >= 214) |
| figure-images-saved | ats-ers-respiratory-muscle-2002 | 55/55 figure images saved to disk |
| section-detection | schroeder-hrv-repeatability-2004 | Expected section 'methods' — FOUND |
| section-detection | schroeder-hrv-repeatability-2004 | Expected section 'results' — FOUND |
| section-detection | schroeder-hrv-repeatability-2004 | Expected section 'discussion' — FOUND |
| table-extraction | schroeder-hrv-repeatability-2004 | Expected tables — found 5 |
| table-content-quality | schroeder-hrv-repeatability-2004/table-0 | Table 0: 56/56 cells non-empty (100%). Caption: 'Table 1. Means for Common Heart |
| table-content-quality | schroeder-hrv-repeatability-2004/table-1 | Table 1: 64/64 cells non-empty (100%). Caption: 'Table 2. Intraclass Correlation |
| table-content-quality | schroeder-hrv-repeatability-2004/table-2 | Table 2: 32/32 cells non-empty (100%). Caption: 'Table 3. Intraclass Correlation |
| table-content-quality | schroeder-hrv-repeatability-2004/table-3 | Table 3: 86/96 cells non-empty (90%). Caption: 'Table 4. Components of Measureme |
| table-content-quality | schroeder-hrv-repeatability-2004/table-4 | Table 4: 48/48 cells non-empty (100%). Caption: 'Table 5. Correlation Coefficien |
| completeness-grade | schroeder-hrv-repeatability-2004 | Grade: A / Figs: 0 found / 0 captioned / 0 missing / Tables: 5 found / 5 caption |
| abstract-detection | schroeder-hrv-repeatability-2004 | Abstract detected |
| content-readability | schroeder-hrv-repeatability-2004 | 0 tables with readability issues |
| table-dimensions-sanity | schroeder-hrv-repeatability-2004 | 0 tables are 1x1 (degenerate) |
| caption-encoding-quality | schroeder-hrv-repeatability-2004 | 0 captions with encoding artifacts |
| caption-number-continuity | schroeder-hrv-repeatability-2004 | Figure gaps: none, Table gaps: none |
| duplicate-captions | schroeder-hrv-repeatability-2004 | 0 duplicate caption(s) found |
| chunk-count-sanity | schroeder-hrv-repeatability-2004 | 40 chunks for 10 pages (expected >= 20) |
| section-detection | raez-emg-techniques-2006 | Expected section 'introduction' — FOUND |
| section-detection | raez-emg-techniques-2006 | Expected section 'conclusion' — FOUND |
| table-extraction | raez-emg-techniques-2006 | Expected tables — found 4 |
| table-content-quality | raez-emg-techniques-2006/table-0 | Table 0: 12/12 cells non-empty (100%). Caption: 'Table 2: Diagnosis performance  |
| table-content-quality | raez-emg-techniques-2006/table-1 | Table 1: 6/6 cells non-empty (100%). Caption: 'Table 3: Typical EMG classificati |
| table-content-quality | raez-emg-techniques-2006/table-2 | Table 2: 14/14 cells non-empty (100%). Caption: 'Table 4: Summary of major metho |
| table-content-quality | raez-emg-techniques-2006/table-3 | Table 3: 14/14 cells non-empty (100%). Caption: 'Table 4: Summary of major metho |
| figure-extraction | raez-emg-techniques-2006 | Expected figures — found 7 |
| figure-caption-rate | raez-emg-techniques-2006 | 7/7 figures have captions (100%) |
| completeness-grade | raez-emg-techniques-2006 | Grade: B / Figs: 7 found / 11 captioned / 4 missing / Tables: 4 found / 3 captio |
| abstract-detection | raez-emg-techniques-2006 | Abstract detected |
| content-readability | raez-emg-techniques-2006 | 0 tables with readability issues |
| table-dimensions-sanity | raez-emg-techniques-2006 | 0 tables are 1x1 (degenerate) |
| caption-encoding-quality | raez-emg-techniques-2006 | 0 captions with encoding artifacts |
| chunk-count-sanity | raez-emg-techniques-2006 | 94 chunks for 25 pages (expected >= 50) |
| figure-images-saved | raez-emg-techniques-2006 | 7/7 figure images saved to disk |
| section-detection | daly-hodgkin-huxley-bayesian-2015 | Expected section 'introduction' — FOUND |
| section-detection | daly-hodgkin-huxley-bayesian-2015 | Expected section 'methods' — FOUND |
| section-detection | daly-hodgkin-huxley-bayesian-2015 | Expected section 'results' — FOUND |
| section-detection | daly-hodgkin-huxley-bayesian-2015 | Expected section 'discussion' — FOUND |
| table-extraction | daly-hodgkin-huxley-bayesian-2015 | Expected tables — found 3 |
| table-content-quality | daly-hodgkin-huxley-bayesian-2015/table-0 | Table 0: 18/18 cells non-empty (100%). Caption: 'Table 1. Specification of prior |
| table-content-quality | daly-hodgkin-huxley-bayesian-2015/table-1 | Table 1: 28/30 cells non-empty (93%). Caption: 'Table 2. Summary statistics of A |
| table-content-quality | daly-hodgkin-huxley-bayesian-2015/table-2 | Table 2: 48/50 cells non-empty (96%). Caption: 'Table 3. Summary statistics of A |
| figure-extraction | daly-hodgkin-huxley-bayesian-2015 | Expected figures — found 4 |
| figure-caption-rate | daly-hodgkin-huxley-bayesian-2015 | 4/4 figures have captions (100%) |
| completeness-grade | daly-hodgkin-huxley-bayesian-2015 | Grade: A / Figs: 4 found / 4 captioned / 0 missing / Tables: 3 found / 3 caption |
| content-readability | daly-hodgkin-huxley-bayesian-2015 | 0 tables with readability issues |
| table-dimensions-sanity | daly-hodgkin-huxley-bayesian-2015 | 0 tables are 1x1 (degenerate) |
| caption-encoding-quality | daly-hodgkin-huxley-bayesian-2015 | 0 captions with encoding artifacts |
| duplicate-captions | daly-hodgkin-huxley-bayesian-2015 | 0 duplicate caption(s) found |
| chunk-count-sanity | daly-hodgkin-huxley-bayesian-2015 | 77 chunks for 20 pages (expected >= 40) |
| figure-images-saved | daly-hodgkin-huxley-bayesian-2015 | 4/4 figure images saved to disk |
| table-extraction | shaffer-hrv-norms-2017 | Expected tables — found 7 |
| table-content-quality | shaffer-hrv-norms-2017/table-0 | Table 0: 6/6 cells non-empty (100%). Caption: 'TABLE 1 / HRV time-domain measure |
| table-content-quality | shaffer-hrv-norms-2017/table-1 | Table 1: 33/33 cells non-empty (100%). Caption: 'TABLE 2 / HRV frequency-domain  |
| table-content-quality | shaffer-hrv-norms-2017/table-2 | Table 2: 22/27 cells non-empty (81%). Caption: 'TABLE 3 / HRV non-linear measure |
| table-content-quality | shaffer-hrv-norms-2017/table-3 | Table 3: 20/20 cells non-empty (100%). Caption: 'TABLE 4 / Ultra-short-term (UST |
| table-content-quality | shaffer-hrv-norms-2017/table-4 | Table 4: 27/28 cells non-empty (96%). Caption: 'TABLE 5 / Short-term ECG norms.' |
| table-content-quality | shaffer-hrv-norms-2017/table-5 | Table 5: 32/32 cells non-empty (100%). Caption: 'TABLE 6 / Nunan et al. (17) sho |
| table-content-quality | shaffer-hrv-norms-2017/table-6 | Table 6: 18/18 cells non-empty (100%). Caption: 'TABLE 7 / Twenty-four-hour HRV  |
| completeness-grade | shaffer-hrv-norms-2017 | Grade: A / Figs: 0 found / 0 captioned / 0 missing / Tables: 7 found / 7 caption |
| content-readability | shaffer-hrv-norms-2017 | 0 tables with readability issues |
| table-dimensions-sanity | shaffer-hrv-norms-2017 | 0 tables are 1x1 (degenerate) |
| caption-encoding-quality | shaffer-hrv-norms-2017 | 0 captions with encoding artifacts |
| caption-number-continuity | shaffer-hrv-norms-2017 | Figure gaps: none, Table gaps: none |
| duplicate-captions | shaffer-hrv-norms-2017 | 0 duplicate caption(s) found |
| chunk-count-sanity | shaffer-hrv-norms-2017 | 96 chunks for 17 pages (expected >= 34) |
| table-extraction | charlton-wearable-ppg-2022 | Expected tables — found 3 |
| table-content-quality | charlton-wearable-ppg-2022/table-0 | Table 0: 60/72 cells non-empty (83%). Caption: 'Table 1 Further Reading on Photo |
| table-content-quality | charlton-wearable-ppg-2022/table-1 | Table 1: 168/170 cells non-empty (99%). Caption: 'Table 2 Datasets of PPG Signal |
| table-content-quality | charlton-wearable-ppg-2022/table-2 | Table 2: 40/40 cells non-empty (100%). Caption: 'Table 3 Selection of Devices Th |
| figure-extraction | charlton-wearable-ppg-2022 | Expected figures — found 4 |
| figure-caption-rate | charlton-wearable-ppg-2022 | 4/4 figures have captions (100%) |
| completeness-grade | charlton-wearable-ppg-2022 | Grade: A / Figs: 4 found / 4 captioned / 0 missing / Tables: 3 found / 3 caption |
| abstract-detection | charlton-wearable-ppg-2022 | Abstract detected |
| content-readability | charlton-wearable-ppg-2022 | 0 tables with readability issues |
| table-dimensions-sanity | charlton-wearable-ppg-2022 | 0 tables are 1x1 (degenerate) |
| caption-encoding-quality | charlton-wearable-ppg-2022 | 0 captions with encoding artifacts |
| caption-number-continuity | charlton-wearable-ppg-2022 | Figure gaps: none, Table gaps: none |
| duplicate-captions | charlton-wearable-ppg-2022 | 0 duplicate caption(s) found |
| chunk-count-sanity | charlton-wearable-ppg-2022 | 146 chunks for 27 pages (expected >= 54) |
| figure-images-saved | charlton-wearable-ppg-2022 | 4/4 figure images saved to disk |
| table-extraction | flett-wearable-hr-accuracy-2025 | Expected tables — found 6 |
| table-content-quality | flett-wearable-hr-accuracy-2025/table-0 | Table 0: 16/16 cells non-empty (100%). Caption: 'Table 1: Participant demographi |
| table-content-quality | flett-wearable-hr-accuracy-2025/table-1 | Table 1: 16/16 cells non-empty (100%). Caption: 'Table 2: Points within 5% error |
| table-content-quality | flett-wearable-hr-accuracy-2025/table-2 | Table 2: 12/12 cells non-empty (100%). Caption: 'Table 3: Increase in points wit |
| table-content-quality | flett-wearable-hr-accuracy-2025/table-3 | Table 3: 12/12 cells non-empty (100%). Caption: 'Table 4: Median absolute differ |
| table-content-quality | flett-wearable-hr-accuracy-2025/table-4 | Table 4: 12/12 cells non-empty (100%). Caption: 'Table 5: Median absolute differ |
| figure-extraction | flett-wearable-hr-accuracy-2025 | Expected figures — found 12 |
| figure-caption-rate | flett-wearable-hr-accuracy-2025 | 12/12 figures have captions (100%) |
| completeness-grade | flett-wearable-hr-accuracy-2025 | Grade: A / Figs: 12 found / 12 captioned / 0 missing / Tables: 6 found / 5 capti |
| content-readability | flett-wearable-hr-accuracy-2025 | 0 tables with readability issues |
| caption-encoding-quality | flett-wearable-hr-accuracy-2025 | 0 captions with encoding artifacts |
| caption-number-continuity | flett-wearable-hr-accuracy-2025 | Figure gaps: none, Table gaps: none |
| duplicate-captions | flett-wearable-hr-accuracy-2025 | 0 duplicate caption(s) found |
| figure-images-saved | flett-wearable-hr-accuracy-2025 | 12/12 figure images saved to disk |
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
| semantic-search-recall | osterrieder-ach-kinetics-1980 | Query: 'acetylcholine potassium channel sinoatrial' — found at rank 1/10 (score  |
| semantic-search-ranking | osterrieder-ach-kinetics-1980 | Ranked 1/10 for its own core content query |
| semantic-search-recall | linssen-emg-fatigue-1993 | Query: 'surface EMG fatigue conduction velocity median fre' — found at rank 1/10 |
| semantic-search-ranking | linssen-emg-fatigue-1993 | Ranked 1/10 for its own core content query |
| semantic-search-recall | berntson-hrv-origins-1997 | Query: 'heart rate variability vagal sympathetic autonomic' — found at rank 4/10 |
| semantic-search-recall | ats-ers-respiratory-muscle-2002 | Query: 'respiratory muscle testing pressure diaphragm phre' — found at rank 1/10 |
| semantic-search-ranking | ats-ers-respiratory-muscle-2002 | Ranked 1/10 for its own core content query |
| semantic-search-recall | schroeder-hrv-repeatability-2004 | Query: 'repeatability heart rate variability measurement v' — found at rank 1/10 |
| semantic-search-ranking | schroeder-hrv-repeatability-2004 | Ranked 1/10 for its own core content query |
| semantic-search-recall | raez-emg-techniques-2006 | Query: 'EMG signal detection processing classification' — found at rank 1/10 (sc |
| semantic-search-ranking | raez-emg-techniques-2006 | Ranked 1/10 for its own core content query |
| semantic-search-recall | daly-hodgkin-huxley-bayesian-2015 | Query: 'Hodgkin Huxley Bayesian approximate posterior repa' — found at rank 1/10 |
| semantic-search-ranking | daly-hodgkin-huxley-bayesian-2015 | Ranked 1/10 for its own core content query |
| semantic-search-recall | shaffer-hrv-norms-2017 | Query: 'heart rate variability SDNN RMSSD norms metrics' — found at rank 10/10 ( |
| semantic-search-recall | charlton-wearable-ppg-2022 | Query: 'photoplethysmography wearable cardiovascular monit' — found at rank 1/10 |
| semantic-search-ranking | charlton-wearable-ppg-2022 | Ranked 1/10 for its own core content query |
| semantic-search-recall | flett-wearable-hr-accuracy-2025 | Query: 'wrist-worn wearable heart rate accuracy activity' — found at rank 1/10 ( |
| semantic-search-ranking | flett-wearable-hr-accuracy-2025 | Ranked 1/10 for its own core content query |
| table-search-recall | active-inference-tutorial | Query: 'algorithm update rules' — found 6 matching table(s), best score 0.277, c |
| table-markdown-quality | active-inference-tutorial | Table markdown has pipes and 8 lines. Preview: **Table 2 Matrix formulation of e |
| table-search-recall | hallett-tms-primer | Query: 'stimulation parameters coil' — found 1 matching table(s), best score 0.3 |
| table-markdown-quality | hallett-tms-primer | Table markdown has pipes and 7 lines. Preview: **Table 1. Summary of Noninvasive |
| table-search-recall | laird-fick-polyps | Query: 'polyp location demographics patient' — found 5 matching table(s), best s |
| table-markdown-quality | laird-fick-polyps | Table markdown has pipes and 15 lines. Preview: **Table 5 Distribution of polyps |
| table-search-recall | roland-emg-filter | Query: 'power consumption filter' — found 7 matching table(s), best score 0.433, |
| table-markdown-quality | roland-emg-filter | Table markdown has pipes and 8 lines. Preview: **Table 7. Effect of reducing sam |
| table-search-recall | yang-ppv-meta | Query: 'sensitivity specificity diagnostic' — found 2 matching table(s), best sc |
| table-markdown-quality | yang-ppv-meta | Table markdown has pipes and 27 lines. Preview: **Table 3 Diagnostic performance |
| table-search-recall | fortune-impedance | Query: 'impedance measurement electrode' — found 6 matching table(s), best score |
| table-markdown-quality | fortune-impedance | Table markdown has pipes and 14 lines. Preview: **Table 3. Error between the cus |
| table-search-recall | reyes-lf-hrv | Query: 'autonomic measures' — found 3 matching table(s), best score 0.450, capti |
| table-markdown-quality | reyes-lf-hrv | Table markdown has pipes and 21 lines. Preview: **Table 4. Correlations of HRV P |
| table-search-recall | linssen-emg-fatigue-1993 | Query: 'median frequency conduction velocity' — found 1 matching table(s), best  |
| table-markdown-quality | linssen-emg-fatigue-1993 | Table markdown has pipes and 32 lines. Preview: **Table 1. Results and reproduci |
| table-search-recall | ats-ers-respiratory-muscle-2002 | Query: 'respiratory pressure measurement' — found 10 matching table(s), best sco |
| table-markdown-quality | ats-ers-respiratory-muscle-2002 | Table markdown has pipes and 28 lines. Preview: **TABLE 1. PRESSURES FOR BASIC R |
| table-search-recall | schroeder-hrv-repeatability-2004 | Query: 'variance reproducibility heart rate' — found 5 matching table(s), best s |
| table-markdown-quality | schroeder-hrv-repeatability-2004 | Table markdown has pipes and 17 lines. Preview: **Table 5. Correlation Coefficie |
| table-search-recall | raez-emg-techniques-2006 | Query: 'EMG classification features' — found 2 matching table(s), best score 0.6 |
| table-markdown-quality | raez-emg-techniques-2006 | Table markdown has pipes and 6 lines. Preview: **Table 3: Typical EMG classifica |
| table-search-recall | daly-hodgkin-huxley-bayesian-2015 | Query: 'parameter prior posterior estimate' — found 3 matching table(s), best sc |
| table-markdown-quality | daly-hodgkin-huxley-bayesian-2015 | Table markdown has pipes and 9 lines. Preview: **Table 1. Specification of prior |
| table-search-recall | shaffer-hrv-norms-2017 | Query: 'SDNN RMSSD norms short-term' — found 4 matching table(s), best score 0.5 |
| table-markdown-quality | shaffer-hrv-norms-2017 | Table markdown has pipes and 14 lines. Preview: **TABLE 6 / Nunan et al. (17) sh |
| table-search-recall | charlton-wearable-ppg-2022 | Query: 'PPG wearable heart rate blood pressure' — found 3 matching table(s), bes |
| table-markdown-quality | charlton-wearable-ppg-2022 | Table markdown has pipes and 37 lines. Preview: **Table 2 Datasets of PPG Signal |
| table-search-recall | flett-wearable-hr-accuracy-2025 | Query: 'heart rate accuracy error wearable' — found 1 matching table(s), best sc |
| table-markdown-quality | flett-wearable-hr-accuracy-2025 | Table markdown has pipes and 5 lines. Preview: **Table 4: Median absolute differ |
| figure-search-recall | active-inference-tutorial | Query: 'generative model graphical' — found 10 matching figure(s), best score 0. |
| figure-search-recall | huang-emd-1998 | Query: 'intrinsic mode function' — found 8 matching figure(s), best score 0.501, |
| figure-search-recall | hallett-tms-primer | Query: 'magnetic field coil' — found 4 matching figure(s), best score 0.597, cap |
| figure-search-recall | helm-coregulation | Query: 'RSA dynamics time series' — found 1 matching figure(s), best score 0.415 |
| figure-search-recall | roland-emg-filter | Query: 'filter frequency response' — found 10 matching figure(s), best score 0.4 |
| figure-search-recall | friston-life | Query: 'Markov blanket' — found 3 matching figure(s), best score 0.553, caption: |
| figure-search-recall | yang-ppv-meta | Query: 'sensitivity specificity receiver operating' — found 1 matching figure(s) |
| figure-search-recall | fortune-impedance | Query: 'impedance frequency' — found 5 matching figure(s), best score 0.443, cap |
| figure-search-recall | osterrieder-ach-kinetics-1980 | Query: 'potassium current conductance' — found 4 matching figure(s), best score  |
| figure-search-recall | linssen-emg-fatigue-1993 | Query: 'EMG power spectrum fatigue' — found 1 matching figure(s), best score 0.4 |
| figure-search-recall | ats-ers-respiratory-muscle-2002 | Query: 'diaphragm pressure stimulation' — found 10 matching figure(s), best scor |
| figure-search-recall | raez-emg-techniques-2006 | Query: 'EMG signal motor unit' — found 6 matching figure(s), best score 0.517, c |
| figure-search-recall | charlton-wearable-ppg-2022 | Query: 'photoplethysmogram waveform pulse' — found 4 matching figure(s), best sc |
| figure-search-recall | flett-wearable-hr-accuracy-2025 | Query: 'heart rate Bland-Altman agreement' — found 10 matching figure(s), best s |
| author-filter | active-inference-tutorial | Filter author='smith' — target paper found (42 total results after filter) |
| author-filter | huang-emd-1998 | Filter author='huang' — target paper found (50 total results after filter) |
| author-filter | hallett-tms-primer | Filter author='hallett' — target paper found (36 total results after filter) |
| author-filter | laird-fick-polyps | Filter author='laird' — target paper found (29 total results after filter) |
| author-filter | helm-coregulation | Filter author='helm' — target paper found (10 total results after filter) |
| author-filter | roland-emg-filter | Filter author='roland' — target paper found (29 total results after filter) |
| author-filter | friston-life | Filter author='friston' — target paper found (42 total results after filter) |
| author-filter | yang-ppv-meta | Filter author='yang' — target paper found (23 total results after filter) |
| author-filter | fortune-impedance | Filter author='fortune' — target paper found (41 total results after filter) |
| author-filter | reyes-lf-hrv | Filter author='reyes' — target paper found (14 total results after filter) |
| author-filter | osterrieder-ach-kinetics-1980 | Filter author='osterrieder' — target paper found (22 total results after filter) |
| author-filter | linssen-emg-fatigue-1993 | Filter author='linssen' — target paper found (11 total results after filter) |
| author-filter | berntson-hrv-origins-1997 | Filter author='berntson' — target paper found (17 total results after filter) |
| author-filter | schroeder-hrv-repeatability-2004 | Filter author='schroeder' — target paper found (15 total results after filter) |
| author-filter | raez-emg-techniques-2006 | Filter author='raez' — target paper found (42 total results after filter) |
| author-filter | daly-hodgkin-huxley-bayesian-2015 | Filter author='daly' — target paper found (24 total results after filter) |
| author-filter | shaffer-hrv-norms-2017 | Filter author='shaffer' — target paper found (22 total results after filter) |
| author-filter | charlton-wearable-ppg-2022 | Filter author='charlton' — target paper found (45 total results after filter) |
| author-filter | flett-wearable-hr-accuracy-2025 | Filter author='flett' — target paper found (27 total results after filter) |
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
| context-expansion | roland-emg-filter | Context expansion: before=4, after=2, full_context=9898 chars |
| context-adds-value | roland-emg-filter | Full context (9898 chars) vs hit (1503 chars) |
| context-expansion | friston-life | Context expansion: before=2, after=2, full_context=7897 chars |
| context-adds-value | friston-life | Full context (7897 chars) vs hit (1591 chars) |
| context-expansion | yang-ppv-meta | Context expansion: before=2, after=2, full_context=8007 chars |
| context-adds-value | yang-ppv-meta | Full context (8007 chars) vs hit (1600 chars) |
| context-expansion | fortune-impedance | Context expansion: before=2, after=3, full_context=9518 chars |
| context-adds-value | fortune-impedance | Full context (9518 chars) vs hit (1482 chars) |
| context-expansion | reyes-lf-hrv | Context expansion: before=0, after=2, full_context=4355 chars |
| context-adds-value | reyes-lf-hrv | Full context (4355 chars) vs hit (1361 chars) |
| context-expansion | osterrieder-ach-kinetics-1980 | Context expansion: before=0, after=2, full_context=4655 chars |
| context-adds-value | osterrieder-ach-kinetics-1980 | Full context (4655 chars) vs hit (1597 chars) |
| context-expansion | linssen-emg-fatigue-1993 | Context expansion: before=1, after=2, full_context=6132 chars |
| context-adds-value | linssen-emg-fatigue-1993 | Full context (6132 chars) vs hit (1561 chars) |
| context-expansion | berntson-hrv-origins-1997 | Context expansion: before=2, after=2, full_context=7543 chars |
| context-adds-value | berntson-hrv-origins-1997 | Full context (7543 chars) vs hit (1567 chars) |
| context-expansion | ats-ers-respiratory-muscle-2002 | Context expansion: before=2, after=9, full_context=23185 chars |
| context-adds-value | ats-ers-respiratory-muscle-2002 | Full context (23185 chars) vs hit (3152 chars) |
| context-expansion | schroeder-hrv-repeatability-2004 | Context expansion: before=0, after=2, full_context=4512 chars |
| context-adds-value | schroeder-hrv-repeatability-2004 | Full context (4512 chars) vs hit (1555 chars) |
| context-expansion | raez-emg-techniques-2006 | Context expansion: before=0, after=2, full_context=4545 chars |
| context-adds-value | raez-emg-techniques-2006 | Full context (4545 chars) vs hit (1507 chars) |
| context-expansion | daly-hodgkin-huxley-bayesian-2015 | Context expansion: before=0, after=2, full_context=4657 chars |
| context-adds-value | daly-hodgkin-huxley-bayesian-2015 | Full context (4657 chars) vs hit (1598 chars) |
| context-expansion | charlton-wearable-ppg-2022 | Context expansion: before=0, after=2, full_context=4672 chars |
| context-adds-value | charlton-wearable-ppg-2022 | Full context (4672 chars) vs hit (1600 chars) |
| context-expansion | flett-wearable-hr-accuracy-2025 | Context expansion: before=2, after=1, full_context=4607 chars |
| context-adds-value | flett-wearable-hr-accuracy-2025 | Full context (4607 chars) vs hit (1076 chars) |
| topic-search-multi-paper | HRV papers | Topic search for HRV: found 1/2 expected papers in 5 total docs. Keys found: {'A |
| topic-search-engineering | impedance papers | Topic search for impedance: found 1/1 expected. Total docs: 3. Keys: {'VP3NJ74M' |
| ocr-text-extraction | active-inference-tutorial | OCR extracted 63342 chars from 3 image pages. OCR pages detected: 3 |
| ocr-page-detection | active-inference-tutorial | OCR page detection: 3/3 pages flagged as OCR |
| nonsense-query-no-crash | all | Nonsense query returned 5 results (top score: 0.265) |
| empty-rerank-no-crash | all | Reranker handles empty input gracefully |
| boundary-chunk-first | active-inference-tutorial | Adjacent chunks for first chunk: got 3 (expected >=1) |
| boundary-chunk-last | active-inference-tutorial | Adjacent chunks for last chunk (idx=336): got 3 |
| boundary-chunk-first | huang-emd-1998 | Adjacent chunks for first chunk: got 3 (expected >=1) |
| boundary-chunk-last | huang-emd-1998 | Adjacent chunks for last chunk (idx=184): got 3 |
| section-weight-effect | all | Default top-3 sections: ['table', 'methods', 'table'], methods-boosted top-3: [' |
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
| section-labels-valid | osterrieder-ach-kinetics-1980 | All 22 section labels are valid |
| section-coverage | osterrieder-ach-kinetics-1980 | Section spans cover 100% of document (first: 0, last: 40953, total: 40953) |
| section-labels-valid | linssen-emg-fatigue-1993 | All 8 section labels are valid |
| section-coverage | linssen-emg-fatigue-1993 | Section spans cover 100% of document (first: 0, last: 34579, total: 34579) |
| section-labels-valid | berntson-hrv-origins-1997 | All 36 section labels are valid |
| section-coverage | berntson-hrv-origins-1997 | Section spans cover 100% of document (first: 0, last: 166128, total: 166128) |
| section-labels-valid | ats-ers-respiratory-muscle-2002 | All 313 section labels are valid |
| section-coverage | ats-ers-respiratory-muscle-2002 | Section spans cover 100% of document (first: 0, last: 692799, total: 692799) |
| section-labels-valid | schroeder-hrv-repeatability-2004 | All 10 section labels are valid |
| section-coverage | schroeder-hrv-repeatability-2004 | Section spans cover 100% of document (first: 0, last: 44247, total: 44247) |
| section-labels-valid | raez-emg-techniques-2006 | All 22 section labels are valid |
| section-coverage | raez-emg-techniques-2006 | Section spans cover 100% of document (first: 0, last: 105503, total: 105503) |
| section-labels-valid | daly-hodgkin-huxley-bayesian-2015 | All 11 section labels are valid |
| section-coverage | daly-hodgkin-huxley-bayesian-2015 | Section spans cover 100% of document (first: 0, last: 85536, total: 85536) |
| section-labels-valid | shaffer-hrv-norms-2017 | All 36 section labels are valid |
| section-coverage | shaffer-hrv-norms-2017 | Section spans cover 100% of document (first: 0, last: 106869, total: 106869) |
| section-labels-valid | charlton-wearable-ppg-2022 | All 41 section labels are valid |
| section-coverage | charlton-wearable-ppg-2022 | Section spans cover 100% of document (first: 0, last: 164721, total: 164721) |
| section-labels-valid | flett-wearable-hr-accuracy-2025 | All 1 section labels are valid |
| section-coverage | flett-wearable-hr-accuracy-2025 | Section spans cover 100% of document (first: 0, last: 29390, total: 29390) |

## OCR Pathway Test

_(See OCR test results in the test output above)_


## Ground Truth Comparison

| Paper | Table ID | Fuzzy Accuracy | Precision | Recall | Splits | Merges | Cell Diffs |
|-------|----------|----------------|-----------|--------|--------|--------|------------|
| laird-fick-polyps | 5SIZVS65_table_1 | 98.7% | 98.7% | 98.7% | 0 | 0 | 0 |
| laird-fick-polyps | 5SIZVS65_table_2 | 98.4% | 98.4% | 98.4% | 0 | 0 | 0 |
| laird-fick-polyps | 5SIZVS65_table_3 | 96.0% | 96.0% | 96.0% | 0 | 0 | 0 |
| laird-fick-polyps | 5SIZVS65_table_4 | 78.9% | 84.5% | 73.9% | 0 | 0 | 11 |
| laird-fick-polyps | 5SIZVS65_table_5 | 98.0% | 98.0% | 98.0% | 0 | 0 | 0 |
| helm-coregulation | 9GKLLJH9_table_1 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| helm-coregulation | 9GKLLJH9_table_2 | 67.6% | 67.6% | 67.6% | 0 | 0 | 56 |
| reyes-lf-hrv | AQ3D94VC_table_1 | 93.0% | 93.0% | 93.0% | 0 | 0 | 8 |
| reyes-lf-hrv | AQ3D94VC_table_2 | 82.2% | 82.2% | 82.2% | 0 | 0 | 8 |
| reyes-lf-hrv | AQ3D94VC_table_3 | 44.9% | 44.9% | 44.9% | 0 | 0 | 48 |
| reyes-lf-hrv | AQ3D94VC_table_4 | 44.9% | 44.9% | 44.9% | 0 | 0 | 52 |
| reyes-lf-hrv | AQ3D94VC_table_5 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| hallett-tms-primer | C626CYVT_table_1 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| yang-ppv-meta | DPYRZTFI_table_1 | 99.8% | 99.8% | 99.8% | 0 | 0 | 1 |
| yang-ppv-meta | DPYRZTFI_table_2 | 99.9% | 99.9% | 99.9% | 0 | 0 | 1 |
| yang-ppv-meta | DPYRZTFI_table_3 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| active-inference-tutorial | SCPXVBLY_table_1 | 89.0% | 89.0% | 89.0% | 0 | 0 | 5 |
| active-inference-tutorial | SCPXVBLY_table_1_p16 | 98.7% | 98.7% | 98.7% | 0 | 0 | 1 |
| active-inference-tutorial | SCPXVBLY_table_2 | 82.9% | 82.9% | 82.9% | 0 | 0 | 6 |
| active-inference-tutorial | SCPXVBLY_table_2_p19 | 67.4% | 67.4% | 67.4% | 0 | 0 | 5 |
| active-inference-tutorial | SCPXVBLY_table_2_p20 | 84.5% | 84.5% | 84.5% | 0 | 0 | 3 |
| active-inference-tutorial | SCPXVBLY_table_3 | 97.9% | 97.9% | 97.9% | 0 | 0 | 2 |
| active-inference-tutorial | SCPXVBLY_table_3_p31 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| fortune-impedance | VP3NJ74M_table_1 | 90.6% | 90.6% | 90.6% | 0 | 0 | 0 |
| fortune-impedance | VP3NJ74M_table_2 | 28.5% | 48.4% | 20.2% | 0 | 0 | 17 |
| fortune-impedance | VP3NJ74M_table_3 | 27.2% | 19.3% | 46.2% | 0 | 0 | 17 |
| fortune-impedance | VP3NJ74M_table_4 | 97.5% | 97.7% | 97.3% | 0 | 0 | 2 |
| fortune-impedance | VP3NJ74M_table_5 | 81.9% | 81.9% | 81.9% | 0 | 0 | 2 |
| fortune-impedance | VP3NJ74M_table_6 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| friston-life | YMWV46JA_table_1 | 75.0% | 70.3% | 80.3% | 0 | 0 | 5 |
| roland-emg-filter | Z9X4JVZ5_table_1 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| roland-emg-filter | Z9X4JVZ5_table_2 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| roland-emg-filter | Z9X4JVZ5_table_3 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| roland-emg-filter | Z9X4JVZ5_table_4 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| roland-emg-filter | Z9X4JVZ5_table_5 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 |
| roland-emg-filter | Z9X4JVZ5_table_6 | 89.9% | 86.1% | 93.9% | 0 | 0 | 0 |
| roland-emg-filter | Z9X4JVZ5_table_7 | 98.8% | 98.8% | 98.8% | 0 | 0 | 0 |

**Overall corpus fuzzy accuracy**: 86.8% (37 tables compared)


## Vision Extraction Report

| Metric | Value |
|--------|-------|
| Tables attempted | 70 |
| Parse success | 70 (100.0%) |
| Re-crops performed | 1 (1.4%) |
| Incomplete tables | 5 (7.1%) |

### Per-paper breakdown

| Paper | Tables | Parsed | Re-cropped | Incomplete |
|-------|--------|--------|------------|------------|
| active-inference-tutorial | 7 | 7 | 0 | 3 |
| ats-ers-respiratory-muscle-2002 | 18 | 18 | 0 | 0 |
| charlton-wearable-ppg-2022 | 3 | 3 | 0 | 0 |
| daly-hodgkin-huxley-bayesian-2015 | 3 | 3 | 0 | 0 |
| flett-wearable-hr-accuracy-2025 | 6 | 6 | 0 | 2 |
| fortune-impedance | 6 | 6 | 0 | 0 |
| friston-life | 1 | 1 | 0 | 0 |
| hallett-tms-primer | 1 | 1 | 0 | 0 |
| helm-coregulation | 2 | 2 | 0 | 0 |
| laird-fick-polyps | 5 | 5 | 0 | 0 |
| linssen-emg-fatigue-1993 | 3 | 3 | 0 | 0 |
| osterrieder-ach-kinetics-1980 | 1 | 1 | 0 | 0 |
| raez-emg-techniques-2006 | 4 | 4 | 0 | 0 |
| reyes-lf-hrv | 5 | 5 | 0 | 0 |
| roland-emg-filter | 7 | 7 | 1 | 0 |
| schroeder-hrv-repeatability-2004 | 5 | 5 | 0 | 0 |
| shaffer-hrv-norms-2017 | 7 | 7 | 0 | 1 |
| yang-ppv-meta | 3 | 3 | 0 | 0 |

### Caption changes (text-layer → vision)

| Table ID | Text Layer | Vision |
|----------|-----------|--------|
| 9GKLLJH9_table_1 | Table 1 Comparisons of Model Fit for Different Tests of Core | Table 1. Comparisons of Model Fit for Different Tests of Cor |
| 9GKLLJH9_table_2 | Table 2 Coefficients From Best-Fitting Cross-Lagged Panel Mo | Table 2. Coefficients From Best-Fitting Cross-Lagged Panel M |
| AQ3D94VC_table_3 | Table 3. Correlations of HRV Parameters Obtained by Fast Fou | Table 3. Correlations of HRV Parameters Obtained by Fast Fou |
| AQ3D94VC_table_4 | Table 4. Correlations of HRV Parameters Obtained by the Auto | Table 4. Correlations of HRV Parameters Obtained by the Auto |
| E4WMHZH5_table_1 | Table 1. Results and reproducibility | Table 1. Results and reproducibility. |
| HGGB64RC_table_6 | TABLE 6 / Nunan et al. (17) short-term norms. | TABLE 6 / Nunan et al. (17) short-term norms. |
| QB3J4QTQ_table_2 | Table 2. Intraclass Correlation Coefﬁcients (95% Conﬁdence I | Table 2. Intraclass Correlation Coefficients (95% Confidence |
| QB3J4QTQ_table_3 | Table 3. Intraclass Correlation Coefﬁcients (95% Conﬁdence I | Table 3. Intraclass Correlation Coefficients (95% Confidence |
| QB3J4QTQ_table_5 | Table 5. Correlation Coefﬁcients (95% Conﬁdence Intervals) f | Table 5. Correlation Coefficients (95% Confidence Intervals) |
| RE7X5G2Q_table_2 | Table 2 Datasets of PPG Signals. Deﬁnitions: Resp—Respirator | Table 2 Datasets of PPG Signals. Definitions: Resp—Respirato |
| RE7X5G2Q_table_3 | Table 3 Selection of Devices That Have Been Used to Acquire  | Table 3 Selection of Devices That Have Been Used to Acquire  |
| SWB2E2Q9_table_2 | Table 2: Diagnosis performance of time domain,  frequency do | Table 2: Diagnosis performance of time domain, frequency dom |
| SWB2E2Q9_table_3 | Table 3: Typical EMG classification accuracy rate.  Method   | Table 3: Typical EMG classification accuracy rate. |
| SWB2E2Q9_table_4 | Table 4: Summary of major methods.  Method  Advantage/Disadv | Table 4: Summary of major methods. |
| VP3NJ74M_table_3 | Table 3 Error between the custom impedance analyser (CIA) an | Table 3. Error between the custom impedance analyser (CIA) a |
| VP3NJ74M_table_4 | Table 4 Electrode–skin impedance imbalance quantified using  | Table 4. Electrode–skin impedance imbalance quantified using |
| VP3NJ74M_table_5 | Table 5 Mean electrode–skin impedance imbalance and imbalanc | Table 5 Mean electrode–skin impedance imbalance and imbalanc |
| W3FYXN62_table_1 | Table 1. Specification of prior and kernel distributions emp | Table 1. Specification of prior and kernel distributions emp |
| W3FYXN62_table_2 | Table 2. Summary statistics of ABC posterior estimates for v | Table 2. Summary statistics of ABC posterior estimates for v |
| W3FYXN62_table_3 | Table 3. Summary statistics of ABC posterior estimates for v | Table 3. Summary statistics of ABC posterior estimates for v |
| YMWV46JA_table_1 | Table 1. Deﬁnitions of the tuple ðV; C; S; A; L; p; qÞ under | Table 1. Definitions of the tuple (Ω, Ψ, S, A, Λ, p, q) unde |
| Z9X4JVZ5_table_1 | Table 1. Floating-point comb ﬁlter coefﬁcients. | Table 1. Floating-point comb filter coefficients. |
| Z9X4JVZ5_table_2 | Table 2. Floating-point highpass ﬁlter coefﬁcients. | Table 2. Floating-point highpass filter coefficients. |
| Z9X4JVZ5_table_3 | Table 3. Poles of comb ﬁlters with quantized coefﬁcients. | Table 3. Poles of comb filters with quantized coefficients. |
| Z9X4JVZ5_table_4 | Table 4. Poles of highpass ﬁlters with quantized coefﬁcients | Table 4. Poles of highpass filters with quantized coefficien |
| Z9X4JVZ5_table_5 | Table 5. Runtime per sample of ﬁlters in C implementation at | Table 5. Runtime per sample of filters in C implementation a |
| Z9X4JVZ5_table_6 | Table 6. Comparison of runtime per sample of various lowpass | Table 6. Comparison of runtime per sample of various lowpass |
