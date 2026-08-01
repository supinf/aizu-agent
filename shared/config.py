"""Runtime configuration for Vertex AI (no API keys)."""

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SHARED_DIR = Path(__file__).resolve().parent
DATA_DIR = SHARED_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
KNOWLEDGE_PATH = DATA_DIR / "knowledge.json"
SOURCES_PATH = DATA_DIR / "sources.yaml"

# LLM / Embedding (Vertex AI)
LLM_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")

# Vertex AI auth via ADC
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "global")


def require_vertex_env() -> None:
    """Fail fast if Vertex AI environment variables are missing."""
    missing = [
        name
        for name, value in (
            ("GOOGLE_CLOUD_PROJECT", GOOGLE_CLOUD_PROJECT),
            ("GOOGLE_CLOUD_LOCATION", GOOGLE_CLOUD_LOCATION),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Vertex AI 用の環境変数が未設定です: "
            + ", ".join(missing)
            + "。`.env.example` を参考に `.env` を作成し、"
            "`gcloud auth application-default login` を実行してください。"
            " API キーは使用しません。"
        )

    # Guardrail: never rely on Gemini API keys in this project.
    for banned in ("GOOGLE_API_KEY", "GEMINI_API_KEY"):
        if os.getenv(banned):
            raise RuntimeError(
                f"{banned} が設定されています。"
                "本デモは Vertex AI + ADC のみで動作させてください。"
            )

    # Guardrail: ADK 経由の LLM 呼び出しが Vertex AI を向いていることを保証する。
    # google-genai 2.x の正式名は GOOGLE_GENAI_USE_ENTERPRISE (旧名は …_USE_VERTEXAI)。
    if not any(
        (os.getenv(flag) or "").lower() in ("true", "1")
        for flag in ("GOOGLE_GENAI_USE_ENTERPRISE", "GOOGLE_GENAI_USE_VERTEXAI")
    ):
        raise RuntimeError(
            "GOOGLE_GENAI_USE_ENTERPRISE=true が未設定です。"
            "`.env.example` を参考に `.env` を作成してください。"
            " API キーは使用しません。"
        )
