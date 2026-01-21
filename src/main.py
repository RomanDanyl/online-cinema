from fastapi import FastAPI

from routes import (
    accounts_router,
    movies_router,
    cart_router,
    orders_router,
    payments_router,
)

app = FastAPI(title="Online Cinema API")

api_version_prefix = "/api/v1"

app.include_router(accounts_router, prefix=api_version_prefix, tags=["accounts"])
app.include_router(
    movies_router,
    prefix=api_version_prefix,
    tags=["movies"],
)
app.include_router(
    cart_router, prefix=f"{api_version_prefix}/cart", tags=["carts"]
)
app.include_router(
    orders_router, prefix=f"{api_version_prefix}/orders", tags=["orders"]
)
app.include_router(
    payments_router, prefix=f"{api_version_prefix}/payments", tags=["payments"]
)
