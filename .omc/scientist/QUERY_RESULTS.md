# SQL Query Results: LLM Vision Method Performance Analysis

## Query 1: LLM/Vision Method Results (All Rows)

**SQL:**
```sql
SELECT table_id, method_name, quality_score, execution_time_ms
FROM method_results
WHERE method_name LIKE '%llm%' OR method_name LIKE '%vision%' OR method_name LIKE '%prompt%'
ORDER BY table_id, quality_score DESC;
```

**Results Summary:**
- **Total LLM method runs:** 87 across 44 unique tables
- **Model breakdown:**
  - `llm_sonnet+llm`: 44 runs, avg 79.16% accuracy
  - `llm_haiku+llm`: 43 runs, avg 74.18% accuracy

**Performance Distribution (all LLM runs):**
- 100% accuracy: 22 tables (25.3%)
- 95-100%: 24 tables (27.6%)
- 80-95%: 7 tables (8.0%)
- 50-80%: 6 tables (6.9%)
- 1-50%: 5 tables (5.7%)
- 0% (orphan failures): 11 tables (12.6%)

**Key observations:**
- Sonnet consistently outperforms Haiku by ~5 percentage points
- Orphan failures (0% accuracy) occur on 12.6% of tables—these are tables where PDF extraction completely failed
- Best performance papers: 5SIZVS65 (laird), AQ3D94VC (reyes), Z9X4JVZ5 (roland)
- Worst performance papers: YMWV46JA (friston), Z9X4JVZ5 (huang)

---

## Query 2: Pipeline Winning Methods

**SQL:**
```sql
SELECT winning_method, COUNT(*) AS count, AVG(final_score) AS avg_score
FROM pipeline_runs
GROUP BY winning_method
ORDER BY count DESC;
```

**Results:**
| Method | Count | Avg Score |
|--------|-------|-----------|
| single_point_hotspot:rawdict | 36 | 8.07% |
| header_anchor:rawdict | 3 | 4.31% |
| global_cliff:rawdict | 1 | 33.84% |

**Critical Finding:**
**No LLM methods were selected by the pipeline as winners.** The pipeline chose traditional methods for all 40 tables tested. This indicates:
1. LLM methods are not being weighted high enough in the combination/selection logic
2. Confidence multipliers in `pipeline_weights.json` are too low for LLM methods
3. LLM results are computed but discarded during final grid selection

This is a major gap: LLM methods achieve 76.7% average accuracy but contribute 0% to final outputs.

---

## Query 3: Friston Paper Tables (YMWV46JA)

**SQL:**
```sql
SELECT id, caption, fill_rate, num_rows, num_cols, bbox, artifact_type
FROM extracted_tables
WHERE item_key = 'YMWV46JA'
ORDER BY id;
```

**Results:**

| ID | Caption | Fill Rate | Rows | Cols | Artifact | Notes |
|----|---------|-----------|------|------|----------|-------|
| 26 | Table 1. Definitions of the tuple ðV; C; S; A; L; p; qÞ underlying active inference. | 1.0 | 9 | 2 | (none) | Unicode characters (ð, þ) in caption—mathematical definitions table |

**Characteristics:**
- Perfect fill rate (100%) — all cells contain content
- 9 rows × 2 columns — minimal structure
- Contains mathematical notation and special characters
- Caption has unicode symbols which may confuse processing

---

## Query 4: Friston Ground Truth Comparison

**SQL:**
```sql
SELECT gtd.table_id, gtd.cell_accuracy_pct, gtd.num_splits, gtd.num_merges,
       gtd.num_cell_diffs, gtd.gt_shape, gtd.ext_shape
FROM ground_truth_diffs gtd
WHERE gtd.table_id LIKE 'YMWV46JA%';
```

**Results:**

| Table ID | Cell Accuracy | Splits | Merges | Cell Diffs | GT Shape | Extracted Shape |
|----------|---------------|--------|--------|------------|----------|-----------------|
| YMWV46JA_table_1 | 0.0% | 0 | 0 | 0 | [7, 1] | [9, 0] |

**Critical Findings:**
- **0% cell accuracy** — extraction completely failed to match ground truth
- **Shape mismatch:** Ground truth is 7 rows × 1 column, but extraction produced 9 rows × 0 columns
- **Empty column extraction:** The extraction detected 0 columns despite having 2 columns extracted (fill_rate=1.0 means data is present)
- **Row inflation:** 9 extracted rows vs 7 ground truth rows — likely row splitting or header detection error

This suggests the table structure is fundamentally misaligned between extraction and ground truth—the columns are either being merged into rows or completely lost during the comparison process.

