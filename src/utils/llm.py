"""
utils/llm.py
------------
 • Pure-OpenRouter LangChain wrapper (no Gemini fallback).
 • Exposes `.bind()` so CrewAI works.
"""

from __future__ import annotations
import os
from typing import Any, List, Mapping, Optional
from dotenv import load_dotenv

from langchain_core.language_models.llms import BaseLLM
from langchain_core.outputs import LLMResult
from litellm import completion

# ------------------------------------------------------------------ #
#  Environment
# ------------------------------------------------------------------ #
load_dotenv()                               # loads .env in container
OR_KEY = os.getenv("OPENROUTER_API_KEY")    # **required**

# ------------------------------------------------------------------ #
#  LangChain-compatible LLM
# ------------------------------------------------------------------ #
class OpenRouterLLM(BaseLLM):
    model:       str   = "openrouter/google/gemini-2.5-flash-preview-05-20"
    api_key:     str   = OR_KEY or ""
    base_url:    str   = "https://openrouter.ai/api/v1"
    temperature: float = 0.7

    # ---- LangChain plumbing ----
    @property
    def _llm_type(self) -> str:
        return "openrouter_litellm"

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        return {
            "model": self.model,
            "temperature": self.temperature,
            "base_url": self.base_url,
        }

    # ---- generation ----
    def _generate(
        self,
        prompts: List[str],
        stop: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> LLMResult:
        if not self.api_key:
            raise RuntimeError("OPENROUTER_API_KEY missing")

        gens = []
        for prompt in prompts:
            resp = completion(
                model       = kwargs.get("model", self.model),
                api_key     = self.api_key,
                base_url    = self.base_url,
                messages    = [{"role": "user", "content": prompt}],
                temperature = kwargs.get("temperature", self.temperature),
                stop        = stop,
            )
            gens.append([{"text": resp.choices[0].message.content}])
        return LLMResult(generations=gens)

# singleton used everywhere
openrouter_llm = OpenRouterLLM()
