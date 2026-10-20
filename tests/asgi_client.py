"""Synchronous test client that drives an ASGI app natively (no FastAPI/Starlette).

Requests travel through the application's real ASGI interface via
`httpx2.ASGITransport`, so tests exercise exactly what uvicorn serves: the
Django handler, `DjangoApiApplication`'s Host validation and its lifespan
protocol.  The surface mirrors the subset of the former Starlette client the
suites rely on:

* ``TestClient(app, raise_server_exceptions=True, base_url=..., follow_redirects=True)``
* ``client.app`` is the wrapped application
* ``get/post/put/patch/delete/head/options/request`` forward ``params``,
  ``json``, ``content``, ``data``, ``headers``, ``follow_redirects`` (and any
  other `httpx2` request option) and return a fully read ``httpx2.Response``
  (``status_code``, ``headers``, ``content``, ``text``, ``json()``)
* ``with TestClient(app) as client:`` runs ASGI lifespan startup/shutdown and
  serves every request in between on the same event loop; outside a ``with``
  block each request runs on its own short-lived loop and no lifespan events
  are sent (as before).
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Awaitable, Callable

import httpx2

__all__ = ["TestClient"]


class _Portal:
    """One event loop on a private thread, kept alive for a ``with`` block."""

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, name="asgi-test-client", daemon=True)
        self.thread.start()

    def run(self, awaitable: Awaitable) -> Any:
        return asyncio.run_coroutine_threadsafe(awaitable, self.loop).result()

    def close(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join()
        self.loop.close()


class _Lifespan:
    """Send ASGI lifespan events to the app and wait for its replies."""

    def __init__(self, app: Callable) -> None:
        self.app = app
        self.incoming: asyncio.Queue = asyncio.Queue()
        self.outgoing: asyncio.Queue = asyncio.Queue()
        self.task: asyncio.Task | None = None

    async def _send(self, message: dict) -> None:
        await self.outgoing.put(message)

    async def _run(self) -> None:
        scope = {"type": "lifespan", "asgi": {"version": "3.0", "spec_version": "2.0"}, "state": {}}
        try:
            await self.app(scope, self.incoming.get, self._send)
        finally:
            await self.outgoing.put(None)

    async def _event(self, name: str) -> None:
        await self.incoming.put({"type": f"lifespan.{name}"})
        reply = await self.outgoing.get()
        if reply is None:
            assert self.task is not None
            self.task.result()  # re-raise an application error
            raise RuntimeError(f"ASGI app returned during lifespan {name}")
        if reply["type"] == f"lifespan.{name}.failed":
            raise RuntimeError(reply.get("message") or f"lifespan {name} failed")
        if reply["type"] != f"lifespan.{name}.complete":
            raise RuntimeError(f"unexpected lifespan reply {reply['type']!r}")

    async def startup(self) -> None:
        self.task = asyncio.get_running_loop().create_task(self._run())
        await self._event("startup")

    async def shutdown(self) -> None:
        await self._event("shutdown")
        assert self.task is not None
        await self.task


class TestClient:
    __test__ = False  # not a test case for collectors

    def __init__(self, app: Callable, base_url: str = "http://testserver", raise_server_exceptions: bool = True,
                 follow_redirects: bool = True) -> None:
        self.app = app
        self.base_url = base_url
        self.raise_server_exceptions = raise_server_exceptions
        self.follow_redirects = follow_redirects
        self._portal: _Portal | None = None
        self._lifespan: _Lifespan | None = None

    async def _send(self, method: str, url: str, kwargs: dict) -> httpx2.Response:
        transport = httpx2.ASGITransport(app=self.app, raise_app_exceptions=self.raise_server_exceptions)
        async with httpx2.AsyncClient(transport=transport, base_url=self.base_url) as client:
            return await client.request(method, url, **kwargs)

    def _run(self, awaitable: Awaitable) -> Any:
        if self._portal is not None:
            return self._portal.run(awaitable)
        return asyncio.run(awaitable)

    def request(self, method: str, url: str, **kwargs: Any) -> httpx2.Response:
        kwargs.setdefault("follow_redirects", self.follow_redirects)
        return self._run(self._send(method.upper(), url, kwargs))

    def get(self, url: str, **kwargs: Any) -> httpx2.Response:
        return self.request("GET", url, **kwargs)

    def head(self, url: str, **kwargs: Any) -> httpx2.Response:
        return self.request("HEAD", url, **kwargs)

    def options(self, url: str, **kwargs: Any) -> httpx2.Response:
        return self.request("OPTIONS", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx2.Response:
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> httpx2.Response:
        return self.request("PUT", url, **kwargs)

    def patch(self, url: str, **kwargs: Any) -> httpx2.Response:
        return self.request("PATCH", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> httpx2.Response:
        return self.request("DELETE", url, **kwargs)

    def __enter__(self) -> TestClient:
        if self._portal is not None:
            raise RuntimeError("TestClient is already running its lifespan")
        portal = _Portal()
        lifespan = _Lifespan(self.app)
        try:
            portal.run(lifespan.startup())
        except BaseException:
            portal.close()
            raise
        self._portal, self._lifespan = portal, lifespan
        return self

    def __exit__(self, *exc_info: object) -> None:
        portal, lifespan = self._portal, self._lifespan
        self._portal = self._lifespan = None
        if portal is None or lifespan is None:
            return
        try:
            portal.run(lifespan.shutdown())
        finally:
            portal.close()
