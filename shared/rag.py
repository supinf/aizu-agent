"""In-memory FAISS RAG over demo knowledge chunks (Vertex embeddings, no API key)."""

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import faiss
import numpy as np
from google import genai

from shared.config import (
    EMBEDDING_MODEL,
    GOOGLE_CLOUD_LOCATION,
    GOOGLE_CLOUD_PROJECT,
    KNOWLEDGE_PATH,
    require_vertex_env,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class KnowledgeChunk:
    id: str
    title: str
    text: str
    source: str
    url: str


class InMemoryJuRag:
    """Tiny FAISS index built from knowledge.json at first use."""

    def __init__(self) -> None:
        self._chunks: list[KnowledgeChunk] = []
        self._index: faiss.IndexFlatIP | None = None
        self._client: genai.Client | None = None

    @property
    def ready(self) -> bool:
        return self._index is not None and bool(self._chunks)

    def _get_client(self) -> genai.Client:
        if self._client is None:
            require_vertex_env()
            self._client = genai.Client(
                vertexai=True,
                project=GOOGLE_CLOUD_PROJECT,
                location=GOOGLE_CLOUD_LOCATION,
            )
        return self._client

    def _embed(self, texts: list[str]) -> np.ndarray:
        client = self._get_client()
        # google-genai は複数 contents をまとめて埋め込める
        response = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=texts,
        )
        embeddings = getattr(response, "embeddings", None)
        if not embeddings:
            raise RuntimeError(f"Unexpected embedding response: {response!r}")

        vectors = [list(item.values) for item in embeddings]
        arr = np.asarray(vectors, dtype=np.float32)
        faiss.normalize_L2(arr)
        return arr

    def load(self, path=KNOWLEDGE_PATH) -> None:
        if not path.exists():
            raise FileNotFoundError(
                f"知識ファイルが見つかりません: {path}\n"
                "デモ前に次を実行してください:\n"
                "  python scripts/fetch_sources.py\n"
                "  python scripts/build_knowledge.py"
            )

        payload = json.loads(path.read_text(encoding="utf-8"))
        raw_chunks = payload.get("chunks") or payload
        chunks: list[KnowledgeChunk] = []
        for item in raw_chunks:
            chunks.append(
                KnowledgeChunk(
                    id=str(item["id"]),
                    title=str(item.get("title", "")),
                    text=str(item["text"]).strip(),
                    source=str(item.get("source", "")),
                    url=str(item.get("url", "")),
                )
            )
        if not chunks:
            raise ValueError(f"知識チャンクが空です: {path}")

        logger.info("Building FAISS index from %d chunks (%s)", len(chunks), path)
        vectors = self._embed([c.text for c in chunks])
        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)
        self._chunks = chunks
        self._index = index
        logger.info("FAISS index ready (dim=%d)", vectors.shape[1])

    def search(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        if not self.ready:
            self.load()
        assert self._index is not None

        query_vec = self._embed([query])
        scores, indices = self._index.search(query_vec, min(top_k, len(self._chunks)))
        results: list[dict[str, Any]] = []
        for score, idx in zip(scores[0], indices[0], strict=True):
            if idx < 0:
                continue
            chunk = self._chunks[int(idx)]
            results.append(
                {
                    "id": chunk.id,
                    "title": chunk.title,
                    "text": chunk.text,
                    "source": chunk.source,
                    "url": chunk.url,
                    "score": float(score),
                }
            )
        return results


@lru_cache(maxsize=1)
def get_rag() -> InMemoryJuRag:
    rag = InMemoryJuRag()
    # Eager load so the first audience question is not slowed by embedding.
    rag.load()
    return rag


def search_ju_knowledge(query: str, top_k: int = 3) -> dict[str, Any]:
    """会津若松市の公式知識 (什の掟・課題・スマートシティ等) をベクトル検索します。

    Args:
        query: 検索したい内容 (日本語の自然文でよい)
        top_k: 返す件数 (既定 3)

    Returns:
        検索結果と出典情報を含む辞書
    """
    try:
        hits = get_rag().search(query=query, top_k=top_k)
        return {
            "status": "success",
            "query": query,
            "count": len(hits),
            "results": hits,
        }
    except Exception:
        # 例外の詳細 (Google Cloud プロジェクト ID / サービスアカウント / 内部パス等) は
        # 公開 Cloud Run の画面に出さない。運用者はサーバログ側で追跡する。
        logger.exception("RAG search failed (query=%r, top_k=%r)", query, top_k)
        return {
            "status": "error",
            "query": query,
            "error_message": (
                "知識の検索に失敗しました。時間をおいて試すか、"
                "別の聞き方をしてみてください。"
            ),
        }
