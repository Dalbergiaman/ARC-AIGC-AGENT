import asyncio
from typing import Any

from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)

from config import (
    CAPTION_VECTOR_DIM,
    COLLECTION_NAME,
    IMAGE_VECTOR_DIM,
)


_CONNECTION_ALIAS = "image-rag-mcp"

_VECTOR_INDEX_PARAMS: dict[str, Any] = {
    "index_type": "HNSW",
    "metric_type": "COSINE",
    "params": {"M": 16, "efConstruction": 200},
}

_SCALAR_INDEX_FIELDS = ("style", "building_type")


def _build_schema() -> CollectionSchema:
    fields = [
        FieldSchema(
            name="image_id",
            dtype=DataType.VARCHAR,
            is_primary=True,
            auto_id=False,
            max_length=36,
        ),
        FieldSchema(name="caption", dtype=DataType.VARCHAR, max_length=2048),
        FieldSchema(
            name="caption_vector",
            dtype=DataType.FLOAT_VECTOR,
            dim=CAPTION_VECTOR_DIM,
        ),
        FieldSchema(
            name="image_vector",
            dtype=DataType.FLOAT_VECTOR,
            dim=IMAGE_VECTOR_DIM,
        ),
        FieldSchema(name="style", dtype=DataType.VARCHAR, max_length=128),
        FieldSchema(name="building_type", dtype=DataType.VARCHAR, max_length=128),
        FieldSchema(name="image_url", dtype=DataType.VARCHAR, max_length=1024),
    ]
    return CollectionSchema(
        fields=fields,
        description="image_library: caption + image vectors with scalar filters",
        enable_dynamic_field=False,
    )


class MilvusImageLibraryClient:
    def __init__(self, host: str, port: str | int) -> None:
        self._host = host
        self._port = str(port)
        self._collection: Collection | None = None

    async def connect(self) -> None:
        await asyncio.to_thread(self._connect_sync)

    async def close(self) -> None:
        await asyncio.to_thread(self._close_sync)

    @property
    def collection(self) -> Collection:
        if self._collection is None:
            raise RuntimeError("Milvus collection not initialized; call connect() first")
        return self._collection

    def _connect_sync(self) -> None:
        if _CONNECTION_ALIAS not in connections.list_connections():
            connections.connect(
                alias=_CONNECTION_ALIAS,
                host=self._host,
                port=self._port,
            )

        if utility.has_collection(COLLECTION_NAME, using=_CONNECTION_ALIAS):
            collection = Collection(COLLECTION_NAME, using=_CONNECTION_ALIAS)
        else:
            schema = _build_schema()
            collection = Collection(
                COLLECTION_NAME,
                schema=schema,
                using=_CONNECTION_ALIAS,
            )

        self._ensure_indexes(collection)
        collection.load()
        self._collection = collection

    def _close_sync(self) -> None:
        if _CONNECTION_ALIAS in connections.list_connections():
            connections.disconnect(_CONNECTION_ALIAS)
        self._collection = None

    def _ensure_indexes(self, collection: Collection) -> None:
        existing = {idx.field_name for idx in collection.indexes}

        for field in ("caption_vector", "image_vector"):
            if field not in existing:
                collection.create_index(
                    field_name=field,
                    index_params=_VECTOR_INDEX_PARAMS,
                )

        for field in _SCALAR_INDEX_FIELDS:
            if field not in existing:
                collection.create_index(
                    field_name=field,
                    index_params={"index_type": "INVERTED"},
                )

    async def health_check(self) -> dict[str, Any]:
        def _check() -> dict[str, Any]:
            collection = self.collection
            return {
                "name": collection.name,
                "num_entities": collection.num_entities,
                "indexes": [idx.field_name for idx in collection.indexes],
            }

        return await asyncio.to_thread(_check)
