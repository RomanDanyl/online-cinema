import stripe
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from config import BaseAppSettings, get_settings, get_accounts_email_notificator
from database import UserGroupEnum, UserModel, PaymentStatusEnum
from notifications import EmailSenderInterface
from schemas.payments import (
    PaymentCheckoutResponseSchema,
    PaymentCreateRequestSchema,
    PaymentListResponseSchema,
    PaymentSchema,
)
from security.dependencies import get_current_user, require_roles
from services import payments as payments_service
from database import get_db

router = APIRouter()


@router.get("/", summary="List payments", response_model=PaymentListResponseSchema)
async def list_payments(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> PaymentListResponseSchema:
    payments = await payments_service.list_payments(db=db, current_user=current_user)
    return PaymentListResponseSchema(
        items=[PaymentSchema.model_validate(payment) for payment in payments]
    )


@router.post(
    "/checkout",
    summary="Create Stripe checkout session",
    response_model=PaymentCheckoutResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_checkout_session(
    payload: PaymentCreateRequestSchema,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
    settings: BaseAppSettings = Depends(get_settings),
) -> PaymentCheckoutResponseSchema:
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stripe secret key is not configured.",
        )

    payment, session_id, session_url = await payments_service.create_checkout_session(
        db=db,
        current_user=current_user,
        order_id=payload.order_id,
        settings=settings,
    )
    return PaymentCheckoutResponseSchema(
        payment_id=payment.id,
        session_id=session_id,
        checkout_url=session_url,
        amount=payment.amount,
        currency=settings.STRIPE_CURRENCY,
    )


@router.get(
    "/admin",
    summary="List all payments",
    response_model=PaymentListResponseSchema,
    dependencies=[Depends(require_roles(allowed_roles=(UserGroupEnum.ADMIN,)))],
)
async def list_all_payments(
    user_id: int | None = Query(default=None),
    payment_status: PaymentStatusEnum | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> PaymentListResponseSchema:
    payments = await payments_service.list_all_payments(
        db=db,
        user_id=user_id,
        status=payment_status,
        date_from=date_from,
        date_to=date_to,
    )
    return PaymentListResponseSchema(
        items=[PaymentSchema.model_validate(payment) for payment in payments]
    )


@router.post("/webhook/", summary="Stripe payment webhook")
async def payment_webhook(
    request: Request,
    stripe_signature: str = Header(alias="Stripe-Signature", default=""),
    db: AsyncSession = Depends(get_db),
    settings: BaseAppSettings = Depends(get_settings),
    email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
):
    payload = await request.body()
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stripe webhook secret is not configured.",
        )

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=stripe_signature,
            secret=settings.STRIPE_WEBHOOK_SECRET,
        )
    except stripe.error.SignatureVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Stripe signature.",
        ) from exc

    event_type = event["type"]
    data_object = event["data"]["object"]
    payment_id = data_object.get("metadata", {}).get("payment_id")
    if not payment_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment metadata is missing.",
        )

    if event_type == "checkout.session.completed":
        payment, already_processed = await payments_service.handle_checkout_completed(
            db=db,
            payment_id=int(payment_id),
        )
        if already_processed:
            return {"status": "ok", "detail": "Payment already processed."}
        if payment.order and payment.order.user:
            await email_sender.send_payment_confirmation_email(
                email=payment.order.user.email,
                order_id=payment.order.id,
                amount=str(payment.amount),
            )
    elif event_type == "checkout.session.expired":
        await payments_service.handle_checkout_expired(
            db=db,
            payment_id=int(payment_id),
        )

    return {"status": "ok"}
