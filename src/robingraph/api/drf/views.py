"""Native DRF views for the RobinGraph public and internal ingest API.

Views only validate the HTTP request (DRF serializers over the shared DTOs),
call the framework-independent service and render its result.  Rendering,
content negotiation, authentication and error handling are fixed per view so
the legacy JSON contract holds regardless of project `REST_FRAMEWORK` settings:

* errors are `{"detail": ...}` (`ApiError`), the legacy 422 error list, or
  `{"detail": "Method Not Allowed"}` with `Allow`;
* the client's `Accept` header never turns a JSON route into a 406;
* no DRF `Allow`/`Vary` decoration is added to successful responses.
"""

from __future__ import annotations

from typing import Any, Callable, ClassVar

from asgiref.sync import sync_to_async
from django.http import HttpResponse
from rest_framework.exceptions import APIException, MethodNotAllowed
from rest_framework.negotiation import BaseContentNegotiation
from rest_framework.permissions import BasePermission
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import ingest_service as ingest_dto
from .. import schemas
from ..ingest_service import IngestService
from ..services import ApiError, ApiService, AssetResponse
from . import serializers
from .validation import RequestValidationFailed, jsonable, read_json_body

_HTML = "text/html; charset=utf-8"


class LegacyJSONRenderer(JSONRenderer):
    """Compact UTF-8 JSON that rejects NaN/Infinity, independent of settings."""

    ensure_ascii = False
    compact = True
    strict = True


class FirstRendererNegotiation(BaseContentNegotiation):
    """Always JSON: the legacy API ignored `Accept` instead of answering 406."""

    def select_parser(self, request, parsers):
        return parsers[0] if parsers else None

    def select_renderer(self, request, renderers, format_suffix=None):
        return renderers[0], renderers[0].media_type


def legacy_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    if isinstance(exc, ApiError):
        return Response({"detail": jsonable(exc.detail)}, status=exc.status_code, headers=exc.headers)
    if isinstance(exc, RequestValidationFailed):
        return Response({"detail": exc.errors}, status=422)
    if isinstance(exc, MethodNotAllowed):
        view = context.get("view")
        allowed = ", ".join(view.allowed_route_methods(context["request"])) if view is not None else ""
        return Response({"detail": "Method Not Allowed"}, status=405, headers={"Allow": allowed})
    if isinstance(exc, APIException):
        return Response({"detail": str(exc.detail)}, status=exc.status_code)
    return None  # unexpected failures become the generic 500 handler response


def threaded(view: Callable) -> Callable:
    """Run a synchronous DRF view (and its rendering) in a worker thread.

    Under ASGI Django runs plain sync views on one shared thread, which would
    serialize every slow Neo4j/embedding/generation call.  These views use no
    ORM connection, so they are safe off that thread.
    """

    def render(request, *args, **kwargs):
        response = view(request, *args, **kwargs)
        if callable(getattr(response, "render", None)) and not response.is_rendered:
            response.render()
        return response

    run = sync_to_async(render, thread_sensitive=False)

    async def threaded_view(request, *args, **kwargs):
        return await run(request, *args, **kwargs)

    threaded_view.view_class = view.view_class
    threaded_view.view_initkwargs = view.view_initkwargs
    return threaded_view


def asset_response(asset: AssetResponse) -> HttpResponse:
    response = HttpResponse(asset.content, status=asset.status_code, content_type=asset.media_type)
    for name, value in asset.headers.items():
        response[name] = value
    return response


