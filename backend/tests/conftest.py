import httpx2
import openai
import pytest


@pytest.fixture
def account_error():
    """What the openai SDK raises when OpenRouter rejects the key itself (spend cap, no credits, bad key)."""
    def make(status):
        request = httpx2.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
        return openai.APIStatusError("Key limit exceeded", response=httpx2.Response(status, request=request), body=None)
    return make
