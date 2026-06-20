from __future__ import annotations

from typing import Any


class VectorStoreError(RuntimeError):
    pass


class VectorStore:
    """In-memory vector store with optional ChromaDB persistence.

    Stores vectors with associated metadata, provides cosine similarity
    search via inner-product on normalized vectors.

    Uses a simple flat index. For production use, install ``chromadb``
    and set the ``backend`` to ``"chromadb"``.
    """

    def __init__(
        self,
        dimension: int = 1536,
        backend: str = "memory",
        persist_path: str | None = None,
    ) -> None:
        self._dimension = dimension
        self._backend = backend
        self._persist_path = persist_path

        # In-memory flat index
        self._vectors: dict[str, list[float]] = {}  # external_id -> vector
        self._metadata: dict[str, dict[str, Any]] = {}  # external_id -> metadata

        # ChromaDB client (lazy)
        self._chroma_client: Any = None
        self._chroma_collection: Any = None

    def add(
        self,
        external_id: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add a single vector with metadata."""
        if len(embedding) != self._dimension:
            raise VectorStoreError(
                f"expected dimension {self._dimension}, got {len(embedding)}"
            )
        self._vectors[external_id] = list(embedding)
        self._metadata[external_id] = metadata or {}

        if self._backend == "chromadb" and self._chroma_collection is not None:
            self._chroma_collection.add(
                ids=[external_id],
                embeddings=[embedding],
                metadatas=[metadata or {}],
            )

    def add_batch(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        """Add multiple vectors."""
        if metadatas is None:
            metadatas = [{} for _ in ids]

        for ext_id, emb, meta in zip(ids, embeddings, metadatas):
            self.add(ext_id, emb, meta)

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        """Search for top_k nearest neighbors via cosine similarity.

        Returns list of (external_id, score, metadata).
        """
        if not self._vectors:
            return []

        scores: list[tuple[str, float]] = []
        for ext_id, vec in self._vectors.items():
            score = self._cosine_similarity(query_embedding, vec)
            scores.append((ext_id, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        top = scores[:top_k]

        return [
            (ext_id, score, dict(self._metadata.get(ext_id, {})))
            for ext_id, score in top
        ]

    def delete(self, external_id: str) -> None:
        """Remove a vector."""
        self._vectors.pop(external_id, None)
        self._metadata.pop(external_id, None)

        if self._backend == "chromadb" and self._chroma_collection is not None:
            try:
                self._chroma_collection.delete(ids=[external_id])
            except Exception:
                pass

    def count(self) -> int:
        return len(self._vectors)

    def persist(self, path: str | None = None) -> None:
        """Persist the index to disk."""
        target = path or self._persist_path
        if not target:
            return

        import json
        import os

        os.makedirs(os.path.dirname(target) if os.path.dirname(target) else target, exist_ok=True)

        data = {
            "dimension": self._dimension,
            "vectors": {k: v for k, v in self._vectors.items()},
            "metadata": {k: v for k, v in self._metadata.items()},
        }
        store_path = (
            os.path.join(target, "vector_store.json")
            if os.path.isdir(target) or target.endswith("/")
            else target
        )
        with open(store_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    @classmethod
    def load(cls, path: str, dimension: int | None = None) -> "VectorStore":
        """Load a persisted index from disk."""
        import json
        import os

        store_path = (
            os.path.join(path, "vector_store.json")
            if os.path.isdir(path)
            else path
        )

        with open(store_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        dim = dimension or data.get("dimension", 1536)
        store = cls(dimension=dim)
        store._vectors = data.get("vectors", {})
        store._metadata = data.get("metadata", {})
        return store

    def init_chromadb(self, collection_name: str = "evohunter_rag") -> None:
        """Initialize ChromaDB backend."""
        try:
            import chromadb
            self._chroma_client = chromadb.PersistentClient(
                path=self._persist_path or "./.evohunter/chromadb"
            )
            self._chroma_collection = self._chroma_client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            self._backend = "chromadb"
        except ImportError:
            raise VectorStoreError(
                "chromadb is not installed. Install with: pip install chromadb"
            )
        except Exception as exc:
            raise VectorStoreError(f"failed to initialize ChromaDB: {exc}") from exc

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = (sum(x * x for x in a)) ** 0.5
        norm_b = (sum(x * x for x in b)) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
