from __future__ import annotations

from typing import Iterable, Optional, Sequence, TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy import and_, asc, case, delete, desc, func, literal, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from database import (
    CertificationModel,
    DirectorModel,
    GenreModel,
    MovieCommentLikeModel,
    MovieCommentModel,
    MovieFavoriteModel,
    MovieModel,
    MovieRatingModel,
    MovieReactionModel,
    OrderItemModel,
    StarModel,
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
    MovieListItemSchema,
    MovieListQueryParams,
    MovieListResponseSchema,
    MovieRatingRequestSchema,
    MovieStarSchema,
    MovieUpdateSchema,
)

if TYPE_CHECKING:
    from notifications import EmailSenderInterface


def apply_movie_filters(
    base_stmt,
    *,
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
        base_stmt = base_stmt.where(MovieModel.genres.any(GenreModel.id == genre_id))

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


async def get_movie_or_404(*, db: AsyncSession, movie_id: int) -> MovieModel:
    stmt = select(MovieModel).where(MovieModel.id == movie_id)
    movie = (await db.execute(stmt)).scalar_one_or_none()
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found.")
    return movie


async def fetch_movie_list(
    *,
    db: AsyncSession,
    base_stmt,
    query: MovieListQueryParams,
    current_user: Optional[UserModel],
) -> MovieListResponseSchema:
    offset = (query.page - 1) * query.per_page

    base_subquery = base_stmt.subquery()
    count_stmt = select(func.count()).select_from(base_subquery)
    total_items = (await db.execute(count_stmt)).scalar() or 0
    if total_items == 0:
        raise HTTPException(status_code=404, detail="No movies found.")

    sort_fields = {
        "price": MovieModel.price,
        "release_year": MovieModel.year,
        "popularity": MovieModel.votes,
        "imdb": MovieModel.imdb,
    }
    sort_column = sort_fields.get(query.sort_by, MovieModel.year)
    sort_clause = desc(sort_column) if query.sort_order == "desc" else asc(sort_column)

    page_ids_stmt = (
        base_stmt.order_by(sort_clause, MovieModel.id.desc())
        .offset(offset)
        .limit(query.per_page)
    )
    page_ids_sq = page_ids_stmt.subquery()

    ratings_sq = (
        select(
            MovieRatingModel.movie_id.label("movie_id"),
            func.avg(MovieRatingModel.rating).label("avg_rating"),
            func.count(MovieRatingModel.id).label("ratings_count"),
        )
        .join(page_ids_sq, page_ids_sq.c.id == MovieRatingModel.movie_id)
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
        .join(page_ids_sq, page_ids_sq.c.id == MovieReactionModel.movie_id)
        .group_by(MovieReactionModel.movie_id)
        .subquery()
    )

    comments_sq = (
        select(
            MovieCommentModel.movie_id.label("movie_id"),
            func.count(MovieCommentModel.id).label("comments_count"),
        )
        .join(page_ids_sq, page_ids_sq.c.id == MovieCommentModel.movie_id)
        .group_by(MovieCommentModel.movie_id)
        .subquery()
    )

    user_fav = aliased(MovieFavoriteModel)
    user_rating = aliased(MovieRatingModel)
    user_reaction = aliased(MovieReactionModel)

    if current_user:
        is_favorite_col = case(
            (user_fav.id.isnot(None), True),
            else_=False,
        ).label("is_favorite")
        user_rating_col = user_rating.rating.label("user_rating")
        user_reaction_col = user_reaction.reaction.label("user_reaction")
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
        .order_by(sort_clause, MovieModel.id.desc())
    )

    if current_user:
        stmt = (
            stmt.outerjoin(
                user_fav,
                and_(
                    user_fav.movie_id == MovieModel.id,
                    user_fav.user_id == current_user.id,
                ),
            )
            .outerjoin(
                user_rating,
                and_(
                    user_rating.movie_id == MovieModel.id,
                    user_rating.user_id == current_user.id,
                ),
            )
            .outerjoin(
                user_reaction,
                and_(
                    user_reaction.movie_id == MovieModel.id,
                    user_reaction.user_id == current_user.id,
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

        items.append(
            MovieListItemSchema.model_validate(
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
        )

    return MovieListResponseSchema(
        items=items,
        total=total_items,
        page=query.page,
        page_size=query.per_page,
    )


async def upsert_movie_reaction(
    *,
    db: AsyncSession,
    movie_id: int,
    reaction: UserReactionsEnum,
    current_user: UserModel,
) -> None:
    stmt = (
        pg_insert(MovieReactionModel)
        .values(movie_id=movie_id, user_id=current_user.id, reaction=reaction)
        .on_conflict_do_update(
            index_elements=["movie_id", "user_id"],
            set_={"reaction": reaction},
        )
    )
    try:
        await db.execute(stmt)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=404, detail="Movie not found.")


async def add_movie_to_favorites(
    *, db: AsyncSession, movie_id: int, current_user: UserModel
) -> MessageResponseSchema:
    stmt = (
        pg_insert(MovieFavoriteModel)
        .values(movie_id=movie_id, user_id=current_user.id)
        .on_conflict_do_nothing(index_elements=["movie_id", "user_id"])
        .returning(MovieFavoriteModel.id)
    )
    try:
        inserted_id = (await db.execute(stmt)).scalar()
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=404, detail="Movie not found.")

    if inserted_id is None:
        raise HTTPException(status_code=409, detail="Movie already in favorites.")

    return MessageResponseSchema(message="Movie added to favorites.")


async def remove_movie_from_favorites(
    *, db: AsyncSession, movie_id: int, current_user: UserModel
) -> MessageResponseSchema:
    stmt = (
        delete(MovieFavoriteModel)
        .where(
            MovieFavoriteModel.movie_id == movie_id,
            MovieFavoriteModel.user_id == current_user.id,
        )
        .returning(MovieFavoriteModel.id)
    )
    deleted_id = (await db.execute(stmt)).scalar()
    await db.commit()

    if deleted_id is None:
        raise HTTPException(status_code=404, detail="Movie not in favorites.")

    return MessageResponseSchema(message="Movie removed from favorites.")


async def rate_movie(
    *,
    db: AsyncSession,
    movie_id: int,
    payload: MovieRatingRequestSchema,
    current_user: UserModel,
) -> MessageResponseSchema:
    stmt = (
        pg_insert(MovieRatingModel)
        .values(movie_id=movie_id, user_id=current_user.id, rating=payload.rating)
        .on_conflict_do_update(
            index_elements=["movie_id", "user_id"],
            set_={"rating": payload.rating},
        )
    )
    try:
        await db.execute(stmt)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=404, detail="Movie not found.")

    return MessageResponseSchema(message="Rating saved.")


async def get_parent_comment_or_404(
    *,
    db: AsyncSession,
    movie_id: int,
    parent_comment_id: int,
) -> MovieCommentModel:
    stmt = (
        select(MovieCommentModel)
        .options(selectinload(MovieCommentModel.user))
        .where(
            MovieCommentModel.id == parent_comment_id,
            MovieCommentModel.movie_id == movie_id,
        )
    )
    parent_comment = (await db.execute(stmt)).scalar_one_or_none()
    if not parent_comment:
        raise HTTPException(status_code=404, detail="Parent comment not found.")
    return parent_comment


async def get_comment_with_relations(
    *, db: AsyncSession, comment_id: int
) -> Optional[MovieCommentModel]:
    stmt = (
        select(MovieCommentModel)
        .options(
            selectinload(MovieCommentModel.user),
            selectinload(MovieCommentModel.movie),
        )
        .where(MovieCommentModel.id == comment_id)
    )
    return (await db.execute(stmt)).scalars().first()


async def send_comment_notification(
    *,
    recipient: UserModel,
    actor: UserModel,
    movie: MovieModel,
    subject: str,
    intro_message: str,
    comment_text: str,
    email_sender: "EmailSenderInterface",
) -> None:
    if recipient.email is None or recipient.id == actor.id:
        return
    await email_sender.send_comment_notification(
        email=recipient.email,
        subject=subject,
        intro_message=intro_message,
        movie_name=movie.name,
        comment_text=comment_text,
    )


async def create_movie_comment(
    *,
    db: AsyncSession,
    movie_id: int,
    payload: MovieCommentCreateSchema,
    current_user: UserModel,
    email_sender: "EmailSenderInterface",
) -> MovieCommentResponseSchema:
    movie = await get_movie_or_404(db=db, movie_id=movie_id)

    parent_comment: Optional[MovieCommentModel] = None
    if payload.parent_comment_id is not None:
        parent_comment = await get_parent_comment_or_404(
            db=db,
            movie_id=movie_id,
            parent_comment_id=payload.parent_comment_id,
        )

    comment = MovieCommentModel(
        movie_id=movie_id,
        user_id=current_user.id,
        text=payload.text,
        parent_comment_id=payload.parent_comment_id,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)

    if parent_comment:
        await send_comment_notification(
            recipient=parent_comment.user,
            actor=current_user,
            movie=movie,
            subject="New reply to your comment",
            intro_message=(
                f'Your comment on "{movie.name}" received a reply from '
                f"{current_user.email}."
            ),
            comment_text=payload.text,
            email_sender=email_sender,
        )

    return MovieCommentResponseSchema.model_validate(comment)


async def like_movie_comment(
    *,
    db: AsyncSession,
    comment_id: int,
    current_user: UserModel,
    email_sender: "EmailSenderInterface",
) -> MessageResponseSchema:
    comment = await get_comment_with_relations(db=db, comment_id=comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found.")

    stmt = (
        pg_insert(MovieCommentLikeModel)
        .values(comment_id=comment_id, user_id=current_user.id)
        .on_conflict_do_nothing(index_elements=["comment_id", "user_id"])
        .returning(MovieCommentLikeModel.id)
    )
    inserted_id = (await db.execute(stmt)).scalar()
    await db.commit()

    if inserted_id is None:
        raise HTTPException(status_code=409, detail="Comment already liked.")

    if comment.user_id != current_user.id:
        await send_comment_notification(
            recipient=comment.user,
            actor=current_user,
            movie=comment.movie,
            subject="Your comment received a like",
            intro_message=(
                f'Your comment on "{comment.movie.name}" received a like from '
                f"{current_user.email}."
            ),
            comment_text=comment.text,
            email_sender=email_sender,
        )

    return MessageResponseSchema(message="Comment liked.")


async def get_entities_by_ids(
    *,
    db: AsyncSession,
    model,
    ids: Iterable[int],
    entity_name: str,
):
    id_list = list(ids)
    if not id_list:
        return []

    stmt = select(model).where(model.id.in_(id_list))
    result = (await db.execute(stmt)).scalars().all()

    found_ids = {entity.id for entity in result}
    missing = sorted({entity_id for entity_id in id_list if entity_id not in found_ids})
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{entity_name} not found: {', '.join(map(str, missing))}",
        )
    return result


async def get_certification_or_404(*, db: AsyncSession, certification_id: int) -> None:
    stmt = select(CertificationModel.id).where(
        CertificationModel.id == certification_id
    )
    if (await db.execute(stmt)).scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Certification not found.")


async def get_movie_with_relations_or_404(
    *, db: AsyncSession, movie_id: int
) -> MovieModel:
    stmt = (
        select(MovieModel)
        .options(
            selectinload(MovieModel.genres),
            selectinload(MovieModel.stars),
            selectinload(MovieModel.directors),
            selectinload(MovieModel.certification),
        )
        .where(MovieModel.id == movie_id)
    )
    movie = (await db.execute(stmt)).scalars().unique().first()
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found.")
    return movie


async def create_movie_admin(
    *, db: AsyncSession, payload: MovieCreateSchema
) -> MovieItemSchema:
    await get_certification_or_404(db=db, certification_id=payload.certification_id)

    genres = await get_entities_by_ids(
        db=db, model=GenreModel, ids=payload.genre_ids, entity_name="Genres"
    )
    stars = await get_entities_by_ids(
        db=db, model=StarModel, ids=payload.star_ids, entity_name="Actors"
    )
    directors = await get_entities_by_ids(
        db=db, model=DirectorModel, ids=payload.director_ids, entity_name="Directors"
    )

    movie = MovieModel(
        name=payload.name,
        year=payload.year,
        time=payload.time,
        imdb=payload.imdb,
        votes=payload.votes,
        meta_score=payload.meta_score,
        gross=payload.gross,
        description=payload.description,
        price=payload.price,
        certification_id=payload.certification_id,
        genres=genres,
        stars=stars,
        directors=directors,
    )
    db.add(movie)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Movie with the same name, year, and duration already exists.",
        )

    await db.refresh(movie)
    movie_full = await get_movie_with_relations_or_404(db=db, movie_id=movie.id)
    return MovieItemSchema.model_validate(movie_full)


