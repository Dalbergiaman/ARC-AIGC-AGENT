import base64
import mimetypes
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool

from agent.prompts import analyze_image_system
from agent.state import ReferenceImageAnalysis
from config import settings
from core.llm.client import LLMClient
from core.observability import message_preview, observe, update_current_generation

_llm = LLMClient()


def _to_data_url(image_url: str) -> str:
    """Convert a local static URL to a base64 data URL so external VLMs can access it.

    External URLs (http/https pointing outside localhost) are returned unchanged.
    Local paths (/static/uploads/...) and localhost URLs are read from disk.
    """
    local_prefix = "/static/uploads/"

    # Normalise: strip scheme+host for localhost URLs
    path_part = image_url
    for prefix in ("http://localhost:8000", "http://127.0.0.1:8000"):
        if image_url.startswith(prefix):
            path_part = image_url[len(prefix):]
            break

    if not path_part.startswith(local_prefix):
        # External URL — return as-is
        return image_url

    filename = path_part[len(local_prefix):]
    file_path = Path(settings.UPLOAD_DIR) / filename
    if not file_path.exists():
        return image_url  # fallback: let VLM try the URL directly

    mime, _ = mimetypes.guess_type(str(file_path))
    mime = mime or "image/jpeg"
    data = base64.b64encode(file_path.read_bytes()).decode()
    return f"data:{mime};base64,{data}"


@tool
@observe(name="tool:analyze_reference_image", as_type="generation")
async def analyze_reference_image(image_url: str) -> dict:
    """Analyze a reference image using VLM and extract architectural design features.

    Returns structured analysis including style, material, lighting, viewpoint, etc.
    """
    import json

    resolved_url = _to_data_url(image_url)

    messages = [
        SystemMessage(content=analyze_image_system()),
        HumanMessage(content="请分析这张建筑参考图。"),
    ]

    raw = await _llm.ainvoke(messages, images=[resolved_url])
    update_current_generation(
        input={"image_url": image_url, "resolved_as_data_url": resolved_url.startswith("data:")},
        output=message_preview(raw),
    )

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
        update_current_generation(
            output={"image_url": image_url, "description": "parse failed"},
            metadata={"parse_ok": False},
            level="WARNING",
            status_message="reference image analysis JSON parse failed",
        )
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
    update_current_generation(output=result, metadata={"parse_ok": True})
    return result


if __name__ == "__main__":
    import asyncio

    async def main():
        # Test with a local upload
        import os
        uploads = Path(settings.UPLOAD_DIR)
        local_files = list(uploads.glob("*.png")) + list(uploads.glob("*.jpg"))
        if local_files:
            test_url = f"/static/uploads/{local_files[0].name}"
            print(f"Testing with local file: {test_url}")
        else:
            test_url = "https://pic.rmb.bdstatic.com/bjh/news/3c7d0066e7b8b1d0bb2b9eabb822f2e1.jpeg"
            print(f"No local files found, testing with external URL: {test_url}")

        analysis = await analyze_reference_image.ainvoke({"image_url": test_url})
        print("✅ 分析成功，结果:", analysis)

    asyncio.run(main())
