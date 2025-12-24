import uuid
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


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