class RobinGraphView(APIView):
    """Base view: no auth/session/CSRF, JSON-only, legacy error contract.

    Order matches the legacy request pipeline: route method check, JSON body
    decoding, then permissions (internal bearer), then parameter/body
    validation inside the handler.
    """

    authentication_classes: ClassVar[list] = []
    permission_classes: ClassVar[list] = []
    throttle_classes: ClassVar[list] = []
    parser_classes: ClassVar[list] = []
    renderer_classes: ClassVar[list] = [LegacyJSONRenderer]
    content_negotiation_class = FirstRendererNegotiation
    request_serializer: ClassVar[type[serializers.EndpointRequestSerializer] | None] = None
    service: ApiService | None = None
    ingest: IngestService | None = None

    @property
    def default_response_headers(self) -> dict[str, str]:
        return {}

    def get_exception_handler(self):
        return legacy_exception_handler

    def perform_authentication(self, request) -> None:
        # Public routes are anonymous; the ingest bearer is a permission.
        pass

    def allowed_route_methods(self, request) -> list[str]:
        return [method.upper() for method in self.http_method_names]

    def initial(self, request, *args, **kwargs) -> None:
        if request.method.upper() not in self.allowed_route_methods(request):
            raise MethodNotAllowed(request.method)
        has_body = self.request_serializer is not None and self.request_serializer.body is not None
        self.request_body = read_json_body(request) if has_body else None
        super().initial(request, *args, **kwargs)

    def validated(self, request, **path: str) -> dict[str, Any]:
        serializer = self.request_serializer(
            data={"path": path, "query": request.query_params, "body": self.request_body})
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    @staticmethod
    def model(instance: Any, response_model: Any) -> Response:
        return Response(serializers.ModelResponseSerializer(instance, response_model=response_model).data)

    @staticmethod
    def plain(instance: Any) -> Response:
        return Response(serializers.PlainResponseSerializer(instance).data)


# -- public JSON API -------------------------------------------------------------


class HealthView(RobinGraphView):
    http_method_names = ["get"]

    def get(self, request):
        return self.plain(self.service.health())


class NameRelationsView(RobinGraphView):
    http_method_names = ["get"]
    request_serializer = serializers.TaxonNameRequestSerializer

    def get(self, request):
        return self.plain(self.service.name_relations(**self.validated(request)))


class RelatedSpeciesView(RobinGraphView):
    http_method_names = ["get"]
    request_serializer = serializers.ScopedTaxonNameRequestSerializer

    def get(self, request):
        return self.plain(self.service.related(**self.validated(request)))


class SimilarSpeciesView(RobinGraphView):
    http_method_names = ["get"]
    request_serializer = serializers.ScopedTaxonNameRequestSerializer

    def get(self, request):
        return self.plain(self.service.similar(**self.validated(request)))


class EcologicalRelatedView(RobinGraphView):
    http_method_names = ["get"]
    request_serializer = serializers.ScopedTaxonNameRequestSerializer

    def get(self, request):
        return self.plain(self.service.ecological_related(**self.validated(request)))


class SubspeciesView(RobinGraphView):
    http_method_names = ["get"]
    request_serializer = serializers.TaxonNameRequestSerializer

    def get(self, request):
        return self.plain(self.service.subspecies(**self.validated(request)))


class SpeciesProfileView(RobinGraphView):
    http_method_names = ["get"]
    request_serializer = serializers.ScopedTaxonNameRequestSerializer

    def get(self, request):
        return self.plain(self.service.profile(**self.validated(request)))


class AnswerView(RobinGraphView):
    http_method_names = ["post"]
    request_serializer = serializers.QuestionRequestSerializer

    def post(self, request):
        return self.model(self.service.answer(**self.validated(request)), schemas.AnswerResponse)


class ChatView(RobinGraphView):
    http_method_names = ["post"]
    request_serializer = serializers.ChatRequestSerializer

    def post(self, request):
        return self.model(self.service.chat(**self.validated(request)), schemas.ChatResponse)


class DocumentSearchView(RobinGraphView):
    http_method_names = ["post"]
    request_serializer = serializers.DocumentSearchRequestSerializer

    def post(self, request):
        return self.model(self.service.search(**self.validated(request)), schemas.DocumentSearchResponse)


