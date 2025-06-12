"""
utils.tokens
============
Lightweight helper that estimates token length for any text
without forcing every caller to import `tiktoken` directly.
"""

from __future__ import annotations

try:
    import tiktoken                                      # type: ignore
    _enc = tiktoken.get_encoding("cl100k_base")

    def n_tokens(text: str) -> int:                      # noqa: D401
        """Return approximate token count using cl100k_base."""
        return len(_enc.encode(text))

except (ImportError, Exception):
    # Fallback: 1 token per ~4 chars (coarse but safe)
    def n_tokens(text: str) -> int:                      # type: ignore[override]
        """Coarse token estimator used when *tiktoken* unavailable."""
        return max(1, len(text) // 4)
