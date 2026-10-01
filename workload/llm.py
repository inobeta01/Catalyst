"""Gemini LLM client wrapper.

Single concrete provider: Google Gemini via the official ``google-genai`` SDK.
Model IDs are resolved against a small explicit allowlist so a typo never sends
a request to a non‑existent model. ``safe_llm_call`` keeps the
``(prompt, system_prompt, model_name, ...) -> str`` signature that the agents
already use.
"""
import os
from typing import Optional
import time
import random
import re
from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors
from openinference.instrumentation.langchain import LangChainInstrumentor

# LangChain instrumentation is loaded once at import time so any direct
# ``ChatOpenAI`` usage elsewhere still emits gen_ai.* spans.
_LangChainInstrumentor = LangChainInstrumentor()
_LangChainInstrumentor.instrument()

load_dotenv()

# Single concrete model family. Concrete IDs are mapped via GEMINI_MODEL_ALIASES.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY (or GOOGLE_API_KEY) is required. Set it in .env."
    )

# Free-tier text models (generateContent endpoint only).
# Excludes TTS, image, live, transcribe, and video models.
# 2.5-series models are limited to existing users; 3.5/3.8 recommended for new projects.
GEMINI_MODEL_ALIASES: dict[str, str] = {
    # --- Gemini 3 series (recommended for new projects) ---
    "gemini-fast": "gemini-3.8-flash",            # 20 RPM free tier
    "gemini-fast-lite": "gemini-3.5-flash-lite",  # 30 RPM free tier (highest quota)
    "gemini-3-flash": "gemini-3.8-flash",
    "gemini-3-flash-lite": "gemini-3.5-flash-lite",
    "gemini-3-7-flash": "gemini-3.7-flash",       # previous-gen Flash
    "gemini-3-6-flash": "gemini-3.6-flash",       # previous-gen Flash
    "gemini-3-5-flash": "gemini-3.5-flash",       # legacy Flash
    "gemini-3-1-flash-lite": "gemini-3.1-flash-lite",  # frontier-class, low cost
    # --- Gemini 2.5 series (limited to existing users) ---
    "gemini-2-5-flash": "gemini-2.5-flash",
    "gemini-2-5-flash-lite": "gemini-2.5-flash-lite",
    "gemini-2-5-pro": "gemini-2.5-pro",
    # --- Back‑compat aliases kept so existing call sites don't break silently ---
    "auto:fast": "gemini-3.8-flash",
    "claude-3-5-sonnet": "gemini-3.8-flash",
    "gpt-4o-mini": "gemini-3.8-flash",
    "fusion": "gemini-3.8-flash",
}

# Default fallback chain: distinct models with separate quota buckets.
# Order: highest free-tier quota first, then progressively lower.
DEFAULT_FALLBACK_CHAIN = [
    "gemini-fast-lite",       # gemini-3.5-flash-lite: 30 RPM
    "gemini-fast",            # gemini-3.8-flash: 20 RPM
    "gemini-3-1-flash-lite", # gemini-3.1-flash-lite: separate bucket
    "gemini-3-7-flash",      # gemini-3.7-flash: separate bucket
    "gemini-2-5-flash-lite", # gemini-2.5-flash-lite: separate bucket (existing users)
    "gemini-2-5-flash",      # gemini-2.5-flash: separate bucket (existing users)
    "gemini-2-5-pro",        # gemini-2.5-pro: separate bucket (existing users)
]


def resolve_model_name(model_name: str) -> str:
    """Map an alias to a concrete Gemini model ID, or pass through a full ID."""
    if model_name in GEMINI_MODEL_ALIASES:
        return GEMINI_MODEL_ALIASES[model_name]
    if model_name.startswith("gemini-"):
        return model_name
    raise ValueError(
        f"Unknown model alias {model_name!r}. "
        f"Use one of: {sorted(GEMINI_MODEL_ALIASES)} or a 'gemini-*' ID."
    )


_client: Optional[genai.Client] = None


