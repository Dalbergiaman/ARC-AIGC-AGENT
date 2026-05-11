"""Generate image caption using the VLM configured in dashboard.yaml.

The caption is optimised for text-embedding retrieval:
  - A dense 2–3 sentence description focused on architectural attributes
    (style, facade material, lighting, viewpoint, surroundings, mood).
  - No prefix/suffix, no markdown.
"""
import httpx

import config


_BAILIAN_ENDPOINT = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
_VOLCENGINE_ENDPOINT = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
_TIMEOUT = 60.0

_SYSTEM_PROMPT = (
    "你是建筑图像理解助手。请为用户提供的建筑效果图生成一段 2-3 句的中文描述，"
    "用于文本向量检索。必须覆盖：建筑类型、风格、外立面材质、光线/氛围、视角、周边环境。"
    "语言紧凑客观，不要使用 markdown、不要加标题、不要加换行、不要使用 '这张图片' 之类的冗余表达。"
)


def _endpoint_for(provider: str) -> str:
    if provider == "bailian":
        return _BAILIAN_ENDPOINT
    if provider == "volcengine":
        return _VOLCENGINE_ENDPOINT
    raise ValueError(f"Unsupported VLM provider: {provider!r}")


async def generate_caption(image_url: str) -> str:
    llm = config.get_llm_config()
    provider = llm.get("provider", "")
    model = llm.get("model", "")
    api_key = llm.get("api_key", "")
    if not provider or not model or not api_key:
        raise RuntimeError("LLM provider/model/api_key missing in dashboard.yaml")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "请为这张建筑图生成检索用描述。"},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            },
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.post(_endpoint_for(provider), headers=headers, json=payload)
        response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


if __name__ == "__main__":
    import asyncio
    import sys

    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.baidu.com/img/PCtm_d9c8750bed0b3c7d089fa7d55720d6cf.png"
    caption = asyncio.run(generate_caption(url))
    print("Caption:", caption)
