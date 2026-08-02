import asyncio

from resolveai.api.dependencies import build_container
from resolveai.config import get_settings
from resolveai.retrieval.loader import load_policies


async def main() -> None:
    settings = get_settings()
    if settings.retrieval_backend != "elasticsearch":
        raise SystemExit("Set RETRIEVAL_BACKEND=elasticsearch before running this script")
    container = await build_container(settings)
    count = await container.retriever.index(load_policies(settings.data_dir))
    print(f"Indexed {count} policy documents into {settings.elasticsearch_index}")
    await container.close()


if __name__ == "__main__":
    asyncio.run(main())
