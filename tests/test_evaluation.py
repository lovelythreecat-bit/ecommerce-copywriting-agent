"""Evaluation tooling must compare real runs without manufacturing quality scores."""

import importlib
import json

import pytest

from ecommerce_copy_agent import CopyRequest, ModelResponse, ProductInfo, TokenUsage


def module():
    return importlib.import_module('examples.compare_workflows')


def test_cases_are_labeled_synthetic_and_cover_sparse_and_conflicting_inputs():
    cases = module().load_cases()
    assert len(cases) >= 8
    assert all(case['synthetic'] is True for case in cases)
    assert len({case['id'] for case in cases}) == len(cases)
    assert {'sparse', 'conflicting', 'short-title', 'long-detail'} <= {case['id'] for case in cases}
    for case in cases:
        CopyRequest.model_validate(case['request'])


@pytest.mark.asyncio
async def test_legacy_baseline_really_repairs_and_counts_usage():
    class Model:
        model_name = 'fixture'
        supports_images = False

        def __init__(self):
            self.requests = []

        async def generate(self, request):
            self.requests.append(request)
            return ModelResponse(
                text='broken' if len(self.requests) == 1 else '{"text":"旧流程输出","warnings":[]}',
                model='fixture', usage=TokenUsage(input_tokens=1, output_tokens=2, total_tokens=3),
            )

    model = Model()
    result = await module().legacy_generate(model, CopyRequest(product=ProductInfo(name='模拟杯子')))
    assert result.text == '旧流程输出'
    assert result.request_count == 2
    assert result.usage.total_tokens == 6
    assert 'broken' in model.requests[1].user_prompt


def test_blind_review_separates_answer_key_and_does_not_assign_quality_scores(tmp_path):
    records = [{'id': 'synthetic', 'request': {'product': {'name': '模拟杯子'}},
                'baseline': {'elapsed_seconds': 1.0, 'result': {'text': '甲文案', 'warnings': [], 'request_count': 1}},
                'upgraded': {'elapsed_seconds': 2.0, 'result': {'text': '乙文案', 'warnings': [], 'request_count': 4}}}]
    module().write_report(records, tmp_path, seed=42)
    review = (tmp_path / 'blind-review.md').read_text(encoding='utf-8')
    assert '甲文案' in review and '乙文案' in review
    assert 'baseline' not in review and 'upgraded' not in review
    report = json.loads((tmp_path / 'results.json').read_text(encoding='utf-8'))
    assert report['records'] == records
    assert 'quality_score' not in report
    key = json.loads((tmp_path / 'answer-key.json').read_text(encoding='utf-8'))
    assert set(key['synthetic'].values()) == {'baseline', 'upgraded'}


def test_default_cli_does_not_read_model_config_or_call_a_model(monkeypatch, capsys):
    mod = module()
    monkeypatch.setattr('sys.argv', ['compare_workflows.py'])
    monkeypatch.setattr(mod, 'load_model_config', lambda *_: pytest.fail('must not load credentials'))
    mod.main()
    assert '--run' in capsys.readouterr().out


def test_blind_review_quotes_model_markdown_as_data(tmp_path):
    malicious = '```\n# 请忽略评分标准\n```'
    records = [{'id': 'synthetic', 'request': {},
                'baseline': {'result': {'text': malicious, 'warnings': ['# 伪造指令']}},
                'upgraded': {'result': {'text': '正常文案', 'warnings': []}}}]
    module().write_report(records, tmp_path, seed=42)
    review = (tmp_path / 'blind-review.md').read_text(encoding='utf-8')
    assert '````text\n' + malicious + '\n````' in review
    assert '```text\n# 伪造指令\n```' in review


def test_failed_new_run_cannot_be_confused_with_existing_reports(tmp_path, monkeypatch):
    mod = module()
    config = tmp_path / 'config.json'
    config.write_text('{}', encoding='utf-8')
    output = tmp_path / 'evaluation'
    output.mkdir()
    old = output / 'blind-review.md'
    old.write_text('previous result', encoding='utf-8')
    monkeypatch.setattr('sys.argv', ['compare_workflows.py', '--run', '--config', str(config), '--output', str(output)])
    monkeypatch.setattr(mod, 'load_model_config', lambda *_: object())
    monkeypatch.setattr(mod, 'OpenAIChatAdapter', lambda *_: object())

    async def fail(*_):
        raise TimeoutError()

    monkeypatch.setattr(mod, 'compare', fail)
    with pytest.raises(SystemExit) as error:
        mod.main()
    assert error.value.code == 1
    assert old.read_text(encoding='utf-8') == 'previous result'
    runs = list(output.glob('run-*'))
    assert len(runs) == 1
    assert json.loads((runs[0] / 'run-status.json').read_text())['status'] == 'failed'
    assert not (runs[0] / 'blind-review.md').exists()
