"""Native Django ASGI application factory for the RobinGraph API (RG-701).

`create_django_app` is the only API application factory.  It returns a Django
`ASGIHandler` whose requests resolve against that app's own URLconf, so
differently wired apps (fixture, Neo4j, ingest, tests) coexist in one process
without global handler state.
"""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Callable

from django.core.exceptions import DisallowedHost
from django.core.handlers.asgi import ASGIHandler

from ...retrieval.repository import GraphRepository
from ..ingest_service import IngestService, IngestStore
from ..jev_router import JevRouter
from ..schemas import AnswerGenerator, LineageHandler, ObservationSearchHandler, SearchHandler
from ..semantic_router import SemanticRouter
from ..services import ApiService

DEFAULT_SETTINGS_MODULE = "robingraph.django_api.settings"


def configure_default_settings() -> None:
    """Load the deployment settings module (unless one is already selected) once."""

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", DEFAULT_SETTINGS_MODULE)
    import django

    django.setup(set_prefix=False)


class DjangoApiApplication(ASGIHandler):
    """Django's ASGI handler bound to one RobinGraph dependency set."""

    def __init__(self, urlconf, openapi_schema: dict) -> None:
        super().__init__()
        self.urlconf = urlconf
        self._openapi_schema = openapi_schema

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            # Nothing to start or stop: dependencies are injected ready-made
            # and closed by the caller that created them.
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        await super().__call__(scope, receive, send)

    async def get_response_async(self, request):
        # Validate Host against ALLOWED_HOSTS once, before any route runs, so
        # matched, missing and trailing-slash paths all reject it the same way
        # (no route reads the host otherwise) without echoing the bad value.
        try:
            request.get_host()
        except DisallowedHost:
            from .urls import bad_request

            return bad_request()
        request.urlconf = self.urlconf
        return await super().get_response_async(request)

    def openapi(self) -> dict:
        """The frozen pre-migration OpenAPI document served at `/openapi.json`."""

        return copy.deepcopy(self._openapi_schema)


def create_django_app(
    repository: GraphRepository | None = None,
    *,
    search_handler: SearchHandler | None = None,
    answer_generator: AnswerGenerator | None = None,
    observation_handler: ObservationSearchHandler | None = None,
    lineage_handler: LineageHandler | None = None,
    korean_lineage_handler: LineageHandler | None = None,
    semantic_router: SemanticRouter | None = None,
    jev_router: JevRouter | None = None,
    species_profile_handler: Callable[[str], dict] | None = None,
    species_basic_profile_handler: Callable[[str], dict] | None = None,
    related_species_handler: Callable[[str], dict] | None = None,
    similar_species_handler: Callable[[str], dict] | None = None,
    ecological_relations_handler: Callable[[str], dict] | None = None,
    subspecies_handler: Callable[[str], dict] | None = None,
    name_relations_handler: Callable[[str], dict | None] | None = None,
    taxon_name_resolution_handler: Callable[[str], dict] | None = None,
    static_dir: Path | None = None,
    ingest_store: IngestStore | None = None,
) -> DjangoApiApplication:
    """Create the native Django/DRF API over the shared `ApiService`.

    The public application never discovers PostgreSQL credentials or opens a
    write path from ambient configuration: the ingest routes exist only when
    a control-plane store is injected, and then also require the internal
    bearer token from the environment (a missing token fails construction).
    """

    configure_default_settings()
    from .urls import build_urlconf, frozen_openapi

    service = ApiService(
        repository,
        search_handler=search_handler,
        answer_generator=answer_generator,
        observation_handler=observation_handler,
        lineage_handler=lineage_handler,
        korean_lineage_handler=korean_lineage_handler,
        semantic_router=semantic_router,
        jev_router=jev_router,
        species_profile_handler=species_profile_handler,
        species_basic_profile_handler=species_basic_profile_handler,
        related_species_handler=related_species_handler,
        similar_species_handler=similar_species_handler,
        ecological_relations_handler=ecological_relations_handler,
        subspecies_handler=subspecies_handler,
        name_relations_handler=name_relations_handler,
        taxon_name_resolution_handler=taxon_name_resolution_handler,
        static_dir=static_dir,
    )
    ingest = IngestService(ingest_store) if ingest_store is not None else None
    schema = frozen_openapi(ingest=ingest is not None)
    return DjangoApiApplication(build_urlconf(service, ingest, schema), schema)
