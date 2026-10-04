"""Catalyst CLI entrypoint using Typer for subcommands."""

import os
import typer
from cli.commands.run import run as run_command
from cli.commands.reset import cmd_reset
from cli.commands.eval import cmd_eval
from cli.commands.feed import feed as feed_command

# Initialize Phoenix OpenTelemetry tracing early so spans are exported to Phoenix
def _init_phoenix_tracing():
    """Register Phoenix as the OTel tracer provider to export spans."""
    try:
        from phoenix.otel import register
        from opentelemetry import trace

        # Check if a tracer provider is already set (to avoid double instrumentation)
        if trace.get_tracer_provider().__class__.__name__ != "ProxyTracerProvider":
            return  # Already initialized

        # Get Phoenix endpoint from env or default
        endpoint = os.getenv("PHOENIX_OTEL_ENDPOINT") or os.getenv("PHOENIX_BASE_URL", "http://localhost:6006")
        # Ensure endpoint has /v1/traces for OTLP
        if not endpoint.endswith("/v1/traces"):
            endpoint = endpoint.rstrip("/") + "/v1/traces"
        register(
            endpoint=endpoint,
            project_name=os.getenv("PHOENIX_PROJECT", "catalyst"),
            set_global_tracer_provider=True,
            auto_instrument=True,
            batch=True,
        )

        # Explicitly instrument Google GenAI so LLM spans carry
        # llm.token_count.prompt/completion/total, llm.model_name, llm.provider
        # and openinference.span.kind = "LLM" (needed for Cost / Token / LLM dashboards).
        try:
            from openinference.instrumentation.google_genai import GoogleGenAIInstrumentor
            GoogleGenAIInstrumentor().instrument()
        except Exception:
            pass  # instrumentation is optional

        # Add instrumentation for google.genai.chats (Chat API) since
        # GoogleGenAIInstrumentor doesn't wrap Chats.create or Chat.send_message.
        try:
            _instrument_genai_chats()
        except Exception:
            pass

        # Instrument LangChain so agent/tool spans get openinference.span.kind = "TOOL"
        try:
            from openinference.instrumentation.langchain import LangChainInstrumentor
            LangChainInstrumentor().instrument()
        except Exception:
            pass

        # Instrument plain Python tool functions to emit TOOL spans
        try:
            _instrument_tools()
        except Exception:
            pass
    except Exception:
        # Graceful degradation - tracing is optional
        pass

def _instrument_genai_chats():
    """Instrument google.genai.chats.Chats.create and google.genai.chats.Chat.send_message
    to emit LLM spans with token counts, model name, and span kind = LLM.
    """
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode
    from opentelemetry.instrumentation.utils import unwrap
    from wrapt import wrap_function_wrapper
    from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes
    import os

    tracer = trace.get_tracer("catalyst.genai.chats", "0.1.0")

    def _set_llm_span_attributes(span, model_name=None, prompt_tokens=None, completion_tokens=None, total_tokens=None):
        """Set standard LLM span attributes."""
        if model_name:
            span.set_attribute(SpanAttributes.LLM_MODEL_NAME, model_name)
            span.set_attribute(SpanAttributes.LLM_PROVIDER, "google")
        if prompt_tokens is not None:
            span.set_attribute(SpanAttributes.LLM_TOKEN_COUNT_PROMPT, prompt_tokens)
        if completion_tokens is not None:
            span.set_attribute(SpanAttributes.LLM_TOKEN_COUNT_COMPLETION, completion_tokens)
        if total_tokens is not None:
            span.set_attribute(SpanAttributes.LLM_TOKEN_COUNT_TOTAL, total_tokens)
        span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, OpenInferenceSpanKindValues.LLM.value)

    def _wrap_chats_create(wrapped, instance, args, kwargs):
        """Wrap Chats.create to capture model name and start a span."""
        model_name = kwargs.get('model') or (args[0] if args else None)
        span_name = f"GenAI Chats.create {model_name}" if model_name else "GenAI Chats.create"
        with tracer.start_as_current_span(span_name) as span:
            _set_llm_span_attributes(span, model_name=model_name)
            try:
                result = wrapped(*args, **kwargs)
                return result
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise

    def _wrap_chat_send_message(wrapped, instance, args, kwargs):
        """Wrap Chat.send_message to capture prompt/completion tokens."""
        prompt = args[0] if args else kwargs.get('message', '')
        span_name = f"GenAI Chat.send_message"
        with tracer.start_as_current_span(span_name) as span:
            _set_llm_span_attributes(span, model_name=getattr(instance, '_model', None))
            try:
                result = wrapped(*args, **kwargs)
                # Extract token usage from response if available
                if hasattr(result, 'usage_metadata'):
                    usage = result.usage_metadata
                    if usage:
                        _set_llm_span_attributes(
                            span,
                            model_name=getattr(instance, '_model', None),
                            prompt_tokens=getattr(usage, 'prompt_token_count', None),
                            completion_tokens=getattr(usage, 'candidates_token_count', None),
                            total_tokens=getattr(usage, 'total_token_count', None),
                        )
                return result
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise

    # Wrap Chats.create
    try:
        from google.genai.chats import Chats
        wrap_function_wrapper(Chats, 'create', _wrap_chats_create)
    except Exception:
        pass

    # Wrap Chat.send_message
    try:
        from google.genai.chats import Chat
        wrap_function_wrapper(Chat, 'send_message', _wrap_chat_send_message)
    except Exception:
        pass


