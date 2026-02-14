# LLM Quality-Check Agent — Assessment

## Context

After implementing heuristic-based table extraction, phantom scoring, garbled
text detection, and caption matching, the stress test (10 diverse papers) shows
limits to what rule-based approaches can fix.  An LLM shallow-check pass at
index time could address remaining issues.

## Issues an LLM pass would fix

| Issue | LLM approach | Confidence |
|-------|-------------|------------|
| Garbled cell false positives | "Is this cell garbled or legitimate technical content?" | High — trivial classification |
| Phantom/junk tables | "Is this a data table or a layout artifact (TOC, footer, metadata)?" | High |
| Orphan caption generation | "Generate a short descriptive caption for this uncaptioned table" | High |
| 1x1 collapsed tables | "Parse this text block into structured rows and columns" | Medium — depends on how mangled |
| Abstract detection | "Does this document have an abstract? Where does it start?" | High |
| Section heading detection | "What section is this heading? (introduction/methods/results/...)" | High |
| Missing introduction sections | "Where does the introduction begin in this paper?" | High |

**Estimated fix rate: all 8 MAJORs, ~12 of 20 MINORs.**

## Cost estimate

- ~1-2K input tokens per table for quality checking
- ~500 tokens per orphan for caption generation
- ~1K tokens per document for section/abstract validation
- For a 10-table paper: ~$0.01-0.02 with Haiku
- For a 500-paper library: ~$5-10 total (one-time indexing)

## Architecture sketch

```
extract_document(pdf_path)
  → raw extraction (current pipeline)
  → LLM quality pass:
      1. For each table: classify as data/junk/collapsed
      2. For collapsed tables: attempt restructuring
      3. For orphan tables/figures: generate descriptive caption
      4. For document: verify abstract/section boundaries
  → enriched extraction
```

The LLM pass runs AFTER heuristic extraction and BEFORE indexing.
It's a validation/enrichment layer, not a replacement for the extraction pipeline.

## When to revisit

Revisit after clearing heuristic easy wins:
- [ ] Remove phantom scoring (net-negative, removes legitimate content)
- [ ] Add synthetic captions for orphans
- [ ] Fix garbled detector false positives (exclude Greek/math)
- [ ] Add ligature normalization
- [ ] Promote 1x1 to MAJOR

After these, re-run stress test. If MAJORs drop to ≤2, the LLM pass becomes
a polish step. If MAJORs remain high, prioritise the LLM pass.

## Strongest use case

The fortune 1x1 collapsed table: all data crammed into one cell by pymupdf.
No heuristic can restructure `"Electrode configuration 𝑅′ 𝐴(kΩ) 𝐶′ 𝐴(nF)
Ag/AgClNSP 1884 ± 3158 144.8 ± 237.2..."` back into rows and columns.
An LLM can.
