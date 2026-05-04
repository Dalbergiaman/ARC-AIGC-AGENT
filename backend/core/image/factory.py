from core.image.bailian_client import BailianClient
from core.image.base import ImageGeneratorBase
# from core.image.openrouter_client import OpenRouterClient
from core.image.volcengine_client import VolcengineClient
from core.image.grsai_client import GrsaiClient


class ImageGeneratorFactory:
    _registry: dict[str, type[ImageGeneratorBase]] = {
        "bailian": BailianClient,
        "volcengine": VolcengineClient,
        "grsai": GrsaiClient,
    }

    @classmethod
    def create(cls, provider: str, api_key: str, model: str) -> ImageGeneratorBase:
        if provider not in cls._registry:
            raise KeyError(f"Unknown image provider: {provider!r}. Available: {list(cls._registry)}")
        return cls._registry[provider](api_key=api_key, model=model)
