"""同步调用示例：从本地 JSON 读取非敏感设置，从环境读取密钥。"""

from __future__ import annotations

import argparse
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


def main() -> None:
    parser = argparse.ArgumentParser(description="生成一份电商文案")
    parser.add_argument("--config", type=Path, default=Path("model-config.json"))
    parser.add_argument("--image", type=Path, help="可选的本地商品图片")
    args = parser.parse_args()

    if not args.config.is_file():
        parser.exit(2, f"配置文件不存在：{args.config}\n先复制 examples/model-config.example.json 并填入实际地址和模型名。\n")
    if not os.environ.get("COPY_AGENT_API_KEY"):
        parser.exit(2, "缺少 COPY_AGENT_API_KEY 环境变量；未发送模型请求。\n")

    try:
        values = json.loads(args.config.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        parser.exit(2, f"无法读取 JSON 配置：{exc}\n")
    if not isinstance(values, dict):
        parser.exit(2, "配置文件顶层必须是 JSON 对象。\n")
    config = load_model_config(values)
    if args.image and not config.supports_images:
        parser.exit(2, "图片示例要求启用 supports_images，并确认中转站和模型支持图片。\n")
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
        images=[FileImage(path=args.image)] if args.image else [],
    )
    result = agent.generate(request)
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
