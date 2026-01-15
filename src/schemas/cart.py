from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict


class CartItemCreateSchema(BaseModel):
    movie_id: int = Field(..., ge=1)


class CartMovieSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    year: int
    price: Decimal
    genres: list[str]


class CartItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    added_at: datetime
    movie: CartMovieSchema


class CartListResponseSchema(BaseModel):
    items: list[CartItemSchema]


class CartItemResponseSchema(BaseModel):
    item: CartItemSchema


class CartActionResponseSchema(BaseModel):
    message: str


class CartAdminSchema(BaseModel):
    user_id: int
    items: list[CartItemSchema]


class CartAdminListResponseSchema(BaseModel):
    items: list[CartAdminSchema]
