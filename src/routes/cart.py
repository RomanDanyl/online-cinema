from fastapi import APIRouter, HTTPException, status

router = APIRouter()


def _not_implemented(detail: str):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=detail)


@router.get("/", summary="View cart (stub)")
async def view_cart():
    _not_implemented("Cart endpoints are not implemented yet.")


@router.post("/items/", summary="Add to cart (stub)")
async def add_to_cart():
    _not_implemented("Cart modification is not implemented yet.")


@router.delete("/items/{item_id}", summary="Remove from cart (stub)")
async def remove_from_cart(item_id: int):
    _not_implemented("Cart modification is not implemented yet.")
