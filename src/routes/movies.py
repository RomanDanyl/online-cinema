from typing import Optional

from fastapi import APIRouter, HTTPException, status, Query, Depends
from sqlalchemy import (
    select,
    func,
    or_,
    and_,
    asc,
    desc,
    literal,
    case,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, aliased

from database import (
    get_db,
    MovieModel,
    MovieRatingModel,
    MovieReactionModel,
    MovieCommentModel,
    MovieFavoriteModel,
    GenreModel,
    StarModel,
    DirectorModel,
    UserReactionsEnum,
    UserModel,
)
from schemas import MessageResponseSchema
from schemas.movies import (
    MovieListResponseSchema,
    MovieListItemSchema,
    GenreListResponseSchema,
    GenreWithMoviesCountSchema,
    MovieRatingRequestSchema,
)
from security.dependencies import get_current_user, get_optional_user

router = APIRouter()


def get_movie_list_query_params(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50),
    search: Optional[str] = Query(
        None, description="Search by title, description, actor, or director"
    ),
    year: Optional[int] = Query(None, ge=1888, description="Filter by release year"),
    year_from: Optional[int] = Query(
        None, ge=1888, description="Filter by minimum release year"
    ),
    year_to: Optional[int] = Query(
        None, ge=1888, description="Filter by maximum release year"
    ),
    imdb_from: Optional[float] = Query(
        None, ge=0, le=10, description="Minimum IMDb rating"
    ),
    imdb_to: Optional[float] = Query(
        None, ge=0, le=10, description="Maximum IMDb rating"
    ),
    genre_id: Optional[int] = Query(None, ge=1, description="Filter by genre"),
    sort_by: str = Query(
        "release_year",
        pattern="^(price|release_year|popularity|imdb)$",
        description="Sort movies by price, release year, popularity, or IMDb rating",
    ),
    sort_order: str = Query(
        "desc",
        pattern="^(asc|desc)$",
        description="Sort order",
    ),
) -> dict:
    return {
        "search": search,
        "year": year,
        "year_from": year_from,
        "year_to": year_to,
        "imdb_from": imdb_from,
        "imdb_to": imdb_to,
        "genre_id": genre_id,
        "sort_by": sort_by,
        "sort_order": sort_order,
        "page": page,
        "per_page": per_page,
    }


def _not_implemented(detail: str):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=detail)


async def _ensure_movie_exists(movie_id: int, db: AsyncSession) -> None:
    exists_stmt = select(MovieModel.id).where(MovieModel.id == movie_id)
    if (await db.execute(exists_stmt)).scalar() is None:
        raise HTTPException(status_code=404, detail="Movie not found.")


def _apply_movie_filters(
    base_stmt,
    search: Optional[str],
    year: Optional[int],
    year_from: Optional[int],
    year_to: Optional[int],
    imdb_from: Optional[float],
    imdb_to: Optional[float],
    genre_id: Optional[int],
):
    if search:
        term = f"%{search.strip()}%"
        base_stmt = base_stmt.where(
            or_(
                MovieModel.name.ilike(term),
                MovieModel.description.ilike(term),
                MovieModel.stars.any(StarModel.name.ilike(term)),
                MovieModel.directors.any(DirectorModel.name.ilike(term)),
            )
        )

    if genre_id:
        base_stmt = base_stmt.join(MovieModel.genres).where(GenreModel.id == genre_id)

    if year is not None:
        base_stmt = base_stmt.where(MovieModel.year == year)
    else:
        if year_from is not None:
            base_stmt = base_stmt.where(MovieModel.year >= year_from)
        if year_to is not None:
            base_stmt = base_stmt.where(MovieModel.year <= year_to)

    if imdb_from is not None:
        base_stmt = base_stmt.where(MovieModel.imdb >= imdb_from)
    if imdb_to is not None:
        base_stmt = base_stmt.where(MovieModel.imdb <= imdb_to)

    return base_stmt


