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

# Concrete aliases. Keep this list short and explicit — every agent picks one.
GEMINI_MODEL_ALIASES: dict[str, str] = {
    "gemini-fast": "gemini-3.8-flash",
    "gemini-pro": "gemini-3.8-flash",
    "gemini-2-flash": "gemini-3.8-flash",
    "gemini-2-flash-lite": "gemini-3.8-flash",
    # Back‑compat aliases kept so existing call sites don't break silently.
    "auto:fast": "gemini-3.8-flash",
    "claude-3-5-sonnet": "gemini-3.8-flash",
    "gpt-4o-mini": "gemini-3.8-flash",
    "fusion": "gemini-3.8-flash",
}


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


def safe_llm_call(
    prompt: str,
    system_prompt: Optional[str] = None,
    model_name: str = "gemini-fast",
    fallback_models: Optional[list[str]] = None,
    temperature: float = 0.4,
    max_output_tokens: int = 1024,
    max_retries: int = 5,
    backoff_seconds: int = 10,
) -> str:
    """Call Gemini, with exponential backoff and multiple fallbacks.

    The call will attempt ``model_name`` up to ``max_retries`` times, sleeping
    ``backoff_seconds`` between attempts.  If all attempts fail with a
    ``503 UNAVAILABLE`` (or network errors), we sequentially fall back to the
    provided ``fallback_models`` list.  If none succeed, a hard‑coded error
    message is returned.
    """
    client = get_gemini_client()
    concrete = resolve_model_name(model_name)
    fallback_models = fallback_models or ["gemini-pro", "gemini-fast"]

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
            # Treat 503 as transient
            if code == 503:
                return None
            print(f"[Gemini Warning] call to {model} failed: {msg} (code {code}).")
            return None
        except Exception as err:
            print(f"[Gemini Warning] call to {model} raised {type(err).__name__}: {err}.")
            return None

    # First try the primary model with retries
    for i in range(max_retries):
        result = _attempt(concrete)
        if result:
            return result
        print(f"[Gemini Warning] retry {i+1}/{max_retries} for {concrete}.")
        time.sleep(backoff_seconds)

    # Fallback chain
    for fb in fallback_models:
        concrete_fb = resolve_model_name(fb)
        for i in range(max_retries):
            result = _attempt(concrete_fb)
            if result:
                return result
            print(f"[Gemini Warning] retry {i+1}/{max_retries} for fallback {concrete_fb}.")
            time.sleep(backoff_seconds)

    # All attempts failed
    print("[Gemini Error] All model attempts failed. Returning error stub.")
    return "Unable to generate LLM response due to provider unavailability."
