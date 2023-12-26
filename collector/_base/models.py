from datetime import datetime
from typing import Annotated, Any
from typing_extensions import Self

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    HttpUrl,
)

from collector._base.post import PostBody, Segment
from collector._base.utils import Price


class Model(BaseModel):
    """The base models representing the data from subscription-based platforms."""

    id: str

    model_config = ConfigDict(
        extra="ignore", arbitrary_types_allowed=True, populate_by_name=True
    )

    @classmethod
    def from_response(cls, response: dict[str, Any]) -> Self:
        return cls.model_validate(response)

    @property
    def client_name(self) -> str:
        return self.__module__.split(".")[1].capitalize()


class User(Model):
    name: str
    avatar: HttpUrl


class Creator(Model):
    name: str
    avatar: HttpUrl
    homepage: HttpUrl
    description: str | None = None
    cover: HttpUrl | None = None
    profile_links: list[HttpUrl] | None
    is_nsfw: bool
    is_following: bool
    is_member: bool


class Membership(Model):
    name: str
    creator: str
    price: Price
    image: HttpUrl | None = Field(repr=False)
    description: str | None = Field(repr=False)


class Comment(Model):
    ...


class Tag(Model):
    ...


class DirectMessage(Model):
    creator: str
    sent_time: datetime
    updated_time: datetime | None = None
    message: str | None = Field(repr=False)


def _to_post_body(data: list[Segment]) -> "PostBody":
    return PostBody(data)


class Post(Model):
    title: str
    creator: str
    body: Annotated[PostBody, BeforeValidator(_to_post_body)] = Field(
        default=None, repr=False
    )
    published_time: datetime
    updated_time: datetime | None = None
    cover: HttpUrl | None = Field(default=None, repr=False)
    is_privileged: bool
    is_nsfw: bool