async def update_movie_admin(
    *, db: AsyncSession, movie_id: int, payload: MovieUpdateSchema
) -> MovieItemSchema:
    movie = await get_movie_with_relations_or_404(db=db, movie_id=movie_id)

    if payload.certification_id is not None:
        await get_certification_or_404(db=db, certification_id=payload.certification_id)
        movie.certification_id = payload.certification_id

    for field in (
        "name",
        "year",
        "time",
        "imdb",
        "votes",
        "meta_score",
        "gross",
        "description",
        "price",
    ):
        value = getattr(payload, field, None)
        if value is not None:
            setattr(movie, field, value)

    if payload.genre_ids is not None:
        movie.genres = await get_entities_by_ids(
            db=db, model=GenreModel, ids=payload.genre_ids, entity_name="Genres"
        )
    if payload.star_ids is not None:
        movie.stars = await get_entities_by_ids(
            db=db, model=StarModel, ids=payload.star_ids, entity_name="Actors"
        )
    if payload.director_ids is not None:
        movie.directors = await get_entities_by_ids(
            db=db,
            model=DirectorModel,
            ids=payload.director_ids,
            entity_name="Directors",
        )

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Movie with the same name, year, and duration already exists.",
        )

    await db.refresh(movie)
    movie_full = await get_movie_with_relations_or_404(db=db, movie_id=movie.id)
    return MovieItemSchema.model_validate(movie_full)


