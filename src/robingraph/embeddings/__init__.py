"""Embedding contracts and a small, synchronous Jina-compatible HTTP client.

The client deliberately does not contain a service URL.  Callers must provide
an endpoint explicitly (normally through :meth:`JinaEmbeddingSettings.from_env`)
so a fixture/test or an operator's private deployment cannot accidentally send
content to an inferred live service.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
import os
import socket
import time
from typing import Any, Callable, Mapping, Protocol, Sequence
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from .. import policy
from ..fixture import FixtureCorpus


PASSAGE_TASK = "retrieval.passage"
QUERY_TASK = "retrieval.query"
DEFAULT_BATCH_SIZE = 32
MAX_BATCH_SIZE = 128
DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
BIRDSNEST_MODELS = {"jina-embeddings-v3", "jinaai/jina-embeddings-v3"}
BIRDSNEST_DIMENSIONS = {32, 64, 128, 256, 512, 768, 1024}


class EmbeddingError(ValueError):
    """Base class for safe, actionable embedding failures."""


class EmbeddingConfigurationError(EmbeddingError):
    """The adapter configuration is missing or invalid."""


class EmbeddingHTTPError(EmbeddingError):
    """The configured server returned an HTTP error."""

    def __init__(self, status: int, reason: str = "") -> None:
        self.status = status
        self.reason = reason
        suffix = f": {reason}" if reason else ""
        super().__init__(f"Embedding HTTP error {status}{suffix}")


class EmbeddingTransportError(EmbeddingError):
    """The request could not be completed (including timeout)."""


class EmbeddingResponseError(EmbeddingError):
    """The server response was not a valid compatible embedding response."""


class EmbeddingPolicyError(EmbeddingError):
    """Embedding was refused because fixture policy or integrity failed."""


class EmbeddingIntegrityError(EmbeddingPolicyError):
    """Chunk content no longer matches its recorded SHA-256 hash."""


@dataclass(frozen=True)
class EmbeddingProfile:
    """The model/vector contract attached to every embedded chunk."""

    model: str
    dimensions: int
    normalized: bool

    def __post_init__(self) -> None:
        if not isinstance(self.model, str) or not self.model.strip():
            raise EmbeddingConfigurationError("Embedding model must be a non-empty string")
        if isinstance(self.dimensions, bool) or not isinstance(self.dimensions, int) or self.dimensions < 1:
            raise EmbeddingConfigurationError("Embedding dimensions must be a positive integer")
        if not isinstance(self.normalized, bool):
            raise EmbeddingConfigurationError("Embedding normalized must be boolean")


@dataclass(frozen=True)
class EmbeddedChunk:
    """A policy-approved chunk and its immutable embedding provenance."""

    chunk_id: str
    content_hash: str
    vector: tuple[float, ...]
    profile: EmbeddingProfile


@dataclass(frozen=True)
class JinaEmbeddingSettings:
    """Explicit settings for a Jina-compatible JSON HTTP endpoint.

    ``endpoint`` has no default by design.  A private server and the official
    Jina service use the same request shape, but compatibility of a user's
    private server is not established by this adapter.
    """

    endpoint: str
    model: str
    dimensions: int
    api_key: str | None = field(default=None, repr=False)
    normalized: bool = True
    batch_size: int = DEFAULT_BATCH_SIZE
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    api_format: str = "jina"
    max_length: int = 1024
    max_retries: int = 0

    def __post_init__(self) -> None:
        _validate_endpoint(self.endpoint)
        # Constructing the profile centralizes model/dimension/normalization checks.
        EmbeddingProfile(self.model, self.dimensions, self.normalized)
        if isinstance(self.batch_size, bool) or not isinstance(self.batch_size, int):
            raise EmbeddingConfigurationError("Embedding batch_size must be an integer")
        if not 1 <= self.batch_size <= MAX_BATCH_SIZE:
            raise EmbeddingConfigurationError(
                f"Embedding batch_size must be between 1 and {MAX_BATCH_SIZE}"
            )
        if isinstance(self.timeout_seconds, bool) or not isinstance(self.timeout_seconds, (int, float)):
            raise EmbeddingConfigurationError("Embedding timeout_seconds must be a number")
        if not math.isfinite(float(self.timeout_seconds)) or self.timeout_seconds <= 0:
            raise EmbeddingConfigurationError("Embedding timeout_seconds must be finite and positive")
        if self.api_key is not None and not isinstance(self.api_key, str):
            raise EmbeddingConfigurationError("Embedding api_key must be a string or None")
        if self.api_format not in {"jina", "birdsnest"}:
            raise EmbeddingConfigurationError("Embedding api_format must be jina or birdsnest")
        if isinstance(self.max_retries, bool) or not isinstance(self.max_retries, int) or not 0 <= self.max_retries <= 3:
            raise EmbeddingConfigurationError("Embedding max_retries must be an integer between 0 and 3")
        if self.api_format == "birdsnest":
            if self.model not in BIRDSNEST_MODELS or self.dimensions not in BIRDSNEST_DIMENSIONS:
                raise EmbeddingConfigurationError("Unsupported BirdsNest model or dimensions")
            if not self.normalized:
                raise EmbeddingConfigurationError("BirdsNest always returns normalized vectors")
            if self.batch_size > 64:
                raise EmbeddingConfigurationError("BirdsNest supports at most 64 inputs per request")
            if isinstance(self.max_length, bool) or not isinstance(self.max_length, int) or not 1 <= self.max_length <= 1024:
                raise EmbeddingConfigurationError("BirdsNest max_length must be an integer between 1 and 1024")

    @property
    def profile(self) -> EmbeddingProfile:
        model = "jinaai/jina-embeddings-v3" if self.api_format == "birdsnest" else self.model
        return EmbeddingProfile(model, self.dimensions, self.normalized)

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "JinaEmbeddingSettings":
        """Build settings from explicit ``ROBINGRAPH_JINA_*`` variables.

        Only the endpoint, model, and dimensions are required.  An API key is
        optional for compatible local/private servers; it is never read from a
        request body or guessed from another setting.
        """

        env = environ if environ is not None else os.environ

        def required(name: str) -> str:
            value = env.get(name)
            if value is None or not value.strip():
                raise EmbeddingConfigurationError(f"Missing required environment variable: {name}")
            return value.strip()

        def integer(name: str) -> int:
            value = required(name)
            try:
                return int(value)
            except ValueError as exc:
                raise EmbeddingConfigurationError(f"{name} must be an integer") from exc

        def boolean(name: str, default: bool) -> bool:
            value = env.get(name)
            if value is None or not value.strip():
                return default
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
            raise EmbeddingConfigurationError(f"{name} must be true/false")

        api_format = env.get("ROBINGRAPH_JINA_API_FORMAT", "jina")
        timeout_raw = env.get("ROBINGRAPH_JINA_TIMEOUT_SECONDS", "120" if api_format == "birdsnest" else str(DEFAULT_TIMEOUT_SECONDS))
        try:
            timeout = float(timeout_raw)
        except ValueError as exc:
            raise EmbeddingConfigurationError("ROBINGRAPH_JINA_TIMEOUT_SECONDS must be a number") from exc
        batch_raw = env.get("ROBINGRAPH_JINA_BATCH_SIZE", str(DEFAULT_BATCH_SIZE))
        try:
            batch_size = int(batch_raw)
        except ValueError as exc:
            raise EmbeddingConfigurationError("ROBINGRAPH_JINA_BATCH_SIZE must be an integer") from exc
        try:
            max_length = int(env.get("ROBINGRAPH_JINA_MAX_LENGTH", "1024"))
            max_retries = int(env.get("ROBINGRAPH_JINA_MAX_RETRIES", "2" if api_format == "birdsnest" else "0"))
        except ValueError as exc:
            raise EmbeddingConfigurationError("Embedding max_length/max_retries must be integers") from exc
        return cls(
            endpoint=required("ROBINGRAPH_JINA_ENDPOINT"),
            model=required("ROBINGRAPH_JINA_MODEL"),
            dimensions=integer("ROBINGRAPH_JINA_DIMENSIONS"),
            api_key=(env.get("ROBINGRAPH_JINA_API_KEY") or None),
            normalized=boolean("ROBINGRAPH_JINA_NORMALIZED", True),
            batch_size=batch_size,
            timeout_seconds=timeout,
            api_format=api_format,
            max_length=max_length,
            max_retries=max_retries,
        )

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "JinaEmbeddingSettings":
        """Readable alias for :meth:`from_env`."""

        return cls.from_env(environ)


class EmbeddingClient(Protocol):
    """Shared synchronous contract consumed by fixture and retrieval code."""

    profile: EmbeddingProfile

    def embed_documents(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]: ...

    def embed_query(self, text: str) -> tuple[float, ...]: ...


Urlopen = Callable[..., Any]


class JinaEmbeddingClient:
    """Stdlib urllib adapter for the OpenAI-shaped Jina embeddings contract."""

    def __init__(
        self,
        settings: JinaEmbeddingSettings | None = None,
        *,
        endpoint: str | None = None,
        model: str | None = None,
        dimensions: int | None = None,
        normalized: bool | None = None,
        api_key: str | None = None,
        batch_size: int | None = None,
        timeout_seconds: float | None = None,
        urlopen: Urlopen | None = None,
    ) -> None:
        if settings is not None and any(
            value is not None
            for value in (endpoint, model, dimensions, normalized, api_key, batch_size, timeout_seconds)
        ):
            raise EmbeddingConfigurationError("Pass settings or keyword options, not both")
        if settings is None:
            if endpoint is None or model is None or dimensions is None:
                raise EmbeddingConfigurationError(
                    "Jina endpoint, model, and dimensions must be explicit; use JinaEmbeddingSettings.from_env()"
                )
            settings = JinaEmbeddingSettings(
                endpoint=endpoint,
                model=model,
                dimensions=dimensions,
                normalized=True if normalized is None else normalized,
                api_key=api_key,
                batch_size=DEFAULT_BATCH_SIZE if batch_size is None else batch_size,
                timeout_seconds=DEFAULT_TIMEOUT_SECONDS if timeout_seconds is None else timeout_seconds,
            )
        self.settings = settings
        self.profile = settings.profile
        self._urlopen = urlopen or urllib_request.urlopen

    @classmethod
    def from_env(
        cls, environ: Mapping[str, str] | None = None, *, urlopen: Urlopen | None = None
    ) -> "JinaEmbeddingClient":
        """Construct a client from ``ROBINGRAPH_JINA_*`` settings."""

        return cls(JinaEmbeddingSettings.from_env(environ), urlopen=urlopen)

    def embed_documents(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        values = _validate_texts(texts)
        self._validate_input_limits(values)
        if not values:
            return ()
        vectors: list[tuple[float, ...]] = []
        batch: list[str] = []
        characters = 0
        for text in values:
            if batch and (len(batch) >= self.settings.batch_size or
                          (self.settings.api_format == "birdsnest" and characters + len(text) > 200_000)):
                vectors.extend(self._embed_batch(batch, PASSAGE_TASK))
                batch, characters = [], 0
            batch.append(text)
            characters += len(text)
        if batch:
            vectors.extend(self._embed_batch(batch, PASSAGE_TASK))
        return tuple(vectors)

    def embed_query(self, text: str) -> tuple[float, ...]:
        values = _validate_texts((text,))
        self._validate_input_limits(values)
        return self._embed_batch(values, QUERY_TASK)[0]

    def _validate_input_limits(self, texts: Sequence[str]) -> None:
        if self.settings.api_format == "birdsnest" and any(not text.strip() or len(text) > 20_000 for text in texts):
            raise EmbeddingConfigurationError("BirdsNest inputs must be non-blank and at most 20000 characters")

    def _embed_batch(self, texts: Sequence[str], task: str) -> tuple[tuple[float, ...], ...]:
        for attempt in range(self.settings.max_retries + 1):
            try:
                return self._request_batch(texts, task)
            except (EmbeddingHTTPError, EmbeddingTransportError) as error:
                if isinstance(error, EmbeddingHTTPError) and error.status not in {429, 500, 503}:
                    raise
                if attempt >= self.settings.max_retries:
                    raise
                time.sleep(0.5 * (2 ** attempt))
        raise AssertionError("Unreachable retry state")

    def _request_batch(self, texts: Sequence[str], task: str) -> tuple[tuple[float, ...], ...]:
        payload: dict[str, Any] = {
            "model": self.profile.model,
            "task": task,
            "dimensions": self.profile.dimensions,
            "normalized": self.profile.normalized,
            "input": list(texts),
        }
        if self.settings.api_format == "birdsnest":
            payload.pop("normalized")
            payload.update(encoding_format="float", max_length=self.settings.max_length)
        request = urllib_request.Request(
            self.settings.endpoint,
            data=json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "RobinGraph/0.1",
                **({"Authorization": f"Bearer {self.settings.api_key}"} if self.settings.api_key else {}),
            },
            method="POST",
        )
        try:
            response = self._urlopen(request, timeout=float(self.settings.timeout_seconds))
            try:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
            finally:
                close = getattr(response, "close", None)
                if close is not None:
                    close()
        except urllib_error.HTTPError as exc:
            # Upstream reason strings may echo request contents or credentials.
            exc.close()
            raise EmbeddingHTTPError(exc.code) from None
        except (urllib_error.URLError, TimeoutError, socket.timeout, OSError) as exc:
            raise EmbeddingTransportError(f"Embedding request failed: {type(exc).__name__}") from exc
        if len(raw) > MAX_RESPONSE_BYTES:
            raise EmbeddingResponseError("Embedding response exceeds the maximum allowed size")
        try:
            document = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise EmbeddingResponseError("Embedding response is not valid UTF-8 JSON") from exc
        return _parse_response(document, len(texts), self.profile)


def _validate_endpoint(endpoint: str) -> None:
    if not isinstance(endpoint, str) or not endpoint.strip():
        raise EmbeddingConfigurationError("Embedding endpoint must be explicitly configured")
    parsed = urllib_parse.urlsplit(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        raise EmbeddingConfigurationError("Embedding endpoint must be an http(s) URL without credentials")
    if parsed.fragment:
        raise EmbeddingConfigurationError("Embedding endpoint must not contain a URL fragment")


def _validate_texts(texts: Sequence[str]) -> tuple[str, ...]:
    if isinstance(texts, (str, bytes)):
        raise EmbeddingConfigurationError("Embedding input must be a sequence of strings")
    try:
        values = tuple(texts)
    except TypeError as exc:
        raise EmbeddingConfigurationError("Embedding input must be a sequence of strings") from exc
    if any(not isinstance(text, str) for text in values):
        raise EmbeddingConfigurationError("Every embedding input must be a string")
    return values


def _parse_response(document: Any, expected_count: int, profile: EmbeddingProfile) -> tuple[tuple[float, ...], ...]:
    if not isinstance(document, dict) or not isinstance(document.get("data"), list):
        raise EmbeddingResponseError("Embedding response must contain a data list")
    if "model" in document and document["model"] != profile.model:
        raise EmbeddingResponseError("Embedding response model does not match the configured model")
    rows = document["data"]
    if len(rows) != expected_count:
        raise EmbeddingResponseError(
            f"Embedding response count mismatch: expected {expected_count}, got {len(rows)}"
        )
    indexed: dict[int, tuple[float, ...]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise EmbeddingResponseError("Embedding response data rows must be objects")
        index = row.get("index")
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < expected_count:
            raise EmbeddingResponseError("Embedding response contains an invalid index")
        if index in indexed:
            raise EmbeddingResponseError("Embedding response contains duplicate indexes")
        indexed[index] = _validate_vector(row.get("embedding"), profile, index)
    if len(indexed) != expected_count:
        raise EmbeddingResponseError("Embedding response indexes are incomplete")
    return tuple(indexed[index] for index in range(expected_count))


def _validate_vector(vector: Any, profile: EmbeddingProfile, position: int) -> tuple[float, ...]:
    if not isinstance(vector, (list, tuple)) or isinstance(vector, (str, bytes)):
        raise EmbeddingResponseError(f"Embedding vector {position} must be an array")
    if len(vector) != profile.dimensions:
        raise EmbeddingResponseError(
            f"Embedding vector {position} dimension mismatch: expected {profile.dimensions}, got {len(vector)}"
        )
    clean: list[float] = []
    for value in vector:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise EmbeddingResponseError(f"Embedding vector {position} contains a non-number")
        try:
            number = float(value)
        except (OverflowError, ValueError) as exc:
            raise EmbeddingResponseError(f"Embedding vector {position} contains a non-finite value") from exc
        if not math.isfinite(number):
            raise EmbeddingResponseError(f"Embedding vector {position} contains a non-finite value")
        clean.append(number)
    norm = math.hypot(*clean)
    if not math.isfinite(norm) or norm == 0:
        raise EmbeddingResponseError(f"Embedding vector {position} must have a finite non-zero norm")
    if profile.normalized and not math.isclose(norm, 1.0, rel_tol=1e-3, abs_tol=1e-3):
        raise EmbeddingResponseError(f"Embedding vector {position} is not L2 normalized as requested")
    return tuple(clean)


def _source_allowed(corpus: FixtureCorpus, source_id: Any) -> bool:
    source = corpus.source_registry.get(source_id) if isinstance(source_id, str) else None
    return bool(
        source
        and source.get("enabled") is True
        and source.get("license_policy_status") == policy.ALLOWED
    )


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def embed_fixture_chunks(corpus: FixtureCorpus, client: EmbeddingClient) -> tuple[EmbeddedChunk, ...]:
    """Embed only chunks passing all local policy/source/integrity checks.

    The complete preflight runs before invoking the client.  This guarantees a
    denied, review-required, orphaned, source-missing, or hash-invalid record
    cannot cause a partial HTTP batch containing sensitive content.
    """

    profile = getattr(client, "profile", None)
    if not isinstance(profile, EmbeddingProfile):
        raise EmbeddingConfigurationError("Embedding client must expose an EmbeddingProfile")
    document_by_id = {
        document.get("document_id"): document
        for document in corpus.documents
        if isinstance(document, dict) and document.get("document_id")
    }
    eligible: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for chunk in corpus.chunks:
        if not isinstance(chunk, dict):
            raise EmbeddingPolicyError("Fixture chunk must be an object")
        document = document_by_id.get(chunk.get("document_id"))
        if not policy.chunk_embedding_allowed(chunk, document):
            continue
        if any(document.get(flag) is not True for flag in (
            "fulltext_storage_allowed", "chunk_storage_allowed", "embedding_allowed"
        )):
            continue
        if not _source_allowed(corpus, chunk.get("source_id")):
            continue
        if not isinstance(document, dict) or not _source_allowed(corpus, document.get("source_id")):
            continue
        chunk_id = chunk.get("chunk_id")
        if not isinstance(chunk_id, str) or not chunk_id:
            raise EmbeddingPolicyError("Eligible fixture chunk has no chunk_id")
        if chunk_id in seen_ids:
            raise EmbeddingPolicyError(f"Duplicate eligible chunk id: {chunk_id}")
        seen_ids.add(chunk_id)
        text = chunk.get("text")
        expected_hash = chunk.get("content_hash")
        if not isinstance(text, str) or not isinstance(expected_hash, str):
            raise EmbeddingIntegrityError(f"Chunk {chunk_id} has invalid text/hash metadata")
        actual_hash = _content_hash(text)
        if expected_hash != actual_hash:
            raise EmbeddingIntegrityError(f"Chunk {chunk_id} content hash mismatch")
        eligible.append(chunk)
    if not eligible:
        return ()

    vectors = client.embed_documents(tuple(chunk["text"] for chunk in eligible))
    if not isinstance(vectors, (tuple, list)) or len(vectors) != len(eligible):
        raise EmbeddingResponseError(
            f"Embedding result count mismatch: expected {len(eligible)}, got {len(vectors) if hasattr(vectors, '__len__') else 'unknown'}"
        )
    embedded: list[EmbeddedChunk] = []
    for position, (chunk, vector) in enumerate(zip(eligible, vectors)):
        clean = _validate_vector(vector, profile, position)
        embedded.append(
            EmbeddedChunk(
                chunk_id=chunk["chunk_id"],
                content_hash=chunk["content_hash"],
                vector=clean,
                profile=profile,
            )
        )
    return tuple(embedded)


# Friendly aliases for callers that name this a settings/adapter rather than a client.
JinaSettings = JinaEmbeddingSettings
JinaEmbeddingAdapter = JinaEmbeddingClient

__all__ = [
    "EmbeddingClient",
    "EmbeddingError",
    "EmbeddingConfigurationError",
    "EmbeddingHTTPError",
    "EmbeddingTransportError",
    "EmbeddingResponseError",
    "EmbeddingPolicyError",
    "EmbeddingIntegrityError",
    "EmbeddingProfile",
    "EmbeddedChunk",
    "JinaEmbeddingSettings",
    "JinaSettings",
    "JinaEmbeddingClient",
    "JinaEmbeddingAdapter",
    "embed_fixture_chunks",
    "PASSAGE_TASK",
    "QUERY_TASK",
]