class ObservationSearchView(RobinGraphView):
    http_method_names = ["get"]
    request_serializer = serializers.ObservationQuerySerializer

    def get(self, request):
        return self.model(self.service.observations(**self.validated(request)),
                          schemas.OperationalObservationSearchResponse)


class TaxonomyLineageView(RobinGraphView):
    http_method_names = ["get"]
    request_serializer = serializers.LineageQuerySerializer

    def get(self, request):
        return self.model(self.service.lineage(**self.validated(request)), schemas.TaxonomyLineageResponse)


# -- packaged UI and static assets -------------------------------------------------


class ChatUIView(RobinGraphView):
    http_method_names = ["get"]

    def get(self, request):
        return asset_response(self.service.chat_ui())


class BirdsUIView(RobinGraphView):
    http_method_names = ["get"]

    def get(self, request):
        return asset_response(self.service.birds_ui())


class FaviconView(RobinGraphView):
    http_method_names = ["get"]

    def get(self, request):
        return asset_response(self.service.favicon())


class StaticAssetView(RobinGraphView):
    http_method_names = ["get"]

    def get(self, request, asset_path: str):
        return asset_response(self.service.static_asset(asset_path))


# -- frozen API documentation ------------------------------------------------------


class OpenAPIView(RobinGraphView):
    # Starlette's plain documentation routes also answered HEAD.
    http_method_names = ["get", "head"]
    schema: dict | None = None

    def get(self, request):
        return Response(self.schema)


class DocumentationPageView(RobinGraphView):
    http_method_names = ["get", "head"]
    page: bytes = b""

    def get(self, request):
        return HttpResponse(self.page, content_type=_HTML)


# -- internal ingest ---------------------------------------------------------------


class InternalBearerPermission(BasePermission):
    """The ingest routes require the deployment's internal bearer token."""

    def has_permission(self, request, view) -> bool:
        view.ingest.require_internal_bearer(request.META.get("HTTP_AUTHORIZATION"))
        return True


class IngestView(RobinGraphView):
    permission_classes = [InternalBearerPermission]


class IngestBeginView(IngestView):
    http_method_names = ["post"]
    request_serializer = serializers.BeginRequestSerializer

    def post(self, request):
        return self.model(self.ingest.begin(**self.validated(request)), ingest_dto.OperationResponse)


_RUN_ACTIONS = {
    "append": serializers.AppendRequestSerializer,
    "finalize": serializers.FinalizeRequestSerializer,
    "fail": serializers.FailRequestSerializer,
}


class IngestTwoSegmentView(IngestView):
    """`active/{pipeline_id}` (GET) and `{run_id}/{append|finalize|fail}` (POST).

    One Django pattern serves both legacy routes because they overlap: a GET
    for `active/append` reads the `append` pipeline while a POST for it
    appends to run `active`, and an unknown action is a plain 404.
    """

    http_method_names = ["get", "post"]

    def allowed_route_methods(self, request) -> list[str]:
        first, second = self.kwargs["first"], self.kwargs["second"]
        return [method for method, allowed in (("GET", first == "active"), ("POST", second in _RUN_ACTIONS))
                if allowed]

    def initial(self, request, *args, **kwargs) -> None:
        allowed = self.allowed_route_methods(request)
        if not allowed:
            raise ApiError(404, "Not Found")
        if request.method.upper() == "POST" and "POST" in allowed:
            self.request_serializer = _RUN_ACTIONS[self.kwargs["second"]]
        else:
            self.request_serializer = serializers.ActiveReleaseRequestSerializer
        super().initial(request, *args, **kwargs)

    def get(self, request, first: str, second: str):
        values = self.validated(request, pipeline_id=second)
        return self.model(self.ingest.active_release(**values), ingest_dto.ActiveReleaseResponse)

    def post(self, request, first: str, second: str):
        values = self.validated(request, run_id=first)
        operation = getattr(self.ingest, second)
        return self.model(operation(**values), ingest_dto.OperationResponse)
