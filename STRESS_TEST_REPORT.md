# Stress Test Report: zotero-chunk-rag

**Date**: 2026-02-28 14:57
**Corpus**: 1 papers from live Zotero library

## Executive Summary

- **Total tests**: 41
- **Passed**: 34 (83%)
- **Failed**: 7
- **Major failures**: 4

> **VERDICT**: This tool is NOT reliable for production research use.
> A researcher depending on this tool WILL miss important results.

## Performance

| Operation | Time |
|-----------|------|
| Total indexing | 50.7s |

## Extraction Quality per Paper

| Paper | Pages | Sections | Tables | Figures | Grade | Issues |
|-------|-------|----------|--------|---------|-------|--------|
| fortune-impedance | 11 | 10 | 6 | 7 | A | 3 unknown sections; no abstract detected |

## Failures (Detailed)

### !!! [MAJOR] table-content-quality — fortune-impedance/table-1

Table 1: 31/204 cells non-empty (15%). Caption: 'Table 3 Error between the custom impedance analyser (CIA) an'

### ! [MINOR] table-content-quality — fortune-impedance/table-2

Table 2: 62/216 cells non-empty (29%). Caption: 'Table 2 Error between the custom impedance analyser (CIA) an'

### ! [MINOR] table-content-quality — fortune-impedance/table-3

Table 3: 292/689 cells non-empty (42%). Caption: 'Table 4 Electrode–skin impedance imbalance quantified using '

### !!! [MAJOR] table-content-quality — fortune-impedance/table-4

Table 4: 80/689 cells non-empty (12%). Caption: 'Table 5 Mean electrode–skin impedance imbalance and imbalanc'

### ! [MINOR] abstract-detection — fortune-impedance

Abstract NOT detected

### !!! [MAJOR] table-dimensions-sanity — fortune-impedance

1 tables are 1x1 (degenerate)

### !!! [MAJOR] topic-search-multi-paper — HRV papers

Topic search for HRV: found 0/2 expected papers in 1 total docs. Keys found: set()

## Passes

