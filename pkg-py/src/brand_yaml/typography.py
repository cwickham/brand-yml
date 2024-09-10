from __future__ import annotations

import itertools
from pathlib import Path
from typing import Annotated, Any, Literal, TypeVar, Union
from urllib.parse import urlencode, urljoin

from pydantic import (
    BaseModel,
    ConfigDict,
    Discriminator,
    Field,
    HttpUrl,
    PositiveInt,
    RootModel,
    Tag,
    field_validator,
    model_validator,
)

from ._utils import BrandBase

T = TypeVar("T")

SingleOrList = Union[T, list[T]]


BrandTypographyFontStyleType = Literal["normal", "italic"]
BrandTypographyFontWeightNamedType = Literal[
    "thin",
    "extra-light",
    "ultra-light",
    "light",
    "normal",
    "regular",
    "medium",
    "semi-bold",
    "demi-bold",
    "bold",
    "extra-bold",
    "ultra-bold",
    "black",
]
BrandTypographyFontWeightAllType = Union[
    float, int, BrandTypographyFontWeightNamedType
]

BrandTypographyFontWeightSimpleType = Union[
    float, int, Literal["normal", "bold"]
]

# https://developer.mozilla.org/en-US/docs/Web/CSS/font-weight#common_weight_name_mapping
BrandTypographyFontWeightMap = {
    "thin": 100,
    "extra-light": 200,
    "ultra-light": 200,
    "light": 300,
    "normal": 400,
    "regular": 400,
    "medium": 500,
    "semi-bold": 600,
    "demi-bold": 600,
    "bold": 700,
    "extra-bold": 800,
    "ultra-bold": 800,
    "black": 900,
}

# https://developer.mozilla.org/en-US/docs/Web/CSS/@font-face/src#font_formats
FontFormats = {
    ".otc": "collection",
    ".ttc": "collection",
    ".eot": "embedded-opentype",
    ".otf": "opentype",
    ".ttf": "truetype",
    ".svg": "svg",
    ".svgz": "svg",
    ".woff": "woff",
    ".woff2": "woff2",
}


class BrandInvalidFontWeight(ValueError):
    def __init__(self, value: Any):
        super().__init__(
            f"Invalid font weight {value!r}. Expected a number divisible "
            + "by 100 and between 100 and 900, or one of "
            + f"{', '.join(BrandTypographyFontWeightMap.keys())}."
        )


class BrandUnsupportedFontFileFormat(ValueError):
    def __init__(self, value: Any):
        supported = ("opentype", "truetype", "woff", "woff2")
        super().__init__(
            f"Unsupported font file {value!r}. Expected one of {', '.join(supported)}."
        )


def validate_font_weight(
    value: int | str,
) -> BrandTypographyFontWeightSimpleType:
    if isinstance(value, str):
        if value in ("normal", "bold"):
            return value
        if value in BrandTypographyFontWeightMap:
            return BrandTypographyFontWeightMap[value]

    try:
        value = int(value)
    except ValueError:
        raise BrandInvalidFontWeight(value)

    if value < 100 or value > 900 or value % 100 != 0:
        raise BrandInvalidFontWeight(value)

    return value


class BrandTypographyFontFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    family: str
    weight: BrandTypographyFontWeightSimpleType = "normal"
    style: BrandTypographyFontStyleType = "normal"

    @field_validator("weight", mode="before")
    @classmethod
    def validate_weight(cls, value: int | str):
        return validate_font_weight(value)

    @field_validator("source", mode="after")
    @classmethod
    def validate_source(cls, value: str):
        if not Path(value).suffix:
            raise BrandUnsupportedFontFileFormat(value)

        if Path(value).suffix not in FontFormats:
            raise BrandUnsupportedFontFileFormat(value)

        return value

    @property
    def format(self) -> Literal["opentype", "truetype", "woff", "woff2"]:
        source_ext = Path(self.source).suffix

        if source_ext not in FontFormats:
            raise BrandUnsupportedFontFileFormat(self.source)

        fmt = FontFormats[source_ext]
        if fmt not in ("opentype", "truetype", "woff", "woff2"):
            raise BrandUnsupportedFontFileFormat(self.source)

        return fmt


