"""Step 2: 什の掟 × 会津弁のシステムプロンプト注入."""

from google.adk.agents import Agent

from shared.config import LLM_MODEL
from shared.prompts import build_persona_instruction

root_agent = Agent(
    name="step2_persona",
    model=LLM_MODEL,
    description="什の掟 × 会津人のペルソナを注入したエージェント",
    instruction=build_persona_instruction(with_rag=False),
)
