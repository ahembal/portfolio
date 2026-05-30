"""Tests for LLM-as-judge scorer."""

from src.evaluation.judge import (
    score_context_relevance,
    score_faithfulness,
    score_answer_relevance,
    evaluate,
)

QUERY  = "What is the function of TP53?"
CHUNKS = ["TP53 is a tumour suppressor gene.", "TP53 regulates apoptosis and cell cycle."]
ANSWER = "TP53 is a tumour suppressor that regulates apoptosis."


def _mock_llm(response: str):
    """Mock LLM as a plain callable — matches the (prompt: str) -> str interface."""
    return lambda prompt: response


def _mock_llm_sequence(*responses: str):
    """Mock LLM that cycles through a sequence of responses — one per call."""
    responses = list(responses)
    calls = [0]
    def call(prompt: str) -> str:
        r = responses[calls[0] % len(responses)]
        calls[0] += 1
        return r
    return call


class TestContextRelevance:
    def test_perfect_relevance(self):
        llm = _mock_llm('{"relevant": 2, "total": 2}')
        assert score_context_relevance(QUERY, CHUNKS, llm) == 1.0

    def test_partial_relevance(self):
        llm = _mock_llm('{"relevant": 1, "total": 2}')
        assert score_context_relevance(QUERY, CHUNKS, llm) == 0.5

    def test_no_relevance(self):
        llm = _mock_llm('{"relevant": 0, "total": 2}')
        assert score_context_relevance(QUERY, CHUNKS, llm) == 0.0


class TestFaithfulness:
    def test_fully_faithful(self):
        llm = _mock_llm('{"supported": 3, "total": 3}')
        assert score_faithfulness(QUERY, ANSWER, CHUNKS, llm) == 1.0

    def test_partially_faithful(self):
        llm = _mock_llm('{"supported": 2, "total": 4}')
        assert score_faithfulness(QUERY, ANSWER, CHUNKS, llm) == 0.5

    def test_empty_answer_is_faithful(self):
        llm = _mock_llm('{"supported": 0, "total": 0}')
        assert score_faithfulness(QUERY, "", CHUNKS, llm) == 1.0


class TestAnswerRelevance:
    def test_relevant_answer(self):
        llm = _mock_llm('{"score": 0.9}')
        assert score_answer_relevance(QUERY, ANSWER, llm) == 0.9

    def test_score_clamped_to_one(self):
        llm = _mock_llm('{"score": 1.5}')
        assert score_answer_relevance(QUERY, ANSWER, llm) == 1.0

    def test_score_clamped_to_zero(self):
        llm = _mock_llm('{"score": -0.3}')
        assert score_answer_relevance(QUERY, ANSWER, llm) == 0.0


class TestEvaluate:
    def test_returns_all_metrics(self):
        llm = _mock_llm('{"relevant": 2, "total": 2, "supported": 2, "score": 0.8}')
        scores = evaluate(QUERY, CHUNKS, ANSWER, llm)
        assert set(scores.keys()) == {"context_relevance", "faithfulness", "answer_relevance"}

    def test_scores_in_range(self):
        llm = _mock_llm_sequence(
            '{"relevant": 1, "total": 2}',
            '{"supported": 3, "total": 4}',
            '{"score": 0.7}',
        )
        scores = evaluate(QUERY, CHUNKS, ANSWER, llm)
        for v in scores.values():
            assert -1.0 <= v <= 1.0