def _instrument_tools():
    """Instrument plain Python tool functions to emit TOOL spans.
    These are not LangChain tools, so LangChainInstrumentor doesn't catch them.
    """
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode
    from wrapt import wrap_function_wrapper
    from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes

    tracer = trace.get_tracer("catalyst.tools", "0.1.0")

    def _wrap_tool(wrapped, instance, args, kwargs):
        tool_name = getattr(wrapped, '__name__', 'unknown_tool')
        span_name = f"Tool {tool_name}"
        with tracer.start_as_current_span(span_name) as span:
            span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, OpenInferenceSpanKindValues.TOOL.value)
            span.set_attribute(SpanAttributes.TOOL_NAME, tool_name)
            # Capture input arguments (sanitized)
            try:
                import json
                span.set_attribute(SpanAttributes.TOOL_PARAMETERS, json.dumps(args, default=str))
            except Exception:
                pass
            try:
                result = wrapped(*args, **kwargs)
                return result
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise

    # Instrument known tool functions in their modules
    try:
        import workload.tools as tools_module
        for name in ['fetch_issue_context', 'fetch_pr_data', 'run_code_analysis', 'fetch_referenced_docs']:
            try:
                if hasattr(tools_module, name):
                    wrap_function_wrapper(tools_module, name, _wrap_tool)
            except Exception:
                pass
    except Exception:
        pass

    # Instrument MCP class methods
    try:
        import workload.tools.mcp as mcp_module
        for method_name in ['set', 'get', 'read_file', 'write_file', 'create_file', 'delete_file',
                            'list_directory', 'move_file', 'search_files', 'grep_codebase',
                            'get_symbol_definition', 'get_symbol_references', 'get_file_outline',
                            'run_command', 'run_tests', 'run_linter', 'run_type_checker',
                            'install_dependency', 'get_diagnostics', 'get_hover_info',
                            'format_file', 'search_docs', 'fetch_url', 'read_pr_diff',
                            'git_status', 'git_diff', 'git_log', 'git_blame', 'git_show',
                            'git_branch', 'git_add', 'git_commit']:
            try:
                if hasattr(mcp_module.MCP, method_name):
                    wrap_function_wrapper(mcp_module.MCP, method_name, _wrap_tool)
            except Exception:
                pass
    except Exception:
        pass

# Initialize tracing before any other imports that might create spans
_init_phoenix_tracing()

cli = typer.Typer(add_completion=False)

# Detailed command registration

cli.command(name="run", help=(
    "Execute a random task against the orchestration.\n\n"
    "A task is chosen at random from the built‑in catalog (see `workload/prompts/templates.py`). "
    "The task description becomes the issue text for the triage agent, which routes the work to the "
    "appropriate downstream agent. No arguments are required; a unique run identifier is generated internally."
))(run_command)

cli.command(name="feed", help=(
    "Manage the task catalog that drives `run` and `eval`.\n\n"
    "Use one of three modes:\n"
    "  • rewrite – replace the entire catalog with a JSON source.\n"
    "  • append  – merge new tasks from a JSON source into the catalog.\n"
    "  • clear   – empty the catalog.\n\n"
    "Provide the JSON source via --source (ignored for `clear`). Each entry must contain at least: description, failure_mode, env_var."
))(feed_command)

@cli.command(name="reset", help=(
    "Reset Catalyst to a clean state.\n\n"
    "Clears Phoenix traces, AgentOps sessions, and any cached fixtures. Safe to run between experiments."
))
def reset():
    cmd_reset()

@cli.command(name="eval", help=(
    "Run a single task with a random chance of injecting its failure mode.\n\n"
    "Specify --task-id, --fixture, and --run-id to run a specific task with a fixture."
))
def eval(
    task_id: str = typer.Option(..., help="Task identifier"),
    fixture: str = typer.Option(..., help="Path to fixture JSON file"),
    run_id: str = typer.Option(..., help="Run identifier"),
):
    cmd_eval(task_id=task_id, fixture=fixture, run_id=run_id)

def main():
    cli()
