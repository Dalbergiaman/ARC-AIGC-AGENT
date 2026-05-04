from core.image.base import GenerationRequest, GenerationResult
from core.image.factory import ImageGeneratorFactory
from services import dashboard_service


class ImageGenerator:
    async def generate(self, request: GenerationRequest) -> GenerationResult:
        config = dashboard_service.get_config()["image_provider"]
        client = ImageGeneratorFactory.create(
            provider=config["provider"],
            api_key=config["api_key"],
            model=config["model"],
        )
        return await client.generate(request)

if __name__ == "__main__":
    import asyncio

    async def main():
        generator = ImageGenerator()
        result = await generator.generate(
            GenerationRequest(
                prompt="汉庭酒店大厅效果图，现代简约风格，温馨舒适，高清",
                width=2048,
                height=2048,
            )
        )
        print("Generated image URL:", result.image_url)
        print("Generation data:", result.raw_response)

    asyncio.run(main())