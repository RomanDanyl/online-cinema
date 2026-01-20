from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from database import PaymentStatusEnum


class PaymentCreateRequestSchema(BaseModel):
    order_id: int


class PaymentCheckoutResponseSchema(BaseModel):
    payment_id: int
    session_id: str
    checkout_url: str
    amount: Decimal
    currency: str


class PaymentItemSchema(BaseModel):
    id: int
    order_item_id: int
    price_at_payment: Decimal

    model_config = ConfigDict(from_attributes=True)


class PaymentSchema(BaseModel):
    id: int
    order_id: int
    user_id: int
    created_at: datetime
    status: PaymentStatusEnum
    amount: Decimal
    external_payment_id: str | None
    items: list[PaymentItemSchema]

    model_config = ConfigDict(from_attributes=True)


class PaymentListResponseSchema(BaseModel):
    items: list[PaymentSchema]
