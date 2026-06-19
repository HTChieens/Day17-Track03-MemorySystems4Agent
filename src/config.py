from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

from model_provider import ProviderConfig


@dataclass
class LabConfig:
    """Student TODO: define the shared configuration for the lab.

    Hints:
    - Keep paths for the repo root, dataset directory, and state directory.
    - Add compact-memory settings such as threshold and number of messages to keep.
    - Add provider settings for `openai`, `custom`, `gemini`, `anthropic`, `ollama`, and `openrouter`.
    """

    base_dir: Path
    data_dir: Path
    state_dir: Path
    compact_threshold_tokens: int
    compact_keep_messages: int
    model: ProviderConfig
    judge_model: ProviderConfig



def load_config(base_dir: Path | None = None) -> LabConfig:
    """Student TODO: load environment variables and return a LabConfig.

    Pseudocode:
    1. Resolve the repo root or default to the current file parent.
    2. Optionally load values from `.env`.
    3. Create `state/` if it does not exist.
    4. Return a populated LabConfig instance.
    """

    root = (base_dir or Path(__file__).resolve().parent.parent).resolve()

    # Load from .env if it exists
    env_path = root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        load_dotenv()

    # Ensure state directory exists
    state_dir = root / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    data_dir = root / "data"

    llm_provider = os.getenv("LLM_PROVIDER", "openrouter")
    llm_model = os.getenv("LLM_MODEL", "google/gemini-2.5-flash")

    judge_provider = os.getenv("JUDGE_PROVIDER", "openrouter")
    judge_model = os.getenv("JUDGE_MODEL", "google/gemini-2.5-flash")

    # Sensible defaults for compact memory
    compact_threshold = int(os.getenv("COMPACT_THRESHOLD_TOKENS", "1000"))
    compact_keep = int(os.getenv("COMPACT_KEEP_MESSAGES", "4"))

    def get_provider_details(provider: str, model_name: str) -> ProviderConfig:
        from model_provider import normalize_provider
        provider = normalize_provider(provider)

        api_key = None
        base_url = None

        if provider == "openrouter":
            api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_kEY")
            base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        elif provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            base_url = os.getenv("OPENAI_BASE_URL")
        elif provider == "gemini":
            api_key = os.getenv("GEMINI_API_KEY")
        elif provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")
        elif provider == "ollama":
            base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        elif provider == "custom":
            api_key = os.getenv("CUSTOM_API_KEY")
            base_url = os.getenv("CUSTOM_BASE_URL")

        return ProviderConfig(
            provider=provider,
            model_name=model_name,
            temperature=0.0,
            api_key=api_key,
            base_url=base_url,
        )

    model_config = get_provider_details(llm_provider, llm_model)
    judge_config = get_provider_details(judge_provider, judge_model)

    return LabConfig(
        base_dir=root,
        data_dir=data_dir,
        state_dir=state_dir,
        compact_threshold_tokens=compact_threshold,
        compact_keep_messages=compact_keep,
        model=model_config,
        judge_model=judge_config,
    )

