#!/usr/bin/env bash
# デプロイ用 requirements.txt を uv から生成する (成果物は gitignore)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: uv が必要です。 https://docs.astral.sh/uv/ を参照してインストールしてください。"
  exit 1
fi

uv export --no-dev --no-hashes --no-emit-project -o requirements.txt
echo "Wrote $(pwd)/requirements.txt"
