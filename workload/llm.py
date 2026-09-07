"""Gemini LLM client wrapper.

Single concrete provider: Google Gemini via the official ``google-genai`` SDK.
Model IDs are resolved against a small explicit allowlist so a typo never sends
a request to a non‑existent model. ``safe_llm_call`` keeps the
``(prompt, system_prompt, model_name, ...) -> str`` signature that the agents
already use.
"""
import os
from typing import Optional

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
    "gemini-fast": "gemini-1.5-flash",
    "gemini-pro": "gemini-1.5-pro",
    "gemini-2-flash": "gemini-2.0-flash",
    "gemini-2-flash-lite": "gemini-2.0-flash-lite",
    # Back‑compat aliases kept so existing call sites don't break silently.
    "auto:fast": "gemini-1.5-flash",
    "claude-3-5-sonnet": "gemini-1.5-pro",
    "gpt-4o-mini": "gemini-1.5-flash",
    "fusion": "gemini-1.5-pro",
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
    fallback_model: str = "gemini-pro",
    temperature: float = 0.4,
    max_output_tokens: int = 1024,
) -> str:
    """Call Gemini and return ``response.text``.

    Errors are caught and a single retry against ``fallback_model`` is performed
    before returning a safe stub — same shape as the old FreeLLM wrapper.
    """
    client = get_gemini_client()
    concrete = resolve_model_name(model_name)

    config: dict = {
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
    }
    contents: list = []
    if system_prompt:
        # ``google-genai`` accepts system instructions via the config object.
        config["system_instruction"] = system_prompt
    contents.append(prompt)

    try:
        response = client.models.generate_content(
            model=concrete,
            contents=contents,
            config=config,
        )
        return (response.text or "").strip()
    except genai_errors.APIError as err:
        print(
            f"[Gemini Warning] call to {concrete} failed: {err}. "
            f"Retrying with fallback {fallback_model}."
        )
    except Exception as err:  # network / SDK failures
        print(
            f"[Gemini Warning] call to {concrete} raised {type(err).__name__}: {err}. "
            f"Retrying with fallback {fallback_model}."
        )

    try:
        fallback_concrete = resolve_model_name(fallback_model)
        response = client.models.generate_content(
            model=fallback_concrete,
            contents=contents,
            config=config,
        )
        return (response.text or "").strip()
    except Exception as err:
        print(f"[Gemini Error] fallback {fallback_model} failed: {err}.")
        return "Unable to generate LLM response due to provider unavailability."
