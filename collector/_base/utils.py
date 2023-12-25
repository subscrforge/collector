import inspect
from collections.abc import Callable, Coroutine
from decimal import Decimal
from http.client import responses as http_resp
from typing import TYPE_CHECKING, Any, Literal, TypeVar

from babel.numbers import format_currency
from httpx import Request, Response
from pydantic import BaseModel, Field

from collector._log import logger

if TYPE_CHECKING:
    from collector._base.client import Client

T_Client = TypeVar("T_Client", bound="Client")
EventHook = Callable[[Request | Response], Coroutine[Any, Any, Any]]


class Price(BaseModel):
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    value: Decimal = Field(decimal_places=2)

    def __str__(self) -> str:
        return format_currency(number=self.value, currency=self.currency)


class _EventHooksMeta(type):
    def __getattr__(
        self, name: Literal["on_request", "on_response"]
    ) -> list[EventHook]:
        hooks = []

        for _, func in inspect.getmembers(self, predicate=inspect.isfunction):
            signature = inspect.signature(func)
            if signature.parameters.get(name.strip("on_")):
                hooks.append(func)

        return hooks


class EventHooks(metaclass=_EventHooksMeta):
    """Hooks to add functionalities while handling requests and responses."""

    on_request: list[EventHook]
    """List of event hooks to be called before sending a request."""
    on_response: list[EventHook]
    """List of event hooks to be called after receiving a response."""

    @staticmethod
    async def log_request(request: Request) -> None:
        """Logs a request which is about to be sent with rich format."""
        request_format = f"<<le><u>{request.method} {request.url}</u></le>>"
        logger.debug(f"Request {request_format} sent.")

    @staticmethod
    async def force_cache(request: Request) -> None:
        """Forces the request to be cached."""
        request.extensions.update({"force_cache": True})

    @staticmethod
    async def raise_for_status(response: Response) -> None:
        """Always raises exception when this response has an error status code."""
        response.raise_for_status()

    @staticmethod
    async def log_response(response: Response) -> None:
        """Logs a received response with rich format."""
        request_info = f"<<le><u>{response.request.method} {response.url}</u></le>>"

        status_code_series = response.status_code // 100
        status_format = {
            2: "<g>{}</g>",
            3: "<e>{}</e>",
            4: "<r>{}</r>",
            5: "<m>{}</m>",
        }
        status_code = status_format.get(status_code_series, "{}").format(
            f"{response.status_code} {http_resp[response.status_code]}"
        )

        logger.debug(f"Request {request_info} responded with status [{status_code}].")
