"""The client for pixivFANBOX."""
import asyncio
import json
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from httpx import ConnectTimeout, HTTPStatusError
from lxml import etree
from pydantic import HttpUrl, TypeAdapter

from collector._base.client import Client, NamespacedClient
from collector._exception import NetworkError, RetrieveUserError
from collector.fanbox.models import Creator, Newsletter, Plan, Post, User

if TYPE_CHECKING:
    from httpx import AsyncClient


class Fanbox(Client):
    """The client for pixivFanbox."""

    creator: "_FanboxCreatorClient"
    post: "_FanboxPostClient"
    plan: "_FanboxPlanClient"
    newsletter: "_FanboxNewsletterClient"

    def __init__(
        self, session_id: str, *, user_agent: str | None = None, **config
    ) -> None:
        """Initialize the client.

        Args:
            session_id (str):
                The session ID of the user.
            user_agent (str | None):
                The user agent to use. Defaults to `None`.
            cache (bool | int | str):
                Enable response caching.
            follow_cache_control (bool):
                Whether to follow the `Cache-Control` header in the response. If
                `True`, the response will be cached only when the `Cache-Control`
                header allows caching, otherwise the response will be cached forcibly.
                Defaults to `False`.
            retries (int):
                The maximum number of retries for each request.
            rate_limit (str):
                The rate limit of the requests. Defaults to `10 req/s`.
            **config (Any):
                Additional configurations which will be directly passed to the
                `httpx.AsyncClient` instance.
        """
        cookies = {"FANBOXSESSID": session_id} if session_id else None
        headers = {"Origin": "https://www.fanbox.cc"}
        if user_agent:
            headers["User-Agent"] = user_agent

        super().__init__(
            base_url="https://api.fanbox.cc",
            cookies=cookies,
            headers=headers,
            http2=True,
            **config,
        )

    async def _retrieve_user(self, session: "AsyncClient") -> User:
        try:
            response = await session.get("https://www.fanbox.cc")
        except ConnectTimeout as err:
            raise NetworkError("Failed to connect to the server.") from err
        except HTTPStatusError as err:
            if err.response.status_code == 302:
                raise RetrieveUserError(credential_method="session_id") from err
            raise err

        root = etree.HTML(response.text, parser=None)

        user_info = None
        if metadata := root.xpath("//meta[@name='metadata']"):
            content = json.loads(metadata[0].attrib["content"])
            user_info = content["context"]["user"]

        if user_info:
            return User.from_response(user_info)
        raise RetrieveUserError(credential_method="session_id")


class _FanboxCreatorClient(NamespacedClient[Fanbox]):
    async def get(
        self, creator_id: str | None = None, user_id: str | None = None
    ) -> Creator | None:
        """Get the creator's information.

        Args:
            creator_id (str | None):
                The creator ID. Defaults to `None`.
            user_id (str | None):
                The user ID. Defaults to `None`.

        Returns:
            Creator:
                The creator's information. `None` if not found.

        Raises:
            ValueError:
                Raised when neither `creator_id` nor `user_id` is specified.
        """
        if creator_id is None and user_id is None:
            raise ValueError("Either `creator_id` or `user_id` must be specified.")

        try:
            response = await self._session.get(
                "creator.get",
                params={"creatorId": creator_id} if creator_id else {"userId": user_id},
            )
        except HTTPStatusError as err:
            if err.response.status_code == 404:
                return None
            raise err
        else:
            return Creator.from_response(response.json().get("body"))

    async def list_plans(self, creator_id: str) -> list[Plan]:
        """List plans provided by the specified creator.

        This method is equivalent to `Fanbox.plan.list_by_creator`.

        Args:
            creator_id (str):
                The creator ID.

        Returns:
            list[Plan]:
                The plans provided by the creator.

        Raises:
            ValueError:
                Raised when the creator is not found.
        """
        return await self._base.plan.list_by_creator(creator_id)

    async def iterate_posts(
        self, creator_id: str, include_body: bool = False
    ) -> AsyncIterator[Post]:
        """Iterate all posts created by the specified creator.

        This method is equivalent to `Fanbox.post.iterate_by_creator`.

        Args:
            creator_id (str):
                The creator ID.
            include_body (bool):
                Whether to include the post body. Defaults to `False`.
                Note that this will send additional requests to the server frequently.
                It is recommended to set a proper rate limit to avoid receiving HTTP 429
                errors from the server if enabled.

        Yields:
            Post:
                The posts created by the creator.

        Raises:
            ValueError:
                Raised when the creator is not found.
        """
        async for post in self._base.post.iterate_by_creator(
            creator_id, include_body=include_body
        ):
            yield post

    async def iterate_newsletters(self, creator_id: str) -> AsyncIterator[Newsletter]:
        """Iterate all received newsletters sent by the specified creator.

        This method is equivalent to filtering the result of
        `Fanbox.newsletter.iterate_received`.

        Args:
            creator_id (str):
                The creator ID.

        Yields:
            Newsletter:
                The creator's newsletters.
        """
        async for newsletter in self._base.newsletter.iterate_received():
            if newsletter.creator == creator_id:
                yield newsletter


