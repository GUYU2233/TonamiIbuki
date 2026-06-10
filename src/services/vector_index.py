"""ChromaDB-backed vector index for persistent document storage.

Provides the same interface as the old JSONL adapter but stores embeddings
and metadata in a persistent ChromaDB collection on disk.
"""

from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from config.settings import settings
from src.services.embedding_service import embedding_service

COLLECTION_NAME = "tonamiibuki_kb"


class ChromaVectorIndex:
    """Persistent ChromaDB vector index for knowledge base documents."""

    def __init__(self) -> None:
        persist_dir = str(Path(settings.VECTOR_STORE_PATH))
        self._client = chromadb.PersistentClient(
            path=persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        self._doc_count: int = 0

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def rebuild(self, documents: list, tokens: list[list[str]]) -> int:
        """Full rebuild: delete existing collection and re-ingest all documents."""
        try:
            self._client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass  # collection may not exist yet
        self._collection = self._client.create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

        if not documents:
            self._doc_count = 0
            return 0

        ids = [doc.doc_id for doc in documents]
        texts = [doc.content[:2000] + " " + doc.title for doc in documents]
        metadatas = [
            {
                "title": doc.title,
                "source": doc.source,
                "tags": ",".join(doc.tags),
            }
            for doc in documents
        ]

        # Use embedding service for vectors
        vectors = embedding_service.embed(texts)

        # Batch add in chunks of 100
        batch = 100
        for i in range(0, len(ids), batch):
            self._collection.add(
                ids=ids[i : i + batch],
                embeddings=vectors[i : i + batch],
                documents=texts[i : i + batch],
                metadatas=metadatas[i : i + batch],
            )

        self._doc_count = len(documents)
        return self._doc_count

    def query(self, query_text: str, top_k: int = 10) -> list[dict]:
        """Semantic search via ChromaDB."""
        try:
            count = self._collection.count()
            if count == 0:
                return []
        except Exception:
            return []
        query_vector = embedding_service.embed(query_text)[0]
        results = self._collection.query(
            query_embeddings=[query_vector],
            n_results=min(top_k, count),
            include=["documents", "metadatas", "distances"],
        )
        if not results["ids"] or not results["ids"][0]:
            return []

        items = []
        for i, doc_id in enumerate(results["ids"][0]):
            dist = results["distances"][0][i] if results["distances"] else 1.0
            score = 1.0 / (1.0 + dist)  # convert cosine distance to similarity
            items.append(
                {
                    "doc_id": doc_id,
                    "content": results["documents"][0][i] if results["documents"] else "",
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "score": round(score, 4),
                }
            )
        return items

    def add(self, doc_id: str, content: str, metadata: dict) -> None:
        """Add a single document."""
        try:
            vec = embedding_service.embed(content)[0]
            self._collection.add(
                ids=[doc_id],
                embeddings=[vec],
                documents=[content],
                metadatas=[metadata],
            )
            self._doc_count += 1
        except Exception:
            pass  # collection may not exist yet; rebuild will pick it up

    def delete(self, doc_id: str) -> None:
        """Remove a single document."""
        try:
            self._collection.delete(ids=[doc_id])
            self._doc_count = max(0, self._doc_count - 1)
        except Exception:
            pass

    def count(self) -> int:
        try:
            return self._collection.count()
        except Exception:
            return 0

    def status(self) -> dict:
        return {
            "backend": "chromadb",
            "collection": COLLECTION_NAME,
            "count": self.count(),
            "ready": True,
            "dim": embedding_service.dim,
        }


# Global singleton
chroma_vector_index = ChromaVectorIndex()
