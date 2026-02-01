"""
All dataclasses for the system. No dependencies on implementation modules.
"""
from dataclasses import dataclass, field
from pathlib import Path


# =============================================================================
# ZOTERO MODELS
# =============================================================================

@dataclass
class ZoteroItem:
    """A bibliographic item from Zotero with optional PDF attachment."""
    item_key: str
    title: str
    authors: str              # "Smith, J." or "Smith, J. et al."
    year: int | None
    pdf_path: Path | None     # Resolved filesystem path to PDF
    citation_key: str = ""    # BetterBibTeX citation key
    publication: str = ""     # Journal/conference name


# =============================================================================
# PDF EXTRACTION MODELS
# =============================================================================

@dataclass
class PageText:
    """Text content from a single PDF page."""
    page_num: int             # 1-indexed
    text: str
    char_start: int           # Character offset in concatenated full document


# =============================================================================
# CHUNKING MODELS
# =============================================================================

@dataclass
class Chunk:
    """A text chunk from a document with position metadata."""
    text: str
    chunk_index: int          # Sequential index within document
    page_num: int             # Primary page (1-indexed)
    char_start: int           # Start offset in full document
    char_end: int             # End offset in full document


# =============================================================================
# VECTOR STORE MODELS
# =============================================================================

@dataclass
class StoredChunk:
    """A chunk retrieved from the vector store."""
    id: str
    text: str
    metadata: dict
    score: float = 0.0        # Similarity score (0-1, higher = more similar)


# =============================================================================
# RETRIEVAL MODELS
# =============================================================================

@dataclass
class RetrievalResult:
    """A search result with expanded context."""
    chunk_id: str
    text: str
    score: float
    doc_id: str
    doc_title: str
    authors: str
    year: int | None
    page_num: int
    chunk_index: int
    citation_key: str = ""
    publication: str = ""
    context_before: list[str] = field(default_factory=list)
    context_after: list[str] = field(default_factory=list)

    def full_context(self) -> str:
        """Return chunk with surrounding context merged."""
        parts = self.context_before + [self.text] + self.context_after
        return "\n\n".join(parts)


@dataclass
class SearchResponse:
    """Complete search response."""
    query: str
    results: list[RetrievalResult]
    total_hits: int
