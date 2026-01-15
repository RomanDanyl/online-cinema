from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Sequence, Set, Optional

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import (
    CartItemModel,
    CartModel,
    MovieModel,
    OrderItemModel,
    OrderModel,
    OrderStatusEnum,
    UserModel,
)


async def _get_cart(db: AsyncSession, *, user_id: int) -> CartModel:
    stmt = (
        select(CartModel)
        .where(CartModel.user_id == user_id)
        .options(selectinload(CartModel.items).selectinload(CartItemModel.movie))
    )
    cart = (await db.execute(stmt)).scalar_one_or_none()
    if not cart or not cart.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cart is empty.",
        )
    return cart


def _filter_available_items(items: Sequence[CartItemModel]) -> List[CartItemModel]:
    unavailable = [item for item in items if item.movie is None]
    if unavailable:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Some movies are no longer available.",
        )
    return list(items)


async def _remove_purchased_items(
    db: AsyncSession,
    *,
    user_id: int,
    items: Sequence[CartItemModel],
) -> List[CartItemModel]:
    paid_movie_stmt = (
        select(OrderItemModel.movie_id)
        .join(OrderModel, OrderModel.id == OrderItemModel.order_id)
        .where(
            OrderModel.user_id == user_id,
            OrderModel.status == OrderStatusEnum.PAID,
        )
        .distinct()
    )
    paid_movie_ids = set((await db.execute(paid_movie_stmt)).scalars().all())
    if not paid_movie_ids:
        return list(items)

    remaining_items = [item for item in items if item.movie_id not in paid_movie_ids]
    removed_item_ids = [item.id for item in items if item.movie_id in paid_movie_ids]
    if removed_item_ids:
        await db.execute(
            delete(CartItemModel).where(CartItemModel.id.in_(removed_item_ids))
        )
    return remaining_items


async def _ensure_no_duplicate_pending_order(
    db: AsyncSession,
    *,
    user_id: int,
    movie_ids: Set[int],
) -> None:
    if not movie_ids:
        return

    stmt = (
        select(OrderModel)
        .where(
            OrderModel.user_id == user_id,
            OrderModel.status == OrderStatusEnum.PENDING,
        )
        .options(selectinload(OrderModel.items))
    )
    orders = (await db.execute(stmt)).scalars().all()
    for order in orders:
        order_movie_ids = {item.movie_id for item in order.items}
        if order_movie_ids == movie_ids:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Pending order with the same movies already exists.",
            )


async def list_orders(*, db: AsyncSession, current_user: UserModel) -> List[OrderModel]:
    stmt = (
        select(OrderModel)
        .where(OrderModel.user_id == current_user.id)
        .options(selectinload(OrderModel.items))
        .order_by(OrderModel.created_at.desc())
    )
    return (await db.execute(stmt)).scalars().all()


async def create_order(*, db: AsyncSession, current_user: UserModel) -> OrderModel:
    cart = await _get_cart(db, user_id=current_user.id)
    items = _filter_available_items(cart.items)
    items = await _remove_purchased_items(db, user_id=current_user.id, items=items)
    if not items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No new movies available to order.",
        )

    movie_ids = {item.movie_id for item in items}
    await _ensure_no_duplicate_pending_order(
        db,
        user_id=current_user.id,
        movie_ids=movie_ids,
    )

    movie_stmt = select(MovieModel.id).where(MovieModel.id.in_(movie_ids))
    found_movie_ids = set((await db.execute(movie_stmt)).scalars().all())
    if found_movie_ids != movie_ids:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Some movies are no longer available.",
        )

    total_amount = sum(
        (item.movie.price for item in items),
        start=Decimal("0.00"),
    )

    order = OrderModel(
        user_id=current_user.id,
        status=OrderStatusEnum.PENDING,
        total_amount=total_amount,
    )
    order.items = [
        OrderItemModel(
            movie_id=item.movie_id,
            price_at_order=item.movie.price,
        )
        for item in items
    ]

    db.add(order)

    await db.execute(
        delete(CartItemModel).where(
            CartItemModel.cart_id == cart.id,
            CartItemModel.movie_id.in_(movie_ids),
        )
    )

    await db.commit()

    stmt = (
        select(OrderModel)
        .where(OrderModel.id == order.id)
        .options(selectinload(OrderModel.items))
    )
    return (await db.execute(stmt)).scalar_one()


async def cancel_order(
    *,
    db: AsyncSession,
    current_user: UserModel,
    order_id: int,
) -> OrderModel:
    stmt = (
        select(OrderModel)
        .where(OrderModel.id == order_id, OrderModel.user_id == current_user.id)
        .options(selectinload(OrderModel.items))
    )
    order = (await db.execute(stmt)).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found.")

    if order.status != OrderStatusEnum.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending orders can be canceled.",
        )

    order.status = OrderStatusEnum.CANCELED
    await db.commit()
    await db.refresh(order)
    return order


async def list_all_orders(
    *,
    db: AsyncSession,
    user_id: Optional[int] = None,
    status: Optional[OrderStatusEnum] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> List[OrderModel]:
    stmt = select(OrderModel).options(selectinload(OrderModel.items))
    if user_id is not None:
        stmt = stmt.where(OrderModel.user_id == user_id)
    if status is not None:
        stmt = stmt.where(OrderModel.status == status)
    if date_from is not None:
        stmt = stmt.where(OrderModel.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(OrderModel.created_at <= date_to)

    stmt = stmt.order_by(OrderModel.created_at.desc())
    return (await db.execute(stmt)).scalars().all()
