from mclaw.agent.builtin_memory_provider import BuiltinMemoryProvider
from mclaw.tools.toolsets import resolve_toolset


class _RecordingMemoryStore:
    def __init__(self) -> None:
        self.prefetch_queries: list[str] = []

    def prefetch(self, query: str) -> str:
        self.prefetch_queries.append(query)
        return "unexpected memory"


def test_robot_control_toolset_exposes_only_terminal() -> None:
    assert resolve_toolset("robot-control") == ["terminal"]


def test_fully_disabled_memory_does_not_prefetch_context() -> None:
    store = _RecordingMemoryStore()
    provider = BuiltinMemoryProvider(
        memory_store=store,
        memory_enabled=False,
        user_profile_enabled=False,
    )

    assert provider.prefetch("check battery", session_id="robot-session") == ""
    assert store.prefetch_queries == []