class BrandTypographyGoogleFontsApi(BaseModel):
    family: str
    weight: SingleOrList[BrandTypographyFontWeightAllType] = [400, 700]
    style: SingleOrList[BrandTypographyFontStyleType] = ["normal", "italic"]
    display: Literal["auto", "block", "swap", "fallback", "optional"] = "auto"
    version: PositiveInt = 2
    url: HttpUrl = Field("https://fonts.googleapis.com/")

    @field_validator("weight", mode="before")
    @classmethod
    def validate_weight(cls, value: SingleOrList[Union[int, str]]):
        if isinstance(value, list):
            return [validate_font_weight(x) for x in value]
        else:
            return validate_font_weight(value)

    def import_url(self) -> str:
        if self.version == 1:
            return self._import_url_v1()
        return self._import_url_v2()

    def _import_url_v1(self) -> str:
        weight = sorted(
            self.weight if isinstance(self.weight, list) else [self.weight]
        )
        style_str = sorted(
            self.style if isinstance(self.style, list) else [self.style]
        )
        style_map = {"normal": "", "italic": "i"}
        ital: list[str] = sorted([style_map[s] for s in style_str])

        values = []
        if len(weight) > 0 and len(ital) > 0:
            values = [f"{w}{i}" for w, i in itertools.product(weight, ital)]
        elif len(weight) > 0:
            values = [str(w) for w in weight]
        elif len(ital) > 0:
            values = ["regular" if i == "" else "italic" for i in ital]

        family_values = "" if len(values) == 0 else f":{','.join(values)}"
        params = urlencode(
            {
                "family": self.family + family_values,
                "display": self.display,
            }
        )

        return urljoin(str(self.url), f"css?{params}")

    def _import_url_v2(self) -> str:
        weight = sorted(
            self.weight if isinstance(self.weight, list) else [self.weight]
        )
        style_str = sorted(
            self.style if isinstance(self.style, list) else [self.style]
        )
        style_map = {"normal": 0, "italic": 1}
        ital: list[int] = sorted([style_map[s] for s in style_str])

        values = []
        axis = ""
        if len(weight) > 0 and len(ital) > 0:
            values = [f"{i},{w}" for i, w in itertools.product(ital, weight)]
            axis = "ital,wght"
        elif len(weight) > 0:
            values = [str(w) for w in weight]
            axis = "wght"
        elif len(ital) > 0:
            values = [str(i) for i in ital]
            axis = "ital"

        axis_range = f":{axis}@{';'.join(values)}"
        params = urlencode(
            {
                "family": self.family + axis_range,
                "display": self.display,
            }
        )

        return urljoin(str(self.url), f"css2?{params}")


class BrandTypographyFontGoogle(BrandTypographyGoogleFontsApi):
    model_config = ConfigDict(extra="forbid")

    source: Literal["google"] = "google"


class BrandTypographyFontBunny(BrandTypographyGoogleFontsApi):
    model_config = ConfigDict(extra="forbid")

    source: Literal["bunny"] = "bunny"
    version: PositiveInt = 1
    url: HttpUrl = Field("https://fonts.bunny.net/")


def brand_typography_font_discriminator(
    x: dict[str, object] | BrandTypographyFontFile | BrandTypographyFontGoogle,
) -> Literal["google", "bunny", "file"]:
    if isinstance(x, BrandTypographyFontBunny):
        return "bunny"
    elif isinstance(x, BrandTypographyFontGoogle):
        return "google"
    elif isinstance(x, BrandTypographyFontFile):
        return "file"

    value = x.get("source")

    if not isinstance(value, str):
        pass
    elif value in ("google", "bunny"):
        return value
    elif Path(value).suffix:
        return "file"

    raise ValueError(
        "Unsupported font source {value!r}, must be a file path, 'google', or 'bunny'."
    )


