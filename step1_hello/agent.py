"""Step 1: 素の Gemini 疎通確認 (Hello World)."""

from google.adk.agents import Agent

root_agent = Agent(
    name="step1_hello",
    model="gemini-3.6-flash",
    description="素の Gemini との疎通確認用エージェント",
    instruction="あなたは親切なアシスタントです。簡潔に答えてください。",
)
