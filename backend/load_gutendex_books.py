from __future__ import annotations

import re
import time
from typing import Optional

import requests
from requests.adapters import HTTPAdapter

from database import Base, SessionLocal, engine
from models import Book


GUTENDEX_URL = "https://gutendex.com/books"

NEW_BOOKS_TARGET = 1

LANGUAGE = "en"

MAX_PAGES = 50

MIN_CONTENT_LENGTH = 3000

CATALOG_TIMEOUT = 90
CATALOG_RETRIES = 5

TEXT_TIMEOUT = 90
TEXT_RETRIES = 3

REQUEST_DELAY_SECONDS = 0.20


def create_session() -> requests.Session:

    session = requests.Session()
    session.trust_env = False

    adapter = HTTPAdapter(
        pool_connections=10,
        pool_maxsize=10
    )

    session.mount("https://", adapter)
    session.mount("http://", adapter)

    session.headers.update(
        {
            "User-Agent": (
                "BookHub educational project "
                "(Gutendex importer)"
            ),
            "Accept": "application/json, text/plain, */*",
        }
    )

    return session


def clean_text(text: str) -> str:

    text = (
        text
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\ufeff", "")
    )

    start_patterns = (
        r"\*\*\* START OF THE PROJECT GUTENBERG EBOOK.*?\*\*\*",
        r"\*\*\* START OF THIS PROJECT GUTENBERG EBOOK.*?\*\*\*",
        r"\*\*\*START OF THE PROJECT GUTENBERG EBOOK.*?\*\*\*",
    )

    end_patterns = (
        r"\*\*\* END OF THE PROJECT GUTENBERG EBOOK.*",
        r"\*\*\* END OF THIS PROJECT GUTENBERG EBOOK.*",
        r"\*\*\*END OF THE PROJECT GUTENBERG EBOOK.*",
    )

    for pattern in start_patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE | re.DOTALL
        )

        if match:
            text = text[match.end():]
            break

    for pattern in end_patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE | re.DOTALL
        )

        if match:
            text = text[:match.start()]
            break

    text = re.sub(
        r"[ \t]+\n",
        "\n",
        text
    )

    text = re.sub(
        r"\n[ \t]*\n[ \t]*\n+",
        "\n\n",
        text
    )

    return text.strip()


def choose_text_url(
    formats: dict
) -> Optional[str]:
    """
    Выбирает лучший доступный TXT-файл.
    """
    preferred_types = (
        "text/plain; charset=utf-8",
        "text/plain; charset=us-ascii",
        "text/plain",
    )

    for mime_type in preferred_types:
        url = formats.get(mime_type)

        if url:
            return str(url)

    for mime_type, url in formats.items():
        if (
            str(mime_type).startswith("text/plain")
            and url
        ):
            return str(url)

    return None


def choose_cover_url(
    formats: dict
) -> Optional[str]:

    cover = formats.get("image/jpeg")

    return str(cover) if cover else None


def format_author(
    authors: list[dict]
) -> str:
    names = [
        str(author.get("name", "")).strip()
        for author in authors
        if str(author.get("name", "")).strip()
    ]

    return (
        ", ".join(names)
        if names
        else "Автор не указан"
    )


def create_description(
    book_data: dict
) -> str:
    summaries = book_data.get("summaries") or []

    if summaries:
        summary = str(summaries[0]).strip()

        if summary:
            return summary

    subjects = book_data.get("subjects") or []

    if subjects:
        return (
            "Темы произведения: "
            + "; ".join(
                str(subject)
                for subject in subjects[:4]
            )
            + "."
        )

    return "Описание отсутствует."


def get_existing_gutenberg_ids(
    db
) -> set[int]:
    rows = (
        db.query(Book.api_id)
        .filter(Book.api_id.like("gutendex:%"))
        .all()
    )

    result: set[int] = set()

    for row in rows:
        api_id = row[0]

        if not api_id:
            continue

        try:
            result.add(
                int(
                    str(api_id).split(
                        ":",
                        maxsplit=1
                    )[1]
                )
            )
        except (
            ValueError,
            IndexError,
        ):
            continue

    return result


def book_exists_by_title_author(
    db,
    title: str,
    author: str
) -> bool:

    return (
        db.query(Book.id)
        .filter(
            Book.title == title,
            Book.author == author
        )
        .first()
        is not None
    )