async def delete_movie_admin(
    *, db: AsyncSession, movie_id: int
) -> MessageResponseSchema:
    movie = await get_movie_with_relations_or_404(db=db, movie_id=movie_id)

    purchase_count = (
        await db.execute(
            select(func.count(OrderItemModel.id)).where(
                OrderItemModel.movie_id == movie_id
            )
        )
    ).scalar_one_or_none()

    if purchase_count:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Movie cannot be deleted because it has been purchased by users.",
        )

    await db.delete(movie)
    await db.commit()
    return MessageResponseSchema(message="Movie deleted successfully.")


# -------- Catalog CRUD (Genres / Actors) --------


async def list_genres(*, db: AsyncSession) -> list[GenreSchema]:
    stmt = select(GenreModel).order_by(GenreModel.name.asc())
    genres = (await db.execute(stmt)).scalars().all()
    return [GenreSchema.model_validate(g) for g in genres]


async def create_genre(*, db: AsyncSession, payload: GenreCreateSchema) -> GenreSchema:
    genre = GenreModel(name=payload.name)
    db.add(genre)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409, detail="Genre with this name already exists."
        )
    await db.refresh(genre)
    return GenreSchema.model_validate(genre)


async def update_genre(
    *, db: AsyncSession, genre_id: int, payload: GenreUpdateSchema
) -> GenreSchema:
    genre = (
        await db.execute(select(GenreModel).where(GenreModel.id == genre_id))
    ).scalar_one_or_none()
    if genre is None:
        raise HTTPException(status_code=404, detail="Genre not found.")

    genre.name = payload.name
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409, detail="Genre with this name already exists."
        )

    await db.refresh(genre)
    return GenreSchema.model_validate(genre)


