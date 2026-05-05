from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool

from agent.prompts import analyze_image_system
from agent.state import ReferenceImageAnalysis
from core.llm.client import LLMClient

_llm = LLMClient()


@tool
async def analyze_reference_image(image_url: str) -> dict:
    """Analyze a reference image using VLM and extract architectural design features.

    Returns structured analysis including style, material, lighting, viewpoint, etc.
    """
    import json

    messages = [
        SystemMessage(content=analyze_image_system()),
        HumanMessage(content="请分析这张建筑参考图。"),
    ]

    raw = await _llm.ainvoke(messages, images=[image_url])

    # Strip markdown code fences if present
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {
            "image_url": image_url,
            "building_type": "",
            "style": "",
            "facade_material": "",
            "lighting": "",
            "viewpoint": "",
            "color_palette": "",
            "description": "图片分析失败，请继续描述您的设计需求",
        }

    result: ReferenceImageAnalysis = {
        "image_url": image_url,
        "building_type": data.get("building_type", ""),
        "style": data.get("style", ""),
        "facade_material": data.get("facade_material", ""),
        "lighting": data.get("lighting", ""),
        "viewpoint": data.get("viewpoint", ""),
        "color_palette": data.get("color_palette", ""),
        "description": data.get("description", ""),
    }
    return result


if __name__ == "__main__":
    import asyncio

    async def main():
        image_url = "https://pic.rmb.bdstatic.com/bjh/news/3c7d0066e7b8b1d0bb2b9eabb822f2e1.jpeg"
        analysis = await analyze_reference_image.ainvoke(image_url)
        print("✅ 分析成功，结果:", analysis)

    asyncio.run(main())