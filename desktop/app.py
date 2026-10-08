"""A small Tkinter client for trying the public agent API."""

from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Callable

from ecommerce_copy_agent.agent import CopywritingAgent
from ecommerce_copy_agent.adapters.openai_chat import OpenAIChatAdapter
from ecommerce_copy_agent.config import ModelConfig, load_model_config
from ecommerce_copy_agent.errors import AgentError, ConfigurationError

from .forms import build_request
from .presentation import format_review, format_sources, format_strategy


def _default_agent(config: ModelConfig) -> CopywritingAgent:
    return CopywritingAgent(model=OpenAIChatAdapter(config))


def _generate_in_background(agent: CopywritingAgent, request, results: queue.Queue) -> None:
    try:
        results.put(("success", agent.generate(request)))
    except Exception as error:
        results.put(("error", error))


class CopyAgentWindow:
    def __init__(
        self,
        root: tk.Tk,
        *,
        agent_factory: Callable[[ModelConfig], CopywritingAgent] | None = None,
    ) -> None:
        self.root = root
        self.agent_factory = agent_factory or _default_agent
        self.image_paths: list[Path] = []
        self._results: queue.Queue = queue.Queue()
        self._poll_id: str | None = None
        self._closed = False
        self._busy = False
        self.fields: dict[str, ttk.Entry] = {}
        self.model_fields: dict[str, ttk.Entry] = {}
        self.status_var = tk.StringVar(value="填写商品与模型信息后生成文案。")
        self.supports_images = tk.BooleanVar(value=False)
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _build_ui(self) -> None:
        self._configure_theme()
        self.root.title("电商文案 Agent 测试工具")
        self.root.geometry("960x760")
        self.root.minsize(700, 600)
        outer = ttk.Frame(self.root, padding=12, style="Workspace.TFrame")
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=3, uniform="panels")
        outer.columnconfigure(1, weight=2, uniform="panels")
        outer.rowconfigure(1, weight=3, minsize=266)
        outer.rowconfigure(2, weight=2)
        header = ttk.Frame(outer, style="Workspace.TFrame")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        ttk.Label(header, text="电商文案工作台", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="填写商品信息与写作要求，查看生成文案及过程资料。", style="Subtitle.TLabel").pack(anchor="w", pady=(2, 0))

        input_holder = ttk.LabelFrame(outer, text="商品与写作要求", padding=10)
        input_holder.grid(row=1, column=0, sticky="nsew", padx=(0, 12), pady=(0, 12))
        input_holder.columnconfigure(0, weight=1)
        input_holder.rowconfigure(0, weight=1)
        input_canvas = tk.Canvas(input_holder, width=1, height=180,
                                 background=self._colors["panel"], highlightthickness=0)
        input_canvas.grid(row=0, column=0, sticky="nsew")
        input_scroll = ttk.Scrollbar(input_holder, orient="vertical", command=input_canvas.yview)
        input_scroll.grid(row=0, column=1, sticky="ns")
        input_canvas.configure(yscrollcommand=input_scroll.set)
        input_box = ttk.Frame(input_canvas, padding=(2, 2, 6, 2))
        input_window = input_canvas.create_window((0, 0), window=input_box, anchor="nw")
        input_box.bind(
            "<Configure>",
            lambda event: input_canvas.configure(scrollregion=input_canvas.bbox("all")),
        )
        input_canvas.bind(
            "<Configure>",
            lambda event: input_canvas.itemconfigure(input_window, width=event.width),
        )
        input_box.columnconfigure(1, weight=1)
        ttk.Label(input_box, text="商品信息", style="Section.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        for row, (key, label) in enumerate(
            [("name", "商品名称 *"), ("category", "品类"), ("brand", "品牌")]
        ):
            self._entry(input_box, row + 1, key, label, self.fields)
        self._text_field(input_box, 4, "商品属性 JSON", "attributes_json", height=3)
        self._text_field(input_box, 5, "补充描述", "description", height=3)
        ttk.Label(input_box, text="图片（最多 4 张）").grid(row=6, column=0, sticky="nw", pady=4)
        image_frame = ttk.Frame(input_box)
        image_frame.grid(row=6, column=1, sticky="nsew", pady=4)
        image_frame.columnconfigure(0, weight=1)
        image_frame.rowconfigure(0, weight=1)
        self.image_list = tk.Listbox(image_frame, height=2, width=1, exportselection=False,
                                    font=self._body_font, background=self._colors["panel"],
                                    foreground=self._colors["text"], selectbackground=self._colors["accent"],
                                    selectforeground="white", relief="flat", borderwidth=0,
                                    highlightthickness=1, highlightbackground=self._colors["border"],
                                    highlightcolor=self._colors["accent"])
        self.image_list.grid(row=0, column=0, sticky="nsew")
        image_scroll = ttk.Scrollbar(image_frame, orient="vertical", command=self.image_list.yview)
        image_scroll.grid(row=0, column=1, sticky="ns")
        self.image_list.configure(yscrollcommand=image_scroll.set)
        image_actions = ttk.Frame(image_frame)
        image_actions.grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Button(image_actions, text="添加图片", command=self.add_images).pack(side="left")
        ttk.Button(image_actions, text="移除所选", command=self.remove_image).pack(side="left", padx=6)

        ttk.Label(input_box, text="写作要求", style="Section.TLabel").grid(row=7, column=0, columnspan=2, sticky="w", pady=(12, 6))
        self._combobox(input_box, 8, "copy_type", "文案类型", ["宣传文案", "商品标题", "卖点描述", "详情介绍", "社交平台文案"])
        self._entry(input_box, 9, "platform", "目标平台", self.fields)
        self._entry(input_box, 10, "audience", "目标人群", self.fields)
        self._entry(input_box, 11, "tone", "语气", self.fields, default="自然")
        self._entry(input_box, 12, "max_chars", "最大字符数", self.fields)
        self._text_field(input_box, 13, "额外写作要求", "extra_instructions", height=3)

        model_box = ttk.LabelFrame(outer, text="模型连接", padding=10)
        model_box.grid(row=1, column=1, sticky="nsew", pady=(0, 12))
        model_box.columnconfigure(1, weight=1)
        self._entry(model_box, 0, "base_url", "API 地址", self.model_fields)
        self._entry(model_box, 1, "model", "模型", self.model_fields)
        self._entry(model_box, 2, "api_key", "API 密钥", self.model_fields, show="•")
        ttk.Checkbutton(model_box, text="模型支持图片", variable=self.supports_images).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=4
        )
        self.model_hint = ttk.Label(model_box, text="地址填写 API 根路径，如 https://example.com/v1。", style="Muted.TLabel", width=1)
        self.model_hint.grid(row=4, column=0, columnspan=2, sticky="ew")
        model_box.bind("<Configure>", lambda event: self.model_hint.configure(wraplength=max(120, event.width - 24)))
        self.generate_button = ttk.Button(model_box, text="生成文案", command=self.submit, style="Primary.TButton")
        self.generate_button.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(10, 4))

        output_box = ttk.LabelFrame(outer, text="生成结果", padding=10)
        output_box.grid(row=2, column=0, columnspan=2, sticky="nsew")
        output_box.columnconfigure(0, weight=1)
        output_box.rowconfigure(1, weight=1)
        self.status_label = ttk.Label(output_box, textvariable=self.status_var, style="Muted.TLabel", width=1)
        self.status_label.grid(row=0, column=0, sticky="ew")
        output_box.bind("<Configure>", lambda event: self.status_label.configure(wraplength=max(160, event.width - 24)))
        self.result_tabs = ttk.Notebook(output_box)
        self.result_tabs.grid(row=1, column=0, sticky="nsew", pady=(6, 4))
        self.artifact_texts: dict[str, tk.Text] = {}
        for name in ("正文", "营销策略", "初稿", "审稿", "资料来源"):
            page = ttk.Frame(self.result_tabs, padding=2)
            page.rowconfigure(0, weight=1)
            page.columnconfigure(0, weight=1)
            widget = self._scrolling_text(page, height=4)
            widget.grid(row=0, column=0, sticky="nsew")
            widget.configure(state="disabled")
            self.artifact_texts[name] = widget
            self.result_tabs.add(page, text=name)
        self.result_text = self.artifact_texts["正文"]
        footer = ttk.Frame(output_box)
        footer.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        footer.columnconfigure(1, weight=1)
        ttk.Label(footer, text="提示", style="Muted.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.warning_text = self._scrolling_text(footer, height=1)
        self.warning_text.grid(row=0, column=1, sticky="ew")
        self.warning_text.configure(state="disabled", background=self._colors["hint"])
        self.copy_button = ttk.Button(footer, text="复制文案", command=self.copy_result, state="disabled")
        self.copy_button.grid(row=0, column=2, sticky="e", padx=(8, 0))

    def _entry(self, parent, row: int, key: str, label: str, target: dict, *, default: str = "", show: str = "") -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)
        entry = ttk.Entry(parent, show=show, width=1)
        entry.grid(row=row, column=1, sticky="ew", pady=3)
        if default:
            entry.insert(0, default)
        target[key] = entry

    def _combobox(self, parent, row: int, key: str, label: str, choices: list[str]) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)
        combo = ttk.Combobox(parent, values=choices, state="normal", width=1)
        combo.set(choices[0])
        combo.grid(row=row, column=1, sticky="ew", pady=3)
        self.fields[key] = combo

    def _text_field(self, parent, row: int, label: str, key: str, *, height: int) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="nw", padx=(0, 8), pady=3)
        widget = self._scrolling_text(parent, height=height)
        widget.grid(row=row, column=1, sticky="nsew", pady=3)
        setattr(self, f"{key}_text", widget)

    def _scrolling_text(self, parent, *, height: int) -> tk.Text:
        widget = ScrolledText(parent, height=height, width=1, wrap="word", undo=True,
                              font=self._body_font, background=self._colors["panel"],
                              foreground=self._colors["text"], insertbackground=self._colors["text"],
                              selectbackground=self._colors["accent"], selectforeground="white",
                              relief="flat", borderwidth=0, highlightthickness=1,
                              highlightbackground=self._colors["border"], highlightcolor=self._colors["accent"],
                              padx=8, pady=5, spacing1=0, spacing3=2)
        widget.frame.configure(background=self._colors["panel"])
        return widget

    def _configure_theme(self) -> None:
        self._colors = {"workspace": "#f2f5fa", "panel": "#ffffff", "text": "#24334a",
                        "muted": "#53647b", "border": "#c9d3e1", "accent": "#245fc0", "hint": "#fff9ed"}
        colors = self._colors
        self._body_font = font.nametofont("TkDefaultFont").copy()
        self._title_font = self._body_font.copy()
        size = self._body_font.cget("size")
        self._title_font.configure(size=size + 3 if size > 0 else size - 3, weight="bold")
        self._section_font = self._body_font.copy()
        self._section_font.configure(weight="bold")
        self.root.configure(background=colors["workspace"])
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", font=self._body_font, background=colors["panel"], foreground=colors["text"])
        style.configure("Workspace.TFrame", background=colors["workspace"])
        style.configure("Title.TLabel", background=colors["workspace"], font=self._title_font)
        style.configure("Subtitle.TLabel", background=colors["workspace"], foreground=colors["muted"])
        style.configure("Muted.TLabel", foreground=colors["muted"])
        style.configure("Section.TLabel", font=self._section_font)
        style.configure("TLabelframe", bordercolor=colors["border"], relief="solid", borderwidth=1)
        style.configure("TLabelframe.Label", font=self._section_font)
        for name in ("TEntry", "TCombobox"):
            style.configure(name, fieldbackground=colors["panel"], bordercolor=colors["border"], padding=3)
            style.map(name, bordercolor=[("focus", colors["accent"])])
        style.configure("TButton", padding=(10, 4), bordercolor=colors["border"], focusthickness=2,
                        focuscolor=colors["accent"])
        style.configure("Primary.TButton", background=colors["accent"], foreground="white",
                        bordercolor=colors["accent"], focuscolor="white", font=self._section_font)
        style.map("Primary.TButton", background=[("disabled", "#e1e7f0"), ("pressed", "#18468f"), ("active", "#1c51a6")],
                  foreground=[("disabled", "#66758a")], bordercolor=[("disabled", colors["border"]), ("focus", "#123975")])
        style.configure("TNotebook", background=colors["panel"], bordercolor=colors["border"])
        style.configure("TNotebook.Tab", padding=(12, 6), background=colors["workspace"])
        style.map("TNotebook.Tab", background=[("selected", colors["panel"])], foreground=[("selected", colors["accent"])])

    def add_images(self) -> None:
        chosen = filedialog.askopenfilenames(
            parent=self.root,
            title="选择商品图片",
            filetypes=[("图片", "*.jpg *.jpeg *.png *.webp"), ("所有文件", "*.*")],
        )
        for path in chosen:
            candidate = Path(path)
            if candidate not in self.image_paths:
                self.image_paths.append(candidate)
                self.image_list.insert("end", str(candidate))
        if len(self.image_paths) > 4:
            self.status_var.set("一次最多选择 4 张图片。")
            self.image_paths = self.image_paths[:4]
            self.image_list.delete(4, "end")

    def remove_image(self) -> None:
        selected = self.image_list.curselection()
        if selected:
            index = selected[0]
            self.image_list.delete(index)
            self.image_paths.pop(index)

    def _values(self) -> dict[str, str]:
        values = {key: entry.get() for key, entry in self.fields.items()}
        for key in ("attributes_json", "description", "extra_instructions"):
            values[key] = getattr(self, f"{key}_text").get("1.0", "end-1c")
        return values

    def _model_config(self) -> ModelConfig:
        values = {key: entry.get().strip() for key, entry in self.model_fields.items()}
        required = {
            "base_url": ("API 地址", "COPY_AGENT_BASE_URL"),
            "model": ("模型", "COPY_AGENT_MODEL"),
            "api_key": ("API 密钥", "COPY_AGENT_API_KEY"),
        }
        missing = [label for key, (label, env_name) in required.items() if not (values[key] or os.environ.get(env_name, "").strip())]
        if missing:
            raise ValueError(f"请填写{'、'.join(missing)}，或设置对应的 COPY_AGENT 环境变量。")
        supplied = {key: value for key, value in values.items() if value}
        supplied["supports_images"] = self.supports_images.get()
        try:
            return load_model_config(supplied)
        except ConfigurationError:
            raise ValueError("模型配置无效：请检查 API 地址是否为 http/https 根路径、模型、API 密钥及相关环境变量。") from None

    @staticmethod
    def _set_text(widget: tk.Text, value: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    def submit(self) -> None:
        if self._closed or self._busy:
            return
        for widget in self.artifact_texts.values():
            self._set_text(widget, "")
        self._set_text(self.warning_text, "")
        self.result_tabs.select(0)
        self.copy_button.state(["disabled"])
        try:
            request = build_request(self._values(), list(self.image_paths))
            config = self._model_config()
            agent = self.agent_factory(config)
        except Exception as error:
            self.status_var.set(self._error_message(error))
            return
        self._busy = True
        self.generate_button.state(["disabled"])
        self.status_var.set("正在生成文案：流程包含资料检索、营销策略、初稿、审稿和定稿，请稍候。")
        threading.Thread(
            target=_generate_in_background,
            args=(agent, request, self._results),
            daemon=True,
        ).start()
        self._poll_id = self.root.after(50, self._poll)

    @staticmethod
    def _error_message(error: Exception) -> str:
        if isinstance(error, AgentError):
            return str(error)
        if isinstance(error, ValueError):
            return str(error)
        return "生成失败，请检查输入、模型配置和网络连接。"

    def _poll(self) -> None:
        self._poll_id = None
        if self._closed:
            return
        try:
            kind, payload = self._results.get_nowait()
        except queue.Empty:
            self._poll_id = self.root.after(50, self._poll)
            return
        self._busy = False
        self.generate_button.state(["!disabled"])
        if kind == "error":
            self.status_var.set(self._error_message(payload))
            return
        self._set_text(self.result_text, payload.text)
        self._set_text(self.artifact_texts["营销策略"], format_strategy(getattr(payload, "strategy", None)))
        self._set_text(self.artifact_texts["初稿"], getattr(payload, "draft", "") or "没有可显示的初稿。")
        self._set_text(self.artifact_texts["审稿"], format_review(getattr(payload, "review", None)))
        self._set_text(self.artifact_texts["资料来源"], format_sources(getattr(payload, "sources", [])))
        self._set_text(self.warning_text, "\n".join(payload.warnings))
        self.copy_button.state(["!disabled"])
        self.status_var.set(f"生成完成 · {payload.model} · 请求 {payload.request_count} 次")

    def copy_result(self) -> None:
        if self._closed or self._busy or self.copy_button.instate(["disabled"]):
            return
        text = self.result_text.get("1.0", "end-1c")
        if text:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.status_var.set("文案已复制到剪贴板。")

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._poll_id is not None:
            self.root.after_cancel(self._poll_id)
            self._poll_id = None
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    CopyAgentWindow(root)
    root.mainloop()
