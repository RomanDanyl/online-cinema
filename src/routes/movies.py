from fastapi import APIRouter, HTTPException, status

router = APIRouter()


def _not_implemented(detail: str):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=detail)


@router.get("/", summary="List movies (stub)")
async def list_movies():
    _not_implemented("Movies catalog endpoints are not implemented yet.")


@router.post("/", summary="Create movie (stub)")
async def create_movie():
    _not_implemented("Movie creation is not implemented yet.")


@router.get("/{movie_id}", summary="Retrieve movie (stub)")
async def get_movie(movie_id: int):
    _not_implemented("Movie retrieval is not implemented yet.")
