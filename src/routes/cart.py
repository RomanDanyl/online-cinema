from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from database import UserModel, get_db
from schemas.cart import (
    CartActionResponseSchema,
    CartItemCreateSchema,
    CartItemResponseSchema,
    CartListResponseSchema,
)
from security.dependencies import get_current_user
from services import cart as cart_service

router = APIRouter()


@router.get("/", summary="View cart", response_model=CartListResponseSchema)
async def view_cart(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> CartListResponseSchema:
    return await cart_service.get_cart_items(db=db, current_user=current_user)


@router.post(
    "/items/",
    summary="Add to cart",
    response_model=CartItemResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def add_to_cart(
    payload: CartItemCreateSchema,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> CartItemResponseSchema:
    return await cart_service.add_cart_item(
        db=db, current_user=current_user, movie_id=payload.movie_id
    )


@router.delete(
    "/items/{item_id}",
    summary="Remove from cart",
    response_model=CartActionResponseSchema,
)
async def remove_from_cart(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> CartActionResponseSchema:
    return await cart_service.remove_cart_item(
        db=db, current_user=current_user, item_id=item_id
    )


@router.delete("/", summary="Clear cart", response_model=CartActionResponseSchema)
async def clear_cart(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> CartActionResponseSchema:
    return await cart_service.clear_cart(db=db, current_user=current_user)
