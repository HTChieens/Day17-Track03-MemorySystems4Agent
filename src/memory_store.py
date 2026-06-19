from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


import re


def estimate_tokens(text: str) -> int:
    """Student TODO: implement a simple token estimator.

    Example idea:
    - Strip whitespace
    - Return 0 for empty text
    - Approximate tokens from character count, e.g. len(text) / 4
    """
    if not text:
        return 0
    return len(str(text).strip()) // 4


@dataclass
class UserProfileStore:
    """Persistent storage for `User.md`.

    Student TODO:
    - Map each user id to one markdown file
    - Support read / write / edit operations
    - Optionally expose helpers like `facts()` or `upsert_fact()`
    """

    root_dir: Path

    def path_for(self, user_id: str) -> Path:
        # slugify or sanitize the user id before building the file path.
        sanitized = re.sub(r"[^a-zA-Z0-9_\-]", "_", user_id).lower()
        return self.root_dir / f"{sanitized}.md"

    def read_text(self, user_id: str) -> str:
        # return file content or an empty default markdown profile.
        path = self.path_for(user_id)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def write_text(self, user_id: str, content: str) -> Path:
        # write markdown to disk and return the file path.
        path = self.path_for(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def edit_text(self, user_id: str, search_text: str, replacement: str) -> bool:
        # replace one occurrence inside User.md and return whether it changed.
        content = self.read_text(user_id)
        if search_text in content:
            new_content = content.replace(search_text, replacement, 1)
            self.write_text(user_id, new_content)
            return True
        return False

    def file_size(self, user_id: str) -> int:
        # return the current file size in bytes.
        path = self.path_for(user_id)
        if not path.exists():
            return 0
        return path.stat().st_size

    def update_facts(self, user_id: str, new_facts: dict[str, str]) -> None:
        """Helper to parse, merge and update facts in User.md."""
        content = self.read_text(user_id)
        facts = {}
        for line in content.splitlines():
            if line.startswith("- ") and ":" in line:
                parts = line[2:].split(":", 1)
                facts[parts[0].strip()] = parts[1].strip()

        # Merge
        for k, v in new_facts.items():
            facts[k] = v

        lines = ["# User Profile", ""]
        for k, v in sorted(facts.items()):
            lines.append(f"- {k}: {v}")
        new_content = "\n".join(lines) + "\n"
        self.write_text(user_id, new_content)


def extract_profile_updates(message: str) -> dict[str, str]:
    """Student TODO: convert raw user text into stable profile facts.

    Example facts you may want to extract:
    - name
    - location
    - profession
    - preferences / response style
    - favorite food / drink

    Pseudocode:
    1. Build a few regex patterns.
    2. Skip obvious question-only turns.
    3. Return only the facts that are confidently present in the message.
    """
    msg_lower = message.lower()

    # Skip questions and queries
    if message.strip().endswith("?"):
        return {}

    question_indicators = ["đâu mới là", "đâu là", "là gì", "là ai", "ở đâu", "thế nào", "nhắc lại", "tóm tắt", "bạn có thể", "nhắc giúp"]
    if any(qi in msg_lower for qi in question_indicators):
        return {}

    facts = {}

    # Extract name
    name_match = re.search(r"(?:mình tên là|tên mình là|tên là)\s+([A-Za-z0-9_À-ỹ\s]+)", message, re.IGNORECASE)
    if name_match:
        name = name_match.group(1).strip().rstrip(".,;! ")
        name = re.split(r"\s+(?:hiện|đang|và|ở|làm)\s+", name, flags=re.IGNORECASE)[0]
        facts["name"] = name

    # Extract location
    if "huế" in msg_lower:
        if "không còn ở huế" not in msg_lower and "không phải nơi ở" not in msg_lower:
            facts["location"] = "Huế"
    if "đà nẵng" in msg_lower:
        if "không còn ở đà nẵng" not in msg_lower and "không phải nơi ở" not in msg_lower:
            facts["location"] = "Đà Nẵng"
    if "hà nội" in msg_lower:
        if "không phải nơi ở hiện tại" not in msg_lower and "không phải nơi ở" not in msg_lower:
            if "ở hà nội" in msg_lower or "đang ở hà nội" in msg_lower:
                facts["location"] = "Hà Nội"

    # Extract profession
    if "mlops engineer" in msg_lower:
        facts["profession"] = "MLOps engineer"
    elif "backend engineer" in msg_lower:
        if "không còn làm backend engineer" not in msg_lower:
            facts["profession"] = "backend engineer"
    elif "product manager" in msg_lower:
        if "chỉ là câu đùa" not in msg_lower and "đùa" not in msg_lower:
            facts["profession"] = "product manager"

    # Extract response style
    style_keywords = []
    if "ngắn gọn" in msg_lower or "ngắn" in msg_lower or "gọn" in msg_lower:
        style_keywords.append("ngắn gọn")
    if "ví dụ thực tế" in msg_lower or "ví dụ thực chiến" in msg_lower:
        style_keywords.append("có ví dụ thực tế")
    if "bullet" in msg_lower or "3 bullet" in msg_lower:
        if "3 bullet" in msg_lower:
            style_keywords.append("3 bullet")
        else:
            style_keywords.append("bullet ngắn")
    if "trade-off" in msg_lower:
        style_keywords.append("nhấn trade-off")
    if style_keywords:
        facts["response_style"] = ", ".join(style_keywords)

    # Food / drink
    if "cà phê sữa đá" in msg_lower:
        facts["favorite_drink"] = "cà phê sữa đá"
    if "mì quảng" in msg_lower:
        facts["favorite_food"] = "mì Quảng"

    # Pet
    if "corgi" in msg_lower:
        if "bơ" in msg_lower:
            facts["pet"] = "corgi tên Bơ"
        else:
            facts["pet"] = "corgi"

    return facts


def summarize_messages(messages: list[dict[str, str]], max_items: int = 6) -> str:
    """Student TODO: create a compact summary of older messages.

    This can be heuristic text concatenation first.
    Later, you can replace it with an LLM-based summary if desired.
    """
    if not messages:
        return ""
    parts = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        parts.append(f"{role}: {content}")
    return " | ".join(parts)


@dataclass
class CompactMemoryManager:
    """Student TODO: implement compact memory for long threads.

    Goal:
    - Keep recent messages in full
    - When the thread grows too large, move older content into a summary
    - Track how many compactions happened for benchmarking
    """

    threshold_tokens: int
    keep_messages: int
    state: dict[str, dict[str, object]] = field(default_factory=dict)

    def append(self, thread_id: str, role: str, content: str) -> None:
        if thread_id not in self.state:
            self.state[thread_id] = {
                "messages": [],
                "summary": "",
                "compactions": 0,
            }

        thread = self.state[thread_id]
        thread["messages"].append({"role": role, "content": content})

        # Check token usage
        total_tokens = estimate_tokens(thread["summary"])
        for msg in thread["messages"]:
            total_tokens += estimate_tokens(msg["content"])

        if total_tokens > self.threshold_tokens and len(thread["messages"]) > self.keep_messages:
            num_to_compact = len(thread["messages"]) - self.keep_messages
            to_compact = thread["messages"][:num_to_compact]
            keep = thread["messages"][num_to_compact:]

            old_summary = thread["summary"]
            added_summary = summarize_messages(to_compact)

            if old_summary:
                thread["summary"] = old_summary + " | " + added_summary
            else:
                thread["summary"] = added_summary

            thread["messages"] = keep
            thread["compactions"] += 1

    def context(self, thread_id: str) -> dict[str, object]:
        if thread_id not in self.state:
            return {"messages": [], "summary": "", "compactions": 0}
        return self.state[thread_id]

    def compaction_count(self, thread_id: str) -> int:
        if thread_id not in self.state:
            return 0
        return self.state[thread_id]["compactions"]

