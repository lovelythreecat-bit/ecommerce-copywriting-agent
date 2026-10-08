"""Keep the original final-output contract covered as the graph grows."""

import pytest

from ecommerce_copy_agent.errors import OutputValidationError
from ecommerce_copy_agent.schemas import CopyRequirements
from ecommerce_copy_agent.validation import validate_output


@pytest.mark.parametrize('raw,max_chars', [
    ('{"text":"  ","warnings":[]}', None),
    ('"plain string"', None),
    ('{"text":"ok"}', None),
    ('{"text":"ok","warnings":[12]}', None),
    ('{"text":"123456","warnings":[]}', 5),
    ('before {"text":"ok","warnings":[]} after', None),
])
def test_bad_output_shapes(raw, max_chars):
    with pytest.raises(OutputValidationError) as error:
        validate_output(raw, CopyRequirements(max_chars=max_chars))
    assert error.value.problems
    assert raw not in str(error.value)


def test_complete_json_fence_accepted():
    checked = validate_output('```json\n{"text":"  好文案  ","warnings":[]}\n```', CopyRequirements())
    assert checked.text == '好文案'
