from datetime import datetime
from html import escape

from fastapi import APIRouter
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.responses import RedirectResponse
from sqlalchemy import func

from auth import COOKIE_NAME
from auth import create_session_token
from auth import get_current_user
from auth import hash_password
from auth import validate_registration
from auth import verify_password
from database import SessionLocal
from home_page import header_html
from home_page import render_home_page
from models import Book
from models import Library
from models import ReadingHistory
from models import User


router = APIRouter()

MIN_CONTENT_LENGTH = 3000


def safe(value) -> str:
    if value is None:
        return ""

    return escape(str(value))


def readable_books_query(db):
    return (
        db.query(Book)
        .filter(Book.content.isnot(None))
        .filter(
            func.length(
                func.trim(Book.content)
            ) >= MIN_CONTENT_LENGTH
        )
    )


def book_image(book: Book) -> str:
    return f"""
    <img
        src="{safe(book.cover)}"
        alt="Обложка книги {safe(book.title)}"
        loading="lazy"
        onerror="
            this.onerror=null;
            this.src='https://placehold.co/400x600/1f6f5f/ffffff?text=Нет+обложки';
        "
    >
    """


def auth_page(
    title: str,
    heading: str,
    form_html: str,
    error: str | None = None
) -> str:
    error_html = ""

    if error:
        error_html = f"""
        <div class="auth-error">
            {safe(error)}
        </div>
        """

    return f"""
    <!DOCTYPE html>

    <html lang="ru">
    <head>
        <meta charset="UTF-8">

        <meta
            name="viewport"
            content="width=device-width, initial-scale=1.0"
        >

        <title>{safe(title)} — BookHub</title>

        <link
            rel="stylesheet"
            href="/static/style.css"
        >

        <link
            rel="stylesheet"
            href="/static/auth.css"
        >
    </head>

    <body>
        {header_html(None)}

        <main class="auth-page">
            <section class="auth-card">
                <a class="auth-logo" href="/">
                    📚
                </a>

                <p class="eyebrow">
                    BookHub
                </p>

                <h1>{safe(heading)}</h1>

                {error_html}

                {form_html}
            </section>
        </main>
    </body>
    </html>
    """


def login_required_response() -> RedirectResponse:
    return RedirectResponse(
        url="/login",
        status_code=303
    )


def register_reading(
    db,
    user_id: int,
    book_id: int
) -> ReadingHistory:
    """
    Создаёт запись истории при первом открытии книги
    или обновляет время последнего чтения.
    """
    history_item = (
        db.query(ReadingHistory)
        .filter(
            ReadingHistory.user_id == user_id,
            ReadingHistory.book_id == book_id
        )
        .first()
    )

    if history_item:
        history_item.last_opened = datetime.utcnow()

    else:
        history_item = ReadingHistory(
            user_id=user_id,
            book_id=book_id,
            last_opened=datetime.utcnow(),
            progress=0
        )

        db.add(history_item)

    db.commit()
    db.refresh(history_item)

    return history_item


@router.get(
    "/",
    response_class=HTMLResponse
)
def home(request: Request):
    db = SessionLocal()

    try:
        current_user = get_current_user(
            request=request,
            db=db
        )

        books = (
            readable_books_query(db)
            .order_by(Book.id.desc())
            .all()
        )

        library_ids: set[int] = set()
        history_books: list[Book] = []

        if current_user:
            library_items = (
                db.query(Library)
                .filter(
                    Library.user_id == current_user.id
                )
                .all()
            )

            library_ids = {
                item.book_id
                for item in library_items
            }

            history_items = (
                db.query(ReadingHistory)
                .filter(
                    ReadingHistory.user_id
                    == current_user.id
                )
                .order_by(
                    ReadingHistory.last_opened.desc()
                )
                .limit(6)
                .all()
            )

            history_books = [
                item.book
                for item in history_items
                if item.book is not None
            ]

        return render_home_page(
            books=books,
            library_ids=library_ids,
            history_books=history_books,
            current_user=current_user
        )

    finally:
        db.close()


