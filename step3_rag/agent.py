"""Step 3: ペルソナ + In-Memory FAISS RAG (ベクトル検索ツール)."""

import sys
from pathlib import Path

# Cloud Run 上で `shared` を import 可能にするための橋渡し。
_HERE = Path(__file__).resolve().parent
if (_HERE / "shared").is_dir() and str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from google.adk.agents import Agent

from shared.config import LLM_MODEL
from shared.prompts import build_persona_instruction
from shared.rag import search_ju_knowledge

root_agent = Agent(
    name="step3_rag",
    model=LLM_MODEL,
    description=(
        "令和の什の掟エージェント。会津弁ペルソナを保ったまま、"
        "会津若松市公式知識をベクトル検索して出典付きで答える。"
    ),
    instruction=build_persona_instruction(with_rag=True),
    tools=[search_ju_knowledge],
)
