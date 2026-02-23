# Combination Diagnosis Report

Analysis of why consensus boundary combination produces 0% accuracy on specific tables where individual methods achieve 100%.

## Summary

| Table ID | Paper | Consensus Acc | Best Method Acc |
|----------|-------|---------------|-----------------|
| SCPXVBLY_table_1_p16 | active-inference-tutorial | 0.0% | 100.0% |
| SCPXVBLY_table_3 | active-inference-tutorial | 0.0% | 100.0% |
| SCPXVBLY_table_3_p31 | active-inference-tutorial | 0.0% | 100.0% |
| 5SIZVS65_table_4 | laird-fick-polyps | 0.0% | 100.0% |
| Z9X4JVZ5_table_5 | roland-emg-filter | 0.0% | 100.0% |
| DPYRZTFI_table_2 | yang-ppv-meta | 0.0% | 100.0% |
| AQ3D94VC_table_1 | reyes-lf-hrv | 0.0% | 100.0% |
| AQ3D94VC_table_2 | reyes-lf-hrv | 0.0% | 100.0% |
| AQ3D94VC_table_3 | reyes-lf-hrv | 0.0% | 100.0% |
| AQ3D94VC_table_4 | reyes-lf-hrv | 0.0% | 100.0% |
| 9GKLLJH9_table_2 | helm-coregulation | 15.4% | 100.0% |

## Per-Table Diagnosis

### SCPXVBLY_table_1_p16

- **Paper**: SCPXVBLY
- **Page**: 16
- **Caption**: Table 1 (continued).
- **BBox**: (42.14899826049805, 66.11695098876953, 549.842529296875, 156.3420867919922)

**Per-method GT accuracy (from stress test):**

| Method | Accuracy |
|--------|----------|
| single_point_hotspot+rawdict | 100.0% |
| single_point_hotspot+word_assignment | 100.0% |
| single_point_hotspot+pdfminer | 100.0% |
| gap_span_hotspot+rawdict | 100.0% |
| gap_span_hotspot+word_assignment | 100.0% |
| gap_span_hotspot+pdfminer | 100.0% |
| header_anchor+rawdict | 100.0% |
| header_anchor+word_assignment | 100.0% |
| header_anchor+pdfminer | 100.0% |
| ruled_lines+rawdict | 100.0% |
| ruled_lines+word_assignment | 100.0% |
| ruled_lines+pdfminer | 100.0% |
| pymupdf_lines+pdfminer | 100.0% |
| pymupdf_lines_strict+pdfminer | 100.0% |
| pymupdf_text+pdfminer | 100.0% |
| pymupdf_lines+rawdict | 0.0% |
| pymupdf_lines+word_assignment | 0.0% |
| pymupdf_lines_strict+rawdict | 0.0% |
| pymupdf_lines_strict+word_assignment | 0.0% |
| pymupdf_text+rawdict | 0.0% |
| pymupdf_text+word_assignment | 0.0% |

**Context properties (adaptive threshold inputs):**

- median_word_height: 6.6311
- median_word_gap: 2.7652
- median_ruled_line_thickness: 0.39800000190734863
- word count: 136
- drawing count: 2

**Structure method boundary counts:**

| Method | Columns | Rows | Activated |
|--------|---------|------|-----------|
| single_point_hotspot | 17 | 0 | YES |
| gap_span_hotspot | 17 | 0 | YES |
| global_cliff | - | - | SKIPPED |
| per_row_cliff | - | - | SKIPPED |
| header_anchor | 23 | 0 | YES |
| ruled_lines | 0 | 2 | YES |
| pymupdf_lines | 0 | 0 | No hypothesis |
| pymupdf_lines_strict | 0 | 0 | No hypothesis |
| pymupdf_text | 6 | 11 | YES |
| camelot_lattice | 0 | 0 | No hypothesis |
| camelot_hybrid | 9 | 12 | YES |
| pdfplumber_lines | 0 | 0 | No hypothesis |
| pdfplumber_text | 0 | 0 | No hypothesis |

**Combination parameters:**

- expansion_threshold: 0.7960
- tolerance: 0.3980
- source_methods: 6

**Consensus result: 50 columns, 17 rows**

**Column count comparison:**

| Method | Columns | vs Consensus |
|--------|---------|-------------|
| camelot_hybrid | 9 | -41 |
| gap_span_hotspot | 17 | -33 |
| header_anchor | 23 | -27 |
| pymupdf_text | 6 | -44 |
| ruled_lines | 0 | -50 |
| single_point_hotspot | 17 | -33 |
| **consensus** | **50** | - |

#### Column Axis

- **Input points**: 72
- **Median confidence**: 1.0000
- **Acceptance threshold**: 0.5000
- **Clusters formed**: 51
- **Accepted positions**: 50

- **Points expanded**: 72/72

**Input points by provenance:**

| Method | Points |
|--------|--------|
| camelot_hybrid | 9 |
| header_anchor | 23 |
| hotspot | 34 |
| pymupdf_text | 6 |

**Cluster details:**

| # | Position | Confidence | Methods | Accepted | Threshold |
|---|----------|------------|---------|----------|-----------|
| 0 | 42.15 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 1 | 47.34 | 0.9000 | 1 (header_anchor) | YES | 0.5000 |
| 2 | 48.13 | 0.6000 | 1 (hotspot) | YES | 0.5000 |
| 3 | 71.96 | 1.3000 | 2 (header_anchor, hotspot) | YES | 0.5000 |
| 4 | 105.33 | 1.5000 | 2 (header_anchor, hotspot) | YES | 0.5000 |
| 5 | 107.32 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 6 | 123.08 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 7 | 128.84 | 0.9000 | 1 (header_anchor) | YES | 0.5000 |
| 8 | 145.89 | 1.6000 | 1 (hotspot) | YES | 0.5000 |
| 9 | 167.74 | 0.9000 | 1 (header_anchor) | YES | 0.5000 |
| 10 | 173.37 | 1.6000 | 1 (hotspot) | YES | 0.5000 |
| 11 | 198.50 | 0.9000 | 1 (header_anchor) | YES | 0.5000 |
| 12 | 199.93 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 13 | 202.93 | 1.5000 | 1 (hotspot) | YES | 0.5000 |
| 14 | 221.21 | 0.9000 | 1 (header_anchor) | YES | 0.5000 |
| 15 | 230.89 | 1.5000 | 1 (hotspot) | YES | 0.5000 |
| 16 | 234.57 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 17 | 241.47 | 0.9000 | 1 (header_anchor) | YES | 0.5000 |
| 18 | 259.86 | 0.9000 | 1 (header_anchor) | YES | 0.5000 |
| 19 | 267.11 | 1.6000 | 1 (hotspot) | YES | 0.5000 |
| 20 | 275.22 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 21 | 285.93 | 0.9000 | 1 (header_anchor) | YES | 0.5000 |
| 22 | 290.83 | 1.3000 | 1 (hotspot) | YES | 0.5000 |
| 23 | 297.64 | 2.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 24 | 300.34 | 0.9000 | 1 (header_anchor) | YES | 0.5000 |
| 25 | 330.49 | 1.1000 | 1 (hotspot) | YES | 0.5000 |
| 26 | 331.46 | 0.9000 | 1 (header_anchor) | YES | 0.5000 |
| 27 | 335.58 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 28 | 353.87 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 29 | 363.79 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 30 | 366.46 | 0.9000 | 1 (header_anchor) | YES | 0.5000 |
| 31 | 376.90 | 1.4000 | 1 (hotspot) | YES | 0.5000 |
| 32 | 386.57 | 1.9000 | 2 (header_anchor, pymupdf_text) | YES | 0.5000 |
| 33 | 392.68 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 34 | 399.41 | 0.9000 | 1 (header_anchor) | YES | 0.5000 |
| 35 | 408.71 | 1.4000 | 1 (hotspot) | YES | 0.5000 |
| 36 | 409.95 | 0.9000 | 1 (header_anchor) | YES | 0.5000 |
| 37 | 429.75 | 1.0000 | 1 (hotspot) | YES | 0.5000 |
| 38 | 430.59 | 0.9000 | 1 (header_anchor) | YES | 0.5000 |
| 39 | 452.06 | 0.9000 | 1 (header_anchor) | YES | 0.5000 |
| 40 | 457.80 | 0.8000 | 1 (hotspot) | YES | 0.5000 |
| 41 | 461.06 | 0.9000 | 1 (header_anchor) | YES | 0.5000 |
| 42 | 476.60 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 43 | 481.74 | 1.0000 | 1 (hotspot) | YES | 0.5000 |
| 44 | 484.98 | 0.9000 | 1 (header_anchor) | YES | 0.5000 |
| 45 | 499.01 | 0.9000 | 1 (header_anchor) | YES | 0.5000 |
| 46 | 503.35 | 0.8000 | 1 (hotspot) | YES | 0.5000 |
| 47 | 512.95 | 0.9000 | 1 (header_anchor) | YES | 0.5000 |
| 48 | 535.28 | 0.4000 | 1 (hotspot) | NO | 0.5000 |
| 49 | 541.98 | 0.9000 | 1 (header_anchor) | YES | 0.5000 |
| 50 | 543.24 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |

#### Row Axis

- **Input points**: 25
- **Median confidence**: 1.0000
- **Acceptance threshold**: 0.5000
- **Clusters formed**: 17
- **Accepted positions**: 17

- **Points expanded**: 25/25

**Input points by provenance:**

| Method | Points |
|--------|--------|
| camelot_hybrid | 12 |
| pymupdf_text | 11 |
| ruled_lines | 2 |

**Cluster details:**

| # | Position | Confidence | Methods | Accepted | Threshold |
|---|----------|------------|---------|----------|-----------|
| 0 | 73.59 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 1 | 81.20 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 2 | 83.85 | 2.0000 | 2 (camelot_hybrid, ruled_lines) | YES | 0.5000 |
| 3 | 86.45 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 4 | 94.39 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 5 | 102.60 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 6 | 110.22 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 7 | 111.68 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 8 | 112.93 | 1.0000 | 1 (ruled_lines) | YES | 0.5000 |
| 9 | 114.68 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 10 | 123.07 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 11 | 131.62 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 12 | 140.19 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 13 | 148.76 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 14 | 617.51 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 15 | 629.26 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 16 | 656.88 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |

#### Detailed Column Boundary Positions

- **single_point_hotspot**: [48.1, 72.2, 105.7, 145.9, 173.4, 202.9, 230.9, 267.1, 290.8, 330.5, 376.9, 408.7, 429.8, 457.8, 481.7, 503.3, 535.3]
- **gap_span_hotspot**: [48.1, 72.2, 105.7, 145.9, 173.4, 202.9, 230.9, 267.1, 290.8, 330.5, 376.9, 408.7, 429.8, 457.8, 481.7, 503.3, 535.3]
- **header_anchor**: [47.3, 71.9, 105.1, 128.8, 167.7, 198.5, 221.2, 241.5, 259.9, 285.9, 300.3, 331.5, 366.5, 386.2, 399.4, 409.9, 430.6, 452.1, 461.1, 485.0, 499.0, 513.0, 542.0]
- **ruled_lines**: []
- **pymupdf_text**: [123.1, 199.9, 234.6, 275.2, 353.9, 386.9]
- **camelot_hybrid**: [42.1, 107.3, 297.6, 297.6, 335.6, 363.8, 392.7, 476.6, 543.2]
- **consensus**: [42.1, 47.3, 48.1, 72.0, 105.3, 107.3, 123.1, 128.8, 145.9, 167.7, 173.4, 198.5, 199.9, 202.9, 221.2, 230.9, 234.6, 241.5, 259.9, 267.1, 275.2, 285.9, 290.8, 297.6, 300.3, 330.5, 331.5, 335.6, 353.9, 363.8, 366.5, 376.9, 386.6, 392.7, 399.4, 408.7, 409.9, 429.8, 430.6, 452.1, 457.8, 461.1, 476.6, 481.7, 485.0, 499.0, 503.3, 513.0, 542.0, 543.2]

**Column count grouping:**

- 0 columns: ruled_lines
- 6 columns: pymupdf_text
- 9 columns: camelot_hybrid
- 17 columns: single_point_hotspot, gap_span_hotspot
- 23 columns: header_anchor

---

### SCPXVBLY_table_3

- **Paper**: SCPXVBLY
- **Page**: 30
- **Caption**: Table 3 Output fields for spm_MDP_VB_X_tutorial.m simulation script.
- **BBox**: (42.14899826049805, 74.68494415283203, 553.127685546875, 717.3811645507812)

**Per-method GT accuracy (from stress test):**

| Method | Accuracy |
|--------|----------|
| single_point_hotspot+rawdict | 100.0% |
| single_point_hotspot+word_assignment | 100.0% |
| single_point_hotspot+pdfminer | 100.0% |
| gap_span_hotspot+rawdict | 100.0% |
| gap_span_hotspot+word_assignment | 100.0% |
| gap_span_hotspot+pdfminer | 100.0% |
| header_anchor+rawdict | 100.0% |
| header_anchor+word_assignment | 100.0% |
| header_anchor+pdfminer | 100.0% |
| ruled_lines+rawdict | 100.0% |
| ruled_lines+word_assignment | 100.0% |
| ruled_lines+pdfminer | 100.0% |
| pymupdf_lines+pdfminer | 100.0% |
| pymupdf_lines_strict+pdfminer | 100.0% |
| pymupdf_text+pdfminer | 100.0% |
| pdfplumber_text+pdfminer | 100.0% |
| pymupdf_text+rawdict | 3.0% |
| pymupdf_lines+rawdict | 2.3% |
| pymupdf_lines+word_assignment | 2.3% |
| pymupdf_lines_strict+rawdict | 2.3% |
| pymupdf_lines_strict+word_assignment | 2.3% |
| pymupdf_text+word_assignment | 2.3% |
| pdfplumber_text+rawdict | 2.3% |
| pdfplumber_text+word_assignment | 2.3% |

**Context properties (adaptive threshold inputs):**

