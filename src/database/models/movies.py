from decimal import Decimal
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import String, Table, Column, ForeignKey, Float, Text, DECIMAL, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from database import Base


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
    Column("director_id", ForeignKey("directors.id", ondelete="CASCADE"), primary_key=True),
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
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"Certification(id={self.id!r}, name={self.name!r})"


class MovieModel(Base):
    __tablename__ = "movies"
    __table_args__ = (
        UniqueConstraint("name", "year", "time", name="uq_movies_name_year_time"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    uuid: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        unique=True,
        nullable=False,
        default=uuid4
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
    price: Mapped[Decimal] = mapped_column(
        DECIMAL(10, 2), nullable=False
    )

    certification_id: Mapped[int] = mapped_column(
        ForeignKey("certifications.id", ondelete="RESTRICT"),
        nullable=False
    )

    certification: Mapped[CertificationModel] = relationship(
        back_populates="movies"
    )

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

    def __repr__(self) -> str:
        return f"Movie(id={self.id!r}, title={self.name!r})"
