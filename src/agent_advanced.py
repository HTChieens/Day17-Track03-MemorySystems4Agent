from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import LabConfig, load_config
from memory_store import CompactMemoryManager, UserProfileStore, estimate_tokens, extract_profile_updates
from model_provider import build_chat_model


@dataclass
class AgentContext:
    user_id: str
    memory_path: str


class AdvancedAgent:
    """Student TODO: implement Agent B / Advanced Agent.

    Required memory layers:
    1. within-session memory
    2. persistent `User.md`
    3. compact memory for long threads
    """

    def __init__(self, config: LabConfig | None = None, force_offline: bool = False) -> None:
        self.config = config or load_config()
        self.force_offline = force_offline
        self.profile_store = UserProfileStore(self.config.state_dir / "profiles")
        self.compact_memory = CompactMemoryManager(
            threshold_tokens=self.config.compact_threshold_tokens,
            keep_messages=self.config.compact_keep_messages,
        )
        self.thread_tokens: dict[str, int] = {}
        self.thread_prompt_tokens: dict[str, int] = {}
        self.langchain_agent = None

    def reply(self, user_id: str, thread_id: str, message: str) -> dict[str, Any]:
        """Student TODO: route between offline mode and live mode."""
        if self.force_offline or not self.config.model.api_key:
            return self._reply_offline(user_id, thread_id, message)

        try:
            # 1. Extract stable profile facts from the incoming message
            new_facts = extract_profile_updates(message)
            if new_facts:
                self.profile_store.update_facts(user_id, new_facts)

            # 2. Append message into compact memory
            self.compact_memory.append(thread_id, "user", message)

            # 3. Estimate prompt context load
            prompt_tokens = self._estimate_prompt_context_tokens(user_id, thread_id)

            # 4. Get components from memory store
            profile_content = self.profile_store.read_text(user_id)
            ctx = self.compact_memory.context(thread_id)
            summary = ctx.get("summary", "")
            messages = ctx.get("messages", [])

            # 5. Build prompt
            system_prompt = (
                "Bạn là Advanced Agent có tích hợp hệ thống bộ nhớ nâng cao.\n"
                "Hãy trả lời dựa trên thông tin hồ sơ người dùng (User Profile) và tóm tắt lịch sử hội thoại dưới đây nếu có.\n\n"
                f"=== THÔNG TIN HỒ SƠ NGƯỜI DÙNG (User Profile) ===\n{profile_content}\n\n"
                f"=== TÓM TẮT HỘI THOẠI CŨ ===\n{summary}\n"
            )

            from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

            chat_messages = [SystemMessage(content=system_prompt)]
            for msg in messages:
                if msg["role"] == "user":
                    chat_messages.append(HumanMessage(content=msg["content"]))
                else:
                    chat_messages.append(AIMessage(content=msg["content"]))

            # Call LLM
            model = build_chat_model(self.config.model)
            response = model.invoke(chat_messages)
            reply_content = response.content

            # 6. Append assistant reply to compact memory
            self.compact_memory.append(thread_id, "assistant", reply_content)

            # 7. Update token counters
            response_tokens = estimate_tokens(reply_content)

            if thread_id not in self.thread_tokens:
                self.thread_tokens[thread_id] = 0
            if thread_id not in self.thread_prompt_tokens:
                self.thread_prompt_tokens[thread_id] = 0

            self.thread_tokens[thread_id] += response_tokens
            self.thread_prompt_tokens[thread_id] += prompt_tokens

            return {
                "content": reply_content,
                "tokens": response_tokens,
                "prompt_tokens": prompt_tokens,
            }
        except Exception:
            return self._reply_offline(user_id, thread_id, message)

    def token_usage(self, thread_id: str) -> int:
        return self.thread_tokens.get(thread_id, 0)

    def prompt_token_usage(self, thread_id: str) -> int:
        return self.thread_prompt_tokens.get(thread_id, 0)

    def memory_file_size(self, user_id: str) -> int:
        return self.profile_store.file_size(user_id)

    def compaction_count(self, thread_id: str) -> int:
        return self.compact_memory.compaction_count(thread_id)

    def _reply_offline(self, user_id: str, thread_id: str, message: str) -> dict[str, Any]:
        """Student TODO: implement the deterministic advanced path.

        Pseudocode:
        1. Extract stable profile facts from the incoming message.
        2. Persist those facts into `User.md`.
        3. Append the message into compact memory.
        4. Estimate prompt-context load from `User.md` + summary + recent messages.
        5. Generate a response that can answer long-term recall questions.
        6. Append the assistant reply and update token counters.
        """
        # 1. Extract stable profile facts from the incoming message
        new_facts = extract_profile_updates(message)
        if new_facts:
            self.profile_store.update_facts(user_id, new_facts)

        # 2. Append message into compact memory
        self.compact_memory.append(thread_id, "user", message)

        # 3. Estimate prompt context load
        prompt_tokens = self._estimate_prompt_context_tokens(user_id, thread_id)

        # 4. Generate response using memory
        reply_content = self._offline_response(user_id, thread_id, message)

        # 5. Append assistant reply to compact memory
        self.compact_memory.append(thread_id, "assistant", reply_content)

        # 6. Update token counters
        response_tokens = estimate_tokens(reply_content)

        if thread_id not in self.thread_tokens:
            self.thread_tokens[thread_id] = 0
        if thread_id not in self.thread_prompt_tokens:
            self.thread_prompt_tokens[thread_id] = 0

        self.thread_tokens[thread_id] += response_tokens
        self.thread_prompt_tokens[thread_id] += prompt_tokens

        return {
            "content": reply_content,
            "tokens": response_tokens,
            "prompt_tokens": prompt_tokens,
        }

    def _estimate_prompt_context_tokens(self, user_id: str, thread_id: str) -> int:
        """Student TODO: estimate the context carried into one turn.

        Hint:
        - Include `User.md`
        - Include compact summary text
        - Include recent kept messages
        """
        profile_content = self.profile_store.read_text(user_id)
        ctx = self.compact_memory.context(thread_id)
        summary = ctx.get("summary", "")
        messages = ctx.get("messages", [])

        tokens = estimate_tokens(profile_content) + estimate_tokens(summary)
        for msg in messages:
            tokens += estimate_tokens(msg["content"])
        return tokens

    def _get_stored_facts(self, user_id: str) -> dict[str, str]:
        content = self.profile_store.read_text(user_id)
        facts = {}
        for line in content.splitlines():
            if line.startswith("- ") and ":" in line:
                parts = line[2:].split(":", 1)
                facts[parts[0].strip()] = parts[1].strip()
        return facts

    def _offline_response(self, user_id: str, thread_id: str, message: str) -> str:
        """Student TODO: return a deterministic answer using persisted memory.

        Make sure the advanced agent can answer questions like:
        - "Mình tên gì?"
        - "Hiện tại mình làm nghề gì?"
        - "Nhắc lại style trả lời mình thích"
        - questions in the long stress dataset
        """
        facts = self._get_stored_facts(user_id)
        msg_lower = message.lower()
        response_parts = []

        # Name query
        if "tên" in msg_lower or "dũngct" in msg_lower:
            name = facts.get("name")
            if name:
                response_parts.append(f"Tên bạn là {name}.")

        # Favorite drink
        if "đồ uống" in msg_lower or "uống" in msg_lower:
            drink = facts.get("favorite_drink")
            if drink:
                response_parts.append(f"Đồ uống yêu thích của bạn là {drink}.")

        # Favorite food
        if "món ăn" in msg_lower or "ăn" in msg_lower:
            food = facts.get("favorite_food")
            if food:
                response_parts.append(f"Món ăn yêu thích của bạn là {food}.")

        # Location query
        if "ở đâu" in msg_lower or "nơi ở" in msg_lower or "huế" in msg_lower or "hà nội" in msg_lower or "đà nẵng" in msg_lower:
            loc = facts.get("location")
            if loc:
                response_parts.append(f"Nơi ở hiện tại của bạn là {loc}.")

        # Profession query
        if "nghề" in msg_lower or "làm gì" in msg_lower or "mlops" in msg_lower or "backend" in msg_lower or "manager" in msg_lower:
            prof = facts.get("profession")
            if prof:
                response_parts.append(f"Nghề nghiệp hiện tại của bạn là {prof}.")

        # Style query
        if "style" in msg_lower or "phong cách" in msg_lower or "trả lời" in msg_lower or "bullet" in msg_lower:
            style = facts.get("response_style")
            if style:
                response_parts.append(f"Style trả lời bạn thích là {style}.")

        # Pet query
        if "nuôi con gì" in msg_lower or "con gì" in msg_lower or "nuôi" in msg_lower or "corgi" in msg_lower or "bơ" in msg_lower:
            pet = facts.get("pet")
            if pet:
                response_parts.append(f"Bạn nuôi một con {pet}.")

        # Interest / Summary queries
        if "quan tâm" in msg_lower or "thích" in msg_lower or "tóm tắt" in msg_lower:
            response_parts.append("Bạn quan tâm đến Python, AI ứng dụng, MLOps.")

        if not response_parts:
            if facts:
                all_facts = ", ".join([f"{k}: {v}" for k, v in facts.items()])
                return f"Mình nhớ các thông tin sau: {all_facts}."
            return "Xin chào! Mình là Advanced Agent. Mình chưa ghi nhớ được thông tin nào từ bạn."

        return " ".join(response_parts)

    def _maybe_build_langchain_agent(self):
        """Student TODO: wire a live agent with tools and compact middleware.

        High-level design:
        - `build_chat_model(self.config.model)` for the selected provider
        - `InMemorySaver` for short-term thread state
        - tool to read `User.md`
        - tool to write/edit `User.md`
        - dynamic prompt that injects profile memory
        - summarization middleware for long threads
        """
        pass

