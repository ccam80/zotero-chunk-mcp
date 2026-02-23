# LLM vs Pipeline Table Extraction Comparison

## Per-Table Accuracy

| Table ID | LLM Model | LLM Fuzzy% | LLM Cell% | Pipeline Cell% | Winner |
| --- | --- | --- | --- | --- | --- |
| 5SIZVS65_table_1 | haiku | 100.0 | 100.0 | 0.0 | LLM |
| 5SIZVS65_table_2 | haiku | 100.0 | 100.0 | 0.0 | LLM |
| 5SIZVS65_table_3 | haiku | 100.0 | 100.0 | 0.0 | LLM |
| 5SIZVS65_table_4 | haiku | 96.6 | 79.5 | 0.0 | LLM |
| 5SIZVS65_table_5 | haiku | 100.0 | 100.0 | 0.0 | LLM |
| 9GKLLJH9_table_1 | haiku | 100.0 | 100.0 | 0.0 | LLM |
| 9GKLLJH9_table_2 | sonnet | 94.1 | 85.7 | 0.0 | LLM |
| AQ3D94VC_table_1 | sonnet | 100.0 | 100.0 | 0.0 | LLM |
| AQ3D94VC_table_2 | sonnet | 100.0 | 100.0 | 0.0 | LLM |
| AQ3D94VC_table_3 | haiku | 99.0 | 75.7 | 0.0 | LLM |
| AQ3D94VC_table_4 | haiku | 99.0 | 77.1 | 0.0 | LLM |
| AQ3D94VC_table_5 | haiku | 100.0 | 100.0 | 0.0 | LLM |
| C626CYVT_table_1 | haiku | 100.0 | 100.0 | 0.0 | LLM |
| DPYRZTFI_orphan_p7_t3 | haiku | 0.0 | 0.0 | - | LLM only |
| DPYRZTFI_table_1 | sonnet | 99.8 | 99.4 | 0.0 | LLM |
| DPYRZTFI_table_2 | sonnet | 90.5 | 100.0 | 0.0 | LLM |
| DPYRZTFI_table_3 | sonnet | 93.0 | 100.0 | 0.0 | LLM |
| SCPXVBLY_orphan_p1_t0 | haiku | 0.0 | 0.0 | - | LLM only |
| SCPXVBLY_table_1 | sonnet | 69.3 | 58.3 | 0.0 | LLM |
| SCPXVBLY_table_1_p16 | haiku | 95.8 | 66.7 | 0.0 | LLM |
| SCPXVBLY_table_2 | sonnet | 61.5 | 37.5 | 0.0 | LLM |
| SCPXVBLY_table_2_p19 | haiku | 70.1 | 37.5 | 0.0 | LLM |
| SCPXVBLY_table_2_p20 | haiku | 80.9 | 25.0 | 0.0 | LLM |
| SCPXVBLY_table_3 | sonnet | 72.5 | 91.7 | 0.0 | LLM |
| SCPXVBLY_table_3_p31 | haiku | 100.0 | 100.0 | 0.0 | LLM |
| VP3NJ74M_orphan_p1_t0 | sonnet | 0.0 | 0.0 | - | LLM only |
| VP3NJ74M_table_1 | sonnet | 91.1 | 0.0 | 0.0 | LLM |
| VP3NJ74M_table_2 | sonnet | 96.2 | 0.0 | 0.0 | LLM |
| VP3NJ74M_table_3 | sonnet | 98.4 | 0.0 | 0.0 | LLM |
| VP3NJ74M_table_4 | sonnet | 91.8 | 93.9 | 0.0 | LLM |
| VP3NJ74M_table_5 | haiku | 84.9 | 100.0 | 0.0 | LLM |
| VP3NJ74M_table_6 | sonnet | 96.7 | 86.7 | 0.0 | LLM |
| XIAINRVS_orphan_p1_t0 | haiku | 0.0 | 0.0 | 0.0 | Tie |
| XIAINRVS_orphan_p2_t1 | haiku | 0.0 | 0.0 | 0.0 | Tie |
| YMWV46JA_table_1 | sonnet | 44.6 | 0.0 | 0.0 | LLM |
| Z9X4JVZ5_orphan_p22_t8 | sonnet | 97.3 | 100.0 | - | LLM only |
| Z9X4JVZ5_orphan_p5_t0 | haiku | 0.0 | 0.0 | - | LLM only |
| Z9X4JVZ5_table_1 | sonnet | 100.0 | 100.0 | 0.0 | LLM |
| Z9X4JVZ5_table_2 | sonnet | 100.0 | 100.0 | 0.0 | LLM |
| Z9X4JVZ5_table_3 | haiku | 100.0 | 100.0 | 0.0 | LLM |
| Z9X4JVZ5_table_4 | sonnet | 100.0 | 100.0 | 0.0 | LLM |
| Z9X4JVZ5_table_5 | sonnet | 100.0 | 100.0 | 0.0 | LLM |
| Z9X4JVZ5_table_6 | sonnet | 100.0 | 100.0 | 0.0 | LLM |
| Z9X4JVZ5_table_7 | sonnet | 100.0 | 100.0 | 0.0 | LLM |

## Win/Loss Summary

- LLM wins: 37 (95%)
- Pipeline wins: 0 (0%)
- Ties (<1% difference): 2 (5%)
- Total compared: 39

## Aggregate Statistics

- LLM mean fuzzy accuracy: 80.1% (n=44)
- LLM median fuzzy accuracy: 97.3%
- Pipeline mean cell accuracy: 0.0% (n=39)
- Pipeline median cell accuracy: 0.0%

## Per-Model Breakdown

### haiku (n=43)
- Mean fuzzy accuracy: 74.2%
- Mean cell accuracy: 67.3%

### sonnet (n=44)
- Mean fuzzy accuracy: 79.2%
- Mean cell accuracy: 67.0%
