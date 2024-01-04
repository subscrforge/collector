from collector._log import logger


class CollectorException(Exception):
    """The base exception for all exceptions raised by the collector."""

    def __init__(self, message: str | None = None) -> None:
        if message:
            logger.error(message)
        self.message = message

        super().__init__(self.message)


class ClientError(CollectorException):
    """The base exception for all exceptions raised by the client."""


class NotConnectedError(ClientError):
    """Raises when the client is not connected yet."""

    def __init__(self) -> None:
        self.message = (
            "The client is not connected yet, and it is not allowed to perform "
            "any requests for now. To connect the client, use the `connect` method, "
            "or initialize with the context manager (`with` statement)."
        )
        super().__init__(self.message)


class NetworkError(ClientError):
    """Raises when the client cannot connect to the server."""


class RetrieveUserError(ClientError):
    """Raises when the user information cannot be retrieved from the client."""

    def __init__(self, credential_method: str | None = None) -> None:
        self.message = (
            "Failed to retrieve user information. Maybe the provided "
            f"{credential_method or 'credential'} is invalid or expired."
        )
        super().__init__(self.message)
