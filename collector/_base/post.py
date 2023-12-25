import abc
import mimetypes
from collections.abc import Iterable
from copy import deepcopy
from typing_extensions import Self

from lxml import etree
from lxml.builder import E
from pydantic import BaseModel, ConfigDict, HttpUrl, computed_field, model_validator


class PostBody(list["Segment"]):
    def __init__(
        self, segments: Self | Iterable["Segment"] | "Segment" | None = None
    ) -> None:
        super().__init__()
        if isinstance(segments, PostBody):
            self = segments
        elif isinstance(segments, Segment):
            self.append(segments)
        elif isinstance(segments, Iterable):
            self.extend(segments)

    def __add__(self, other: Self | Iterable["Segment"] | "Segment") -> Self:
        result = self.copy()
        result += other
        return result

    def __radd__(self, other: Self | Iterable["Segment"] | "Segment") -> Self:
        result = self.__class__(other)
        return result + self

    def __iadd__(self, other: Self | Iterable["Segment"] | "Segment") -> Self:
        if isinstance(other, Segment):
            self.append(other)
        elif isinstance(other, PostBody | Iterable):
            self.extend(other)

        return self

    def copy(self) -> Self:
        return deepcopy(self)

    def render(self) -> str:
        return etree.tostring(
            E.body(*[seg.html for seg in self]),
            encoding="utf-8",  # type: ignore
            pretty_print=True,  # type: ignore
        ).decode()

    @property
    def images(self) -> list["Image"]:
        return [seg for seg in self if isinstance(seg, Image)]

    @property
    def videos(self) -> list["Video"]:
        return [seg for seg in self if isinstance(seg, Video)]

    @property
    def files(self) -> list["File"]:
        return [seg for seg in self if isinstance(seg, File)]


class Segment(BaseModel, abc.ABC):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    @computed_field
    @property
    @abc.abstractmethod
    def html(self) -> etree._Element:
        raise NotImplementedError

    @computed_field
    @property
    @abc.abstractmethod
    def mime_type(self) -> str:
        raise NotImplementedError


class Paragraph(Segment):
    text: etree._Element

    @computed_field
    @property
    def mime_type(self) -> str:
        return "text/html"

    @computed_field
    @property
    def html(self) -> etree._Element:
        return self.text


class Image(Segment):
    id: str
    url: HttpUrl
    name: str
    thumbnail: HttpUrl | None = None

    @computed_field
    @property
    def mime_type(self) -> str:
        if result := mimetypes.guess_type(self.name)[0]:
            return result
        raise ValueError(f"Cannot determine the MIME type of {self.name}.")

    @computed_field
    @property
    def html(self) -> etree._Element:
        return E.img(src=str(self.url), id=self.id, alt=self.name)

    @model_validator(mode="after")
    def _validate_mime_type(self) -> Self:
        if not self.mime_type.startswith("image/"):
            raise ValueError(
                "The image segment must be initialized with an image MIME type."
            )
        return self


class Video(Segment):
    id: str
    url: HttpUrl
    name: str

    @computed_field
    @property
    def mime_type(self) -> str:
        if result := mimetypes.guess_type(self.name)[0]:
            return result
        raise ValueError(f"Cannot determine the MIME type of {self.name}.")

    @computed_field
    @property
    def html(self) -> etree._Element:
        return E.video(
            E.source(src=str(self.url), type=self.mime_type),
            id=self.id,
            controls="controls",
        )

    @model_validator(mode="after")
    def _validate_mime_type(self) -> Self:
        if not self.mime_type.startswith("video/"):
            raise ValueError(
                "The video segment must be initialized with a video MIME type."
            )
        return self


class File(Segment):
    id: str
    url: HttpUrl
    name: str
    size: int | None = None

    @computed_field
    @property
    def mime_type(self) -> str:
        return mimetypes.guess_type(self.name)[0] or "application/octet-stream"

    @computed_field
    @property
    def html(self) -> etree._Element:
        return E.a(self.name, href=str(self.url), id=self.id)
