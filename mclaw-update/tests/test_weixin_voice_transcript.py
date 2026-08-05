import asyncio
from types import SimpleNamespace

from mclaw.channels.weixin.adapter import _extract_text, _media_items_needing_cache
from mclaw.channels.weixin.media import ITEM_IMAGE, ITEM_VOICE
from mclaw.channels.base import AgentTurnResult


def test_transcribed_voice_uses_weixin_text_without_caching_audio() -> None:
    voice = {
        "type": ITEM_VOICE,
        "voice_item": {
            "text": "然后你能不能给我拍照？",
            "media": {"encrypt_query_param": "voice-media"},
        },
    }

    assert _extract_text([voice]) == "然后你能不能给我拍照？"
    assert _media_items_needing_cache([voice]) == []


def test_transcribed_voice_filter_preserves_other_media() -> None:
    voice = {
        "type": ITEM_VOICE,
        "voice_item": {
            "text": "看一下这个",
            "media": {"encrypt_query_param": "voice-media"},
        },
    }
    image = {
        "type": ITEM_IMAGE,
        "image_item": {"media": {"encrypt_query_param": "image-media"}},
    }

    assert _media_items_needing_cache([voice, image]) == [image]


def test_untranscribed_voice_keeps_existing_audio_fallback() -> None:
    voice = {
        "type": ITEM_VOICE,
        "voice_item": {"media": {"encrypt_query_param": "voice-media"}},
    }

    assert _media_items_needing_cache([voice]) == [voice]


def test_adapter_sends_transcribed_voice_as_plain_text(monkeypatch) -> None:
    from mclaw.channels.weixin import adapter as adapter_module
    from mclaw.channels.weixin.adapter import WeixinAdapter

    delivered = []
    media_collect_calls = []
    adapter = WeixinAdapter.__new__(WeixinAdapter)
    adapter.config = SimpleNamespace(account_id="account", media_cache_enabled=True)
    adapter.dedup = SimpleNamespace(
        is_duplicate=lambda _key: False,
        content_key=lambda *_args: "content-key",
    )
    adapter.token_store = SimpleNamespace(set=lambda *_args: None)
    adapter.is_dm_allowed = lambda _sender_id: True

    async def no_typing_ticket(*_args, **_kwargs):
        return None

    async def no_schedule_bind(**_kwargs):
        return None

    async def no_typing(*_args, **_kwargs):
        return None

    async def collect(*_args, **_kwargs):
        media_collect_calls.append((_args, _kwargs))
        return []

    async def handle_message(**kwargs):
        delivered.append(kwargs["message"])
        return AgentTurnResult(session_id=kwargs["session_id"], final_response="ok")

    adapter._maybe_fetch_typing_ticket = no_typing_ticket
    adapter._maybe_handle_schedule_bind = no_schedule_bind
    adapter.send_typing = no_typing
    adapter.stop_typing = no_typing
    adapter.media_cache = SimpleNamespace(collect=collect)
    adapter.command_router = SimpleNamespace(
        handle=lambda *_args, **_kwargs: SimpleNamespace(handled=False)
    )
    adapter.runner = SimpleNamespace(
        startup_provider_runtime=SimpleNamespace(model="test-model"),
        get_status=lambda _session_id: "idle",
        session_db=SimpleNamespace(get_messages_as_conversation=lambda _session_id: []),
        handle_message=handle_message,
    )
    adapter.session_router = SimpleNamespace(
        route=lambda *_args, **_kwargs: SimpleNamespace(session_id="session-1")
    )
    monkeypatch.setattr(adapter_module, "register_weixin_outbound_target", lambda **_kwargs: None)

    result = asyncio.run(
        adapter.process_message(
            {
                "from_user_id": "user-1",
                "message_id": "message-1",
                "item_list": [
                    {
                        "type": ITEM_VOICE,
                        "voice_item": {
                            "text": "然后你能不能给我拍照？",
                            "media": {"encrypt_query_param": "voice-media"},
                        },
                    }
                ],
            }
        )
    )

    assert result is not None
    assert result.final_response == "ok"
    assert media_collect_calls == []
    assert len(delivered) == 1
    assert delivered[0].text == "然后你能不能给我拍照？"
    assert "Weixin Attachments" not in delivered[0].text
