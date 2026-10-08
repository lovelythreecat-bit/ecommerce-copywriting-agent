"""Readable desktop views for the public marketing artifacts."""

from types import SimpleNamespace

from desktop.presentation import format_review, format_sources, format_strategy


def test_strategy_shows_assumptions_and_actual_citations() -> None:
    strategy = SimpleNamespace(
        facts=["容量 500 毫升"],
        audience_hypothesis="通勤者（假设）",
        purchase_motivation="随身饮水",
        key_message="便于携带",
        benefits=["小巧，放入背包"],
        scenarios=["通勤路上"],
        objections=["保温时长待核实"],
        call_to_action="",
        assumptions=["使用者经常通勤"],
        missing_information=["材质"],
        source_ids=["K1"],
    )

    rendered = format_strategy(strategy)

    assert "已知事实\n• 容量 500 毫升" in rendered
    assert "受众假设\n通勤者（假设）" in rendered
    assert "信息缺口\n• 材质" in rendered
    assert "引用资料编号\n• K1" in rendered
    assert "行动目标\n未指定" in rendered


def test_review_shows_quote_problem_suggestion_and_risks() -> None:
    review = SimpleNamespace(
        strengths=["场景具体"],
        issues=[SimpleNamespace(quote="保温一整天", problem="没有证据", suggestion="删除时长")],
        factual_risks=["材质未核实"],
    )

    rendered = format_review(review)

    assert "优点\n• 场景具体" in rendered
    assert "原句：保温一整天" in rendered
    assert "问题：没有证据" in rendered
    assert "建议：删除时长" in rendered
    assert "事实风险\n• 材质未核实" in rendered


def test_sources_label_each_origin_without_claiming_live_search() -> None:
    sources = [
        SimpleNamespace(id="K1", title="标题写法", origin="curated", url="https://example.test/a", summary="本地整理", tags=["标题"], accessed_on=""),
        SimpleNamespace(id="K2", title="平台规则", origin="web", url="https://example.test/b", summary="检索器返回", tags=[], accessed_on="2026-09-30"),
        SimpleNamespace(id="K3", title="私有资料", origin="custom", url="https://example.test/c", summary="自定义", tags=[], accessed_on=""),
    ]

    rendered = format_sources(sources)

    assert "默认检索器使用本地资料" in rendered
    assert "K1 · 标题写法 · 本地整理" in rendered
    assert "K2 · 平台规则 · 网络来源" in rendered
    assert "K3 · 私有资料 · 自定义来源" in rendered
    assert "https://example.test/b" in rendered
    assert "获取日期：2026-09-30" in rendered
    assert "实时联网搜索" not in rendered


def test_missing_artifacts_have_explicit_empty_state() -> None:
    assert "没有" in format_strategy(None)
    assert "没有" in format_review(None)
    assert "没有" in format_sources([])
