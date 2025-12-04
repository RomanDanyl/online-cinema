from fastapi import APIRouter, HTTPException, status

router = APIRouter()


def _not_implemented(detail: str):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=detail)


@router.get("/", summary="List orders (stub)")
async def list_orders():
    _not_implemented("Order history is not implemented yet.")


@router.post("/", summary="Create order (stub)")
async def create_order():
    _not_implemented("Order creation is not implemented yet.")
