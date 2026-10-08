"""Run with ``python -m tests.manual.desktop_smoke`` on a desktop with Tk."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from types import SimpleNamespace
from unittest.mock import patch

from desktop.app import CopyAgentWindow


class DelayedAgent:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.calls = 0
        self.fail = False

    def generate(self, request):
        self.calls += 1
        self.started.set()
        assert request.product.name == "保温杯"
        assert self.release.wait(3), "fake generation was not released"
        if self.fail:
            raise ValueError("测试失败")
        return SimpleNamespace(
            text="保温杯文案",
            warnings=["核实容量"],
            model="test-model",
            request_count=4,
            strategy=SimpleNamespace(
                facts=["容量 500 毫升"], audience_hypothesis="通勤者", purchase_motivation="随身饮水",
                key_message="便于携带", benefits=["小巧"], scenarios=["通勤"], objections=[],
                call_to_action="", assumptions=[], missing_information=["材质"], source_ids=["K1"],
            ),
            draft="初稿内容",
            review=SimpleNamespace(
                strengths=["场景明确"], issues=[SimpleNamespace(quote="原句", problem="笼统", suggestion="具体化")],
                factual_risks=["材质待核实"],
            ),
            sources=[SimpleNamespace(
                id="K1", title="本地写作资料", origin="curated", url="https://example.test/guide",
                summary="整理摘要", tags=["文案"], accessed_on="",
            )],
        )


def pump(root: tk.Tk, condition, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        root.update()
        if condition():
            return
        time.sleep(0.02)
    raise AssertionError("Timed out waiting for desktop state")


def fill(window: CopyAgentWindow) -> None:
    window.fields["name"].insert(0, "保温杯")
    window.model_fields["base_url"].insert(0, "https://example.test/v1")
    window.model_fields["api_key"].insert(0, "local-test-key")
    window.model_fields["model"].insert(0, "test-model")


def config_guidance_smoke() -> None:
    env_keys = ("COPY_AGENT_BASE_URL", "COPY_AGENT_API_KEY", "COPY_AGENT_MODEL")
    with patch.dict(os.environ, {key: "" for key in env_keys}):
        root = tk.Tk()
        root.withdraw()
        agent = DelayedAgent()
        window = CopyAgentWindow(root, agent_factory=lambda config: agent)
        window.fields["name"].insert(0, "保温杯")
        try:
            window.submit()
            hint = window.status_var.get()
            assert all(label in hint for label in ("API 地址", "模型", "API 密钥")), hint
            assert not agent.started.is_set()

            os.environ["COPY_AGENT_BASE_URL"] = "https://example.test/v1"
            os.environ["COPY_AGENT_API_KEY"] = "env-test-secret"
            os.environ["COPY_AGENT_MODEL"] = "test-model"
            window.submit()
            pump(root, agent.started.is_set)
            agent.release.set()
            pump(root, lambda: not window.generate_button.instate(["disabled"]))
            assert window.result_text.get("1.0", "end-1c") == "保温杯文案"

            window.model_fields["base_url"].insert(0, "bad-address")
            window.submit()
            hint = window.status_var.get()
            assert "API 地址" in hint and "http" in hint.lower(), hint
            assert "env-test-secret" not in hint
            assert all(widget.get("1.0", "end-1c") == "" for widget in window.artifact_texts.values())
            assert window.copy_button.instate(["disabled"])
        finally:
            window.close()


def main_smoke() -> None:
    root = tk.Tk()
    root.withdraw()
    destroyed = threading.Event()
    root.bind("<Destroy>", lambda event: destroyed.set() if event.widget is root else None)
    agent = DelayedAgent()
    window = CopyAgentWindow(root, agent_factory=lambda config: agent)
    fill(window)
    try:
        window.submit()
        pump(root, agent.started.is_set)
        assert window.generate_button.instate(["disabled"])
        assert window.copy_button.instate(["disabled"])
        window.submit()
        assert agent.calls == 1, "duplicate submit started another generation"
        agent.release.set()
        pump(root, lambda: not window.generate_button.instate(["disabled"]))
        assert window.result_text.get("1.0", "end-1c") == "保温杯文案"
        assert [window.result_tabs.tab(index, "text") for index in range(5)] == [
            "正文", "营销策略", "初稿", "审稿", "资料来源"
        ]
        assert "材质" in window.artifact_texts["营销策略"].get("1.0", "end-1c")
        assert window.artifact_texts["初稿"].get("1.0", "end-1c") == "初稿内容"
        assert "建议：具体化" in window.artifact_texts["审稿"].get("1.0", "end-1c")
        assert "本地整理" in window.artifact_texts["资料来源"].get("1.0", "end-1c")
        assert not window.copy_button.instate(["disabled"])
        assert "核实容量" in window.warning_text.get("1.0", "end-1c")
        window.copy_result()
        assert root.clipboard_get() == "保温杯文案"

        agent.started.clear()
        agent.release.clear()
        agent.fail = True
        window.submit()
        pump(root, agent.started.is_set)
        assert window.result_text.get("1.0", "end-1c") == ""
        assert all(widget.get("1.0", "end-1c") == "" for widget in window.artifact_texts.values())
        assert window.copy_button.instate(["disabled"])
        agent.release.set()
        pump(root, lambda: not window.generate_button.instate(["disabled"]))
        assert window.copy_button.instate(["disabled"])
        assert window.result_text.get("1.0", "end-1c") == ""
        assert all(widget.get("1.0", "end-1c") == "" for widget in window.artifact_texts.values())
        assert window.fields["name"].get() == "保温杯"
        assert "测试失败" in window.status_var.get()

        agent.started.clear()
        agent.release.clear()
        window.submit()
        pump(root, agent.started.is_set)
        window.close()
        agent.release.set()
        assert destroyed.is_set(), "root did not emit Destroy"
        assert window._results.get(timeout=3)[0] == "error"
        assert window._poll_id is None, "a Tk poll remained scheduled after close"
    finally:
        if not destroyed.is_set():
            window.close()


def blocked_child() -> None:
    root = tk.Tk()
    root.withdraw()
    started = threading.Event()
    release = threading.Event()

    class NeverFinishes:
        def generate(self, request):
            started.set()
            release.wait(30)

    window = CopyAgentWindow(root, agent_factory=lambda config: NeverFinishes())
    fill(window)
    window.submit()
    pump(root, started.is_set)
    window.close()
    root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--blocked-child":
        blocked_child()
    else:
        config_guidance_smoke()
        main_smoke()
        completed = subprocess.run(
            [sys.executable, "-m", "tests.manual.desktop_smoke", "--blocked-child"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert completed.returncode == 0, completed.stderr
        print("desktop smoke passed")