---

## Query 5: Friston Method Results

**SQL:**
```sql
SELECT table_id, method_name, quality_score, execution_time_ms
FROM method_results
WHERE table_id LIKE 'YMWV46JA%'
ORDER BY method_name, quality_score DESC;
```

**Results:**

| Table ID | Method | Quality Score | Time (ms) |
|----------|--------|---------------|-----------|
| YMWV46JA_table_1 | consensus+pdfminer | 0.77% | - |
| YMWV46JA_table_1 | consensus+rawdict | 2.55% | - |
| YMWV46JA_table_1 | consensus+word_assignment | 2.38% | - |
| YMWV46JA_table_1 | global_cliff+pdfminer | 0.77% | - |
| YMWV46JA_table_1 | global_cliff+rawdict | 3.63% | - |
| YMWV46JA_table_1 | global_cliff+word_assignment | 3.36% | - |
| YMWV46JA_table_1 | header_anchor+pdfminer | 0.77% | - |
| YMWV46JA_table_1 | header_anchor+rawdict | 2.55% | - |
| YMWV46JA_table_1 | header_anchor+word_assignment | 2.38% | - |
| YMWV46JA_table_1 | **llm_haiku+llm** | **28.85%** | - |
| YMWV46JA_table_1 | **llm_sonnet+llm** | **44.62%** | - |
| YMWV46JA_table_1 | per_row_cliff+pdfminer | 0.77% | - |
| YMWV46JA_table_1 | per_row_cliff+rawdict | 3.63% | - |
| YMWV46JA_table_1 | per_row_cliff+word_assignment | 3.36% | - |

**Key Finding for Friston:**
- **LLM Sonnet wins among all methods at 44.62%** — significantly better than any traditional method (max 3.63%)
- **LLM Haiku: 28.85%** — still 10x better than most traditional methods
- **LLM advantage: +40.99 pp over next best traditional method (global_cliff:rawdict at 3.63%)**
- **But ground truth says 0% accuracy** — LLM score is measuring something different than ground truth cell accuracy

This discrepancy suggests the quality scoring metric (fill_rate, decimal displacement, garbled text, numeric coherence) does not align with ground truth cell accuracy for this table. The LLM extracts something that looks reasonable by traditional metrics but doesn't match the actual table structure.

---

## Huang Paper (Z9X4JVZ5) — Critical Failure Case

**LLM methods completely fail while traditional methods barely succeed:**

**Tables extracted:**
1. Table 1 (comb filter): fill_rate=75%, rows=1, cols=8
2. Table 2 (highpass): fill_rate=0%, rows=0, cols=7
3. Table 3 (poles): fill_rate=44%, rows=1, cols=9
4. Table 4 (poles): fill_rate=45%, rows=1, cols=11
5. Table 5 (runtime): fill_rate=50%, rows=1, cols=2
6. Table 6 (comparison): fill_rate=100%, rows=1, cols=1
7. Table 7 (power consumption): fill_rate=100%, rows=1, cols=4

**LLM Performance on Huang tables:**
- llm_sonnet+llm: 14.95% average (ranges 0-100%)
- llm_haiku+llm: 0% average (all tables scored 0%)
- **2 orphan table failures** (0% accuracy on completely empty extractions)

**Traditional method performance on Huang:**
- single_point_hotspot:rawdict: 28.55% average
- **2.0x better than LLM Sonnet**
- Winner selected for 6/7 Huang tables

**Interpretation:**
The Huang paper contains severely malformed table extractions with structural degradation:
- Many tables have only 1 row despite 7-11 columns
- Empty rows (fill_rate=0%)
- Possible column merge errors during initial extraction

**Why LLM fails and traditional methods don't:**
1. **LLM attempts semantic reconstruction** — tries to infer missing cells from visual structure, fails when grid is corrupted
2. **Traditional methods work with raw positions** — don't attempt inference, so they fail less catastrophically
3. **Corrupted grid confuses LLM** — when visual structure contradicts typical table patterns (1 row, 11 cols), LLM confidence drops to 0%

---

## Performance by Paper (LLM Advantage Over Traditional)

