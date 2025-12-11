import enum
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    String,
    Table,
    Column,
    ForeignKey,
    Float,
    Text,
    DECIMAL,
    UniqueConstraint,
    Integer,
    DateTime,
    func,
    Enum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as SAUUID
from uuid import UUID as PyUUID

from database import Base

if TYPE_CHECKING:
    from database import UserModel

movie_genres = Table(
    "movie_genres",
    Base.metadata,
    Column("movie_id", ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True),
    Column("genre_id", ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True),
)


movie_stars = Table(
    "movie_stars",
    Base.metadata,
    Column("movie_id", ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True),
    Column("star_id", ForeignKey("stars.id", ondelete="CASCADE"), primary_key=True),
)


movie_directors = Table(
    "movie_directors",
    Base.metadata,
    Column("movie_id", ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "director_id", ForeignKey("directors.id", ondelete="CASCADE"), primary_key=True
    ),
)


class GenreModel(Base):
    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    movies: Mapped[List["MovieModel"]] = relationship(
        secondary=movie_genres,
        back_populates="genres",
    )

    def __repr__(self) -> str:
        return f"Genre(id={self.id!r}, name={self.name!r})"


class StarModel(Base):
    __tablename__ = "stars"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True, nullable=False)

    movies: Mapped[List["MovieModel"]] = relationship(
        secondary=movie_stars,
        back_populates="stars",
    )

    def __repr__(self) -> str:
        return f"Star(id={self.id!r}, name={self.name!r})"


class DirectorModel(Base):
    __tablename__ = "directors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True, nullable=False)

    movies: Mapped[List["MovieModel"]] = relationship(
        secondary=movie_directors,
        back_populates="directors",
    )

    def __repr__(self) -> str:
        return f"Director(id={self.id!r}, name={self.name!r})"


class CertificationModel(Base):
    __tablename__ = "certifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    movies: Mapped[List["MovieModel"]] = relationship(
        back_populates="certification",
    )

    def __repr__(self) -> str:
        return f"Certification(id={self.id!r}, name={self.name!r})"


class MovieModel(Base):
    __tablename__ = "movies"
    __table_args__ = (
        UniqueConstraint("name", "year", "time", name="uq_movies_name_year_time"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    uuid: Mapped[PyUUID] = mapped_column(
        SAUUID(as_uuid=True), unique=True, nullable=False, default=uuid4
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    year: Mapped[int] = mapped_column(nullable=False)
    time: Mapped[int] = mapped_column(nullable=False)

    imdb: Mapped[float] = mapped_column(Float, nullable=False)
    votes: Mapped[int] = mapped_column(nullable=False)
    meta_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    gross: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )

    description: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)

    certification_id: Mapped[int] = mapped_column(
        ForeignKey("certifications.id", ondelete="RESTRICT"), nullable=False
    )

    certification: Mapped[CertificationModel] = relationship(back_populates="movies")

    genres: Mapped[List[GenreModel]] = relationship(
        secondary=movie_genres,
        back_populates="movies",
    )

    stars: Mapped[List[StarModel]] = relationship(
        secondary=movie_stars,
        back_populates="movies",
    )

    directors: Mapped[List[DirectorModel]] = relationship(
        secondary=movie_directors,
        back_populates="movies",
    )
    ratings: Mapped[List["MovieRatingModel"]] = relationship(
        back_populates="movie", cascade="all, delete-orphan"
    )
    reactions: Mapped[List["MovieReactionModel"]] = relationship(
        back_populates="movie", cascade="all, delete-orphan"
    )
    favorited_by: Mapped[List["MovieFavoriteModel"]] = relationship(
        back_populates="movie", cascade="all, delete-orphan"
    )
    comments: Mapped[List["MovieCommentModel"]] = relationship(
        back_populates="movie", cascade="all, delete-orphan"
    )

    @classmethod
    def default_order_by(cls):
        return [cls.id.desc()]

    def __repr__(self) -> str:
        return f"Movie(id={self.id!r}, title={self.name!r})"


class MovieRatingModel(Base):
    __tablename__ = "movie_ratings"
    __table_args__ = (
        UniqueConstraint("user_id", "movie_id", name="uq_movie_rating_user_movie"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"), nullable=False
    )

    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1–10

    user: Mapped["UserModel"] = relationship(back_populates="movie_ratings")
    movie: Mapped[MovieModel] = relationship(back_populates="ratings")


class UserReactionsEnum(str, enum.Enum):
    LIKE = "like"
    DISLIKE = "dislike"


class MovieReactionModel(Base):
    __tablename__ = "movie_reactions"
    __table_args__ = (
        UniqueConstraint("user_id", "movie_id", name="uq_movie_reaction_user_movie"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"), nullable=False
    )

    reaction: Mapped[UserReactionsEnum] = mapped_column(
        Enum(UserReactionsEnum),
        nullable=False,
    )

    user: Mapped["UserModel"] = relationship(back_populates="movie_reactions")
    movie: Mapped["MovieModel"] = relationship(back_populates="reactions")


class MovieFavoriteModel(Base):
    __tablename__ = "movie_favorites"
    __table_args__ = (
        UniqueConstraint("user_id", "movie_id", name="uq_movie_favorite_user_movie"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"), nullable=False
    )

    user: Mapped["UserModel"] = relationship(back_populates="favorite_movies")
    movie: Mapped["MovieModel"] = relationship(back_populates="favorited_by")


class MovieCommentModel(Base):
    __tablename__ = "movie_comments"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"), nullable=False
    )

    text: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped["UserModel"] = relationship(back_populates="movie_comments")
    movie: Mapped["MovieModel"] = relationship(back_populates="comments")
