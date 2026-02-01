# Zotero Chunk RAG

Passage-level semantic search over a Zotero library. PDFs are extracted, split into overlapping text chunks, embedded via Gemini, and stored in ChromaDB. An MCP server exposes the index to Claude Code (or any MCP client) as tool calls that return specific passages with expandable surrounding context.

## Install

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
```

Requires Python 3.10+ and a [Gemini API key](https://aistudio.google.com/app/apikey).

## Setup

### 1. Configuration

Copy the example config and fill in your API key:

```bash
mkdir -p ~/.config/zotero-chunk-rag
cp config.example.json ~/.config/zotero-chunk-rag/config.json
```

Edit `~/.config/zotero-chunk-rag/config.json`:

```json
{
    "zotero_data_dir": "~/Zotero",
    "chroma_db_path": "~/.local/share/zotero-chunk-rag/chroma",
    "embedding_model": "gemini-embedding-001",
    "embedding_dimensions": 768,
    "chunk_size": 400,
    "chunk_overlap": 100,
    "gemini_api_key": "YOUR_KEY_HERE"
}
```

Alternatively, set `GEMINI_API_KEY` as an environment variable and omit the field from the file.

#### Configuration reference

| Field | Default | Description |
|---|---|---|
| `zotero_data_dir` | `~/Zotero` | Path to Zotero's data directory (contains `zotero.sqlite` and `storage/`). |
| `chroma_db_path` | `~/.local/share/zotero-chunk-rag/chroma` | Where the ChromaDB vector index is stored on disk. |
| `embedding_model` | `gemini-embedding-001` | Gemini embedding model name. `gemini-embedding-001` is the current recommended model. |
| `embedding_dimensions` | `768` | Output dimensionality of the embedding vectors. See notes below. |
| `chunk_size` | `400` | Target chunk size in tokens (estimated at 4 characters per token). |
| `chunk_overlap` | `100` | Overlap between consecutive chunks in tokens. |
| `gemini_api_key` | `null` | Gemini API key. Falls back to the `GEMINI_API_KEY` environment variable if null. |

#### Embedding dimensions

`gemini-embedding-001` supports output dimensions from 64 to 3072. The default 768 is a good general-purpose setting.

- **Lower values (256-512):** Faster search, smaller index on disk, slightly less precise retrieval. Suitable if your library is small or queries are topically broad.
- **Higher values (1024-3072):** More expressive embeddings that can distinguish finer semantic differences. Diminishing returns above 1024 for most academic search tasks, and the index grows linearly with dimension count.

Changing this value after indexing requires a full re-index (`--force`), since stored vectors must all share the same dimensionality.

#### Chunk size and overlap

`chunk_size` controls how much text (in approximate tokens) each passage contains. `chunk_overlap` controls how many tokens are shared between consecutive chunks.

- **Smaller chunks (200-300 tokens):** Each result is a tighter, more focused passage. Better for locating specific claims or definitions. Risk: a single idea may be split across chunks, reducing retrieval quality for broader questions.
- **Larger chunks (500-800 tokens):** Each result carries more context. Better for questions about methods or arguments that span multiple sentences. Risk: irrelevant surrounding text dilutes the embedding, making it harder to match precise queries.
- **Overlap** ensures that sentence-boundary content is not lost between chunks. Setting overlap to 25-30% of chunk size (the default ratio of 100/400) is a reasonable starting point. Too little overlap risks splitting key sentences at chunk boundaries; too much wastes embedding API calls on redundant text.

Like embedding dimensions, changing chunk size or overlap requires a full re-index.

### 2. Initial indexing

Index your full Zotero library (processes all PDFs, skips items without PDF attachments):

```bash
python scripts\index_library.py -v
```

To test with a subset first:

```bash
python scripts\index_library.py --limit 10 -v
```

This reads the Zotero SQLite database (read-only; safe to run while Zotero is open), extracts text from each PDF, chunks it, embeds via Gemini, and stores everything in ChromaDB.

### 3. Register the MCP server

Add to your Claude Code settings (`~/.claude/settings.json`) under `mcpServers`:

```json
{
    "mcpServers": {
        "zotero-chunk-rag": {
            "command": "C:\\path\\to\\zotero_citation_mcp\\.venv\\Scripts\\python.exe",
            "args": ["-m", "zotero_chunk_rag.server"]
        }
    }
}
```

Restart Claude Code. The four tools (`search_papers`, `search_topic`, `get_passage_context`, `get_index_stats`) will be available in every session.

---

## User Guide

### Updating from Zotero

Re-run the indexing script whenever you add new papers or attach PDFs to existing items:

```bash
python scripts\index_library.py -v
```

The indexer is incremental by default. It compares the set of Zotero items that have PDFs against the set of document IDs already in the vector store, and only processes the difference. This means:

- New items with PDFs are indexed.
- Existing items that previously had no PDF but now do are indexed.
- Already-indexed items are skipped entirely (no re-embedding, no API cost).

To force a complete re-index (for example after changing `chunk_size` or `embedding_dimensions`):

```bash
python scripts\index_library.py --force -v
```

### Asking questions

The MCP server exposes four tools to Claude Code:

#### `search_topic`

Find the most relevant papers for a topic, deduplicated by document. Each paper is scored by both its average chunk relevance (overall topical fit) and its best single chunk (strongest individual passage). Results are sorted by average score.

Parameters:
- `query` (string, required) -- Natural language topic description.
- `num_papers` (int, default 10) -- Number of distinct papers to return (max 50).
- `year_min` / `year_max` (int, optional) -- Filter by publication year range.

Each result includes:
- `doc_title`, `authors`, `year`, `publication` -- Bibliographic metadata.
- `citation_key` -- BetterBibTeX citation key for LaTeX `\cite{}`.
- `avg_score` -- Average relevance across all matching chunks in the paper.
- `best_chunk_score` -- Score of the single most relevant chunk.
- `num_relevant_chunks` -- How many chunks in this paper matched.
- `best_passage`, `best_passage_page`, `best_passage_context` -- The strongest passage with context.

#### `search_papers`

Passage-level semantic search across all indexed chunks. Returns the matching text, relevance score, document metadata, and optionally surrounding chunks for context.

Parameters:
- `query` (string, required) -- Natural language search query.
- `top_k` (int, default 10) -- Number of chunk results to return (max 50).
- `context_chunks` (int, default 1) -- How many adjacent chunks to include before and after each hit (0-3).
- `year_min` / `year_max` (int, optional) -- Filter results by publication year range.

Each result includes:
- `passage` -- The matched chunk text.
- `context_before` / `context_after` -- Lists of adjacent chunk texts.
- `full_context` -- All context merged into a single string.
- `doc_title`, `authors`, `year`, `publication`, `page` -- Bibliographic metadata.
- `citation_key` -- BetterBibTeX citation key.
- `doc_id`, `chunk_index` -- Identifiers for follow-up with `get_passage_context`.

#### `get_passage_context`

Expands the context window around a specific passage returned by `search_papers`. Use this when the initial result is relevant but you need to read more of the surrounding text.

Parameters:
- `doc_id` (string, required) -- Document ID from a search result.
- `chunk_index` (int, required) -- Chunk index from a search result.
- `window` (int, default 2) -- Chunks before/after to include (1-5).

Returns the requested chunks with page numbers, citation key, plus a `merged_text` field containing all passages concatenated.

#### `get_index_stats`

Returns the current state of the index: total documents, total chunks, and average chunks per document. No parameters. Useful for verifying that indexing completed and checking coverage.

### Example session

In Claude Code, ask questions that reference your library. Claude will call the tools automatically when the MCP server is registered:

```
You: Find the 10 most relevant papers on autonomic innervation of the heart.

Claude: [calls search_topic with query="autonomic innervation of the heart", num_papers=10]
       Here are the top papers from your library, ranked by overall relevance...

You: Find citations for and against using LF/HF ratio as a measure of sympathovagal balance.

Claude: [calls search_papers with query="LF/HF ratio sympathovagal balance", top_k=25, context_chunks=2]
       Three papers support this interpretation, while two challenge it...

You: Show me more context around that Heathers quote.

Claude: [calls get_passage_context with the doc_id and chunk_index, window=4]
       The full surrounding argument reads...
```

---

## Integration with agents and skills

The `zotero-research` skill is an example Claude Code agent designed to use this server. It accepts high-level research requests ("find 10 papers about X", "find citations for and against Y") and returns formatted markdown with verbatim passages, summaries, and BetterBibTeX citation keys. See [`examples/zotero-research/SKILL.md`](examples/zotero-research/SKILL.md) for the full skill specification.