async def _fetch_movie_list(
    *,
    base_stmt,
    page: int,
    per_page: int,
    sort_by: str,
    sort_order: str,
    db: AsyncSession,
    current_user: Optional[UserModel],
) -> MovieListResponseSchema:
    offset = (page - 1) * per_page

    # total count (no order/limit)
    base_subquery = base_stmt.subquery()
    count_stmt = select(func.count()).select_from(base_subquery)
    total_items = (await db.execute(count_stmt)).scalar() or 0

    # Prefer 200 with empty list in many APIs, but keep your behavior:
    if total_items == 0:
        raise HTTPException(status_code=404, detail="No movies found.")

    sort_fields = {
        "price": MovieModel.price,
        "release_year": MovieModel.year,
        "popularity": MovieModel.votes,
        "imdb": MovieModel.imdb,  # external IMDb
    }
    sort_column = sort_fields.get(sort_by, MovieModel.year)
    sort_clause = desc(sort_column) if sort_order == "desc" else asc(sort_column)

    # page ids (apply sorting + pagination here)
    page_ids_stmt = (
        base_stmt.order_by(sort_clause, MovieModel.id.desc())
        .offset(offset)
        .limit(per_page)
    )
    page_ids_sq = page_ids_stmt.subquery()

    # aggregates (1 row per movie_id)
    ratings_sq = (
        select(
            MovieRatingModel.movie_id.label("movie_id"),
            func.avg(MovieRatingModel.rating).label("avg_rating"),
            func.count(MovieRatingModel.id).label("ratings_count"),
        )
        .group_by(MovieRatingModel.movie_id)
        .subquery()
    )

    likes_sq = (
        select(
            MovieReactionModel.movie_id.label("movie_id"),
            func.count(MovieReactionModel.id)
            .filter(MovieReactionModel.reaction == UserReactionsEnum.LIKE)
            .label("likes_count"),
        )
        .group_by(MovieReactionModel.movie_id)
        .subquery()
    )

    comments_sq = (
        select(
            MovieCommentModel.movie_id.label("movie_id"),
            func.count(MovieCommentModel.id).label("comments_count"),
        )
        .group_by(MovieCommentModel.movie_id)
        .subquery()
    )

    # user-specific joins (avoid extra subqueries; keep them indexed by (movie_id, user_id))
    UserFav = aliased(MovieFavoriteModel)
    UserRating = aliased(MovieRatingModel)
    UserReaction = aliased(MovieReactionModel)

    if current_user:
        is_favorite_col = case(
            (UserFav.id.isnot(None), True),
            else_=False,
        ).label("is_favorite")

        user_rating_col = UserRating.rating.label("user_rating")
        user_reaction_col = UserReaction.reaction.label("user_reaction")
    else:
        is_favorite_col = literal(False).label("is_favorite")
        user_rating_col = literal(None).label("user_rating")
        user_reaction_col = literal(None).label("user_reaction")

    stmt = (
        select(
            MovieModel,
            ratings_sq.c.avg_rating,
            ratings_sq.c.ratings_count,
            likes_sq.c.likes_count,
            comments_sq.c.comments_count,
            is_favorite_col,
            user_rating_col,
            user_reaction_col,
        )
        .join(page_ids_sq, page_ids_sq.c.id == MovieModel.id)
        .outerjoin(ratings_sq, ratings_sq.c.movie_id == MovieModel.id)
        .outerjoin(likes_sq, likes_sq.c.movie_id == MovieModel.id)
        .outerjoin(comments_sq, comments_sq.c.movie_id == MovieModel.id)
        .options(
            selectinload(MovieModel.genres),
            selectinload(MovieModel.stars),
            selectinload(MovieModel.directors),
        )
        .order_by(sort_clause, MovieModel.id.desc())  # stable order on the page
    )

    if current_user:
        stmt = (
            stmt.outerjoin(
                UserFav,
                and_(
                    UserFav.movie_id == MovieModel.id,
                    UserFav.user_id == current_user.id,
                ),
            )
            .outerjoin(
                UserRating,
                and_(
                    UserRating.movie_id == MovieModel.id,
                    UserRating.user_id == current_user.id,
                ),
            )
            .outerjoin(
                UserReaction,
                and_(
                    UserReaction.movie_id == MovieModel.id,
                    UserReaction.user_id == current_user.id,
                ),
            )
        )

    rows = (await db.execute(stmt)).all()
    if not rows:
        raise HTTPException(status_code=404, detail="No movies found.")

    items: list[MovieListItemSchema] = []
    for row in rows:
        movie = row[0]

        ratings_count = int(row.ratings_count or 0)
        avg_rating = (
            float(row.avg_rating)
            if row.avg_rating is not None and ratings_count > 0
            else None
        )

        item = MovieListItemSchema.model_validate(
            movie,
            update={
                "avg_rating": avg_rating,
                "ratings_count": ratings_count,
                "likes_count": int(row.likes_count or 0),
                "comments_count": int(row.comments_count or 0),
                "is_favorite": bool(row.is_favorite),
                "user_rating": row.user_rating,
                "user_reaction": row.user_reaction,
            },
        )
        items.append(item)

    return MovieListResponseSchema(
        items=items,
        total=total_items,
        page=page,
        page_size=per_page,
    )


