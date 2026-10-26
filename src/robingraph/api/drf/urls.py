"""URL patterns for the native Django/DRF RobinGraph API.

`build_urlconf` binds one dependency set (service, optional ingest service,
frozen OpenAPI document) to a URLconf object; `create_django_app` sets it as
`request.urlconf` so several apps can coexist in one process.  The module
level `urlpatterns` serve the offline fixture app for `ROOT_URLCONF`.
"""

from __future__ import annotations

from importlib import resources
import json

from django.http import HttpResponse
from django.urls import Resolver404, get_urlconf, path, re_path, resolve

from ..ingest_service import IngestService
from ..services import ApiService
from . import views

_PACKAGE = "robingraph.api.drf"


def _page(name: str) -> bytes:
    return resources.files(_PACKAGE).joinpath(name).read_bytes()


def frozen_openapi(*, ingest: bool) -> dict:
    """The packaged public contract, with reviewed additive feature updates."""

    return json.loads(_page("openapi_ingest.json" if ingest else "openapi.json"))


def build_urlpatterns(service: ApiService, ingest: IngestService | None = None,
                      openapi_schema: dict | None = None) -> list:
    def bind(view_class, **extra):
        return views.threaded(view_class.as_view(service=service, **extra))

    patterns = []
    if ingest is not None:
        patterns += [
            path("internal/v1/ingest/begin", views.threaded(views.IngestBeginView.as_view(ingest=ingest))),
            path("internal/v1/ingest/<str:first>/<str:second>",
                 views.threaded(views.IngestTwoSegmentView.as_view(ingest=ingest))),
        ]
    patterns += [
        path("v1/taxa/name-relations", bind(views.NameRelationsView)),
        path("v1/taxa/related", bind(views.RelatedSpeciesView)),
        path("v1/taxa/similar", bind(views.SimilarSpeciesView)),
        path("v1/taxa/ecological-related", bind(views.EcologicalRelatedView)),
        path("v1/taxa/subspecies", bind(views.SubspeciesView)),
        path("v1/taxa/profile", bind(views.SpeciesProfileView)),
        path("birds", bind(views.BirdsUIView)),
        path("favicon.ico", bind(views.FaviconView)),
        re_path(r"^static/(?P<asset_path>.*)\Z", bind(views.StaticAssetView)),
        path("", bind(views.ChatUIView)),
        path("chat", bind(views.ChatUIView)),
        path("health", bind(views.HealthView)),
        path("v1/answers", bind(views.AnswerView)),
        path("v1/chat", bind(views.ChatView)),
        path("v1/search", bind(views.DocumentSearchView)),
        path("v1/observations", bind(views.ObservationSearchView)),
        path("v1/taxa/lineage", bind(views.TaxonomyLineageView)),
        path("openapi.json", views.threaded(views.OpenAPIView.as_view(
            schema=openapi_schema if openapi_schema is not None else frozen_openapi(ingest=ingest is not None)))),
        path("docs", views.threaded(views.DocumentationPageView.as_view(page=_page("docs.html")))),
        path("docs/oauth2-redirect", views.threaded(views.DocumentationPageView.as_view(
            page=_page("oauth2_redirect.html")))),
        path("redoc", views.threaded(views.DocumentationPageView.as_view(page=_page("redoc.html")))),
    ]
    return patterns


def handler404(request, exception=None):
    """Legacy `{"detail": "Not Found"}`, or a 307 to the other trailing-slash form.

    The previous router redirected `/health/` to `/health` (and `/static` to
    `/static/`) whenever only the other form matched any route.
    """

    route = request.path_info
    if route != "/":
        alternative = route.rstrip("/") if route.endswith("/") else route + "/"
        try:
            resolve(alternative, urlconf=get_urlconf())
        except Resolver404:
            pass
        else:
            location = f"{request.scheme}://{request.get_host()}{request.script_name.rstrip('/')}{alternative}"
            query = request.META.get("QUERY_STRING")
            response = HttpResponse(status=307)
            response["location"] = f"{location}?{query}" if query else location
            del response["Content-Type"]
            return response
    return HttpResponse(b'{"detail":"Not Found"}', status=404, content_type="application/json")


def handler500(request):
    return HttpResponse(b"Internal Server Error", status=500, content_type="text/plain; charset=utf-8")


def bad_request() -> HttpResponse:
    return HttpResponse(b'{"detail":"Bad Request"}', status=400, content_type="application/json")


def handler400(request, exception=None):
    return bad_request()


class UrlConf:
    """A per-application URLconf object (hashable by identity for Django's cache)."""

    handler400 = staticmethod(handler400)
    handler404 = staticmethod(handler404)
    handler500 = staticmethod(handler500)

    def __init__(self, urlpatterns: list) -> None:
        self.urlpatterns = urlpatterns


def build_urlconf(service: ApiService, ingest: IngestService | None = None,
                  openapi_schema: dict | None = None) -> UrlConf:
    return UrlConf(build_urlpatterns(service, ingest, openapi_schema))


class _FixturePatterns:
    """`ROOT_URLCONF` patterns for the offline fixture app, built on first use."""

    def __init__(self) -> None:
        self._patterns: list | None = None

    def _resolve(self) -> list:
        if self._patterns is None:
            self._patterns = build_urlpatterns(ApiService())
        return self._patterns

    def __iter__(self):
        return iter(self._resolve())

    def __len__(self) -> int:
        return len(self._resolve())

    def __getitem__(self, index):
        return self._resolve()[index]


urlpatterns = _FixturePatterns()