class BrandNamedColor(RootModel):
    root: str


class BrandTypographyOptionsColor(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    color: BrandNamedColor | None = None
    background_color: BrandNamedColor | None = Field(
        None, alias="background-color"
    )


class BrandTypographyOptionsWeight(BaseModel):
    weight: BrandTypographyFontWeightSimpleType | None = None

    @field_validator("weight", mode="before")
    @classmethod
    def validate_weight(cls, value: int | str):
        return validate_font_weight(value)


class BrandTypographyOptionsGenericText(BrandTypographyOptionsWeight):
    family: str | None = None
    style: SingleOrList[BrandTypographyFontStyleType] | None = None


class BrandTypographyOptionsSize(BaseModel):
    size: str | None = None


class BrandTypographyOptionsBlockText(BaseModel):
    line_height: float | None = Field(None, alias="line-height")


class BrandTypographyBase(
    BrandBase,
    BrandTypographyOptionsGenericText,
    BrandTypographyOptionsSize,
    BrandTypographyOptionsBlockText,
    BrandTypographyOptionsColor,
):
    model_config = ConfigDict(extra="forbid")


class BrandTypographyHeadings(
    BrandBase,
    BrandTypographyOptionsGenericText,
    BrandTypographyOptionsBlockText,
    BrandTypographyOptionsColor,
):
    model_config = ConfigDict(extra="forbid")


class BrandTypographyMonospace(
    BrandBase,
    BrandTypographyOptionsGenericText,
    BrandTypographyOptionsSize,
):
    model_config = ConfigDict(extra="forbid")


class BrandTypographyMonospaceInline(
    BrandBase,
    BrandTypographyOptionsGenericText,
    BrandTypographyOptionsSize,
    BrandTypographyOptionsColor,
):
    model_config = ConfigDict(extra="forbid")


class BrandTypographyMonospaceBlock(
    BrandBase,
    BrandTypographyOptionsGenericText,
    BrandTypographyOptionsSize,
    BrandTypographyOptionsBlockText,
    BrandTypographyOptionsColor,
):
    model_config = ConfigDict(extra="forbid")


class BrandTypographyLink(
    BrandBase,
    BrandTypographyOptionsWeight,
    BrandTypographyOptionsColor,
):
    model_config = ConfigDict(extra="forbid")

    decoration: str | None = None


class BrandTypography(BrandBase):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    fonts: list[
        Annotated[
            Union[
                Annotated[BrandTypographyFontGoogle, Tag("google")],
                Annotated[BrandTypographyFontBunny, Tag("bunny")],
                Annotated[BrandTypographyFontFile, Tag("file")],
            ],
            Discriminator(brand_typography_font_discriminator),
        ]
    ] = Field(default_factory=list)
    base: BrandTypographyBase | None = None
    headings: BrandTypographyHeadings | None = None
    monospace: BrandTypographyMonospace | None = None
    monospace_inline: BrandTypographyMonospaceInline | None = Field(
        None, alias="monospace-inline"
    )
    monospace_block: BrandTypographyMonospaceBlock | None = Field(
        None, alias="monospace-block"
    )
    link: BrandTypographyLink | None = None

    @model_validator(mode="after")
    def forward_monospace_values(self):
        """
        Forward values from `monospace` to inline and block variants.

        `monospace-inline` and `monospace-block` both inherit `family`, `style`,
        `weight` and `size` from `monospace`.
        """

        def use_fallback(obj: BaseModel | None, parent: BaseModel | None):
            if parent is None or obj is None:
                return

            for field in ("family", "style", "weight", "size"):
                fallback = getattr(parent, field)
                if fallback is None:
                    continue
                if getattr(obj, field) is None:
                    setattr(obj, field, fallback)

        use_fallback(self.monospace_inline, self.monospace)
        use_fallback(self.monospace_block, self.monospace)
        return self