@router.get(
    "/genres",
    summary="List genres with movies count",
    response_model=GenreListResponseSchema,
)
async def list_genres(db: AsyncSession = Depends(get_db)) -> GenreListResponseSchema:
    genre_counts_stmt = (
        select(
            GenreModel.id,
            GenreModel.name,
            func.count(MovieModel.id).label("movies_count"),
        )
        .join(MovieModel.genres, isouter=True)
        .group_by(GenreModel.id)
        .order_by(GenreModel.name.asc())
    )

    genres = (await db.execute(genre_counts_stmt)).all()
    items = [
        GenreWithMoviesCountSchema(
            id=genre.id,
            name=genre.name,
            movies_count=genre.movies_count or 0,
        )
        for genre in genres
    ]

    return GenreListResponseSchema(items=items)


@router.get(
    "/",
    summary="List movies",
    response_model=MovieListResponseSchema,
)
async def list_movies(
    query_params: dict = Depends(get_movie_list_query_params),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[UserModel] = Depends(get_optional_user),
) -> MovieListResponseSchema:
    base_stmt = select(MovieModel.id)

    base_stmt = _apply_movie_filters(
        base_stmt=base_stmt,
        search=query_params["search"],
        year=query_params["year"],
        year_from=query_params["year_from"],
        year_to=query_params["year_to"],
        imdb_from=query_params["imdb_from"],
        imdb_to=query_params["imdb_to"],
        genre_id=query_params["genre_id"],
    )

    return await _fetch_movie_list(
        base_stmt=base_stmt,
        page=query_params["page"],
        per_page=query_params["per_page"],
        sort_by=query_params["sort_by"],
        sort_order=query_params["sort_order"],
        db=db,
        current_user=current_user,
    )


