from core.llm.base import LLMClientBase
from core.llm.bailian_client import BailianLLMClient
from core.llm.volcengine_client import VolcengineLLMClient


class LLMClientFactory:
    _registry: dict[str, type[LLMClientBase]] = {
        "bailian": BailianLLMClient,
        "volcengine": VolcengineLLMClient,
    }

    @classmethod
    def create(cls, provider: str, model: str, api_key: str) -> LLMClientBase:
        if provider not in cls._registry:
            raise KeyError(f"Unknown LLM provider: {provider!r}. Available: {list(cls._registry)}")
        return cls._registry[provider](model=model, api_key=api_key)
