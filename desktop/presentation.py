"""Plain-text presentation of public marketing workflow artifacts."""

from __future__ import annotations

from typing import Any, Iterable


def _line(value: str) -> str:
    return value.strip() or "未指定"


def _bullets(values: Iterable[str]) -> str:
    items = [f"• {value}" for value in values if value.strip()]
    return "\n".join(items) if items else "暂无"


def format_strategy(strategy: Any | None) -> str:
    if strategy is None:
        return "没有可显示的营销策略。"
    sections = [
        ("已知事实", _bullets(strategy.facts)),
        ("受众假设", _line(strategy.audience_hypothesis)),
        ("购买动机", _line(strategy.purchase_motivation)),
        ("核心主张", _line(strategy.key_message)),
        ("属性与利益", _bullets(strategy.benefits)),
        ("使用场景", _bullets(strategy.scenarios)),
        ("可能顾虑", _bullets(strategy.objections)),
        ("行动目标", _line(strategy.call_to_action)),
        ("其他假设", _bullets(strategy.assumptions)),
        ("信息缺口", _bullets(strategy.missing_information)),
        ("引用资料编号", _bullets(strategy.source_ids)),
    ]
    return "\n\n".join(f"{title}\n{value}" for title, value in sections)


def format_review(review: Any | None) -> str:
    if review is None:
        return "没有可显示的审稿记录。"
    issues = [
        f"{index}. 原句：{issue.quote}\n   问题：{issue.problem}\n   建议：{issue.suggestion}"
        for index, issue in enumerate(review.issues, 1)
    ]
    issues_text = "\n\n".join(issues) if issues else "暂无"
    return "\n\n".join(
        (
            f"优点\n{_bullets(review.strengths)}",
            f"具体问题与修改建议\n{issues_text}",
            f"事实风险\n{_bullets(review.factual_risks)}",
        )
    )


def format_sources(sources: Iterable[Any]) -> str:
    intro = "默认检索器使用本地资料。以下是本次实际返回并用于策划的资料；来源类型以各条标记为准。"
    origin_labels = {"curated": "本地整理", "web": "网络来源", "custom": "自定义来源"}
    entries = []
    for source in sources:
        lines = [
            f"{source.id} · {source.title} · {origin_labels.get(source.origin, source.origin)}",
            f"链接：{source.url}",
            f"摘要：{source.summary}",
        ]
        if source.tags:
            lines.append(f"标签：{'、'.join(source.tags)}")
        if source.accessed_on:
            lines.append(f"获取日期：{source.accessed_on}")
        entries.append("\n".join(lines))
    return intro + ("\n\n" + "\n\n".join(entries) if entries else "\n\n没有可显示的资料来源。")
