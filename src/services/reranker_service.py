"""Reranker service – re-ranks a candidate list to improve retrieval precision.

Supports mock (BM25-score-based) and cross-encoder placeholders.
"""

from src.models import RAGDocument
from config.settings import settings


class RerankerService:
    """Multi-provider re-ranker.

    - mock: returns candidates sorted by their existing score (identity re-rank)
    - cross-encoder: placeholder – would call a local or remote cross-encoder model
    """

    def __init__(self) -> None:
        self.provider = settings.RERANKER_PROVIDER

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def rerank(self, query: str, candidates: list[RAGDocument], top_k: int | None = None) -> list[RAGDocument]:
        """Re-rank candidates and return the top_k results.

        If top_k is None, returns all candidates in re-ranked order.
        """
        if not candidates:
            return []

        if self.provider == "mock":
            ranked = self._mock_rerank(query, candidates)
        elif self.provider == "cross-encoder":
            ranked = self._cross_encoder_rerank(query, candidates)
        else:
            raise ValueError(f"Unsupported reranker provider: {self.provider}")

        if top_k is not None:
            ranked = ranked[:top_k]
        return ranked

    def status(self) -> dict:
        return {
            "provider": self.provider,
            "ready": True,
        }

    # ------------------------------------------------------------------
    # mock backend
    # ------------------------------------------------------------------

    @staticmethod
    def _mock_rerank(_query: str, candidates: list[RAGDocument]) -> list[RAGDocument]:
        """Sort by existing score descending – identity re-rank."""
        return sorted(candidates, key=lambda d: d.score, reverse=True)

    # ------------------------------------------------------------------
    # cross-encoder placeholder
    # ------------------------------------------------------------------

    @staticmethod
    def _cross_encoder_rerank(_query: str, candidates: list[RAGDocument]) -> list[RAGDocument]:
        """Placeholder – would use sentence-transformers CrossEncoder in production."""
        # In production, load a CrossEncoder model and score each (query, doc.content) pair.
        return sorted(candidates, key=lambda d: d.score, reverse=True)


reranker_service = RerankerService()
