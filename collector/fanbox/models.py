"""The data models representing the data from pixivFANBOX."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from lxml.builder import E
from pydantic import Field, HttpUrl, root_validator

from collector._base import models as base
from collector._base.models import Price
from collector._base.post import File, Image, Paragraph

if TYPE_CHECKING:
    from lxml.etree import _Element

    from collector._base.models import Segment


class User(base.User):
    """The user of pixivFANBOX.

    Attributes:
        id (str):
            The user ID.
        name (str):
            The user name.
        avatar (HttpUrl):
            The URL of the user's avatar.
    """

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
        if cover := values.get("cover"):
            values["cover"] = cover["url"]

        return values

    @root_validator(pre=True)
    @classmethod
    def _build_body(cls, values: dict[str, Any]) -> dict[str, Any]:
        if "body" in values:
            try:
                result = getattr(cls, f"_build_{values['type']}_body")(values["body"])
            except AttributeError as err:
                raise NotImplementedError(
                    f"Unknown post type: {values['type']}"
                ) from err
            else:
                values["body"] = result

        return values

    @staticmethod
    def _build_article_body(data: dict[str, Any]) -> list["Segment"]:
        result: list["Segment"] = []

        def _format_text(data: dict[str, Any]) -> list["str | _Element"]:
            result: list["str | _Element"] = []

            if "style" in data:
                text = data["text"]
                current_index = 0

                for style in data["style"]:
                    result.append(text[current_index : style["offset"]])
                    formatted = text[
                        style["offset"] : style["offset"] + style["length"]
                    ]

                    match style["type"]:
                        case "bold":
                            result.append(E.b(formatted))
                        case _:
                            result.append(formatted)

                    current_index = style["offset"] + style["length"]

                if current_index < len(text):
                    result.append(text[current_index:])
            else:
                result.append(data["text"])

            return result

        for block in data["blocks"]:
            match block["type"]:
                case "p":
                    result.append(Paragraph(text=E.p(*_format_text(block))))
                case "header":
                    result.append(Paragraph(text=E.h2(block["text"])))
                case "url_embed":
                    url = data["urlEmbedMap"][block["urlEmbedId"]]["url"]
                    result.append(
                        E.a(data["urlEmbedMap"][block["urlEmbedId"]]["host"], href=url)
                    )
                case "image":
                    image_data = data["imageMap"][block["imageId"]]
                    result.append(
                        Image(
                            id=image_data["id"],
                            url=image_data["originalUrl"],
                            name=f"{image_data['id']}.{image_data['extension']}",
                            thumbnail=image_data["thumbnailUrl"],
                        )
                    )
                case "file":
                    file_data = data["fileMap"][block["fileId"]]
                    result.append(
                        File(
                            id=file_data["id"],
                            url=file_data["url"],
                            name=f"{file_data['name']}.{file_data['extension']}",
                            size=file_data["size"],
                        )
                    )
                case _:
                    raise NotImplementedError(f"Unknown block type: {block['type']}")

        return result

    @staticmethod
    def _build_image_body(data: dict[str, Any]) -> list["Segment"]:
        result: list["Segment"] = [
            Image(
                id=image["id"],
                url=image["originalUrl"],
                name=f"{image['id']}.{image['extension']}",
                thumbnail=image["thumbnailUrl"],
            )
            for image in data["images"]
        ]
        if "text" in data:
            result.extend(
                Paragraph(text=E.p(line)) for line in data["text"].splitlines()
            )
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