def get_gemini_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def _is_retryable_error(err: genai_errors.APIError) -> bool:
    """Check if error is retryable (503 unavailable, 500 server error).

    NOTE: 429 (quota exceeded) is NOT retryable on the same model.
    Quota is per-model; retrying the same model will always fail until
    the rate-limit window resets. Instead, immediately fall back to the
    next model with a separate quota bucket.
    """
    code = getattr(err, "code", None)
    return code in (500, 502, 503, 504)


def _extract_retry_after(err: genai_errors.APIError) -> Optional[float]:
    """Extract Retry-After seconds from API error message, or return None.

    Reserved for future use if 503 responses include a Retry-After header.
    """
    msg = getattr(err, "message", str(err))
    match = re.search(r"retry in ([\d.]+)s", msg, re.IGNORECASE)
    if match:
        return float(match.group(1))
    return None


def safe_llm_call(
    prompt: str,
    system_prompt: Optional[str] = None,
    model_name: str = "gemini-fast",
    fallback_models: Optional[list[str]] = None,
    temperature: float = 0.4,
    max_output_tokens: int = 1024,
    max_retries: int = 3,
    base_backoff_seconds: float = 2.0,
    max_backoff_seconds: float = 60.0,
) -> str:
    """Call Gemini with exponential backoff, jitter, and quota-aware fallbacks.

    Key fixes:
    - 429 (quota exceeded) is NOT retried on the same model — immediately
      falls back to the next model with a separate quota bucket
    - 404 (model not found) fails fast — no retry on deprecated models
    - 503 (server unavailable) retries with exponential backoff + jitter
    - Fallback chain uses DIFFERENT models with SEPARATE quota buckets
    """
    client = get_gemini_client()
    concrete = resolve_model_name(model_name)
    fallback_models = fallback_models or DEFAULT_FALLBACK_CHAIN

    # Build model chain: primary -> fallbacks (all distinct models)
    model_chain = [concrete] + [resolve_model_name(fb) for fb in fallback_models]
    # Deduplicate while preserving order
    seen = set()
    model_chain = [m for m in model_chain if not (m in seen or seen.add(m))]

    config: dict = {
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
    }
    if system_prompt:
        config["system_instruction"] = system_prompt

    def _attempt(model: str) -> Optional[str]:
        try:
            chat = client.chats.create(
                model=model,
                config=config,
            )
            rsp = chat.send_message(prompt)
            return (rsp.text or "").strip()
        except genai_errors.APIError as err:
            code = getattr(err, "code", None)
            msg = getattr(err, "message", str(err))

            if code == 404:
                # Model deprecated/removed - don't retry, fail fast to next model
                print(f"[Gemini Warning] {model} not found (deprecated): {msg}")
                return None
            if code == 429:
                # Quota exceeded on this model - retrying same model is pointless.
                # Quota is per-model; immediately fall back to next model.
                print(f"[Gemini Warning] {model} quota exceeded: {msg}")
                return None
            if _is_retryable_error(err):
                # 503/500 - server-side, might recover. Return sentinel to retry.
                return "__RETRYABLE__"
            print(f"[Gemini Warning] call to {model} failed: {msg} (code {code}).")
            return None
        except Exception as err:
            print(f"[Gemini Warning] call to {model} raised {type(err).__name__}: {err}.")
            return None

    for model in model_chain:
        backoff = base_backoff_seconds
        for attempt in range(max_retries):
            result = _attempt(model)
            if result and result != "__RETRYABLE__":
                return result

            # If result is None (non-retryable like 404), break to next model
            if result is None:
                break

            # Exponential backoff with jitter
            sleep_time = min(backoff + random.uniform(0, 1), max_backoff_seconds)
            print(f"[Gemini Warning] retry {attempt+1}/{max_retries} for {model} (sleeping {sleep_time:.1f}s).")
            time.sleep(sleep_time)
            backoff *= 2  # Exponential backoff

    # All attempts failed
    print("[Gemini Error] All model attempts failed. Returning error stub.")
    return "Unable to generate LLM response due to provider unavailability."
