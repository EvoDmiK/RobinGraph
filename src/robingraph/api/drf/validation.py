"""Request parsing/validation for the DRF adapters with the legacy 422 contract.

The public API promised FastAPI's validation body, `{"detail": [{"type",
"loc", "msg", "input", "ctx"?}, ...]}` with `loc` prefixed by `body`, `query`
or `path`.  DRF's own `ValidationError` stringifies every leaf value (an
integer `ctx.max_length` would become `"200"`), so the serializers raise
`RequestValidationFailed` with the Pydantic error list kept as JSON values.
Nothing here imports FastAPI; the rules mirror its request handling exactly.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
import email.message
from enum import Enum
import json
from pathlib import PurePath
from typing import Any
from uuid import UUID

from pydantic import BaseModel, TypeAdapter, ValidationError
from rest_framework.exceptions import APIException

from ..services import ApiError

_PARSE_ERROR = "There was an error parsing the body"


class RequestValidationFailed(APIException):
    """A 422 whose `detail` is the legacy Pydantic error list, never re-stringified."""

    status_code = 422

    def __init__(self, errors: list[dict[str, Any]]) -> None:
        self.errors = errors
        super().__init__(detail="Request validation failed")


def jsonable(value: Any) -> Any:
    """JSON-compatible copy of handler/validation output (legacy encoder rules)."""

    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if is_dataclass(value) and not isinstance(value, type):
        return jsonable(asdict(value))
    if isinstance(value, Enum):
        return jsonable(value.value)
    if isinstance(value, PurePath):
        return str(value)
    if value is None or isinstance(value, (str, int, float)):
        return value
    if isinstance(value, dict):
        return {jsonable(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [jsonable(item) for item in value]
    if isinstance(value, bytes):
        return value.decode()
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    if isinstance(value, timedelta):
        return value.total_seconds()
    if isinstance(value, Decimal):
        return int(value) if value.as_tuple().exponent >= 0 else float(value)
    if isinstance(value, UUID):
        return str(value)
    try:
        return jsonable(dict(value))
    except Exception:
        try:
            # An exception object (e.g. Pydantic `ctx.error`) encodes as `{}`.
            return jsonable(vars(value))
        except TypeError:
            raise ValueError(f"Object of type {type(value).__name__} is not JSON serializable") from None


def missing(loc: tuple[str | int, ...]) -> dict[str, Any]:
    return {"type": "missing", "loc": loc, "msg": "Field required", "input": None}


def validate(adapter: TypeAdapter, value: Any, loc: tuple[str | int, ...]) -> tuple[Any, list[dict[str, Any]]]:
    try:
        return adapter.validate_python(value, from_attributes=True), []
    except ValidationError as error:
        return None, [{**item, "loc": (*loc, *item["loc"])} for item in error.errors(include_url=False)]


def raise_if_errors(errors: list[dict[str, Any]]) -> None:
    if errors:
        raise RequestValidationFailed(jsonable(errors))


def read_json_body(request) -> Any:
    """Return the decoded JSON body, raw bytes for a non-JSON body, or `None`.

    Mirrors the legacy rules: a missing Content-Type is not treated as JSON,
    malformed JSON is a 422 `json_invalid`, and an undecodable body is a 400.
    """

    body = request.body
    if not body:
        return None
    content_type = request.META.get("CONTENT_TYPE")
    is_json = False
    if content_type:
        message = email.message.Message()
        message["content-type"] = content_type
        if message.get_content_maintype() == "application":
            subtype = message.get_content_subtype()
            is_json = subtype == "json" or subtype.endswith("+json")
    if not is_json:
        return body
    try:
        return json.loads(body)
    except json.JSONDecodeError as error:
        raise RequestValidationFailed([{
            "type": "json_invalid", "loc": ["body", error.pos], "msg": "JSON decode error",
            "input": {}, "ctx": {"error": error.msg},
        }]) from error
    except Exception as error:
        raise ApiError(400, _PARSE_ERROR) from error
