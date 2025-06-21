"""
Central registry of LLMs used by qc_ai.py.
Each entry is a 2-tuple: (model_name, provider).

provider values
---------------
"openrouter" → call goes to https://openrouter.ai
               (needs OPENROUTER_API_KEY; OpenRouter adds your BYO
                OPENAI_API_KEY upstream where required)

Override at runtime
-------------------
export QC_AI_MODEL_LIST='[
  ["openai/gpt-4.1-2025-04-14","openrouter"],
  ["openai/gpt-4o-2024-08-06","openrouter"],
  ["google/gemini-2.5-pro-preview-06-05","openrouter"],
  ["deepseek/deepseek-r1-0528","openrouter"],
  ["openai/o3","openrouter"]
]'
"""

import json, os

# Default roster (all via OpenRouter; o3 is prefixed with openai/)
DEFAULT_MODELS = [
    #("openai/gpt-4.1-2025-04-14",         "openrouter"),
    #("openai/gpt-4o-2024-08-06",          "openrouter"),
    #("google/gemini-2.5-pro-preview-06-05","openrouter"),
    ("deepseek/deepseek-r1-0528",         "openrouter"),
    #("openai/o3",                         "openrouter"),
]

# Allow env override while preserving (model, provider) tuple structure
MODEL_LIST = [
    tuple(entry) for entry in json.loads(
        os.getenv("QC_AI_MODEL_LIST", json.dumps(DEFAULT_MODELS))
    )
]
