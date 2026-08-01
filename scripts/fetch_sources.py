#!/usr/bin/env python3
"""公式サイトからデモ用ソースを取得する (著作権あり → raw/ は gitignore)。"""

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import httpx
import yaml
from bs4 import BeautifulSoup
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.config import DATA_DIR, RAW_DIR, SOURCES_PATH

USER_AGENT = "aizu-agent-demo/1.0 (+local educational demo; contact: local)"
TIMEOUT = 60.0


def _slug(source_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", source_id)


def load_sources() -> list[dict]:
    payload = yaml.safe_load(SOURCES_PATH.read_text(encoding="utf-8"))
    return list(payload.get("sources") or [])


def fetch_bytes(url: str) -> bytes:
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    with httpx.Client(
        headers=headers, follow_redirects=True, timeout=TIMEOUT
    ) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.content


def html_to_text(html: bytes) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header"]):
        tag.decompose()
    main = soup.find("main") or soup.find(id="tmp_contents") or soup.body or soup
    text = main.get_text("\n", strip=True)
    # Collapse excessive blank lines
    lines = [line.strip() for line in text.splitlines()]
    compact: list[str] = []
    blank = False
    for line in lines:
        if not line:
            if not blank:
                compact.append("")
            blank = True
            continue
        compact.append(line)
        blank = False
    return "\n".join(compact).strip()


def pdf_to_text(data: bytes) -> str:
    # 一時ファイルを介さずメモリ上で読む (並行実行時の競合と後始末を避ける)
    reader = PdfReader(BytesIO(data))
    pages: list[str] = []
    for i, page in enumerate(reader.pages, start=1):
        page_text = (page.extract_text() or "").strip()
        if page_text:
            pages.append(f"--- page {i} ---\n{page_text}")
    return "\n\n".join(pages).strip()


def save_raw(source: dict, content_bytes: bytes | None, text: str) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out_dir = RAW_DIR / _slug(source["id"])
    out_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "id": source["id"],
        "title": source.get("title"),
        "kind": source.get("kind"),
        "url": source.get("url"),
        "page_url": source.get("page_url"),
        "fetched_at": datetime.now(UTC).isoformat(),
        "notes": source.get("notes"),
        "copyright_notice": (
            "会津若松市公式サイト等の著作物を含む可能性があります。"
            "デモ用途のローカル利用のみを想定し、再配布・コミットはしないでください。"
        ),
    }
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out_dir / "content.txt").write_text(text + "\n", encoding="utf-8")

    if content_bytes is not None:
        suffix = ".pdf" if source.get("kind") == "pdf" else ".html"
        (out_dir / f"original{suffix}").write_bytes(content_bytes)

    return out_dir


def fetch_one(source: dict) -> Path | None:
    kind = source.get("kind")
    if kind == "curated":
        print(f"[skip] curated source (no download): {source['id']}")
        return None

    url = source.get("url")
    if not url:
        print(f"[skip] no url: {source['id']}")
        return None

    print(f"[fetch] {source['id']} <- {url}")
    data = fetch_bytes(url)
    if kind == "pdf":
        text = pdf_to_text(data)
    elif kind == "html":
        text = html_to_text(data)
    else:
        raise ValueError(f"Unknown kind: {kind}")

    if not text.strip():
        raise RuntimeError(f"Extracted empty text for {source['id']}")

    out = save_raw(source, data, text)
    print(f"  -> {out} ({len(text)} chars)")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch official Aizu sources into data/raw/"
    )
    parser.add_argument(
        "--only",
        nargs="*",
        help="Fetch only these source ids",
    )
    args = parser.parse_args()

    sources = load_sources()
    if args.only:
        wanted = set(args.only)
        sources = [s for s in sources if s["id"] in wanted]

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    ok = 0
    for source in sources:
        try:
            result = fetch_one(source)
            if result is not None:
                ok += 1
        except Exception as exc:  # noqa: BLE001
            print(f"[error] {source.get('id')}: {exc}", file=sys.stderr)
            return 1

    print(f"Done. fetched={ok}")
    print("Next: python scripts/build_knowledge.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