@router.get(
    "/register",
    response_class=HTMLResponse
)
def register_page():
    form_html = """
    <form
        class="auth-form"
        action="/register"
        method="post"
    >
        <label>
            Имя пользователя

            <input
                type="text"
                name="username"
                minlength="3"
                maxlength="50"
                required
                autocomplete="username"
            >
        </label>

        <label>
            Электронная почта

            <input
                type="email"
                name="email"
                required
                autocomplete="email"
            >
        </label>

        <label>
            Пароль

            <input
                type="password"
                name="password"
                minlength="6"
                required
                autocomplete="new-password"
            >
        </label>

        <label>
            Повторите пароль

            <input
                type="password"
                name="password_repeat"
                minlength="6"
                required
                autocomplete="new-password"
            >
        </label>

        <button class="button" type="submit">
            Создать аккаунт
        </button>
    </form>

    <p class="auth-switch">
        Уже есть аккаунт?
        <a href="/login">Войти</a>
    </p>
    """

    return auth_page(
        title="Регистрация",
        heading="Создайте аккаунт",
        form_html=form_html
    )


@router.post(
    "/register",
    response_class=HTMLResponse
)
async def register_user(
    request: Request
):
    from urllib.parse import parse_qs

    body = (
        await request.body()
    ).decode(
        "utf-8",
        errors="replace"
    )

    form_data = parse_qs(
        body,
        keep_blank_values=True
    )

    username = form_data.get(
        "username",
        [""]
    )[0]

    email = form_data.get(
        "email",
        [""]
    )[0]

    password = form_data.get(
        "password",
        [""]
    )[0]

    password_repeat = form_data.get(
        "password_repeat",
        [""]
    )[0]

    db = SessionLocal()

    try:
        error = validate_registration(
            db=db,
            username=username,
            email=email,
            password=password,
            password_repeat=password_repeat
        )

        if error:
            return auth_page(
                title="Регистрация",
                heading="Создайте аккаунт",
                form_html=register_page_form(),
                error=error
            )

        user = User(
            username=username.strip(),
            email=email.strip().lower(),
            password_hash=hash_password(password)
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        response = RedirectResponse(
            url="/",
            status_code=303
        )

        response.set_cookie(
            key=COOKIE_NAME,
            value=create_session_token(user.id),
            max_age=60 * 60 * 24 * 30,
            httponly=True,
            samesite="lax"
        )

        return response

    finally:
        db.close()


def register_page_form() -> str:
    return """
    <form
        class="auth-form"
        action="/register"
        method="post"
    >
        <label>
            Имя пользователя
            <input
                type="text"
                name="username"
                minlength="3"
                maxlength="50"
                required
            >
        </label>

        <label>
            Электронная почта
            <input
                type="email"
                name="email"
                required
            >
        </label>

        <label>
            Пароль
            <input
                type="password"
                name="password"
                minlength="6"
                required
            >
        </label>

        <label>
            Повторите пароль
            <input
                type="password"
                name="password_repeat"
                minlength="6"
                required
            >
        </label>

        <button class="button" type="submit">
            Создать аккаунт
        </button>
    </form>

    <p class="auth-switch">
        Уже есть аккаунт?
        <a href="/login">Войти</a>
    </p>
    """


@router.get(
    "/login",
    response_class=HTMLResponse
)
def login_page():
    return auth_page(
        title="Вход",
        heading="Войдите в BookHub",
        form_html=login_page_form()
    )


def login_page_form() -> str:
    return """
    <form
        class="auth-form"
        action="/login"
        method="post"
    >
        <label>
            Почта или имя пользователя

            <input
                type="text"
                name="login"
                required
                autocomplete="username"
            >
        </label>

        <label>
            Пароль

            <input
                type="password"
                name="password"
                required
                autocomplete="current-password"
            >
        </label>

        <button class="button" type="submit">
            Войти
        </button>
    </form>

    <p class="auth-switch">
        Нет аккаунта?
        <a href="/register">Зарегистрироваться</a>
    </p>
    """


@router.post(
    "/login",
    response_class=HTMLResponse
)
async def login_user(
    request: Request
):
    from urllib.parse import parse_qs

    body = (
        await request.body()
    ).decode(
        "utf-8",
        errors="replace"
    )

    form_data = parse_qs(
        body,
        keep_blank_values=True
    )

    login = form_data.get(
        "login",
        [""]
    )[0]

    password = form_data.get(
        "password",
        [""]
    )[0]

    db = SessionLocal()

    try:
        login_value = login.strip()

        user = (
            db.query(User)
            .filter(
                (
                    User.username == login_value
                )
                | (
                    User.email
                    == login_value.lower()
                )
            )
            .first()
        )

        if (
            not user
            or not verify_password(
                password,
                user.password_hash
            )
        ):
            return auth_page(
                title="Вход",
                heading="Войдите в BookHub",
                form_html=login_page_form(),
                error="Неверный логин или пароль."
            )

        response = RedirectResponse(
            url="/",
            status_code=303
        )

        response.set_cookie(
            key=COOKIE_NAME,
            value=create_session_token(user.id),
            max_age=60 * 60 * 24 * 30,
            httponly=True,
            samesite="lax"
        )

        return response

    finally:
        db.close()


@router.get("/logout")
def logout():
    response = RedirectResponse(
        url="/",
        status_code=303
    )

    response.delete_cookie(COOKIE_NAME)

    return response


@router.get("/books")
def get_books():
    db = SessionLocal()

    try:
        return (
            readable_books_query(db)
            .order_by(Book.id.desc())
            .all()
        )

    finally:
        db.close()


@router.get(
    "/book/{book_id}",
    response_class=HTMLResponse
)
def book_page(
    request: Request,
    book_id: int
):
    db = SessionLocal()

    try:
        current_user = get_current_user(
            request=request,
            db=db
        )

        book = (
            readable_books_query(db)
            .filter(Book.id == book_id)
            .first()
        )

        if not book:
            return HTMLResponse(
                "<h1>Книга недоступна</h1>",
                status_code=404
            )

        library_item = None

        if current_user:
            library_item = (
                db.query(Library)
                .filter(
                    Library.user_id
                    == current_user.id,
                    Library.book_id == book.id
                )
                .first()
            )

        if not current_user:
            library_button = """
            <a
                class="button button-secondary"
                href="/login"
            >
                Войти, чтобы добавить
            </a>
            """
        elif library_item:
            library_button = f"""
            <a
                class="button button-danger"
                href="/library/remove/{book.id}"
            >
                Удалить из библиотеки
            </a>
            """
        else:
            library_button = f"""
            <a
                class="button button-secondary"
                href="/library/add/{book.id}"
            >
                ＋ Добавить в библиотеку
            </a>
            """

        return f"""
        <!DOCTYPE html>

        <html lang="ru">
        <head>
            <meta charset="UTF-8">

            <meta
                name="viewport"
                content="width=device-width, initial-scale=1.0"
            >

            <title>
                {safe(book.title)} — BookHub
            </title>

            <link
                rel="stylesheet"
                href="/static/style.css"
            >
        </head>

        <body>
            {header_html(current_user)}

            <main class="container">
                <section class="book-page">
                    <div class="book-cover-wrapper">
                        {book_image(book)}
                    </div>

                    <div class="book-details">
                        <p class="eyebrow">
                            {safe(book.year) or "Год не указан"}
                        </p>

                        <h1>{safe(book.title)}</h1>

                        <h2>
                            {safe(book.author) or "Автор не указан"}
                        </h2>

                        <p class="description">
                            {
                                safe(book.description)
                                or "Описание отсутствует"
                            }
                        </p>

                        <div class="actions">
                            <a
                                class="button"
                                href="/read/{book.id}"
                            >
                                Читать книгу
                            </a>

                            {library_button}
                        </div>

                        <a
                            class="back-link"
                            href="/#catalog"
                        >
                            ← Вернуться в каталог
                        </a>
                    </div>
                </section>
            </main>
        </body>
        </html>
        """

    finally:
        db.close()


@router.get("/library/add/{book_id}")
def add_to_library(
    request: Request,
    book_id: int
):
    db = SessionLocal()

    try:
        current_user = get_current_user(
            request=request,
            db=db
        )

        if not current_user:
            return login_required_response()

        book = (
            readable_books_query(db)
            .filter(Book.id == book_id)
            .first()
        )

        if not book:
            return RedirectResponse(
                url="/",
                status_code=303
            )

        exists = (
            db.query(Library)
            .filter(
                Library.user_id
                == current_user.id,
                Library.book_id == book_id
            )
            .first()
        )

        if not exists:
            db.add(
                Library(
                    user_id=current_user.id,
                    book_id=book_id
                )
            )

            db.commit()

        return RedirectResponse(
            url="/profile",
            status_code=303
        )

    finally:
        db.close()


@router.get("/library/remove/{book_id}")
def remove_from_library(
    request: Request,
    book_id: int
):
    db = SessionLocal()

    try:
        current_user = get_current_user(
            request=request,
            db=db
        )

        if not current_user:
            return login_required_response()

        item = (
            db.query(Library)
            .filter(
                Library.user_id
                == current_user.id,
                Library.book_id == book_id
            )
            .first()
        )

        if item:
            db.delete(item)
            db.commit()

        return RedirectResponse(
            url="/profile",
            status_code=303
        )

    finally:
        db.close()


@router.get("/history/remove/{book_id}")
def remove_from_history(
    request: Request,
    book_id: int
):
    db = SessionLocal()

    try:
        current_user = get_current_user(
            request=request,
            db=db
        )

        if not current_user:
            return login_required_response()

        item = (
            db.query(ReadingHistory)
            .filter(
                ReadingHistory.user_id
                == current_user.id,
                ReadingHistory.book_id == book_id
            )
            .first()
        )

        if item:
            db.delete(item)
            db.commit()

        return RedirectResponse(
            url="/profile",
            status_code=303
        )

    finally:
        db.close()


@router.get(
    "/profile",
    response_class=HTMLResponse
)
def profile(request: Request):
    db = SessionLocal()

    try:
        current_user = get_current_user(
            request=request,
            db=db
        )

        if not current_user:
            return login_required_response()

        library_items = (
            db.query(Library)
            .filter(
                Library.user_id == current_user.id
            )
            .order_by(Library.id.desc())
            .all()
        )

        history_items = (
            db.query(ReadingHistory)
            .filter(
                ReadingHistory.user_id
                == current_user.id
            )
            .order_by(
                ReadingHistory.last_opened.desc()
            )
            .limit(8)
            .all()
        )

        library_cards = ""

        for item in library_items:
            book = item.book

            if not book:
                continue

            library_cards += f"""
            <article class="card">
                {book_image(book)}

                <div class="info">
                    <h2>{safe(book.title)}</h2>

                    <p>
                        {safe(book.author) or "Автор не указан"}
                    </p>

                    <div class="card-actions">
                        <a
                            class="button"
                            href="/read/{book.id}"
                        >
                            Читать
                        </a>

                        <a
                            class="button button-secondary"
                            href="/book/{book.id}"
                        >
                            Подробнее
                        </a>

                        <a
                            class="button button-danger"
                            href="/library/remove/{book.id}"
                        >
                            Удалить
                        </a>
                    </div>
                </div>
            </article>
            """

        history_cards = ""

        for item in history_items:
            book = item.book

            if not book:
                continue

            opened_at = item.last_opened.strftime(
                "%d.%m.%Y в %H:%M"
            )

            history_cards += f"""
            <article class="history-card">
                <img
                    src="{safe(book.cover)}"
                    alt="{safe(book.title)}"
                >

                <div class="history-info">
                    <p class="eyebrow">
                        Последнее чтение: {opened_at}
                    </p>

                    <h3>{safe(book.title)}</h3>

                    <p>
                        {safe(book.author) or "Автор не указан"}
                    </p>

                    <div class="reading-progress-block">
                        <div class="reading-progress-label">
                            <span>Прочитано</span>
                            <strong>{max(0, min(100, item.progress or 0))}%</strong>
                        </div>

                        <div class="reading-progress-track">
                            <div
                                class="reading-progress-fill"
                                style="width:{max(0, min(100, item.progress or 0))}%"
                            ></div>
                        </div>
                    </div>

                    <div class="history-actions">
                        <a
                            class="button"
                            href="/read/{book.id}"
                        >
                            Продолжить
                        </a>

                        <a
                            class="button button-danger"
                            href="/history/remove/{book.id}"
                        >
                            Удалить из истории
                        </a>
                    </div>
                </div>
            </article>
            """

        return f"""
        <!DOCTYPE html>

        <html lang="ru">
        <head>
            <meta charset="UTF-8">

            <meta
                name="viewport"
                content="width=device-width, initial-scale=1.0"
            >

            <title>
                Профиль — BookHub
            </title>

            <link
                rel="stylesheet"
                href="/static/style.css"
            >

            <link
                rel="stylesheet"
                href="/static/progress.css"
            >
        </head>

        <body>
            {header_html(current_user)}

            <main class="container">
                <section class="profile-heading">
                    <div class="avatar">
                        {safe(current_user.username[:1].upper())}
                    </div>

                    <div>
                        <p class="eyebrow">
                            Профиль читателя
                        </p>

                        <h1>
                            {safe(current_user.username)}
                        </h1>

                        <p>
                            {safe(current_user.email)}
                        </p>

                        <p>
                            Книг в библиотеке:
                            {len(library_items)}
                        </p>
                    </div>
                </section>

                <h2 class="section-title">
                    Продолжить читать
                </h2>

                {
                    f'<section class="history-list">{history_cards}</section>'
                    if history_cards
                    else '<section class="empty-state"><p>История чтения пока пустая.</p></section>'
                }

                <h2 class="section-title">
                    Моя библиотека
                </h2>

                {
                    f'<section class="books">{library_cards}</section>'
                    if library_cards
                    else '<section class="empty-state"><p>Библиотека пока пустая.</p><a class="button" href="/#catalog">Перейти в каталог</a></section>'
                }
            </main>
        </body>
        </html>
        """

    finally:
        db.close()


@router.post("/api/progress/{book_id}")
async def save_reading_progress(
    request: Request,
    book_id: int
):
    """
    Сохраняет процент прочтения для текущего пользователя.
    """
    db = SessionLocal()

    try:
        current_user = get_current_user(
            request=request,
            db=db
        )

        if not current_user:
            return JSONResponse(
                {
                    "saved": False,
                    "reason": "authentication_required"
                },
                status_code=401
            )

        book = (
            readable_books_query(db)
            .filter(Book.id == book_id)
            .first()
        )

        if not book:
            return JSONResponse(
                {
                    "saved": False,
                    "reason": "book_not_found"
                },
                status_code=404
            )

        try:
            payload = await request.json()
            progress = int(payload.get("progress", 0))
        except (
            ValueError,
            TypeError
        ):
            return JSONResponse(
                {
                    "saved": False,
                    "reason": "invalid_progress"
                },
                status_code=400
            )

        progress = max(
            0,
            min(100, progress)
        )

        history_item = (
            db.query(ReadingHistory)
            .filter(
                ReadingHistory.user_id
                == current_user.id,
                ReadingHistory.book_id == book_id
            )
            .first()
        )

        if not history_item:
            history_item = ReadingHistory(
                user_id=current_user.id,
                book_id=book_id,
                last_opened=datetime.utcnow(),
                progress=progress
            )

            db.add(history_item)

        else:
            history_item.progress = progress
            history_item.last_opened = datetime.utcnow()

        db.commit()

        return {
            "saved": True,
            "progress": progress
        }

    finally:
        db.close()


@router.get(
    "/read/{book_id}",
    response_class=HTMLResponse
)
def read_book(
    request: Request,
    book_id: int
):
    db = SessionLocal()

    try:
        current_user = get_current_user(
            request=request,
            db=db
        )

        book = (
            readable_books_query(db)
            .filter(Book.id == book_id)
            .first()
        )

        if not book:
            return HTMLResponse(
                "<h1>Книга недоступна</h1>",
                status_code=404
            )

        initial_progress = 0

        if current_user:
            history_item = register_reading(
                db=db,
                user_id=current_user.id,
                book_id=book.id
            )

            initial_progress = max(
                0,
                min(
                    100,
                    history_item.progress or 0
                )
            )

        account_message = (
            ""
            if current_user
            else """
            <div class="reader-login-note">
                Войдите в аккаунт, чтобы сохранять прогресс чтения.
            </div>
            """
        )

        return f"""
        <!DOCTYPE html>

        <html lang="ru">
        <head>
            <meta charset="UTF-8">

            <meta
                name="viewport"
                content="width=device-width, initial-scale=1.0"
            >

            <title>
                {safe(book.title)} — чтение
            </title>

            <link
                rel="stylesheet"
                href="/static/style.css"
            >

            <link
                rel="stylesheet"
                href="/static/progress.css"
            >
        </head>

        <body class="reader-body">
            <div class="reader-page-progress">
                <div
                    id="readerPageProgressFill"
                    class="reader-page-progress-fill"
                    style="width:{initial_progress}%"
                ></div>
            </div>

            <div class="reader-toolbar">
                <a href="/book/{book.id}">
                    ← К книге
                </a>

                <div class="reader-toolbar-status">
                    <span id="progressText">
                        {initial_progress}% прочитано
                    </span>

                    <button
                        id="fontDecreaseButton"
                        type="button"
                    >
                        A−
                    </button>

                    <button
                        id="fontIncreaseButton"
                        type="button"
                    >
                        A+
                    </button>

                    <button
                        id="themeButton"
                        type="button"
                    >
                        Тема
                    </button>
                </div>
            </div>

            {account_message}

            <main class="reader">
                <p class="eyebrow">
                    Чтение
                </p>

                <h1>{safe(book.title)}</h1>

                <h2>
                    {safe(book.author) or "Автор не указан"}
                </h2>

                <article
                    id="bookText"
                    class="book-text"
                >
                    {safe(book.content)}
                </article>
            </main>

            <script>
                const bookId = {book.id};
                const canSaveProgress = {
                    "true"
                    if current_user
                    else "false"
                };
                const initialProgress = {initial_progress};

                const bookText =
                    document.getElementById("bookText");

                const progressText =
                    document.getElementById("progressText");

                const progressFill =
                    document.getElementById(
                        "readerPageProgressFill"
                    );

                const fontDecreaseButton =
                    document.getElementById(
                        "fontDecreaseButton"
                    );

                const fontIncreaseButton =
                    document.getElementById(
                        "fontIncreaseButton"
                    );

                const themeButton =
                    document.getElementById(
                        "themeButton"
                    );

                let fontSize = 20;
                let saveTimer = null;
                let lastSavedProgress = initialProgress;

                function clamp(value, minimum, maximum) {{
                    return Math.max(
                        minimum,
                        Math.min(maximum, value)
                    );
                }}

                function calculateProgress() {{
                    const scrollableHeight =
                        document.documentElement.scrollHeight
                        - window.innerHeight;

                    if (scrollableHeight <= 0) {{
                        return 100;
                    }}

                    return clamp(
                        Math.round(
                            (
                                window.scrollY
                                / scrollableHeight
                            ) * 100
                        ),
                        0,
                        100
                    );
                }}

                function updateProgressView(progress) {{
                    progressFill.style.width =
                        progress + "%";

                    progressText.textContent =
                        progress + "% прочитано";
                }}

                async function saveProgress(
                    progress,
                    useBeacon = false
                ) {{
                    if (!canSaveProgress) {{
                        return;
                    }}

                    const normalizedProgress =
                        clamp(
                            Math.round(progress),
                            0,
                            100
                        );

                    if (
                        normalizedProgress
                        === lastSavedProgress
                    ) {{
                        return;
                    }}

                    const body = JSON.stringify({{
                        progress: normalizedProgress
                    }});

                    if (
                        useBeacon
                        && navigator.sendBeacon
                    ) {{
                        const blob = new Blob(
                            [body],
                            {{
                                type: "application/json"
                            }}
                        );

                        navigator.sendBeacon(
                            "/api/progress/" + bookId,
                            blob
                        );

                        lastSavedProgress =
                            normalizedProgress;

                        return;
                    }}

                    try {{
                        const response = await fetch(
                            "/api/progress/" + bookId,
                            {{
                                method: "POST",
                                headers: {{
                                    "Content-Type":
                                        "application/json"
                                }},
                                body: body
                            }}
                        );

                        if (response.ok) {{
                            lastSavedProgress =
                                normalizedProgress;
                        }}
                    }} catch (error) {{
                        console.log(
                            "Не удалось сохранить прогресс",
                            error
                        );
                    }}
                }}

                function scheduleProgressSave(progress) {{
                    if (saveTimer) {{
                        clearTimeout(saveTimer);
                    }}

                    saveTimer = setTimeout(
                        function () {{
                            saveProgress(progress);
                        }},
                        900
                    );
                }}

                function handleScroll() {{
                    const progress =
                        calculateProgress();

                    updateProgressView(progress);
                    scheduleProgressSave(progress);
                }}

                function changeFont(value) {{
                    fontSize = clamp(
                        fontSize + value,
                        14,
                        34
                    );

                    bookText.style.fontSize =
                        fontSize + "px";

                    handleScroll();
                }}

                function toggleTheme() {{
                    document.body.classList.toggle(
                        "dark-theme"
                    );
                }}

                function restorePosition() {{
                    if (initialProgress <= 0) {{
                        updateProgressView(0);
                        return;
                    }}

                    requestAnimationFrame(
                        function () {{
                            const scrollableHeight =
                                document.documentElement
                                    .scrollHeight
                                - window.innerHeight;

                            const targetPosition =
                                scrollableHeight
                                * initialProgress
                                / 100;

                            window.scrollTo(
                                0,
                                targetPosition
                            );

                            updateProgressView(
                                initialProgress
                            );
                        }}
                    );
                }}

                fontDecreaseButton.addEventListener(
                    "click",
                    function () {{
                        changeFont(-2);
                    }}
                );

                fontIncreaseButton.addEventListener(
                    "click",
                    function () {{
                        changeFont(2);
                    }}
                );

                themeButton.addEventListener(
                    "click",
                    toggleTheme
                );

                window.addEventListener(
                    "scroll",
                    handleScroll,
                    {{
                        passive: true
                    }}
                );

                window.addEventListener(
                    "pagehide",
                    function () {{
                        saveProgress(
                            calculateProgress(),
                            true
                        );
                    }}
                );

                window.addEventListener(
                    "DOMContentLoaded",
                    restorePosition
                );
            </script>
        </body>
        </html>
        """

    finally:
        db.close()
