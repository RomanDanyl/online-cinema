from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from database import UserModel, get_db, UserGroupEnum
from schemas.orders import (
    OrderListResponseSchema,
    OrderSchema,
    OrderAdminQueryParamsSchema,
)
from security.dependencies import get_current_user, require_roles
from services import orders as orders_service

router = APIRouter()


@router.get("/", summary="List orders", response_model=OrderListResponseSchema)
async def list_orders(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> OrderListResponseSchema:
    orders = await orders_service.list_orders(db=db, current_user=current_user)
    return OrderListResponseSchema(items=orders)


@router.post(
    "/",
    summary="Create order",
    response_model=OrderSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_order(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> OrderSchema:
    order = await orders_service.create_order(db=db, current_user=current_user)
    return OrderSchema.model_validate(order)


@router.post(
    "/{order_id}/cancel",
    summary="Cancel pending order",
    response_model=OrderSchema,
)
async def cancel_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> OrderSchema:
    order = await orders_service.cancel_order(
        db=db,
        current_user=current_user,
        order_id=order_id,
    )
    return OrderSchema.model_validate(order)


@router.get(
    "/admin",
    dependencies=[Depends(require_roles(allowed_roles=(UserGroupEnum.ADMIN,)))],
    summary="List all orders",
    response_model=OrderListResponseSchema,
)
async def list_all_orders(
    query: OrderAdminQueryParamsSchema = Depends(),
    db: AsyncSession = Depends(get_db),
) -> OrderListResponseSchema:
    orders = await orders_service.list_all_orders(
        db=db,
        user_id=query.user_id,
        status=query.status,
        date_from=query.date_from,
        date_to=query.date_to,
    )
    return OrderListResponseSchema(items=orders)
