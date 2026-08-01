# 令和の什の掟 AI エージェント

会津若松市の歴史的資源「什の掟」と Gemini / Google ADK を使い、地域課題 (若者流出・地域参加) とスマートシティの文脈をつなぐデモ用エージェントです。

## デモ構成

| Step | アプリ名        | 内容                                        |
| ---- | --------------- | ------------------------------------------- |
| 1    | `step1_hello`   | 素の Gemini (Hello World)                   |
| 2    | `step2_persona` | 什の掟 × 会津弁のシステムプロンプト         |
| 3    | `step3_rag`     | ペルソナ + In-Memory FAISS RAG (検索ツール) |
| 4    | Cloud Run       | `adk deploy cloud_run` で参加者に URL 共有  |

## 技術スタック

- Python 3.11 / uv (`pyproject.toml` + `uv.lock`)
  - `adk deploy cloud_run` が生成する Dockerfile が `python:3.11-slim` 固定のため、
    ローカルも 3.11 に揃えている (`.python-version`)。3.12+ でロックすると
    コンテナ内の `pip install` が解決できずデプロイが失敗する
- `google-adk==2.6.1`
- LLM: `gemini-3.6-flash`
- Embedding: `gemini-embedding-001`
- RAG: FAISS (インメモリ) + Vertex Embedding
- 認証: **Vertex AI + ADC のみ (APIキー禁止)**
- デプロイ: `adk deploy cloud_run` (推奨) / リージョン `asia-northeast1`、モデル loc は `global`

## セットアップ

```bash
uv sync
cp .env.example .env
vi .env

gcloud auth application-default login
gcloud config set project "$GOOGLE_CLOUD_PROJECT"

# ADC に quota project を設定する (未設定だと実行時に
# "quota exceeded" / "API not enabled" を誘発することがある)
gcloud auth application-default set-quota-project "$GOOGLE_CLOUD_PROJECT"
```

`GOOGLE_API_KEY` / `GEMINI_API_KEY` は設定しないでください。

## デモ中のデータ作成

市公式ドキュメントの本文・PDF 抽出結果・生成済み `knowledge.json` は **gitignore** しています。
リポジトリに含まれるのは URL 定義 (`shared/data/sources.yaml`) とスキーマ例のみです。

```bash
uv run python scripts/fetch_sources.py
uv run python scripts/build_knowledge.py
# デモ向けに絞る場合:
# uv run python scripts/build_knowledge.py --max-chunks 3
```

## ローカル起動 (ADK WebUI)

```bash
uv run adk web
```

### ポイント

1. **アプリ切替**: 左ペインで `step1_hello` → `step2_persona` → `step3_rag`
2. **トレース / Events**: Step3 で質問すると、`search_ju_knowledge` の呼び出し
   (検索クエリ・ヒットしたチャンク・スコア) がイベントとして見える
3. **ペルソナの維持**: Step3 でも会津弁のまま出典付きで答える。
   知識検索を*サブエージェントへの委任*ではなく*ツール*にしているのがポイント
   (委任すると制御がサブエージェント側へ移り、以降ペルソナが失われる)
4. **軌跡テスト (Eval) **:
   - WebUI の Eval から `ju_rag_demo` / `persona_demo` を実行
   - または CLI:

```bash
uv run adk eval step3_rag step3_rag/ju_rag_demo.evalset.json --config_file_path eval_config.json
uv run adk eval step2_persona step2_persona/persona_demo.evalset.json --config_file_path eval_config.json
```

`--config_file_path` を省くと ADK の既定基準
(`tool_trajectory_avg_score=1.0` / `response_match_score=0.8`) が使われ、**必ず失敗します**。
既定の軌跡スコアはツール引数の完全一致を要求しますが、検索クエリは LLM が毎回自由に生成するためです。
また応答一致スコアは会津弁の自由記述では実測 0.20〜0.28 程度で、0.8 には到達しません。
`eval_config.json` には回帰検知に使える現実的な下限のみを設定しています
(ツール呼び出しの軌跡そのものは WebUI の Events タブで目視するのが本デモの主目的)。

### おすすめ質問

1. Step1/2: 「会津若松で若者が地域に関わるには？」
2. Step3: 「什の掟を今のまちづくりにどう活かす？」
3. Step3: 「スマートシティ会津若松って何？」
4. Step3: 「若者の人口流出について、第 7 次と第 8 次素案ではどう書かれている？」

## Cloud Run デプロイ

### デプロイ

```bash
export GOOGLE_CLOUD_PROJECT=your-gcp-project-id
export GOOGLE_CLOUD_LOCATION=global
export GOOGLE_CLOUD_REGION=asia-northeast1

./scripts/deploy.sh
```

事前に Vertex AI API 有効化と、実行 SA への `roles/aiplatform.user` 付与が必要です。

### 公開範囲と後片付け

参加者にその場で触ってもらうため、`--allow-unauthenticated` で**認証なしの一般公開**として
デプロイします。URL を知る全員が Gemini を呼べる状態になり、利用量はプロジェクトに課金されます。

**デモ終了後は削除してください:**

```bash
gcloud run services delete "$SERVICE_NAME" --region "$GOOGLE_CLOUD_REGION" --project "$GOOGLE_CLOUD_PROJECT"
```

## ディレクトリ

```
.
├── pyproject.toml / uv.lock
├── step1_hello/
├── step2_persona/
│   └── persona_demo.evalset.json
├── step3_rag/
│   ├── agent.py
│   └── ju_rag_demo.evalset.json
├── shared/
│   ├── config.py
│   ├── prompts.py
│   ├── rag.py
│   └── data/sources.yaml
├── scripts/
│   ├── fetch_sources.py
│   ├── build_knowledge.py
│   ├── export_requirements.sh
│   └── deploy.sh
└── .env.example
```
