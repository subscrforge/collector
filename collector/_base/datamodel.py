from datetime import datetime
from typing import Annotated, Any
from typing_extensions import Self

from lxml import html
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    HttpUrl,
    computed_field,
)
from pydantic.alias_generators import to_snake

from collector._base.utils import Price


class DataModel(BaseModel):
    """The base models representing the data from subscription-based platforms."""

    id: str

    model_config = ConfigDict(extra="ignore", alias_generator=to_snake)

    @classmethod
    def from_response(cls, response: dict[str, Any]) -> Self:
        return cls.model_validate(response)

    @property
    def client_name(self) -> str:
        return self.__module__.split(".")[1].capitalize()


class User(DataModel):
    name: str
    avatar: HttpUrl


class Creator(DataModel):
    name: str
    avatar: HttpUrl
    homepage: HttpUrl
    description: str | None = None
    cover: HttpUrl | None = None
    profile_links: list[HttpUrl] | None
    is_nsfw: bool
    is_following: bool
    is_member: bool


class Membership(DataModel):
    name: str
    creator: str
    price: Price
    image: HttpUrl | None = Field(repr=False)
    description: str | None = Field(repr=False)


class Comment(DataModel):
    ...


class Tag(DataModel):
    ...


class DirectMessage(DataModel):
    creator: str
    sent_time: datetime
    updated_time: datetime | None = None
    message: str | None = Field(repr=False)


def _to_post_content(raw: str) -> "PostContent":
    return PostContent(raw=raw)


class PostContent(BaseModel):
    raw: str

    @computed_field
    @property
    def images(self) -> list[HttpUrl]:
        return list(html.fromstring(self.raw).xpath("//img/@src"))


class Post(DataModel):
    title: str
    creator: str
    content: Annotated[PostContent, BeforeValidator(_to_post_content)] = Field(
        repr=False
    )
    published_time: datetime
    updated_time: datetime | None = None
    cover: HttpUrl | None = Field(repr=False)
    is_privileged: bool
    is_nsfw: bool
