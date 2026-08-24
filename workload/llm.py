"""LLM client wrapper supporting FreeLLM API (OpenAI compatible at http://localhost:3001/v1)
with model auto-routing, failover resilience, and multi-LLM configuration per step.
"""
import os
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

# OpenInference auto‑instrumentation for LangChain – emits gen_ai.* spans for all LLM calls
from openinference.instrumentation.langchain import LangChainInstrumentor

# Instrumentation is performed once at import time to ensure all subsequent LangChain operations are traced.
_LangChainInstrumentor = LangChainInstrumentor()
_LangChainInstrumentor.instrument()


FREELLM_BASE_URL = os.getenv("FREELLM_BASE_URL", "http://localhost:3001/v1")
# Load .env to get the FreeLLM API key
from dotenv import load_dotenv
load_dotenv()
FREELLM_API_KEY = os.getenv("FREE_LLM_API", "freellmapi-default-key")


def get_freellm_chat_model(
    model_name: str = "auto:fast",
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
) -> ChatOpenAI:
    """Instantiate a ChatOpenAI model configured to talk to the FreeLLM API proxy.

    FreeLLM API model routing options:
    - 'auto' or 'auto:fast': Automatic model routing across free providers with auto-failover
    - 'fusion': Multi-model synthesis judge model
    - Specific model names e.g. 'gpt-4o-mini', 'claude-3-5-sonnet', 'gemini-1.5-flash'
    """
    return ChatOpenAI(
        model=model_name,
        openai_api_base=FREELLM_BASE_URL,
        openai_api_key=FREELLM_API_KEY,
        temperature=temperature,
        max_tokens=max_tokens,
        max_retries=3,
        request_timeout=30.0,
    )


def safe_llm_call(
    prompt: str,
    system_prompt: Optional[str] = None,
    model_name: str = "auto:fast",
    fallback_model: str = "auto",
) -> str:
    """Safe wrapper around LLM invocation that catches runtime / network / API errors
    and falls back to an alternative model or safe default response.
    """
    try:
        model = get_freellm_chat_model(model_name=model_name)
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))

        response = model.invoke(messages)
        return str(response.content)
    except Exception as err:
        print(f"[FreeLLM Warning] LLM call with {model_name} failed: {err}. Retrying with fallback {fallback_model}...")
        try:
            fallback = get_freellm_chat_model(model_name=fallback_model)
            messages = []
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            messages.append(HumanMessage(content=prompt))
            res = fallback.invoke(messages)
            return str(res.content)
        except Exception as fallback_err:
            print(f"[FreeLLM Error] Fallback model failed: {fallback_err}. Returning safe fallback response.")
            return "Unable to generate LLM response due to provider unavailability."
