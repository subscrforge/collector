import abc
import inspect
from types import TracebackType
from typing import TYPE_CHECKING, Any, Generic
from typing_extensions import Self

from hishel import AsyncCacheClient as AsyncClient
from hishel import AsyncFileStorage

from collector._base.utils import EventHooks, T_Client
from collector._constants import CACHE_DIR
from collector._exception import NotConnectedError
from collector._log import logger
from collector._utils import parse_duration

if TYPE_CHECKING:
    from collector._base.datamodel import User


class Client(abc.ABC):
    """The base class for clients that collect data from subscription-based platforms.

    All clients should be implemented as a subclass of this class.

    It is responsible for creating a session to send requests to the platform's server.
    Client implementations must credentials (e.g. cookies or access token) to create a
    session which will enable to access the data from the server.

    The clients support response caching for improving the performance and reducing the
    network traffic. All responses will be cached forcibly when the response caching is
    enabled, regardless of whether the server disables the caching.
    """

    def __init__(
        self,
        cache: bool | int | str = True,
        **config: Any,
    ) -> None:
        """Initialize the client.

        Args:
            cache (bool | int | str):
                Enable response caching.
            **config (Any):
                Additional configurations which will be directly passed to the
                `httpx.AsyncClient` instance.
        """
        if isinstance(cache, bool):
            self.__cache_max_age = 86400 if cache else 0
        else:
            self.__cache_max_age = parse_duration(cache)

        if config.get("proxies"):
            logger.debug(f"Using custom proxy: <u>{config['proxies']}</u>.")

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
            storage=AsyncFileStorage(base_path=CACHE_DIR, ttl=self.__cache_max_age),
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
