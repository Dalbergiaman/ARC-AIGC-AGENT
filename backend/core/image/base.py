from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class GenerationRequest:
    prompt: str
    negative_prompt: str | None = None
    ref_image_url: str | None = None
    control_image_url: str | None = None
    input_image_urls: list[str] | None = None
    width: int = 1920
    height: int = 1920
    steps: int = 30
    seed: int | None = None
    aspectRatio: str | None = None
    imageSize: str | None = None


@dataclass
class GenerationResult:
    image_url: str
    provider: str
    generation_time: float
    raw_response: dict


class ImageGeneratorBase(ABC):
    @abstractmethod
    async def generate(self, request: GenerationRequest) -> GenerationResult:
        ...
