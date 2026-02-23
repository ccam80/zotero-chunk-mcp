# Production Agent QA Pipeline — Design Document

This document scopes what a production-mode agent QA pipeline would look like, where every newly-indexed PDF gets an automatic haiku agent QA pass on its extracted tables.

## 1. Cost Analysis

### Token estimates per table

A 300 DPI PNG of a typical academic table (roughly 500x300 PDF points) renders to approximately 1000x600 pixels. Anthropic's vision token pricing charges based on image resolution:

- **Typical table image at 300 DPI**: ~1,568 input tokens (image) + ~200 tokens (prompt text + extraction JSON) = **~1,768 input tokens per table**
- **Agent response**: ~150-400 output tokens (JSON with errors list), average ~250 tokens

### Haiku pricing (as of early 2026)

- Input: $0.25 per million tokens
- Output: $1.25 per million tokens

### Per-table cost

- Input cost: 1,768 tokens x $0.25/1M = $0.000442
- Output cost: 250 tokens x $1.25/1M = $0.0003125
- **Total per table: ~$0.00076** (less than one-tenth of a cent)

### Per-paper cost

From the 10-paper corpus, the average non-artifact table count is approximately 3.9 tables per paper (39 non-artifact tables across 10 papers).

- **Average cost per paper: ~$0.003** (0.3 cents)
- **Cost for a 1,000-paper library: ~$3.00**

### Monthly budget estimate

Assuming a researcher indexes 10-20 new papers per month:

- **Monthly cost: $0.03-$0.06** — negligible

## 2. Latency Analysis

### Per-agent call timing

- Haiku API latency: ~1-3 seconds per call (including image upload and response generation)
- Image loading overhead: negligible (local file read)
- JSON parsing: negligible

### Per-paper timing

- Average 3.9 tables per paper
- Sequential processing: 3.9 x 2s average = **~8 seconds per paper**
- Parallel processing (3-5 concurrent calls): **~3-4 seconds per paper**

### Comparison with extraction time

Current extraction pipeline takes 5-30 seconds per paper depending on complexity. Agent QA adds:

- Sequential: +8s (~30-160% overhead)
- Parallel: +3-4s (~10-80% overhead)

## 3. Async vs Sync Recommendation

**Recommendation: Asynchronous (background pass).**

Rationale:

1. **QA is non-blocking for the researcher**. The extracted content is usable immediately — QA results are quality metadata, not a prerequisite for search or citation.

2. **Latency budget**. Adding 3-8 seconds to every indexing operation degrades the user experience with no immediate benefit. The researcher wants to search, not wait for QA.

3. **Failure tolerance**. If the haiku API is unavailable or slow, synchronous QA would block indexing entirely. Async allows graceful degradation — indexing proceeds, QA runs when possible.

4. **Batch efficiency**. Async processing allows batching multiple tables into concurrent API calls, reducing total wall-clock time.

### Implementation sketch

- After indexing completes, enqueue a QA job (paper key + table IDs)
- A background worker processes the queue, spawning one haiku call per table
- Results are written to the debug database (`ground_truth_diffs` table or a new `agent_qa_results` table)
- A status field on the paper record tracks QA state: `pending`, `running`, `complete`, `failed`
- The MCP server exposes a `qa_status` tool so the researcher can check progress

## 4. Trigger Policy

**Recommendation: Run on every new paper, skip on re-index unless extraction changed.**

| Trigger | Run QA? | Rationale |
|---------|---------|-----------|
| New paper indexed for the first time | Yes | Baseline quality check |
| Paper re-indexed (same extraction output) | No | No new information to validate |
| Paper re-indexed (extraction changed) | Yes | New extraction may have new errors |
| Pipeline code changes (new release) | Yes, full corpus | Regression detection |
| Manual trigger via MCP tool | Yes | Researcher suspects an issue |

### Change detection

Compare a hash of the extraction output (headers + rows JSON) against the stored hash from the last QA run. If identical, skip. This avoids redundant API calls when re-indexing produces the same result.

## 5. Failure Modes

### Agent disagrees with a correct extraction (false positive)

This is the primary risk. The haiku agent may:

- Misread a visually ambiguous character (e.g., "l" vs "1", "O" vs "0")
- Report formatting differences that are not extraction errors (e.g., "0.047" vs "0.047" with different whitespace)
- Fail to parse complex table layouts (merged cells, multi-line headers)

**Mitigation**: Track false positive rates per error type. If a specific error pattern (e.g., whitespace differences) has a high false positive rate, add a post-processing filter to suppress it. Maintain a "known false positives" list that can be updated as patterns emerge.

### Agent cannot read an image (blurry, too small, complex layout)

The agent reports `"visual": "UNREADABLE"` for cells it cannot confidently read.

