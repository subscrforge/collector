"""The client for pixivFANBOX."""

import json
from collections.abc import AsyncIterator
from os import PathLike
from typing import TYPE_CHECKING

from httpx import ConnectTimeout, HTTPStatusError
from lxml import etree

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
            retries (int):
                The maximum number of retries for each request.
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

    async def iterate_newsletters(self, creator_id: str) -> AsyncIterator[Newsletter]:
        """Iterate all received newsletters sent by the specified creator.

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

    async def download_assets(
        self, post_id: str, output_dir: str | PathLike, filter: str | None = None
    ) -> None:
        ...


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
