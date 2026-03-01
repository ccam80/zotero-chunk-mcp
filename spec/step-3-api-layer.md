# Step 3: API Layer

## Overview

Rewrite `vision_api.py` from async multi-agent to sync single-agent batch-only.
After this step, callers can pass a list of `TableVisionSpec` objects to
`extract_tables_batch()` and receive `AgentResponse` objects back — one per
input spec, in the same order.

**File modified**: `src/zotero_chunk_rag/feature_extraction/vision_api.py`
**Test file created**: `tests/test_feature_extraction/test_vision_api.py`

**Dependencies**: Step 2 must be complete (`render_table_region`,
`VISION_FIRST_SYSTEM`, updated `AgentResponse`, updated `parse_agent_response`
must exist in `vision_extract.py`).

---

## Wave 3.1: Sync conversion and init cleanup

### Task 3.1.1: Convert all async code to sync and clean up VisionAPI init

- **Description**: Mechanically convert all async methods to sync. Drop the
  async Anthropic client, the `asyncio.Lock`, and init parameters that are no
  longer needed (`concurrency`, `dpi`, `padding_px` — rendering is now handled
  by `render_table_region()` with its own DPI logic).

- **Files to modify**:
  - `src/zotero_chunk_rag/feature_extraction/vision_api.py`:
    - **Imports**: Remove `import asyncio`. Add `import time` (already imported,
      verify present). Remove `import pymupdf` if present (rendering delegated
      to `vision_extract.py`).
    - **`_LOG_LOCK`** (line 99): Delete entirely. No lock needed in sync
      single-threaded code.
    - **`_append_cost_entry()`** (lines 102–115): Convert from `async def` to
      `def`. Remove `async with _LOG_LOCK:` — just run the body directly.
    - **`_poll_batch()`** (lines 187–248): Convert from `async def` to `def`.
      Replace `await asyncio.sleep(poll_interval)` with `time.sleep(poll_interval)`.
      Replace `await _append_cost_entry(...)` with `_append_cost_entry(...)`.
    - **`_submit_and_poll()`** (lines 250–259): Convert from `async def` to
      `def`. Replace `await self._poll_batch(...)` with `self._poll_batch(...)`.
    - **`VisionAPI.__init__()`** (lines 144–166): Remove `concurrency` parameter.
      Remove `dpi` and `padding_px` parameters (rendering is no longer this
      module's concern). Remove `self._client = anthropic.AsyncAnthropic(...)`.
      Keep `self._sync_client = anthropic.Anthropic(api_key=api_key)`, rename
      to `self._client`. Keep `self._model`, `self._cost_log_path`, `self._cache`,
      `self._session_id`, `self._session_cost`.
    - **Import from vision_extract** (lines 23–28): Remove `render_table_png`
      from import list (already done by Step 2 task 2.1.4). The remaining
      imports (`AgentResponse`, `build_common_ctx`, `parse_agent_response`) stay.

- **Updated `__init__` signature**:
  ```python
  def __init__(
      self,
      api_key: str,
      model: str = "claude-haiku-4-5-20251001",
      cost_log_path: Path | str = Path("vision_api_costs.json"),
      cache: bool = True,
  ) -> None:
  ```

- **Tests**:
  - `test_vision_api.py::TestSyncConversion::test_no_asyncio_import`
    — Assert: the string `"asyncio"` does not appear as an import in
    `vision_api.py` source (read the file, check `import asyncio` not present).
  - `test_vision_api.py::TestSyncConversion::test_poll_batch_is_not_coroutine`
    — Assert: `asyncio.iscoroutinefunction(VisionAPI._poll_batch)` is `False`.
  - `test_vision_api.py::TestSyncConversion::test_append_cost_entry_is_not_coroutine`
    — Assert: `asyncio.iscoroutinefunction(_append_cost_entry)` is `False`.
  - `test_vision_api.py::TestSyncConversion::test_init_no_concurrency_param`
    — Assert: `VisionAPI.__init__` does not accept `concurrency` keyword
    (call with `concurrency=10` raises `TypeError`).
  - `test_vision_api.py::TestSyncConversion::test_init_no_dpi_param`
    — Assert: `VisionAPI.__init__` does not accept `dpi` keyword
    (call with `dpi=300` raises `TypeError`).

- **Acceptance criteria**:
  - No `asyncio` import in the module
  - No `async def` in the module
  - No `await` in the module
  - No `_LOG_LOCK` in the module
  - `VisionAPI.__init__` accepts only `api_key`, `model`, `cost_log_path`, `cache`
  - `_poll_batch` uses `time.sleep` for polling
  - `_append_cost_entry` writes cost entries without any locking mechanism
  - All tests pass

---

## Wave 3.2: Batch extraction entry point

### Task 3.2.1: Rewrite `_prepare_table()` for multi-strip rendering

- **Description**: Rewrite `_prepare_table()` to use `render_table_region()`
  from `vision_extract.py` instead of the deleted `render_table_png()`. Returns
  a list of base64-encoded image pairs (one pair per strip) instead of a single
  image.

- **Files to modify**:
  - `src/zotero_chunk_rag/feature_extraction/vision_api.py`:
    - **Import**: Add `render_table_region` to the import from `vision_extract`.
    - **`_prepare_table()`** (lines 265–274): Rewrite entirely.

- **Updated import**:
  ```python
  from .vision_extract import (
      AgentResponse,
      build_common_ctx,
      parse_agent_response,
      render_table_region,
  )
  ```

- **New `_prepare_table` implementation**:
  ```python
  def _prepare_table(
      self, spec: TableVisionSpec,
  ) -> list[tuple[str, str]]:
      """Render PNG(s) for a table spec.

      Opens the PDF, renders the crop region (possibly as multiple
      overlapping strips for tall tables), and base64-encodes each image.

      Returns list of (base64_string, media_type) pairs.
      """
      import pymupdf

      doc = pymupdf.open(str(spec.pdf_path))
      try:
          page = doc[spec.page_num - 1]
          strips = render_table_region(page, spec.bbox)
          return [
              (base64.b64encode(png_bytes).decode("ascii"), media_type)
              for png_bytes, media_type in strips
          ]
      finally:
          doc.close()
  ```

- **Tests**:
  - `test_vision_api.py::TestPrepareTable::test_returns_list_of_pairs`
    — Patch `render_table_region` to return `[(b"fake_png", "image/png")]`.
    Patch `pymupdf.open` to return a mock doc. Call `_prepare_table(spec)`.
    Assert: returns a list with 1 tuple; second element is `"image/png"`.
  - `test_vision_api.py::TestPrepareTable::test_base64_encoded`
    — Same setup. Assert: first element of the returned tuple is valid
    base64 (`base64.b64decode(result[0][0])` does not raise).
  - `test_vision_api.py::TestPrepareTable::test_multi_strip`
    — Patch `render_table_region` to return 2 strips. Assert: returns
    2 tuples; both have valid base64 and `"image/png"`.
  - `test_vision_api.py::TestPrepareTable::test_document_closed`
    — Patch `pymupdf.open`. Assert: mock doc's `.close()` was called
    exactly once (even if rendering raises).

- **Acceptance criteria**:
  - `_prepare_table` calls `render_table_region` (not `render_table_png`)
  - Returns `list[tuple[str, str]]` with valid base64 in first element
  - PDF document is always closed (try/finally)
  - All tests pass

---

### Task 3.2.2: Add `_build_request()` helper

- **Description**: Build a single Anthropic batch request dict from a table
  spec and its pre-rendered images. Constructs user content blocks (context
  text + image blocks) and wraps them in the batch request format. The system
  prompt (`VISION_FIRST_SYSTEM`) gets a cache breakpoint.

- **Files to modify**:
  - `src/zotero_chunk_rag/feature_extraction/vision_api.py`:
    - **Import**: Add `VISION_FIRST_SYSTEM` to the import from `vision_extract`.
    - Add `_build_request()` method to `VisionAPI`.

- **Updated import**:
  ```python
  from .vision_extract import (
      AgentResponse,
      build_common_ctx,
      parse_agent_response,
      render_table_region,
      VISION_FIRST_SYSTEM,
  )
  ```

- **Method signature and implementation**:
  ```python
  def _build_request(
      self,
      spec: TableVisionSpec,
      images: list[tuple[str, str]],
  ) -> dict:
      """Build one Anthropic batch request dict.

      Args:
          spec: Table vision spec (provides raw_text, caption, garbled, table_id).
          images: Pre-rendered images as (base64_string, media_type) pairs.

      Returns:
          Batch request dict with custom_id, params (model, max_tokens,
          system, messages).
      """
      ctx = build_common_ctx(spec.raw_text, spec.caption, spec.garbled)

      user_content: list[dict] = [{"type": "text", "text": ctx}]
      for b64, media_type in images:
          user_content.append({
              "type": "image",
              "source": {
                  "type": "base64",
                  "media_type": media_type,
                  "data": b64,
              },
          })

      system_blocks: list[dict] = [
          {"type": "text", "text": VISION_FIRST_SYSTEM},
      ]
      if self._cache:
          system_blocks[0]["cache_control"] = {"type": "ephemeral"}

      return {
          "custom_id": f"{spec.table_id}__transcriber",
          "params": {
              "model": self._model,
              "max_tokens": 4096,
              "system": system_blocks,
              "messages": [{"role": "user", "content": user_content}],
          },
      }
  ```

- **Design notes**:
  - **Cache strategy**: Only BP1 (system prompt) gets `cache_control`. All
    tables in a batch share `VISION_FIRST_SYSTEM`, so the system prompt is
    cached after the first request processes. No BP2 on images — each table
    has unique images, and re-crops (handled by the caller) send different
    images, so image caching provides no benefit.
  - **`max_tokens = 4096`**: Transcriber output averages ~530 tokens. 4096
    provides ample headroom for large tables.
  - **`custom_id` format**: `{table_id}__transcriber`. The `__` delimiter
    is parsed by `_poll_batch` to extract table_id and role for cost logging.

- **Tests**:
  - `test_vision_api.py::TestBuildRequest::test_custom_id_format`
    — spec with `table_id="5SIZVS65_table_1"`. Assert:
    `request["custom_id"] == "5SIZVS65_table_1__transcriber"`.
  - `test_vision_api.py::TestBuildRequest::test_system_prompt_cache_control`
    — VisionAPI with `cache=True`. Assert:
    `request["params"]["system"][0]["cache_control"] == {"type": "ephemeral"}`.
  - `test_vision_api.py::TestBuildRequest::test_no_cache_control_when_disabled`
    — VisionAPI with `cache=False`. Assert:
    `"cache_control" not in request["params"]["system"][0]`.
  - `test_vision_api.py::TestBuildRequest::test_user_content_structure`
    — 1 image. Assert: `user_content` has 2 blocks — text block (context)
    then image block; text block contains the raw_text; image block has
    `source.type == "base64"`.
  - `test_vision_api.py::TestBuildRequest::test_multi_image_content`
    — 2 images. Assert: `user_content` has 3 blocks — 1 text + 2 images;
    images are in order.
  - `test_vision_api.py::TestBuildRequest::test_model_matches_init`
    — Assert: `request["params"]["model"] == self._model`.
  - `test_vision_api.py::TestBuildRequest::test_garbled_warning_in_context`
    — spec with `garbled=True`. Assert: user content text block contains
    "GARBLED SYMBOL ENCODING".

- **Acceptance criteria**:
  - Custom ID uses `{table_id}__transcriber` format
  - System prompt has `cache_control` when `cache=True`, absent when `False`
  - No `cache_control` on image blocks
  - User content has text context followed by image blocks in order
  - Garbled flag propagates through `build_common_ctx`
  - `max_tokens` set to 4096
  - All tests pass

---

### Task 3.2.3: Add `extract_tables_batch()` — main entry point

- **Description**: The primary public method on `VisionAPI`. Takes a list of
  `TableVisionSpec` objects, renders each table, builds batch requests, submits
  one batch to the Anthropic API, polls until complete, parses responses, and
  returns `AgentResponse` objects in the same order as input specs. Missing or
  failed batch results produce `AgentResponse` with `parse_success=False`.

  This method does NOT handle re-crops. If any returned `AgentResponse` has
  `recrop_needed=True`, it is the caller's responsibility to compute a new
  crop (via `compute_recrop_bbox` in `vision_extract.py`), build a new
  `TableVisionSpec`, and call `extract_tables_batch()` again.

- **Files to modify**:
  - `src/zotero_chunk_rag/feature_extraction/vision_api.py` — add
    `extract_tables_batch()` method to `VisionAPI`

- **Method signature**:
  ```python
  def extract_tables_batch(
      self,
      specs: list[TableVisionSpec],
  ) -> list[AgentResponse]:
      """Extract tables via the Anthropic Batch API.

      Renders each table as PNG(s), builds batch requests with
      VISION_FIRST_SYSTEM prompt, submits a single batch, polls
      until complete, and parses responses.

      Re-crop is NOT handled here. If any response has
      recrop_needed=True, the caller should compute a new crop
      and call this method again with updated specs.

      Args:
          specs: Table vision specs to extract.

      Returns:
          AgentResponse per spec, in the same order as input.
          Failed/missing batch results return AgentResponse with
          parse_success=False.
      """
  ```

- **Implementation flow**:
  1. If `specs` is empty, return `[]`.
  2. For each spec: call `_prepare_table(spec)` → images; call
     `_build_request(spec, images)` → request dict.
  3. Submit all requests via `self._submit_and_poll(requests)` → `dict[custom_id, raw_text]`.
  4. For each spec in input order:
     - Look up `results.get(f"{spec.table_id}__transcriber")`
     - If found: `parse_agent_response(raw_text, "transcriber")`
     - If missing: return a failed `AgentResponse` (all empty, `parse_success=False`)
  5. Return the list.

- **Failed response sentinel**:
  ```python
  AgentResponse(
      headers=[], rows=[], footnotes="",
      table_label=None, caption="",
      is_incomplete=False, incomplete_reason="",
      raw_shape=(0, 0), parse_success=False,
      raw_response="",
      recrop_needed=False, recrop_bbox_pct=None,
  )
  ```

- **Tests**:
  - `test_vision_api.py::TestExtractTablesBatch::test_empty_specs`
    — `extract_tables_batch([])` returns `[]`.
  - `test_vision_api.py::TestExtractTablesBatch::test_successful_extraction`
    — 2 specs. Patch `_prepare_table` to return dummy images. Patch
    `_submit_and_poll` to return a dict mapping both custom_ids to valid
    JSON responses (with headers, rows, table_label, caption, recrop). Assert:
    returns 2 `AgentResponse` objects; both have `parse_success=True`;
    headers/rows match the mocked JSON.
  - `test_vision_api.py::TestExtractTablesBatch::test_missing_result`
    — 2 specs. Patch `_submit_and_poll` to return results for only the first
    spec. Assert: second response has `parse_success=False`, `headers==[]`,
    `rows==[]`.
  - `test_vision_api.py::TestExtractTablesBatch::test_result_order_matches_input`
    — 3 specs with table_ids "A", "B", "C". Patch `_submit_and_poll` to
    return results in reversed order (C, B, A). Assert: output list has
    responses in A, B, C order matching input.
  - `test_vision_api.py::TestExtractTablesBatch::test_calls_prepare_and_build`
    — 1 spec. Patch `_prepare_table` and `_build_request` as mocks. Assert:
    `_prepare_table` called once with the spec; `_build_request` called once
    with the spec and the images returned by `_prepare_table`.

- **Acceptance criteria**:
  - Returns one `AgentResponse` per input spec, in input order
  - Missing batch results produce `AgentResponse` with `parse_success=False`
  - Uses `_prepare_table` for rendering and `_build_request` for message construction
  - Does NOT handle re-crops (no re-crop logic in this method)
  - All tests pass

---

## Agent Execution Rules

### No API calls

Implementation agents MUST NOT make external API calls (Anthropic, Zotero,
or any network request). The Anthropic client must be mocked in all tests.
`_prepare_table` tests mock `pymupdf.open` and `render_table_region`.

### Test execution protocol

Tests are run at most TWICE per implementation session:

1. **First run**: Execute `tests/test_feature_extraction/test_vision_api.py`.
   Record all failures.
2. **Quick fix round**: Fix only mechanical issues (broken imports, missing
   symbols, trivial type errors). No restructuring.
3. **Second run**: Execute again. Record remaining failures.
4. **Report**: Surface all remaining failures to the user. Do not loop.

### No test modification to make tests pass

If a test fails, the agent reports the failure — it does not modify test
assertions.

---

## Acceptance Criteria

1. **Clean import**: `from zotero_chunk_rag.feature_extraction.vision_api import VisionAPI, TableVisionSpec, CostEntry` succeeds
2. **No async**: Module contains no `async def`, no `await`, no `import asyncio`
3. **No lock**: Module contains no `Lock` (no asyncio.Lock, no threading.Lock)
4. **Init simplified**: `VisionAPI.__init__` accepts only `api_key`, `model`, `cost_log_path`, `cache`
5. **Rendering**: `_prepare_table` uses `render_table_region`, returns `list[tuple[str, str]]`
6. **Request format**: `_build_request` produces correctly structured batch request dicts with system prompt cache breakpoint
7. **Entry point**: `extract_tables_batch(specs)` returns `list[AgentResponse]` in input order
8. **Failed handling**: Missing/failed batch results produce `AgentResponse(parse_success=False)`
9. **No re-crop**: `extract_tables_batch` does not contain re-crop logic
10. **Cost logging**: `_poll_batch` logs cost entries via `_append_cost_entry` for each successful result
11. **Tests**: All tests in `test_vision_api.py` pass
12. **No new regressions**: no test that was passing before this step now fails because of this step's changes. Pre-existing failures (e.g., `test_ground_truth.py`, table-dependent tests) are expected and NOT blockers — report them and move on.
