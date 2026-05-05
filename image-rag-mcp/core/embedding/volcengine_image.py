import httpx

from .base import ImageEmbeddingClientBase

_ENDPOINT = "https://ark.cn-beijing.volces.com/api/v3/embeddings/multimodal"
_MODEL = "doubao-embedding-vision-251215"
_TIMEOUT = 60.0


class VolcengineImageEmbedding(ImageEmbeddingClientBase):
    def __init__(self, api_key: str) -> None:
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def embed_image(self, image_url: str) -> list[float]:
        payload = {
            "model": _MODEL,
            "input": [
                {"type": "image_url", "image_url": {"url": image_url}}
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
        image_url = "https://www.baidu.com/img/PCtm_d9c8750bed0b3c7d089fa7d55720d6cf.png"
        embedding_client = VolcengineImageEmbedding(api_key)
        embedding = await embedding_client.embed_image(image_url)
        print("✅ 生成成功，向量长度:", len(embedding))
        print("Image embedding:", embedding[:5], "...")
        print("Embedding JSON:", len(embedding), "...")

    asyncio.run(main())