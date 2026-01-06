from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_accounts_email_notificator
from database import (
    get_db,
    MovieFavoriteModel,
    MovieModel,
    UserGroupEnum,
    UserModel,
    UserReactionsEnum,
)
from schemas import MessageResponseSchema
from schemas.movies import (
    ActorCreateSchema,
    ActorUpdateSchema,
    GenreCreateSchema,
    GenreSchema,
    GenreUpdateSchema,
    MovieCommentCreateSchema,
    MovieCommentResponseSchema,
    MovieCreateSchema,
    MovieItemSchema,
    MovieListQueryParams,
    MovieListResponseSchema,
    MovieRatingRequestSchema,
    MovieStarSchema,
    MovieUpdateSchema,
    GenreListResponseSchema,
    MovieDetailSchema,
)
from security.dependencies import get_current_user, get_optional_user, require_roles
from services import movies as movie_service

if TYPE_CHECKING:
    from notifications import EmailSenderInterface


public_router = APIRouter(prefix="/movies", tags=["Movies"])

admin_access = Depends(
    require_roles(allowed_roles=(UserGroupEnum.MODERATOR, UserGroupEnum.ADMIN))
)
admin_router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[admin_access])


# -------- Public: list + favorites list --------


@public_router.get("/", summary="List movies", response_model=MovieListResponseSchema)
async def list_movies(
    query: MovieListQueryParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[UserModel] = Depends(get_optional_user),
) -> MovieListResponseSchema:
    base_stmt = select(MovieModel.id)
    base_stmt = movie_service.apply_movie_filters(
        base_stmt,
        search=query.search,
        year=query.year,
        year_from=query.year_from,
        year_to=query.year_to,
        imdb_from=query.imdb_from,
        imdb_to=query.imdb_to,
        genre_id=query.genre_id,
    )
    return await movie_service.fetch_movie_list(
        db=db, base_stmt=base_stmt, query=query, current_user=current_user
    )


@public_router.get(
    "/{movie_id}",
    summary="Get movie details",
    response_model=MovieDetailSchema,
)
async def get_movie_details(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[UserModel] = Depends(get_optional_user),
) -> MovieDetailSchema:
    return await movie_service.get_movie_details(
        db=db, movie_id=movie_id, current_user=current_user
    )


@public_router.get(
    "/genres",
    summary="List genres with movie counts",
    response_model=GenreListResponseSchema,
)
async def list_genres_with_counts(
    db: AsyncSession = Depends(get_db),
) -> GenreListResponseSchema:
    return await movie_service.list_genres_with_counts(db=db)


