"""Gemini embedding service."""
from google import genai
from google.genai import types


class Embedder:
    """
    Gemini embedding wrapper using gemini-embedding-001.

    This model is #1 on MTEB Multilingual leaderboard.
    Uses asymmetric embeddings: different task types for docs vs queries.

    Output dimensions: configurable (768 default, up to 3072)
    Max input: 2048 tokens per text
    Batch size: up to 100 texts
    """

    def __init__(
        self,
        model: str = "gemini-embedding-001",
        dimensions: int = 768,
        api_key: str | None = None
    ):
        # Uses GEMINI_API_KEY env var if api_key not provided
        if api_key:
            self.client = genai.Client(api_key=api_key)
        else:
            self.client = genai.Client()
        self.model = model
        self.dimensions = dimensions

    def embed(
        self,
        texts: list[str],
        task_type: str = "RETRIEVAL_DOCUMENT"
    ) -> list[list[float]]:
        """
        Embed a batch of texts.

        Args:
            texts: List of texts to embed
            task_type: One of:
                - "RETRIEVAL_DOCUMENT": For indexing documents (default)
                - "RETRIEVAL_QUERY": For search queries
                - "SEMANTIC_SIMILARITY": For comparing texts
                - "CLASSIFICATION": For classification

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        results = []
        batch_size = 100  # Gemini limit

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = self.client.models.embed_content(
                model=self.model,
                contents=batch,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=self.dimensions
                )
            )
            results.extend([e.values for e in response.embeddings])

        return results

    def embed_query(self, query: str) -> list[float]:
        """
        Embed a search query.

        Uses RETRIEVAL_QUERY task type for asymmetric retrieval.
        """
        return self.embed([query], task_type="RETRIEVAL_QUERY")[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """
        Embed documents for indexing.

        Uses RETRIEVAL_DOCUMENT task type.
        """
        return self.embed(texts, task_type="RETRIEVAL_DOCUMENT")
