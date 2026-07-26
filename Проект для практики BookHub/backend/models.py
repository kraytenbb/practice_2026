from datetime import datetime
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(
        Integer,
        primary_key=True
    )

    username = Column(
        String(50),
        unique=True,
        nullable=False
    )

    email = Column(
        String(255),
        unique=True,
        nullable=False
    )

    password_hash = Column(
        Text,
        nullable=False
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    library_items = relationship(
        "Library",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    reading_history = relationship(
        "ReadingHistory",
        back_populates="user",
        cascade="all, delete-orphan"
    )


class Book(Base):
    __tablename__ = "books"

    id = Column(
        Integer,
        primary_key=True
    )

    api_id = Column(
        String,
        unique=True
    )

    title = Column(
        String,
        nullable=False
    )

    author = Column(
        String
    )

    cover = Column(
        Text
    )

    description = Column(
        Text
    )

    year = Column(
        Integer
    )

    content = Column(
        Text
    )

    reading_url = Column(
        Text
    )


class Library(Base):
    __tablename__ = "library"

    id = Column(
        Integer,
        primary_key=True
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True
    )

    book_id = Column(
        Integer,
        ForeignKey("books.id"),
        nullable=False
    )

    user = relationship(
        "User",
        back_populates="library_items"
    )

    book = relationship(
        "Book"
    )


class ReadingHistory(Base):
    __tablename__ = "reading_history"

    id = Column(
        Integer,
        primary_key=True
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True
    )

    book_id = Column(
        Integer,
        ForeignKey("books.id"),
        nullable=False
    )

    last_opened = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    progress = Column(
        Integer,
        default=0,
        nullable=False
    )

    user = relationship(
        "User",
        back_populates="reading_history"
    )

    book = relationship(
        "Book"
    )
