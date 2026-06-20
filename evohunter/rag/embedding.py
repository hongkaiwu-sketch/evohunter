from __future__ import annotations

from typing import Any


class EmbeddingError(RuntimeError):
    pass


class EmbeddingProvider:
    """Generate text embeddings for RAG vector search.

    Uses OpenAI-compatible embedding API by default, with
    optional sentence-transformers fallback for offline use.
    """

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        dimension: int = 1536,
        client: Any | None = None,
    ) -> None:
        self._model = model
        self._dimension = dimension
        self._client = client
        self._local_model: Any = None

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_text(self, text: str) -> list[float]:
        """Single text -> embedding vector."""
        return self.embed_texts([text])[0]

    def embed_texts(self, texts: list[str], batch_size: int = 16) -> list[list[float]]:
        """Batch embedding. Uses API client if available, else local model."""
        valid_texts = [t if t.strip() else " " for t in texts]

        if self._client is not None:
            return self._embed_via_api(valid_texts, batch_size)
        return self._embed_via_local(valid_texts)

    def _embed_via_api(
        self, texts: list[str], batch_size: int
    ) -> list[list[float]]:
        import math

        all_embeddings: list[list[float]] = []
        batches = math.ceil(len(texts) / batch_size)

        for i in range(batches):
            batch = texts[i * batch_size : (i + 1) * batch_size]
            try:
                response = self._client.embeddings.create(
                    model=self._model,
                    input=batch,
                )
                all_embeddings.extend(
                    [item.embedding for item in response.data]
                )
            except Exception as exc:
                raise EmbeddingError(
                    f"embedding API call failed: {exc}"
                ) from exc

        return all_embeddings

    def _embed_via_local(self, texts: list[str]) -> list[list[float]]:
        """Fallback: deterministic pseudo-embeddings for testing.

        In production, install ``sentence-transformers`` and set ``_local_model``.
        """
        if self._local_model is not None:
            import numpy as np
            embeddings = self._local_model.encode(texts, normalize_embeddings=True)
            if isinstance(embeddings, list):
                return [e.tolist() if hasattr(e, "tolist") else list(e) for e in embeddings]
            return embeddings.tolist() if hasattr(embeddings, "tolist") else list(embeddings)

        # Deterministic fallback for testing without deps
        import hashlib
        results: list[list[float]] = []
        for text in texts:
            # Use SHA-256 to generate a deterministic 128-dim vector
            h = hashlib.sha256(text.encode("utf-8")).digest()
            vec = [
                (h[i] / 255.0) if i < len(h) else 0.0
                for i in range(min(self._dimension, 32))
            ]
            # Pad to dimension
            while len(vec) < self._dimension:
                vec.append(0.0)
            # Normalize
            norm = sum(v * v for v in vec) ** 0.5 or 1.0
            results.append([v / norm for v in vec])
        return results
