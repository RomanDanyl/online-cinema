from fastapi import FastAPI

from routes import (
    accounts_router,
    movies_public_router,
    movies_admin_router,
    cart_public_router,
    cart_admin_router,
    orders_router,
    payments_router,
)

app = FastAPI(title="Online Cinema API")

api_version_prefix = "/api/v1"

app.include_router(accounts_router, prefix=api_version_prefix, tags=["accounts"])
app.include_router(
    movies_public_router,
    prefix=api_version_prefix,
    tags=["public_movies"],
)

app.include_router(
    movies_admin_router,
    prefix=api_version_prefix,
    tags=["admin_movies"],
)
app.include_router(
    cart_public_router, prefix=f"{api_version_prefix}/cart", tags=["public_cart"]
)
app.include_router(
    cart_admin_router, prefix=f"{api_version_prefix}/", tags=["admin_cart"]
)
app.include_router(
    orders_router, prefix=f"{api_version_prefix}/orders", tags=["orders"]
)
app.include_router(
    payments_router, prefix=f"{api_version_prefix}/payments", tags=["payments"]
)
