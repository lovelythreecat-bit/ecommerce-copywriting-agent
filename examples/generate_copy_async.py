"""异步调用示例：适合已有 asyncio 事件循环的应用。"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from ecommerce_copy_agent import (
    CopyRequest,
    CopyRequirements,
    CopywritingAgent,
    FileImage,
    OpenAIChatAdapter,
    ProductInfo,
    load_model_config,
)


async def generate(config_path: Path, image_path: Path | None) -> None:
    if not config_path.is_file():
        raise ValueError(
            f"配置文件不存在：{config_path}。先复制 examples/model-config.example.json 并填入实际地址和模型名。"
        )
    if not os.environ.get("COPY_AGENT_API_KEY"):
        raise ValueError("缺少 COPY_AGENT_API_KEY 环境变量；未发送模型请求。")
    try:
        values = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取 JSON 配置：{exc}") from None
    if not isinstance(values, dict):
        raise ValueError("配置文件顶层必须是 JSON 对象。")
    config = load_model_config(values)
    if image_path and not config.supports_images:
        raise ValueError("图片示例要求启用 supports_images，并确认中转站和模型支持图片。")

    agent = CopywritingAgent(OpenAIChatAdapter(config))
    request = CopyRequest(
        product=ProductInfo(
            name="示例保温杯",
            category="日用品",
            description="容量 500 毫升；不提供未核实的保温时长。",
            selling_points=["可重复使用", "杯盖可拆洗"],
        ),
        requirements=CopyRequirements(
            copy_type="商品详情页短文案", platform="自有商城", max_chars=120
        ),
        images=[FileImage(path=image_path)] if image_path else [],
    )
    result = await agent.agenerate(request)
    print(result.model_dump_json(indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="异步生成一份电商文案")
    parser.add_argument("--config", type=Path, default=Path("model-config.json"))
    parser.add_argument("--image", type=Path, help="可选的本地商品图片")
    args = parser.parse_args()
    try:
        asyncio.run(generate(args.config, args.image))
    except ValueError as exc:
        parser.exit(2, f"{exc}\n")


if __name__ == "__main__":
    main()
