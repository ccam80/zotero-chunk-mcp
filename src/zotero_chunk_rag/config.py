"""Configuration management."""
from dataclasses import dataclass
from pathlib import Path
import json
import os


@dataclass
class Config:
    """Application configuration."""
    zotero_data_dir: Path
    chroma_db_path: Path
    embedding_model: str
    embedding_dimensions: int
    chunk_size: int
    chunk_overlap: int
    gemini_api_key: str | None
    # Embedding provider: "gemini" (API) or "local" (ChromaDB default all-MiniLM-L6-v2)
    embedding_provider: str
    # Embedding settings
    embedding_timeout: float
    embedding_max_retries: int
    # Reranking settings
    rerank_alpha: float
    rerank_section_weights: dict[str, float] | None
    rerank_journal_weights: dict[str, float] | None  # Use "unknown" for null quartile
    rerank_enabled: bool
    oversample_multiplier: int
    oversample_topic_factor: int  # Additional factor for search_topic
    stats_sample_limit: int
    # OCR settings (language passed through to pymupdf-layout)
    ocr_language: str
    # Table extraction settings
    tables_enabled: bool
    table_strategy: str  # pymupdf4llm table detection strategy
    image_size_limit: float  # minimum image size as page fraction
    # Figure extraction settings
    figures_enabled: bool
    figures_min_size: int  # Minimum width/height to filter out icons/logos
    # Quality metric thresholds
    quality_threshold_a: int  # chars/page for A grade
    quality_threshold_b: int  # chars/page for B grade
    quality_threshold_c: int  # chars/page for C grade
    quality_threshold_d: int  # chars/page for D grade
    quality_entropy_min: float  # minimum entropy for A grade
    # OpenAlex settings
    openalex_email: str | None  # Optional email for polite pool (10 req/sec vs 1 req/sec)

    @classmethod
    def load(cls, path: Path | str | None = None) -> "Config":
        """Load config from file and/or environment."""
        if path is not None:
            config_path = Path(path).expanduser()
        else:
            config_path = Path("~/.config/zotero-chunk-rag/config.json").expanduser()

        data = {}
        if config_path.exists():
            with open(config_path) as f:
                data = json.load(f)

        return cls(
            zotero_data_dir=Path(data.get("zotero_data_dir", "~/Zotero")).expanduser(),
            chroma_db_path=Path(data.get("chroma_db_path", "~/.local/share/zotero-chunk-rag/chroma")).expanduser(),
            embedding_model=data.get("embedding_model", "gemini-embedding-001"),
            embedding_dimensions=data.get("embedding_dimensions", 768),
            chunk_size=data.get("chunk_size", 400),
            chunk_overlap=data.get("chunk_overlap", 100),
            gemini_api_key=data.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY"),
            # Embedding provider: "gemini" or "local"
            embedding_provider=data.get("embedding_provider", "gemini"),
            # Embedding settings
            embedding_timeout=data.get("embedding_timeout", 120.0),
            embedding_max_retries=data.get("embedding_max_retries", 3),
            # Reranking settings
            rerank_alpha=data.get("rerank_alpha", 0.7),
            rerank_section_weights=data.get("rerank_section_weights"),
            rerank_journal_weights=data.get("rerank_journal_weights"),
            rerank_enabled=data.get("rerank_enabled", True),
            oversample_multiplier=data.get("oversample_multiplier", 3),
            oversample_topic_factor=data.get("oversample_topic_factor", 5),
            stats_sample_limit=data.get("stats_sample_limit", 10000),
            # OCR settings — language passed through to pymupdf-layout
            ocr_language=data.get("ocr_language", "eng"),
            # Table extraction settings
            tables_enabled=data.get("tables_enabled", False),
            table_strategy=data.get("table_strategy", "lines_strict"),
            image_size_limit=data.get("image_size_limit", 0.05),
            # Figure extraction settings
            figures_enabled=data.get("figures_enabled", False),
            figures_min_size=data.get("figures_min_size", 100),
            # Quality metric thresholds
            quality_threshold_a=data.get("quality_threshold_a", 2000),
            quality_threshold_b=data.get("quality_threshold_b", 1000),
            quality_threshold_c=data.get("quality_threshold_c", 500),
            quality_threshold_d=data.get("quality_threshold_d", 100),
            quality_entropy_min=data.get("quality_entropy_min", 4.0),
            # OpenAlex settings
            openalex_email=data.get("openalex_email") or os.environ.get("OPENALEX_EMAIL"),
        )

    def validate(self) -> list[str]:
        """Return list of validation errors, empty if valid."""
        errors = []
        if not self.zotero_data_dir.exists():
            errors.append(f"Zotero data dir not found: {self.zotero_data_dir}")
        if not (self.zotero_data_dir / "zotero.sqlite").exists():
            errors.append(f"Zotero database not found: {self.zotero_data_dir / 'zotero.sqlite'}")

        # Only require API key for Gemini provider
        if self.embedding_provider == "gemini" and not self.gemini_api_key:
            errors.append("GEMINI_API_KEY not set (required for embedding_provider='gemini')")
        elif self.embedding_provider not in ("gemini", "local"):
            errors.append(f"Invalid embedding_provider: {self.embedding_provider}. Must be 'gemini' or 'local'")

        return errors