- median_word_height: 6.6311
- median_word_gap: 2.7652
- median_ruled_line_thickness: 0.39800000190734863
- word count: 756
- drawing count: 11

**Structure method boundary counts:**

| Method | Columns | Rows | Activated |
|--------|---------|------|-----------|
| single_point_hotspot | 17 | 0 | YES |
| gap_span_hotspot | 17 | 0 | YES |
| global_cliff | - | - | SKIPPED |
| per_row_cliff | - | - | SKIPPED |
| header_anchor | 23 | 0 | YES |
| ruled_lines | 0 | 11 | YES |
| pymupdf_lines | 0 | 0 | No hypothesis |
| pymupdf_lines_strict | 0 | 0 | No hypothesis |
| pymupdf_text | 11 | 81 | YES |
| camelot_lattice | 0 | 0 | No hypothesis |
| camelot_hybrid | 3 | 70 | YES |
| pdfplumber_lines | 0 | 0 | No hypothesis |
| pdfplumber_text | 4 | 71 | YES |

**Combination parameters:**

- expansion_threshold: 0.7960
- tolerance: 0.3980
- source_methods: 7

**Consensus result: 48 columns, 141 rows**

**Column count comparison:**

| Method | Columns | vs Consensus |
|--------|---------|-------------|
| camelot_hybrid | 3 | -45 |
| gap_span_hotspot | 17 | -31 |
| header_anchor | 23 | -25 |
| pdfplumber_text | 4 | -44 |
| pymupdf_text | 11 | -37 |
| ruled_lines | 0 | -48 |
| single_point_hotspot | 17 | -31 |
| **consensus** | **48** | - |

#### Column Axis

- **Input points**: 75
- **Median confidence**: 0.9500
- **Acceptance threshold**: 0.4750
- **Clusters formed**: 49
- **Accepted positions**: 48

- **Points expanded**: 75/75

**Input points by provenance:**

| Method | Points |
|--------|--------|
| camelot_hybrid | 3 |
| header_anchor | 23 |
| hotspot | 34 |
| pdfplumber_text | 4 |
| pymupdf_text | 11 |

**Cluster details:**

| # | Position | Confidence | Methods | Accepted | Threshold |
|---|----------|------------|---------|----------|-----------|
| 0 | 76.37 | 0.4225 | 1 (hotspot) | NO | 0.4750 |
| 1 | 77.61 | 0.9500 | 1 (header_anchor) | YES | 0.4750 |
| 2 | 81.99 | 1.0000 | 1 (camelot_hybrid) | YES | 0.4750 |
| 3 | 89.60 | 2.0000 | 2 (pdfplumber_text, pymupdf_text) | YES | 0.4750 |
| 4 | 103.12 | 0.9500 | 1 (header_anchor) | YES | 0.4750 |
| 5 | 118.76 | 0.5775 | 1 (hotspot) | YES | 0.4750 |
| 6 | 136.81 | 0.9500 | 1 (header_anchor) | YES | 0.4750 |
| 7 | 137.98 | 0.4789 | 1 (hotspot) | YES | 0.4750 |
| 8 | 142.96 | 1.0000 | 1 (pymupdf_text) | YES | 0.4750 |
| 9 | 156.14 | 0.9500 | 1 (header_anchor) | YES | 0.4750 |
| 10 | 163.04 | 1.4570 | 2 (header_anchor, hotspot) | YES | 0.4750 |
| 11 | 173.65 | 1.0000 | 1 (pymupdf_text) | YES | 0.4750 |
| 12 | 177.71 | 1.0000 | 1 (pdfplumber_text) | YES | 0.4750 |
| 13 | 191.39 | 1.4852 | 2 (header_anchor, hotspot) | YES | 0.4750 |
| 14 | 196.88 | 1.0000 | 1 (pymupdf_text) | YES | 0.4750 |
| 15 | 220.40 | 0.5211 | 1 (hotspot) | YES | 0.4750 |
| 16 | 227.80 | 0.9500 | 1 (header_anchor) | YES | 0.4750 |
| 17 | 242.84 | 1.4789 | 2 (camelot_hybrid, hotspot) | YES | 0.4750 |
| 18 | 246.64 | 2.0000 | 2 (pdfplumber_text, pymupdf_text) | YES | 0.4750 |
| 19 | 270.96 | 0.9500 | 1 (header_anchor) | YES | 0.4750 |
| 20 | 273.14 | 1.0000 | 1 (hotspot) | YES | 0.4750 |
| 21 | 284.27 | 1.0000 | 1 (pymupdf_text) | YES | 0.4750 |
| 22 | 300.34 | 0.8028 | 1 (hotspot) | YES | 0.4750 |
| 23 | 308.52 | 0.9500 | 1 (header_anchor) | YES | 0.4750 |
| 24 | 324.14 | 1.5634 | 2 (hotspot, pymupdf_text) | YES | 0.4750 |
| 25 | 328.18 | 0.9500 | 1 (header_anchor) | YES | 0.4750 |
| 26 | 353.10 | 0.9155 | 1 (hotspot) | YES | 0.4750 |
| 27 | 358.00 | 0.9500 | 1 (header_anchor) | YES | 0.4750 |
| 28 | 365.00 | 0.9500 | 1 (header_anchor) | YES | 0.4750 |
| 29 | 369.69 | 1.0000 | 1 (pymupdf_text) | YES | 0.4750 |
| 30 | 374.91 | 0.6761 | 1 (hotspot) | YES | 0.4750 |
| 31 | 377.71 | 0.9500 | 1 (header_anchor) | YES | 0.4750 |
| 32 | 399.89 | 1.9500 | 2 (camelot_hybrid, header_anchor) | YES | 0.4750 |
| 33 | 403.69 | 2.0000 | 2 (pdfplumber_text, pymupdf_text) | YES | 0.4750 |
| 34 | 428.04 | 1.6901 | 1 (hotspot) | YES | 0.4750 |
| 35 | 435.62 | 0.9500 | 1 (header_anchor) | YES | 0.4750 |
| 36 | 444.35 | 0.9500 | 1 (header_anchor) | YES | 0.4750 |
| 37 | 454.05 | 1.4648 | 1 (hotspot) | YES | 0.4750 |
| 38 | 461.23 | 0.9500 | 1 (header_anchor) | YES | 0.4750 |
| 39 | 468.87 | 1.0000 | 1 (pymupdf_text) | YES | 0.4750 |
| 40 | 476.59 | 0.9500 | 1 (header_anchor) | YES | 0.4750 |
| 41 | 478.56 | 1.4648 | 1 (hotspot) | YES | 0.4750 |
| 42 | 490.75 | 0.9500 | 1 (header_anchor) | YES | 0.4750 |
| 43 | 499.42 | 0.9500 | 1 (header_anchor) | YES | 0.4750 |
| 44 | 507.02 | 1.3803 | 1 (hotspot) | YES | 0.4750 |
| 45 | 512.17 | 0.9500 | 1 (header_anchor) | YES | 0.4750 |
| 46 | 523.04 | 1.0000 | 1 (pymupdf_text) | YES | 0.4750 |
| 47 | 526.54 | 1.9359 | 2 (header_anchor, hotspot) | YES | 0.4750 |
| 48 | 535.11 | 0.9500 | 1 (header_anchor) | YES | 0.4750 |

#### Row Axis

- **Input points**: 233
- **Median confidence**: 1.0000
- **Acceptance threshold**: 0.5000
- **Clusters formed**: 141
- **Accepted positions**: 141

- **Points expanded**: 233/233

**Input points by provenance:**

| Method | Points |
|--------|--------|
| camelot_hybrid | 70 |
| pdfplumber_text | 71 |
| pymupdf_text | 81 |
| ruled_lines | 11 |

**Cluster details:**

