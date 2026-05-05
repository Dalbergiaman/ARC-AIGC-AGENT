from .base import ImageEmbeddingClientBase, TextEmbeddingClientBase
from .volcengine_image import VolcengineImageEmbedding
from .volcengine_text import VolcengineTextEmbedding


class TextEmbeddingFactory:
    _registry: dict[str, type[TextEmbeddingClientBase]] = {
        "volcengine": VolcengineTextEmbedding,
    }

    @classmethod
    def create(cls, provider: str, api_key: str) -> TextEmbeddingClientBase:
        if provider not in cls._registry:
            raise KeyError(f"Unknown text embedding provider: {provider!r}")
        return cls._registry[provider](api_key)


class ImageEmbeddingFactory:
    _registry: dict[str, type[ImageEmbeddingClientBase]] = {
        "volcengine": VolcengineImageEmbedding,
    }

    @classmethod
    def create(cls, provider: str, api_key: str) -> ImageEmbeddingClientBase:
        if provider not in cls._registry:
            raise KeyError(f"Unknown image embedding provider: {provider!r}")
        return cls._registry[provider](api_key)
