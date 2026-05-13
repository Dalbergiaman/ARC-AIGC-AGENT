from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class GenerationRequest:
    prompt: str
    negative_prompt: str | None = None
    ref_image_url: str | None = None
    control_image_url: str | None = None
    input_image_urls: list[str] | None = None
    width: int = 2048
    height: int = 1152
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


def append_negative_prompt_to_prompt(prompt: str, negative_prompt: str | None) -> str:
    """Fold negative constraints into prompt for providers without a native field."""
    negative = (negative_prompt or "").strip()
    if not negative:
        return prompt
    return f"{prompt.strip()}\n\n避免出现以下问题：{negative}"
