"""Tests for RAG evaluation metrics."""

import pytest
from src.services.evaluation_service import EvaluationService, EvaluationMetrics


class TestEvaluationMetrics:
    """Unit tests for EvaluationMetrics calculations."""

    def test_perfect_match(self):
        m = EvaluationMetrics()
        m.add_query_result(
            query="test",
            relevant_ids=["a", "b"],
            retrieved_ids=["a", "b", "c"],
            latency_ms=10.0,
        )
        m.compute_summary()
        s = m.summary
        # retrieved = [a,b,c] → k=min(3,5)=3, 2 relevant in top-3 → 2/3
        assert abs(s["precision@5"] - 2/3) < 0.01
        assert s["recall"] == 1.0       # all relevant retrieved
        assert s["mrr"] == 1.0          # first hit at rank 1
        assert s["num_queries"] == 1

    def test_partial_match(self):
        m = EvaluationMetrics()
        m.add_query_result(
            query="test",
            relevant_ids=["a", "b", "c"],
            retrieved_ids=["x", "a", "y", "b"],
            latency_ms=5.0,
        )
        m.compute_summary()
        s = m.summary
        # top-5: x, a, y, b → 2 relevant out of 4 retrieved, 2 relevant in top-5
        assert s["precision@5"] == 2 / 4  # 2 of first 4 are relevant
        assert s["recall"] == 2 / 3        # 2 of 3 relevant found
        assert s["mrr"] == 1 / 2           # first hit at rank 2
        assert s["num_queries"] == 1

    def test_no_match(self):
        m = EvaluationMetrics()
        m.add_query_result(
            query="test",
            relevant_ids=["a", "b"],
            retrieved_ids=["x", "y", "z"],
            latency_ms=3.0,
        )
        m.compute_summary()
        s = m.summary
        assert s["precision@5"] == 0.0
        assert s["recall"] == 0.0
        assert s["mrr"] == 0.0
        assert s["map"] == 0.0

    def test_empty_retrieved(self):
        m = EvaluationMetrics()
        m.add_query_result(
            query="test",
            relevant_ids=["a"],
            retrieved_ids=[],
            latency_ms=1.0,
        )
        m.compute_summary()
        s = m.summary
        assert s["recall"] == 0.0
        assert s["mrr"] == 0.0

    def test_multiple_queries_aggregate(self):
        m = EvaluationMetrics()
        m.add_query_result("q1", ["a", "b"], ["a", "b"], latency_ms=5.0)
        m.add_query_result("q2", ["c"], ["x", "y", "c"], latency_ms=3.0)
        m.compute_summary()
        s = m.summary
        assert s["num_queries"] == 2
        # q1: retrieved=[a,b], k=2, 2 relevant → 2/2=1.0
        # q2: retrieved=[x,y,c], k=3, 1 relevant → 1/3≈0.333
        # avg = (1.0 + 0.333) / 2 ≈ 0.667
        assert abs(s["precision@5"] - 0.667) < 0.01

    def test_mrr_multiple(self):
        m = EvaluationMetrics()
        m.add_query_result("q1", ["a"], ["a", "b"])        # MRR = 1/1 = 1.0
        m.add_query_result("q2", ["c"], ["x", "c"])         # MRR = 1/2 = 0.5
        m.add_query_result("q3", ["d"], ["x", "y", "z"])   # MRR = 0.0
        m.compute_summary()
        assert abs(m.summary["mrr"] - 0.5) < 0.01  # (1.0 + 0.5 + 0.0) / 3

    def test_latency_tracking(self):
        m = EvaluationMetrics()
        m.add_query_result("q1", ["a"], ["a"], latency_ms=12.0)
        m.add_query_result("q2", ["b"], ["b"], latency_ms=8.0)
        m.compute_summary()
        assert m.summary["avg_latency_ms"] == 10.0


class TestEvaluationService:
    """Tests for EvaluationService."""

    def test_default_queries(self):
        svc = EvaluationService()
        queries = svc.load_test_queries("nonexistent_path.json")
        assert len(queries) == 10
        assert all("query" in q and "relevant_ids" in q for q in queries)

    def test_evaluate_without_rag(self):
        svc = EvaluationService()
        metrics = svc.evaluate_sync()
        s = metrics.summary
        assert s["num_queries"] == 10
        assert s["precision@5"] == 1.0  # without RAG, mock returns exact match
        assert s["recall"] == 1.0

    def test_evaluate_with_custom_queries(self):
        svc = EvaluationService()
        custom = [
            {"query": "Nginx error", "relevant_ids": ["nginx_502", "nginx_504"]},
            {"query": "k8s issue", "relevant_ids": ["k8s_pod_crashloop"]},
        ]
        metrics = svc.evaluate_sync(custom)
        assert metrics.summary["num_queries"] == 2

    def test_metrics_to_dict_serializable(self):
        import json
        m = EvaluationMetrics()
        m.add_query_result("q", ["a"], ["a", "b"])
        m.compute_summary()
        # Should be JSON serializable
        dumped = json.dumps(m.summary)
        assert "precision" in dumped
