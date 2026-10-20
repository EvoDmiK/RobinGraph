"""DRF serializers for the public and internal RobinGraph API.

Each request serializer validates one endpoint's path, query and JSON body
inputs through the shared Pydantic DTO/constraint, in the legacy order
(path, query, body) so a request with several problems reports them together
exactly as before.  `validated_data` is the keyword set handed to the
framework-independent service.  Response serializers render the shared DTOs.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, ClassVar

from pydantic import BaseModel, Field, TypeAdapter
from rest_framework import serializers
from rest_framework.fields import empty

from ...retrieval.species_scope import SpeciesScope
from .. import ingest_service as ingest
from .. import schemas
from .validation import jsonable, missing, raise_if_errors, validate

_REQUIRED = object()


class Param:
    """One path/query parameter: its constraint and its default (or required)."""

    def __init__(self, annotation: Any, default: Any = _REQUIRED) -> None:
        self.adapter = TypeAdapter(annotation)
        self.default = default


class EndpointRequestSerializer(serializers.Serializer):
    """Validate `{"path": ..., "query": ..., "body": ...}` for one endpoint.

    `body` is `(keyword, Model)`; `None` means the endpoint has no body.
    Failures raise `RequestValidationFailed` (422, legacy error list).
    """

    path_params: ClassVar[dict[str, Param]] = {}
    query_params: ClassVar[dict[str, Param]] = {}
    body: ClassVar[tuple[str, type[BaseModel]] | None] = None
    _body_adapters: ClassVar[dict[type, TypeAdapter]] = {}

    @classmethod
    def _body_adapter(cls, model: type[BaseModel]) -> TypeAdapter:
        adapter = cls._body_adapters.get(model)
        if adapter is None:
            adapter = cls._body_adapters[model] = TypeAdapter(model)
        return adapter

    def run_validation(self, data: Any = empty) -> dict[str, Any]:
        data = {} if data is empty or data is None else data
        values: dict[str, Any] = {}
        errors: list[dict[str, Any]] = []
        for location, params, source in (("path", self.path_params, data.get("path") or {}),
                                         ("query", self.query_params, data.get("query") or {})):
            for name, param in params.items():
                raw = source.get(name)
                if raw is None:
                    if param.default is _REQUIRED:
                        errors.append(missing((location, name)))
                    else:
                        values[name] = param.default
                    continue
                value, field_errors = validate(param.adapter, raw, (location, name))
                errors.extend(field_errors)
                if not field_errors:
                    values[name] = value
        if self.body is not None:
            keyword, model = self.body
            raw = data.get("body")
            if raw is None:
                errors.append(missing(("body",)))
            else:
                value, body_errors = validate(self._body_adapter(model), raw, ("body",))
                errors.extend(body_errors)
                values[keyword] = value
        raise_if_errors(errors)
        return values

    def to_representation(self, instance: Any) -> Any:  # requests are never rendered
        raise NotImplementedError


class ModelResponseSerializer(serializers.BaseSerializer):
    """Render a shared response DTO exactly as its declared response model."""

    _adapters: ClassVar[dict[Any, TypeAdapter]] = {}

    def __init__(self, instance: Any, *, response_model: Any, **kwargs: Any) -> None:
        super().__init__(instance, **kwargs)
        adapter = self._adapters.get(response_model)
        if adapter is None:
            adapter = self._adapters[response_model] = TypeAdapter(response_model)
        self.adapter = adapter

    def to_representation(self, instance: Any) -> Any:
        # Validation is a no-op for an instance of the model; it rejects a
        # service result that drifted from the declared response contract.
        return self.adapter.dump_python(self.adapter.validate_python(instance, from_attributes=True), mode="json")


class PlainResponseSerializer(serializers.BaseSerializer):
    """Render an undeclared (dict) handler result with the legacy encoder rules."""

    def to_representation(self, instance: Any) -> Any:
        return jsonable(instance)


_NAME = Annotated[str, Field(min_length=1, max_length=200)]
_OPTIONAL_NAME = Annotated[str | None, Field(min_length=1, max_length=200)]
_SCOPE = Param(SpeciesScope, "all")


class TaxonNameRequestSerializer(EndpointRequestSerializer):
    query_params = {"name": Param(_NAME)}


class ScopedTaxonNameRequestSerializer(EndpointRequestSerializer):
    query_params = {"name": Param(_NAME), "species_scope": _SCOPE}


class QuestionRequestSerializer(EndpointRequestSerializer):
    body = ("request", schemas.QuestionRequest)


class ChatRequestSerializer(EndpointRequestSerializer):
    body = ("request", schemas.ChatRequest)


class DocumentSearchRequestSerializer(EndpointRequestSerializer):
    body = ("request", schemas.DocumentSearchRequest)


class ObservationQuerySerializer(EndpointRequestSerializer):
    query_params = {
        "taxon_key": Param(Annotated[str | None, Field(min_length=1, max_length=50)], None),
        "scientific_name": Param(_OPTIONAL_NAME, None),
        "place": Param(_OPTIONAL_NAME, None),
        "observed_from": Param(date | None, None),
        "observed_to": Param(date | None, None),
        "limit": Param(Annotated[int, Field(ge=1, le=100)], 25),
        "offset": Param(Annotated[int, Field(ge=0)], 0),
    }


class LineageQuerySerializer(EndpointRequestSerializer):
    query_params = {
        "scientific_name": Param(_OPTIONAL_NAME, None),
        "name": Param(_OPTIONAL_NAME, None),
        "species_scope": _SCOPE,
    }


_INGEST_ID = Param(Annotated[str, Field(min_length=1, max_length=ingest._IDENTIFIER_MAX_LENGTH)])


class ActiveReleaseRequestSerializer(EndpointRequestSerializer):
    path_params = {"pipeline_id": _INGEST_ID}


class BeginRequestSerializer(EndpointRequestSerializer):
    body = ("request", ingest.BeginRequest)


class AppendRequestSerializer(EndpointRequestSerializer):
    path_params = {"run_id": _INGEST_ID}
    body = ("request", ingest.AppendRequest)


class FinalizeRequestSerializer(EndpointRequestSerializer):
    path_params = {"run_id": _INGEST_ID}
    body = ("request", ingest.FinalizeRequest)


class FailRequestSerializer(EndpointRequestSerializer):
    path_params = {"run_id": _INGEST_ID}
    body = ("request", ingest.FailRequest)
