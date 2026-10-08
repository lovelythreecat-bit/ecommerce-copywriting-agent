"""Example entry points use the effective model configuration without network calls."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from examples import generate_copy, generate_copy_async


@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("explicit_vision", [None, False])
def test_image_example_respects_effective_vision_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], mode: str, explicit_vision: bool | None
) -> None:
    values: dict[str, object] = {
        "provider": "openai_chat",
        "base_url": "https://relay.example.com/v1",
        "model": "test-model",
    }
    if explicit_vision is not None:
        values["supports_images"] = explicit_vision
    config_path = tmp_path / "model-config.json"
    config_path.write_text(json.dumps(values), encoding="utf-8")
    image_path = tmp_path / "product.png"
    image_path.write_bytes(b"fake-image-used-only-by-stub")
    monkeypatch.setenv("COPY_AGENT_API_KEY", "local-test-sentinel")
    monkeypatch.setenv("COPY_AGENT_SUPPORTS_IMAGES", "true")

    seen: list[tuple[object, object]] = []

    class FakeAdapter:
        def __init__(self, config: object) -> None:
            self.config = config

    class FakeAgent:
        def __init__(self, adapter: FakeAdapter) -> None:
            self.adapter = adapter

        def generate(self, request: object) -> object:
            seen.append((self.adapter.config, request))
            return SimpleNamespace(model_dump_json=lambda **_: '{"text":"stub"}')

        async def agenerate(self, request: object) -> object:
            return self.generate(request)

    module = generate_copy if mode == "sync" else generate_copy_async
    monkeypatch.setattr(module, "OpenAIChatAdapter", FakeAdapter)
    monkeypatch.setattr(module, "CopywritingAgent", FakeAgent)

    if explicit_vision is False:
        with pytest.raises((SystemExit, ValueError)) as error:
            if mode == "sync":
                monkeypatch.setattr("sys.argv", ["generate_copy.py", "--config", str(config_path), "--image", str(image_path)])
                generate_copy.main()
            else:
                asyncio.run(generate_copy_async.generate(config_path, image_path))
        assert "supports_images" in str(error.value) or "supports_images" in capsys.readouterr().err
        assert not seen
    else:
        if mode == "sync":
            monkeypatch.setattr("sys.argv", ["generate_copy.py", "--config", str(config_path), "--image", str(image_path)])
            generate_copy.main()
        else:
            asyncio.run(generate_copy_async.generate(config_path, image_path))
        assert len(seen) == 1
        config, request = seen[0]
        assert config.supports_images is True
        assert len(request.images) == 1
        assert request.images[0].path == image_path
        assert '"text":"stub"' in capsys.readouterr().out
