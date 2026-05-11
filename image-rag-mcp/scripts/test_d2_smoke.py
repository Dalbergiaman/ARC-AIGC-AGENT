"""End-to-end smoke test for D-2: VLM caption + text/image embeddings.

Pipeline:
  1. Read LLM config from dashboard.yaml.
  2. Generate a caption for a real architectural image (local file -> data URL).
  3. Embed caption via VolcengineTextEmbedding (multimodal endpoint, text input).
  4. Embed the same image via VolcengineImageEmbedding (data URL).
  5. Assert both vectors are 2048-d floats.
"""
import asyncio
import base64
import mimetypes
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from core.embedding.factory import (  # noqa: E402
    ImageEmbeddingFactory,
    TextEmbeddingFactory,
)
from core.vlm_caption import generate_caption  # noqa: E402

_LOCAL_IMAGE = (
    ROOT.parent
    / "backend"
    / "generated"
    / "781b8c81-2c4b-4e86-9c0d-683b9c00907a.png"
)


def _to_data_url(path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    mime = mime or "image/png"
    data = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{data}"


async def main() -> None:
    api_key = config.get_embedding_api_key()
    if not api_key:
        raise RuntimeError("embedding.api_key missing in dashboard.yaml")
    if not _LOCAL_IMAGE.exists():
        raise RuntimeError(f"local test image missing: {_LOCAL_IMAGE}")

    image_url = _to_data_url(_LOCAL_IMAGE)
    print(f"image: {_LOCAL_IMAGE.name} ({len(image_url)} bytes data-url)")

    print("[1] generating caption ...")
    caption = await generate_caption(image_url)
    print(f"    caption: {caption}")

    text_client = TextEmbeddingFactory.create("volcengine", api_key)
    image_client = ImageEmbeddingFactory.create("volcengine", api_key)

    print("[2] embedding caption ...")
    cap_vec = await text_client.embed(caption)
    print(f"    caption_vector dim={len(cap_vec)} sample={cap_vec[:3]}")

    print("[3] embedding image ...")
    img_vec = await image_client.embed_image(image_url)
    print(f"    image_vector dim={len(img_vec)} sample={img_vec[:3]}")

    assert len(cap_vec) == config.CAPTION_VECTOR_DIM, "caption dim mismatch"
    assert len(img_vec) == config.IMAGE_VECTOR_DIM, "image dim mismatch"
    print("OK")


if __name__ == "__main__":
    asyncio.run(main())
