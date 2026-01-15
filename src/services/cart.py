from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
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
from schemas.cart import (
    CartActionResponseSchema,
    CartItemResponseSchema,
    CartItemSchema,
    CartListResponseSchema,
    CartMovieSchema,
    CartAdminSchema,
    CartAdminListResponseSchema,
)


async def _get_movie_or_404(*, db: AsyncSession, movie_id: int) -> MovieModel:
    stmt = (
        select(MovieModel)
        .where(MovieModel.id == movie_id)
        .options(selectinload(MovieModel.genres))
    )
    result = await db.execute(stmt)
    movie = result.scalar_one_or_none()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found.")
    return movie


async def _ensure_not_purchased(
    *, db: AsyncSession, current_user: UserModel, movie_id: int
) -> None:
    stmt = (
        select(OrderItemModel.id)
        .join(OrderModel, OrderModel.id == OrderItemModel.order_id)
        .where(
            OrderModel.user_id == current_user.id,
            OrderItemModel.movie_id == movie_id,
            OrderModel.status == OrderStatusEnum.PAID,
        )
        .limit(1)
    )
    purchased = (await db.execute(stmt)).scalar_one_or_none()
    if purchased:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Movie already purchased.",
        )


def _serialize_cart_item(item: CartItemModel) -> CartItemSchema:
    movie = item.movie
    genres = [genre.name for genre in movie.genres] if movie else []
    movie_schema = CartMovieSchema(
        id=movie.id,
        name=movie.name,
        year=movie.year,
        price=movie.price,
        genres=genres,
    )
    return CartItemSchema(id=item.id, added_at=item.added_at, movie=movie_schema)


async def get_cart_items(
    *, db: AsyncSession, current_user: UserModel
) -> CartListResponseSchema:
    stmt = (
        select(CartModel)
        .where(CartModel.user_id == current_user.id)
        .options(
            selectinload(CartModel.items)
            .selectinload(CartItemModel.movie)
            .selectinload(MovieModel.genres)
        )
    )
    cart = (await db.execute(stmt)).scalar_one_or_none()
    if not cart:
        return CartListResponseSchema(items=[])
    items = [_serialize_cart_item(item) for item in cart.items]
    return CartListResponseSchema(items=items)


async def _get_or_create_cart(
    *, db: AsyncSession, current_user: UserModel
) -> CartModel:
    stmt = select(CartModel).where(CartModel.user_id == current_user.id)
    cart = (await db.execute(stmt)).scalar_one_or_none()
    if cart:
        return cart
    cart = CartModel(user_id=current_user.id)
    db.add(cart)
    await db.commit()
    await db.refresh(cart)
    return cart


async def add_cart_item(
    *, db: AsyncSession, current_user: UserModel, movie_id: int
) -> CartItemResponseSchema:
    await _ensure_not_purchased(db=db, current_user=current_user, movie_id=movie_id)
    await _get_movie_or_404(db=db, movie_id=movie_id)

    cart = await _get_or_create_cart(db=db, current_user=current_user)

    existing_stmt = select(CartItemModel.id).where(
        CartItemModel.cart_id == cart.id, CartItemModel.movie_id == movie_id
    )
    existing = (await db.execute(existing_stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Movie already in cart.",
        )

    item = CartItemModel(cart_id=cart.id, movie_id=movie_id)
    db.add(item)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Movie already in cart.",
        )

    stmt = (
        select(CartItemModel)
        .where(CartItemModel.id == item.id)
        .options(selectinload(CartItemModel.movie).selectinload(MovieModel.genres))
    )
    item = (await db.execute(stmt)).scalars().first()
    return CartItemResponseSchema(item=_serialize_cart_item(item))


async def remove_cart_item(
    *, db: AsyncSession, current_user: UserModel, item_id: int
) -> CartActionResponseSchema:
    stmt = select(CartModel.id).where(CartModel.user_id == current_user.id)
    cart_id = (await db.execute(stmt)).scalar_one_or_none()
    if not cart_id:
        raise HTTPException(status_code=404, detail="Cart is empty.")

    item_stmt = select(CartItemModel).where(
        CartItemModel.cart_id == cart_id, CartItemModel.id == item_id
    )
    item = (await db.execute(item_stmt)).scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found.")

    await db.delete(item)
    await db.commit()
    return CartActionResponseSchema(message="Cart item removed.")


async def clear_cart(
    *, db: AsyncSession, current_user: UserModel
) -> CartActionResponseSchema:
    stmt = select(CartModel.id).where(CartModel.user_id == current_user.id)
    cart_id = (await db.execute(stmt)).scalar_one_or_none()
    if not cart_id:
        return CartActionResponseSchema(message="Cart is already empty.")

    await db.execute(delete(CartItemModel).where(CartItemModel.cart_id == cart_id))
    await db.commit()
    return CartActionResponseSchema(message="Cart cleared.")


def _serialize_cart(cart: CartModel) -> CartAdminSchema:
    items = [_serialize_cart_item(item) for item in cart.items]
    return CartAdminSchema(user_id=cart.user_id, items=items)


async def get_cart_items_for_user(*, db: AsyncSession, user_id: int) -> CartAdminSchema:
    stmt = (
        select(CartModel)
        .where(CartModel.user_id == user_id)
        .options(
            selectinload(CartModel.items)
            .selectinload(CartItemModel.movie)
            .selectinload(MovieModel.genres)
        )
    )
    cart = (await db.execute(stmt)).scalar_one_or_none()
    if not cart:
        return CartAdminSchema(user_id=user_id, items=[])
    return _serialize_cart(cart)


async def list_all_carts(*, db: AsyncSession) -> CartAdminListResponseSchema:
    stmt = select(CartModel).options(
        selectinload(CartModel.items)
        .selectinload(CartItemModel.movie)
        .selectinload(MovieModel.genres)
    )
    carts = (await db.execute(stmt)).scalars().all()
    return CartAdminListResponseSchema(items=[_serialize_cart(cart) for cart in carts])