| # | Position | Confidence | Methods | Accepted | Threshold |
|---|----------|------------|---------|----------|-----------|
| 0 | 81.20 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 1 | 83.00 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 2 | 83.91 | 1.0000 | 1 (ruled_lines) | YES | 0.5000 |
| 3 | 85.50 | 2.0000 | 2 (pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 4 | 93.50 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 5 | 102.36 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 6 | 110.75 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 7 | 119.19 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 8 | 128.30 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 9 | 135.92 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 10 | 136.86 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 11 | 137.72 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 12 | 138.63 | 1.0000 | 1 (ruled_lines) | YES | 0.5000 |
| 13 | 140.47 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 14 | 144.46 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 15 | 148.39 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 16 | 156.97 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 17 | 165.39 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 18 | 174.18 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 19 | 182.05 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 20 | 183.03 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 21 | 186.50 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 22 | 190.64 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 23 | 192.45 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 24 | 193.36 | 1.0000 | 1 (ruled_lines) | YES | 0.5000 |
| 25 | 194.33 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 26 | 195.20 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 27 | 203.12 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 28 | 211.94 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 29 | 219.97 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 30 | 224.09 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 31 | 228.93 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 32 | 232.16 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 33 | 236.80 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 34 | 238.60 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 35 | 239.51 | 1.0000 | 1 (ruled_lines) | YES | 0.5000 |
| 36 | 241.20 | 2.0000 | 2 (pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 37 | 249.14 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 38 | 258.20 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 39 | 264.83 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 40 | 266.77 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 41 | 269.61 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 42 | 275.22 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 43 | 283.91 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 44 | 287.06 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 45 | 292.47 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 46 | 296.53 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 47 | 301.04 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 48 | 301.87 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 49 | 307.25 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 50 | 308.66 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 51 | 310.46 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 52 | 311.37 | 1.0000 | 1 (ruled_lines) | YES | 0.5000 |
| 53 | 313.21 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 54 | 317.07 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 55 | 320.85 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 56 | 326.13 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 57 | 329.81 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 58 | 336.23 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 59 | 338.63 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 60 | 346.24 | 2.0000 | 2 (pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 61 | 348.04 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 62 | 348.95 | 1.0000 | 1 (ruled_lines) | YES | 0.5000 |
| 63 | 350.79 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 64 | 356.51 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 65 | 358.44 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 66 | 366.88 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 67 | 375.74 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 68 | 384.81 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 69 | 393.35 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 70 | 395.32 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 71 | 401.92 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 72 | 405.10 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 73 | 410.48 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 74 | 415.34 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 75 | 419.05 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 76 | 426.70 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 77 | 427.62 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 78 | 436.19 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 79 | 437.16 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 80 | 443.75 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 81 | 448.54 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 82 | 452.43 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 83 | 458.20 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 84 | 460.75 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 85 | 461.55 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 86 | 468.55 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 87 | 470.48 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 88 | 478.79 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 89 | 487.60 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 90 | 488.45 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 91 | 495.21 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 92 | 497.86 | 2.0000 | 2 (camelot_hybrid, ruled_lines) | YES | 0.5000 |
| 93 | 499.27 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 94 | 500.46 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 95 | 507.58 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 96 | 510.39 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 97 | 515.98 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 98 | 520.85 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 99 | 524.54 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 100 | 526.95 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 101 | 532.39 | 2.0000 | 2 (pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 102 | 534.60 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 103 | 535.51 | 1.0000 | 1 (ruled_lines) | YES | 0.5000 |
| 104 | 537.35 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 105 | 541.77 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 106 | 544.99 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 107 | 552.60 | 2.0000 | 2 (pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 108 | 555.90 | 2.0000 | 2 (camelot_hybrid, ruled_lines) | YES | 0.5000 |
| 109 | 558.50 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 110 | 562.69 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 111 | 565.61 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 112 | 572.67 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 113 | 574.01 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 114 | 580.55 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 115 | 582.97 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 116 | 585.26 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 117 | 590.83 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 118 | 593.68 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, ruled_lines) | YES | 0.5000 |
| 119 | 596.08 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 120 | 603.20 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 121 | 604.54 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 122 | 611.82 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 123 | 615.56 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 124 | 620.61 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 125 | 629.42 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 126 | 637.94 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 127 | 640.19 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 128 | 645.56 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 129 | 648.21 | 2.0000 | 2 (camelot_hybrid, ruled_lines) | YES | 0.5000 |
| 130 | 650.91 | 2.0000 | 2 (pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 131 | 657.92 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 132 | 661.47 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 133 | 666.71 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 134 | 671.94 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 135 | 675.06 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 136 | 681.82 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 137 | 683.84 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 138 | 692.10 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 139 | 701.25 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 140 | 709.80 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |

#### Detailed Column Boundary Positions

- **single_point_hotspot**: [76.4, 118.8, 138.0, 162.9, 191.9, 220.4, 242.8, 273.1, 300.3, 323.9, 353.1, 374.9, 428.0, 454.1, 478.6, 507.0, 526.7]
- **gap_span_hotspot**: [76.4, 118.8, 138.0, 162.9, 191.9, 220.4, 242.8, 273.1, 300.3, 323.9, 353.1, 374.9, 428.0, 454.1, 478.6, 507.0, 526.7]
- **header_anchor**: [77.6, 103.1, 136.8, 156.1, 163.1, 191.1, 227.8, 271.0, 308.5, 328.2, 358.0, 365.0, 377.7, 399.9, 435.6, 444.3, 461.2, 476.6, 490.8, 499.4, 512.2, 526.4, 535.1]
- **ruled_lines**: []
- **pymupdf_text**: [89.6, 143.0, 173.7, 196.9, 246.6, 284.3, 324.3, 369.7, 403.7, 468.9, 523.0]
- **camelot_hybrid**: [82.0, 242.8, 399.9]
- **pdfplumber_text**: [89.6, 177.7, 246.6, 403.7]
- **consensus**: [77.6, 82.0, 89.6, 103.1, 118.8, 136.8, 138.0, 143.0, 156.1, 163.0, 173.7, 177.7, 191.4, 196.9, 220.4, 227.8, 242.8, 246.6, 271.0, 273.1, 284.3, 300.3, 308.5, 324.1, 328.2, 353.1, 358.0, 365.0, 369.7, 374.9, 377.7, 399.9, 403.7, 428.0, 435.6, 444.3, 454.1, 461.2, 468.9, 476.6, 478.6, 490.8, 499.4, 507.0, 512.2, 523.0, 526.5, 535.1]

**Column count grouping:**

- 0 columns: ruled_lines
- 3 columns: camelot_hybrid
- 4 columns: pdfplumber_text
- 11 columns: pymupdf_text
- 17 columns: single_point_hotspot, gap_span_hotspot
- 23 columns: header_anchor

---

### SCPXVBLY_table_3_p31

- **Paper**: SCPXVBLY
- **Page**: 31
- **Caption**: Table 3 (continued).
- **BBox**: (42.14899826049805, 66.11695098876953, 551.208984375, 248.65013122558594)

**Per-method GT accuracy (from stress test):**

| Method | Accuracy |
|--------|----------|
| single_point_hotspot+rawdict | 100.0% |
| single_point_hotspot+word_assignment | 100.0% |
| single_point_hotspot+pdfminer | 100.0% |
| gap_span_hotspot+rawdict | 100.0% |
| gap_span_hotspot+word_assignment | 100.0% |
| gap_span_hotspot+pdfminer | 100.0% |
| header_anchor+rawdict | 100.0% |
| header_anchor+word_assignment | 100.0% |
| header_anchor+pdfminer | 100.0% |
| ruled_lines+rawdict | 100.0% |
| ruled_lines+word_assignment | 100.0% |
| ruled_lines+pdfminer | 100.0% |
| pymupdf_lines+pdfminer | 100.0% |
| pymupdf_lines_strict+pdfminer | 100.0% |
| pymupdf_text+pdfminer | 100.0% |
| pymupdf_lines+rawdict | 12.5% |
| pymupdf_lines+word_assignment | 12.5% |
| pymupdf_lines_strict+rawdict | 12.5% |
| pymupdf_lines_strict+word_assignment | 12.5% |
| pymupdf_text+rawdict | 0.0% |
| pymupdf_text+word_assignment | 0.0% |

**Context properties (adaptive threshold inputs):**

- median_word_height: 6.6311
- median_word_gap: 2.7652
- median_ruled_line_thickness: 0.39800000190734863
- word count: 230
- drawing count: 4

**Structure method boundary counts:**

| Method | Columns | Rows | Activated |
|--------|---------|------|-----------|
| single_point_hotspot | 14 | 0 | YES |
| gap_span_hotspot | 14 | 0 | YES |
| global_cliff | - | - | SKIPPED |
| per_row_cliff | - | - | SKIPPED |
| header_anchor | 21 | 0 | YES |
| ruled_lines | 0 | 4 | YES |
| pymupdf_lines | 0 | 0 | No hypothesis |
| pymupdf_lines_strict | 0 | 0 | No hypothesis |
| pymupdf_text | 11 | 23 | YES |
| camelot_lattice | 0 | 0 | No hypothesis |
| camelot_hybrid | 10 | 32 | YES |
| pdfplumber_lines | 0 | 0 | No hypothesis |
| pdfplumber_text | 0 | 0 | No hypothesis |

**Combination parameters:**

- expansion_threshold: 0.7960
- tolerance: 0.3980
- source_methods: 6

**Consensus result: 50 columns, 45 rows**

**Column count comparison:**

| Method | Columns | vs Consensus |
|--------|---------|-------------|
| camelot_hybrid | 10 | -40 |
| gap_span_hotspot | 14 | -36 |
| header_anchor | 21 | -29 |
| pymupdf_text | 11 | -39 |
| ruled_lines | 0 | -50 |
| single_point_hotspot | 14 | -36 |
| **consensus** | **50** | - |

#### Column Axis

- **Input points**: 70
- **Median confidence**: 1.0000
- **Acceptance threshold**: 0.5000
- **Clusters formed**: 50
- **Accepted positions**: 50

- **Points expanded**: 70/70

**Input points by provenance:**

| Method | Points |
|--------|--------|
| camelot_hybrid | 10 |
| header_anchor | 21 |
| hotspot | 28 |
| pymupdf_text | 11 |

**Cluster details:**

| # | Position | Confidence | Methods | Accepted | Threshold |
|---|----------|------------|---------|----------|-----------|
| 0 | 37.62 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 1 | 42.15 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 2 | 77.98 | 1.3500 | 2 (header_anchor, hotspot) | YES | 0.5000 |
| 3 | 81.99 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 4 | 89.60 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 5 | 119.42 | 1.5100 | 2 (header_anchor, hotspot) | YES | 0.5000 |
| 6 | 150.01 | 0.9500 | 1 (header_anchor) | YES | 0.5000 |
| 7 | 151.12 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 8 | 156.48 | 0.5200 | 1 (hotspot) | YES | 0.5000 |
| 9 | 158.74 | 0.9500 | 1 (header_anchor) | YES | 0.5000 |
| 10 | 178.31 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 11 | 181.05 | 0.9500 | 1 (header_anchor) | YES | 0.5000 |
| 12 | 182.64 | 0.5200 | 1 (hotspot) | YES | 0.5000 |
| 13 | 221.00 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 14 | 224.75 | 0.5200 | 1 (hotspot) | YES | 0.5000 |
| 15 | 229.91 | 0.9500 | 1 (header_anchor) | YES | 0.5000 |
| 16 | 239.45 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 17 | 246.64 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 18 | 265.26 | 1.2000 | 1 (hotspot) | YES | 0.5000 |
| 19 | 268.84 | 0.9500 | 1 (header_anchor) | YES | 0.5000 |
| 20 | 284.86 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 21 | 297.64 | 2.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 22 | 299.83 | 1.9100 | 2 (header_anchor, hotspot) | YES | 0.5000 |
| 23 | 308.84 | 0.9500 | 1 (header_anchor) | YES | 0.5000 |
| 24 | 329.60 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 25 | 333.46 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 26 | 335.18 | 1.0000 | 1 (hotspot) | YES | 0.5000 |
| 27 | 337.25 | 0.9500 | 1 (header_anchor) | YES | 0.5000 |
| 28 | 355.51 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 29 | 364.26 | 1.9900 | 2 (header_anchor, hotspot) | YES | 0.5000 |
| 30 | 377.16 | 0.9500 | 1 (header_anchor) | YES | 0.5000 |
| 31 | 378.53 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 32 | 396.20 | 1.8700 | 2 (header_anchor, hotspot) | YES | 0.5000 |
| 33 | 399.89 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 34 | 403.69 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 35 | 417.73 | 0.9500 | 1 (header_anchor) | YES | 0.5000 |
| 36 | 421.69 | 0.8800 | 1 (hotspot) | YES | 0.5000 |
| 37 | 444.98 | 0.9500 | 1 (header_anchor) | YES | 0.5000 |
| 38 | 446.08 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 39 | 454.36 | 0.9600 | 1 (hotspot) | YES | 0.5000 |
| 40 | 470.23 | 0.9500 | 1 (header_anchor) | YES | 0.5000 |
| 41 | 482.98 | 0.9500 | 1 (header_anchor) | YES | 0.5000 |
| 42 | 489.39 | 0.9600 | 1 (hotspot) | YES | 0.5000 |
| 43 | 497.86 | 0.9500 | 1 (header_anchor) | YES | 0.5000 |
| 44 | 504.53 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 45 | 506.58 | 0.9500 | 1 (header_anchor) | YES | 0.5000 |
| 46 | 515.53 | 0.7200 | 1 (hotspot) | YES | 0.5000 |
| 47 | 531.08 | 0.9500 | 1 (header_anchor) | YES | 0.5000 |
| 48 | 539.85 | 0.9500 | 1 (header_anchor) | YES | 0.5000 |
| 49 | 541.78 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |

#### Row Axis

- **Input points**: 59
- **Median confidence**: 1.0000
- **Acceptance threshold**: 0.5000
- **Clusters formed**: 45
- **Accepted positions**: 45

- **Points expanded**: 59/59

**Input points by provenance:**

| Method | Points |
|--------|--------|
| camelot_hybrid | 32 |
| pymupdf_text | 23 |
| ruled_lines | 4 |

**Cluster details:**

| # | Position | Confidence | Methods | Accepted | Threshold |
|---|----------|------------|---------|----------|-----------|
| 0 | 72.63 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 1 | 75.29 | 2.0000 | 2 (camelot_hybrid, ruled_lines) | YES | 0.5000 |
| 2 | 77.88 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 3 | 85.00 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 4 | 93.78 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 5 | 102.14 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 6 | 110.92 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 7 | 118.98 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 8 | 128.32 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 9 | 136.88 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 10 | 144.49 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 11 | 146.29 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 12 | 147.20 | 1.0000 | 1 (ruled_lines) | YES | 0.5000 |
| 13 | 149.04 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 14 | 156.38 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 15 | 164.75 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 16 | 165.55 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 17 | 174.48 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 18 | 182.08 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 19 | 183.88 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 20 | 184.79 | 1.0000 | 1 (ruled_lines) | YES | 0.5000 |
| 21 | 186.63 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 22 | 193.96 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 23 | 202.33 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 24 | 203.13 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 25 | 212.06 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 26 | 219.66 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 27 | 221.46 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 28 | 222.37 | 1.0000 | 1 (ruled_lines) | YES | 0.5000 |
| 29 | 224.21 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 30 | 232.25 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 31 | 241.07 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 32 | 426.14 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 33 | 431.93 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 34 | 437.16 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 35 | 440.98 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 36 | 448.06 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 37 | 451.86 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 38 | 458.08 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 39 | 463.31 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 40 | 468.54 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 41 | 473.78 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 42 | 586.35 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 43 | 595.72 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 44 | 693.94 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |

#### Detailed Column Boundary Positions

- **single_point_hotspot**: [78.0, 119.7, 156.5, 182.6, 224.8, 265.3, 299.6, 335.2, 364.3, 396.2, 421.7, 454.4, 489.4, 515.5]
- **gap_span_hotspot**: [78.0, 119.7, 156.5, 182.6, 224.8, 265.3, 299.6, 335.2, 364.3, 396.2, 421.7, 454.4, 489.4, 515.5]
- **header_anchor**: [78.0, 119.3, 150.0, 158.7, 181.0, 229.9, 268.8, 300.1, 308.8, 337.2, 364.3, 377.2, 396.2, 417.7, 445.0, 470.2, 483.0, 497.9, 506.6, 531.1, 539.8]
- **ruled_lines**: []
- **pymupdf_text**: [89.6, 151.1, 178.3, 246.6, 284.9, 329.6, 355.5, 378.5, 403.7, 446.1, 504.5]
- **camelot_hybrid**: [37.6, 42.1, 82.0, 221.0, 239.5, 297.6, 297.6, 333.5, 399.9, 541.8]
- **consensus**: [37.6, 42.1, 78.0, 82.0, 89.6, 119.4, 150.0, 151.1, 156.5, 158.7, 178.3, 181.0, 182.6, 221.0, 224.8, 229.9, 239.5, 246.6, 265.3, 268.8, 284.9, 297.6, 299.8, 308.8, 329.6, 333.5, 335.2, 337.2, 355.5, 364.3, 377.2, 378.5, 396.2, 399.9, 403.7, 417.7, 421.7, 445.0, 446.1, 454.4, 470.2, 483.0, 489.4, 497.9, 504.5, 506.6, 515.5, 531.1, 539.8, 541.8]

**Column count grouping:**

- 0 columns: ruled_lines
- 10 columns: camelot_hybrid
- 11 columns: pymupdf_text
- 14 columns: single_point_hotspot, gap_span_hotspot
- 21 columns: header_anchor

---

### 5SIZVS65_table_4

- **Paper**: 5SIZVS65
- **Page**: 5
- **Caption**: Table 4 Odds ratios and 95 % confidence intervals for association of age with multiple versus single polyp classification in 13,881 patients
- **BBox**: (56.692901611328125, 495.19384765625, 290.03326416015625, 719.857421875)

**Per-method GT accuracy (from stress test):**

| Method | Accuracy |
|--------|----------|
| single_point_hotspot+rawdict | 100.0% |
| single_point_hotspot+word_assignment | 100.0% |
| single_point_hotspot+pdfminer | 100.0% |
| gap_span_hotspot+rawdict | 100.0% |
| gap_span_hotspot+word_assignment | 100.0% |
| gap_span_hotspot+pdfminer | 100.0% |
| global_cliff+rawdict | 100.0% |
| global_cliff+word_assignment | 100.0% |
| global_cliff+pdfminer | 100.0% |
| per_row_cliff+rawdict | 100.0% |
| per_row_cliff+word_assignment | 100.0% |
| per_row_cliff+pdfminer | 100.0% |
| header_anchor+rawdict | 100.0% |
| header_anchor+word_assignment | 100.0% |
| header_anchor+pdfminer | 100.0% |
| ruled_lines+rawdict | 50.0% |
| pymupdf_lines+rawdict | 21.4% |
| pymupdf_lines+word_assignment | 21.4% |
| pymupdf_lines_strict+rawdict | 21.4% |
| pymupdf_lines_strict+word_assignment | 21.4% |
| pymupdf_text+rawdict | 21.4% |
| pymupdf_text+word_assignment | 21.4% |
| pymupdf_lines+pdfminer | 17.9% |
| pymupdf_lines_strict+pdfminer | 17.9% |
| pymupdf_text+pdfminer | 17.9% |
| ruled_lines+word_assignment | 0.0% |
| ruled_lines+pdfminer | 0.0% |

**Context properties (adaptive threshold inputs):**

- median_word_height: 7.9999
- median_word_gap: 19.4342
- median_ruled_line_thickness: None
- word count: 90
- drawing count: 6

**Structure method boundary counts:**

| Method | Columns | Rows | Activated |
|--------|---------|------|-----------|
| single_point_hotspot | 6 | 0 | YES |
| gap_span_hotspot | 7 | 0 | YES |
| global_cliff | 7 | 0 | YES |
| per_row_cliff | 7 | 0 | YES |
| header_anchor | 7 | 0 | YES |
| ruled_lines | 2 | 1 | YES |
| pymupdf_lines | 0 | 0 | No hypothesis |
| pymupdf_lines_strict | 0 | 0 | No hypothesis |
| pymupdf_text | 5 | 31 | YES |
| camelot_lattice | - | - | SKIPPED |
| camelot_hybrid | - | - | SKIPPED |
| pdfplumber_lines | 0 | 0 | No hypothesis |
| pdfplumber_text | 0 | 0 | No hypothesis |

**Combination parameters:**

- expansion_threshold: 9.7171
- tolerance: 5.8302
- source_methods: 7

**Consensus result: 8 columns, 1 rows**

**Column count comparison:**

| Method | Columns | vs Consensus |
|--------|---------|-------------|
| gap_span_hotspot | 7 | -1 |
| global_cliff | 7 | -1 |
| header_anchor | 7 | -1 |
| per_row_cliff | 7 | -1 |
| pymupdf_text | 5 | -3 |
| ruled_lines | 2 | -6 |
| single_point_hotspot | 6 | -2 |
| **consensus** | **8** | - |

#### Column Axis

- **Input points**: 41
- **Median confidence**: 3.2790
- **Acceptance threshold**: 1.6395
- **Clusters formed**: 9
- **Accepted positions**: 8

- **Points expanded**: 41/41

**Input points by provenance:**

| Method | Points |
|--------|--------|
| global_cliff | 7 |
| header_anchor | 7 |
| hotspot | 13 |
| per_row_cliff | 7 |
| pymupdf_text | 5 |
| ruled_lines | 2 |

**Cluster details:**

| # | Position | Confidence | Methods | Accepted | Threshold |
|---|----------|------------|---------|----------|-----------|
| 0 | 79.35 | 3.5333 | 2 (header_anchor, hotspot) | YES | 1.6395 |
| 1 | 101.83 | 2.6057 | 3 (global_cliff, hotspot, per_row_cliff) | YES | 1.6395 |
| 2 | 117.28 | 3.2790 | 5 (global_cliff, hotspot, per_row_cliff, pymupdf_text, ruled_lines) | YES | 1.6395 |
| 3 | 145.41 | 2.8273 | 3 (global_cliff, header_anchor, per_row_cliff) | YES | 1.6395 |
| 4 | 164.09 | 3.0860 | 3 (global_cliff, hotspot, per_row_cliff) | YES | 1.6395 |
| 5 | 177.28 | 1.0008 | 2 (pymupdf_text, ruled_lines) | NO | 1.6395 |
| 6 | 197.54 | 4.6324 | 5 (global_cliff, header_anchor, hotspot, per_row_cliff, pymupdf_text) | YES | 1.6395 |
| 7 | 226.78 | 4.4478 | 5 (global_cliff, header_anchor, hotspot, per_row_cliff, pymupdf_text) | YES | 1.6395 |
| 8 | 259.03 | 4.4567 | 5 (global_cliff, header_anchor, hotspot, per_row_cliff, pymupdf_text) | YES | 1.6395 |

#### Row Axis

- **Input points**: 32
- **Median confidence**: 31.2393
- **Acceptance threshold**: 0.0000
- **Clusters formed**: 1
- **Accepted positions**: 1

- **Points expanded**: 32/32

**Input points by provenance:**

| Method | Points |
|--------|--------|
| pymupdf_text | 31 |
| ruled_lines | 1 |

**Cluster details:**

| # | Position | Confidence | Methods | Accepted | Threshold |
|---|----------|------------|---------|----------|-----------|
| 0 | 606.95 | 31.2393 | 2 (pymupdf_text, ruled_lines) | YES | 0.0000 |

#### Detailed Column Boundary Positions

- **single_point_hotspot**: [80.8, 101.8, 164.1, 196.1, 224.6, 256.9]
- **gap_span_hotspot**: [80.8, 101.8, 115.5, 164.1, 196.1, 224.6, 256.9]
- **global_cliff**: [101.8, 115.5, 145.4, 164.1, 196.1, 224.6, 256.9]
- **per_row_cliff**: [101.8, 115.5, 145.4, 164.1, 197.1, 224.6, 256.9]
- **header_anchor**: [72.0, 78.2, 86.4, 145.4, 196.1, 224.6, 256.9]
- **ruled_lines**: [121.4, 177.3]
- **pymupdf_text**: [121.4, 177.3, 202.1, 234.3, 266.6]
- **consensus**: [79.3, 101.8, 117.3, 145.4, 164.1, 197.5, 226.8, 259.0]

**Column count grouping:**

- 2 columns: ruled_lines
- 5 columns: pymupdf_text
- 6 columns: single_point_hotspot
- 7 columns: gap_span_hotspot, global_cliff, per_row_cliff, header_anchor

---

### Z9X4JVZ5_table_5

- **Paper**: Z9X4JVZ5
- **Page**: 19
- **Caption**: Table 5. Runtime per sample of filters in C implementation at a 48 MHz clock.
- **BBox**: (204.67799377441406, 374.6124267578125, 413.72235107421875, 464.5973205566406)

**Per-method GT accuracy (from stress test):**

| Method | Accuracy |
|--------|----------|
| single_point_hotspot+rawdict | 100.0% |
| single_point_hotspot+word_assignment | 100.0% |
| single_point_hotspot+pdfminer | 100.0% |
| gap_span_hotspot+rawdict | 100.0% |
| gap_span_hotspot+word_assignment | 100.0% |
| gap_span_hotspot+pdfminer | 100.0% |
| pymupdf_lines+rawdict | 20.0% |
| pymupdf_lines+word_assignment | 20.0% |
| pymupdf_lines_strict+rawdict | 20.0% |
| pymupdf_lines_strict+word_assignment | 20.0% |
| ruled_lines+rawdict | 0.0% |
| ruled_lines+word_assignment | 0.0% |
| ruled_lines+pdfminer | 0.0% |
| pymupdf_lines+pdfminer | 0.0% |
| pymupdf_lines_strict+pdfminer | 0.0% |
| pymupdf_text+rawdict | 0.0% |
| pymupdf_text+word_assignment | 0.0% |
| pymupdf_text+pdfminer | 0.0% |

**Context properties (adaptive threshold inputs):**

- median_word_height: 10.9928
- median_word_gap: 2.2416
- median_ruled_line_thickness: 0.6204233765602112
- word count: 29
- drawing count: 5

**Structure method boundary counts:**

| Method | Columns | Rows | Activated |
|--------|---------|------|-----------|
| single_point_hotspot | 1 | 0 | YES |
| gap_span_hotspot | 1 | 0 | YES |
| global_cliff | - | - | SKIPPED |
| per_row_cliff | - | - | SKIPPED |
| header_anchor | 0 | 0 | No hypothesis |
| ruled_lines | 0 | 4 | YES |
| pymupdf_lines | 0 | 0 | No hypothesis |
| pymupdf_lines_strict | 0 | 0 | No hypothesis |
| pymupdf_text | 1 | 7 | YES |
| camelot_lattice | 0 | 0 | No hypothesis |
| camelot_hybrid | 2 | 19 | YES |
| pdfplumber_lines | 0 | 0 | No hypothesis |
| pdfplumber_text | 0 | 0 | No hypothesis |

**Combination parameters:**

- expansion_threshold: 1.2408
- tolerance: 0.6204
- source_methods: 5

**Consensus result: 4 columns, 27 rows**

**Column count comparison:**

| Method | Columns | vs Consensus |
|--------|---------|-------------|
| camelot_hybrid | 2 | -2 |
| gap_span_hotspot | 1 | -3 |
| pymupdf_text | 1 | -3 |
| ruled_lines | 0 | -4 |
| single_point_hotspot | 1 | -3 |
| **consensus** | **4** | - |

#### Column Axis

- **Input points**: 5
- **Median confidence**: 1.0000
- **Acceptance threshold**: 0.5000
- **Clusters formed**: 4
- **Accepted positions**: 4

- **Points expanded**: 5/5

**Input points by provenance:**

| Method | Points |
|--------|--------|
| camelot_hybrid | 2 |
| hotspot | 2 |
| pymupdf_text | 1 |

**Cluster details:**

| # | Position | Confidence | Methods | Accepted | Threshold |
|---|----------|------------|---------|----------|-----------|
| 0 | 204.68 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 1 | 366.69 | 1.6667 | 1 (hotspot) | YES | 0.5000 |
| 2 | 370.42 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 3 | 392.35 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |

#### Row Axis

- **Input points**: 30
- **Median confidence**: 1.0000
- **Acceptance threshold**: 0.5000
- **Clusters formed**: 27
- **Accepted positions**: 27

- **Points expanded**: 30/30

**Input points by provenance:**

| Method | Points |
|--------|--------|
| camelot_hybrid | 19 |
| pymupdf_text | 7 |
| ruled_lines | 4 |

**Cluster details:**

| # | Position | Confidence | Methods | Accepted | Threshold |
|---|----------|------------|---------|----------|-----------|
| 0 | 385.28 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 1 | 387.63 | 1.0000 | 1 (ruled_lines) | YES | 0.5000 |
| 2 | 389.11 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 3 | 392.06 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 4 | 396.84 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 5 | 402.02 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 6 | 403.72 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 7 | 407.14 | 1.0000 | 1 (ruled_lines) | YES | 0.5000 |
| 8 | 412.72 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 9 | 424.23 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 10 | 430.25 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 11 | 433.90 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 12 | 437.08 | 0.9180 | 1 (ruled_lines) | YES | 0.5000 |
| 13 | 438.53 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 14 | 440.90 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 15 | 452.67 | 1.9180 | 2 (camelot_hybrid, ruled_lines) | YES | 0.5000 |
| 16 | 518.95 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 17 | 528.91 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 18 | 539.87 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 19 | 549.76 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 20 | 562.12 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 21 | 570.86 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 22 | 582.38 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 23 | 593.05 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 24 | 599.27 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 25 | 609.51 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 26 | 622.11 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |

#### Detailed Column Boundary Positions

- **single_point_hotspot**: [366.7]
- **gap_span_hotspot**: [366.7]
- **ruled_lines**: []
- **pymupdf_text**: [370.4]
- **camelot_hybrid**: [204.7, 392.4]
- **consensus**: [204.7, 366.7, 370.4, 392.4]

**Column count grouping:**

- 0 columns: ruled_lines
- 1 columns: single_point_hotspot, gap_span_hotspot, pymupdf_text
- 2 columns: camelot_hybrid

---

### DPYRZTFI_table_2

- **Paper**: DPYRZTFI
- **Page**: 5
- **Caption**: Table 2 Selected methodological characteristics of included studies
- **BBox**: (60.943267822265625, 119.3765640258789, 703.707275390625, 469.8984069824219)

**Per-method GT accuracy (from stress test):**

| Method | Accuracy |
|--------|----------|
| single_point_hotspot+rawdict | 100.0% |
| single_point_hotspot+word_assignment | 100.0% |
| single_point_hotspot+pdfminer | 100.0% |
| gap_span_hotspot+rawdict | 100.0% |
| gap_span_hotspot+word_assignment | 100.0% |
| gap_span_hotspot+pdfminer | 100.0% |
| global_cliff+rawdict | 100.0% |
| global_cliff+word_assignment | 100.0% |
| global_cliff+pdfminer | 100.0% |
| per_row_cliff+rawdict | 100.0% |
| per_row_cliff+word_assignment | 100.0% |
| per_row_cliff+pdfminer | 100.0% |
| header_anchor+rawdict | 100.0% |
| header_anchor+word_assignment | 100.0% |
| header_anchor+pdfminer | 100.0% |
| ruled_lines+rawdict | 100.0% |
| ruled_lines+pdfminer | 100.0% |
| pymupdf_lines+rawdict | 100.0% |
| pymupdf_lines+word_assignment | 100.0% |
| pymupdf_lines+pdfminer | 100.0% |
| pymupdf_lines_strict+rawdict | 100.0% |
| pymupdf_lines_strict+word_assignment | 100.0% |
| pymupdf_lines_strict+pdfminer | 100.0% |
| pymupdf_text+pdfminer | 100.0% |
| pymupdf_text+rawdict | 8.3% |
| pymupdf_text+word_assignment | 8.3% |
| ruled_lines+word_assignment | 0.0% |

**Context properties (adaptive threshold inputs):**

- median_word_height: 7.9999
- median_word_gap: 17.6774
- median_ruled_line_thickness: None
- word count: 473
- drawing count: 15

**Structure method boundary counts:**

| Method | Columns | Rows | Activated |
|--------|---------|------|-----------|
| single_point_hotspot | 20 | 0 | YES |
| gap_span_hotspot | 29 | 0 | YES |
| global_cliff | 25 | 0 | YES |
| per_row_cliff | 23 | 0 | YES |
| header_anchor | 22 | 0 | YES |
| ruled_lines | 15 | 1 | YES |
| pymupdf_lines | 0 | 0 | No hypothesis |
| pymupdf_lines_strict | 0 | 0 | No hypothesis |
| pymupdf_text | 16 | 48 | YES |
| camelot_lattice | - | - | SKIPPED |
| camelot_hybrid | - | - | SKIPPED |
| pdfplumber_lines | 0 | 0 | No hypothesis |
| pdfplumber_text | 0 | 0 | No hypothesis |

**Combination parameters:**

- expansion_threshold: 8.8387
- tolerance: 5.3032
- source_methods: 7

**Consensus result: 24 columns, 1 rows**

**Column count comparison:**

| Method | Columns | vs Consensus |
|--------|---------|-------------|
| gap_span_hotspot | 29 | +5 |
| global_cliff | 25 | +1 |
| header_anchor | 22 | -2 |
| per_row_cliff | 23 | -1 |
| pymupdf_text | 16 | -8 |
| ruled_lines | 15 | -9 |
| single_point_hotspot | 20 | -4 |
| **consensus** | **24** | - |

#### Column Axis

- **Input points**: 150
- **Median confidence**: 3.2552
- **Acceptance threshold**: 1.6276
- **Clusters formed**: 29
- **Accepted positions**: 24

- **Points expanded**: 150/150

**Input points by provenance:**

| Method | Points |
|--------|--------|
| global_cliff | 25 |
| header_anchor | 22 |
| hotspot | 49 |
| per_row_cliff | 23 |
| pymupdf_text | 16 |
| ruled_lines | 15 |

**Cluster details:**

| # | Position | Confidence | Methods | Accepted | Threshold |
|---|----------|------------|---------|----------|-----------|
| 0 | 60.95 | 0.0005 | 1 (ruled_lines) | NO | 1.6276 |
| 1 | 79.26 | 4.9518 | 6 (global_cliff, header_anchor, hotspot, per_row_cliff, pymupdf_text, ruled_lines) | YES | 1.6276 |
| 2 | 112.53 | 2.0667 | 2 (header_anchor, hotspot) | YES | 1.6276 |
| 3 | 127.16 | 3.0944 | 3 (header_anchor, hotspot, pymupdf_text) | YES | 1.6276 |
| 4 | 148.95 | 1.7544 | 2 (global_cliff, per_row_cliff) | YES | 1.6276 |
| 5 | 163.02 | 5.0648 | 5 (global_cliff, header_anchor, hotspot, per_row_cliff, pymupdf_text) | YES | 1.6276 |
| 6 | 180.33 | 4.6647 | 6 (global_cliff, header_anchor, hotspot, per_row_cliff, pymupdf_text, ruled_lines) | YES | 1.6276 |
| 7 | 220.45 | 13.9012 | 6 (global_cliff, header_anchor, hotspot, per_row_cliff, pymupdf_text, ruled_lines) | YES | 1.6276 |
| 8 | 264.51 | 0.4722 | 1 (hotspot) | NO | 1.6276 |
| 9 | 281.93 | 7.2621 | 6 (global_cliff, header_anchor, hotspot, per_row_cliff, pymupdf_text, ruled_lines) | YES | 1.6276 |
| 10 | 325.94 | 3.9575 | 4 (global_cliff, header_anchor, hotspot, per_row_cliff) | YES | 1.6276 |
| 11 | 351.16 | 7.6282 | 6 (global_cliff, header_anchor, hotspot, per_row_cliff, pymupdf_text, ruled_lines) | YES | 1.6276 |
| 12 | 384.49 | 4.0248 | 4 (global_cliff, header_anchor, hotspot, per_row_cliff) | YES | 1.6276 |
| 13 | 405.24 | 3.2552 | 5 (global_cliff, hotspot, per_row_cliff, pymupdf_text, ruled_lines) | YES | 1.6276 |
| 14 | 435.22 | 4.0455 | 4 (global_cliff, header_anchor, hotspot, per_row_cliff) | YES | 1.6276 |
| 15 | 450.57 | 3.1041 | 5 (global_cliff, hotspot, per_row_cliff, pymupdf_text, ruled_lines) | YES | 1.6276 |
| 16 | 463.47 | 1.6778 | 2 (header_anchor, hotspot) | YES | 1.6276 |
| 17 | 487.82 | 4.0366 | 4 (global_cliff, header_anchor, hotspot, per_row_cliff) | YES | 1.6276 |
| 18 | 498.66 | 1.0005 | 2 (pymupdf_text, ruled_lines) | NO | 1.6276 |
| 19 | 511.36 | 2.1222 | 2 (header_anchor, hotspot) | YES | 1.6276 |
| 20 | 528.34 | 4.8801 | 6 (global_cliff, header_anchor, hotspot, per_row_cliff, pymupdf_text, ruled_lines) | YES | 1.6276 |
| 21 | 546.74 | 0.6111 | 1 (hotspot) | NO | 1.6276 |
| 22 | 562.71 | 4.0713 | 4 (global_cliff, header_anchor, hotspot, per_row_cliff) | YES | 1.6276 |
| 23 | 583.47 | 2.3816 | 4 (global_cliff, hotspot, pymupdf_text, ruled_lines) | YES | 1.6276 |
| 24 | 596.04 | 1.9239 | 2 (global_cliff, per_row_cliff) | YES | 1.6276 |
| 25 | 608.98 | 4.1494 | 4 (global_cliff, header_anchor, hotspot, per_row_cliff) | YES | 1.6276 |
| 26 | 624.14 | 3.1289 | 5 (global_cliff, hotspot, per_row_cliff, pymupdf_text, ruled_lines) | YES | 1.6276 |
| 27 | 661.89 | 7.2335 | 6 (global_cliff, header_anchor, hotspot, per_row_cliff, pymupdf_text, ruled_lines) | YES | 1.6276 |
| 28 | 703.67 | 0.0005 | 1 (ruled_lines) | NO | 1.6276 |

#### Row Axis

- **Input points**: 49
- **Median confidence**: 48.1504
- **Acceptance threshold**: 0.0000
- **Clusters formed**: 1
- **Accepted positions**: 1

- **Points expanded**: 49/49

**Input points by provenance:**

| Method | Points |
|--------|--------|
| pymupdf_text | 48 |
| ruled_lines | 1 |

**Cluster details:**

| # | Position | Confidence | Methods | Accepted | Threshold |
|---|----------|------------|---------|----------|-----------|
| 0 | 294.69 | 48.1504 | 2 (pymupdf_text, ruled_lines) | YES | 0.0000 |

#### Detailed Column Boundary Positions

- **single_point_hotspot**: [77.8, 111.7, 126.2, 161.6, 179.2, 202.0, 222.3, 236.9, 275.5, 285.7, 325.9, 382.6, 435.2, 463.5, 487.8, 511.4, 527.0, 563.1, 608.8, 656.7]
- **gap_span_hotspot**: [77.8, 111.7, 126.2, 161.6, 179.2, 202.0, 222.3, 236.9, 264.5, 275.5, 285.7, 325.9, 341.0, 356.8, 382.6, 404.2, 435.2, 449.6, 463.5, 487.8, 511.4, 527.0, 546.7, 563.1, 582.2, 608.8, 623.2, 656.7, 667.0]
- **global_cliff**: [77.8, 149.0, 163.2, 179.2, 202.0, 229.9, 242.6, 275.5, 285.7, 325.9, 341.0, 356.8, 382.6, 404.2, 435.2, 449.6, 487.8, 527.0, 563.1, 582.2, 596.0, 608.8, 623.2, 656.7, 667.0]
- **per_row_cliff**: [77.8, 149.0, 163.2, 179.2, 202.0, 229.9, 275.5, 285.7, 325.9, 338.2, 356.8, 382.6, 403.1, 435.2, 449.6, 487.8, 527.0, 563.1, 596.0, 608.8, 623.2, 656.7, 666.8]
- **header_anchor**: [75.8, 113.6, 128.1, 164.1, 180.3, 202.0, 210.1, 219.2, 236.9, 275.5, 325.9, 355.8, 364.9, 391.1, 435.2, 463.5, 487.8, 511.4, 527.0, 561.2, 609.6, 656.7]
- **ruled_lines**: [60.9, 86.9, 183.6, 205.1, 245.7, 295.6, 347.0, 408.5, 452.6, 498.7, 533.4, 585.2, 626.2, 671.5, 703.7]
- **pymupdf_text**: [86.9, 127.4, 163.5, 183.6, 205.1, 220.4, 245.7, 295.6, 347.0, 408.5, 452.6, 498.7, 533.3, 585.2, 626.2, 671.5]
- **consensus**: [79.3, 112.5, 127.2, 149.0, 163.0, 180.3, 220.5, 281.9, 325.9, 351.2, 384.5, 405.2, 435.2, 450.6, 463.5, 487.8, 511.4, 528.3, 562.7, 583.5, 596.0, 609.0, 624.1, 661.9]

**Column count grouping:**

- 15 columns: ruled_lines
- 16 columns: pymupdf_text
- 20 columns: single_point_hotspot
- 22 columns: header_anchor
- 23 columns: per_row_cliff
- 25 columns: global_cliff
- 29 columns: gap_span_hotspot

---

### AQ3D94VC_table_1

- **Paper**: AQ3D94VC
- **Page**: 3
- **Caption**: Table 1. Means and Standard Deviations (in Parentheses) of HRV Parameters Before and After Pharmacological Blockade
- **BBox**: (57.206695556640625, 80.70177459716797, 553.4557495117188, 202.87953186035156)

**Per-method GT accuracy (from stress test):**

| Method | Accuracy |
|--------|----------|
| single_point_hotspot+rawdict | 100.0% |
| single_point_hotspot+word_assignment | 100.0% |
| single_point_hotspot+pdfminer | 100.0% |
| gap_span_hotspot+rawdict | 100.0% |
| gap_span_hotspot+word_assignment | 100.0% |
| gap_span_hotspot+pdfminer | 100.0% |
| header_anchor+rawdict | 100.0% |
| header_anchor+word_assignment | 100.0% |
| header_anchor+pdfminer | 100.0% |
| pymupdf_lines+pdfminer | 100.0% |
| pymupdf_lines_strict+pdfminer | 100.0% |
| pymupdf_text+pdfminer | 100.0% |
| pdfplumber_text+rawdict | 100.0% |
| pdfplumber_text+word_assignment | 100.0% |
| pdfplumber_text+pdfminer | 100.0% |
| pymupdf_lines+rawdict | 93.3% |
| pymupdf_lines+word_assignment | 93.3% |
| pymupdf_lines_strict+rawdict | 93.3% |
| pymupdf_lines_strict+word_assignment | 93.3% |
| pymupdf_text+rawdict | 27.3% |
| ruled_lines+rawdict | 0.0% |
| ruled_lines+word_assignment | 0.0% |
| ruled_lines+pdfminer | 0.0% |
| pymupdf_text+word_assignment | 0.0% |

**Context properties (adaptive threshold inputs):**

- median_word_height: 7.9824
- median_word_gap: 2.3923
- median_ruled_line_thickness: 0.49900001287460327
- word count: 108
- drawing count: 1

**Structure method boundary counts:**

| Method | Columns | Rows | Activated |
|--------|---------|------|-----------|
| single_point_hotspot | 10 | 0 | YES |
| gap_span_hotspot | 10 | 0 | YES |
| global_cliff | - | - | SKIPPED |
| per_row_cliff | - | - | SKIPPED |
| header_anchor | 13 | 0 | YES |
| ruled_lines | 0 | 2 | YES |
| pymupdf_lines | 0 | 0 | No hypothesis |
| pymupdf_lines_strict | 0 | 0 | No hypothesis |
| pymupdf_text | 10 | 10 | YES |
| camelot_lattice | 0 | 0 | No hypothesis |
| camelot_hybrid | 5 | 12 | YES |
| pdfplumber_lines | 0 | 0 | No hypothesis |
| pdfplumber_text | 4 | 12 | YES |

**Combination parameters:**

- expansion_threshold: 0.9980
- tolerance: 0.4990
- source_methods: 7

**Consensus result: 31 columns, 24 rows**

**Column count comparison:**

| Method | Columns | vs Consensus |
|--------|---------|-------------|
| camelot_hybrid | 5 | -26 |
| gap_span_hotspot | 10 | -21 |
| header_anchor | 13 | -18 |
| pdfplumber_text | 4 | -27 |
| pymupdf_text | 10 | -21 |
| ruled_lines | 0 | -31 |
| single_point_hotspot | 10 | -21 |
| **consensus** | **31** | - |

#### Column Axis

- **Input points**: 52
- **Median confidence**: 1.0000
- **Acceptance threshold**: 0.5000
- **Clusters formed**: 31
- **Accepted positions**: 31

- **Points expanded**: 52/52

**Input points by provenance:**

| Method | Points |
|--------|--------|
| camelot_hybrid | 5 |
| header_anchor | 13 |
| hotspot | 20 |
| pdfplumber_text | 4 |
| pymupdf_text | 10 |

**Cluster details:**

| # | Position | Confidence | Methods | Accepted | Threshold |
|---|----------|------------|---------|----------|-----------|
| 0 | 115.51 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 1 | 117.49 | 1.1429 | 1 (hotspot) | YES | 0.5000 |
| 2 | 140.60 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 3 | 147.06 | 0.9000 | 1 (header_anchor) | YES | 0.5000 |
| 4 | 154.00 | 2.2857 | 2 (hotspot, pymupdf_text) | YES | 0.5000 |
| 5 | 162.16 | 0.9000 | 1 (header_anchor) | YES | 0.5000 |
| 6 | 201.05 | 3.1857 | 3 (camelot_hybrid, header_anchor, hotspot) | YES | 0.5000 |
| 7 | 230.55 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 8 | 237.40 | 0.9000 | 1 (header_anchor) | YES | 0.5000 |
| 9 | 243.96 | 2.2857 | 2 (hotspot, pymupdf_text) | YES | 0.5000 |
| 10 | 252.64 | 0.9000 | 1 (header_anchor) | YES | 0.5000 |
| 11 | 291.61 | 3.1857 | 3 (camelot_hybrid, header_anchor, hotspot) | YES | 0.5000 |
| 12 | 313.74 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 13 | 318.22 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 14 | 322.98 | 0.9000 | 1 (header_anchor) | YES | 0.5000 |
| 15 | 335.33 | 2.2857 | 2 (hotspot, pymupdf_text) | YES | 0.5000 |
| 16 | 341.19 | 0.9000 | 1 (header_anchor) | YES | 0.5000 |
| 17 | 379.98 | 1.9000 | 2 (camelot_hybrid, header_anchor) | YES | 0.5000 |
| 18 | 383.08 | 1.2857 | 1 (hotspot) | YES | 0.5000 |
| 19 | 409.30 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 20 | 416.44 | 0.9000 | 1 (header_anchor) | YES | 0.5000 |
| 21 | 426.40 | 2.2857 | 2 (hotspot, pymupdf_text) | YES | 0.5000 |
| 22 | 434.79 | 0.9000 | 1 (header_anchor) | YES | 0.5000 |
| 23 | 460.19 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 24 | 473.80 | 2.2857 | 2 (camelot_hybrid, hotspot) | YES | 0.5000 |
| 25 | 478.43 | 0.9000 | 1 (header_anchor) | YES | 0.5000 |
| 26 | 504.65 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 27 | 507.70 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 28 | 525.07 | 2.4286 | 2 (hotspot, pymupdf_text) | YES | 0.5000 |
| 29 | 527.13 | 0.9000 | 1 (header_anchor) | YES | 0.5000 |
| 30 | 528.96 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |

#### Row Axis

- **Input points**: 36
- **Median confidence**: 1.0000
- **Acceptance threshold**: 0.5000
- **Clusters formed**: 24
- **Accepted positions**: 24

- **Points expanded**: 36/36

**Input points by provenance:**

| Method | Points |
|--------|--------|
| camelot_hybrid | 12 |
| pdfplumber_text | 12 |
| pymupdf_text | 10 |
| ruled_lines | 2 |

**Cluster details:**

| # | Position | Confidence | Methods | Accepted | Threshold |
|---|----------|------------|---------|----------|-----------|
| 0 | 80.70 | 1.0000 | 1 (ruled_lines) | YES | 0.5000 |
| 1 | 91.12 | 2.0000 | 2 (pdfplumber_text, ruled_lines) | YES | 0.5000 |
| 2 | 92.51 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 3 | 102.10 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 4 | 104.38 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 5 | 113.17 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 6 | 122.47 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 7 | 124.05 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 8 | 128.83 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 9 | 131.40 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 10 | 136.17 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 11 | 140.37 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 12 | 145.86 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 13 | 149.41 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 14 | 156.58 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 15 | 158.34 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 16 | 166.10 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 17 | 167.31 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 18 | 173.23 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 19 | 176.36 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 20 | 180.57 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 21 | 185.28 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 22 | 190.17 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 23 | 194.25 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |

#### Detailed Column Boundary Positions

- **single_point_hotspot**: [117.5, 153.6, 201.2, 243.5, 291.9, 334.9, 383.1, 426.0, 474.0, 524.7]
- **gap_span_hotspot**: [117.5, 153.6, 201.2, 243.5, 291.9, 334.9, 383.1, 426.0, 474.0, 524.7]
- **header_anchor**: [147.1, 162.2, 200.9, 237.4, 252.6, 291.4, 323.0, 341.2, 380.0, 416.4, 434.8, 478.4, 527.1]
- **ruled_lines**: []
- **pymupdf_text**: [140.6, 154.6, 230.6, 244.5, 318.2, 335.9, 409.3, 427.0, 507.7, 525.7]
- **camelot_hybrid**: [115.5, 200.9, 291.4, 380.0, 473.6]
- **pdfplumber_text**: [313.7, 460.2, 504.6, 529.0]
- **consensus**: [115.5, 117.5, 140.6, 147.1, 154.0, 162.2, 201.0, 230.6, 237.4, 244.0, 252.6, 291.6, 313.7, 318.2, 323.0, 335.3, 341.2, 380.0, 383.1, 409.3, 416.4, 426.4, 434.8, 460.2, 473.8, 478.4, 504.6, 507.7, 525.1, 527.1, 529.0]

**Column count grouping:**

- 0 columns: ruled_lines
- 4 columns: pdfplumber_text
- 5 columns: camelot_hybrid
- 10 columns: single_point_hotspot, gap_span_hotspot, pymupdf_text
- 13 columns: header_anchor

---

### AQ3D94VC_table_2

- **Paper**: AQ3D94VC
- **Page**: 4
- **Caption**: Table 2. Means and Standard Deviations (in Parentheses) of HRV Parameters of Physically Active (A) and Sedentary (S) Participants in the Martín-Vázquez and Reyes del Paso (2010) Study during Baseline and a Mental Arithmetic Task
- **BBox**: (313.74420166015625, 113.62895965576172, 552.8787841796875, 235.59124755859375)

**Per-method GT accuracy (from stress test):**

| Method | Accuracy |
|--------|----------|
| single_point_hotspot+rawdict | 100.0% |
| single_point_hotspot+word_assignment | 100.0% |
| single_point_hotspot+pdfminer | 100.0% |
| gap_span_hotspot+rawdict | 100.0% |
| gap_span_hotspot+word_assignment | 100.0% |
| gap_span_hotspot+pdfminer | 100.0% |
| header_anchor+rawdict | 100.0% |
| header_anchor+word_assignment | 100.0% |
| header_anchor+pdfminer | 100.0% |
| pymupdf_lines+rawdict | 100.0% |
| pymupdf_lines+word_assignment | 100.0% |
| pymupdf_lines_strict+rawdict | 100.0% |
| pymupdf_lines_strict+word_assignment | 100.0% |
| pymupdf_text+word_assignment | 100.0% |
| pdfplumber_text+rawdict | 100.0% |
| pdfplumber_text+word_assignment | 100.0% |
| pdfplumber_text+pdfminer | 100.0% |
| pymupdf_text+rawdict | 63.6% |
| ruled_lines+rawdict | 0.0% |
| ruled_lines+word_assignment | 0.0% |
| ruled_lines+pdfminer | 0.0% |
| pymupdf_lines+pdfminer | 0.0% |
| pymupdf_lines_strict+pdfminer | 0.0% |
| pymupdf_text+pdfminer | 0.0% |

**Context properties (adaptive threshold inputs):**

- median_word_height: 7.9824
- median_word_gap: 24.2841
- median_ruled_line_thickness: 0.49900001287460327
- word count: 61
- drawing count: 1

**Structure method boundary counts:**

| Method | Columns | Rows | Activated |
|--------|---------|------|-----------|
| single_point_hotspot | 7 | 0 | YES |
| gap_span_hotspot | 7 | 0 | YES |
| global_cliff | - | - | SKIPPED |
| per_row_cliff | - | - | SKIPPED |
| header_anchor | 7 | 0 | YES |
| ruled_lines | 0 | 2 | YES |
| pymupdf_lines | 0 | 0 | No hypothesis |
| pymupdf_lines_strict | 0 | 0 | No hypothesis |
| pymupdf_text | 7 | 13 | YES |
| camelot_lattice | 0 | 0 | No hypothesis |
| camelot_hybrid | 28 | 72 | YES |
| pdfplumber_lines | 0 | 0 | No hypothesis |
| pdfplumber_text | 0 | 8 | YES |

**Combination parameters:**

- expansion_threshold: 0.9980
- tolerance: 0.4990
- source_methods: 7

**Consensus result: 30 columns, 77 rows**

**Column count comparison:**

| Method | Columns | vs Consensus |
|--------|---------|-------------|
| camelot_hybrid | 28 | -2 |
| gap_span_hotspot | 7 | -23 |
| header_anchor | 7 | -23 |
| pdfplumber_text | 0 | -30 |
| pymupdf_text | 7 | -23 |
| ruled_lines | 0 | -30 |
| single_point_hotspot | 7 | -23 |
| **consensus** | **30** | - |

#### Column Axis

- **Input points**: 56
- **Median confidence**: 1.0000
- **Acceptance threshold**: 0.5000
- **Clusters formed**: 30
- **Accepted positions**: 30

- **Points expanded**: 56/56

**Input points by provenance:**

| Method | Points |
|--------|--------|
| camelot_hybrid | 28 |
| header_anchor | 7 |
| hotspot | 14 |
| pymupdf_text | 7 |

**Cluster details:**

| # | Position | Confidence | Methods | Accepted | Threshold |
|---|----------|------------|---------|----------|-----------|
| 0 | 57.21 | 3.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 1 | 88.12 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 2 | 97.11 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 3 | 123.42 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 4 | 144.44 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 5 | 186.98 | 2.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 6 | 215.29 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 7 | 216.42 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 8 | 305.07 | 6.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 9 | 313.74 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 10 | 339.64 | 4.0429 | 3 (camelot_hybrid, header_anchor, hotspot) | YES | 0.5000 |
| 11 | 349.11 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 12 | 366.40 | 3.0429 | 3 (header_anchor, hotspot, pymupdf_text) | YES | 0.5000 |
| 13 | 394.51 | 0.9000 | 1 (header_anchor) | YES | 0.5000 |
| 14 | 396.51 | 1.2857 | 1 (hotspot) | YES | 0.5000 |
| 15 | 398.50 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 16 | 408.65 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 17 | 421.95 | 3.0429 | 3 (header_anchor, hotspot, pymupdf_text) | YES | 0.5000 |
| 18 | 445.40 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 19 | 450.31 | 1.9000 | 2 (camelot_hybrid, header_anchor) | YES | 0.5000 |
| 20 | 452.45 | 0.7143 | 1 (hotspot) | YES | 0.5000 |
| 21 | 460.19 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 22 | 462.96 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 23 | 491.95 | 1.6143 | 2 (header_anchor, hotspot) | YES | 0.5000 |
| 24 | 494.50 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 25 | 504.65 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 26 | 510.45 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 27 | 517.71 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 28 | 528.76 | 2.4714 | 3 (camelot_hybrid, header_anchor, hotspot) | YES | 0.5000 |
| 29 | 538.91 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |

#### Row Axis

- **Input points**: 95
- **Median confidence**: 1.0000
- **Acceptance threshold**: 0.5000
- **Clusters formed**: 77
- **Accepted positions**: 77

- **Points expanded**: 95/95

**Input points by provenance:**

| Method | Points |
|--------|--------|
| camelot_hybrid | 72 |
| pdfplumber_text | 8 |
| pymupdf_text | 13 |
| ruled_lines | 2 |

**Cluster details:**

| # | Position | Confidence | Methods | Accepted | Threshold |
|---|----------|------------|---------|----------|-----------|
| 0 | 113.63 | 1.0000 | 1 (ruled_lines) | YES | 0.5000 |
| 1 | 122.00 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 2 | 124.10 | 1.0000 | 1 (ruled_lines) | YES | 0.5000 |
| 3 | 125.44 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 4 | 128.99 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 5 | 137.39 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 6 | 146.25 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 7 | 155.35 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 8 | 156.98 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 9 | 164.33 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 10 | 167.95 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 11 | 173.31 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 12 | 178.93 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 13 | 182.29 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 14 | 189.90 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 15 | 191.27 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 16 | 200.51 | 4.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 17 | 205.27 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 18 | 209.57 | 3.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 19 | 211.86 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 20 | 215.24 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 21 | 218.21 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 22 | 220.23 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 23 | 222.83 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 24 | 225.22 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 25 | 227.19 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 26 | 230.21 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 27 | 235.20 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 28 | 244.51 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 29 | 254.53 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 30 | 259.52 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 31 | 264.51 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 32 | 269.61 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 33 | 274.16 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 34 | 279.58 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 35 | 289.45 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 36 | 299.66 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 37 | 310.64 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 38 | 320.66 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 39 | 331.64 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 40 | 342.61 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 41 | 354.54 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 42 | 365.52 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 43 | 372.70 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 44 | 378.19 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 45 | 383.67 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 46 | 389.16 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 47 | 398.44 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 48 | 409.42 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 49 | 420.40 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 50 | 431.37 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 51 | 442.35 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 52 | 453.32 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 53 | 464.30 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 54 | 475.27 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 55 | 486.75 | 2.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 56 | 497.23 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 57 | 508.20 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 58 | 519.18 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 59 | 530.15 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 60 | 540.27 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 61 | 551.21 | 2.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 62 | 562.23 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 63 | 574.18 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 64 | 585.15 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 65 | 597.01 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 66 | 607.48 | 2.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 67 | 616.99 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 68 | 627.96 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 69 | 649.94 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 70 | 661.98 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 71 | 672.84 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 72 | 683.81 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 73 | 694.79 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 74 | 705.77 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 75 | 716.74 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 76 | 726.74 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |

#### Detailed Column Boundary Positions

- **single_point_hotspot**: [339.6, 366.1, 396.5, 421.6, 452.5, 492.0, 528.8]
- **gap_span_hotspot**: [339.6, 366.1, 396.5, 421.6, 452.5, 492.0, 528.8]
- **header_anchor**: [340.3, 366.1, 394.5, 421.6, 450.6, 492.0, 528.8]
- **ruled_lines**: []
- **pymupdf_text**: [349.1, 367.1, 408.6, 422.6, 460.2, 504.6, 538.9]
- **camelot_hybrid**: [57.2, 57.2, 57.2, 88.1, 97.1, 123.4, 144.4, 186.7, 187.3, 215.3, 216.4, 305.1, 305.1, 305.1, 305.1, 305.1, 305.1, 313.7, 339.0, 339.7, 398.5, 445.4, 450.0, 463.0, 494.5, 510.5, 517.7, 528.8]
- **pdfplumber_text**: []
- **consensus**: [57.2, 88.1, 97.1, 123.4, 144.4, 187.0, 215.3, 216.4, 305.1, 313.7, 339.6, 349.1, 366.4, 394.5, 396.5, 398.5, 408.6, 421.9, 445.4, 450.3, 452.5, 460.2, 463.0, 492.0, 494.5, 504.6, 510.5, 517.7, 528.8, 538.9]

**Column count grouping:**

- 0 columns: ruled_lines, pdfplumber_text
- 7 columns: single_point_hotspot, gap_span_hotspot, header_anchor, pymupdf_text
- 28 columns: camelot_hybrid

---

### AQ3D94VC_table_3

- **Paper**: AQ3D94VC
- **Page**: 6
- **Caption**: Table 3. Correlations of HRV Parameters Obtained by Fast Fourier Transformations with Interbeat Interval (IBI), Pulse Transit Time (PTT), and Baroreflex Sensitivity (BRS) Recorded during Baseline (BL) and Cognitive Load (Task) in the Duschek, Muckenthaler, et al. (2009; Panel A, n = 60) and Duschek et al. (2013; Panel B, n = 54) Studies
- **BBox**: (313.7430725097656, 136.4815216064453, 552.8777465820312, 275.5025634765625)

**Per-method GT accuracy (from stress test):**

| Method | Accuracy |
|--------|----------|
| single_point_hotspot+rawdict | 100.0% |
| single_point_hotspot+word_assignment | 100.0% |
| single_point_hotspot+pdfminer | 100.0% |
| gap_span_hotspot+rawdict | 100.0% |
| gap_span_hotspot+word_assignment | 100.0% |
| gap_span_hotspot+pdfminer | 100.0% |
| header_anchor+rawdict | 100.0% |
| header_anchor+word_assignment | 100.0% |
| header_anchor+pdfminer | 100.0% |
| pdfplumber_text+rawdict | 100.0% |
| pdfplumber_text+word_assignment | 100.0% |
| pdfplumber_text+pdfminer | 100.0% |
| pymupdf_lines+rawdict | 17.1% |
| pymupdf_lines+word_assignment | 17.1% |
| pymupdf_lines_strict+rawdict | 17.1% |
| pymupdf_lines_strict+word_assignment | 17.1% |
| pymupdf_text+rawdict | 10.0% |
| pymupdf_text+word_assignment | 10.0% |
| ruled_lines+rawdict | 0.0% |
| ruled_lines+word_assignment | 0.0% |
| ruled_lines+pdfminer | 0.0% |
| pymupdf_lines+pdfminer | 0.0% |
| pymupdf_lines_strict+pdfminer | 0.0% |
| pymupdf_text+pdfminer | 0.0% |

**Context properties (adaptive threshold inputs):**

- median_word_height: 7.9824
- median_word_gap: 34.7450
- median_ruled_line_thickness: 0.49900001287460327
- word count: 64
- drawing count: 1

**Structure method boundary counts:**

| Method | Columns | Rows | Activated |
|--------|---------|------|-----------|
| single_point_hotspot | 5 | 0 | YES |
| gap_span_hotspot | 5 | 0 | YES |
| global_cliff | - | - | SKIPPED |
| per_row_cliff | - | - | SKIPPED |
| header_anchor | 4 | 0 | YES |
| ruled_lines | 0 | 2 | YES |
| pymupdf_lines | 0 | 0 | No hypothesis |
| pymupdf_lines_strict | 0 | 0 | No hypothesis |
| pymupdf_text | 4 | 15 | YES |
| camelot_lattice | 0 | 0 | No hypothesis |
| camelot_hybrid | 18 | 45 | YES |
| pdfplumber_lines | 0 | 0 | No hypothesis |
| pdfplumber_text | 0 | 8 | YES |

**Combination parameters:**

- expansion_threshold: 0.9980
- tolerance: 0.4990
- source_methods: 7

**Consensus result: 27 columns, 46 rows**

**Column count comparison:**

| Method | Columns | vs Consensus |
|--------|---------|-------------|
| camelot_hybrid | 18 | -9 |
| gap_span_hotspot | 5 | -22 |
| header_anchor | 4 | -23 |
| pdfplumber_text | 0 | -27 |
| pymupdf_text | 4 | -23 |
| ruled_lines | 0 | -27 |
| single_point_hotspot | 5 | -22 |
| **consensus** | **27** | - |

#### Column Axis

- **Input points**: 36
- **Median confidence**: 1.0000
- **Acceptance threshold**: 0.5000
- **Clusters formed**: 27
- **Accepted positions**: 27

- **Points expanded**: 36/36

**Input points by provenance:**

| Method | Points |
|--------|--------|
| camelot_hybrid | 18 |
| header_anchor | 4 |
| hotspot | 10 |
| pymupdf_text | 4 |

**Cluster details:**

| # | Position | Confidence | Methods | Accepted | Threshold |
|---|----------|------------|---------|----------|-----------|
| 0 | 57.21 | 2.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 1 | 113.38 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 2 | 120.74 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 3 | 142.97 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 4 | 146.39 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 5 | 147.40 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 6 | 181.79 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 7 | 197.31 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 8 | 219.29 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 9 | 259.93 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 10 | 305.06 | 2.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 11 | 313.74 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 12 | 358.58 | 0.9500 | 1 (header_anchor) | YES | 0.5000 |
| 13 | 360.10 | 1.3333 | 1 (hotspot) | YES | 0.5000 |
| 14 | 361.63 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 15 | 376.80 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 16 | 384.57 | 0.5333 | 1 (hotspot) | YES | 0.5000 |
| 17 | 410.08 | 3.4167 | 3 (camelot_hybrid, header_anchor, hotspot) | YES | 0.5000 |
| 18 | 428.76 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 19 | 460.65 | 0.9500 | 1 (header_anchor) | YES | 0.5000 |
| 20 | 462.65 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 21 | 464.09 | 1.7333 | 1 (hotspot) | YES | 0.5000 |
| 22 | 482.21 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 23 | 513.36 | 0.9500 | 1 (header_anchor) | YES | 0.5000 |
| 24 | 515.35 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 25 | 517.54 | 1.7333 | 1 (hotspot) | YES | 0.5000 |
| 26 | 534.91 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |

#### Row Axis

- **Input points**: 70
- **Median confidence**: 1.0000
- **Acceptance threshold**: 0.5000
- **Clusters formed**: 46
- **Accepted positions**: 46

- **Points expanded**: 70/70

**Input points by provenance:**

| Method | Points |
|--------|--------|
| camelot_hybrid | 45 |
| pdfplumber_text | 8 |
| pymupdf_text | 15 |
| ruled_lines | 2 |

**Cluster details:**

| # | Position | Confidence | Methods | Accepted | Threshold |
|---|----------|------------|---------|----------|-----------|
| 0 | 80.10 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 1 | 136.15 | 2.0000 | 2 (camelot_hybrid, ruled_lines) | YES | 0.5000 |
| 2 | 143.95 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 3 | 146.05 | 1.0000 | 1 (ruled_lines) | YES | 0.5000 |
| 4 | 147.29 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 5 | 151.11 | 2.0000 | 2 (pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 6 | 159.64 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 7 | 168.63 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 8 | 177.60 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 9 | 186.61 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 10 | 195.44 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 11 | 204.60 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 12 | 213.32 | 4.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 13 | 222.20 | 3.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 14 | 230.87 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 15 | 240.16 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 16 | 249.14 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 17 | 258.12 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 18 | 266.79 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 19 | 553.10 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 20 | 563.08 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 21 | 570.58 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 22 | 575.57 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 23 | 585.55 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 24 | 595.03 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 25 | 600.02 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 26 | 605.00 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 27 | 609.99 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 28 | 614.98 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 29 | 619.97 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 30 | 624.96 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 31 | 629.95 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 32 | 639.45 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 33 | 649.41 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 34 | 654.50 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 35 | 659.38 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 36 | 664.37 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 37 | 669.10 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 38 | 674.46 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 39 | 684.33 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 40 | 694.79 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 41 | 703.61 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 42 | 708.76 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 43 | 713.64 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 44 | 718.57 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 45 | 728.13 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |

#### Detailed Column Boundary Positions

- **single_point_hotspot**: [360.1, 384.6, 410.1, 464.1, 517.5]
- **gap_span_hotspot**: [360.1, 384.6, 410.1, 464.1, 517.5]
- **header_anchor**: [358.6, 410.1, 460.7, 513.4]
- **ruled_lines**: []
- **pymupdf_text**: [376.8, 428.8, 482.2, 534.9]
- **camelot_hybrid**: [57.2, 57.2, 113.4, 120.7, 143.0, 146.4, 147.4, 181.8, 197.3, 219.3, 259.9, 305.1, 305.1, 313.7, 361.6, 409.9, 462.7, 515.4]
- **pdfplumber_text**: []
- **consensus**: [57.2, 113.4, 120.7, 143.0, 146.4, 147.4, 181.8, 197.3, 219.3, 259.9, 305.1, 313.7, 358.6, 360.1, 361.6, 376.8, 384.6, 410.1, 428.8, 460.7, 462.7, 464.1, 482.2, 513.4, 515.4, 517.5, 534.9]

**Column count grouping:**

- 0 columns: ruled_lines, pdfplumber_text
- 4 columns: header_anchor, pymupdf_text
- 5 columns: single_point_hotspot, gap_span_hotspot
- 18 columns: camelot_hybrid

---

### AQ3D94VC_table_4

- **Paper**: AQ3D94VC
- **Page**: 6
- **Caption**: Table 4. Correlations of HRV Parameters Obtained by the Autoregression Technique with Interbeat Interval (IBI), Pre- Ejection Period (PEP), and Baroreflex Sensitivity (BRS) in the Physical Exercise Study (cf. Table 2) by Martín-Vázquez and Reyes del Paso (2010; Panel A, n = 40) and in the Chronic Pain Study by Reyes del Paso, Garrido, et al. (2010; Panel B, n = 64)
- **BBox**: (57.207672119140625, 553.809326171875, 296.34161376953125, 693.0457763671875)

**Per-method GT accuracy (from stress test):**

| Method | Accuracy |
|--------|----------|
| single_point_hotspot+rawdict | 100.0% |
| single_point_hotspot+word_assignment | 100.0% |
| single_point_hotspot+pdfminer | 100.0% |
| gap_span_hotspot+rawdict | 100.0% |
| gap_span_hotspot+word_assignment | 100.0% |
| gap_span_hotspot+pdfminer | 100.0% |
| header_anchor+rawdict | 100.0% |
| header_anchor+word_assignment | 100.0% |
| header_anchor+pdfminer | 100.0% |
| pdfplumber_text+rawdict | 100.0% |
| pdfplumber_text+word_assignment | 100.0% |
| pdfplumber_text+pdfminer | 100.0% |
| ruled_lines+rawdict | 0.0% |
| ruled_lines+word_assignment | 0.0% |
| ruled_lines+pdfminer | 0.0% |
| pymupdf_lines+rawdict | 0.0% |
| pymupdf_lines+word_assignment | 0.0% |
| pymupdf_lines+pdfminer | 0.0% |
| pymupdf_lines_strict+rawdict | 0.0% |
| pymupdf_lines_strict+word_assignment | 0.0% |
| pymupdf_lines_strict+pdfminer | 0.0% |
| pymupdf_text+rawdict | 0.0% |
| pymupdf_text+word_assignment | 0.0% |
| pymupdf_text+pdfminer | 0.0% |

**Context properties (adaptive threshold inputs):**

- median_word_height: 7.9824
- median_word_gap: 36.5450
- median_ruled_line_thickness: 0.49900001287460327
- word count: 64
- drawing count: 1

**Structure method boundary counts:**

| Method | Columns | Rows | Activated |
|--------|---------|------|-----------|
| single_point_hotspot | 5 | 0 | YES |
| gap_span_hotspot | 5 | 0 | YES |
| global_cliff | - | - | SKIPPED |
| per_row_cliff | - | - | SKIPPED |
| header_anchor | 4 | 0 | YES |
| ruled_lines | 0 | 2 | YES |
| pymupdf_lines | 0 | 0 | No hypothesis |
| pymupdf_lines_strict | 0 | 0 | No hypothesis |
| pymupdf_text | 4 | 15 | YES |
| camelot_lattice | 0 | 0 | No hypothesis |
| camelot_hybrid | 36 | 54 | YES |
| pdfplumber_lines | 0 | 0 | No hypothesis |
| pdfplumber_text | 0 | 10 | YES |

**Combination parameters:**

- expansion_threshold: 0.9980
- tolerance: 0.4990
- source_methods: 7

**Consensus result: 36 columns, 62 rows**

**Column count comparison:**

| Method | Columns | vs Consensus |
|--------|---------|-------------|
| camelot_hybrid | 36 | 0 |
| gap_span_hotspot | 5 | -31 |
| header_anchor | 4 | -32 |
| pdfplumber_text | 0 | -36 |
| pymupdf_text | 4 | -32 |
| ruled_lines | 0 | -36 |
| single_point_hotspot | 5 | -31 |
| **consensus** | **36** | - |

#### Column Axis

- **Input points**: 54
- **Median confidence**: 1.0000
- **Acceptance threshold**: 0.5000
- **Clusters formed**: 37
- **Accepted positions**: 36

- **Points expanded**: 54/54

**Input points by provenance:**

| Method | Points |
|--------|--------|
| camelot_hybrid | 36 |
| header_anchor | 4 |
| hotspot | 10 |
| pymupdf_text | 4 |

**Cluster details:**

| # | Position | Confidence | Methods | Accepted | Threshold |
|---|----------|------------|---------|----------|-----------|
| 0 | 57.21 | 2.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 1 | 75.49 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 2 | 91.10 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 3 | 102.99 | 0.9500 | 1 (header_anchor) | YES | 0.5000 |
| 4 | 104.59 | 1.1765 | 1 (hotspot) | YES | 0.5000 |
| 5 | 106.19 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 6 | 122.46 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 7 | 129.12 | 0.4706 | 1 (hotspot) | NO | 0.5000 |
| 8 | 136.65 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 9 | 148.77 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 10 | 157.26 | 4.1853 | 3 (camelot_hybrid, header_anchor, hotspot) | YES | 0.5000 |
| 11 | 176.60 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 12 | 204.98 | 2.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 13 | 209.60 | 2.4794 | 2 (header_anchor, hotspot) | YES | 0.5000 |
| 14 | 211.59 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 15 | 227.87 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 16 | 231.51 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 17 | 243.63 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 18 | 260.11 | 2.4206 | 2 (header_anchor, hotspot) | YES | 0.5000 |
| 19 | 262.10 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 20 | 278.38 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 21 | 305.07 | 4.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 22 | 313.74 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 23 | 359.40 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 24 | 370.98 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 25 | 397.25 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 26 | 410.52 | 2.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 27 | 413.61 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 28 | 434.98 | 2.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 29 | 462.65 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 30 | 474.08 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 31 | 483.40 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 32 | 508.56 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 33 | 515.35 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 34 | 523.48 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 35 | 534.29 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 36 | 538.62 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |

#### Row Axis

- **Input points**: 81
- **Median confidence**: 1.0000
- **Acceptance threshold**: 0.5000
- **Clusters formed**: 62
- **Accepted positions**: 62

- **Points expanded**: 81/81

**Input points by provenance:**

| Method | Points |
|--------|--------|
| camelot_hybrid | 54 |
| pdfplumber_text | 10 |
| pymupdf_text | 15 |
| ruled_lines | 2 |

**Cluster details:**

| # | Position | Confidence | Methods | Accepted | Threshold |
|---|----------|------------|---------|----------|-----------|
| 0 | 70.07 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 1 | 135.81 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 2 | 146.50 | 2.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 3 | 153.38 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 4 | 158.37 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 5 | 168.24 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 6 | 177.95 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 7 | 182.92 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 8 | 187.80 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 9 | 192.90 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 10 | 197.78 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 11 | 202.77 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 12 | 212.75 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 13 | 221.97 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 14 | 227.22 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 15 | 231.95 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 16 | 237.20 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 17 | 242.18 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 18 | 247.17 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 19 | 252.16 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 20 | 257.15 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 21 | 266.76 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 22 | 277.71 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 23 | 286.41 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 24 | 291.56 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 25 | 296.44 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 26 | 301.54 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 27 | 310.81 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 28 | 321.62 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 29 | 332.59 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 30 | 342.59 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 31 | 353.29 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 32 | 358.78 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 33 | 364.26 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 34 | 369.75 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 35 | 553.47 | 2.0000 | 2 (camelot_hybrid, ruled_lines) | YES | 0.5000 |
| 36 | 561.28 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 37 | 563.38 | 1.0000 | 1 (ruled_lines) | YES | 0.5000 |
| 38 | 564.61 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 39 | 568.26 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 40 | 574.05 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 41 | 576.35 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 42 | 585.44 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 43 | 594.63 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 44 | 596.00 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 45 | 603.61 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 46 | 606.98 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 47 | 607.98 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 48 | 612.59 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 49 | 617.93 | 2.0000 | 2 (camelot_hybrid, pdfplumber_text) | YES | 0.5000 |
| 50 | 621.57 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 51 | 628.97 | 2.0000 | 2 (camelot_hybrid, pdfplumber_text) | YES | 0.5000 |
| 52 | 630.55 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 53 | 639.68 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 54 | 648.50 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 55 | 650.95 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 56 | 657.54 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 57 | 661.98 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 58 | 666.16 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 59 | 672.83 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 60 | 675.50 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 61 | 684.42 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |

#### Detailed Column Boundary Positions

- **single_point_hotspot**: [104.6, 129.1, 157.9, 209.6, 260.1]
- **gap_span_hotspot**: [104.6, 129.1, 157.9, 209.6, 260.1]
- **header_anchor**: [103.0, 156.9, 209.6, 260.1]
- **ruled_lines**: []
- **pymupdf_text**: [122.5, 176.6, 227.9, 278.4]
- **camelot_hybrid**: [57.2, 57.2, 75.5, 91.1, 106.2, 136.6, 148.8, 156.7, 157.4, 204.5, 205.4, 211.6, 231.5, 243.6, 262.1, 305.1, 305.1, 305.1, 305.1, 313.7, 359.4, 371.0, 397.2, 410.1, 410.9, 413.6, 434.8, 435.1, 462.7, 474.1, 483.4, 508.6, 515.4, 523.5, 534.3, 538.6]
- **pdfplumber_text**: []
- **consensus**: [57.2, 75.5, 91.1, 103.0, 104.6, 106.2, 122.5, 136.6, 148.8, 157.3, 176.6, 205.0, 209.6, 211.6, 227.9, 231.5, 243.6, 260.1, 262.1, 278.4, 305.1, 313.7, 359.4, 371.0, 397.2, 410.5, 413.6, 435.0, 462.7, 474.1, 483.4, 508.6, 515.4, 523.5, 534.3, 538.6]

**Column count grouping:**

- 0 columns: ruled_lines, pdfplumber_text
- 4 columns: header_anchor, pymupdf_text
- 5 columns: single_point_hotspot, gap_span_hotspot
- 36 columns: camelot_hybrid

---

### 9GKLLJH9_table_2

- **Paper**: 9GKLLJH9
- **Page**: 6
- **Caption**: Table 2 Coefficients From Best-Fitting Cross-Lagged Panel Model (Model 6)
- **BBox**: (47.999603271484375, 118.40787506103516, 288.0240173339844, 292.2356262207031)

**Per-method GT accuracy (from stress test):**

| Method | Accuracy |
|--------|----------|
| single_point_hotspot+rawdict | 100.0% |
| single_point_hotspot+word_assignment | 100.0% |
| single_point_hotspot+pdfminer | 100.0% |
| gap_span_hotspot+rawdict | 100.0% |
| gap_span_hotspot+word_assignment | 100.0% |
| gap_span_hotspot+pdfminer | 100.0% |
| header_anchor+rawdict | 100.0% |
| header_anchor+word_assignment | 100.0% |
| header_anchor+pdfminer | 100.0% |
| ruled_lines+rawdict | 100.0% |
| ruled_lines+word_assignment | 100.0% |
| ruled_lines+pdfminer | 100.0% |
| pymupdf_lines+pdfminer | 100.0% |
| pymupdf_lines_strict+pdfminer | 100.0% |
| pymupdf_text+pdfminer | 100.0% |
| pdfplumber_text+pdfminer | 100.0% |
| pymupdf_lines+word_assignment | 59.1% |
| pymupdf_lines_strict+word_assignment | 59.1% |
| pymupdf_lines+rawdict | 52.7% |
| pymupdf_lines_strict+rawdict | 52.7% |
| pdfplumber_text+word_assignment | 28.6% |
| pymupdf_text+word_assignment | 25.6% |
| pdfplumber_text+rawdict | 21.4% |
| pymupdf_text+rawdict | 7.1% |

**Context properties (adaptive threshold inputs):**

- median_word_height: 8.0000
- median_word_gap: 23.2072
- median_ruled_line_thickness: 0.5
- word count: 97
- drawing count: 2

**Structure method boundary counts:**

| Method | Columns | Rows | Activated |
|--------|---------|------|-----------|
| single_point_hotspot | 8 | 0 | YES |
| gap_span_hotspot | 9 | 0 | YES |
| global_cliff | - | - | SKIPPED |
| per_row_cliff | - | - | SKIPPED |
| header_anchor | 9 | 0 | YES |
| ruled_lines | 0 | 2 | YES |
| pymupdf_lines | 0 | 0 | No hypothesis |
| pymupdf_lines_strict | 0 | 0 | No hypothesis |
| pymupdf_text | 5 | 33 | YES |
| camelot_lattice | 0 | 0 | No hypothesis |
| camelot_hybrid | 0 | 30 | YES |
| pdfplumber_lines | 0 | 0 | No hypothesis |
| pdfplumber_text | 1 | 21 | YES |

**Combination parameters:**

- expansion_threshold: 1.0000
- tolerance: 0.5000
- source_methods: 7

**Consensus result: 17 columns, 56 rows**

**Column count comparison:**

| Method | Columns | vs Consensus |
|--------|---------|-------------|
| camelot_hybrid | 0 | -17 |
| gap_span_hotspot | 9 | -8 |
| header_anchor | 9 | -8 |
| pdfplumber_text | 1 | -16 |
| pymupdf_text | 5 | -12 |
| ruled_lines | 0 | -17 |
| single_point_hotspot | 8 | -9 |
| **consensus** | **17** | - |

#### Column Axis

- **Input points**: 32
- **Median confidence**: 0.9531
- **Acceptance threshold**: 0.4766
- **Clusters formed**: 20
- **Accepted positions**: 17

- **Points expanded**: 32/32

**Input points by provenance:**

| Method | Points |
|--------|--------|
| header_anchor | 9 |
| hotspot | 17 |
| pdfplumber_text | 1 |
| pymupdf_text | 5 |

**Cluster details:**

| # | Position | Confidence | Methods | Accepted | Threshold |
|---|----------|------------|---------|----------|-----------|
| 0 | 79.41 | 1.0562 | 2 (header_anchor, hotspot) | YES | 0.4766 |
| 1 | 93.15 | 0.1875 | 1 (hotspot) | NO | 0.4766 |
| 2 | 105.37 | 1.1187 | 2 (header_anchor, hotspot) | YES | 0.4766 |
| 3 | 112.92 | 1.0000 | 1 (pymupdf_text) | YES | 0.4766 |
| 4 | 129.32 | 0.1562 | 1 (hotspot) | NO | 0.4766 |
| 5 | 133.35 | 0.9000 | 1 (header_anchor) | YES | 0.4766 |
| 6 | 152.24 | 1.2125 | 2 (header_anchor, hotspot) | YES | 0.4766 |
| 7 | 165.94 | 0.0625 | 1 (hotspot) | NO | 0.4766 |
| 8 | 170.55 | 1.0000 | 1 (pymupdf_text) | YES | 0.4766 |
| 9 | 190.33 | 0.9000 | 1 (header_anchor) | YES | 0.4766 |
| 10 | 196.16 | 0.9688 | 1 (hotspot) | YES | 0.4766 |
| 11 | 203.26 | 0.9000 | 1 (header_anchor) | YES | 0.4766 |
| 12 | 204.83 | 1.0000 | 1 (pymupdf_text) | YES | 0.4766 |
| 13 | 228.53 | 0.9375 | 1 (hotspot) | YES | 0.4766 |
| 14 | 231.95 | 0.9000 | 1 (header_anchor) | YES | 0.4766 |
| 15 | 235.30 | 1.0000 | 1 (pymupdf_text) | YES | 0.4766 |
| 16 | 255.31 | 0.9000 | 1 (header_anchor) | YES | 0.4766 |
| 17 | 265.26 | 1.9375 | 2 (hotspot, pdfplumber_text) | YES | 0.4766 |
| 18 | 270.84 | 1.0000 | 1 (pymupdf_text) | YES | 0.4766 |
| 19 | 279.78 | 0.9000 | 1 (header_anchor) | YES | 0.4766 |

#### Row Axis

- **Input points**: 86
- **Median confidence**: 1.0000
- **Acceptance threshold**: 0.5000
- **Clusters formed**: 56
- **Accepted positions**: 56

- **Points expanded**: 86/86

**Input points by provenance:**

| Method | Points |
|--------|--------|
| camelot_hybrid | 30 |
| pdfplumber_text | 21 |
| pymupdf_text | 33 |
| ruled_lines | 2 |

**Cluster details:**

| # | Position | Confidence | Methods | Accepted | Threshold |
|---|----------|------------|---------|----------|-----------|
| 0 | 125.90 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 1 | 128.75 | 0.9999 | 1 (ruled_lines) | YES | 0.5000 |
| 2 | 129.99 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 3 | 134.45 | 2.0000 | 2 (pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 4 | 142.04 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 5 | 147.01 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 6 | 148.10 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 7 | 149.29 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 8 | 151.72 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 9 | 154.95 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 10 | 156.01 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 11 | 158.29 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 12 | 160.96 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 13 | 165.01 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 14 | 167.37 | 2.0000 | 2 (camelot_hybrid, pdfplumber_text) | YES | 0.5000 |
| 15 | 169.72 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 16 | 174.02 | 2.0000 | 2 (pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 17 | 176.29 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 18 | 178.72 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 19 | 183.01 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 20 | 185.29 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 21 | 187.72 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 22 | 190.64 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 23 | 192.01 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 24 | 194.29 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 25 | 197.20 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 26 | 198.44 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 27 | 205.31 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 28 | 210.09 | 2.0000 | 2 (pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 29 | 212.29 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 30 | 214.70 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 31 | 219.01 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 32 | 221.43 | 2.0000 | 2 (camelot_hybrid, pdfplumber_text) | YES | 0.5000 |
| 33 | 223.72 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |
| 34 | 227.63 | 2.0000 | 2 (pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 35 | 230.29 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 36 | 233.13 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 37 | 237.01 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 38 | 239.29 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 39 | 241.29 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 40 | 246.01 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 41 | 247.28 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 42 | 248.29 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 43 | 251.11 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 44 | 255.01 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 45 | 257.29 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 46 | 260.04 | 2.0000 | 2 (pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 47 | 262.08 | 1.9999 | 2 (camelot_hybrid, ruled_lines) | YES | 0.5000 |
| 48 | 266.10 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 49 | 268.06 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 50 | 270.07 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 51 | 272.29 | 1.0000 | 1 (camelot_hybrid) | YES | 0.5000 |
| 52 | 274.35 | 3.0000 | 3 (camelot_hybrid, pdfplumber_text, pymupdf_text) | YES | 0.5000 |
| 53 | 279.07 | 1.0000 | 1 (pymupdf_text) | YES | 0.5000 |
| 54 | 280.07 | 1.0000 | 1 (pdfplumber_text) | YES | 0.5000 |
| 55 | 283.72 | 2.0000 | 2 (camelot_hybrid, pymupdf_text) | YES | 0.5000 |

#### Detailed Column Boundary Positions

- **single_point_hotspot**: [78.7, 93.2, 105.6, 129.3, 152.8, 196.2, 228.5, 265.4]
- **gap_span_hotspot**: [78.7, 93.2, 105.6, 129.3, 152.8, 165.9, 196.2, 228.5, 265.4]
- **header_anchor**: [79.5, 105.3, 133.3, 152.1, 190.3, 203.3, 232.0, 255.3, 279.8]
- **ruled_lines**: []
- **pymupdf_text**: [112.9, 170.6, 204.8, 235.3, 270.8]
- **camelot_hybrid**: []
- **pdfplumber_text**: [265.1]
- **consensus**: [79.4, 105.4, 112.9, 133.3, 152.2, 170.6, 190.3, 196.2, 203.3, 204.8, 228.5, 232.0, 235.3, 255.3, 265.3, 270.8, 279.8]

**Column count grouping:**

- 0 columns: ruled_lines, camelot_hybrid
- 1 columns: pdfplumber_text
- 5 columns: pymupdf_text
- 8 columns: single_point_hotspot
- 9 columns: gap_span_hotspot, header_anchor

---

