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
    avg_rating: float
    ratings_count: int
    likes_count: int
    comments_count: int

    is_favorite: Optional[bool]
    user_rating: Optional[int]

    user_reaction: Optional[UserReactionsEnum]

    model_config = {"from_attributes": False}


class MovieListResponseSchema(BaseModel):
    items: List[MovieItemSchema]
    total: int
    page: int
    page_size: int


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
