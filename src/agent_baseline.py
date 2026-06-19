from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from config import LabConfig, load_config
from memory_store import estimate_tokens
from model_provider import build_chat_model


@dataclass
class SessionState:
    messages: list[dict[str, str]] = field(default_factory=list)
    token_usage: int = 0
    prompt_tokens_processed: int = 0


class BaselineAgent:
    """Student TODO: implement Agent A.

    Requirements:
    - Within-session memory only
    - No persistent `User.md`
    - Should forget long-term facts across new threads
    """

    def __init__(self, config: LabConfig | None = None, force_offline: bool = False) -> None:
        self.config = config or load_config()
        self.force_offline = force_offline
        self.sessions: dict[str, SessionState] = {}
        self.langchain_agent = None

    def reply(self, user_id: str, thread_id: str, message: str) -> dict[str, Any]:
        """Student TODO: return the agent response and token accounting.

        Pseudocode:
        - If a live agent exists, call the live path.
        - Otherwise use a deterministic offline path.
        """
        if self.force_offline or not self.config.model.api_key:
            return self._reply_offline(thread_id, message)

        try:
            if thread_id not in self.sessions:
                self.sessions[thread_id] = SessionState()
            session = self.sessions[thread_id]

            from langchain_core.messages import AIMessage, HumanMessage

            chat_history = []
            prompt_tokens = 0
            for msg in session.messages:
                prompt_tokens += estimate_tokens(msg["content"])
                if msg["role"] == "user":
                    chat_history.append(HumanMessage(content=msg["content"]))
                else:
                    chat_history.append(AIMessage(content=msg["content"]))

            # Add current message
            chat_history.append(HumanMessage(content=message))
            prompt_tokens += estimate_tokens(message)

            model = build_chat_model(self.config.model)
            response = model.invoke(chat_history)
            reply_content = response.content

            # Save state
            session.messages.append({"role": "user", "content": message})
            response_tokens = estimate_tokens(reply_content)
            session.token_usage += response_tokens
            session.prompt_tokens_processed += prompt_tokens

            session.messages.append({"role": "assistant", "content": reply_content})

            return {
                "content": reply_content,
                "tokens": response_tokens,
                "prompt_tokens": prompt_tokens,
            }
        except Exception:
            return self._reply_offline(thread_id, message)

    def token_usage(self, thread_id: str) -> int:
        if thread_id not in self.sessions:
            return 0
        return self.sessions[thread_id].token_usage

    def prompt_token_usage(self, thread_id: str) -> int:
        if thread_id not in self.sessions:
            return 0
        return self.sessions[thread_id].prompt_tokens_processed

    def compaction_count(self, thread_id: str) -> int:
        # Baseline has no compact memory.
        return 0

    def _reply_offline(self, thread_id: str, message: str) -> dict[str, Any]:
        """Student TODO: implement a simple offline behavior.

        Suggested behavior:
        - Store the new user message in the session
        - Generate a short deterministic reply
        - Update token counts
        - Never remember facts across different thread ids
        """
        if thread_id not in self.sessions:
            self.sessions[thread_id] = SessionState()
        session = self.sessions[thread_id]

        session.messages.append({"role": "user", "content": message})

        msg_lower = message.lower()
        reply_content = "Xin chào! Mình là Baseline Agent. Mình chỉ có bộ nhớ ngắn hạn trong phiên chat này."

        # simple recall within same thread
        if "tên" in msg_lower:
            name = None
            for m in session.messages:
                if m["role"] == "user":
                    from memory_store import extract_profile_updates

                    facts = extract_profile_updates(m["content"])
                    if "name" in facts:
                        name = facts["name"]
            if name:
                reply_content = f"Tên bạn là {name}."
            else:
                reply_content = "Mình chưa biết tên bạn."

        prompt_tokens = 0
        for m in session.messages:
            prompt_tokens += estimate_tokens(m["content"])

        response_tokens = estimate_tokens(reply_content)
        session.token_usage += response_tokens
        session.prompt_tokens_processed += prompt_tokens

        session.messages.append({"role": "assistant", "content": reply_content})

        return {
            "content": reply_content,
            "tokens": response_tokens,
            "prompt_tokens": prompt_tokens,
        }

    def _maybe_build_langchain_agent(self):
        """Student TODO: optionally wire `create_agent` + `InMemorySaver` here.

        Use `build_chat_model(self.config.model)` so the baseline can run with any supported provider.
        """
        pass

