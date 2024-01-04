from typing import TYPE_CHECKING

import httpcore
from aiolimiter import AsyncLimiter
from hishel import AsyncCacheTransport, AsyncFileStorage, Controller
from httpx import AsyncBaseTransport, AsyncHTTPTransport

from collector._constants import CACHE_DIR
from collector._utils import parse_duration, parse_rate_limit

if TYPE_CHECKING:
    from httpx import Request, Response


class ClientTransport(AsyncBaseTransport):
    def __init__(
        self,
        cache: bool | int | str = True,
        follow_cache_control: bool = False,
        retries: int = 3,
        rate_limit: str = "10 req/s",
        proxy: str | None = None,
    ) -> None:
        if isinstance(cache, bool):
            self._cache_max_age = 86400 if cache else 0
        else:
            self._cache_max_age = parse_duration(cache)

        self._cache_storage = AsyncFileStorage(
            base_path=CACHE_DIR, ttl=self._cache_max_age
        )
        self._cache_controller = Controller()
        self._transport = AsyncCacheTransport(
            transport=AsyncHTTPTransport(retries=retries, proxy=proxy),
            storage=self._cache_storage,
            controller=self._cache_controller,
        )
        self._force_cache = not follow_cache_control

        self._limiter = AsyncLimiter(*parse_rate_limit(rate_limit))

    async def handle_async_request(self, request: "Request") -> "Response":
        if not self._cache_max_age:
            request.extensions["cache_disabled"] = True
        elif self._force_cache:
            request.extensions["force_cache"] = True

        httpcore_request = httpcore.Request(
            method=request.method,
            url=httpcore.URL(
                scheme=request.url.raw_scheme,
                host=request.url.raw_host,
                port=request.url.port,
                target=request.url.raw_path,
            ),
            headers=request.headers.raw,
            content=request.stream,
            extensions=request.extensions,
        )
        key = self._cache_controller._key_generator(httpcore_request)

        if not await self._cache_storage.retrieve(key):
            await self._limiter.acquire()

        return await self._transport.handle_async_request(request)
