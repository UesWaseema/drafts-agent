"""
Initialise LiteLLM Redis-backed prompt cache.
Works on ≥1.70; falls back gracefully on older versions.
"""
import os, redis, litellm

# ─── Redis connection ────────────────────────────────────────────────
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=int(os.getenv("REDIS_DB", 0)),
    password=os.getenv("REDIS_PASSWORD") or None,
)

# ─── LiteLLM cache wiring ────────────────────────────────────────────
try:                               # new API (≥1.70)
    from litellm.caching.caching import Cache
    litellm.cache = Cache(type="redis", redis_client=redis_client)
except (ImportError, AttributeError):
    # old API (<1.70) – only if you decide to stay there
    if hasattr(litellm, "set_cache"):
        litellm.set_cache("redis", redis_client=redis_client)
    else:
        raise RuntimeError(
            "LiteLLM cache API not found – check package version."
        )
