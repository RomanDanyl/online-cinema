import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional, Literal

from pydantic import BaseModel, Field


class MovieListQueryParams(BaseModel):
    page: int = Field(1, ge=1)
    per_page: int = Field(10, ge=1, le=50)

    search: Optional[str] = Field(
        default=None,
        description="Search by title, description, actor, or director",
    )

    year: Optional[int] = Field(default=None, ge=1888)
    year_from: Optional[int] = Field(default=None, ge=1888)
    year_to: Optional[int] = Field(default=None, ge=1888)

    imdb_from: Optional[float] = Field(default=None, ge=0, le=10)
    imdb_to: Optional[float] = Field(default=None, ge=0, le=10)

    genre_id: Optional[int] = Field(default=None, ge=1)

    sort_by: Literal["price", "release_year", "popularity", "imdb"] = "release_year"
    sort_order: Literal["asc", "desc"] = "desc"


class UserReactionsEnum(str, Enum):
    LIKE: str = "like"
    DISLIKE: str = "dislike"


class GenreSchema(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class GenreWithMoviesCountSchema(BaseModel):
    id: int
    name: str
    movies_count: int

    model_config = {"from_attributes": True}


class GenreListResponseSchema(BaseModel):
    items: List[GenreWithMoviesCountSchema]


class CertificationSchema(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class MovieRatingRequestSchema(BaseModel):
    rating: int = Field(..., ge=1, le=10, description="Rating from 1 to 10")


class MovieDirectorSchema(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class MovieStarSchema(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class GenreCreateSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class GenreUpdateSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class ActorCreateSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class ActorUpdateSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class MovieCreateSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    year: int = Field(..., ge=1888)
    time: int = Field(..., ge=1)
    imdb: float = Field(..., ge=0, le=10)
    votes: int = Field(..., ge=0)
    meta_score: Optional[float] = Field(default=None, ge=0, le=100)
    gross: Optional[float] = Field(default=None, ge=0)
    description: str = Field(..., min_length=1)
    price: Decimal = Field(..., gt=0)
    certification_id: int = Field(..., ge=1)
    genre_ids: List[int] = Field(default_factory=list)
    star_ids: List[int] = Field(default_factory=list)
    director_ids: List[int] = Field(default_factory=list)


class MovieUpdateSchema(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    year: Optional[int] = Field(default=None, ge=1888)
    time: Optional[int] = Field(default=None, ge=1)
    imdb: Optional[float] = Field(default=None, ge=0, le=10)
    votes: Optional[int] = Field(default=None, ge=0)
    meta_score: Optional[float] = Field(default=None, ge=0, le=100)
    gross: Optional[float] = Field(default=None, ge=0)
    description: Optional[str] = Field(default=None, min_length=1)
    price: Optional[Decimal] = Field(default=None, gt=0)
    certification_id: Optional[int] = Field(default=None, ge=1)
    genre_ids: Optional[List[int]]
    star_ids: Optional[List[int]]
    director_ids: Optional[List[int]]


class MovieItemSchema(BaseModel):
    id: int
    uuid: uuid.UUID

    name: str
    year: int
    time: int
    imdb: float
    votes: int
    price: Decimal
    genres: List[GenreSchema]
    stars: List[MovieStarSchema]
    directors: List[MovieDirectorSchema]

    model_config = {"from_attributes": True}


class MovieListItemSchema(MovieItemSchema):
    avg_rating: Optional[float] = Field(default=None, ge=0, le=10)
    ratings_count: int = 0
    likes_count: int = 0
    comments_count: int = 0

    is_favorite: Optional[bool]
    user_rating: Optional[int]

    user_reaction: Optional[UserReactionsEnum]

    model_config = {"from_attributes": True}


class MovieListResponseSchema(BaseModel):
    items: List[MovieListItemSchema]
    total: int
    page: int
    page_size: int


class MovieDetailSchema(MovieListItemSchema):
    description: str
    meta_score: Optional[float] = None
    gross: Optional[float] = None
    certification: CertificationSchema


class MovieCommentCreateSchema(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    parent_comment_id: Optional[int] = Field(
        None, description="Optional parent comment id for replies", ge=1
    )


class MovieCommentResponseSchema(BaseModel):
    id: int
    movie_id: int
    user_id: int
    text: str
    parent_comment_id: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}
