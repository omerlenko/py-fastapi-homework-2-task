import datetime
from datetime import timedelta
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, field_validator, AfterValidator, ConfigDict

from database.models import MovieStatusEnum


def clean_names(values: list[str]) -> list[str]:
    cleaned = [" ".join(v.split()) for v in values]
    return list(dict.fromkeys(v for v in cleaned if v))


NameList = Annotated[list[str], AfterValidator(clean_names)]
Money = Annotated[Decimal, Field(max_digits=15, decimal_places=2, ge=0)]


class CountryRead(BaseModel):
    id: int
    code: str
    name: str | None

    model_config = ConfigDict(from_attributes=True)


class GenreRead(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class ActorRead(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class LanguageRead(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class MovieCreateSchema(BaseModel):
    name: Annotated[str, Field(max_length=255)]
    date: datetime.date
    score: Annotated[float, Field(ge=0, le=100)]
    overview: str
    status: MovieStatusEnum
    budget: Money
    revenue: Money
    country: str
    genres: NameList
    actors: NameList
    languages: NameList

    @field_validator("date")
    @classmethod
    def validate_future_date(cls, date: datetime.date):
        max_future_date = datetime.date.today() + timedelta(days=365)
        if date > max_future_date:
            raise ValueError("Date cannot be more than 1 year in the future.")
        return date

    @field_validator("country")
    @classmethod
    def validate_country(cls, country: str):
        country = country.strip().upper()
        if len(country) > 3:
            raise ValueError("Country must be in valid format (ISO 3166-1 alpha-3 code).")
        return country


class MovieUpdateSchema(BaseModel):
    name: Annotated[str, Field(max_length=255)] | None = None
    date: datetime.date | None = None
    score: Annotated[float, Field(ge=0, le=100)] | None = None
    overview: str | None = None
    status: MovieStatusEnum | None = None
    budget: Money | None = None
    revenue: Money | None = None


class MovieDetailSchema(BaseModel):
    id: int
    name: str
    date: datetime.date
    score: float
    overview: str
    status: MovieStatusEnum
    budget: float
    revenue: float
    country: CountryRead
    genres: list[GenreRead]
    actors: list[ActorRead]
    languages: list[LanguageRead]

    model_config = ConfigDict(from_attributes=True)


class MovieListItemSchema(BaseModel):
    id: int
    name: str
    date: datetime.date
    score: float
    overview: str

    model_config = ConfigDict(from_attributes=True)


class MovieListResponseSchema(BaseModel):
    movies: list[MovieListItemSchema]
    prev_page: str | None
    next_page: str | None
    total_pages: int
    total_items: int
