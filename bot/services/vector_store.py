import logging
import os

import chromadb
from openai import OpenAI

from bot.config import DATA_PATH, DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL

logger = logging.getLogger(__name__)

CHROMA_PATH = os.path.join(DATA_PATH, "chroma")
COLLECTION_NAME = "files"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
EMBEDDING_MODEL = "deepseek-embedding-v2"

_client: chromadb.ClientAPI | None = None
_collection: chromadb.Collection | None = None
_openai: OpenAI | None = None


def _get_openai() -> OpenAI:
    global _openai
    if _openai is None:
        _openai = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            max_retries=3,
            timeout=60.0,
        )
    return _openai


def _get_collection() -> chromadb.Collection:
    global _client, _collection
    if _collection is None:
        os.makedirs(CHROMA_PATH, exist_ok=True)
        _client = chromadb.PersistentClient(path=CHROMA_PATH)
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def _embed(texts: list[str]) -> list[list[float]]:
    client = _get_openai()
    resp = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [d.embedding for d in resp.data]


def _chunk_text(text: str, filename: str) -> list[dict]:
    chunks = []
    start = 0
    idx = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunk = text[start:end]
        chunks.append({
            "id": f"{filename}::{idx}",
            "text": chunk,
            "metadata": {"filename": filename, "chunk_idx": idx, "start": start},
        })
        idx += 1
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def index_file(filename: str, text: str) -> int:
    collection = _get_collection()
    # Remove old chunks for this file
    remove_file(filename)

    chunks = _chunk_text(text, filename)
    if not chunks:
        return 0

    batch_size = 50
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        texts = [c["text"] for c in batch]
        embeddings = _embed(texts)
        collection.add(
            ids=[c["id"] for c in batch],
            documents=texts,
            embeddings=embeddings,
            metadatas=[c["metadata"] for c in batch],
        )

    logger.info("Indexed %s: %d chunks", filename, len(chunks))
    return len(chunks)


def remove_file(filename: str) -> None:
    collection = _get_collection()
    results = collection.get(where={"filename": filename})
    if results["ids"]:
        collection.delete(ids=results["ids"])
        logger.info("Removed %d chunks for %s", len(results["ids"]), filename)


def search(query: str, n_results: int = 5) -> list[dict]:
    collection = _get_collection()
    if collection.count() == 0:
        return []
    query_embedding = _embed([query])[0]
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(n_results, collection.count()),
    )
    items = []
    for i, doc in enumerate(results["documents"][0]):
        meta = results["metadatas"][0][i]
        dist = results["distances"][0][i] if results["distances"] else None
        items.append({
            "filename": meta["filename"],
            "chunk_idx": meta["chunk_idx"],
            "text": doc,
            "distance": dist,
        })
    return items


def get_stats() -> dict:
    collection = _get_collection()
    return {"total_chunks": collection.count()}