def fetch_gutendex_page(
    session: requests.Session,
    page_number: int
) -> Optional[dict]:

    params = {
        "languages": LANGUAGE,
        "sort": "popular",
        "mime_type": "text/plain",
        "page": page_number,
    }

    for attempt in range(
        1,
        CATALOG_RETRIES + 1
    ):
        try:
            print(
                f"  Попытка {attempt}/"
                f"{CATALOG_RETRIES}..."
            )

            response = session.get(
                GUTENDEX_URL,
                params=params,
                timeout=(
                    20,
                    CATALOG_TIMEOUT
                )
            )

            response.raise_for_status()
            payload = response.json()

            if isinstance(payload, dict):
                return payload

            print(
                "  Gutendex вернул неожиданный формат."
            )

        except requests.RequestException as error:
            print(
                "  Временная ошибка Gutendex: "
                f"{error}"
            )

        except ValueError as error:
            print(
                "  Не удалось прочитать JSON: "
                f"{error}"
            )

        if attempt < CATALOG_RETRIES:
            pause = attempt * 3

            print(
                f"  Повтор через {pause} сек."
            )

            time.sleep(pause)

    return None


def download_text(
    session: requests.Session,
    text_url: str
) -> Optional[str]:

    for attempt in range(
        1,
        TEXT_RETRIES + 1
    ):
        try:
            response = session.get(
                text_url,
                timeout=(
                    20,
                    TEXT_TIMEOUT
                ),
                allow_redirects=True
            )

            response.raise_for_status()

            response.encoding = (
                response.apparent_encoding
                or "utf-8"
            )

            raw_text = response.text

            beginning = raw_text[:700].lower()

            if (
                "<html" in beginning
                or "<!doctype html" in beginning
            ):
                print(
                    "  Вместо TXT получен HTML."
                )

                return None

            content = clean_text(raw_text)

            if len(content) < MIN_CONTENT_LENGTH:
                print(
                    "  Текст слишком короткий: "
                    f"{len(content)} символов."
                )

                return None

            return content

        except requests.RequestException as error:
            print(
                "  Ошибка скачивания текста "
                f"[{attempt}/{TEXT_RETRIES}]: "
                f"{error}"
            )

            if attempt < TEXT_RETRIES:
                time.sleep(attempt * 2)

    return None


def save_new_book(
    db,
    book_data: dict,
    content: str,
    text_url: str,
    cover_url: Optional[str]
) -> Book:
    gutenberg_id = int(book_data["id"])

    title = (
        str(book_data.get("title", "")).strip()
        or "Без названия"
    )

    author = format_author(
        book_data.get("authors", []) or []
    )

    book = Book(
        api_id=f"gutendex:{gutenberg_id}",
        title=title,
        author=author,
        cover=cover_url,
        description=create_description(book_data),
        year=None,
        content=content,
        reading_url=text_url
    )

    db.add(book)
    db.commit()
    db.refresh(book)

    return book