| Test | Paper | Detail |
|------|-------|--------|
| section-detection | fortune-impedance | Expected section 'introduction' — FOUND |
| section-detection | fortune-impedance | Expected section 'methods' — FOUND |
| section-detection | fortune-impedance | Expected section 'results' — FOUND |
| table-extraction | fortune-impedance | Expected tables — found 6 |
| table-content-quality | fortune-impedance/table-0 | Table 0: 21/24 cells non-empty (88%). Caption: 'Table 1 Component values used fo |
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
| semantic-search-recall | fortune-impedance | Query: 'electrode skin impedance imbalance frequency' — found at rank 1/10 (scor |
| semantic-search-ranking | fortune-impedance | Ranked 1/10 for its own core content query |
| table-search-recall | fortune-impedance | Query: 'impedance measurement electrode' — found 6 matching table(s), best score |
| table-markdown-quality | fortune-impedance | Table markdown has pipes and 2 lines. Preview: **Table 6 Mean and standard devia |
| figure-search-recall | fortune-impedance | Query: 'impedance frequency' — found 7 matching figure(s), best score 0.443, cap |
| author-filter | fortune-impedance | Filter author='fortune' — target paper found (50 total results after filter) |
| year-filter-accuracy | all | Year filter >=2015: 0 papers from before 2015 leaked through (total results: 50) |
| context-expansion | fortune-impedance | Context expansion: before=2, after=3, full_context=9518 chars |
| context-adds-value | fortune-impedance | Full context (9518 chars) vs hit (1482 chars) |
| topic-search-engineering | impedance papers | Topic search for impedance: found 1/1 expected. Total docs: 1. Keys: {'VP3NJ74M' |
| ocr-text-extraction | fortune-impedance | OCR extracted 18226 chars from 3 image pages. OCR pages detected: 3 |
| ocr-page-detection | fortune-impedance | OCR page detection: 3/3 pages flagged as OCR |
| nonsense-query-no-crash | all | Nonsense query returned 5 results (top score: 0.199) |
| empty-rerank-no-crash | all | Reranker handles empty input gracefully |
| boundary-chunk-first | fortune-impedance | Adjacent chunks for first chunk: got 3 (expected >=1) |
| boundary-chunk-last | fortune-impedance | Adjacent chunks for last chunk (idx=39): got 3 |
| section-weight-effect | all | Default top-3 sections: ['table', 'methods', 'results'], methods-boosted top-3:  |
| section-labels-valid | fortune-impedance | All 11 section labels are valid |
| section-coverage | fortune-impedance | Section spans cover 100% of document (first: 0, last: 43880, total: 43880) |

## OCR Pathway Test

_(See OCR test results in the test output above)_

## Ground Truth Comparison

| Paper | Table ID | Fuzzy Accuracy | Precision | Recall | Splits | Merges | Cell Diffs |
|-------|----------|----------------|-----------|--------|--------|--------|------------|
| fortune-impedance | VP3NJ74M_table_1 | 84.8% | 83.3% | 86.3% | 0 | 0 | 18 |
| fortune-impedance | VP3NJ74M_table_2 | 29.6% | 20.8% | 51.6% | 0 | 0 | 20 |
| fortune-impedance | VP3NJ74M_table_3 | 25.9% | 38.0% | 19.6% | 0 | 0 | 55 |
| fortune-impedance | VP3NJ74M_table_4 | 81.0% | 73.8% | 89.7% | 0 | 0 | 245 |
| fortune-impedance | VP3NJ74M_table_5 | 36.3% | 22.7% | 90.8% | 0 | 0 | 15 |
| fortune-impedance | VP3NJ74M_table_6 | 0.5% | 5.3% | 0.3% | 0 | 0 | 0 |

**Overall corpus fuzzy accuracy**: 43.0% (6 tables compared)


## Pipeline Depth Report

### Per-Method Win Rates

**Structure method wins** (how often each method's boundaries produce the best cell accuracy):

| Structure Method | Wins | Participated | Win Rate |
|-----------------|------|-------------|----------|
| vision_haiku_consensus | 6 | 6 | 100% |

**Cell method wins** (how often each method is selected as best):

| Cell Method | Wins | Participated | Win Rate |
|------------|------|-------------|----------|
| vision_consensus | 6 | 6 | 100% |

### Combination Value

Comparison of best-single-method accuracy vs pipeline (consensus boundaries) accuracy:

- **Avg best-single-method accuracy**: 71.7%
- **Avg pipeline (consensus) accuracy**: 43.0%
- **Delta (positive = combination helps)**: -28.7%
- **Tables compared**: 6

### Per-Table Accuracy Chain

| Table ID | Best Single Method | Best Accuracy | Pipeline Accuracy | Delta |
|----------|-------------------|---------------|-------------------|-------|
| VP3NJ74M_table_1 | vision_haiku_consensus+vision_consensus | 84.8% | 84.8% | +0.0% |
| VP3NJ74M_table_3 | vision_haiku_consensus+vision_consensus | 29.2% | 25.9% | -3.3% |
| VP3NJ74M_table_2 | vision_haiku_consensus+vision_consensus | 32.8% | 29.6% | -3.2% |
| VP3NJ74M_table_4 | vision_haiku_consensus+vision_consensus | 98.2% | 81.0% | -17.2% |
| VP3NJ74M_table_5 | vision_haiku_consensus+vision_consensus | 85.2% | 36.3% | -48.8% |
| VP3NJ74M_table_6 | vision_haiku_consensus+vision_consensus | 100.0% | 0.5% | -99.5% |


## Variant Comparison

Accuracy and speed across named pipeline configs on corpus tables.

### Summary

| Config | Tables | Avg Accuracy | Avg Time (s) |
|--------|--------|-------------|-------------|
| DEFAULT | 3 | 46.8% | 1.504 |
| FAST | 3 | 46.8% | 0.424 |
| RULED | 3 | 46.8% | 0.863 |
| MINIMAL | 3 | 40.1% | 0.431 |

### Per-Table Detail

| Table ID | Paper | DEFAULT | FAST | RULED | MINIMAL | |
|----------|------|-----|-----|-----|-----||
| VP3NJ74M_table_1 | fortune-impedance | 84.8% | 84.8% | 84.8% | 65.8% | |
| VP3NJ74M_table_3 | fortune-impedance | 25.9% | 25.9% | 25.9% | 24.7% | |
| VP3NJ74M_table_2 | fortune-impedance | 29.6% | 29.6% | 29.6% | 29.6% | |

