#!/usr/bin/env bash
# step1_hello または step3_rag (+ shared) を ADK 推奨の `adk deploy cloud_run` でデプロイする
#  (APIキー不使用 / Vertex AI + ADC)
#
# 使い方:
#   ./scripts/deploy.sh              # デフォルト: step3_rag をデプロイ
#   ./scripts/deploy.sh step1_hello  # step1_hello をデプロイ
#
# 注意: 本スクリプトはライブデモ用に Cloud Run サービスを *一般公開* します
#       (--allow-unauthenticated)。URL を知る全員が Gemini を呼べる状態になり、
#       利用量はプロジェクトに課金されます。デモ終了後は必ず削除してください
#       (実行後に表示される gcloud run services delete コマンド)。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

STEP="${1:-step3_rag}"
case "$STEP" in
  step1_hello|step3_rag) ;;
  *)
    echo "ERROR: 不明なデプロイ対象です: $STEP (step1_hello または step3_rag を指定してください)"
    exit 1
    ;;
esac

: "${GOOGLE_CLOUD_PROJECT:?GOOGLE_CLOUD_PROJECT を設定してください}"
REGION="${GOOGLE_CLOUD_REGION:-asia-northeast1}"
SERVICE_NAME="${SERVICE_NAME:-aizu-agent}"
MODEL_LOCATION="${GOOGLE_CLOUD_LOCATION:-global}"
MODEL_NAME="${GEMINI_MODEL:-gemini-3.6-flash}"
EMBED_NAME="${EMBEDDING_MODEL:-gemini-embedding-001}"

MAX_INSTANCES="${MAX_INSTANCES:-3}"
MIN_INSTANCES="${MIN_INSTANCES:-0}"

if [[ "$STEP" == "step3_rag" && ! -f "shared/data/knowledge.json" ]]; then
  echo "ERROR: shared/data/knowledge.json がありません。"
  echo "先にデモ用データを作成してください:"
  echo "  uv run python scripts/fetch_sources.py"
  echo "  uv run python scripts/build_knowledge.py"
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: uv が必要です。"
  exit 1
fi

if ! command -v adk >/dev/null 2>&1 && ! uv run adk --version >/dev/null 2>&1; then
  echo "ERROR: adk CLI が必要です。uv sync 後に再実行してください。"
  exit 1
fi

# デプロイ直前に requirements.txt を生成
./scripts/export_requirements.sh

STAGE="$(mktemp -d "${TMPDIR:-/tmp}/aizu-agent-deploy.XXXXXX")"
cleanup() { rm -rf "$STAGE"; }
trap cleanup EXIT

echo "[stage] $STAGE"
# adk deploy は agent ディレクトリ単位でパッケージする
mkdir -p "$STAGE/$STEP"
cp -R "$STEP/." "$STAGE/$STEP/"

if [[ "$STEP" == "step3_rag" ]]; then
  # step3_rag は shared (RAG 検索ツール等) に依存するため同梱する
  cp -R shared "$STAGE/$STEP/shared"
  rm -rf "$STAGE/$STEP/shared/data/raw"
fi

cp requirements.txt "$STAGE/$STEP/requirements.txt"

# google-genai 2.x の正式な環境変数は GOOGLE_GENAI_USE_ENTERPRISE。
# (GOOGLE_GENAI_USE_VERTEXAI は後方互換の旧名。両方あると ENTERPRISE が優先される)
cat > "$STAGE/$STEP/.env" <<EOF
GOOGLE_GENAI_USE_ENTERPRISE=true
GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT}
GOOGLE_CLOUD_LOCATION=${MODEL_LOCATION}
GEMINI_MODEL=${MODEL_NAME}
EMBEDDING_MODEL=${EMBED_NAME}
EOF

echo "[deploy] step=${STEP}"
echo "[deploy] project=${GOOGLE_CLOUD_PROJECT} region=${REGION} service=${SERVICE_NAME}"
echo "[deploy] model=${MODEL_NAME} location=${MODEL_LOCATION}"
echo "[deploy] instances: min=${MIN_INSTANCES} max=${MAX_INSTANCES}"
echo "[deploy] 認証なしの一般公開 (--allow-unauthenticated) でデプロイします"

ADK_BIN=(adk)
if ! command -v adk >/dev/null 2>&1; then
  ADK_BIN=(uv run adk)
fi

# `--` 以降は gcloud run deploy にそのまま渡される。
# 既存の env をすべて置き換える --set-env-vars ではなく --update-env-vars を使う。
"${ADK_BIN[@]}" deploy cloud_run \
  --project="$GOOGLE_CLOUD_PROJECT" \
  --region="$REGION" \
  --service_name="$SERVICE_NAME" \
  --with_ui \
  "$STAGE/$STEP" \
  -- \
  --allow-unauthenticated \
  --min-instances="$MIN_INSTANCES" \
  --max-instances="$MAX_INSTANCES" \
  --update-env-vars="GOOGLE_GENAI_USE_ENTERPRISE=true,GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT},GOOGLE_CLOUD_LOCATION=${MODEL_LOCATION},GEMINI_MODEL=${MODEL_NAME},EMBEDDING_MODEL=${EMBED_NAME}"

cat <<EOF

Deploy requested.
- Cloud Run 実行 SA に roles/aiplatform.user があること
- デモ向けに --with_ui を付けています (ADK Web UI は開発用途。恒久運用は非推奨)
- 認証なしで公開中です。URL を知る全員がアクセスできます

デモ終了後は必ず削除してください:
  gcloud run services delete ${SERVICE_NAME} --region ${REGION} --project ${GOOGLE_CLOUD_PROJECT}
EOF