def load_new_books() -> None:

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    session = create_session()

    added_count = 0
    existing_count = 0
    missing_text_count = 0
    missing_cover_count = 0
    skipped_count = 0
    error_count = 0
    failed_pages = 0

    try:
        known_ids = get_existing_gutenberg_ids(db)

        print("=" * 65)
        print("BookHub — загрузка новых книг из Gutendex")
        print(
            f"Цель: добавить "
            f"{NEW_BOOKS_TARGET} новых книг"
        )
        print("Обложки берутся из Gutendex")
        print(
            "Уже загружено Gutenberg ID: "
            f"{len(known_ids)}"
        )
        print("=" * 65)
        print()

        for page_number in range(
            1,
            MAX_PAGES + 1
        ):
            if added_count >= NEW_BOOKS_TARGET:
                break

            print(
                f"Получаем страницу Gutendex "
                f"№{page_number}..."
            )

            payload = fetch_gutendex_page(
                session=session,
                page_number=page_number
            )

            if payload is None:
                failed_pages += 1
                error_count += 1

                print(
                    "  Страница недоступна после "
                    "всех попыток."
                )

                print(
                    "  Переходим к следующей странице."
                )

                print()

                continue

            books = payload.get("results", [])

            if not isinstance(books, list):
                error_count += 1

                print(
                    "  Некорректный список книг."
                )

                continue

            if not books:
                print(
                    "  На странице больше нет книг."
                )

                break

            for book_data in books:
                if added_count >= NEW_BOOKS_TARGET:
                    break

                if not isinstance(book_data, dict):
                    skipped_count += 1
                    continue

                gutenberg_id = book_data.get("id")

                if not isinstance(gutenberg_id, int):
                    skipped_count += 1
                    continue

                title = (
                    str(
                        book_data.get(
                            "title",
                            ""
                        )
                    ).strip()
                    or "Без названия"
                )

                author = format_author(
                    book_data.get("authors", [])
                    or []
                )

                print(
                    f"Проверяем: {title}"
                )

                if gutenberg_id in known_ids:
                    existing_count += 1

                    print(
                        "  Уже загружена — "
                        "пропускаем."
                    )

                    continue

                if book_exists_by_title_author(
                    db=db,
                    title=title,
                    author=author
                ):
                    existing_count += 1
                    known_ids.add(gutenberg_id)

                    print(
                        "  Название и автор уже есть "
                        "в базе — пропускаем."
                    )

                    continue

                if book_data.get("copyright") is True:
                    skipped_count += 1

                    print(
                        "  copyright=True — "
                        "пропускаем."
                    )

                    continue

                languages = (
                    book_data.get("languages")
                    or []
                )

                if LANGUAGE not in languages:
                    skipped_count += 1

                    print(
                        "  Книга не на английском — "
                        "пропускаем."
                    )

                    continue

                formats = (
                    book_data.get("formats")
                    or {}
                )

                text_url = choose_text_url(formats)

                if not text_url:
                    missing_text_count += 1

                    print(
                        "  Полный TXT отсутствует."
                    )

                    continue

                print(
                    "  Скачиваем полный текст..."
                )

                content = download_text(
                    session=session,
                    text_url=text_url
                )

                if not content:
                    missing_text_count += 1

                    print(
                        "  Книга не добавлена."
                    )

                    continue

                cover_url = choose_cover_url(formats)

                if cover_url:
                    print(
                        "  Обложка Gutendex найдена."
                    )
                else:
                    missing_cover_count += 1

                    print(
                        "  У Gutendex нет обложки. "
                        "Сайт покажет заглушку."
                    )

                try:
                    saved_book = save_new_book(
                        db=db,
                        book_data=book_data,
                        content=content,
                        text_url=text_url,
                        cover_url=cover_url
                    )

                except Exception as error:
                    db.rollback()
                    error_count += 1

                    print(
                        "  Ошибка сохранения: "
                        f"{error}"
                    )

                    continue

                known_ids.add(gutenberg_id)
                added_count += 1

                print(
                    f"  ДОБАВЛЕНО "
                    f"[{added_count}/"
                    f"{NEW_BOOKS_TARGET}]: "
                    f"{saved_book.title}"
                )

                print(
                    f"  Автор: "
                    f"{saved_book.author}"
                )

                print(
                    "  Объём текста: "
                    f"{len(content):,} символов"
                )

                print()

                time.sleep(
                    REQUEST_DELAY_SECONDS
                )

        print()
        print("=" * 65)
        print("Загрузка завершена")
        print(
            f"Добавлено новых книг: "
            f"{added_count}"
        )
        print(
            f"Уже существовало: "
            f"{existing_count}"
        )
        print(
            "Пропущено без полноценного текста: "
            f"{missing_text_count}"
        )
        print(
            "Книг без обложки Gutendex: "
            f"{missing_cover_count}"
        )
        print(
            "Пропущено по другим причинам: "
            f"{skipped_count}"
        )
        print(
            f"Недоступных страниц: "
            f"{failed_pages}"
        )
        print(f"Ошибок: {error_count}")

        if added_count < NEW_BOOKS_TARGET:
            print()
            print(
                "Не удалось добавить все книги "
                "за один запуск."
            )
            print(
                "Запустите файл повторно: "
                "уже добавленные книги будут "
                "автоматически пропущены."
            )

        print("=" * 65)

    finally:
        db.close()
        session.close()


if __name__ == "__main__":
    load_new_books()