@public_router.get(
    "/favorites", summary="List favorite movies", response_model=MovieListResponseSchema
)
async def list_favorite_movies(
    query: MovieListQueryParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> MovieListResponseSchema:
    base_stmt = (
        select(MovieModel.id)
        .join(MovieFavoriteModel, MovieFavoriteModel.movie_id == MovieModel.id)
        .where(MovieFavoriteModel.user_id == current_user.id)
    )
    base_stmt = movie_service.apply_movie_filters(
        base_stmt,
        search=query.search,
        year=query.year,
        year_from=query.year_from,
        year_to=query.year_to,
        imdb_from=query.imdb_from,
        imdb_to=query.imdb_to,
        genre_id=query.genre_id,
    )
    return await movie_service.fetch_movie_list(
        db=db, base_stmt=base_stmt, query=query, current_user=current_user
    )


# -------- Public: reactions / favorites / rating --------


@public_router.post(
    "/{movie_id}/like", summary="Like a movie", response_model=MessageResponseSchema
)
async def like_movie(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> MessageResponseSchema:
    await movie_service.upsert_movie_reaction(
        db=db,
        movie_id=movie_id,
        reaction=UserReactionsEnum.LIKE,
        current_user=current_user,
    )
    return MessageResponseSchema(message="Movie liked.")


@public_router.post(
    "/{movie_id}/dislike",
    summary="Dislike a movie",
    response_model=MessageResponseSchema,
)
async def dislike_movie(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> MessageResponseSchema:
    await movie_service.upsert_movie_reaction(
        db=db,
        movie_id=movie_id,
        reaction=UserReactionsEnum.DISLIKE,
        current_user=current_user,
    )
    return MessageResponseSchema(message="Movie disliked.")


@public_router.post(
    "/{movie_id}/favorites",
    summary="Add movie to favorites",
    response_model=MessageResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def add_movie_to_favorites(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> MessageResponseSchema:
    return await movie_service.add_movie_to_favorites(
        db=db, movie_id=movie_id, current_user=current_user
    )


@public_router.delete(
    "/{movie_id}/favorites",
    summary="Remove movie from favorites",
    response_model=MessageResponseSchema,
)
async def remove_movie_from_favorites(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> MessageResponseSchema:
    return await movie_service.remove_movie_from_favorites(
        db=db, movie_id=movie_id, current_user=current_user
    )


@public_router.post(
    "/{movie_id}/rating",
    summary="Rate a movie",
    response_model=MessageResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def rate_movie(
    movie_id: int,
    payload: MovieRatingRequestSchema,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> MessageResponseSchema:
    return await movie_service.rate_movie(
        db=db, movie_id=movie_id, payload=payload, current_user=current_user
    )


# -------- Public: comments --------


@public_router.post(
    "/{movie_id}/comments",
    summary="Create movie comment",
    response_model=MovieCommentResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_movie_comment(
    movie_id: int,
    payload: MovieCommentCreateSchema,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
    email_sender: "EmailSenderInterface" = Depends(get_accounts_email_notificator),
) -> MovieCommentResponseSchema:
    return await movie_service.create_movie_comment(
        db=db,
        movie_id=movie_id,
        payload=payload,
        current_user=current_user,
        email_sender=email_sender,
    )


@public_router.post(
    "/comments/{comment_id}/like",
    summary="Like a movie comment",
    response_model=MessageResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def like_comment(
    comment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
    email_sender: "EmailSenderInterface" = Depends(get_accounts_email_notificator),
) -> MessageResponseSchema:
    return await movie_service.like_movie_comment(
        db=db,
        comment_id=comment_id,
        current_user=current_user,
        email_sender=email_sender,
    )


# -------- Admin: movies CRUD --------


@admin_router.post(
    "/movies",
    summary="Create movie",
    response_model=MovieItemSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_movie_admin(
    payload: MovieCreateSchema,
    db: AsyncSession = Depends(get_db),
) -> MovieItemSchema:
    return await movie_service.create_movie_admin(db=db, payload=payload)


@admin_router.put(
    "/movies/{movie_id}",
    summary="Update movie",
    response_model=MovieItemSchema,
)
async def update_movie_admin(
    movie_id: int,
    payload: MovieUpdateSchema,
    db: AsyncSession = Depends(get_db),
) -> MovieItemSchema:
    return await movie_service.update_movie_admin(
        db=db, movie_id=movie_id, payload=payload
    )


@admin_router.delete(
    "/movies/{movie_id}",
    summary="Delete movie",
    response_model=MessageResponseSchema,
)
async def delete_movie_admin(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
) -> MessageResponseSchema:
    return await movie_service.delete_movie_admin(db=db, movie_id=movie_id)


# -------- Admin: genres CRUD --------


@admin_router.get("/genres", summary="List genres", response_model=list[GenreSchema])
async def list_genres_admin(db: AsyncSession = Depends(get_db)) -> list[GenreSchema]:
    return await movie_service.list_genres(db=db)


@admin_router.post(
    "/genres",
    summary="Create genre",
    response_model=GenreSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_genre_admin(
    payload: GenreCreateSchema,
    db: AsyncSession = Depends(get_db),
) -> GenreSchema:
    return await movie_service.create_genre(db=db, payload=payload)


@admin_router.put(
    "/genres/{genre_id}",
    summary="Update genre",
    response_model=GenreSchema,
)
async def update_genre_admin(
    genre_id: int,
    payload: GenreUpdateSchema,
    db: AsyncSession = Depends(get_db),
) -> GenreSchema:
    return await movie_service.update_genre(db=db, genre_id=genre_id, payload=payload)


@admin_router.delete(
    "/genres/{genre_id}",
    summary="Delete genre",
    response_model=MessageResponseSchema,
)
async def delete_genre_admin(
    genre_id: int,
    db: AsyncSession = Depends(get_db),
) -> MessageResponseSchema:
    return await movie_service.delete_genre(db=db, genre_id=genre_id)


# -------- Admin: actors CRUD --------


@admin_router.get(
    "/actors", summary="List actors", response_model=list[MovieStarSchema]
)
async def list_actors_admin(
    db: AsyncSession = Depends(get_db),
) -> list[MovieStarSchema]:
    return await movie_service.list_actors(db=db)


@admin_router.post(
    "/actors",
    summary="Create actor",
    response_model=MovieStarSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_actor_admin(
    payload: ActorCreateSchema,
    db: AsyncSession = Depends(get_db),
) -> MovieStarSchema:
    return await movie_service.create_actor(db=db, payload=payload)


@admin_router.put(
    "/actors/{actor_id}",
    summary="Update actor",
    response_model=MovieStarSchema,
)
async def update_actor_admin(
    actor_id: int,
    payload: ActorUpdateSchema,
    db: AsyncSession = Depends(get_db),
) -> MovieStarSchema:
    return await movie_service.update_actor(db=db, actor_id=actor_id, payload=payload)


@admin_router.delete(
    "/actors/{actor_id}",
    summary="Delete actor",
    response_model=MessageResponseSchema,
)
async def delete_actor_admin(
    actor_id: int,
    db: AsyncSession = Depends(get_db),
) -> MessageResponseSchema:
    return await movie_service.delete_actor(db=db, actor_id=actor_id)
