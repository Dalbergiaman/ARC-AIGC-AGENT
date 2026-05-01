from collections.abc import AsyncIterator

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from core.llm.base import LLMClientBase
from core.llm.factory import LLMClientFactory
from services import dashboard_service


class LLMClient:
    def _make_client(self) -> LLMClientBase:
        config = dashboard_service.get_config()
        llm_cfg = config["llm"]
        return LLMClientFactory.create(
            provider=llm_cfg["provider"],
            model=llm_cfg["model"],
            api_key=llm_cfg["api_key"],
        )

    async def ainvoke(
        self,
        messages: list[BaseMessage],
        images: list[str] | None = None,
    ) -> str:
        client = self._make_client()
        if images:
            return await client.ainvoke_with_vision(messages, images)
        return await client.ainvoke(messages)

    async def astream(
        self,
        messages: list[BaseMessage],
        images: list[str] | None = None,
    ) -> AsyncIterator[str]:
        client = self._make_client()
        return client.astream(messages, images)


if __name__ == "__main__":
    import asyncio

    async def main():
        llm_client = LLMClient()
        response = await llm_client.ainvoke(
            messages=[HumanMessage(content="你是什么模型？")],
        )
        print("Response:", response)

    asyncio.run(main())