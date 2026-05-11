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

    async def insert(
        self,
        *,
        image_id: str,
        caption: str,
        caption_vector: list[float],
        image_vector: list[float],
        style: str,
        building_type: str,
        image_url: str,
    ) -> None:
        def _insert() -> None:
            self.collection.insert(
                [
                    [image_id],
                    [caption[:2048]],
                    [caption_vector],
                    [image_vector],
                    [style[:128]],
                    [building_type[:128]],
                    [image_url[:1024]],
                ]
            )
            self.collection.flush()

        await asyncio.to_thread(_insert)

    async def search(
        self,
        *,
        vector_field: str,
        query_vector: list[float],
        top_k: int,
        filters: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        if vector_field not in ("caption_vector", "image_vector"):
            raise ValueError(f"Unsupported vector field: {vector_field!r}")

        expr = _build_filter_expr(filters)

        def _search() -> list[dict[str, Any]]:
            params = {"metric_type": "COSINE", "params": {"ef": 64}}
            results = self.collection.search(
                data=[query_vector],
                anns_field=vector_field,
                param=params,
                limit=top_k,
                expr=expr,
                output_fields=["image_id", "caption", "image_url", "style", "building_type"],
            )
            hits = results[0] if results else []
            return [
                {
                    "image_id": hit.entity.get("image_id"),
                    "caption": hit.entity.get("caption"),
                    "image_url": hit.entity.get("image_url"),
                    "style": hit.entity.get("style"),
                    "building_type": hit.entity.get("building_type"),
                    "score": float(hit.score),
                }
                for hit in hits
            ]

        return await asyncio.to_thread(_search)


def _build_filter_expr(filters: dict[str, str] | None) -> str | None:
    if not filters:
        return None
    clauses: list[str] = []
    for key, value in filters.items():
        if key not in ("style", "building_type"):
            continue
        if not value:
            continue
        safe = value.replace('"', '\\"')
        clauses.append(f'{key} == "{safe}"')
    return " and ".join(clauses) if clauses else None
