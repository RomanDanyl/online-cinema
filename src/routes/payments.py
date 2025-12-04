from fastapi import APIRouter, HTTPException, status

router = APIRouter()


def _not_implemented(detail: str):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=detail)


@router.get("/", summary="List payments (stub)")
async def list_payments():
    _not_implemented("Payments flow is not implemented yet.")


@router.post("/webhook/", summary="Payment webhook (stub)")
async def payment_webhook():
    _not_implemented("Payment webhook handling is not implemented yet.")
