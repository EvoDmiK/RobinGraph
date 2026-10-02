"""Optional, fail-open MLflow tracing for the serving process.

Tracing is off unless ``ROBINGRAPH_MLFLOW_TRACING`` is truthy *and* the
optional ``tracing`` extra (``mlflow-tracing``) is installed.  When off, no
MLflow module is imported and every helper here is a cheap no-op, so API
behavior and latency are unchanged.

When on, startup configures the tracking server and experiment, enables
``mlflow.langchain.autolog`` (which already traces the LCEL evidence and
species-card flows), and enables ``mlflow.gemini.autolog`` when a Google
GenAI SDK is importable.  RobinGraph's own adapters call Jina, Neo4j, and the
Gemini REST endpoint through stdlib/driver code that no autolog integration
patches, so those boundaries open explicit child spans with ``span`` below.

Tracing must never change a response: span creation, attribute writes, and
export failures are swallowed and logged by exception type only.  Attribute
values are redacted by key and truncated so API keys, bearer tokens, and
credential-bearing URIs never reach a trace.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, MutableMapping
from contextlib import contextmanager
from dataclasses import dataclass
import importlib.util
import logging
import os
import sys
from typing import Any
from urllib.parse import urlsplit

_LOGGER = logging.getLogger(__name__)

ENABLE_ENV = "ROBINGRAPH_MLFLOW_TRACING"
DEFAULT_EXPERIMENT_NAME = "robingraph"
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_SUPPORTED_URI_SCHEMES = frozenset({"http", "https", "databricks"})
# MLflow's client defaults retry for minutes; a down tracking server must not
# hold API startup hostage.  Operators can still override either value.
_BOUNDED_HTTP_DEFAULTS = {"MLFLOW_HTTP_REQUEST_MAX_RETRIES": "2", "MLFLOW_HTTP_REQUEST_TIMEOUT": "10"}
_SENSITIVE_KEY_PARTS = (
    "api_key", "apikey", "api-key", "private_key", "secret", "password", "passwd",
    "authorization", "credential", "bearer", "cookie",
)
_MAX_TEXT = 2_000
_MAX_ITEMS = 50

# OpenInference/MLflow span types used by RobinGraph's manual spans.
CHAIN = "CHAIN"
RETRIEVER = "RETRIEVER"
EMBEDDING = "EMBEDDING"
LLM = "LLM"
TOOL = "TOOL"


@dataclass(frozen=True)
class TracingStatus:
    enabled: bool
    reason: str
    langchain_autolog: bool = False
    gemini_autolog: bool = False


_mlflow: Any = None
_status = TracingStatus(enabled=False, reason="not configured")


def status() -> TracingStatus:
    return _status


def is_enabled() -> bool:
    return _mlflow is not None


def configure_tracing(environ: MutableMapping[str, str] | None = None) -> TracingStatus:
    """Initialize MLflow tracing once at process startup; never raises."""

    global _mlflow, _status
    env = os.environ if environ is None else environ
    if env.get(ENABLE_ENV, "").strip().lower() not in _TRUE_VALUES:
        return _set_disabled(f"{ENABLE_ENV} is not enabled")
    tracking_uri = env.get("MLFLOW_TRACKING_URI", "").strip()
    if urlsplit(tracking_uri).scheme.lower() not in _SUPPORTED_URI_SCHEMES:
        # Never echo the URI: it may embed basic-auth credentials.
        return _set_disabled("MLFLOW_TRACKING_URI must be an http(s) or databricks URI")
    try:
        import mlflow
    except ImportError:
        return _set_disabled("the optional 'tracing' extra (mlflow-tracing) is not installed")

    for name, value in _BOUNDED_HTTP_DEFAULTS.items():
        env.setdefault(name, value)
        # MLflow reads its settings from the process environment.
        os.environ.setdefault(name, env[name])
    try:
        mlflow.set_tracking_uri(tracking_uri)
        experiment_id = env.get("MLFLOW_EXPERIMENT_ID", "").strip()
        if experiment_id:
            mlflow.set_experiment(experiment_id=experiment_id)
        else:
            mlflow.set_experiment(env.get("MLFLOW_EXPERIMENT_NAME", "").strip() or DEFAULT_EXPERIMENT_NAME)
        mlflow.langchain.autolog(silent=True)
    except Exception as error:
        _LOGGER.warning("MLflow tracing disabled: initialization failed (%s)", type(error).__name__)
        return _set_disabled(f"initialization failed ({type(error).__name__})")

    gemini_autolog = False
    if _google_genai_sdk_available():
        try:
            mlflow.gemini.autolog(silent=True)
            gemini_autolog = True
        except Exception as error:
            _LOGGER.warning("MLflow Gemini autolog unavailable (%s)", type(error).__name__)
    _mlflow = mlflow
    _status = TracingStatus(enabled=True, reason="enabled", langchain_autolog=True, gemini_autolog=gemini_autolog)
    _LOGGER.info("MLflow tracing enabled (langchain_autolog=True, gemini_autolog=%s)", gemini_autolog)
    return _status


def reset_tracing() -> None:
    """Return to the disabled state (tests and process shutdown)."""

    global _mlflow
    mlflow = _mlflow
    _mlflow = None
    _set_disabled("reset")
    if mlflow is not None:
        try:
            mlflow.langchain.autolog(disable=True, silent=True)
            if _google_genai_sdk_available():
                mlflow.gemini.autolog(disable=True, silent=True)
        except Exception:
            pass


def _set_disabled(reason: str) -> TracingStatus:
    global _mlflow, _status
    _mlflow = None
    _status = TracingStatus(enabled=False, reason=reason)
    return _status


def _google_genai_sdk_available() -> bool:
    # mlflow.gemini.autolog patches the Google GenAI SDKs only.  The packaged
    # GeminiAnswerer uses the REST endpoint directly and is traced manually.
    for module in ("google.genai", "google.generativeai"):
        try:
            if importlib.util.find_spec(module) is not None:
                return True
        except (ImportError, ValueError):
            continue
    return False


class _NoopSpan:
    def set_inputs(self, inputs: Any) -> None:
        pass

    def set_outputs(self, outputs: Any) -> None:
        pass

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def set_attributes(self, attributes: Mapping[str, Any]) -> None:
        pass

    def set_token_usage(self, input_tokens: Any, output_tokens: Any, total_tokens: Any = None) -> None:
        pass


NOOP_SPAN = _NoopSpan()


class _SafeSpan(_NoopSpan):
    """Redacting, exception-swallowing facade over an MLflow ``LiveSpan``."""

    def __init__(self, live: Any) -> None:
        self._live = live

    def set_inputs(self, inputs: Any) -> None:
        self._call("set_inputs", redact(inputs))

    def set_outputs(self, outputs: Any) -> None:
        self._call("set_outputs", redact(outputs))

    def set_attribute(self, key: str, value: Any) -> None:
        self.set_attributes({key: value})

    def set_attributes(self, attributes: Mapping[str, Any]) -> None:
        self._call("set_attributes", redact(dict(attributes)))

    def set_token_usage(self, input_tokens: Any, output_tokens: Any, total_tokens: Any = None) -> None:
        usage = {
            name: value
            for name, value in (
                ("input_tokens", input_tokens),
                ("output_tokens", output_tokens),
                ("total_tokens", total_tokens),
            )
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0
        }
        if "total_tokens" not in usage and {"input_tokens", "output_tokens"} <= usage.keys():
            usage["total_tokens"] = usage["input_tokens"] + usage["output_tokens"]
        if usage:
            # MLflow aggregates this reserved attribute into trace-level usage.
            self._call("set_attribute", "mlflow.chat.tokenUsage", usage)

    def _call(self, method: str, *args: Any) -> None:
        try:
            getattr(self._live, method)(*args)
        except Exception as error:
            _LOGGER.debug("MLflow span %s failed (%s)", method, type(error).__name__)


@contextmanager
def span(name: str, span_type: str = CHAIN, attributes: Mapping[str, Any] | None = None) -> Iterator[_NoopSpan]:
    """Open a child of the active span, or a no-op when tracing is disabled.

    Exceptions raised by the traced block are recorded on the span by MLflow
    and always re-raised unchanged; tracing's own failures are swallowed.
    """

    mlflow = _mlflow
    if mlflow is None:
        yield NOOP_SPAN
        return
    try:
        manager = mlflow.start_span(name=name, span_type=span_type, attributes=redact(dict(attributes or {})))
        live = manager.__enter__()
    except Exception as error:
        _LOGGER.debug("MLflow span start failed (%s)", type(error).__name__)
        yield NOOP_SPAN
        return
    exc_info: tuple[Any, Any, Any] = (None, None, None)
    try:
        yield _SafeSpan(live)
    except BaseException:
        exc_info = sys.exc_info()
        raise
    finally:
        try:
            manager.__exit__(*exc_info)
        except BaseException as error:
            if error is not exc_info[1]:
                _LOGGER.debug("MLflow span end failed (%s)", type(error).__name__)


def redact(value: Any, _depth: int = 0) -> Any:
    """Bound trace payloads and drop credential-looking keys."""

    if _depth > 4:
        return "[truncated]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value if len(value) <= _MAX_TEXT else value[:_MAX_TEXT] + "...[truncated]"
    if isinstance(value, Mapping):
        result = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= _MAX_ITEMS:
                result["[truncated]"] = True
                break
            text_key = str(key)
            lowered = text_key.lower()
            if any(part in lowered for part in _SENSITIVE_KEY_PARTS) or lowered.endswith("token"):
                result[text_key] = "[redacted]"
            else:
                result[text_key] = redact(item, _depth + 1)
        return result
    if isinstance(value, (list, tuple, set, frozenset)):
        items = list(value)
        bounded = [redact(item, _depth + 1) for item in items[:_MAX_ITEMS]]
        if len(items) > _MAX_ITEMS:
            bounded.append("[truncated]")
        return bounded
    return redact(str(value), _depth + 1)
