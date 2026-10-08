import pytest

from ecommerce_copy_agent.adapters.base import ModelAdapter, ModelRequest, ModelResponse


class FakeAdapter:
    model_name = "test-model"
    supports_images = True

    async def generate(self, request: ModelRequest) -> ModelResponse:
        assert request.system_prompt == "Follow product facts"
        assert request.user_prompt == "Describe cup"
        assert request.images == []
        return ModelResponse(text='{"text":"A cup","warnings":[]}', model=self.model_name)


@pytest.mark.asyncio
async def test_provider_independent_adapter_contract():
    adapter: ModelAdapter = FakeAdapter()
    response = await adapter.generate(ModelRequest(system_prompt="Follow product facts", user_prompt="Describe cup", images=[]))
    assert response.text == '{"text":"A cup","warnings":[]}'
    assert response.model == "test-model"
    assert response.usage is None
