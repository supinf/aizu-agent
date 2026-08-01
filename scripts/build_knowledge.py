#!/usr/bin/env python3
"""raw/ の公式抽出テキストからデモ用 knowledge.json を構築する。"""

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.config import KNOWLEDGE_PATH, RAW_DIR, SOURCES_PATH
from shared.prompts import JU_NO_OKITE_TEXT

# デモ向けに「必ず入れたい」超軽量チャンクを、取得テキストからキーワード近傍で切り出す。
CHUNK_SPECS: list[dict] = [
    {
        "id": "ju_no_okite",
        "title": "什の掟 (伝統的文言)",
        "mode": "curated_ju",
        "source": "会津若松市「あいづっこ宣言」関連資料で紹介される什の掟",
        "url": "https://www.city.aizuwakamatsu.fukushima.jp/docs/2007080601668/",
    },
    {
        "id": "challenge_youth_outflow_7th",
        "title": "【第7次・現行】若者層の人口流出と地域課題",
        "mode": "from_raw",
        "raw_id": "comprehensive_plan_prologue_pdf",
        "keywords": ["若年層", "人口流出", "社会動態", "15～19歳", "地方創生"],
        "max_chars": 900,
        "source": "会津若松市第7次総合計画 プロローグ「2020年代の会津若松市の課題」 (施行中)",
        "url": "https://www.city.aizuwakamatsu.fukushima.jp/docs/2016110400058/file_contents/003_prologue.pdf",
    },
    {
        "id": "challenge_youth_8th_draft",
        "title": "【第8次・素案】人口減少と若者・女性に選ばれるまちづくり",
        "mode": "from_raw",
        "raw_id": "comprehensive_plan_8th_draft_pdf",
        "keywords": [
            "進学や就職等を契機とした若者の流出",
            "若者の中でも 20～24 歳の女性",
            "若者や女性に選ばれるまちづくり",
            "本市が今直面している最大の課題は人口減少",
        ],
        "max_chars": 900,
        "source": "会津若松市第8次総合計画 基本構想及び基本計画 (素案・施行前)",
        "url": "https://www.city.aizuwakamatsu.fukushima.jp/docs/2026061200010/file_contents/keikaku_soan.pdf",
    },
    {
        "id": "aidzukko_declaration",
        "title": "あいづっこ宣言と「ならぬことはならぬ」",
        "mode": "from_raw",
        "raw_id": "aidzukko_declaration",
        "keywords": [
            "あいづっこ宣言",
            "ならぬことはならぬ",
            "やってはならぬ",
            "什の掟",
        ],
        "max_chars": 900,
        "source": "会津若松市「あいづっこ宣言」",
        "url": "https://www.city.aizuwakamatsu.fukushima.jp/docs/2007080601668/",
    },
    {
        "id": "smartcity_overview",
        "title": "スマートシティ会津若松の概要と3つの視点",
        "mode": "from_raw",
        "raw_id": "smartcity_overview",
        "keywords": [
            "スマートシティ会津若松",
            "重要視している3つの視点",
            "地域活力",
            "まちの見える化",
        ],
        "max_chars": 900,
        "source": "会津若松市「スマートシティ会津若松」について",
        "url": "https://www.city.aizuwakamatsu.fukushima.jp/docs/2013101500018/",
    },
    {
        "id": "smartcity_digital_garden",
        "title": "デジタル田園都市・共助型スマートシティ",
        "mode": "from_raw",
        "raw_id": "smartcity_digital_garden",
        "keywords": ["デジタル田園都市", "TYPE3", "データ連携", "共助型"],
        "max_chars": 800,
        "source": "会津若松市 デジタル田園都市国家構想プロジェクト",
        "url": "https://www.city.aizuwakamatsu.fukushima.jp/docs/2023070600046/",
    },
]


