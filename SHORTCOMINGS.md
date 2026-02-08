# Package Shortcomings

Each item is an independent investigation task.

1. **Caption regex too strict** — Requires period after figure number, silently misses formats like `Figure 2:`, `Fig 2.`, `FIGURE 2 -`, `Figure S1.`
2. **Vector figures invisible** — Layout engine classifies vector graphics as `table`, pipe-table parser rejects gibberish, figure vanishes silently
3. **Abstract never detected** — Absorbed into preamble across all papers because layout engine never produces a section-header box for it
4. **Section labels too coarse** — 18 duplicate "methods" labels in one paper makes section-based search reranking useless
5. **Quality grader meaningless** — Papers with missing abstracts, duplicate sections, and lost figures still grade "A"
6. **Scanned PDFs silently empty** — No OCR fallback surfaces zero content with no user-facing error
7. **No caption length guard on caption-box path** — Text-box capped at 800 chars but caption-box path has no limit (one caption is 1,634 chars)
8. **Supplementary figures not handled** — `Figure S1`, `Figure A1`, `Supplementary Figure 2` all rejected by regex
