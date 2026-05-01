from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from langchain_core.messages import BaseMessage


class LLMClientBase(ABC):
    @abstractmethod
    async def ainvoke(self, messages: list[BaseMessage]) -> str:
        ...

    @abstractmethod
    async def ainvoke_with_vision(
        self,
        messages: list[BaseMessage],
        images: list[str],
    ) -> str:
        ...

    @abstractmethod
    async def astream(
        self,
        messages: list[BaseMessage],
        images: list[str] | None = None,
    ) -> AsyncIterator[str]:
        ...