async def delete_genre(*, db: AsyncSession, genre_id: int) -> MessageResponseSchema:
    genre = (
        await db.execute(select(GenreModel).where(GenreModel.id == genre_id))
    ).scalar_one_or_none()
    if genre is None:
        raise HTTPException(status_code=404, detail="Genre not found.")
    await db.delete(genre)
    await db.commit()
    return MessageResponseSchema(message="Genre deleted successfully.")


async def list_actors(*, db: AsyncSession) -> list[MovieStarSchema]:
    stmt = select(StarModel).order_by(StarModel.name.asc())
    actors = (await db.execute(stmt)).scalars().all()
    return [MovieStarSchema.model_validate(a) for a in actors]


async def create_actor(
    *, db: AsyncSession, payload: ActorCreateSchema
) -> MovieStarSchema:
    actor = StarModel(name=payload.name)
    db.add(actor)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409, detail="Actor with this name already exists."
        )
    await db.refresh(actor)
    return MovieStarSchema.model_validate(actor)


async def update_actor(
    *, db: AsyncSession, actor_id: int, payload: ActorUpdateSchema
) -> MovieStarSchema:
    actor = (
        await db.execute(select(StarModel).where(StarModel.id == actor_id))
    ).scalar_one_or_none()
    if actor is None:
        raise HTTPException(status_code=404, detail="Actor not found.")

    actor.name = payload.name
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409, detail="Actor with this name already exists."
        )

    await db.refresh(actor)
    return MovieStarSchema.model_validate(actor)


async def delete_actor(*, db: AsyncSession, actor_id: int) -> MessageResponseSchema:
    actor = (
        await db.execute(select(StarModel).where(StarModel.id == actor_id))
    ).scalar_one_or_none()
    if actor is None:
        raise HTTPException(status_code=404, detail="Actor not found.")
    await db.delete(actor)
    await db.commit()
    return MessageResponseSchema(message="Actor deleted successfully.")
