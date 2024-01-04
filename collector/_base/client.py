import abc
import inspect
from functools import partial
from types import TracebackType
from typing import TYPE_CHECKING, Any, Generic
from typing_extensions import Self

from httpx import AsyncClient
from httpx._utils import get_environment_proxies

from collector._base._transport import ClientTransport
from collector._base._utils import EventHooks, T_Client
from collector._exception import NotConnectedError
from collector._log import logger

if TYPE_CHECKING:
    from collector._base.models import User


class Client(abc.ABC):
    """The base class for clients that collect data from subscription-based platforms.

    All client implementations should inherit this class and implement all abstract
    methods.

    The clients are used to create sessions that make requests to the servers and
    retrieve data. Credentials such as cookies or access tokens are required to create
    sessions, ensuring that the sessions are able to access to the platforms' data.

    The clients support response caching (defaults to enable) for improving the
    performance and reducing the network traffic. All responses will be cached forcibly
    when the response caching is enabled, regardless of whether the server disables the
    caching.
    """

    def __init__(
        self,
        cache: bool | int | str = True,
        follow_cache_control: bool = False,
        retries: int = 3,
        rate_limit: str = "10 req/s",
        **config: Any,
    ) -> None:
        """Initialize the client.

        Args:
            cache (bool | int | str):
                Enable response caching. The value can be a boolean, an integer or a
                string.
                If it is a boolean, `True` means to enable the response caching
                with a default cache max age of `86400` seconds (1 day), and `False`
                means to disable the response caching.
                If it is an integer, it means to enable the response caching with the
                specified cache max age in seconds.
                If it is a string, it means to enable the response caching with the
                specified cache max age in a human-readable format.
            follow_cache_control (bool):
                Whether to follow the `Cache-Control` header in the response. If
                `True`, the response will be cached only when the `Cache-Control`
                header allows caching, otherwise the response will be cached forcibly.
                Defaults to `False`.
            retries (int):
                The maximum number of retries for each request. Defaults to `3`.
            rate_limit (str):
                The rate limit of the requests. Defaults to `10 req/s`.
            **config (Any):
                Additional configurations which will be directly passed to the
                `httpx.AsyncClient` instance.
        """
        _transport = partial(
            ClientTransport,
            cache=cache,
            follow_cache_control=follow_cache_control,
            retries=retries,
            rate_limit=rate_limit,
        )

        if proxy := config.pop("proxy", None):
            logger.debug(f"Using custom proxy: <u>{proxy}</u>.")
            config["transport"] = _transport(proxy=proxy)
        elif proxy_map := get_environment_proxies():
            logger.debug("Using proxies from environment variables.")
            config["mounts"] = {
                pattern: _transport(proxy=proxy) for pattern, proxy in proxy_map.items()
            }

        self.__config = config

        logger.info(f"Client created{'' if cache else ' without caching'}.")

    @property
    def _namespaced_clients(self) -> dict[str, type["NamespacedClient[Self]"]]:
        return {
            name: client
            for name, client in inspect.get_annotations(
                self.__class__, eval_str=True
            ).items()
            if issubclass(client, NamespacedClient)
        }

    def __getattr__(self, __name: str) -> Any:
        if __name == "_session" or __name in self._namespaced_clients:
            raise NotConnectedError()
        return self.__getattribute__(__name)

    async def __aenter__(self) -> Self:
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        exc_traceback: TracebackType | None,
    ) -> None:
        await self.close()

    async def connect(self) -> None:
        """Connect to the client."""
        session = AsyncClient(
            follow_redirects=True,
            event_hooks={
                "request": EventHooks.on_request,
                "response": EventHooks.on_response,
            },
            **self.__config,
        )

        self.user = await self._retrieve_user(session)
        # Create the session and register the namespace clients.
        self._session = session
        for name, client in self._namespaced_clients.items():
            setattr(self, name, client(self))

        logger.info(
            f"The session for <i>{self.user.client_name}</i> has been connected. "
            f"Current user in the session: <b>{self.user.name} (ID: {self.user.id})</b>"
        )

    async def close(self) -> None:
        """Close the client."""
        await self._session.aclose()
        logger.info("Client closed.")

    @abc.abstractmethod
    async def _retrieve_user(self, session: AsyncClient) -> "User":
        """Retrieve the user information from the client.

        This method is utilized to validate the credentials before creating a session,
        considering that the credential is valid if a non-anonymous user information can
        be retrieved by the credentials.

        Args:
            session (httpx.AsyncClient):
                The session to be used to retrieve the user information.

        Returns:
            User:
                The user information. It should be an implementation of the `User`
                model which is corresponding to the client.

        Raises:
            RetrieveUserError:
                Raised when the user information cannot be retrieved from the client.
            NetworkError:
                Raised when the client cannot connect to the server.
        """
        raise NotImplementedError("It should be called by the client implementation.")


class NamespacedClient(abc.ABC, Generic[T_Client]):
    def __init__(self, base: T_Client) -> None:
        self._base = base
        self._session = self._base._session
