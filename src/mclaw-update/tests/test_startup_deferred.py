# Copyright © 2026 Shenzhen Kaihong Digital Industry Development Co., Ltd.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from types import SimpleNamespace

from prompt_toolkit.document import Document

from mclaw.cli.app import InteractiveChat
from mclaw.cli.slash_completer import SlashCompleter


def test_optional_startup_work_is_deferred_until_after_construction(
    monkeypatch,
    tmp_path,
) -> None:
    from mclaw import state
    from mclaw.cli import app
    from mclaw.tools import process_registry as process_registry_module

    events: list[str] = []

    class Registry:
        _last_scan = 0

        def refresh(self) -> None:
            events.append("skills")

    class Lock:
        def __init__(self, session_id: str):
            self.session_id = session_id

        def acquire(self) -> None:
            return None

        def release(self) -> None:
            return None

    class Pet:
        def start_if_enabled(self) -> bool:
            events.append("pet")
            return False

        def stop(self) -> None:
            return None

    monkeypatch.setattr(state, "DEFAULT_DB_PATH", tmp_path / "state.db")
    monkeypatch.setattr(app, "InteractiveSessionLock", Lock)
    monkeypatch.setattr(app, "get_skill_registry", Registry)
    monkeypatch.setattr(app.PetController, "from_config", lambda *_args, **_kwargs: Pet())
    monkeypatch.setattr(
        InteractiveChat,
        "_init_agent",
        lambda self: setattr(self, "agent", SimpleNamespace()),
    )
    monkeypatch.setattr(
        process_registry_module.process_registry,
        "recover_from_checkpoint",
        lambda: events.append("processes") or 0,
    )

    chat = InteractiveChat(
        provider_runtime=SimpleNamespace(),
        config={"_launch_cwd": str(tmp_path)},
    )
    try:
        assert events == ["pet"]

        chat._run_deferred_startup_tasks(force=True)
        chat._run_deferred_startup_tasks(force=True)

        assert events == ["pet", "processes"]
    finally:
        chat._release_session_lock()
        chat._session_db.close()


def test_skill_registry_loads_only_when_slash_completion_is_requested() -> None:
    class Registry:
        def __init__(self) -> None:
            self._last_scan = 0
            self.refresh_calls = 0

        def refresh(self) -> None:
            self.refresh_calls += 1
            self._last_scan = 1

        def list_skills(self) -> list:
            return []

    registry = Registry()
    completer = SlashCompleter(registry)

    assert registry.refresh_calls == 0

    list(completer.get_completions(Document("/"), SimpleNamespace()))
    list(completer.get_completions(Document("/help"), SimpleNamespace()))

    assert registry.refresh_calls == 1
