"""The data models representing the data from pixivFANBOX."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from lxml import etree
from lxml.builder import E
from pydantic import Field, HttpUrl, root_validator

from collector._base import datamodel as base
from collector._base.datamodel import Price

if TYPE_CHECKING:
    from lxml.builder import ElementMaker


class User(base.User):
    id: str = Field(..., alias="userId")
    avatar: HttpUrl = Field(..., alias="iconUrl")


class Creator(base.Creator):
    id: str = Field(..., alias="creatorId")
    user: User
    cover: HttpUrl | None = Field(..., alias="coverImageUrl")
    profile_links: list[HttpUrl] | None = None
    is_nsfw: bool = Field(..., alias="hasAdultContent")
    is_following: bool = Field(..., alias="isFollowed")
    is_member: bool = Field(..., alias="isSupported")
    is_stopped: bool
    has_booth_shop: bool

    @root_validator(pre=True)
    @classmethod
    def _set_default_fields(cls, values: dict[str, Any]) -> dict[str, Any]:
        if "name" not in values:
            values["name"] = values["user"]["name"]
        if "avatar" not in values:
            values["avatar"] = values["user"]["iconUrl"]
        if "homepage" not in values:
            values["homepage"] = f"https://www.fanbox.cc/@{values['creatorId']}"

        return values


class Post(base.Post):
    creator: str = Field(..., alias="creatorId")
    published_time: datetime = Field(..., alias="publishedDatetime")
    updated_time: datetime | None = Field(..., alias="updatedDatetime")
    cover: HttpUrl | None = Field(..., alias="coverImageUrl", repr=False)
    excerpt: str | None = None
    is_nsfw: bool = Field(..., alias="hasAdultContent")

    @root_validator(pre=True)
    @classmethod
    def _set_default_fields(cls, values: dict[str, Any]) -> dict[str, Any]:
        if "is_privileged" not in values:
            values["is_privileged"] = not values["isRestricted"]

        return values

    @root_validator(pre=True)
    @classmethod
    def _build_content(cls, values: dict[str, Any]) -> dict[str, Any]:
        try:
            result = getattr(cls, f"_build_{values['type']}_content")(values["body"])
        except AttributeError:
            raise NotImplementedError(f"Unknown post type: {values['type']}")

        values["content"] = etree.tostring(
            E.body(*result),
            encoding="utf-8",  # type: ignore
            pretty_print=True,  # type: ignore
        )

        return values

    @staticmethod
    def _build_article_content(data: dict[str, Any]) -> list["ElementMaker"]:
        result: list["ElementMaker"] = []

        for block in data["blocks"]:
            match block["type"]:
                case "p":
                    segments: list["str | ElementMaker"] = []
                    cur_string = block["text"]

                    if "styles" in block:
                        for style in block["styles"]:
                            segments.append(cur_string[: style["offset"]])
                            formatted = cur_string[
                                style["offset"] : style["offset"] + style["length"]
                            ]
                            match style["type"]:
                                case "bold":
                                    segments.append(E.b(formatted))
                                case _:
                                    segments.append(formatted)

                            cur_string = cur_string[style["offset"] + style["length"] :]
                    else:
                        segments.append(cur_string)

                    result.append(E.p(*segments))
                case "header":
                    result.append(E.h2(block["text"]))
                case "url_embed":
                    url = data["urlEmbedMap"][block["urlEmbedId"]]["url"]
                    result.append(
                        E.a(data["urlEmbedMap"][block["urlEmbedId"]]["host"], href=url)
                    )
                case "image":
                    image_id = block["imageId"]
                    result.append(
                        E.img(
                            src=data["imageMap"][image_id]["originalUrl"], alt=image_id
                        )
                    )
                case _:
                    pass

        return result

    @staticmethod
    def _build_image_content(data: dict[str, Any]) -> list["ElementMaker"]:
        result: list["ElementMaker"] = []

        for image in data["images"]:
            result.append(E.img(src=image["originalUrl"], alt=image["id"]))
        if "text" in data:
            result.append(E.p(data["text"]))

        return result


class Plan(base.Membership):
    name: str = Field(..., alias="title")
    user: User = Field(repr=False)
    creator: str = Field(..., alias="creatorId")
    image: HttpUrl | None = Field(..., alias="coverImageUrl", repr=False)

    @root_validator(pre=True)
    @classmethod
    def _set_default_fields(cls, values: dict[str, Any]) -> dict[str, Any]:
        if "price" not in values:
            values["price"] = Price(value=values["fee"], currency="JPY")

        return values


class Newsletter(base.DirectMessage):
    message: str = Field(..., alias="body")
    sent_time: datetime = Field(..., alias="createdAt")
    is_read: bool

    @root_validator(pre=True)
    @classmethod
    def _set_default_fields(cls, values: dict[str, Any]) -> dict[str, Any]:
        if isinstance(values["creator"], dict):
            values["creator"] = values["creator"]["creatorId"]

        return values
