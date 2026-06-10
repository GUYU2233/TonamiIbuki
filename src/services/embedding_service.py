"""Embedding service – generates dense vector representations for documents and queries.

Supports mock (deterministic hash-based), OpenAI-compatible, and Ollama backends.
"""

import hashlib
import math
import struct
from typing import Sequence

import requests

from config.settings import settings


class EmbeddingService:
    """Multi-provider embedding generator.

    - mock: deterministic pseudo-embedding via SHA-256 → normalized float vector
    - openai: calls /v1/embeddings on OPENAI_BASE_URL with OPENAI_API_KEY
    - ollama: calls /api/embed on OLLAMA_BASE_URL

    All backends return List[float] of the same configured dimension so that
    downstream cosine-similarity / vector-index logic stays provider-agnostic.
    """

    MOCK_DIM = 384  # lightweight default; real providers will override

    def __init__(self) -> None:
        self.provider = settings.EMBEDDING_PROVIDER
        self.model = settings.EMBEDDING_MODEL
        self._dim_cache: int | None = None

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def embed(self, texts: str | list[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""
        if isinstance(texts, str):
            texts = [texts]
        if not texts:
            return []

        if self.provider == "mock":
            return [self._mock_embed(t) for t in texts]
        if self.provider == "openai":
            return self._openai_embed(texts)
        if self.provider == "ollama":
            return self._ollama_embed(texts)

        raise ValueError(f"Unsupported embedding provider: {self.provider}")

    @property
    def dim(self) -> int:
        """Dimension of the embedding vectors (cached after first call)."""
        if self._dim_cache is not None:
            return self._dim_cache
        # probe with a single word to discover real dimension
        try:
            vec = self.embed("dim-probe")[0]
            self._dim_cache = len(vec)
        except Exception:
            self._dim_cache = self.MOCK_DIM
        return self._dim_cache

    def status(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.model,
            "dim": self.dim,
            "ready": True,
        }

    # ------------------------------------------------------------------
    # mock backend
    # ------------------------------------------------------------------

    @staticmethod
    def _mock_embed(text: str) -> list[float]:
        """Deterministic pseudo-embedding so that identical texts produce identical vectors."""
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        # unpack first N × 4 bytes as floats in [-1, 1]
        n = EmbeddingService.MOCK_DIM
        values = []
        for i in range(n):
            chunk = digest[(i * 4) % len(digest) : (i * 4) % len(digest) + 4]
            if len(chunk) < 4:
                chunk = chunk + b"\x00" * (4 - len(chunk))
            val = struct.unpack(">f", chunk)[0]
            # clamp to [-1, 1] and handle NaN / Inf
            if math.isnan(val) or math.isinf(val):
                val = 0.0
            values.append(max(-1.0, min(1.0, val)))
        # L2-normalize
        norm = math.sqrt(sum(v * v for v in values))
        if norm > 0:
            values = [v / norm for v in values]
        return values

    # ------------------------------------------------------------------
    # OpenAI-compatible backend
    # ------------------------------------------------------------------

    def _openai_embed(self, texts: list[str]) -> list[list[float]]:
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is not set")
        url = f"{settings.OPENAI_BASE_URL.rstrip('/')}/embeddings"
        resp = requests.post(
            url,
            json={"input": texts, "model": self.model},
            headers={
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        # sort by index to preserve input order
        items = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in items]

    # ------------------------------------------------------------------
    # Ollama backend
    # ------------------------------------------------------------------

    def _ollama_embed(self, texts: list[str]) -> list[list[float]]:
        url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/embed"
        vectors: list[list[float]] = []
        for text in texts:
            resp = requests.post(
                url,
                json={"model": self.model, "input": text},
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            vectors.append(data["embedding"])
        return vectors


embedding_service = EmbeddingService()