class _FanboxPostClient(NamespacedClient[Fanbox]):
    async def get(self, post_id: str) -> Post | None:
        """Get the post by ID.

        Args:
            post_id (str):
                The post ID. `None` if not exists.

        Returns:
            Post:
                The post.
        """
        try:
            response = await self._session.get("post.info", params={"postId": post_id})
        except HTTPStatusError as err:
            if err.response.status_code == 404:
                return None
            raise err
        return Post.from_response(response.json().get("body"))

    async def iterate_by_creator(
        self, creator_id: str, *, include_body: bool = False
    ) -> AsyncIterator[Post]:
        """Iterate all posts created by the specified creator.

        Args:
            creator_id (str):
                The creator ID.
            include_body (bool):
                Whether to include the post body. Defaults to `False`.
                Note that this will send additional requests to the server frequently.
                It is recommended to set a proper rate limit to avoid receiving HTTP 429
                errors from the server if enabled.

        Yields:
            Post:
                The posts created by the creator.

        Raises:
            ValueError:
                Raised when the creator is not found.
        """
        next_url: HttpUrl | None = None

        while True:
            params = {"creatorId": creator_id, "limit": 10}
            if next_url is not None:
                query_params = dict(next_url.query_params())
                params |= query_params

            try:
                response = await self._session.get("post.listCreator", params=params)
            except HTTPStatusError as err:
                if err.response.status_code == 404:
                    raise ValueError(f"Creator {creator_id} not found.") from err
                raise err
            else:
                result = response.json().get("body")

                async for post in self._get_posts(result, include_body):
                    yield post

                if url := result.get("nextUrl"):
                    next_url = TypeAdapter(HttpUrl).validate_strings(url)
                else:
                    break

    async def _get_posts(
        self, result: dict[str, Any], include_body: bool
    ) -> AsyncIterator[Post]:
        if include_body:
            tasks = [self.get(post["id"]) for post in result.get("items", [])]
            for post in await asyncio.gather(*tasks):
                if post is not None:
                    yield post
        else:
            for post in result.get("items", []):
                yield Post.from_response(post)


class _FanboxPlanClient(NamespacedClient[Fanbox]):
    async def list_by_creator(self, creator_id: str) -> list[Plan]:
        """List plans provided by the specified creator.

        Args:
            creator_id (str):
                The creator ID.

        Returns:
            list[Plan]:
                The plans provided by the creator.

        Raises:
            ValueError:
                Raised when the creator is not found.
        """
        try:
            response = await self._session.get(
                "plan.listCreator", params={"creatorId": creator_id}
            )
        except HTTPStatusError as err:
            if err.response.status_code == 404:
                raise ValueError(f"Creator {creator_id} not found.") from err
            raise err

        return [Plan.from_response(plan) for plan in response.json().get("body")]

    async def iterate_supporting(self) -> AsyncIterator[Plan]:
        """Iterate the supporting plans.

        Yields:
            Plan:
                The supporting plans.
        """
        response = await self._session.get("plan.listSupporting")
        for plan in response.json().get("body"):
            yield Plan.from_response(plan)


class _FanboxNewsletterClient(NamespacedClient[Fanbox]):
    async def get(self, newsletter_id: str) -> Newsletter | None:
        """Get the newsletter by ID.

        Args:
            newsletter_id (str):
                The newsletter ID. `None` if not exists.

        Returns:
            Newsletter:
                The newsletter.
        """
        try:
            response = await self._session.get(
                "newsletter.get", params={"id": newsletter_id}
            )
        except HTTPStatusError as err:
            if err.response.status_code == 404:
                return None
            raise err
        return Newsletter.from_response(response.json().get("body"))

    async def iterate_received(self) -> AsyncIterator[Newsletter]:
        """Iterate all received newsletters.

        Yields:
            Newsletter:
                The received newsletters.
        """
        response = await self._session.get("newsletter.list")
        for newsletter in response.json().get("body"):
            yield Newsletter.from_response(newsletter)
