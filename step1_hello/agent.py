"""Step 1: 素の Gemini 疎通確認 (Hello World)."""

from google.adk.agents import Agent

from shared.config import LLM_MODEL

root_agent = Agent(
    name="step1_hello",
    model=LLM_MODEL,
    description="素の Gemini との疎通確認用エージェント (キャラクター設定なし)",
    instruction=(
        "あなたは親切なアシスタントです。質問には簡潔かつ一般的な言葉で答えてください。"
    ),
)
