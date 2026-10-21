"""Fixture ASGI entrypoint; live Neo4j dependencies are injected by the CLI."""
from robingraph.api.drf import create_django_app

application = create_django_app()