**Mitigation**: Track UNREADABLE rates. If a table has >30% UNREADABLE cells, flag it for manual review rather than treating it as an extraction failure. Consider re-rendering at higher DPI (600 DPI) for tables with high UNREADABLE rates.

### API failures (rate limits, timeouts, outages)

**Mitigation**: Exponential backoff with 3 retries. After 3 failures, mark the table's QA status as `failed` and continue. Failed tables are retried on the next QA pass.

### Agent hallucinates or produces malformed output

**Mitigation**: Strict JSON schema validation on the response. If `parse_agent_response()` raises `ValueError`, treat it as a failed QA attempt — log the raw response for debugging, mark as `failed`, retry once.

## 6. Confidence Calibration

### Trust hierarchy

1. **Ground truth (human-verified)**: Highest confidence. Always correct by definition.
2. **Agent QA reading**: High confidence for simple tables with clear text. Lower confidence for complex layouts, small text, or visually ambiguous characters.
3. **Automated extraction**: The baseline to be validated.

### When to trust the agent vs the extraction

| Scenario | Trust | Action |
|----------|-------|--------|
| Agent and extraction agree | Both correct | No action needed |
| Agent reports missing value, extraction has value | Agent likely correct | Flag for review — extraction may have hallucinated (rare) |
| Agent reports different value, difference is numeric (e.g., "0.047" vs ".047") | Agent likely correct | Auto-accept if agent value has leading zero (known extraction issue) |
| Agent reports different value, difference is text | Uncertain | Flag for human review |
| Agent reports UNREADABLE | Low confidence | Do not flag extraction as wrong; note for manual review |

### Auto-accept rules

Certain error patterns have near-100% agent accuracy:

- Leading zero recovery: agent reads "0.047", extraction has ".047" — auto-accept agent
- Negative sign: agent reads "-1.23", extraction has "- 1.23" or "1.23" — auto-accept agent
- Missing cell: agent reads a value, extraction is empty — auto-accept agent

All other differences should be flagged for human review until sufficient data confirms the pattern.

### Confidence scoring

Future enhancement: assign a confidence score to each agent reading based on:

- Image quality (DPI, contrast, text size)
- Table complexity (number of rows/cols, merged cells)
- Historical accuracy of the agent on similar tables

## 7. Integration with Ground Truth

### Relationship between agent QA and ground truth

| Aspect | Ground Truth | Agent QA |
|--------|-------------|----------|
| Source | Human expert + agent draft | Haiku agent alone |
| Accuracy | Definitive (verified) | High but imperfect |
| Coverage | Limited (manually reviewed subset) | Full (every table) |
| Cost | High (human time) | Low ($0.001/table) |
| Speed | Slow (minutes per table) | Fast (seconds per table) |

### Complementary roles

1. **Ground truth for calibration**: Use the verified ground truth corpus to measure the agent QA false positive/negative rate. This provides the confidence calibration data needed for Section 6.

2. **Agent QA for coverage**: Ground truth can only cover a small fraction of the library. Agent QA provides a quality signal for every table, even those without ground truth.

3. **Agent QA as draft for new ground truth**: When adding a new paper to the ground truth corpus, the agent QA reading can serve as the initial draft — similar to the existing blind drafting workflow but with structured diff output.

### Can agent QA replace ground truth?

**No, but it can supplement it.** Ground truth provides the definitive answer; agent QA provides a probabilistic quality signal. The two serve different purposes:

- Ground truth is for measuring extraction accuracy with mathematical precision
- Agent QA is for flagging likely problems across the full library

Over time, as agent QA accuracy is validated against ground truth, the auto-accept rules (Section 6) can be expanded, reducing the need for human review of agent-flagged issues.

## 8. Decision Framework

When to use each quality assurance method:

| Method | When to use | Strengths | Weaknesses |
|--------|------------|-----------|------------|
| **Statistical checks** (fill rate, garbled detection) | Every extraction, inline | Zero cost, instant, catches gross errors | Cannot detect value-level errors |
| **Agent QA** | Every new paper (async) | Full coverage, cell-level accuracy, low cost | False positives, cannot read all images, API dependency |
| **Ground truth comparison** | Corpus papers, regression testing | Definitive accuracy measurement | Manual effort, limited coverage |

### Recommended pipeline

1. **Inline (during extraction)**: Statistical checks flag gross problems (fill rate < 50%, garbled text). These trigger immediate re-extraction with alternative strategies.

2. **Post-indexing (async)**: Agent QA runs on all non-artifact tables. Results are stored in the debug database. Tables with errors are flagged.

3. **On demand (manual)**: Ground truth comparison runs during stress testing and when validating extraction pipeline changes. Ground truth corpus is expanded using the agent QA blind-drafting workflow.

4. **Dashboard**: A summary view shows per-paper QA status, error counts, and confidence levels. Researchers can drill into specific tables flagged by the agent.