@router.get(
    "/favorites",
    summary="List favorite movies",
    response_model=MovieListResponseSchema,
)
async def list_favorite_movies(
    query_params: dict = Depends(get_movie_list_query_params),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> MovieListResponseSchema:
    base_stmt = (
        select(MovieModel.id)
        .join(MovieFavoriteModel, MovieFavoriteModel.movie_id == MovieModel.id)
        .where(MovieFavoriteModel.user_id == current_user.id)
    )

    base_stmt = _apply_movie_filters(
        base_stmt=base_stmt,
        search=query_params["search"],
        year=query_params["year"],
        year_from=query_params["year_from"],
        year_to=query_params["year_to"],
        imdb_from=query_params["imdb_from"],
        imdb_to=query_params["imdb_to"],
        genre_id=query_params["genre_id"],
    )

    return await _fetch_movie_list(
        base_stmt=base_stmt,
        page=query_params["page"],
        per_page=query_params["per_page"],
        sort_by=query_params["sort_by"],
        sort_order=query_params["sort_order"],
        db=db,
        current_user=current_user,
    )


@router.post("/", summary="Create movie (stub)")
async def create_movie():
    _not_implemented("Movie creation is not implemented yet.")


@router.get("/{movie_id}", summary="Retrieve movie (stub)")
async def get_movie(movie_id: int):
    _not_implemented("Movie retrieval is not implemented yet.")


async def _upsert_movie_reaction(
    *,
    movie_id: int,
    reaction: UserReactionsEnum,
    db: AsyncSession,
    current_user: UserModel,
) -> None:
    await _ensure_movie_exists(movie_id=movie_id, db=db)

    stmt = select(MovieReactionModel).where(
        MovieReactionModel.movie_id == movie_id,
        MovieReactionModel.user_id == current_user.id,
    )
    existing_reaction = (await db.execute(stmt)).scalars().first()
    if existing_reaction:
        existing_reaction.reaction = reaction
    else:
        db.add(
            MovieReactionModel(
                movie_id=movie_id,
                user_id=current_user.id,
                reaction=reaction,
            )
        )
    await db.commit()


@router.post(
    "/{movie_id}/like",
    summary="Like a movie",
    response_model=MessageResponseSchema,
)
async def like_movie(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> MessageResponseSchema:
    await _upsert_movie_reaction(
        movie_id=movie_id,
        reaction=UserReactionsEnum.LIKE,
        db=db,
        current_user=current_user,
    )
    return MessageResponseSchema(message="Movie liked.")


@router.post(
    "/{movie_id}/dislike",
    summary="Dislike a movie",
    response_model=MessageResponseSchema,
)
async def dislike_movie(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> MessageResponseSchema:
    await _upsert_movie_reaction(
        movie_id=movie_id,
        reaction=UserReactionsEnum.DISLIKE,
        db=db,
        current_user=current_user,
    )
    return MessageResponseSchema(message="Movie disliked.")


@router.post(
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
    await _ensure_movie_exists(movie_id=movie_id, db=db)

    favorite_exists_stmt = select(MovieFavoriteModel.id).where(
        MovieFavoriteModel.movie_id == movie_id,
        MovieFavoriteModel.user_id == current_user.id,
    )
    if (await db.execute(favorite_exists_stmt)).scalar() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Movie already in favorites.",
        )

    db.add(
        MovieFavoriteModel(
            movie_id=movie_id,
            user_id=current_user.id,
        )
    )
    await db.commit()

    return MessageResponseSchema(message="Movie added to favorites.")


@router.delete(
    "/{movie_id}/favorites",
    summary="Remove movie from favorites",
    response_model=MessageResponseSchema,
)
async def remove_movie_from_favorites(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> MessageResponseSchema:
    await _ensure_movie_exists(movie_id=movie_id, db=db)

    favorite_stmt = select(MovieFavoriteModel).where(
        MovieFavoriteModel.movie_id == movie_id,
        MovieFavoriteModel.user_id == current_user.id,
    )
    favorite = (await db.execute(favorite_stmt)).scalars().first()
    if not favorite:
        raise HTTPException(status_code=404, detail="Movie not in favorites.")

    await db.delete(favorite)
    await db.commit()

    return MessageResponseSchema(message="Movie removed from favorites.")


@router.post(
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
    await _ensure_movie_exists(movie_id=movie_id, db=db)

    rating_stmt = select(MovieRatingModel).where(
        MovieRatingModel.movie_id == movie_id,
        MovieRatingModel.user_id == current_user.id,
    )
    existing_rating = (await db.execute(rating_stmt)).scalars().first()

    if existing_rating:
        existing_rating.rating = payload.rating
    else:
        db.add(
            MovieRatingModel(
                movie_id=movie_id,
                user_id=current_user.id,
                rating=payload.rating,
            )
        )

    await db.commit()

    return MessageResponseSchema(message="Rating saved.")