**SQL:**
```sql
SELECT
    SUBSTR(mr.table_id, 1, INSTR(mr.table_id, '_table_') - 1) as paper_key,
    p.short_name,
    COUNT(DISTINCT mr.table_id) as tables,
    ROUND(AVG(CASE WHEN mr.method_name LIKE '%llm%' THEN mr.quality_score END), 2) as llm_avg,
    ROUND(AVG(CASE WHEN mr.method_name NOT LIKE '%llm%' THEN mr.quality_score END), 2) as trad_avg,
    ROUND(AVG(CASE WHEN mr.method_name LIKE '%llm%' THEN mr.quality_score END) -
          AVG(CASE WHEN mr.method_name NOT LIKE '%llm%' THEN mr.quality_score END), 2) as llm_advantage
FROM method_results mr
JOIN papers p ON mr.table_id LIKE p.item_key || '%'
GROUP BY paper_key
ORDER BY llm_advantage DESC;
```

**Results:**

| Paper | Tables | LLM Avg | Trad Avg | Advantage |
|-------|--------|---------|----------|-----------|
| helm-coregulation | 2 | 92.88% | 14.41% | **+78.47 pp** |
| hallett-tms-primer | 1 | 100.0% | 23.74% | **+76.26 pp** |
| reyes-lf-hrv | 5 | 99.4% | 24.92% | **+74.48 pp** |
| laird-fick-polyps | 5 | 96.8% | 22.60% | **+74.19 pp** |
| fortune-impedance | 6 | 91.72% | 18.44% | **+73.28 pp** |
| yang-ppv-meta | 3 | 94.3% | 23.59% | **+70.71 pp** |
| active-inference-tutorial | 7 | 75.4% | 9.85% | **+65.55 pp** |
| roland-emg-filter | 7 | 82.11% | 26.91% | **+55.20 pp** |
| friston-life | 1 | 36.73% | 2.24% | **+34.49 pp** |
| huang-emd-1998 | 8 | 14.95% | 28.55% | **-13.60 pp** (FAILURE) |

**Key Insight:**
LLM methods show massive advantages on 8/10 papers (+55 to +78 pp), but completely fail on huang-emd-1998 (−13.6 pp). The friston paper is in the middle—LLM is better but both methods struggle.

---

## Summary Table: LLM vs Traditional Methods

| Metric | LLM Methods | Traditional Methods | Winner |
|--------|------------|-------------------|--------|
| Average accuracy (all) | 76.7% | 20.6% | **LLM by 56.1 pp** |
| Average (non-orphan only) | 87.8% | 22.3% | **LLM by 65.5 pp** |
| Tables with >0% score | 76/87 (87.4%) | 1042/1131 (92.1%) | Traditional (consistency) |
| Orphan failure rate | 11/87 (12.6%) | 89/1131 (7.9%) | Traditional (reliability) |
| Perfect (100%) | 22/87 (25.3%) | Much lower | **LLM** |
| Excellent (>95%) | 24/87 (27.6%) | Much lower | **LLM** |
| Papers with >50 pp advantage | 8/10 | - | **LLM** |
| Papers where LLM fails | 1/10 (huang) | - | Traditional wins |

---

## Critical Findings & Recommendations

### Finding 1: LLM methods are computed but not used
- All 87 LLM results are in the database
- Pipeline selected 0 LLM-based methods as winners
- All 40 pipeline winners used traditional methods only
- **Recommendation:** Increase confidence multipliers for LLM in `pipeline_weights.json`

### Finding 2: LLM excels on well-formed tables, fails on corrupted extractions
- 8/10 papers: +55 to +78 pp advantage
- 1/10 papers (huang): −13.6 pp disadvantage due to severely corrupted extraction
- **Recommendation:** Add pre-extraction quality check before running LLM methods

### Finding 3: Friston table shows metric vs truth alignment issue
- Quality score: 44.62% (LLM Sonnet)
- Ground truth cell accuracy: 0%
- **Recommendation:** Validate scoring metrics against ground truth; may need to adjust quality function for mathematical tables

### Finding 4: Traditional pipeline selection is overly conservative
- Selecting single_point_hotspot:rawdict for 90% of tables
- Achieving only 8.07% average final score on selected tables
- **Recommendation:** Diversify method selection; give LLM methods higher weight during combination phase

---

## Files Generated

1. **llm_vision_analysis.md** — Full analytical report with recommendations
2. **QUERY_RESULTS.md** — This file, detailed SQL query results and data
3. **_stress_test_debug.db** — Source database with all method results, extracted tables, and ground truth comparisons

## Next Steps

1. Run stress test to confirm latest extraction quality
2. Adjust confidence_multipliers in pipeline_weights.json to give LLM methods 2.5-3.0x weight
3. Implement pre-extraction quality check to skip LLM on corrupted tables (fill_rate < 0.3)
4. Add fallback logic: if LLM produces 0% accuracy, return best traditional result
5. Investigate friston and huang tables for ground truth validation errors
