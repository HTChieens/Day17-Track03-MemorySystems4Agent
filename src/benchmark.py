from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_advanced import AdvancedAgent
from agent_baseline import BaselineAgent
from config import load_config


@dataclass
class BenchmarkRow:
    agent_name: str
    agent_tokens_only: int
    prompt_tokens_processed: int
    recall_score: float
    response_quality: float
    memory_growth_bytes: int
    compactions: int


def load_conversations(path: Path) -> list[dict[str, Any]]:
    """Student TODO: read JSON conversations from disk."""
    import json

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def recall_points(answer: str, expected: list[str]) -> float:
    """Student TODO: return 0 / 0.5 / 1 depending on how many expected facts appear."""
    if not expected:
        return 1.0

    answer_lower = answer.lower()
    matches = 0
    for fact in expected:
        if fact.lower() in answer_lower:
            matches += 1

    if matches == 0:
        return 0.0
    elif matches == len(expected):
        return 1.0
    else:
        return 0.5


def heuristic_quality(answer: str, expected: list[str]) -> float:
    """Student TODO: add a lightweight quality score for offline mode."""
    if not answer or "error" in answer.lower():
        return 0.0
    score = 0.5
    answer_lower = answer.lower()
    for fact in expected:
        if fact.lower() in answer_lower:
            score += 0.3
            break
    if len(answer) > 15:
        score += 0.2
    return min(score, 1.0)


def run_agent_benchmark(
    agent_name: str, agent, conversations: list[dict[str, Any]], config
) -> BenchmarkRow:
    """Student TODO: evaluate one agent over many conversations.

    Pseudocode:
    1. Feed all turns to the agent.
    2. Track `agent tokens only`.
    3. Track `prompt tokens processed`.
    4. Ask recall questions in a fresh thread.
    5. Compute average recall and quality.
    6. Record memory file growth and compaction count.
    """
    import shutil

    # Reset profile storage before benchmarking this agent
    profiles_dir = config.state_dir / "profiles"
    if profiles_dir.exists():
        try:
            shutil.rmtree(profiles_dir)
        except Exception:
            pass

    total_agent_tokens = 0
    total_prompt_tokens = 0
    total_compactions = 0

    recall_scores = []
    quality_scores = []

    for conv in conversations:
        user_id = conv["user_id"]
        conv_id = conv["id"]
        thread_id = conv_id

        # Feed turns
        for turn in conv["turns"]:
            agent.reply(user_id, thread_id, turn)

        # Record thread tokens
        total_agent_tokens += agent.token_usage(thread_id)
        total_prompt_tokens += agent.prompt_token_usage(thread_id)
        total_compactions += agent.compaction_count(thread_id)

        # Ask recall questions in a fresh thread
        recall_thread_prefix = f"recall-{conv_id}"
        for idx, q_info in enumerate(conv["recall_questions"]):
            q_text = q_info["question"]
            expected = q_info["expected_contains"]

            recall_thread_id = f"{recall_thread_prefix}-{idx}"
            reply_dict = agent.reply(user_id, recall_thread_id, q_text)

            # Record recall thread tokens
            total_agent_tokens += agent.token_usage(recall_thread_id)
            total_prompt_tokens += agent.prompt_token_usage(recall_thread_id)
            total_compactions += agent.compaction_count(recall_thread_id)

            answer = reply_dict["content"]
            r_score = recall_points(answer, expected)
            q_score = heuristic_quality(answer, expected)

            recall_scores.append(r_score)
            quality_scores.append(q_score)

    # Compute memory growth
    memory_growth = 0
    if profiles_dir.exists():
        for p in profiles_dir.glob("*.md"):
            memory_growth += p.stat().st_size

    avg_recall = sum(recall_scores) / len(recall_scores) if recall_scores else 0.0
    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0

    return BenchmarkRow(
        agent_name=agent_name,
        agent_tokens_only=total_agent_tokens,
        prompt_tokens_processed=total_prompt_tokens,
        recall_score=avg_recall,
        response_quality=avg_quality,
        memory_growth_bytes=memory_growth,
        compactions=total_compactions,
    )


def format_rows(rows: list[BenchmarkRow]) -> str:
    """Student TODO: print a markdown table or tabulated output."""
    from tabulate import tabulate

    table_data = []
    for r in rows:
        table_data.append(
            [
                r.agent_name,
                r.agent_tokens_only,
                r.prompt_tokens_processed,
                f"{r.recall_score * 100:.1f}%",
                f"{r.response_quality * 100:.1f}%",
                r.memory_growth_bytes,
                r.compactions,
            ]
        )
    headers = [
        "Agent",
        "Agent tokens only",
        "Prompt tokens processed",
        "Cross-session recall",
        "Response quality",
        "Memory growth (bytes)",
        "Compactions",
    ]
    return tabulate(table_data, headers=headers, tablefmt="github")


def main() -> None:
    """Student TODO: run both benchmark suites.

    Required benchmark sections:
    - Standard benchmark from `data/conversations.json`
    - Long-context stress benchmark from `data/advanced_long_context.json`

    Compare:
    - Baseline
    - Advanced

    Keep the same output columns as the solved lab:
    - Agent tokens only
    - Prompt tokens processed
    - Cross-session recall
    - Response quality
    - Memory growth (bytes)
    - Compactions
    """
    config = load_config(Path(__file__).resolve().parent.parent)

    # Load datasets
    standard_data_path = config.data_dir / "conversations.json"
    stress_data_path = config.data_dir / "advanced_long_context.json"

    standard_convs = load_conversations(standard_data_path)
    stress_convs = load_conversations(stress_data_path)

    # 1. Standard Benchmark
    print("=== RUNNING STANDARD BENCHMARK ===")
    baseline_std = BaselineAgent(config, force_offline=True)
    advanced_std = AdvancedAgent(config, force_offline=True)

    row_baseline_std = run_agent_benchmark("Baseline Agent", baseline_std, standard_convs, config)
    row_advanced_std = run_agent_benchmark("Advanced Agent", advanced_std, standard_convs, config)

    print("\nStandard Benchmark Results:")
    print(format_rows([row_baseline_std, row_advanced_std]))
    print("\n" + "=" * 50 + "\n")

    # 2. Long-Context Stress Benchmark
    print("=== RUNNING LONG-CONTEXT STRESS BENCHMARK ===")
    baseline_stress = BaselineAgent(config, force_offline=True)
    advanced_stress = AdvancedAgent(config, force_offline=True)

    row_baseline_stress = run_agent_benchmark(
        "Baseline Agent", baseline_stress, stress_convs, config
    )
    row_advanced_stress = run_agent_benchmark(
        "Advanced Agent", advanced_stress, stress_convs, config
    )

    print("\nLong-Context Stress Benchmark Results:")
    print(format_rows([row_baseline_stress, row_advanced_stress]))



if __name__ == "__main__":
    main()
