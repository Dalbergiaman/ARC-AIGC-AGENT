import httpx

from .base import ImageEmbeddingClientBase, TextEmbeddingClientBase

_ENDPOINT = "https://ark.cn-beijing.volces.com/api/v3/embeddings/multimodal"
_MODEL = "doubao-embedding-vision-251215"
_TIMEOUT = 60.0


class VolcengineTextEmbedding(TextEmbeddingClientBase):
    def __init__(self, api_key: str) -> None:
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def embed(self, text: str) -> list[float]:
        payload = {
            "model": _MODEL,
            "input": [
                {"type": "text", "text": text}
            ],
            "encoding_format": "float",
        }
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(_ENDPOINT, headers=self._headers, json=payload)
            response.raise_for_status()
        return response.json()["data"]["embedding"]

if __name__ == "__main__":
    import asyncio

    async def main():
        api_key = "bc709e98-2051-430e-a872-b3293a6acd27"
        text = "Hello, my dog is cute"
        embedding_client = VolcengineTextEmbedding(api_key)
        embedding = await embedding_client.embed(text)
        print("✅ 生成成功，向量长度:", len(embedding))
        print("Text embedding:", embedding[:5], "...")
        print("Embedding JSON:", len(embedding), "...")

    asyncio.run(main())