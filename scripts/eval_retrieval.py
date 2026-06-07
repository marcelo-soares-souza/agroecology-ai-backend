#!/usr/bin/env python3
"""Retrieval evaluation script.

Loads questions from docs/RAG_EVALUATION_SET.md, runs hybrid_search(),
and reports metrics: Recall@K, MRR, hit rate, latency.

Usage:
    python backend/scripts/eval_retrieval.py
    python backend/scripts/eval_retrieval.py --no-reranker
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.adapters.rest.dependencies import (
    get_retriever,
    init_services,
    shutdown_services,
)
from src.shared.logging_utils import configure_logging

configure_logging()

_EVAL_FILE = (
    Path(__file__).resolve().parent.parent.parent / "docs" / "RAG_EVALUATION_SET.md"
)

_QUESTIONS = [
    # (id, question, expected_doc_keywords)
    ("Q1_definition", "O que são Sistemas Agroflorestais?", ["SAF", "agroflorest"]),
    ("Q2_definition", "O que é agroecologia?", ["agroecologia"]),
    (
        "Q3_definition",
        "Defina agricultura familiar",
        ["agricultura familiar", "familiar"],
    ),
    (
        "Q4_definition_es",
        "Qué es la soberanía alimentaria?",
        ["soberanía", "alimentaria"],
    ),
    ("Q5_definition_en", "What is permaculture?", ["permaculture"]),
    (
        "Q6_specific",
        "Quais são as conclusões principais do paper sobre SAFs?",
        ["SAF", "conclus"],
    ),
    (
        "Q7_specific",
        "O que o estudo encontrou sobre carbono no solo?",
        ["carbono", "solo"],
    ),
    (
        "Q8_compare",
        "Compare SAFs com monocultura em termos de biodiversidade",
        ["SAF", "biodiversidade"],
    ),
    (
        "Q9_compare",
        "Qual a diferença entre agroecologia e agricultura orgânica?",
        ["agroecologia", "orgânica"],
    ),
    (
        "Q10_method",
        "Como foi feito o experimento de adubação verde?",
        ["adubação", "verde", "método"],
    ),
    (
        "Q11_method",
        "Qual foi a metodologia usada para medir a fixação de nitrogênio?",
        ["nitrogênio", "fixação"],
    ),
    (
        "Q12_results",
        "Quais foram os resultados do consórcio milho-feijão?",
        ["milho", "feijão", "consórcio"],
    ),
    (
        "Q13_followup",
        "E quais são os benefícios econômicos?",
        ["benefícios", "econômic"],
    ),
    ("Q14_followup", "E no Brasil?", ["Brasil"]),
    ("Q15_ooc", "Qual é a capital da França?", []),
    ("Q16_ooc", "Como funciona um motor a combustão?", []),
]


def _loosely_relevant(text: str, keywords: list[str]) -> bool:
    if not keywords:
        return False
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate retrieval pipeline")
    _ = parser.parse_args()

    print("=== RAG Retrieval Evaluation ===\n")

    try:
        asyncio.run(init_services())
    except Exception as e:
        print(f"WARNING: Could not initialize services: {e}")
        print("Continuing with basic evaluation...\n")
        asyncio.run(shutdown_services())
        return

    retriever = get_retriever()

    recall_5 = 0
    recall_10 = 0
    mrr_sum = 0.0
    multi_doc = 0
    latencies: list[float] = []

    for qid, question, keywords in _QUESTIONS:
        t0 = time.perf_counter()
        try:
            results = retriever.hybrid_search(question, top_k=10)
        except Exception as e:
            print(f"  {qid}: ERROR — {e}")
            continue
        elapsed_ms = (time.perf_counter() - t0) * 1000
        latencies.append(elapsed_ms)

        first_relevant_rank = 0
        relevant_in_5 = False
        relevant_in_10 = False
        sources = set()

        for rank, r in enumerate(results, 1):
            text = r.text
            source = r.source
            sources.add(source)

            if _loosely_relevant(text, keywords):
                if first_relevant_rank == 0:
                    first_relevant_rank = rank
                if rank <= 5:
                    relevant_in_5 = True
                if rank <= 10:
                    relevant_in_10 = True

        if first_relevant_rank > 0:
            mrr_sum += 1.0 / first_relevant_rank

        if relevant_in_5:
            recall_5 += 1
        if relevant_in_10:
            recall_10 += 1
        if len(sources) >= 2:
            multi_doc += 1

        status = "HIT" if relevant_in_5 else ("NEAR" if relevant_in_10 else "MISS")
        print(
            f"  {qid}: {status} | first_rank={first_relevant_rank} | "
            f"sources={len(sources)} | {elapsed_ms:.0f}ms"
        )

    total = len(_QUESTIONS)
    latencies.sort()
    p50 = latencies[int(len(latencies) * 0.5)] if latencies else 0
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0

    print(f"\n=== Results ({total} questions) ===")
    print(f"  Recall@5:       {recall_5}/{total} = {recall_5 / total:.1%}")
    print(f"  Recall@10:      {recall_10}/{total} = {recall_10 / total:.1%}")
    print(f"  MRR:            {mrr_sum / total:.4f}")
    print(f"  Multi-doc hit:  {multi_doc}/{total} = {multi_doc / total:.1%}")
    print(f"  Latency p50:    {p50:.0f}ms")
    print(f"  Latency p95:    {p95:.0f}ms")
    print(
        f"  Latency max:    {latencies[-1]:.0f}ms"
        if latencies
        else "  Latency max:    N/A"
    )

    asyncio.run(shutdown_services())


if __name__ == "__main__":
    main()
