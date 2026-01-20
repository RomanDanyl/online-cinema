from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

import anyio
import stripe
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import BaseAppSettings
from database import (
    OrderModel,
    OrderItemModel,
    OrderStatusEnum,
    PaymentItemModel,
    PaymentModel,
    PaymentStatusEnum,
    UserModel,
)


def _amount_to_cents(amount: Decimal) -> int:
    return int((amount * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


async def _get_order_with_items_or_404(
    db: AsyncSession, *, order_id: int, user_id: int
) -> OrderModel:
    stmt = (
        select(OrderModel)
        .where(OrderModel.id == order_id, OrderModel.user_id == user_id)
        .options(selectinload(OrderModel.items).selectinload(OrderItemModel.movie))
    )
    order = (await db.execute(stmt)).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    return order


def _calculate_order_total(order: OrderModel) -> Decimal:
    total = sum(
        (item.price_at_order for item in order.items),
        start=Decimal("0.00"),
    )
    return total


async def _ensure_no_pending_payment(
    db: AsyncSession, *, order_id: int
) -> Optional[PaymentModel]:
    stmt = select(PaymentModel).where(
        PaymentModel.order_id == order_id,
        PaymentModel.status == PaymentStatusEnum.PENDING,
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def create_checkout_session(
    *,
    db: AsyncSession,
    current_user: UserModel,
    order_id: int,
    settings: BaseAppSettings,
) -> tuple[PaymentModel, str, str]:
    order = await _get_order_with_items_or_404(
        db, order_id=order_id, user_id=current_user.id
    )
    if order.status != OrderStatusEnum.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending orders can be paid.",
        )
    if not order.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order has no items.",
        )

    pending_payment = await _ensure_no_pending_payment(db, order_id=order.id)
    if pending_payment:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payment already in progress for this order.",
        )

    total = _calculate_order_total(order)
    if order.total_amount != total:
        order.total_amount = total

    payment = PaymentModel(
        user_id=current_user.id,
        order_id=order.id,
        status=PaymentStatusEnum.PENDING,
        amount=total,
    )
    payment.payment_items = [
        PaymentItemModel(
            order_item_id=item.id,
            price_at_payment=item.price_at_order,
        )
        for item in order.items
    ]
    db.add(payment)
    await db.flush()

    stripe.api_key = settings.STRIPE_SECRET_KEY
    currency = settings.STRIPE_CURRENCY
    line_items = []
    for item in order.items:
        movie_name = item.movie.name if item.movie else f"Movie {item.movie_id}"
        line_items.append(
            {
                "price_data": {
                    "currency": currency,
                    "product_data": {"name": movie_name},
                    "unit_amount": _amount_to_cents(item.price_at_order),
                },
                "quantity": 1,
            }
        )

    try:
        session = await anyio.to_thread.run_sync(
            stripe.checkout.Session.create,
            success_url=settings.STRIPE_SUCCESS_URL,
            cancel_url=settings.STRIPE_CANCEL_URL,
            mode="payment",
            line_items=line_items,
            metadata={
                "payment_id": str(payment.id),
                "order_id": str(order.id),
                "user_id": str(current_user.id),
            },
        )
    except Exception as exc:
        payment.status = PaymentStatusEnum.CANCELED
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Stripe checkout session creation failed.",
        ) from exc

    payment.external_payment_id = session.id
    await db.commit()
    await db.refresh(payment)

    return payment, session.id, session.url


async def list_payments(
    *, db: AsyncSession, current_user: UserModel
) -> list[PaymentModel]:
    stmt = (
        select(PaymentModel)
        .where(PaymentModel.user_id == current_user.id)
        .options(selectinload(PaymentModel.payment_items))
        .order_by(PaymentModel.created_at.desc())
    )
    return (await db.execute(stmt)).scalars().all()


async def list_all_payments(
    *,
    db: AsyncSession,
    user_id: Optional[int] = None,
    status: Optional[PaymentStatusEnum] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> list[PaymentModel]:
    stmt = select(PaymentModel).options(selectinload(PaymentModel.payment_items))
    if user_id is not None:
        stmt = stmt.where(PaymentModel.user_id == user_id)
    if status is not None:
        stmt = stmt.where(PaymentModel.status == status)
    if date_from is not None:
        stmt = stmt.where(PaymentModel.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(PaymentModel.created_at <= date_to)

    stmt = stmt.order_by(PaymentModel.created_at.desc())
    return (await db.execute(stmt)).scalars().all()


async def handle_checkout_completed(
    *,
    db: AsyncSession,
    payment_id: int,
) -> tuple[PaymentModel, bool]:
    stmt = (
        select(PaymentModel)
        .where(PaymentModel.id == payment_id)
        .options(selectinload(PaymentModel.order).selectinload(OrderModel.user))
    )
    payment = (await db.execute(stmt)).scalar_one_or_none()
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found.")

    if payment.status == PaymentStatusEnum.SUCCESSFUL:
        return payment, True

    payment.status = PaymentStatusEnum.SUCCESSFUL
    if payment.order:
        payment.order.status = OrderStatusEnum.PAID

    await db.commit()
    await db.refresh(payment)
    return payment, False


async def handle_checkout_expired(
    *,
    db: AsyncSession,
    payment_id: int,
) -> PaymentModel:
    stmt = select(PaymentModel).where(PaymentModel.id == payment_id)
    payment = (await db.execute(stmt)).scalar_one_or_none()
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found.")

    if payment.status == PaymentStatusEnum.PENDING:
        payment.status = PaymentStatusEnum.CANCELED
        await db.commit()
        await db.refresh(payment)

    return payment