def _normalize(text: str) -> str:
    text = text.replace("\u3000", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _strip_pdf_noise(text: str) -> str:
    """PDF 抽出に混じる頁番号・表の数値行を落とす。"""
    kept: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            kept.append("")
            continue
        if re.fullmatch(r"-{2,}\s*page\s*\d+\s*-{2,}", s, flags=re.IGNORECASE):
            continue
        if re.fullmatch(r"[\d\s\./~\-〜～％% () (),，]+", s):
            continue
        if re.fullmatch(r"[-−]?\d{1,3}(?:,\d{3})*", s):
            continue
        if re.fullmatch(
            r"[HSＲR]\d{1,2}(?:→[HSＲR]\d{1,2})?(?:\s+[HSＲR]\d{1,2}(?:→[HSＲR]\d{1,2})?)*",
            s,
        ):
            continue
        if "年間婚姻数" in s and "人口千" in s:
            continue
        # 日本語行末に密着した頁番号ゴミを除去
        s = re.sub(r"(?<=[\u3040-\u30ff\u4e00-\u9fff])\d{1,2}$", "", s)
        s = re.sub(r"(?<=\S)\s+\d{1,2}$", "", s)
        kept.append(s)
    return _normalize("\n".join(kept))


def _read_raw_text(raw_id: str) -> str:
    path = RAW_DIR / raw_id / "content.txt"
    if not path.exists():
        raise FileNotFoundError(
            f"raw テキストがありません: {path}\n"
            "先に `python scripts/fetch_sources.py` を実行してください。"
        )
    return _normalize(path.read_text(encoding="utf-8"))


def _extract_around_keywords(text: str, keywords: list[str], max_chars: int) -> str:
    # keywords は優先度順。最初にヒットした語の周辺を切り出す。
    best_idx = -1
    best_key = ""
    for key in keywords:
        idx = text.find(key)
        if idx >= 0:
            best_idx = idx
            best_key = key
            break
    if best_idx < 0:
        return text[:max_chars].strip()

    start = max(0, best_idx - 80)
    end = min(len(text), start + max_chars)
    snippet = text[start:end].strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet = snippet + "…"
    if best_key and best_key not in snippet:
        snippet = f" (抽出キー: {best_key}) \n{snippet}"
    return snippet


def build_chunks(max_chunks: int | None = None) -> list[dict]:
    chunks: list[dict] = []
    for spec in CHUNK_SPECS:
        if max_chunks is not None and len(chunks) >= max_chunks:
            break

        if spec["mode"] == "curated_ju":
            text = (
                "江戸時代の会津藩では、藩校・日新館に入学する前の子どもたちが "
                "武士としての心構えを学ぶための規則として「什の掟」がありました。\n"
                f"{JU_NO_OKITE_TEXT}\n"
                "会津若松市では、この伝統的な規範意識を踏まえ、"
                "青少年健全育成の共通指針「あいづっこ宣言」が策定されています。"
            )
        elif spec["mode"] == "from_raw":
            raw_text = _strip_pdf_noise(_read_raw_text(spec["raw_id"]))
            text = _extract_around_keywords(
                raw_text,
                keywords=list(spec["keywords"]),
                max_chars=int(spec["max_chars"]),
            )
            text = _strip_pdf_noise(text)
        else:
            raise ValueError(f"Unknown mode: {spec['mode']}")

        chunks.append(
            {
                "id": spec["id"],
                "title": spec["title"],
                "text": _normalize(text),
                "source": spec["source"],
                "url": spec["url"],
            }
        )
    return chunks


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build knowledge.json for in-memory RAG"
    )
    parser.add_argument(
        "--max-chunks",
        type=int,
        default=None,
        help="デモ向けにチャンク数を制限 (例: 3)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="ファイル書き込みせず内容だけ表示",
    )
    args = parser.parse_args()

    # Ensure sources.yaml exists (sanity)
    if not SOURCES_PATH.exists():
        print(f"sources.yaml がありません: {SOURCES_PATH}", file=sys.stderr)
        return 1
    _ = yaml.safe_load(SOURCES_PATH.read_text(encoding="utf-8"))

    chunks = build_chunks(max_chunks=args.max_chunks)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "disclaimer": (
            "本ファイルは会津若松市公式サイト等の公開情報をデモ用途で抽出・要約したローカルデータです。"
            "著作権に留意し、再配布・公開リポジトリへのコミットは行わないでください。"
        ),
        "chunk_count": len(chunks),
        "chunks": chunks,
    }

    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.dry_run:
        print(rendered)
        return 0

    KNOWLEDGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    KNOWLEDGE_PATH.write_text(rendered, encoding="utf-8")
    print(f"Wrote {KNOWLEDGE_PATH} ({len(chunks)} chunks)")
    for chunk in chunks:
        print(f"  - {chunk['id']}: {chunk['title']} ({len(chunk['text'])} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
