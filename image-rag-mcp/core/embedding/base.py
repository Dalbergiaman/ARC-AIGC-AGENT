from abc import ABC, abstractmethod


class TextEmbeddingClientBase(ABC):
    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        ...


class ImageEmbeddingClientBase(ABC):
    @abstractmethod
    async def embed_image(self, image_url: str) -> list[float]:
        ...
