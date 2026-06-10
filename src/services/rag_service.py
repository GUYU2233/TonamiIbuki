import json
import math
import re
from pathlib import Path
from uuid import uuid4

import jieba
from rank_bm25 import BM25Okapi

from config.settings import settings
from src.models import (
    KnowledgeBulkImportRequest,
    KnowledgeBulkImportResponse,
    KnowledgeImportRequest,
    KnowledgeImportResponse,
    RAGAnswer,
    RAGDocument,
    RAGEvalItem,
    RAGEvalResult,
    RAGQuery,
)
from src.services.embedding_service import embedding_service
from src.services.reranker_service import reranker_service
from src.services.vector_index import chroma_vector_index


KB_PATH = settings.KB_PATH


class RAGService:
    def __init__(self) -> None:
        self.documents: list[RAGDocument] = []
        self.tokens: list[list[str]] = []
        self.bm25: BM25Okapi | None = None
        self.doc_vectors: list[list[float]] = []  # dense embedding vectors
        self.reload()

    def reload(self) -> int:
        self.documents = self._load_documents()
        self.tokens = [self._tokenize(doc.content + " " + doc.title + " " + " ".join(doc.tags)) for doc in self.documents]
        self.bm25 = BM25Okapi(self.tokens) if self.tokens else None
        # Generate dense embedding vectors for all documents
        if self.documents:
            texts = [doc.content[:2000] + " " + doc.title for doc in self.documents]
            self.doc_vectors = embedding_service.embed(texts)
        else:
            self.doc_vectors = []
        chroma_vector_index.rebuild(self.documents, self.tokens)
        return len(self.documents)

    def import_document(self, request: KnowledgeImportRequest) -> KnowledgeImportResponse:
        documents = self._load_documents()
        document = RAGDocument(
            doc_id=f"kb-{uuid4().hex[:8]}",
            title=request.title,
            source=request.source,
            content=request.content,
            tags=request.tags,
        )
        documents.append(document)
        KB_PATH.parent.mkdir(parents=True, exist_ok=True)
        KB_PATH.write_text(
            json.dumps([doc.model_dump(mode="json") for doc in documents], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        total = self.reload()
        return KnowledgeImportResponse(document=document, total_documents=total)

    def bulk_import(self, request: KnowledgeBulkImportRequest) -> KnowledgeBulkImportResponse:
        base = Path(request.directory)
        documents = self._load_documents()
        sources: list[str] = []
        imported = 0
        for pattern in request.include_patterns:
            for path in sorted(base.glob(pattern)):
                if not path.is_file():
                    continue
                content = path.read_text(encoding="utf-8", errors="ignore")
                for idx, chunk in enumerate(self._split_document(content)):
                    if not chunk.strip():
                        continue
                    documents.append(
                        RAGDocument(
                            doc_id=f"kb-{uuid4().hex[:8]}",
                            title=f"{path.name}#{idx + 1}",
                            source=str(path),
                            content=chunk,
                            tags=[path.suffix.lstrip("."), "bulk-import"],
                        )
                    )
                    imported += 1
                sources.append(str(path))
        KB_PATH.parent.mkdir(parents=True, exist_ok=True)
        KB_PATH.write_text(
            json.dumps([doc.model_dump(mode="json") for doc in documents], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        total = self.reload()
        return KnowledgeBulkImportResponse(imported_documents=imported, total_documents=total, sources=sources)

    def _split_document(self, content: str, chunk_size: int = 600, overlap: int = 120) -> list[str]:
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", content) if part.strip()]
        chunks: list[str] = []
        current = ""
        for paragraph in paragraphs:
            if len(current) + len(paragraph) <= chunk_size:
                current = f"{current}\n\n{paragraph}".strip()
            else:
                if current:
                    chunks.append(current)
                current = paragraph
                while len(current) > chunk_size:
                    chunks.append(current[:chunk_size])
                    current = current[chunk_size - overlap :]
        if current:
            chunks.append(current)
        return chunks

    def evaluate(self, items: list[RAGEvalItem], top_k: int = 5) -> RAGEvalResult:
        details: list[dict] = []
        hits = 0
        for item in items:
            answer = self.query(RAGQuery(query=item.query, top_k=top_k))
            retrieved = [doc.doc_id for doc in answer.citations]
            hit = any(expected in retrieved for expected in item.expected_doc_ids)
            hits += int(hit)
            details.append({"query": item.query, "expected": item.expected_doc_ids, "retrieved": retrieved, "hit": hit})
        total = len(items)
        return RAGEvalResult(total=total, top_k=top_k, hit_count=hits, hit_rate=round(hits / total, 4) if total else 0.0, details=details)

    def _load_documents(self) -> list[RAGDocument]:
        if not KB_PATH.exists():
            return []
        raw = json.loads(KB_PATH.read_text(encoding="utf-8"))
        return [RAGDocument.model_validate(item) for item in raw]

    def _tokenize(self, text: str) -> list[str]:
        exact_codes = re.findall(r"[A-Z]+-[A-Z]+-\d+|CrashLoopBackOff", text)
        words = [word.strip().lower() for word in jieba.lcut(text) if word.strip()]
        return [*words, *[code.lower() for code in exact_codes]]

    def _dense_cosine(self, left: list[float], right: list[float]) -> float:
        """Cosine similarity between two dense embedding vectors."""
        numerator = sum(a * b for a, b in zip(left, right, strict=False))
        left_norm = math.sqrt(sum(v * v for v in left))
        right_norm = math.sqrt(sum(v * v for v in right))
        if not left_norm or not right_norm:
            return 0.0
        return numerator / (left_norm * right_norm)

    def query(self, request: RAGQuery) -> RAGAnswer:
        if not self.documents:
            return RAGAnswer(answer="知识库为空，请先导入运维手册。", citations=[])
        query_tokens = self._tokenize(request.query)

        # 1. BM25 lexical scores
        bm25_scores = self.bm25.get_scores(query_tokens) if self.bm25 else [0.0] * len(self.documents)

        # 2. Dense embedding scores
        query_vector = embedding_service.embed(request.query)[0]
        vector_scores = [self._dense_cosine(query_vector, doc_vec) for doc_vec in self.doc_vectors]

        # 3. Reciprocal Rank Fusion (RRF)
        bm25_rank = sorted(range(len(self.documents)), key=lambda idx: bm25_scores[idx], reverse=True)
        vector_rank = sorted(range(len(self.documents)), key=lambda idx: vector_scores[idx], reverse=True)
        fused: dict[int, float] = {}
        for rank, idx in enumerate(bm25_rank):
            fused[idx] = fused.get(idx, 0.0) + 1 / (settings.RRF_K + rank + 1)
        for rank, idx in enumerate(vector_rank):
            fused[idx] = fused.get(idx, 0.0) + 1 / (settings.RRF_K + rank + 1)
        ranked = sorted(fused.items(), key=lambda item: item[1], reverse=True)

        # 4. Build candidate list with fusion scores (fetch top_k * 3 for re-ranking)
        candidate_count = min(len(ranked), request.top_k * 3)
        candidates: list[RAGDocument] = []
        for idx, score in ranked[:candidate_count]:
            doc = self.documents[idx].model_copy()
            doc.score = round(float(score), 4)
            candidates.append(doc)

        # 5. Re-rank candidates
        reranked = reranker_service.rerank(request.query, candidates, top_k=request.top_k)
        citations = reranked

        answer = self._compose_answer(request.query, citations)
        return RAGAnswer(answer=answer, citations=citations)

    def _compose_answer(self, query: str, citations: list[RAGDocument]) -> str:
        if not citations:
            return "未检索到相关知识，请补充知识库或转人工。"
        steps = []
        for doc in citations[:3]:
            snippet = doc.content[:120].replace("\n", " ")
            steps.append(f"- 参考《{doc.title}》：{snippet}...")
        return "根据知识库，建议按以下证据链处理：\n" + "\n".join(steps)


rag_service = RAGService()
