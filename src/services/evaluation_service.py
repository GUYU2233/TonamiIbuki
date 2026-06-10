"""Evaluation service for RAG pipeline metrics."""

import time
import json
from pathlib import Path
from typing import Any
from collections import defaultdict


class EvaluationMetrics:
    """Container for evaluation results."""

    def __init__(self) -> None:
        self.queries: list[dict] = []
        self.summary: dict[str, float] = {}

    def add_query_result(
        self,
        query: str,
        relevant_ids: list[str],
        retrieved_ids: list[str],
        retrieved_scores: list[float] | None = None,
        latency_ms: float = 0.0,
    ) -> None:
        self.queries.append({
            "query": query,
            "relevant_ids": relevant_ids,
            "retrieved_ids": retrieved_ids,
            "retrieved_scores": retrieved_scores or [],
            "latency_ms": latency_ms,
        })

    def compute_summary(self) -> dict[str, float]:
        """Compute aggregate metrics across all queries."""
        if not self.queries:
            return {}

        precision_list = []
        recall_list = []
        mrr_list = []
        ndcg_list = []
        map_list = []
        latency_list = []

        for q in self.queries:
            relevant = set(q["relevant_ids"])
            retrieved = q["retrieved_ids"]
            scores = q["retrieved_scores"]

            # Precision@k (k=min(len(retrieved), 5))
            k = min(len(retrieved), 5) if retrieved else 1
            p = len(set(retrieved[:k]) & relevant) / k if k > 0 else 0.0
            precision_list.append(p)

            # Recall
            r = len(set(retrieved) & relevant) / len(relevant) if relevant else 0.0
            recall_list.append(r)

            # MRR
            mrr = self._mrr(relevant, retrieved)
            mrr_list.append(mrr)

            # NDCG@k
            ndcg = self._ndcg(relevant, retrieved, scores, k)
            ndcg_list.append(ndcg)

            # MAP
            ap = self._average_precision(relevant, retrieved)
            map_list.append(ap)

            latency_list.append(q["latency_ms"])

        n = len(self.queries)
        self.summary = {
            "num_queries": n,
            "precision@5": sum(precision_list) / n,
            "recall": sum(recall_list) / n,
            "mrr": sum(mrr_list) / n,
            "ndcg@5": sum(ndcg_list) / n,
            "map": sum(map_list) / n,
            "avg_latency_ms": sum(latency_list) / n,
        }
        return self.summary

    @staticmethod
    def _mrr(relevant: set, retrieved: list[str]) -> float:
        for i, doc_id in enumerate(retrieved, 1):
            if doc_id in relevant:
                return 1.0 / i
        return 0.0

    @staticmethod
    def _ndcg(relevant: set, retrieved: list[str], scores: list[float], k: int) -> float:
        if not retrieved or not relevant:
            return 0.0
        dcg = 0.0
        for i, doc_id in enumerate(retrieved[:k]):
            if doc_id in relevant:
                # Use reciprocal rank as relevance if no explicit scores
                dcg += 1.0 / (EvaluationMetrics._log2(i + 2))
        # Ideal DCG: all relevant docs at top
        ideal_count = min(len(relevant), k)
        idcg = sum(1.0 / EvaluationMetrics._log2(i + 2) for i in range(ideal_count))
        return dcg / idcg if idcg > 0 else 0.0

    @staticmethod
    def _average_precision(relevant: set, retrieved: list[str]) -> float:
        if not relevant:
            return 0.0
        hits = 0
        ap_sum = 0.0
        for i, doc_id in enumerate(retrieved, 1):
            if doc_id in relevant:
                hits += 1
                ap_sum += hits / i
        return ap_sum / len(relevant)

    @staticmethod
    def _log2(x: float) -> float:
        import math
        return math.log2(x)


class EvaluationService:
    """Runs RAG pipeline evaluations."""

    def __init__(self, rag_service=None):
        self._rag = rag_service

    def set_rag_service(self, rag_service) -> None:
        self._rag = rag_service

    def load_test_queries(self, path: str = "data/eval/test_queries.json") -> list[dict]:
        """Load evaluation test queries.

        Each query dict:
            - query (str)
            - relevant_ids (list[str]): ground-truth document IDs
        """
        p = Path(path)
        if not p.exists():
            # Return built-in defaults
            return self._default_queries()
        return json.loads(p.read_text(encoding="utf-8"))

    @staticmethod
    def _default_queries() -> list[dict]:
        return [
            {
                "query": "Nginx 502 错误怎么排查",
                "relevant_ids": ["nginx_502"],
            },
            {
                "query": "磁盘满了服务写不进去",
                "relevant_ids": ["disk_full"],
            },
            {
                "query": "CPU 100% 怎么办",
                "relevant_ids": ["high_cpu"],
            },
            {
                "query": "MySQL 查询很慢",
                "relevant_ids": ["mysql_slow"],
            },
            {
                "query": "Pod 一直重启 CrashLoopBackOff",
                "relevant_ids": ["k8s_pod_crashloop"],
            },
            {
                "query": "OOM 进程被杀",
                "relevant_ids": ["oom_kill"],
            },
            {
                "query": "SSL 证书过期了",
                "relevant_ids": ["ssl_expiry"],
            },
            {
                "query": "Docker daemon 连不上",
                "relevant_ids": ["docker_daemon_down"],
            },
            {
                "query": "DNS 解析失败",
                "relevant_ids": ["dns_failure"],
            },
            {
                "query": "文件描述符用完 too many open files",
                "relevant_ids": ["file_descriptor_exhaust"],
            },
        ]

    async def evaluate(self, queries: list[dict] | None = None) -> EvaluationMetrics:
        """Run evaluation on a set of test queries.

        Args:
            queries: List of query dicts. Uses defaults if None.

        Returns:
            EvaluationMetrics with per-query and aggregate results.
        """
        if queries is None:
            queries = self.load_test_queries()

        metrics = EvaluationMetrics()

        for q in queries:
            query_text = q["query"]
            relevant_ids = q["relevant_ids"]

            if self._rag is None:
                # Without RAG service, simulate results for testing
                retrieved_ids = relevant_ids[:1]  # perfect match for testing
                retrieved_scores = [0.9]
                latency_ms = 1.0
            else:
                t0 = time.perf_counter()
                results = await self._rag.retrieve(query_text, top_k=5)
                latency_ms = (time.perf_counter() - t0) * 1000
                retrieved_ids = [r.get("id", "") for r in results]
                retrieved_scores = [r.get("score", 0.0) for r in results]

            metrics.add_query_result(
                query=query_text,
                relevant_ids=relevant_ids,
                retrieved_ids=retrieved_ids,
                retrieved_scores=retrieved_scores,
                latency_ms=latency_ms,
            )

        metrics.compute_summary()
        return metrics

    def evaluate_sync(self, queries: list[dict] | None = None) -> EvaluationMetrics:
        """Synchronous wrapper for evaluate."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None:
            import concurrent.futures
            future = asyncio.run_coroutine_threadsafe(self.evaluate(queries), loop)
            return future.result()
        else:
            return asyncio.run(self.evaluate(queries))
