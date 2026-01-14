from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from database import OrderStatusEnum


class OrderItemSchema(BaseModel):
    id: int
    movie_id: int
    price_at_order: Decimal

    model_config = ConfigDict(from_attributes=True)


class OrderSchema(BaseModel):
    id: int
    user_id: int
    created_at: datetime
    status: OrderStatusEnum
    total_amount: Optional[Decimal] = None
    items: List[OrderItemSchema]

    model_config = ConfigDict(from_attributes=True)


class OrderListResponseSchema(BaseModel):
    items: List[OrderSchema]
