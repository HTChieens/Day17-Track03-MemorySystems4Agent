from __future__ import annotations

from pathlib import Path

from agent_advanced import AdvancedAgent
from agent_baseline import BaselineAgent
from config import load_config


def make_config(tmp_path: Path):
    """Student TODO: build an isolated config for tests."""
    from config import LabConfig
    from model_provider import ProviderConfig

    return LabConfig(
        base_dir=tmp_path,
        data_dir=tmp_path / "data",
        state_dir=tmp_path / "state",
        compact_threshold_tokens=50,  # low threshold to trigger compaction quickly
        compact_keep_messages=2,  # keep only 2 messages
        model=ProviderConfig(
            provider="openai",
            model_name="gpt-4o-mini",
            temperature=0.0,
            api_key=None,
            base_url=None,
        ),
        judge_model=ProviderConfig(
            provider="openai",
            model_name="gpt-4o-mini",
            temperature=0.0,
            api_key=None,
            base_url=None,
        ),
    )


def test_user_markdown_read_write_edit(tmp_path: Path) -> None:
    """Student TODO: verify `User.md` can be created, updated, and edited."""
    config = make_config(tmp_path)
    from memory_store import UserProfileStore

    store = UserProfileStore(config.state_dir / "profiles")
    user_id = "test_user"

    # Write and read
    content = "# User Profile\n- name: Alice\n"
    path = store.write_text(user_id, content)
    assert path.exists()
    assert store.read_text(user_id) == content
    assert store.file_size(user_id) > 0

    # Edit
    success = store.edit_text(user_id, "Alice", "Bob")
    assert success
    assert "Bob" in store.read_text(user_id)
    assert "Alice" not in store.read_text(user_id)

    # Missing user
    assert store.read_text("missing") == ""
    assert store.file_size("missing") == 0


def test_compact_trigger(tmp_path: Path) -> None:
    """Student TODO: verify long threads trigger compaction."""
    config = make_config(tmp_path)
    from memory_store import CompactMemoryManager

    manager = CompactMemoryManager(
        threshold_tokens=config.compact_threshold_tokens,
        keep_messages=config.compact_keep_messages,
    )
    thread_id = "test_thread"

    # A long message: ~100 characters (~25 tokens)
    long_msg = "This is a long message to exceed the compaction threshold and verify compaction logic."

    # First message (~25 tokens)
    manager.append(thread_id, "user", long_msg)
    assert manager.compaction_count(thread_id) == 0

    # Second message (total ~50 tokens, len is 2, not > keep_messages)
    manager.append(thread_id, "assistant", long_msg)
    assert manager.compaction_count(thread_id) == 0

    # Third message (total ~75 tokens, len is 3 > 2) -> should compact!
    manager.append(thread_id, "user", long_msg)
    assert manager.compaction_count(thread_id) > 0

    ctx = manager.context(thread_id)
    assert ctx["summary"] != ""
    assert len(ctx["messages"]) == config.compact_keep_messages


def test_cross_session_recall(tmp_path: Path) -> None:
    """Student TODO: verify advanced remembers across sessions and baseline does not."""
    config = make_config(tmp_path)

    baseline = BaselineAgent(config, force_offline=True)
    advanced = AdvancedAgent(config, force_offline=True)

    user_id = "test_user_recall"
    thread_1 = "thread_1"
    thread_2 = "thread_2"

    intro = "Chào bạn, mình tên là Alice. Mình đang ở Huế."
    baseline.reply(user_id, thread_1, intro)
    advanced.reply(user_id, thread_1, intro)

    query = "Nhắc lại tên mình và nơi ở hiện tại."
    res_baseline = baseline.reply(user_id, thread_2, query)
    res_advanced = advanced.reply(user_id, thread_2, query)

    # Baseline forgets
    assert "Alice" not in res_baseline["content"]
    assert "Huế" not in res_baseline["content"]

    # Advanced recalls
    assert "Alice" in res_advanced["content"]
    assert "Huế" in res_advanced["content"]


def test_compact_reduces_prompt_load_on_long_thread(tmp_path: Path) -> None:
    """Student TODO: compare prompt load of baseline vs advanced on a long thread."""
    config = make_config(tmp_path)

    baseline = BaselineAgent(config, force_offline=True)
    advanced = AdvancedAgent(config, force_offline=True)

    user_id = "test_user_load"
    thread_id = "long_thread"

    long_msg = "This is a long message to exceed the compaction threshold and verify compaction logic."

    # Send 5 messages
    for _ in range(5):
        baseline.reply(user_id, thread_id, long_msg)
        advanced.reply(user_id, thread_id, long_msg)

    assert advanced.compaction_count(thread_id) > 0

